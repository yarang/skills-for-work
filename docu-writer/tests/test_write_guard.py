"""hooks/write_guard.py 수용 테스트.

계약: template/skills/template-workflow/SKILL.md 「견본 보호」.
hook은 표준 입력 JSON 한 개를 받고, 막을 때는 표준 출력에
PreToolUse `permissionDecision: deny` JSON을 내거나 종료 코드 2로 끝납니다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "hooks" / "write_guard.py"
KORDOC = "mcp__plugin_moai-officer_kordoc__"


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


@pytest.fixture
def ws(tmp_path):
    """작업 디렉터리: 견본은 cwd 밖, .docu-writer/protected-paths에 견본 경로."""
    cwd = tmp_path / "work"
    dw = cwd / ".docu-writer"
    (dw / "work").mkdir(parents=True)
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    sample = sample_dir / "견본.hwpx"
    sample.write_bytes(b"PK")
    (dw / "protected-paths").write_text(f"{sample}\n", encoding="utf-8")
    for name in ("approved.sha256", "session.yaml", "profile.yaml", "evidence.yaml"):
        (dw / name).write_text("x", encoding="utf-8")
    return {"cwd": cwd, "dw": dw, "sample": sample}


def call(ws, agent, tool, path, key="file_path"):
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": str(ws["cwd"]),
        "tool_name": tool,
        "tool_input": {} if path is None else {key: str(path)},
    }
    if agent is not None:
        payload["agent_type"] = agent
    return run_guard(payload)


# --- 메인 대화와 다른 플러그인은 검사하지 않음 ---------------------------------

def test_main_conversation_not_checked(ws):
    assert not denied(call(ws, None, "Write", ws["sample"]))


def test_other_plugin_agent_not_checked(ws):
    assert not denied(call(ws, "moai-officer:doc-producer", "Write", ws["sample"]))


# --- 역할별 허용 범위 -------------------------------------------------------------

@pytest.mark.parametrize("rel,ok", [
    ("profile.yaml", True),
    ("work/tables.yaml", True),
    ("render/source/page.svg", True),
    ("protected-paths", False),
    ("approved.sha256", False),
    ("session.yaml", False),
])
def test_analyst_scope(ws, rel, ok):
    assert denied(call(ws, "docu-writer:analyst", "Write", ws["dw"] / rel)) is not ok


def test_analyst_outside_docu_writer(ws):
    assert denied(call(ws, "docu-writer:analyst", "Write", ws["cwd"] / "out.docx"))


# kordoc은 숨김 경로(.docu-writer/)에 쓰지 않으므로 analyst의 kordoc 출력은 보이는
# 임시 폴더 docu-writer-out/에 냈다가 옮깁니다 (종단 시험 F15).
@pytest.mark.parametrize("tool", ["render_document", "extract_profile", "convert_to_hwpx"])
def test_analyst_kordoc_staging_allowed(ws, tool):
    out = ws["cwd"] / "docu-writer-out" / "page.png"
    assert not denied(call(ws, "docu-writer:analyst", KORDOC + tool, out, key="output_path"))


def test_analyst_staging_relative_path_allowed(ws):
    assert not denied(call(ws, "docu-writer:analyst", KORDOC + "render_document",
                           "docu-writer-out/page.svg", key="output_path"))


@pytest.mark.parametrize("path", ["docu-writer-out", "docu-writer-out/../out.docx", "docu-writer-outx/a.png"])
def test_analyst_staging_escape_denied(ws, path):
    assert denied(call(ws, "docu-writer:analyst", KORDOC + "render_document", path, key="output_path"))


def test_analyst_symlinked_staging_denied(ws, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (ws["cwd"] / "docu-writer-out").symlink_to(elsewhere)
    assert denied(call(ws, "docu-writer:analyst", KORDOC + "render_document",
                       ws["cwd"] / "docu-writer-out" / "page.png", key="output_path"))


def test_staging_does_not_open_contract_or_sample(ws):
    link = ws["cwd"] / "docu-writer-out"
    link.mkdir()
    (link / "s.hwpx").symlink_to(ws["sample"])
    assert denied(call(ws, "docu-writer:analyst", KORDOC + "render_document", link / "s.hwpx",
                       key="output_path"))


@pytest.mark.parametrize("rel,ok", [
    ("evidence.yaml", True),
    ("profile.yaml", False),
    ("work/notes.md", False),
])
def test_researcher_scope(ws, rel, ok):
    assert denied(call(ws, "docu-writer:researcher", "Write", ws["dw"] / rel)) is not ok


@pytest.mark.parametrize("rel,ok", [
    ("placeholders.yaml", True),
    ("work/edits.yaml", True),
    ("render/page_001.png", True),
    ("profile.yaml", False),
    ("evidence.yaml", False),
    ("approved.sha256", False),
    ("protected-paths", False),
    ("session.yaml", False),
])
def test_writer_scope_inside_docu_writer(ws, rel, ok):
    assert denied(call(ws, "docu-writer:writer", "Edit", ws["dw"] / rel)) is not ok


def test_writer_may_write_output(ws):
    assert not denied(call(ws, "docu-writer:writer", "Write", ws["cwd"] / "결과.hwpx"))


def test_writer_may_not_write_sample(ws):
    assert denied(call(ws, "docu-writer:writer", "Write", ws["sample"]))


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_reviewer_denied_everything(ws, tool):
    assert denied(call(ws, "docu-writer:reviewer", tool, ws["dw"] / "work" / "x.md"))


def test_unknown_docu_writer_role_denied(ws):
    assert denied(call(ws, "docu-writer:intruder", "Write", ws["dw"] / "work" / "x.md"))


# --- kordoc 쓰기 도구의 output_path -------------------------------------------------

@pytest.mark.parametrize("tool", [
    "patch_document", "fill_form", "generate_document",
    "convert_to_hwpx", "extract_profile", "render_document",
])
def test_kordoc_output_path_sample_denied(ws, tool):
    assert denied(call(ws, "docu-writer:writer", KORDOC + tool, ws["sample"], key="output_path"))


def test_kordoc_output_path_allowed(ws):
    assert not denied(call(ws, "docu-writer:writer", KORDOC + "patch_document",
                           ws["cwd"] / "결과.hwpx", key="output_path"))


def test_kordoc_missing_output_path_denied(ws):
    assert denied(call(ws, "docu-writer:writer", KORDOC + "render_document", None))


# --- 경로 정규화 ------------------------------------------------------------------

def test_relative_path_resolved_against_cwd(ws):
    assert denied(call(ws, "docu-writer:writer", "Write", ".docu-writer/profile.yaml"))
    assert not denied(call(ws, "docu-writer:writer", "Write", ".docu-writer/work/edits.yaml"))


def test_dotdot_escape(ws):
    p = f"{ws['dw']}/work/../../../samples/견본.hwpx"
    assert denied(call(ws, "docu-writer:writer", "Write", p))


def test_symlink_to_sample(ws):
    link = ws["cwd"] / "link.hwpx"
    link.symlink_to(ws["sample"])
    assert denied(call(ws, "docu-writer:writer", "Write", link))


def test_symlinked_directory_to_contract(ws):
    alias = ws["cwd"] / "alias"
    alias.symlink_to(ws["dw"])
    assert denied(call(ws, "docu-writer:writer", "Write", alias / "profile.yaml"))


def test_hardlink_to_sample(ws):
    hard = ws["cwd"] / "hard.hwpx"
    os.link(ws["sample"], hard)
    assert denied(call(ws, "docu-writer:writer", "Write", hard))


def test_private_prefix_alias(ws):
    """macOS: /var/… 와 /private/var/… 는 같은 곳."""
    s = str(ws["sample"])
    if s.startswith("/private/"):
        alias = s[len("/private"):]
    elif Path("/private" + s).exists():
        alias = "/private" + s
    else:
        pytest.skip("/private 별칭이 없는 플랫폼")
    assert denied(call(ws, "docu-writer:writer", "Write", alias))


# --- 실패 시 막음 -----------------------------------------------------------------

def test_malformed_input_denied():
    assert denied(run_guard("{not json"))


def test_write_without_file_path_denied(ws):
    assert denied(call(ws, "docu-writer:writer", "Write", None))


# --- 리뷰 회귀 (codex·antigravity) ------------------------------------------------

def test_symlink_then_dotdot_follows_link_target(ws):
    """`link/../x`의 `..`는 링크 목적지 기준 — 정규화를 먼저 하면 cwd/x로 잘못 풀린다."""
    (ws["cwd"] / "lnk").symlink_to(ws["dw"] / "work")
    assert denied(call(ws, "docu-writer:writer", "Write", ws["cwd"] / "lnk" / ".." / "profile.yaml"))


@pytest.mark.parametrize("name", ["Profile.YAML", "SESSION.yaml", "Protected-Paths"])
def test_case_variant_contract_file(ws, name):
    assert denied(call(ws, "docu-writer:writer", "Write", ws["dw"] / name))


def test_dangling_symlink_to_contract(ws):
    (ws["dw"] / "approved.sha256").unlink()
    (ws["cwd"] / "dangling").symlink_to(ws["dw"] / "approved.sha256")
    assert denied(call(ws, "docu-writer:writer", "Write", ws["cwd"] / "dangling"))


@pytest.mark.parametrize("role", ["writer", "analyst", "researcher"])
def test_missing_protected_paths_fails_closed(ws, role):
    (ws["dw"] / "protected-paths").unlink()
    assert denied(call(ws, f"docu-writer:{role}", "Write", ws["dw"] / "work" / "a.yaml"))


def test_researcher_evidence_symlink_denied(ws):
    ev = ws["dw"] / "evidence.yaml"
    ev.unlink()
    ev.symlink_to(ws["cwd"] / "elsewhere.txt")
    assert denied(call(ws, "docu-writer:researcher", "Write", ev))


def test_researcher_link_pointing_at_evidence_denied(ws):
    (ws["cwd"] / "ev").symlink_to(ws["dw"] / "evidence.yaml")
    assert denied(call(ws, "docu-writer:researcher", "Write", ws["cwd"] / "ev"))


def test_notebook_edit_checked(ws):
    assert denied(call(ws, "docu-writer:writer", "NotebookEdit", ws["dw"] / "profile.yaml",
                       key="notebook_path"))
    assert denied(call(ws, "docu-writer:reviewer", "NotebookEdit", ws["cwd"] / "n.ipynb",
                       key="notebook_path"))


def test_whitespace_path_denied(ws):
    assert denied(call(ws, "docu-writer:writer", "Write", "   "))


def test_guard_never_exits_1(ws):
    """종료 코드 1은 Claude Code가 막지 않으므로 가드는 0 또는 2만 낸다."""
    for payload in ("[]", "null", '{"agent_type": "docu-writer:writer", "tool_name": "Write", "tool_input": 3}'):
        assert run_guard(payload).returncode in (0, 2)
