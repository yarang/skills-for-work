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

from conftest import BODY_SENTENCE, DOC_VERIFY, FIXTURES, PII_YAML, assert_no_pii, uv

IDS = ["hash", "residue", "markup", "placeholder", "fields", "scope", "r4_headings", "r5_tokens",
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
    want = {"hash": "pass", "markup": "pass", "placeholder": "skip", "fields": "skip", "scope": "skip",
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


# --- markup (종단 시험 F12) ---------------------------------------------------------

@pytest.mark.parametrize("text", ["> 신청 건수는 135건이다.", "## 추진 배경", "신청 **135건** 접수",
                                  "신청 건수 135건\\~140건", "| 구분 | 내용 |"])
def test_markup_leak_fails(samples, tmp_path, text):
    """kordoc patch_document가 요약 상자 글 앞에 「> 」를 남긴 사례처럼 마크다운 표지가 글자로 남으면 실패."""
    _, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path, replace_body(text)))
    assert r["markup"]["status"] == "fail", r["markup"]
    assert r["markup"]["locations"]


def test_markup_plain_text_passes(samples, tmp_path):
    out = output(samples, tmp_path, replace_body("신청 건수는 135건(전년 대비 12% 증가)이다. a>b, 3*4"))
    _, r = verify(samples, tmp_path, profile(samples), out)
    assert r["markup"]["status"] == "pass", r["markup"]


def test_markup_kind_in_source_is_document_text(samples, tmp_path):
    """견본에도 같은 꼴(「> 」로 시작하는 줄)이 있으면 그 종류는 문서 고유의 글로 봅니다."""
    from docx import Document

    src = tmp_path / "src.docx"
    shutil.copy(samples["docx"], src)
    doc = Document(src)
    doc.add_paragraph("> 견본의 인용 줄")
    doc.save(src)
    out = tmp_path / "out.docx"
    shutil.copy(src, out)
    doc = Document(out)
    doc.add_paragraph("> 결과의 인용 줄")
    doc.save(out)
    _, r = verify({**samples, "docx": src}, tmp_path, profile({**samples, "docx": src}), out)
    assert r["markup"]["status"] == "pass", r["markup"]


# --- 보고에 출력 글을 옮기지 않음 (리뷰 3차 H2) ---------------------------------------
# 결과 문서의 글은 양식 값(전화번호·이름)일 수 있으므로 detail·locations·표준 출력에는
# 검사 종류와 위치만 남깁니다. 필드 검사가 값 대신 「값(N자)」을 적는 것과 같은 규칙입니다.

def _leaks(proc, entry, *needles):
    seen = json.dumps(entry, ensure_ascii=False) + proc.stdout
    return [n for n in needles if n in seen]


def test_markup_report_has_no_output_text(samples, tmp_path):
    out = output(samples, tmp_path, replace_body("담당자 연락처 **010-1234-5678** 확인"))
    proc, r = verify(samples, tmp_path, profile(samples), out)
    assert r["markup"]["status"] == "fail", r["markup"]
    assert "굵게" in r["markup"]["detail"]
    assert not _leaks(proc, r["markup"], "1234", "담당자"), r["markup"]


def test_markup_counts_distinct_hits_without_locator(samples, tmp_path):
    """MD 문단은 locator가 없어도 서로 다른 두 줄은 2건으로 셉니다(중복 제거는 글 기준으로 안에서만)."""
    out = output(samples, tmp_path, fmt="md")
    out.write_text(out.read_text(encoding="utf-8") + "\n신청 **135건** 접수\n\n처리 **120건** 완료\n",
                   encoding="utf-8")
    proc, r = verify(samples, tmp_path, profile(samples, "md"), out, fmt="md")
    assert r["markup"]["status"] == "fail", r["markup"]
    assert r["markup"]["detail"].startswith("2건"), r["markup"]
    assert not _leaks(proc, r["markup"], "135건", "120건"), r["markup"]


def test_markup_table_cell_counted_once(samples, tmp_path):
    """표 칸 글은 칸·표 단위로 두 번 읽히지만 한 건입니다."""
    def edit(doc):
        doc.tables[0].cell(1, 0).paragraphs[0].runs[0].text = "**준비**"
    _, r = verify(samples, tmp_path, profile(samples), output(samples, tmp_path, edit))
    assert r["markup"]["status"] == "fail", r["markup"]
    assert r["markup"]["detail"].startswith("1건"), r["markup"]


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


def test_fields_violation_does_not_echo_value(samples, tmp_path):
    """칸 값은 개인정보일 수 있어 위반 보고에 값 대신 글자 수만 냅니다 (종단 시험 F16)."""
    secret = "010-12-345"
    proc, r = verify(samples, tmp_path, form_profile(samples, r"re:^\d+건$"), output(samples, tmp_path, fill(secret)))
    assert r["fields"]["status"] == "fail"
    assert "10자" in r["fields"]["detail"]
    assert secret not in proc.stdout + proc.stderr
    assert secret not in json.dumps(r, ensure_ascii=False)


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


def test_scope_pptx_protected_first_slide_swap_fails(tmp_path):
    """리뷰 3차 재검토(agy HIGH3-1): 보호 섹션 s2의 첫 장(글 없는 그림 장)을 지우고 그 자리에 글 장을
    끼우면, s2를 남은 장(견본 3장)에서 시작으로 잡을 때 끼운 장이 편집 섹션 s1에 묻혀 scope가 통과합니다.
    보호 섹션은 첫 장이 없으면 「찾지 못함」으로 fail입니다."""
    from pptx import Presentation

    src, out = tmp_path / "src.pptx", tmp_path / "out.pptx"
    prs = Presentation()
    for title in ("표지", None, "본문", "실적"):
        if title is None:
            prs.slides.add_slide(prs.slide_layouts[6])
        else:
            prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = title
    prs.save(src)
    prs = Presentation(src)
    prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = "끼운 글"   # 지우기 전에 넣어야 부품 이름이 안 겹침
    ids = prs.slides._sldIdLst
    new, gone = ids[-1], ids[1]
    prs.part.drop_rel(gone.rId)
    ids.remove(gone)
    ids.remove(new)
    ids.insert(1, new)
    prs.save(out)
    prof = {
        "profile_version": 1,
        "source": {"path": str(src), "format": "pptx", "sha256": sha256(src)},
        "mode": "update",
        "update": {"sections": ["s1"], "requests": ["표지 갱신"]},
        "structure": {"numbering": [], "sections": [
            {"id": "s1", "title": "표지", "level": 1, "anchor": "sl:1"},
            {"id": "s2", "title": "본문", "level": 1, "anchor": "sl:2"},
            {"id": "s3", "title": "실적", "level": 1, "anchor": "sl:4"},
        ]},
        "design": {"styles_allowed": ALLOWED},
        "sample_text": [],
    }
    pf = tmp_path / "profile.yaml"
    pf.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
    proc = uv(DOC_VERIFY, "--profile", pf, "--source", src, "--expect-sha256", sha256(src),
              "--output", out, "--out-dir", tmp_path / "verify")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = {e["id"]: e for e in json.loads((tmp_path / "verify" / "report.json").read_text(encoding="utf-8"))}
    assert report["scope"]["status"] == "fail", report["scope"]
    assert "s2" in report["scope"]["locations"], report["scope"]
    assert "s3" not in report["scope"]["locations"], report["scope"]


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


def test_r6_report_has_no_output_text(samples, tmp_path):
    """「010.1234.5678」은 1.1 모양으로 읽힙니다 — 보고에는 모양만 적고 글 토큰은 옮기지 않습니다."""
    prof = profile(samples)
    prof["structure"]["numbering"] = ["1."]
    proc, r = verify(samples, tmp_path, prof, output(samples, tmp_path, add_paras("010.1234.5678 연락처")))
    assert r["r6_numbering"]["status"] == "fail", r["r6_numbering"]
    assert "1.1" in r["r6_numbering"]["detail"]
    assert not _leaks(proc, r["r6_numbering"], "1234", "연락처"), r["r6_numbering"]


def test_r6_locator_fallback_has_no_output_text(samples, tmp_path):
    """MD·HWPX 문단은 locator가 없습니다 — 위치는 글 앞부분이 아니라 문단 순번으로 적습니다."""
    out = output(samples, tmp_path, fmt="md")
    out.write_text(out.read_text(encoding="utf-8") + "\n010.1234.5678 연락처\n", encoding="utf-8")
    prof = profile(samples, "md")
    prof["structure"]["numbering"] = ["1."]
    proc, r = verify(samples, tmp_path, prof, out, fmt="md")
    assert r["r6_numbering"]["status"] == "fail", r["r6_numbering"]
    assert r["r6_numbering"]["locations"], r["r6_numbering"]
    assert all(loc.startswith("문단 ") for loc in r["r6_numbering"]["locations"]), r["r6_numbering"]
    assert not _leaks(proc, r["r6_numbering"], "1234", "연락처"), r["r6_numbering"]


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


def _svg(path, text="구분"):
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg"><text>{text}</text></svg>', encoding="utf-8")


def test_length_pages_from_single_svg(samples, tmp_path):
    """종단 시험 F14: kordoc은 한 쪽만 렌더하면 _page_NNN 접미 없이 page.svg 하나를 냅니다."""
    render = tmp_path / "render"
    render.mkdir()
    _svg(render / "page.svg")
    prof = profile(samples)
    prof["length"] = {"pages": [1, 1]}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path), pages=True)
    assert r["length"]["status"] == "pass", r["length"]
    assert "1" in r["length"]["detail"]


def test_mixed_single_and_numbered_svg_is_usage_error(samples, tmp_path):
    render = tmp_path / "render"
    render.mkdir()
    _svg(render / "page.svg")
    _svg(render / "page_page_001.svg")
    pf = tmp_path / "profile.yaml"
    pf.write_text(yaml.safe_dump(profile(samples), allow_unicode=True), encoding="utf-8")
    proc = uv(DOC_VERIFY, "--profile", pf, "--source", samples["docx"], "--expect-sha256", sha256(samples["docx"]),
              "--output", output(samples, tmp_path), "--pages-dir", render, "--out-dir", tmp_path / "verify")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "섞여" in proc.stdout + proc.stderr


def test_length_section_chars(samples, tmp_path):
    prof = profile(samples)
    prof["structure"]["sections"][0]["length"] = {"chars": [0, 10]}
    _, r = verify(samples, tmp_path, prof, output(samples, tmp_path))
    assert r["length"]["status"] == "fail"
    assert "s1" in json.dumps(r["length"], ensure_ascii=False)



def test_length_form_ignores_section_chars_keeps_doc_pages(samples, tmp_path):
    """종단 시험 F7: form 모드의 섹션은 쓰는 글이 아니라 양식 뼈대입니다.
    마지막 섹션이 문서 끝까지(표 포함) 이어져 글자 수가 양식 전체가 되므로 섹션 chars는 보지 않고,
    값이 양식을 다음 쪽으로 밀어내지 않았는지(최상위 pages)만 판정합니다."""
    prof = form_profile(samples)
    prof["structure"]["sections"][0]["length"] = {"chars": [0, 10]}
    out = output(samples, tmp_path, fill("기획팀"))
    _, r = verify(samples, tmp_path, prof, out)
    assert r["length"]["status"] == "skip"
    assert "form" in r["length"]["detail"]
    prof["length"] = {"pages": [1, 1]}
    _, r = verify(samples, tmp_path, prof, out, pages=TWO_PAGES)
    assert r["length"]["status"] == "fail"
    assert "s1" not in json.dumps(r["length"]["locations"], ensure_ascii=False)

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
    assert not _leaks(proc, r["r1_tables"], "구분"), r["r1_tables"]  # 첫 칸 글은 옮기지 않음 (리뷰 3차 H2)


def test_broken_profile_yaml_reports_line_only(samples, tmp_path):
    """YAML 오류 보고는 줄·열만 — PyYAML 메시지의 원문 조각은 옮기지 않습니다 (리뷰 3차 M9)."""
    pf = tmp_path / "profile.yaml"
    pf.write_text(PII_YAML, encoding="utf-8")
    proc = uv(DOC_VERIFY, "--profile", pf, "--source", samples["docx"], "--expect-sha256", sha256(samples["docx"]),
              "--output", output(samples, tmp_path), "--out-dir", tmp_path / "verify")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert_no_pii(proc.stdout + proc.stderr)


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


# --- 신규 모드 (mode: new) ------------------------------------------------------------
# 계약: SKILL.md 「신규 모드 (`mode: new`)」. 견본이 없으므로 결과 DOCX는 python-docx로 새로 만듭니다.

NEW_PROFILE = FIXTURES / "new" / "doc_verify" / "profile_new_docx.yaml"
NEW_BODY = [
    ("Ⅰ. 추진 배경", "Heading 1"),
    ("○ 지역 수요가 늘어 사업을 시작한다", None),
    ("1) 현황", "Heading 2"),
    ("○ 이용 건수는 지난해보다 늘었다", None),
]


def new_profile():
    return yaml.safe_load(NEW_PROFILE.read_text(encoding="utf-8"))


def new_output(tmp_path, paras=NEW_BODY):
    from docx import Document
    doc = Document()
    for text, style in paras:
        doc.add_paragraph(text, style=style)
    out = tmp_path / "new.docx"
    doc.save(out)
    return out


def run_new(tmp_path, prof, out, *extra, placeholders=None):
    pf = tmp_path / "profile.yaml"
    pf.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
    args = ["--profile", pf, "--output", out, "--out-dir", tmp_path / "verify", *extra]
    if placeholders is not None:
        ph = tmp_path / "placeholders.yaml"
        ph.write_text(yaml.safe_dump(placeholders, allow_unicode=True), encoding="utf-8")
        args += ["--placeholders", ph]
    return uv(DOC_VERIFY, *args)


def verify_new(tmp_path, prof, out, *extra, placeholders=None):
    proc = run_new(tmp_path, prof, out, *extra, placeholders=placeholders)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    report = json.loads((tmp_path / "verify" / "report.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in report] == IDS
    return proc, {e["id"]: e for e in report}


def test_new_mode_without_source_passes(tmp_path):
    proc, r = verify_new(tmp_path, new_profile(), new_output(tmp_path))
    assert proc.returncode == 0, proc.stdout
    for cid in ("hash", "residue", "scope", "fields"):
        assert r[cid]["status"] == "skip", r[cid]
        assert "신규 모드" in r[cid]["detail"], r[cid]


def test_new_mode_with_both_source_args_still_skips_hash(samples, tmp_path):
    src = samples["docx"]
    proc, r = verify_new(tmp_path, new_profile(), new_output(tmp_path),
                         "--source", src, "--expect-sha256", "0" * 64)
    assert proc.returncode == 0, proc.stdout
    assert r["hash"]["status"] == "skip"
    assert "신규 모드" in r["hash"]["detail"]


@pytest.mark.parametrize("case", ["new-only-source", "new-only-sha", "sample-no-source", "sample-only-sha"])
def test_new_mode_source_arg_usage_errors(samples, tmp_path, case):
    src = samples["docx"]
    if case.startswith("new"):
        prof, out = new_profile(), new_output(tmp_path)
    else:
        prof, out = profile(samples), output(samples, tmp_path)
    extra = {
        "new-only-source": ["--source", src],
        "new-only-sha": ["--expect-sha256", sha256(src)],
        "sample-no-source": [],
        "sample-only-sha": ["--expect-sha256", sha256(src)],
    }[case]
    proc = run_new(tmp_path, prof, out, *extra)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stderr.strip()
    assert not (tmp_path / "verify" / "report.json").exists()


def _section_limits(prof, limits):
    for s, limit in zip(prof["structure"]["sections"], limits):
        s["length"] = {"chars": [0, limit]}
    return prof


def test_new_mode_heading_anchor_ignores_chapter_number(tmp_path):
    """「Ⅰ. 추진 배경」은 h:"추진배경"과, 「1) 현황」은 h:"현황"과 맞아야 섹션 분량을 잴 수 있습니다."""
    prof = _section_limits(new_profile(), [5, 5])
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert proc.returncode == 1
    assert r["length"]["status"] == "fail", r["length"]
    assert {"s1", "s2"} <= set(r["length"]["locations"])
    prof = _section_limits(new_profile(), [500, 500])
    _, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert r["length"]["status"] == "pass", r["length"]


@pytest.mark.parametrize("body", [
    [("□ 추진 배경", "Heading 1"), ("○ 지역 수요가 늘어 사업을 시작한다", None),
     ("○ 1) 현황", "Heading 2"), ("○ 이용 건수는 지난해보다 늘었다", None)],
    [("현황", None)] + NEW_BODY,
], ids=["bullet-heading", "stray-line-before-s1"])
def test_new_mode_section_length_fails_not_skips(tmp_path, body):
    """리뷰 3차 H3: 「□ 추진 배경」 제목이나 s1 앞의 「현황」 한 줄 때문에 섹션을 놓치면 분량 초과가
    fail 대신 skip으로 숨었습니다."""
    prof = _section_limits(new_profile(), [5, 5])
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path, body))
    assert proc.returncode == 1, proc.stdout
    assert r["length"]["status"] == "fail", r["length"]
    assert {"s1", "s2"} <= set(r["length"]["locations"])
    assert "찾지 못" not in r["length"]["detail"]


def test_new_mode_fall_forward_start_does_not_cut_previous_section(tmp_path):
    """리뷰 3차 H3 재검토(codex): s2 제목이 빠졌고 본문에 「현황」 한 줄만 있을 때, 그 줄을 뒤로 찾아
    s2 시작으로 잡더라도 s1 끝을 자르면 안 됩니다 — 자르면 s1 분량 초과가 pass로 숨습니다."""
    long = "가" * 60
    body = [("현황", None), ("Ⅰ. 추진 배경", "Heading 1"), (long, None), ("현황", None), (long, None)]
    prof = _section_limits(new_profile(), [100, 100])
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path, body))
    assert proc.returncode == 1, proc.stdout
    assert r["length"]["status"] == "fail", r["length"]
    assert "s1" in r["length"]["locations"]


LONG = "가" * 120


@pytest.mark.parametrize("body", [
    [("1. 추진 배경", None), ("2. 현황", None),
     ("Ⅰ. 추진 배경", "Heading 1"), (LONG, None), ("Ⅱ. 현황", "Heading 1"), ("짧다", None)],
    [("Ⅰ. 추진 배경", "Heading 1"), ("○ 현황", None), (LONG, None), ("1) 현황", "Heading 2"), ("짧다", None)],
    [("추진 배경", None), ("현황", None),
     ("Ⅰ. 추진 배경", "Heading 1"), (LONG, None), ("Ⅱ. 현황", "Heading 1"), ("짧다", None)],
], ids=["toc-lines-before-headings", "bullet-line-inside-s1", "plain-summary-lines"])
def test_new_mode_body_line_does_not_steal_heading_anchor(tmp_path, body):
    """리뷰 3차 재검토(agy HIGH1·HIGH2): 목차 줄 「1. 추진 배경」이나 본문 「○ 현황」이 제목보다 먼저
    h: anchor에 잡히면 s1이 잘려 분량 초과가 pass로 숨습니다. 제목 스타일 문단이 있으면 그 문단만
    셉니다."""
    prof = _section_limits(new_profile(), [100, 100])
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path, body))
    assert proc.returncode == 1, proc.stdout
    assert r["length"]["status"] == "fail", r["length"]
    assert "s1" in r["length"]["locations"]
    assert "찾지 못" not in r["length"]["detail"]


def test_new_mode_body_line_after_sections_is_not_heading(tmp_path):
    """agy HIGH2 반대 순서: s2 제목이 없고 s1 뒤 본문에 「○ 현황」만 있으면 s2는 찾지 못함(skip 메모)이지
    그 줄로 s2를 잡아 분량을 재지 않습니다."""
    body = [("Ⅰ. 현황", "Heading 1"), (LONG, None), ("Ⅱ. 추진 배경", "Heading 1"), ("○ 현황", None)]
    prof = _section_limits(new_profile(), [500, 500])
    _, r = verify_new(tmp_path, prof, new_output(tmp_path, body))
    assert "s2" in r["length"]["detail"] and "찾지 못" in r["length"]["detail"], r["length"]


def test_new_mode_normal_style_heading_still_anchors(tmp_path):
    """리뷰 3차 재검토(codex HIGH1): 다른 제목은 Heading 스타일인데 섹션 제목 한 줄만 일반 스타일이면,
    제목 스타일 문단만 세는 규칙으로는 그 섹션을 놓쳐 분량 초과가 skip으로 숨습니다. 제목에 맞는 글이
    없으면 일반 문단을 글이 똑같을 때 셉니다."""
    body = [("표지", "Heading 1"), ("추진 배경", None), (LONG, None)]
    prof = _section_limits(new_profile(), [100])
    prof["structure"]["sections"] = prof["structure"]["sections"][:1]
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path, body))
    assert proc.returncode == 1, proc.stdout
    assert r["length"]["status"] == "fail", r["length"]
    assert "s1" in r["length"]["locations"]


def test_new_mode_normal_style_heading_ends_previous_section(tmp_path):
    """codex HIGH1 후반: s2 제목만 일반 스타일이면 s1이 s2 글까지 먹어 s1 자리표시 검사가 s2의 글로
    거짓 통과합니다."""
    body = [("Ⅰ. 추진 배경", "Heading 1"), ("짧다", None), ("현황", None), ("[담당자]", None)]
    _, r = verify_new(tmp_path, new_profile(), new_output(tmp_path, body),
                      placeholders=[{"locator": "s1", "expect": "[담당자]"}])
    assert r["placeholder"]["status"] == "fail", r["placeholder"]


def test_new_mode_unstyled_list_bullet_heading_skips_with_note(tmp_path):
    """제목 스타일이 없는 문서에서 「○ 현황」은 본문 목록 줄과 가를 수 없어 제목으로 보지 않습니다
    (codex 재검토 HIGH2, 받지 않음). 대신 못 찾은 섹션은 detail에 드러나야 합니다."""
    body = [("□ 추진배경", None), (LONG, None), ("○ 현황", None), ("짧다", None)]
    _, r = verify_new(tmp_path, _section_limits(new_profile(), [500, 500]), new_output(tmp_path, body))
    assert "s2" in r["length"]["detail"] and "찾지 못" in r["length"]["detail"], r["length"]


def test_new_mode_missing_section_length_skips(tmp_path):
    prof = _section_limits(new_profile(), [500, 500])
    prof["structure"]["sections"].append(
        {"id": "s3", "title": "기대 효과", "level": 1, "anchor": 'h:"기대효과"', "length": {"chars": [0, 1]}})
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert r["length"]["status"] != "fail"
    assert "s3" in r["length"]["detail"]


@pytest.mark.parametrize("spec", [{"lines": [1, 3]}, {"pages": [0, 1]}])
def test_new_mode_missing_section_noted_for_any_length_key(tmp_path, spec):
    """종단 시험 결함: 글자 수(chars)가 없는 섹션은 제목을 못 찾아도 detail에 남지 않았습니다.
    계약(SKILL 「신규 모드」)은 못 찾은 섹션을 length detail에 적으라고 합니다."""
    prof = new_profile()
    prof["structure"]["sections"].append(
        {"id": "s3", "title": "기대 효과", "level": 1, "anchor": 'h:"기대효과"', "length": spec})
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert "s3 섹션 시작을 찾지 못" in r["length"]["detail"], r["length"]


@pytest.mark.parametrize("locator,status", [("s2", "pass"), ("s1", "fail")])
def test_new_mode_placeholder_uses_loose_anchor(tmp_path, locator, status):
    phs = [{"locator": locator, "expect": "이용 건수"}]
    _, r = verify_new(tmp_path, new_profile(), new_output(tmp_path), placeholders=phs)
    assert r["placeholder"]["status"] == status, r["placeholder"]


def test_new_mode_markup_has_no_sample_exception(tmp_path):
    """견본 대조 예외 없이 모든 마크다운 표지를 봅니다.
    (작업 지시서 시험 5의 「○○」는 SKILL 계약상 markup 대상이 아니어서 이 시험으로 바꿈 — 조정자 승인.)"""
    out = new_output(tmp_path, NEW_BODY + [("○ 신청은 **135건**이다", None)])
    proc, r = verify_new(tmp_path, new_profile(), out)
    assert proc.returncode == 1
    assert r["markup"]["status"] == "fail", r["markup"]


def test_new_mode_empty_tokens_skip_r5(tmp_path):
    prof = new_profile()
    prof["design"].update({"type": {}, "color": {}, "styles_allowed": []})
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert r["r5_tokens"]["status"] == "skip", r["r5_tokens"]


@pytest.mark.parametrize("types", [{}, {"body": {"font": "맑은 고딕", "pt": 10.5}}, {"h1": "맑은 고딕"}])
def test_new_mode_empty_tokens_skip_r4(tmp_path, types):
    """신규 모드에서 비교할 제목 토큰이 하나도 없으면 통과라 말할 근거가 없어 skip (SKILL 「신규 모드」 빈 토큰)."""
    prof = new_profile()
    prof["design"].update({"type": types, "color": {}, "styles_allowed": []})
    proc, r = verify_new(tmp_path, prof, new_output(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert r["r4_headings"]["status"] == "skip", r["r4_headings"]
    assert "design.type" in r["r4_headings"]["detail"]


def test_new_mode_hwpx_shape_ids_skip(samples, tmp_path):
    prof = new_profile()
    prof["structure"]["numbering"] = []
    out = tmp_path / "new.hwpx"
    shutil.copy(samples["hwpx"], out)
    _, r = verify_new(tmp_path, prof, out)
    for cid in ("r4_headings", "r5_tokens"):
        assert r[cid]["status"] == "skip", r[cid]
        assert "신규 모드" in r[cid]["detail"]
    errors = [k for k, v in r.items() if str(v.get("detail", "")).startswith("검사 오류")]
    assert not errors, errors


def test_new_mode_md_output_skips_markup(tmp_path):
    """MD 출력은 마크다운이 곧 형식이므로 표·제목·굵게가 있어도 markup은 skip입니다."""
    out = tmp_path / "new.md"
    out.write_text("# 추진 배경\n\n- 신청은 **135건**이다\n\n## 현황\n\n| 구분 | 건수 |\n|---|---|\n| 신청 | 135 |\n",
                   encoding="utf-8")
    prof = new_profile()
    prof["design"] = {"route": {"tool": "copy"}}
    _, r = verify_new(tmp_path, prof, out)
    assert r["markup"]["status"] == "skip", r["markup"]
    assert "신규 모드" in r["markup"]["detail"]


def test_r6_skips_when_numbering_declared_but_text_has_no_markers(tmp_path):
    """자동 번호(DOCX numPr)·HWPX 프리셋 부호는 글에 없으므로 「부호 없음」을 통과로 보지 않고 skip합니다."""
    prof = new_profile()
    prof["structure"]["numbering"] = ["□", "ㅇ", "-"]
    out = new_output(tmp_path, [("추진 배경", "Heading 1"), ("지역 수요가 늘어 사업을 시작한다", None)])
    proc, r = verify_new(tmp_path, prof, out)
    assert r["r6_numbering"]["status"] == "skip", r["r6_numbering"]
    assert "렌더로 확인" in r["r6_numbering"]["detail"]


def test_r6_passes_without_markers_when_no_numbering_declared(tmp_path):
    prof = new_profile()
    prof["structure"]["numbering"] = []
    out = new_output(tmp_path, [("추진 배경", "Heading 1"), ("지역 수요가 늘어 사업을 시작한다", None)])
    _, r = verify_new(tmp_path, prof, out)
    assert r["r6_numbering"]["status"] == "pass", r["r6_numbering"]
