"""종단 사슬 통합 테스트 (종단 시험 T2).

매뉴얼에 적힌 명령을 그대로 이어 붙여 ② 프로파일 → ④ 승인 → ⑥ 적용·검증까지 한 번에 돌립니다.
사람·에이전트가 채우는 칸(analyst 몫)은 코드가 대신 채웁니다. 렌더는 soffice가 있어야 하므로
여기서는 빼고(쪽 기준은 skip), 렌더를 포함한 실행은 docs/manual.md 「종단 시험 결과」에 적습니다.
"""
import hashlib
import json
import subprocess

import pytest
import yaml

from conftest import DOC_VERIFY, PATCH_DOCX, PATCH_PPTX, PROFILE_EXTRACT, build_pptx, uv

PHONE = r"re:010-\d{4}-\d{4}"
SIGN = "부서장 ○○○ (서명)"


def build_form(path):
    from docx import Document

    doc = Document()
    doc.add_heading("수강 신청서", 1)
    doc.add_paragraph("아래 칸을 빠짐없이 적어 주십시오.")
    table = doc.add_table(rows=3, cols=4)
    table.style = "Table Grid"
    for r, row in enumerate([("성명", "", "연락처", ""), ("과정명", "", "신청일", ""), ("부서장 확인", "", "", "")]):
        for c, text in enumerate(row):
            table.cell(r, c).text = text
    table.cell(2, 1).merge(table.cell(2, 3))  # 실제 양식처럼 서명 칸을 한 칸으로 병합
    doc.add_paragraph("※ 개인정보는 교육 운영에만 씁니다.")
    doc.save(path)


def write_yaml(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def form_ws(tmp_path):
    """견본 + ② 프로파일(analyst 칸 채움) + ④ 승인까지 마친 작업 공간."""
    src = tmp_path / "수강 신청서.docx"
    build_form(src)
    ws = tmp_path / ".docu-writer"
    (ws / "work").mkdir(parents=True)
    draft = ws / "work/draft.yaml"
    proc = uv(PROFILE_EXTRACT, "profile", src, "--mode", "form", "--out", draft)
    assert proc.returncode == 0, proc.stderr

    prof = yaml.safe_load(draft.read_text(encoding="utf-8"))
    by_label = {f["label"]: f for f in prof["fields"]}
    assert set(by_label) == {"성명", "연락처", "과정명", "신청일", "부서장 확인"}
    by_label["연락처"]["constraint"] = PHONE
    for s in prof["structure"]["sections"]:  # form 섹션은 length 없이 (F7)
        s.update(id="s1", kind="서술", required=True, guide="양식 제목 — 고치지 않음")
    prof.update(voice={"style": "혼합", "ending": "", "terms": {}}, sample_text=[], conflicts=[],
                length={"pages": [1, 1]})
    for k in ("sample_text_candidates", "objects", "warnings"):
        prof.pop(k, None)
    profile = write_yaml(ws / "profile.yaml", prof)

    tables = ws / "work/tables.yaml"
    tables.write_text(uv(PROFILE_EXTRACT, "tables", src).stdout, encoding="utf-8")
    proc = uv(PROFILE_EXTRACT, "check", profile, "--source", src, "--tables", tables)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    evidence = write_yaml(ws / "evidence.yaml", {"facts": [
        {"field": f["id"], "value": "", "source": "사용자 (대화, 2026-11-04)"} for f in prof["fields"]]})
    approved = ws / "approved.sha256"
    approved.write_text(subprocess.run(["shasum", "-a", "256", profile, evidence], capture_output=True,
                                       text=True, check=True, cwd=tmp_path).stdout, encoding="utf-8")
    loc = {f["label"]: f["locator"] for f in prof["fields"]}
    return {"root": tmp_path, "src": src, "ws": ws, "profile": profile, "approved": approved, "loc": loc}


def values(loc, **override):
    v = {"성명": "홍길동", "연락처": "010-1234-5678", "과정명": "공공데이터 분석 기초",
         "신청일": "2026.11.4.", "부서장 확인": SIGN}
    v.update(override)
    return [{"op": "replace", "at": loc[k], "text": t} for k, t in v.items() if t is not None]


def apply_and_verify(ws, name, edits):
    """⑥: 승인 확인 → 적용 → 검증. (검증 종료 코드, 검사 id별 보고) 를 돌려줌."""
    check = subprocess.run(["shasum", "-c", ws["approved"]], capture_output=True, text=True, cwd=ws["root"])
    assert check.returncode == 0, check.stdout
    edits_path = write_yaml(ws["ws"] / f"work/{name}.yaml", edits)
    out = ws["root"] / f"{name}.docx"
    proc = uv(PATCH_DOCX, "apply", ws["src"], "--edits", edits_path, "--profile", ws["profile"], "--out", out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    placeholders = write_yaml(ws["ws"] / "placeholders.yaml", [
        {"locator": ws["loc"]["부서장 확인"], "expect": "부서장 ○○○", "reason": "근거 없음 — 서명 칸"}])
    vdir = ws["ws"] / f"verify-{name}"
    proc = uv(DOC_VERIFY, "--profile", ws["profile"], "--source", ws["src"],
              "--expect-sha256", hashlib.sha256(ws["src"].read_bytes()).hexdigest(), "--output", out,
              "--placeholders", placeholders, "--out-dir", vdir)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    report = json.loads((vdir / "report.json").read_text(encoding="utf-8"))
    return proc.returncode, {e["id"]: e for e in report}


def test_docx_form_chain_passes(form_ws):
    code, r = apply_and_verify(form_ws, "filled", values(form_ws["loc"]))
    assert code == 0, {k: v for k, v in r.items() if v["status"] == "fail"}
    assert r["fields"]["status"] == "pass"
    assert r["placeholder"]["status"] == "pass"
    assert r["residue"]["status"] == "skip" and r["scope"]["status"] == "skip"


def test_docx_form_chain_bad_phone_fails(form_ws):
    code, r = apply_and_verify(form_ws, "bad-phone", values(form_ws["loc"], 연락처="010-12-5678"))
    assert code == 1
    assert r["fields"]["status"] == "fail"
    assert r["fields"]["locations"] == ["f2"]


def test_docx_form_chain_blank_field_fails(form_ws):
    code, r = apply_and_verify(form_ws, "blank", values(form_ws["loc"], 과정명=None))
    assert code == 1
    assert r["fields"]["status"] == "fail"
    assert "f3 빈칸" in r["fields"]["detail"]


def test_docx_form_chain_stale_approval_blocks(form_ws):
    """② 프로파일을 고친 뒤 ④를 다시 거치지 않으면 ⑥ 첫 줄이 막아야 합니다."""
    prof = form_ws["profile"]
    prof.write_text(prof.read_text(encoding="utf-8") + "\n# 고침\n", encoding="utf-8")
    check = subprocess.run(["shasum", "-c", form_ws["approved"]], capture_output=True, text=True,
                           cwd=form_ws["root"])
    assert check.returncode == 1 and "profile.yaml: FAILED" in check.stdout


# --- PPTX update: 슬라이드 복제·삭제 뒤 섹션 경계 (종단 시험 F8) ---------------------

def approve(root, profile, evidence):
    approved = root / ".docu-writer/approved.sha256"
    approved.write_text(subprocess.run(["shasum", "-a", "256", profile, evidence], capture_output=True,
                                       text=True, check=True, cwd=root).stdout, encoding="utf-8")
    return approved


@pytest.fixture
def deck_ws(tmp_path):
    """견본 3장(표지·추진 일정·실적) + update 프로파일(s2만 고침) + ④ 승인."""
    src = tmp_path / "추진계획.pptx"
    build_pptx(src)
    ws = tmp_path / ".docu-writer"
    (ws / "work").mkdir(parents=True)
    draft = ws / "work/draft.yaml"
    proc = uv(PROFILE_EXTRACT, "profile", src, "--mode", "update", "--out", draft)
    assert proc.returncode == 0, proc.stderr
    prof = yaml.safe_load(draft.read_text(encoding="utf-8"))
    for i, s in enumerate(prof["structure"]["sections"], 1):
        s.update(id=f"s{i}", kind="목록", required=True, guide="견본과 같은 꼴", length={"lines": [1, 8]})
    prof.update(voice={"style": "개조식", "ending": "-다", "terms": {}}, sample_text=[], conflicts=[],
                update={"sections": ["s2"], "requests": ["추진 일정을 한 장 더 나누어 적음"]})
    for k in ("sample_text_candidates", "objects", "warnings"):
        prof.pop(k, None)
    profile = write_yaml(ws / "profile.yaml", prof)
    tables = ws / "work/tables.yaml"
    tables.write_text(uv(PROFILE_EXTRACT, "tables", src).stdout, encoding="utf-8")
    proc = uv(PROFILE_EXTRACT, "check", profile, "--source", src, "--tables", tables)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    evidence = write_yaml(ws / "evidence.yaml", {"facts": [
        {"claim": "준비 단계 2월", "source": "사용자 (대화, 2026-11-04)"}]})
    return {"root": tmp_path, "src": src, "ws": ws, "profile": profile,
            "approved": approve(tmp_path, profile, evidence)}


def deck_verify(ws, name, edits):
    check = subprocess.run(["shasum", "-c", ws["approved"]], capture_output=True, text=True, cwd=ws["root"])
    assert check.returncode == 0, check.stdout
    edits_path = write_yaml(ws["ws"] / f"work/{name}.yaml", edits)
    out = ws["root"] / f"{name}.pptx"
    proc = uv(PATCH_PPTX, "apply", ws["src"], "--edits", edits_path, "--profile", ws["profile"], "--out", out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    vdir = ws["ws"] / f"verify-{name}"
    proc = uv(DOC_VERIFY, "--profile", ws["profile"], "--source", ws["src"],
              "--expect-sha256", hashlib.sha256(ws["src"].read_bytes()).hexdigest(), "--output", out,
              "--out-dir", vdir)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    report = json.loads((vdir / "report.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in report}


S2_EDIT = {"op": "replace", "at": "sl:2/ph:1/p:1", "text": "준비 단계는 2월에 기획팀이 맡는다"}


def test_pptx_update_dup_inside_section_passes_scope(deck_ws):
    """s2 뒤에 복제한 장은 s2 몫 — 뒤 섹션 s3(실적)가 한 칸 밀려도 견본과 같아야 합니다."""
    r = deck_verify(deck_ws, "dup-s2", [
        S2_EDIT,
        {"op": "slide_dup", "like": "sl:2", "after": "sl:2"},
        {"op": "replace", "at": "new:1/ph:0", "text": "추진 일정 (계속)"},
    ])
    assert r["scope"]["status"] == "pass", r["scope"]


def test_pptx_update_dup_into_other_section_fails_scope(deck_ws):
    r = deck_verify(deck_ws, "dup-s3", [S2_EDIT, {"op": "slide_dup", "like": "sl:2", "after": "sl:3"}])
    assert r["scope"]["status"] == "fail"
    assert "s3" in r["scope"]["detail"]


def test_pptx_update_delete_other_section_fails_scope(deck_ws):
    r = deck_verify(deck_ws, "del-s3", [S2_EDIT, {"op": "slide_delete", "at": "sl:3"}])
    assert r["scope"]["status"] == "fail"
    assert "s3" in r["scope"]["detail"] and "찾지 못함" in r["scope"]["detail"]
