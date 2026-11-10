"""exaone_review.py 테스트 — 가짜 SSE 서버로만 검증한다. 실제 API는 부르지 않는다."""
import json
import os
import pathlib
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "exaone_review.py"
KEY_ENV_NAMES = ("EXAONE_API_KEY", "EXAONE_BASE_URL", "EXAONE_MODEL", "LLM_ENV_FILE")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Handler(BaseHTTPRequestHandler):
    """큐의 응답을 순서대로 돌려주고, 요청 헤더·본문을 `seen`에 기록한다."""

    queue: list = []   # [(status, headers, body_bytes)]
    seen: list = []    # [{"headers": {...}, "body": str}]

    def log_message(self, *args):  # 표준 로그를 끈다
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        Handler.seen.append({"headers": dict(self.headers), "body": body})
        status, headers, payload = Handler.queue.pop(0)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def sse(chunks: list) -> bytes:
    """딕셔너리 목록을 SSE data: 줄로 바꾼다."""
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def reply(chunks: list, status: int = 200, headers: dict | None = None) -> tuple:
    return (status, headers or {}, sse(chunks))


def delta(text: str = "", reasoning: str = "", finish=None, usage=None) -> dict:
    chunk: dict = {"choices": [{"delta": {}, "finish_reason": finish}]}
    if text:
        chunk["choices"][0]["delta"]["content"] = text
    if reasoning:
        chunk["choices"][0]["delta"]["reasoning_content"] = reasoning
    if usage:
        chunk["usage"] = usage
    return chunk


@pytest.fixture()
def server():
    Handler.queue, Handler.seen = [], []
    httpd = ThreadingHTTPServer(("127.0.0.1", free_port()), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1", Handler
    httpd.shutdown()
    httpd.server_close()


def run_script(args: list, tmp_path: pathlib.Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in KEY_ENV_NAMES}
    env["EXAONE_API_KEY"] = "env-key-0000"  # 기본: 키 파일을 읽지 않게 한다
    env.update(env_extra or {})
    packet = tmp_path / "packet.md"
    if not packet.exists():
        packet.write_text("# 검토 꾸러미\n- 역할: work-standards:reviewer\n- 관점: code\n")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--packet", str(packet), "--out", str(tmp_path / "out.md"), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def request_body(handler) -> dict:
    assert handler.seen, "요청이 서버에 닿지 않았습니다"
    return json.loads(handler.seen[0]["body"])


def user_content(handler) -> str:
    body = request_body(handler)
    return next(m for m in body["messages"] if m["role"] == "user")["content"]


def test_sse_chunks_concat(tmp_path, server):
    """SSE 조각을 이어 붙여 결과 파일에 쓰는지."""
    base, handler = server
    handler.queue = [reply([
        delta(text="첫 문단 "),
        delta(text="둘째 문단", finish="stop", usage={"reasoning_tokens": 7}),
    ])]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    text = (tmp_path / "out.md").read_text()
    assert "첫 문단 둘째 문단" in text


def test_request_has_stream_effort_model(tmp_path, server):
    """요청 본문에 stream: true, reasoning_effort "high"(기본), 모델 이름이 들어가는지."""
    base, handler = server
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    body = request_body(handler)
    assert body["stream"] is True
    assert body["reasoning_effort"] == "high"
    assert body["model"] == "k-exaone_v2.5"
    assert any(m["role"] == "system" for m in body["messages"])


def test_effort_flag_overrides_default(tmp_path, server):
    """--effort를 주면 기본 high를 덮어쓰는지."""
    base, handler = server
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script(["--effort", "max"], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert request_body(handler)["reasoning_effort"] == "max"


def test_retry_after_429(tmp_path, server):
    """429 한 번 뒤 200이면 재시도해 성공하는지."""
    base, handler = server
    handler.queue = [
        (429, {"Retry-After": "0"}, b'{"error": "rate limited"}'),
        reply([delta(text="재시도 성공", finish="stop")]),
    ]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert "재시도 성공" in (tmp_path / "out.md").read_text()
    assert len(handler.seen) == 2


def test_http_500_exits_1(tmp_path, server):
    """500이면 상태 코드를 stderr에 적고 종료 코드 1."""
    base, handler = server
    handler.queue = [(500, {}, b'{"error": "boom"}')]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 1
    assert "500" in result.stderr
    assert "boom" in result.stderr


def test_key_file_reads_only_exaone_line(tmp_path, server):
    """llm.env에 다른 키 줄이 있어도 EXAONE_API_KEY만 Authorization에 쓰이는지."""
    base, handler = server
    env_file = tmp_path / "llm.env"
    env_file.write_text('OTHER_API_KEY=other-secret-111\nEXAONE_API_KEY="file-key-9999"\n'
                        'THIRD_TOKEN=third-secret-333\n')
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    env = {"EXAONE_BASE_URL": base, "LLM_ENV_FILE": str(env_file)}
    env = {k: v for k, v in env.items()}
    full = {k: v for k, v in os.environ.items() if k not in KEY_ENV_NAMES}
    full.update(env)
    packet = tmp_path / "packet.md"
    packet.write_text("# 검토 꾸러미\n- 역할: work-standards:reviewer\n- 관점: code\n")
    out = tmp_path / "out.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--packet", str(packet), "--out", str(out)],
        capture_output=True, text=True, env=full, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert handler.seen[0]["headers"].get("Authorization") == "Bearer file-key-9999"
    dumped = json.dumps(handler.seen)
    assert "other-secret-111" not in dumped and "third-secret-333" not in dumped


def test_env_key_beats_file(tmp_path, server):
    """환경 변수 EXAONE_API_KEY가 있으면 키 파일보다 우선하는지."""
    base, handler = server
    env_file = tmp_path / "llm.env"
    env_file.write_text("EXAONE_API_KEY=file-key-9999\n")
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base, "LLM_ENV_FILE": str(env_file),
                                       "EXAONE_API_KEY": "env-key-4242"})
    assert result.returncode == 0, result.stderr
    assert handler.seen[0]["headers"].get("Authorization") == "Bearer env-key-4242"


def test_attached_file_gets_line_numbers(tmp_path, server):
    """첨부 파일에 줄 번호가 붙는지."""
    base, handler = server
    target = tmp_path / "code.py"
    target.write_text("alpha\nbeta\n")
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script([str(target)], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    content = user_content(handler)
    assert "   1  alpha" in content
    assert "   2  beta" in content
    assert "code.py" in content


def test_diff_bundle_includes_git_diff(tmp_path, server):
    """--diff를 주면 git diff <기준>..HEAD가 줄 번호와 함께 묶이는지."""
    base, handler = server
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com"); git("config", "user.name", "t")
    (repo / "a.txt").write_text("one\n")
    git("add", "."); git("commit", "-qm", "first")
    (repo / "a.txt").write_text("one\ntwo\n")
    git("add", "."); git("commit", "-qm", "second")
    base_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD~1"],
                              capture_output=True, text=True, check=True).stdout.strip()
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script(["--diff", str(repo), base_sha], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    content = user_content(handler)
    assert f"git diff {base_sha}..HEAD" in content
    assert "+two" in content


def test_finish_length_warns(tmp_path, server):
    """finish_reason이 length면 경고를 stderr에 남기는지."""
    base, handler = server
    handler.queue = [reply([delta(text="잘린 답", finish="length")])]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert "잘렸" in result.stderr


def test_empty_data_lines_ignored(tmp_path, server):
    """SSE 스트림의 빈 data: 줄은 건너뛰는지."""
    base, handler = server
    body = b"data: \n\n" + sse([delta(text="빈 줄 무시 후 본문", finish="stop")])
    handler.queue = [(200, {}, body)]
    result = run_script([], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert "빈 줄 무시 후 본문" in (tmp_path / "out.md").read_text()


def test_secret_attachment_blocks_send(tmp_path, server):
    """가짜 키가 든 첨부는 전송하지 않고 종료 코드 3. stderr에는 값이 없어야 한다."""
    base, handler = server
    leak = tmp_path / "notes.md"
    leak.write_text("첫 줄\nGITHUB_TOKEN=ghp_0123456789abcdefghijklmnop\n셋째 줄\n")
    result = run_script([str(leak)], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 3
    assert "ghp_0123456789" not in result.stderr      # 값은 출력하지 않음
    assert str(leak) in result.stderr                 # 어느 입력인지
    assert ":2" in result.stderr                      # 몇 번째 줄인지
    assert not handler.seen                           # 전송도 하지 않음


def test_allow_secret_like_sends(tmp_path, server):
    """--allow-secret-like면 비밀값 검사를 건너뛰고 전송한다."""
    base, handler = server
    leak = tmp_path / "notes.md"
    leak.write_text("GITHUB_TOKEN=ghp_0123456789abcdefghijklmnop\n")
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script(["--allow-secret-like", str(leak)], tmp_path,
                        {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert "ghp_0123456789" in user_content(handler)


def test_plain_words_do_not_block(tmp_path, server):
    """일반 단어(token, password)나 짧은 값만으로는 검사에 걸리지 않는다."""
    base, handler = server
    doc = tmp_path / "doc.md"
    doc.write_text("token과 password라는 단어가 든 보통 문서\nMY_TOKEN=short\n")
    handler.queue = [reply([delta(text="ok", finish="stop")])]
    result = run_script([str(doc)], tmp_path, {"EXAONE_BASE_URL": base})
    assert result.returncode == 0, result.stderr
    assert handler.seen
