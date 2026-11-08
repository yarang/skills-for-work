"""SKILL.md의 셸 명령을 그대로 꺼내 실행하는 회귀 테스트 (종단 시험 F2, 리뷰 3차 M5·M6).

update 모드에서 ③을 건너뛰면 evidence.yaml이 없는데, 예전 ④ 명령은 실패하면서도
profile.yaml 한 줄짜리 approved.sha256을 남겨 근거가 잠기지 않았습니다.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT

WORKFLOW = ROOT / "template/skills/template-workflow/SKILL.md"


def approve_snippet() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    found = [b for b in blocks if "approved.sha256" in b and "shasum -a 256 .docu-writer/profile.yaml" in b]
    assert len(found) == 1, "④ 승인 명령 블록을 하나만 찾아야 합니다"
    return found[0]


SHELLS = {"bash": ["bash", "-c"], "zsh": ["zsh", "-f", "-c"]}  # zsh는 맞는 파일 없는 glob을 오류로 멈춤


def run(snippet, cwd, sh="bash"):
    return subprocess.run([*SHELLS[sh], snippet], cwd=cwd, capture_output=True, text=True)


@pytest.fixture(params=["bash", pytest.param("zsh", marks=pytest.mark.skipif(
    shutil.which("zsh") is None, reason="zsh 없음"))])
def sh(request):
    """사용자 셸이 macOS 기본 zsh일 수 있으므로 M5·M6 스니펫은 두 셸에서 돌립니다."""
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / ".docu-writer").mkdir()
    (tmp_path / ".docu-writer/profile.yaml").write_text("mode: update\n", encoding="utf-8")
    return tmp_path


def test_approve_without_evidence_leaves_no_hash_file(ws):
    proc = run(approve_snippet(), ws)
    assert proc.returncode != 0
    assert not (ws / ".docu-writer/approved.sha256").exists()


def test_approve_locks_both_files(ws):
    (ws / ".docu-writer/evidence.yaml").write_text("sections: []\n", encoding="utf-8")
    assert run(approve_snippet(), ws).returncode == 0
    lines = (ws / ".docu-writer/approved.sha256").read_text(encoding="utf-8").splitlines()
    assert [ln.split()[-1] for ln in lines] == [".docu-writer/profile.yaml", ".docu-writer/evidence.yaml"]
    assert run("shasum -c .docu-writer/approved.sha256", ws).returncode == 0


def test_every_step3_skip_says_who_writes_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("|") and "| ③" in ln]
    assert rows and all("evidence.yaml" in r for r in rows)


# ── 리뷰 3차 M5·M6: format-hwpx·template ①⑥·newdoc ① 스니펫 ─────────────────────
FORMAT_HWPX = ROOT / "skills/format-hwpx/SKILL.md"
NEWDOC = ROOT / "newdoc/skills/newdoc-workflow/SKILL.md"
NAME = "출장 신청서"  # 공백이 든 이름 — 따옴표가 빠지면 mv가 깨짐


def bash_block(path, *needles) -> str:
    blocks = re.findall(r"```bash\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    found = [b for b in blocks if all(n in b for n in needles)]
    assert len(found) == 1, f"{path.name}에서 {needles} 블록을 하나만 찾아야 합니다 ({len(found)}개)"
    return found[0]


def section(path, title) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(title)
    end = text.find("\n## ", start + len(title))
    return text[start:end if end != -1 else None]


def update_move_snippet() -> str:
    return bash_block(FORMAT_HWPX, "<이름>.updated.hwpx", "rewrite").replace("<이름>", NAME)


def test_update_move_handles_space_and_rewrite_files(tmp_path, sh):
    out = tmp_path / "docu-writer-out"
    out.mkdir()
    for suffix in (".updated.hwpx", ".updated.hwpx.rewrite.hwpx", ".updated.rewrite.hwpx"):
        (out / f"{NAME}{suffix}").write_bytes(b"x")
    proc = run(update_move_snippet(), tmp_path, sh)
    assert proc.returncode == 0, proc.stderr
    assert not out.exists()  # 대체본이 남으면 rmdir가 실패하고 check_rewrite가 놓침
    moved = sorted(p.name for p in (tmp_path / ".docu-writer/work").iterdir())
    assert moved == sorted(f"{NAME}{s}" for s in (".updated.hwpx", ".updated.hwpx.rewrite.hwpx", ".updated.rewrite.hwpx"))


def test_update_move_without_rewrite_and_clears_stale_rewrite(tmp_path, sh):
    work = tmp_path / ".docu-writer/work"
    work.mkdir(parents=True)
    (work / f"{NAME}.updated.hwpx.rewrite.hwpx").write_bytes(b"old")  # 지난 시도의 대체본
    (tmp_path / "docu-writer-out").mkdir()
    (tmp_path / f"docu-writer-out/{NAME}.updated.hwpx").write_bytes(b"new")
    proc = run(update_move_snippet(), tmp_path, sh)
    assert proc.returncode == 0, proc.stderr
    assert sorted(p.name for p in work.iterdir()) == [f"{NAME}.updated.hwpx"]


def test_update_move_fails_when_output_missing(tmp_path, sh):
    (tmp_path / "docu-writer-out").mkdir()
    assert run(update_move_snippet(), tmp_path, sh).returncode != 0


def render_snippets():
    sec = section(FORMAT_HWPX, "## 렌더 (⑥)")
    blocks = re.findall(r"```bash\n(.*?)```", sec, re.S)
    assert len(blocks) == 2, "렌더 절에는 kordoc 호출 앞뒤로 bash 블록이 둘 있어야 합니다"
    return blocks


def test_render_clears_stale_pages_and_keeps_source(tmp_path, sh):
    before, after = render_snippets()
    render = tmp_path / ".docu-writer/render"
    (render / "source").mkdir(parents=True)
    (render / "source/page.png").write_bytes(b"src")
    for name in ("page.svg", "page.png", "pages.json"):  # 지난 한 쪽 렌더
        (render / name).write_bytes(b"old")
    (tmp_path / "docu-writer-out").mkdir()
    (tmp_path / "docu-writer-out/page_page_009.svg").write_bytes(b"stale")  # 실패한 시도의 잔여
    assert run(before, tmp_path, sh).returncode == 0
    for n in (1, 2):  # kordoc render_document가 낸 것처럼
        for ext in ("svg", "png"):
            (tmp_path / f"docu-writer-out/page_page_{n:03}.{ext}").write_bytes(b"new")
    proc = run(after, tmp_path, sh)
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "docu-writer-out").exists()
    names = sorted(p.name for p in render.iterdir() if p.is_file())
    assert names == ["page_page_001.png", "page_page_001.svg", "page_page_002.png", "page_page_002.svg"]
    assert (render / "source/page.png").read_bytes() == b"src"


def test_render_before_works_without_existing_folders(tmp_path, sh):
    before, _ = render_snippets()
    proc = run(before, tmp_path, sh)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr  # zsh는 빈 glob이면 그 명령만 실패시키고 이어 감
    assert (tmp_path / ".docu-writer/render").is_dir()


def test_every_render_document_names_output_path():
    md = [p for d in ("skills", "agents", "template", "newdoc") for p in (ROOT / d).rglob("*.md")]
    calls = [(p.name, m) for p in md for m in re.findall(r"render_document\(([^)]*)\)", p.read_text(encoding="utf-8"))]
    assert calls
    missing = [(name, args) for name, args in calls if "output_path" not in args]
    assert not missing, f"output_path 없는 render_document — write_guard가 막음: {missing}"


SAMPLE = "견본 파일.hwpx"


def template_record(kind, materials="") -> str:
    snippet = bash_block(WORKFLOW, kind, "protected-paths").replace("<견본>", SAMPLE)
    return snippet.replace("<자료 경로…>", materials)


@pytest.fixture
def stale(tmp_path):
    dw = tmp_path / ".docu-writer"
    dw.mkdir()
    (tmp_path / SAMPLE).write_bytes(b"sample")
    (dw / "protected-paths").write_text("/자료/메모.txt\n", encoding="utf-8")
    (dw / "route.json").write_text('{"route": "theme"}\n', encoding="utf-8")
    (dw / "materials.sha256").write_text("0" * 64 + "  /자료/메모.txt\n", encoding="utf-8")
    return tmp_path


def test_template_direct_start_resets_newdoc_leftovers(stale, sh):
    proc = run(template_record("# 직접 시작"), stale, sh)
    assert proc.returncode == 0, proc.stderr
    assert "find" not in proc.stderr  # 자료가 없으면 find를 부르지 않음
    dw = stale / ".docu-writer"
    sample = str((stale / SAMPLE).resolve())
    assert dw.joinpath("protected-paths").read_text(encoding="utf-8").splitlines() == [sample]
    assert not (dw / "route.json").exists()
    hashed = [ln.split("  ", 1)[1] for ln in dw.joinpath("materials.sha256").read_text(encoding="utf-8").splitlines()]
    assert hashed == [sample]  # 지난 newdoc 자료(/자료/메모.txt)의 옛 해시가 아니라 새로 적은 견본 해시
    assert run("shasum -c .docu-writer/materials.sha256", stale).returncode == 0


def test_template_direct_start_protects_materials(stale, sh):
    (stale / "자료 폴더").mkdir()
    (stale / "자료 폴더/보고 메모.txt").write_text("a", encoding="utf-8")
    (stale / "통계 1.csv").write_text("b", encoding="utf-8")
    proc = run(template_record("# 직접 시작", '"자료 폴더" "통계 1.csv"'), stale, sh)
    assert proc.returncode == 0, proc.stderr
    paths = (stale / ".docu-writer/protected-paths").read_text(encoding="utf-8").splitlines()
    assert paths == [str((stale / p).resolve()) for p in (SAMPLE, "자료 폴더/보고 메모.txt", "통계 1.csv")]
    check = "[ ! -f .docu-writer/materials.sha256 ] || shasum -c .docu-writer/materials.sha256"
    assert run(check, stale).returncode == 0
    (stale / "통계 1.csv").write_text("changed", encoding="utf-8")  # writer가 Bash로 자료를 고쳤다면
    assert run(check, stale).returncode != 0


def test_template_from_newdoc_fixed_keeps_material_protection(stale, sh):
    proc = run(template_record("# newdoc fixed"), stale, sh)
    assert proc.returncode == 0, proc.stderr
    dw = stale / ".docu-writer"
    assert dw.joinpath("protected-paths").read_text(encoding="utf-8").splitlines() == [
        "/자료/메모.txt", str((stale / SAMPLE).resolve())]
    assert (dw / "route.json").exists() and (dw / "materials.sha256").exists()


def template_step6_materials() -> str:
    sec = section(WORKFLOW, "## ⑥ 검증")
    cmds = [c for c in re.findall(r"`([^`]+)`", sec) if "materials.sha256" in c]
    assert len(cmds) == 1, "⑥에 materials.sha256 대조 명령이 하나 있어야 합니다"
    return cmds[0]


def test_template_step6_checks_materials_when_present(tmp_path, sh):
    cmd = template_step6_materials()
    assert run(cmd, tmp_path, sh).returncode == 0  # 파일이 없으면(이 규칙 전에 시작한 작업) 통과
    (tmp_path / ".docu-writer").mkdir()
    (tmp_path / "m.txt").write_text("a", encoding="utf-8")
    run("shasum -a 256 m.txt > .docu-writer/materials.sha256", tmp_path, sh)
    assert run(cmd, tmp_path, sh).returncode == 0
    (tmp_path / "m.txt").write_text("b", encoding="utf-8")
    assert run(cmd, tmp_path, sh).returncode != 0


def newdoc_record(materials: str, doc_type: str, fmt: str) -> str:
    snippet = bash_block(NEWDOC, 'catalog.py" match')
    return (snippet.replace("<자료 경로…>", materials).replace("<문서 종류>", doc_type)
            .replace("<md|docx|hwpx>", fmt))


@pytest.fixture
def newdoc_env(tmp_path):
    (tmp_path / "user-templates").mkdir()
    env = dict(os.environ, DOCU_WRITER_TEMPLATES=str(tmp_path / "user-templates"),
               CLAUDE_SKILL_DIR=str(ROOT / "newdoc/skills/newdoc-workflow"))
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws, env


def run_newdoc(snippet, ws, env, sh):
    shim = f'uv() {{ shift; "{sys.executable}" "$@"; }}\n'  # uv run → 테스트 파이썬(pyyaml 있음)
    return subprocess.run([*SHELLS[sh], shim + snippet], cwd=ws, env=env, capture_output=True, text=True)


def test_newdoc_record_with_spaced_materials(newdoc_env, sh):
    ws, env = newdoc_env
    (ws / "자료 폴더").mkdir()
    (ws / "자료 폴더/보고 메모.txt").write_text("a", encoding="utf-8")
    (ws / "메모 1.txt").write_text("b", encoding="utf-8")
    proc = run_newdoc(newdoc_record('"자료 폴더" "메모 1.txt"', "없는 종류", "md"), ws, env, sh)
    assert proc.returncode == 0, proc.stderr
    paths = (ws / ".docu-writer/protected-paths").read_text(encoding="utf-8").splitlines()
    assert sorted(paths) == sorted(str(p.resolve()) for p in (ws / "자료 폴더/보고 메모.txt", ws / "메모 1.txt"))
    assert run("shasum -c .docu-writer/materials.sha256", ws).returncode == 0


def test_newdoc_record_without_materials_scans_nothing(newdoc_env, sh):
    ws, env = newdoc_env
    (ws / "관계없는 파일.txt").write_text("x", encoding="utf-8")  # GNU find는 빈 인자면 . 을 훑음
    proc = run_newdoc(newdoc_record("", "없는 종류", "md"), ws, env, sh)
    assert proc.returncode == 0, proc.stderr
    assert "find" not in proc.stderr  # BSD find는 빈 인자면 오류를 찍고 넘어감
    assert (ws / ".docu-writer/protected-paths").read_text(encoding="utf-8") == ""
    assert not (ws / ".docu-writer/materials.sha256").exists()


def test_newdoc_rerun_drops_stale_materials_hash(newdoc_env, sh):
    ws, env = newdoc_env
    (ws / "메모.txt").write_text("a", encoding="utf-8")
    assert run_newdoc(newdoc_record('"메모.txt"', "없는 종류", "md"), ws, env, sh).returncode == 0
    assert (ws / ".docu-writer/materials.sha256").exists()
    (ws / "메모.txt").write_text("changed", encoding="utf-8")
    proc = run_newdoc(newdoc_record("", "없는 종류", "md"), ws, env, sh)  # 자료 없이 ①을 다시
    assert proc.returncode == 0, proc.stderr
    assert not (ws / ".docu-writer/materials.sha256").exists()


ANALYSIS = ROOT / "template/skills/template-analysis/SKILL.md"


def analysis_render_snippets():
    return (bash_block(ANALYSIS, "render/source", "-delete"),
            bash_block(ANALYSIS, "mv docu-writer-out/page*", "render/source"))


def test_analysis_source_render_clears_stale_pages(tmp_path, sh):
    """지난 분석이 3쪽(page_page_00N.png)이고 이번 견본이 한 쪽(page.png)이면 섞이지 않아야 합니다."""
    before, after = analysis_render_snippets()
    source = tmp_path / ".docu-writer/render/source"
    source.mkdir(parents=True)
    for n in (1, 2, 3):
        (source / f"page_page_{n:03}.png").write_bytes(b"old")
    (source / "notes.txt").write_bytes(b"keep")  # page* 밖은 건드리지 않음
    assert run(before, tmp_path, sh).returncode == 0
    (tmp_path / "docu-writer-out").mkdir()
    (tmp_path / "docu-writer-out/page.png").write_bytes(b"new")
    proc = run(after, tmp_path, sh)
    assert proc.returncode == 0, proc.stderr
    assert sorted(p.name for p in source.iterdir()) == ["notes.txt", "page.png"]
    assert not (tmp_path / "docu-writer-out").exists()


def test_analysis_source_render_before_works_on_fresh_workspace(tmp_path, sh):
    before, _ = analysis_render_snippets()
    proc = run(before, tmp_path, sh)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr  # 종료 코드만으로는 zsh 빈 glob 오류를 못 봄
    assert (tmp_path / ".docu-writer/render/source").is_dir()
