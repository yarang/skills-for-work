"""스크립트 수용 테스트 공용 픽스처.

DOCX·PPTX·MD 견본은 테스트마다 코드로 만들고, HWPX는 kordoc이 만든
`fixtures/sample.hwpx`(최상위 hp:tbl 5개)를 씁니다. 표·문단 번호의 정답은
여기 `EXPECTED_*`에 적어 두고 세 스크립트가 모두 이 값을 내야 합니다.
"""
import copy
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

PROFILE_EXTRACT = ROOT / "template/skills/template-analysis/scripts/profile_extract.py"
PATCH_DOCX = ROOT / "skills/format-docx/scripts/patch_docx.py"
PATCH_PPTX = ROOT / "skills/format-pptx/scripts/patch_pptx.py"
RENDER = ROOT / "skills/doc-verify/scripts/render.py"
DOC_VERIFY = ROOT / "skills/doc-verify/scripts/doc_verify.py"

BODY_SENTENCE = "2026년 상반기 신청 건수는 120건으로 전년보다 늘었다."

EXPECTED_TABLES = {
    "hwpx": [
        {"at": "t:1", "rows": 1, "cols": 1, "first": "○○사업 추진계획(안)", "nested": 0},
        {"at": "t:2", "rows": 1, "cols": 1, "nested": 0},
        {"at": "t:3", "rows": 1, "cols": 3, "nested": 0},
        {"at": "t:4", "rows": 1, "cols": 3, "nested": 0},
        {"at": "t:5", "rows": 3, "cols": 3, "first": "구분", "last": "운영팀", "nested": 0},
    ],
    "docx": [
        {"at": "t:1", "rows": 3, "cols": 3, "first": "구분", "last": "120건", "nested": 0},
        {"at": "t:2", "rows": 2, "cols": 2, "first": "단계", "last": "운영팀 담당", "nested": 1},
        {"at": "t:3", "rows": 1, "cols": 1, "first": "요약 상자 글입니다", "last": "요약 상자 글입니다", "nested": 0},
    ],
    "pptx": [
        {"at": "t:1", "slide": 2, "rows": 3, "cols": 3, "first": "구분", "last": "운영팀"},
        {"at": "t:2", "slide": 3, "rows": 2, "cols": 2, "first": "항목", "last": "50건"},
        {"at": "t:3", "slide": 3, "rows": 2, "cols": 2, "first": "그룹 표", "last": "끝칸"},
    ],
    "md": [
        {"at": "t:1", "rows": 3, "cols": 3, "first": "구분", "last": "운영팀"},
        {"at": "t:2", "rows": 2, "cols": 2, "first": "항목", "last": "50건"},
    ],
}


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=300, **kw)


def uv(script, *args, **kw):
    return run(["uv", "run", "--quiet", "--python", "3.13", script, *args], **kw)


# --- DOCX ------------------------------------------------------------------------

def build_docx(path: Path) -> dict:
    """본문: 제목, 제목1, 본문, 빈 문단, 표1, 제목1, 목록, 표2(안에 표), 표3(틀 표).

    머리글에 표가 하나 있지만 세지 않습니다.
    반환값: 최상위 문단 번호 정답 {글: "p:N"}.
    """
    from docx import Document

    doc = Document()
    doc.add_paragraph("○○사업 추진계획(안)", style="Title")
    doc.add_paragraph("1. 추진 배경", style="Heading 1")
    doc.add_paragraph(BODY_SENTENCE)
    doc.add_paragraph("")
    t1 = doc.add_table(rows=3, cols=3)
    for r, row in enumerate([["구분", "기간", "담당"], ["준비", "1월", "기획팀"], ["합계", "120건", ""]]):
        for c, text in enumerate(row):
            t1.cell(r, c).text = text
    doc.add_paragraph("2. 추진 일정", style="Heading 1")
    doc.add_paragraph("준비 단계는 1월에 기획팀이 맡는다", style="List Bullet")
    t2 = doc.add_table(rows=2, cols=2)
    t2.cell(0, 0).text = "단계"
    t2.cell(0, 1).text = "내용"
    t2.cell(1, 0).text = "시행"
    inner = t2.cell(1, 1).add_table(rows=1, cols=1)
    inner.cell(0, 0).text = "안쪽 표"
    t2.cell(1, 1).add_paragraph("운영팀 담당")
    t3 = doc.add_table(rows=1, cols=1)
    t3.cell(0, 0).text = "요약 상자 글입니다"
    header = doc.sections[0].header
    header.add_table(rows=1, cols=1, width=doc.sections[0].page_width // 2).cell(0, 0).text = "머리글 표"
    doc.save(path)

    from docx.oxml.ns import qn
    body = Document(path).element.body
    paras = [p for p in body.iterchildren(qn("w:p"))]
    answer = {}
    for i, p in enumerate(paras, 1):
        text = "".join(t.text or "" for t in p.iter(qn("w:t")))
        answer.setdefault(text, f"p:{i}")
    return answer


# --- PPTX ------------------------------------------------------------------------

def build_pptx(path: Path) -> None:
    """슬라이드1 제목, 슬라이드2 본문+표, 슬라이드3 표 하나와 그룹 안 표 하나."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.shapes.title.text = "○○사업 추진계획(안)"
    s1.placeholders[1].text = "기획팀"

    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.shapes.title.text = "추진 일정"
    body = s2.placeholders[1].text_frame
    body.text = "준비 단계는 1월에 기획팀이 맡는다"
    p = body.add_paragraph()
    p.text = "시행 단계는 2~6월에 운영팀이 맡는다"
    p.level = 1
    t = s2.shapes.add_table(3, 3, Inches(1), Inches(4), Inches(6), Inches(1.5)).table
    for r, row in enumerate([["구분", "기간", "담당"], ["준비", "1월", "기획팀"], ["시행", "2~6월", "운영팀"]]):
        for c, text in enumerate(row):
            t.cell(r, c).text = text

    s3 = prs.slides.add_slide(prs.slide_layouts[5])
    s3.shapes.title.text = "실적"
    ta = s3.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(3), Inches(1)).table
    for (r, c), text in {(0, 0): "항목", (0, 1): "값", (1, 0): "신청", (1, 1): "50건"}.items():
        ta.cell(r, c).text = text
    group = s3.shapes.add_group_shape()
    gf = s3.shapes.add_table(2, 2, Inches(5), Inches(2), Inches(3), Inches(1))
    for (r, c), text in {(0, 0): "그룹 표", (0, 1): "열", (1, 0): "행", (1, 1): "끝칸"}.items():
        gf.table.cell(r, c).text = text
    group._element.append(copy.deepcopy(gf._element))
    gf._element.getparent().remove(gf._element)
    prs.save(path)


# --- MD --------------------------------------------------------------------------

MD_TEXT = f"""# ○○사업 추진계획(안)

## 1. 추진 배경

{BODY_SENTENCE}

| 구분 | 기간 | 담당 |
|---|---|---|
| 준비 | 1월 | 기획팀 |
| 시행 | 2~6월 | 운영팀 |

```
| 코드 | 블록 |
|---|---|
| 세지 | 않음 |
```

## 2. 실적

- 신청 건수는 계속 늘고 있다

| 항목 | 값 |
|:---|---:|
| 신청 | 50건 |
"""


@pytest.fixture
def samples(tmp_path):
    d = tmp_path / "samples"
    d.mkdir()
    docx = d / "sample.docx"
    pptx = d / "sample.pptx"
    md = d / "sample.md"
    hwpx = d / "sample.hwpx"
    para = build_docx(docx)
    build_pptx(pptx)
    md.write_text(MD_TEXT, encoding="utf-8")
    shutil.copy(FIXTURES / "sample.hwpx", hwpx)
    return {"docx": docx, "pptx": pptx, "md": md, "hwpx": hwpx, "docx_paras": para}
