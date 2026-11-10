"""hooks/write_guard.py 수용 테스트.

계약: docs/design.md 「쓰기 보호」. hook은 표준 입력 JSON 한 개를 받고,
막을 때는 표준 출력에 PreToolUse `permissionDecision: deny` JSON을 내거나(종료 코드 0),
입력이 잘못되면 stderr에 메시지를 쓰고 종료 코드 2로 끝납니다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "hooks" / "write_guard.py"


def run_guard(payload) -> subprocess.CompletedProcess:
    assert GUARD.is_file(), f"스크립트 없음: {GUARD}"
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD)], input=data, capture_output=True, text=True, timeout=10
    )


def denied(proc: subprocess.CompletedProcess) -> bool:
    if proc.returncode == 2:
        return True
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False
    out = json.loads(proc.stdout)
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def deny_reason(proc: subprocess.CompletedProcess) -> str:
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    return out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


@pytest.fixture
def repo(tmp_path):
    """원고 저장소: 루트에 manifest.md, 계획·원고·검토·조사·예제 폴더."""
    root = tmp_path / "book"
    for sub in ("plans/vol1/ch01", "plans/front/preface", "manuscript/vol1/part1/images",
                "reviews", "research", "examples/vol1"):
        (root / sub).mkdir(parents=True)
    (root / "manifest.md").write_text("# manifest\n", encoding="utf-8")
    return root


def call(repo, agent, tool, path, key="file_path", cwd=None):
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": str(cwd or repo),
        "tool_name": tool,
        "tool_input": {} if path is None else {key: str(path)},
    }
    if agent is not None:
        payload["agent_type"] = agent
    return run_guard(payload)


# --- 메인 대화와 다른 플러그인은 검사하지 않음 ---------------------------------

def test_main_conversation_allowed(repo):
    proc = call(repo, None, "Write", repo / "manuscript/vol1/part1/ch01.md")
    assert not denied(proc)
    assert not proc.stdout.strip()


def test_other_plugin_agent_allowed(repo):
    assert not denied(call(repo, "docu-writer:writer", "Write", repo / "manifest.md"))


def test_other_tool_allowed(repo):
    # Bash는 검사 도구가 아니므로 흘려 보냅니다.
    assert not denied(call(repo, "book-writer:editor", "Bash", "reviews/x.md", key="command"))


# --- 역할별 허용·거부 ------------------------------------------------------------

@pytest.mark.parametrize("role,rel,ok", [
    ("planner", "plans/vol1/ch01/story.md", True),
    ("planner", "plans/front/preface/story.md", True),      # 앞붙이 계획 (#2)
    ("planner", "plans/vol1/ch01/story.rev1.md", True),     # 승인 수정안 (#4)
    ("planner", "manuscript/vol1/part1/ch01.md", False),
    ("writer", "manuscript/vol1/part1/ch01.md", True),
    ("writer", "manuscript/vol1/part1/images/fig1.png", True),
    ("writer", "manifest.md", True),
    ("writer", "examples/vol1/start.md", True),
    ("writer", "plans/vol1/ch01/story.md", False),
    ("writer", "reviews/editor-vol1-ch01-2026-11-10-r1.md", False),
    ("editor", "reviews/editor-vol1-ch01-2026-11-10-r1.md", True),
    ("editor", "reviews/sub/nested.md", True),
    ("editor", "manuscript/vol1/part1/ch01.md", False),
    ("researcher", "research/agents-2026-11-10.md", True),
    ("researcher", "manuscript/vol1/part1/ch01.md", False),
    ("capturer", "manuscript/vol1/part1/images/fig2-1.png", True),
    ("capturer", "research/measure-vol1-ch02-2026-11-10.md", True),
    ("capturer", "manuscript/vol1/part1/ch01.md", False),
    ("capturer", "research/topic.md", False),
    ("formatter", "manuscript/vol1/part1/ch01.md", False),  # 정의되지 않은 역할
])
def test_role_paths(repo, role, rel, ok):
    assert denied(call(repo, f"book-writer:{role}", "Write", repo / rel)) is not ok


def test_relative_path_resolved_against_cwd(repo):
    assert not denied(call(repo, "book-writer:planner", "Write", "plans/vol1/ch01/story.md"))


def test_root_found_from_subdirectory(repo, tmp_path):
    # cwd가 원고 깊숙이 있어도 위로 올라 manifest.md가 있는 곳을 원고 루트로 삼습니다.
    cwd = repo / "manuscript" / "vol1" / "part1"
    assert not denied(call(repo, "book-writer:writer", "Write",
                           repo / "manuscript/vol1/part1/ch01.md", cwd=cwd))


def test_root_normalized_when_cwd_via_symlink(repo, tmp_path):
    # 심볼릭 링크를 거친 cwd 아래에 manifest.md가 있어도, find_root가 돌려준
    # 루트가 대상 경로와 같은 방식(realpath)으로 정규화되어 비교됩니다.
    link = tmp_path / "book-link"
    os.symlink(repo, link)
    cwd = link / "manuscript" / "vol1"
    assert not denied(call(repo, "book-writer:writer", "Write",
                           repo / "manuscript/vol1/part1/ch01.md", cwd=cwd))


def test_no_manifest_root_is_cwd(tmp_path):
    # manifest.md가 없으면 cwd 자체가 루트이므로, cwd 안 plans/** 는 허용됩니다.
    cwd = tmp_path / "plain"
    (cwd / "plans").mkdir(parents=True)
    assert not denied(call(cwd, "book-writer:planner", "Write",
                           cwd / "plans/story.md", cwd=cwd))


# --- planner: 승인된 계획 문서 보호 ----------------------------------------------

def test_planner_approved_file_denied(repo):
    story = repo / "plans/vol1/ch01/story.md"
    story.write_text("상태: 승인 (2026-11-01)\n", encoding="utf-8")
    assert denied(call(repo, "book-writer:planner", "Edit", story))


def test_planner_approved_blockquote_bold_denied(repo):
    story = repo / "plans/vol1/ch01/story.md"
    story.write_text("# 이야기\n\n> 상태: **승인** (2026-11-01)\n", encoding="utf-8")
    assert denied(call(repo, "book-writer:planner", "Edit", story))


def test_planner_proposed_file_allowed(repo):
    story = repo / "plans/vol1/ch01/story.md"
    story.write_text("상태: 제안\n", encoding="utf-8")
    assert not denied(call(repo, "book-writer:planner", "Edit", story))


def test_planner_new_rev_file_allowed(repo):
    story = repo / "plans/vol1/ch01/story.md"
    story.write_text("상태: 승인 (2026-11-01)\n", encoding="utf-8")
    assert not denied(call(repo, "book-writer:planner", "Write",
                           repo / "plans/vol1/ch01/story.rev1.md"))


def test_planner_approval_checked_beyond_first_10_lines(repo):
    story = repo / "plans/vol1/ch01/story.md"
    story.write_text("\n" * 10 + "상태: 승인 (2026-11-01)\n", encoding="utf-8")
    assert not denied(call(repo, "book-writer:planner", "Edit", story))


# --- 원고 루트 밖 ----------------------------------------------------------------

def test_writer_outside_root_denied(repo, tmp_path):
    assert denied(call(repo, "book-writer:writer", "Write", tmp_path / "elsewhere.md"))


def test_outside_root_reason_without_manifest_mentions_cwd(tmp_path):
    # manifest.md를 찾지 못해 cwd가 루트가 된 경우, 밖 경로 거부 사유에
    # cwd 경로와 "manifest.md를 찾지 못해" 이유가 들어갑니다.
    cwd = tmp_path / "plain"
    (cwd / "manuscript").mkdir(parents=True)
    proc = call(cwd, "book-writer:writer", "Write", tmp_path / "elsewhere.md", cwd=cwd)
    assert denied(proc)
    reason = deny_reason(proc)
    assert "manifest.md를 찾지 못해" in reason
    assert os.path.realpath(cwd) in reason


def test_outside_root_reason_with_manifest_mentions_root(repo, tmp_path):
    # manifest.md를 찾은 루트의 밖 경로 거부 사유에 루트 경로와
    # "세션 작업 디렉터리 기준"이 들어갑니다.
    proc = call(repo, "book-writer:writer", "Write", tmp_path / "elsewhere.md")
    assert denied(proc)
    reason = deny_reason(proc)
    assert os.path.realpath(repo) in reason
    assert "세션 작업 디렉터리 기준" in reason


def test_writer_dotdot_escape_denied(repo):
    assert denied(call(repo, "book-writer:writer", "Write",
                       str(repo / "manuscript/vol1/../../escape.md")))


def test_writer_symlink_escape_denied(repo, tmp_path):
    # 원고 안의 링크가 루트 밖 파일을 가리키면 실제 대상 기준으로 막습니다.
    secret = tmp_path / "secret.md"
    secret.write_text("x", encoding="utf-8")
    link = repo / "manuscript" / "escape.md"
    os.symlink(secret, link)
    assert denied(call(repo, "book-writer:writer", "Write", link))


# --- paths.json 덮어쓰기 ----------------------------------------------------------

def test_paths_json_replaces_role_list(repo):
    guard = repo / ".book-writer"
    guard.mkdir()
    (guard / "paths.json").write_text(
        json.dumps({"capturer": ["shots/**"]}), encoding="utf-8")
    assert not denied(call(repo, "book-writer:capturer", "Write", repo / "shots/fig1.png"))
    # 교체는 그 역할의 목록만 바꿉니다 — 기본 허용 경로는 더 이상 허용되지 않습니다.
    assert denied(call(repo, "book-writer:capturer", "Write",
                       repo / "research/measure-x-2026-11-10.md"))
    # 다른 역할의 목록은 그대로입니다.
    assert not denied(call(repo, "book-writer:writer", "Write",
                           repo / "manuscript/vol1/part1/ch01.md"))


def test_paths_json_invalid_blocks_all(repo):
    guard = repo / ".book-writer"
    guard.mkdir()
    (guard / "paths.json").write_text("{oops", encoding="utf-8")
    proc = call(repo, "book-writer:writer", "Write", repo / "manuscript/vol1/part1/ch01.md")
    assert denied(proc)
    assert "paths.json" in deny_reason(proc)


def test_guard_dir_not_writable_by_any_role(repo):
    guard = repo / ".book-writer"
    guard.mkdir()
    for role in ("planner", "writer", "editor", "researcher", "capturer"):
        assert denied(call(repo, f"book-writer:{role}", "Edit", guard / "paths.json"))


# --- 입력 형식 --------------------------------------------------------------------

def test_missing_path_denied(repo):
    assert denied(call(repo, "book-writer:writer", "Write", None))


def test_empty_path_denied(repo):
    assert denied(call(repo, "book-writer:writer", "Write", "   "))


def test_notebook_path_checked(repo):
    # NotebookEdit은 notebook_path 키를 검사합니다 — writer는 허용, editor는 거부.
    assert not denied(call(repo, "book-writer:writer", "NotebookEdit",
                           repo / "manuscript/notebook.ipynb", key="notebook_path"))
    assert denied(call(repo, "book-writer:editor", "NotebookEdit",
                       repo / "manuscript/notebook.ipynb", key="notebook_path"))


def test_invalid_json_exits_2():
    proc = run_guard("이건 JSON이 아닙니다")
    assert proc.returncode == 2
    assert proc.stderr.strip()


def test_non_object_json_exits_2():
    proc = run_guard("[1, 2, 3]")
    assert proc.returncode == 2
    assert proc.stderr.strip()


# --- glob 경계: **는 0개 이상 디렉터리, *는 /를 넘지 않음 -------------------------

@pytest.mark.parametrize("rel,ok", [
    ("manuscript/images/fig.png", True),             # ** 가 0개 디렉터리
    ("manuscript/vol1/part1/images/fig.png", True),
    ("manuscript/vol1/images/fig.png", True),
    ("manuscript/vol1/part1/images/sub/fig.png", True),  # 뒤의 ** 가 여러 디렉터리
    ("manuscript/vol1/part1/ch01.md", False),        # images/ 아래가 아니면 불일치
    ("manuscript/ch01.md", False),
    ("manuscriptx/ch01.md", False),                  # 접두만 같은 다른 폴더
])
def test_capturer_glob_boundaries(repo, rel, ok):
    assert denied(call(repo, "book-writer:capturer", "Write", repo / rel)) is not ok


@pytest.mark.parametrize("rel,ok", [
    ("research/measure-a.md", True),
    ("research/measure-a/b.md", False),              # * 는 / 를 넘지 않습니다
    ("research/measure-.md", True),                  # * 는 빈 글자에도 대응
    ("research/xmeasure-a.md", False),               # * 는 세그먼트 안에서만 대응
])
def test_capturer_star_boundary(repo, rel, ok):
    assert denied(call(repo, "book-writer:capturer", "Write", repo / rel)) is not ok


@pytest.mark.parametrize("rel", [
    "research/raw/x.txt",                            # 실측 응답 원문 (발견 7)
    "research/raw/sub/y.json",                       # raw/ 안의 더 깊은 경로
])
def test_capturer_raw_research_allowed(repo, rel):
    assert not denied(call(repo, "book-writer:capturer", "Write", repo / rel))


def test_capturer_research_notes_denied(repo):
    # raw/ 밖의 research 문서는 여전히 거부합니다(기존 동작 유지).
    assert denied(call(repo, "book-writer:capturer", "Write", repo / "research/notes.md"))


def test_writer_research_raw_denied(repo):
    # 실측 원문 자리는 capturer 전용입니다.
    assert denied(call(repo, "book-writer:writer", "Write", repo / "research/raw/x.txt"))
