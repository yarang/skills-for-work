"""기본 docx 테마 수용 테스트.

계약: docs/design.md §9.5 (토큰 파일은 재추출로 검사), docs/briefs/brief_newdoc.md N3.
default.docx에서 토큰을 다시 뽑아 default.tokens.yaml과 비교하고, 플러그인 카탈로그가
check를 통과하는지, pandoc 변환 결과가 styles_allowed·A4를 지키는지 봅니다.
"""
import shutil
import subprocess

import docx
import pytest
import yaml
from docx.oxml.ns import qn
from docx.shared import Emu

from conftest import ROOT, uv

TEMPLATES = ROOT / "newdoc/templates"
THEME = TEMPLATES / "themes/docx"
DOCX = THEME / "default.docx"
TOKENS = THEME / "default.tokens.yaml"
CATALOG = ROOT / "newdoc/skills/newdoc-workflow/scripts/catalog.py"
PANDOC = shutil.which("pandoc") or shutil.which("pandoc", path="/opt/homebrew/bin")
LEVELS = {"Heading 1": "h1", "Heading 2": "h2", "Heading 3": "h3"}


def _mm(length) -> int:
    return round(Emu(length).mm)


def _rpr_value(style, getter):
    """스타일 사슬을 따라 올라가며 처음 정해진 값을 돌려준다."""
    while style is not None:
        rpr = style.element.find(qn("w:rPr"))
        value = getter(rpr) if rpr is not None else None
        if value is not None:
            return value
        style = style.base_style
    return None


def _font(rpr):
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        return None
    return fonts.get(qn("w:eastAsia")) or fonts.get(qn("w:ascii"))


def _size(rpr):
    sz = rpr.find(qn("w:sz"))
    return int(sz.get(qn("w:val"))) / 2 if sz is not None else None


def _bold(rpr):
    b = rpr.find(qn("w:b"))
    if b is None:
        return None
    return b.get(qn("w:val"), "true") not in ("0", "false")


def _defaults(document):
    node = document.styles.element.find(qn("w:docDefaults"))
    rpr = node.find(qn("w:rPrDefault")).find(qn("w:rPr"))
    return {"font": _font(rpr), "pt": _size(rpr), "bold": _bold(rpr)}


def _style_type(document, name) -> dict:
    style = document.styles[name]
    base = _defaults(document)
    got = {
        "font": _rpr_value(style, _font) or base["font"],
        "pt": _rpr_value(style, _size) or base["pt"],
    }
    bold = _rpr_value(style, _bold)
    if bold if bold is not None else base["bold"]:
        got["bold"] = True
    return got


def _extract(document) -> dict:
    sec = document.sections[0]
    portrait = sec.page_height > sec.page_width
    page = {
        "size": "A4" if (_mm(sec.page_width), _mm(sec.page_height)) in ((210, 297), (297, 210)) else None,
        "orientation": "portrait" if portrait else "landscape",
        "margins_mm": [_mm(sec.top_margin), _mm(sec.bottom_margin), _mm(sec.left_margin), _mm(sec.right_margin)],
    }
    kinds = {"body": _style_type(document, "Body Text")}
    kinds.update({key: _style_type(document, name) for name, key in LEVELS.items()})
    return {"page": page, "type": kinds}


@pytest.fixture(scope="module")
def tokens() -> dict:
    return yaml.safe_load(TOKENS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def document():
    return docx.Document(str(DOCX))


def _norm(value):
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


# --- 1 재추출 ---------------------------------------------------------------------

def test_tokens_match_docx(document, tokens):
    got = _extract(document)
    assert _norm(got["page"]) == _norm(tokens["page"])
    assert _norm(got["type"]) == _norm(tokens["type"])
    assert tokens["color"] == {}


def test_normal_matches_body(document, tokens):
    assert _norm(_style_type(document, "Normal")) == _norm(tokens["type"]["body"])


def test_east_asia_and_latin_fonts_set(document):
    for name in ("Normal", "Body Text", *LEVELS):
        fonts = document.styles[name].element.find(qn("w:rPr")).find(qn("w:rFonts"))
        assert fonts is not None, name
        for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
            assert fonts.get(qn(attr)) == "맑은 고딕", (name, attr)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme"):
            assert fonts.get(qn(attr)) is None, (name, attr)


def test_styles_allowed_exist(document, tokens):
    names = {s.name for s in document.styles}
    allowed = tokens["styles_allowed"]
    assert allowed and len(set(allowed)) == len(allowed)
    assert set(allowed) <= names
    assert {"Title", "Heading 1", "Heading 2", "Heading 3", "Body Text"} <= set(allowed)


# --- 2 카탈로그 -------------------------------------------------------------------

def test_plugin_catalog_check():
    proc = uv(CATALOG, "check", TEMPLATES / "catalog.yaml")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_plugin_catalog_content():
    data = yaml.safe_load((TEMPLATES / "catalog.yaml").read_text(encoding="utf-8"))
    presets = ["보고서", "계획서", "기안문", "회의록", "보도자료"]
    assert data == {
        "catalog_version": 1,
        "themes": {
            "docx": {"default": {"reference_doc": "themes/docx/default.docx",
                                 "tokens": "themes/docx/default.tokens.yaml"}},
            "hwpx": {"default": {"preset_map": {p: p for p in presets}}},
            "md": {},
        },
        "fixed": [],
    }


# --- 3 pandoc 변환 ----------------------------------------------------------------

SAMPLE = """# 문서 제목

본문 첫 문단입니다.

## 추진 배경

둘째 문단입니다. 이어지는 설명입니다.

- 첫째 항목
- 둘째 항목

### 세부 내용

| 구분 | 내용 |
|------|------|
| 가 | 나 |
"""


def _paragraph_styles(document) -> set:
    names = {p.style.name for p in document.paragraphs}
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                names.update(p.style.name for p in cell.paragraphs)
    names.update(t.style.name for t in document.tables if t.style is not None)
    return names


@pytest.mark.skipif(PANDOC is None, reason="pandoc 없음")
def test_pandoc_output_obeys_tokens(tmp_path, tokens):
    src = tmp_path / "in.md"
    src.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "out.docx"
    proc = subprocess.run([PANDOC, str(src), "-o", str(out), "--reference-doc", str(DOCX)],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    result = docx.Document(str(out))
    used = _paragraph_styles(result)
    assert used <= set(tokens["styles_allowed"]), used - set(tokens["styles_allowed"])
    sec = result.sections[0]
    assert (_mm(sec.page_width), _mm(sec.page_height)) == (210, 297)
    assert [_mm(sec.top_margin), _mm(sec.bottom_margin),
            _mm(sec.left_margin), _mm(sec.right_margin)] == tokens["page"]["margins_mm"]
