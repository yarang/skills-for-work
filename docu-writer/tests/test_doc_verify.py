"""doc_verify.py 수용 테스트.

계약: skills/doc-verify/SKILL.md 「검사 항목」·「검사 세부」·「출력」.
결과 파일은 견본 복사본을 python-docx로 고쳐 만들고, 쪽별 글(pages.json)은 렌더 없이
테스트가 직접 씁니다.
"""
import copy
import hashlib
import json
import shutil

import pytest
import yaml

from conftest import BODY_SENTENCE, DOC_VERIFY, uv

IDS = ["hash", "residue", "placeholder", "fields", "scope", "r4_headings", "r5_tokens",
       "r6_numbering", "table_header", "length", "r1_tables", "rewrite"]
ALLOWED = ["Normal", "Title", "Heading 1", "List Bullet"]
BULLET = "준비 단계는 1월에 기획팀이 맡는다"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(samples, fmt="docx"):
    src = samples[fmt]
    prof = {
        "profile_version": 1,
        "source": {"path": str(src), "format": fmt, "sha256": sha256(src)},
        "mode": "sample",
        "structure": {"numbering": ["1."], "sections": []},
        "design": {"styles_allowed": ALLOWED},
        "sample_text": [],
    }
    if fmt == "docx":
        p = samples["docx_paras"]
        prof["structure"]["sections"] = [
            {"id": "s1", "title": "추진 배경", "level": 1, "anchor": p["1. 추진 배경"]},
            {"id": "s2", "title": "추진 일정", "level": 1, "anchor": p["2. 추진 일정"]},
        ]
    return prof


def output(samples, tmp_path, edit=None, fmt="docx"):
    out = tmp_path / f"out.{fmt}"
    shutil.copy(samples[fmt], out)
    if edit:
        from docx import Document
        doc = Document(out)
        edit(doc)
        doc.save(out)
    return out


def verify(samples, tmp_path, prof, out, placeholders=None, pages=None, expect=None, fmt="docx"):
    pf = tmp_path / "profile.yaml"
    pf.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
    args = ["--profile", pf, "--source", samples[fmt], "--expect-sha256", expect or sha256(samples[fmt]),
            "--output", out, "--out-dir", tmp_path / "verify"]
    if placeholders is not None:
        ph = tmp_path / "placeholders.yaml"
        ph.write_text(yaml.safe_dump(placeholders, allow_unicode=True), encoding="utf-8")
        args += ["--placeholders", ph]
    if pages is not None:
        render = tmp_path / "render"
        render.mkdir(exist_ok=True)
        if isinstance(pages, list):
            (render / "pages.json").write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        args += ["--pages-dir", render]
    proc = uv(DOC_VERIFY, *args)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    report = json.loads((tmp_path / "verify" / "report.json").read_text(encoding="utf-8"))
    return proc, {e["id"]: e for e in report}


# --- python-docx 편집 도우미 -------------------------------------------------------

def para(doc, text):
    return next(p for p in doc.paragraphs if p.text == text)


def set_text(p, text):
    for r in p.runs[1:]:
        r._element.getparent().remove(r._element)
    p.runs[0].text = text


def set_font(run, name=None, pt=None, bold=None):
    from docx.oxml.ns import qn
    from docx.shared import Pt
    if name:
        run.font.name = name
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), name)
    if pt:
        run.font.size = Pt(pt)
    if bold is not None:
        run.font.bold = bold


def replace_body(text):
    return lambda doc: set_text(para(doc, BODY_SENTENCE), text)


def add_paras(*texts, style=None):
    def edit(doc):
        for t in texts:
            doc.add_paragraph(t, style=style)
    return edit


# --- 보고서 모양 -------------------------------------------------------------------

def test_clean_copy_report_shape(samples, tmp_path):
    proc, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path))
    assert proc.returncode == 0, proc.stdout
    report = json.loads((tmp_path / "verify" / "report.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in report] == IDS
    for e in report:
        assert {"id", "status", "detail", "locations"} <= set(e)
        assert e["status"] in {"pass", "fail", "warn", "skip"}
        assert isinstance(e["locations"], list)
    assert "### 문서 검증" in proc.stdout
    want = {"hash": "pass", "placeholder": "skip", "fields": "skip", "scope": "skip",
            "r4_headings": "pass", "r5_tokens": "pass", "r6_numbering": "pass",
            "table_header": "pass", "length": "skip", "r1_tables": "skip", "rewrite": "skip"}
    assert {k: r[k]["status"] for k in want} == want
    assert r["residue"]["status"] != "fail"


def test_hash_mismatch_fails(samples, tmp_path):
    proc, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path), expect="0" * 64)
    assert proc.returncode == 1
    assert r["hash"]["status"] == "fail"


# --- residue ---------------------------------------------------------------------

def test_residue(samples, tmp_path):
    prof = profile(samples)
    prof["sample_text"] = [BODY_SENTENCE[:20]]
    proc, r = verify(samples, tmp_path, prof, output(samples, tmp_path))
    assert proc.returncode == 1
    assert r["residue"]["status"] == "fail"

    out = output(samples, tmp_path, replace_body("신청 건수는 135건이다."))
    _, r = verify(samples, tmp_path, prof, out)
    assert r["residue"]["status"] == "pass"


# --- placeholder -----------------------------------------------------------------

PH = [{"locator": "s1", "expect": "총 ○○건", "reason": "근거 없음"}]


def test_placeholder_found_in_section(samples, tmp_path):
    out = output(samples, tmp_path, replace_body("신청 건수는 총 ○○건이다."))
    _, r = verify(samples, tmp_path, profile(samples), out, placeholders=PH)
    assert r["placeholder"]["status"] == "pass"


def test_placeholder_missing_fails(samples, tmp_path):
    proc, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path), placeholders=PH)
    assert proc.returncode == 1
    assert r["placeholder"]["status"] == "fail"


def test_placeholder_outside_section_fails(samples, tmp_path):
    out = output(samples, tmp_path, lambda doc: set_text(para(doc, BULLET), "준비는 총 ○○건이다"))
    _, r = verify(samples, tmp_path, profile(samples), out, placeholders=PH)
    assert r["placeholder"]["status"] == "fail"


def test_placeholder_dump_locator_searches_whole_document(samples, tmp_path):
    out = output(samples, tmp_path, lambda doc: set_text(para(doc, BULLET), "준비는 총 ○○건이다"))
    ph = [{"locator": samples["docx_paras"][BODY_SENTENCE], "expect": "총 ○○건", "reason": "근거 없음"}]
    _, r = verify(samples, tmp_path, profile(samples), out, placeholders=ph)
    assert r["placeholder"]["status"] == "pass"


def test_placeholder_cell_locator(samples, tmp_path):
    def edit(doc):
        doc.tables[0].cell(2, 2).text = "○○팀"
    ph = [{"locator": "t:1/r:3/c:3", "expect": "○○팀", "reason": "근거 없음"}]
    _, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path, edit), placeholders=ph)
    assert r["placeholder"]["status"] == "pass"


# --- fields (form) ---------------------------------------------------------------

def form_profile(samples, constraint=None):
    prof = profile(samples)
    prof["mode"] = "form"
    field = {"id": "f1", "label": "담당", "locator": "t:1/r:3/c:3"}
    if constraint:
        field["constraint"] = constraint
    prof["fields"] = [field]
    return prof


def fill(text):
    def edit(doc):
        doc.tables[0].cell(2, 2).text = text
    return edit


def test_fields_empty_fails(samples, tmp_path):
    proc, r = verify(samples, tmp_path, form_profile(samples), output(samples, tmp_path))
    assert proc.returncode == 1
    assert r["fields"]["status"] == "fail"
    assert "f1" in json.dumps(r["fields"], ensure_ascii=False)


def test_fields_filled_passes(samples, tmp_path):
    _, r = verify(samples, tmp_path, form_profile(samples), output(samples, tmp_path, fill("기획팀")))
    assert r["fields"]["status"] == "pass"


@pytest.mark.parametrize("text,status", [("120건", "pass"), ("많음", "fail")])
def test_fields_regex_constraint(samples, tmp_path, text, status):
    _, r = verify(samples, tmp_path, form_profile(samples, r"re:^\d+건$"), output(samples, tmp_path, fill(text)))
    assert r["fields"]["status"] == status


def test_fields_placeholder_exempts_constraint(samples, tmp_path):
    prof = form_profile(samples, r"re:^\d+건$")
    out = output(samples, tmp_path, fill("○○건"))
    _, r = verify(samples, tmp_path, prof, out)
    assert r["fields"]["status"] == "fail"
    ph = [{"locator": "f1", "expect": "○○건", "reason": "근거 없음"}]
    _, r = verify(samples, tmp_path, prof, out, placeholders=ph)
    assert r["fields"]["status"] == "pass"


def test_fields_prose_constraint_not_judged(samples, tmp_path):
    _, r = verify(samples, tmp_path, form_profile(samples, "한글 2~10자"), output(samples, tmp_path, fill("x")))
    assert r["fields"]["status"] != "fail"
    assert "한글 2~10자" in r["fields"]["detail"]


# --- scope (update) --------------------------------------------------------------

def update_profile(samples):
    prof = profile(samples)
    prof["mode"] = "update"
    prof["update"] = {"sections": ["s2"], "requests": ["추진 일정 갱신"]}
    return prof


def insert_after_bullet(doc):
    bullet = para(doc, BULLET)
    new = copy.deepcopy(bullet._p)
    bullet._p.addnext(new)
    from docx.text.paragraph import Paragraph
    set_text(Paragraph(new, bullet._parent), "시행 단계는 2~6월이다")


@pytest.mark.parametrize("name,edit,status", [
    ("s1 body", replace_body("바뀐 문장이다."), "fail"),
    ("title before s1", lambda doc: set_text(para(doc, "○○사업 추진계획(안)"), "다른 제목"), "fail"),
    ("s1 table cell", fill("기획팀"), "fail"),
    ("s2 bullet", lambda doc: set_text(para(doc, BULLET), "준비 단계는 2월이다"), "pass"),
    ("s2 table cell", lambda doc: setattr(doc.tables[1].cell(0, 1), "text", "세부"), "pass"),
    ("s2 inserted paragraph", insert_after_bullet, "pass"),
])
def test_scope(samples, tmp_path, name, edit, status):
    _, r = verify(samples, tmp_path, update_profile(samples), output(samples, tmp_path, edit))
    assert r["scope"]["status"] == status, name


# --- R4 제목 -----------------------------------------------------------------------

def headings(doc):
    return [p for p in doc.paragraphs if p.style.name == "Heading 1"]


def test_r4_mixed_heading_size_fails(samples, tmp_path):
    out = output(samples, tmp_path, lambda doc: set_font(headings(doc)[0].runs[0], pt=20))
    proc, r = verify(samples, tmp_path, profile(samples), out)
    assert proc.returncode == 1
    assert r["r4_headings"]["status"] == "fail"


@pytest.mark.parametrize("token_pt,status", [(16, "pass"), (20, "fail")])
def test_r4_heading_matches_type_token(samples, tmp_path, token_pt, status):
    def edit(doc):
        for h in headings(doc):
            set_font(h.runs[0], name="맑은 고딕", pt=16, bold=True)
    prof = profile(samples)
    prof["design"]["type"] = {"h1": {"font": "맑은 고딕", "pt": token_pt, "bold": True}}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path, edit))
    assert r["r4_headings"]["status"] == status


# --- R5 토큰 -----------------------------------------------------------------------

def test_r5_style_not_allowed_fails(samples, tmp_path):
    out = output(samples, tmp_path, add_paras("3. 세부 내용", style="Heading 2"))
    proc, r = verify(samples, tmp_path, profile(samples), out)
    assert proc.returncode == 1
    assert r["r5_tokens"]["status"] == "fail"


def test_r5_font_outside_tokens_fails(samples, tmp_path):
    prof = profile(samples)
    prof["design"]["type"] = {"body": {"font": "바탕", "pt": 11}}
    out = output(samples, tmp_path, lambda doc: set_font(para(doc, BODY_SENTENCE).runs[0], name="Comic Sans MS"))
    _, r = verify(samples, tmp_path, prof, out)
    assert r["r5_tokens"]["status"] == "fail"


def test_r5_table_style_ignored(samples, tmp_path):
    """표 스타일(Normal Table·Table Grid)은 styles_allowed와 비교하지 않음."""
    out = output(samples, tmp_path, lambda doc: setattr(doc.tables[0], "style", "Table Grid"))
    _, r = verify(samples, tmp_path, profile(samples), out)
    assert r["r5_tokens"]["status"] == "pass"


# --- R6 번호 -----------------------------------------------------------------------

@pytest.mark.parametrize("numbering,texts,status", [
    (["1."], ["■ 항목"], "fail"),
    (["1.", "○"], ["ㅇ 항목"], "pass"),
    (["1.", "□", "ㅇ"], ["□ 가", "ㅇ 나"], "fail"),
    (["1."], ["○○사업은 계속한다"], "pass"),
])
def test_r6_numbering(samples, tmp_path, numbering, texts, status):
    prof = profile(samples)
    prof["structure"]["numbering"] = numbering
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path, add_paras(*texts)))
    assert r["r6_numbering"]["status"] == status, texts


# --- 표 머리행 ----------------------------------------------------------------------

def test_table_header_mismatch_fails(samples, tmp_path):
    def edit(doc):
        for c in doc.tables[0].rows[0].cells:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.bold = True
    proc, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path, edit))
    assert proc.returncode == 1
    assert r["table_header"]["status"] == "fail"


# --- length ----------------------------------------------------------------------

TWO_PAGES = [{"page": 1, "text": "가"}, {"page": 2, "text": "나"}]


@pytest.mark.parametrize("limit,status", [(1, "fail"), (5, "pass")])
def test_length_pages(samples, tmp_path, limit, status):
    prof = profile(samples)
    prof["length"] = {"pages": limit}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path), pages=TWO_PAGES)
    assert r["length"]["status"] == status


def test_length_pages_without_render_skips(samples, tmp_path):
    prof = profile(samples)
    prof["length"] = {"pages": 1}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path))
    assert r["length"]["status"] == "skip"


def test_length_pages_from_svg(samples, tmp_path):
    render = tmp_path / "render"
    render.mkdir()
    for i in (1, 2):
        (render / f"page_{i:03d}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><text>구분</text></svg>', encoding="utf-8")
    prof = profile(samples)
    prof["length"] = {"pages": 1}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path), pages=True)
    assert r["length"]["status"] == "fail"


def test_length_section_chars(samples, tmp_path):
    prof = profile(samples)
    prof["structure"]["sections"][0]["length"] = {"chars": [0, 10]}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path))
    assert r["length"]["status"] == "fail"
    assert "s1" in json.dumps(r["length"], ensure_ascii=False)


# --- R1 표 -------------------------------------------------------------------------

def test_r1_table_split_warns(samples, tmp_path):
    pages = [
        {"page": 1, "text": "1. 추진 배경\n구분 기간 담당\n준비 1월 기획팀\n합계"},
        {"page": 2, "text": "120건\n2. 추진 일정\n단계 내용\n시행 운영팀 담당\n요약 상자 글입니다"},
    ]
    proc, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path), pages=pages)
    assert proc.returncode == 0, proc.stdout
    assert r["r1_tables"]["status"] == "warn"
    assert "t:1" in r["r1_tables"]["locations"]
    assert "t:2" not in r["r1_tables"]["locations"]


def test_r1_tables_on_one_page_pass(samples, tmp_path):
    pages = [{"page": 1, "text": "구분 기간 담당 합계 120건 단계 운영팀 담당 요약 상자 글입니다"}]
    _, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path), pages=pages)
    assert r["r1_tables"]["status"] == "pass"


# --- 형식별 ------------------------------------------------------------------------

@pytest.mark.parametrize("sibling", [None, "out.rewrite.hwpx", "out.hwpx.rewrite.hwpx"])
def test_rewrite_sibling_hwpx(samples, tmp_path, sibling):
    prof = profile(samples, "hwpx")
    prof["structure"]["numbering"] = []
    out = output(samples, tmp_path, fmt="hwpx")
    if sibling:
        shutil.copy(out, tmp_path / sibling)
    _, r = verify(samples, tmp_path, prof, out, fmt="hwpx")
    assert [*r] == IDS
    assert r["rewrite"]["status"] == ("fail" if sibling else "pass")


def test_md_skips_tables_and_tokens(samples, tmp_path):
    prof = profile(samples, "md")
    prof["structure"]["numbering"] = ["1.", "-"]
    prof["length"] = {"pages": 1}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path, fmt="md"), pages=TWO_PAGES, fmt="md")
    assert r["r1_tables"]["status"] == "skip"
    assert r["r5_tokens"]["status"] == "skip"
    assert r["length"]["status"] == "skip"


@pytest.mark.parametrize("allowed,status", [
    (["Title Slide", "Title and Content", "Title Only"], "pass"),
    (["Title Slide", "Title and Content"], "fail"),
])
def test_pptx_layout_tokens(samples, tmp_path, allowed, status):
    prof = profile(samples, "pptx")
    prof["structure"]["numbering"] = []
    prof["design"]["styles_allowed"] = allowed
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path, fmt="pptx"), fmt="pptx")
    assert r["hash"]["status"] == "pass"
    assert r["r5_tokens"]["status"] == status


# --- 사용법 오류 ----------------------------------------------------------------------

@pytest.mark.parametrize("case", ["no-profile", "txt-output", "no-source"])
def test_usage_errors_exit_2(samples, tmp_path, case):
    pf = tmp_path / "profile.yaml"
    pf.write_text(yaml.safe_dump(profile(samples), allow_unicode=True), encoding="utf-8")
    out = output(samples, tmp_path)
    src = samples["docx"]
    if case == "no-profile":
        pf = tmp_path / "missing.yaml"
    elif case == "txt-output":
        out = tmp_path / "out.txt"
        out.write_text("x", encoding="utf-8")
    else:
        src = tmp_path / "missing.docx"
    proc = uv(DOC_VERIFY, "--profile", pf, "--source", src, "--expect-sha256", "0" * 64,
              "--output", out, "--out-dir", tmp_path / "verify")
    assert proc.returncode == 2, proc.stdout + proc.stderr
