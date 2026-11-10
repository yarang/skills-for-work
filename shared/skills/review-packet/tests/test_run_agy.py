"""run_agy.sh 테스트 — 가짜 agy 실행 파일로 인자 순서와 종료 코드를 검증한다."""
import os
import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_agy.sh"


def make_fake_agy(bindir: pathlib.Path, log: pathlib.Path, output: str, exit_code: int) -> None:
    agy = bindir / "agy"
    agy.write_text(
        "#!/bin/sh\n"
        ": > \"$FAKE_AGY_LOG\"\n"
        "for a in \"$@\"; do printf '%s\\n' \"$a\" >> \"$FAKE_AGY_LOG\"; done\n"
        f"printf '{output}'\n"
        f"exit {exit_code}\n",
    )
    agy.chmod(0o755)


def run_agy(bindir: pathlib.Path, repo: pathlib.Path, packet: pathlib.Path, out: pathlib.Path,
            log: pathlib.Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "FAKE_AGY_LOG": str(log)}
    return subprocess.run(["bash", str(SCRIPT), str(repo), str(packet), str(out)],
                          capture_output=True, text=True, env=env, timeout=30)


def setup(tmp_path: pathlib.Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = tmp_path / "packet.md"
    packet.write_text("꾸러미 첫 줄\n꾸러미 둘째 줄\n")
    return bindir, repo, packet, tmp_path / "args.log", tmp_path / "result.md"


def test_argument_order(tmp_path):
    """인자 순서가 --mode plan --print <꾸러미 내용>인지 (--print가 맨 뒤, 지시문이 바로 뒤)."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="FAKE RESULT\\n", exit_code=0)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 0, result.stderr
    lines = log.read_text().splitlines()
    assert lines[:3] == ["--mode", "plan", "--print"]
    assert lines[3:] == ["꾸러미 첫 줄", "꾸러미 둘째 줄"]
    assert out.read_text() == "FAKE RESULT\n"


def test_empty_output_exits_2(tmp_path):
    """agy가 아무것도 출력하지 않으면(성공해도) 종료 코드 2."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="", exit_code=0)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 2
    assert "비어" in result.stderr


def test_agy_exit_code_passes_through(tmp_path):
    """agy의 종료 코드를 그대로 돌려주는지."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="partial\\n", exit_code=3)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 3


def test_runs_inside_repo(tmp_path):
    """cd <저장소> 안에서 agy를 부르는지."""
    bindir, repo, packet, log, out = setup(tmp_path)
    marker = repo / "here.txt"
    marker.write_text("repo marker\n")
    agy = bindir / "agy"
    agy.write_text(
        "#!/bin/sh\n"
        "for a in \"$@\"; do :; done\n"
        "if [ -f here.txt ]; then printf 'IN-REPO\\n'; fi\n"
        "exit 0\n",
    )
    agy.chmod(0o755)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == "IN-REPO\n"
