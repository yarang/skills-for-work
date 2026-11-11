"""deck-design 생성기(build_deck.py) 수용 테스트.

계약: skills/deck-design/SKILL.md 「원고와 visual 주석」·「글자 크기 맞춤」·
「배치 세부」·「렌더 검수」.

견본 원고는 새로 썼다(주제: 사내 문서 도구 사용 교육). 아이콘·그림 PNG는
테스트가 직접 만든 최소 PNG(흰 단색)이고, 다이어그램은 가로세로비 3.0(넓음)과
1.5(좁음) 두 종류로 준비한다.
"""
import math
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from conftest import ROOT, uv

SCRIPTS = ROOT / "skills/deck-design/scripts"
BUILD = SCRIPTS / "build_deck.py"
RENDER_SVGS = SCRIPTS / "render_svgs.sh"

sys.path.insert(0, str(SCRIPTS))

from _deck_layouts import DeckContext  # noqa: E402
from _deck_parse import Assets as DeckAssets, Config as DeckConfig, parse_doc  # noqa: E402
from _deck_text import (fit_font_size, pill_width_in, text_width_pt, visible_text,  # noqa: E402
                        widest_word_pt)
from _deck_theme import Theme  # noqa: E402
import build_deck  # noqa: E402

EMU = 914400
ICONS = ["doc", "search", "share", "chart", "flag"]


# --- 픽스처 -----------------------------------------------------------------------

def write_png(path: Path, w: int, h: int) -> Path:
    """zlib+struct로 흰 단색 최소 PNG(8비트 회색조)를 직접 쓴다."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff" * w for _ in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return path


MD = """# 사내 문서 도구 사용 교육

> 대상: 입사 3개월 이내 신규 직원
> 기준: 2026년 11월 사내 교육 자료

<!-- visual: {"hero": "cover", "strip": ["계획", "작성", "검토", "공유"]} -->

## 1. 도구 소개

### 1.1 무엇을 배우나
<!-- visual: {"layout": "icon-rows", "icons": ["doc", "search", "share"], "stat": {"value": "3종", "label": "공통 문서 도구", "note": "전 부서 같은 규칙"}} -->
- **문서 작성**: 표준 서식으로 보고서를 씁니다
- **자료 검색**: 공유 드라이브에서 과거 문서를 찾습니다
- **협업 공유**: 링크 하나로 동료와 문서를 나눕니다
- 예: "지난주 회의록을 서식에 맞춰 정리해 줘"

> 발표 노트: 첫 시간이므로 화면을 함께 띄워 실습 위주로 진행한다.

### 1.2 어디까지 왔나
<!-- visual: {"layout": "spotlight", "icon": "flag", "active": 0} -->
- 오늘은 첫 단계인 계획 세우기를 다룹니다
- 나머지 단계는 다음 교육에서 이어집니다

## 2. 주요 기능

### 2.1 기능 카드
<!-- visual: {"layout": "cards", "cols": 2, "icons": ["doc", "search", "share", "chart"], "highlight": [0], "count_badge": true, "chips": true} -->
- **보고서 작성**: `weekly-report` 서식으로 주간 보고서를 씁니다. 머리는 한 줄로 요약하고 본문은 항목별로 나누며 마지막에 다음 주 계획을 적습니다. 처음 쓰는 사람은 지난주 보고서를 복사해 고치는 방법으로 시작합니다
- **자료 검색**: 폴더 규칙에 따라 과거 문서를 찾습니다
- **협업 공유**: 링크 권한을 정해 문서를 나눕니다
- **통계 확인**: `usage-stat` 화면에서 문서 사용량을 봅니다
- 활용 단계: 초안, 검토, 승인, 공유

### 2.2 문서 만들기 절차
<!-- visual: {"layout": "steps"} -->
- 주제와 독자를 정합니다
- 표준 서식을 골라 초안을 씁니다
- 동료 검토를 받아 고칩니다
- 최종본을 공유 드라이브에 올립니다

### 2.3 처리 흐름
<!-- visual: {"layout": "image"} -->
![처리 흐름](diagrams/flow-wide.svg)
- 초안이 검토를 거쳐 공유로 이어집니다
- 단계마다 담당자가 다릅니다

### 2.4 화면 구성
<!-- visual: {"layout": "image"} -->
![화면 구성](diagrams/screen-narrow.svg)
- 왼쪽에 문서 목록이 나타납니다
- 오른쪽에서 본문을 편집합니다

### 2.5 문서 종류
<!-- visual: {"layout": "table", "badge_col": 2} -->
| 종류 | 용도 | 단계 |
|---|---|---|
| 보고서 | 주간 보고 | 초안 |
| 기획서 | 신규 사업 | 검토 |
| 회의록 | 회의 기록 | 승인 |

### 2.6 도입 일정
<!-- visual: {"layout": "timeline", "icons": ["flag", "doc", "search", "share"]} -->
| 단계 | 내용 |
|---|---|
| 10월 | 도구 설치와 계정 발급 |
| 11월 | 부서별 교육을 진행하고 담당자를 지정합니다 |
| 12월 | 표준 서식을 정착시킵니다 |
| 1월 | 사용 현황을 점검합니다 |

### 2.7 좋은 문서의 공식
<!-- visual: {"layout": "equation", "terms": [{"icon": "doc", "label": "표준 서식"}, {"icon": "search", "label": "과거 사례"}], "result": {"icon": "share", "label": "좋은 문서"}} -->
- 서식과 사례를 더하면 처음부터 쓰는 시간이 줄어듭니다

### 2.8 오늘의 정리 (핵심)
<!-- visual: {"layout": "bullets", "badge": "핵심", "dark": true} -->
- 문서는 서식부터 고릅니다
- 검색으로 지난 문서를 활용합니다
- 공유 링크로 버전을 하나로 묶습니다

> 발표 노트: 마지막에 실습 과제를 안내한다.

## 3. 마무리

### 3.1 다음 단계
<!-- visual: {"layout": "bullets"} -->
- 다음 주 그룹 실습에 참여하세요
- 궁금한 점은 문의 창구로 보내주세요

## 부록. 관리자 안내 (덱에 넣지 않음)

### 계정 관리
<!-- visual: {"layout": "bullets"} -->
- 관리자 화면에서 계정을 관리합니다
"""


@pytest.fixture
def assets(tmp_path) -> Path:
    root = tmp_path / "assets"
    for name in ICONS:
        write_png(root / "icons" / f"{name}.png", 64, 64)
    write_png(root / "illustrations" / "cover.png", 400, 300)
    write_png(root / "diagrams" / "flow-wide.png", 1200, 400)    # 가로세로비 3.0
    write_png(root / "diagrams" / "screen-narrow.png", 600, 400)  # 가로세로비 1.5
    return root


@pytest.fixture
def built(tmp_path, assets):
    md = assets / "training.md"
    md.write_text(MD, encoding="utf-8")
    out = assets / "deck.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    return {"proc": proc, "prs": Presentation(out), "md": md, "out": out,
            "assets": assets, "tmp": tmp_path}


# --- 헬퍼 -------------------------------------------------------------------------

def find_slide(prs, text):
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame and text in sh.text_frame.text:
                return slide
    raise AssertionError(f"슬라이드를 찾을 수 없음: {text}")


def all_text(prs) -> str:
    chunks = []
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame:
                chunks.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                chunks.extend(cell.text_frame.text for row in sh.table.rows
                              for cell in row.cells)
    return "\n".join(chunks)


def role_sizes(slide, role: str) -> set[float]:
    """역할 이름을 가진 도형들의 run 글자 크기 모음."""
    sizes = set()
    for sh in slide.shapes:
        if sh.name == role and sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.size:
                        sizes.add(r.font.size.pt)
    return sizes


def shapes_by_role(slide, role: str) -> list:
    return [sh for sh in slide.shapes if sh.name == role]


# --- 1 슬라이드 수 ----------------------------------------------------------------

def test_slide_count(built):
    # 표지 1 + 목차 1 + 구분(2장짜리 섹션, 8장짜리 섹션) 2 + 내용 11 = 15.
    # 1장짜리 '3. 마무리'는 구분 슬라이드가 없고, 부록은 skip_marker로 통째로 제외.
    prs = built["prs"]
    dividers, contents = 2, 11
    assert len(prs.slides) == 1 + 1 + dividers + contents
    assert f"({len(prs.slides)} slides)" in built["proc"].stdout
    assert "만들었음:" in built["proc"].stdout


# --- 2 경계 안 --------------------------------------------------------------------

def test_all_shapes_within_bounds(built):
    prs = built["prs"]
    for i, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            l, t = sh.left / EMU, sh.top / EMU
            r, b = (sh.left + sh.width) / EMU, (sh.top + sh.height) / EMU
            assert l >= -0.01 and t >= -0.01, (i, sh.name, l, t)
            assert r <= 13.333 + 0.01 and b <= 7.5 + 0.01, (i, sh.name, r, b)


# --- 3 같은 역할 글자 크기 통일(cards) ---------------------------------------------

def test_card_body_sizes_unified_to_minimum(built):
    slide = find_slide(built["prs"], "기능 카드")
    bodies = shapes_by_role(slide, "card-body")
    assert len(bodies) >= 2
    unified = role_sizes(slide, "card-body")
    assert len(unified) == 1, f"card-body 크기가 들쭉날쭉: {unified}"
    # 짧은 본문 카드 하나만으로 맞췄다면 더 큰 크기가 나온다 — 통일이 실제로 일어남.
    short = min(bodies, key=lambda sh: len(sh.text_frame.text))
    alone = fit_font_size([short.text_frame.text], short.width / EMU,
                          short.height / EMU, 18, 12)
    assert next(iter(unified)) < alone, (unified, alone)
    heads = role_sizes(slide, "card-head")
    assert len(heads) == 1, f"card-head 크기가 들쭉날쭉: {heads}"


# --- 4 타임라인 설명 통일 ----------------------------------------------------------

def test_timeline_desc_sizes_unified(built):
    slide = find_slide(built["prs"], "도입 일정")
    descs = shapes_by_role(slide, "timeline-desc")
    assert len(descs) == 4
    assert len(role_sizes(slide, "timeline-desc")) == 1
    assert len(role_sizes(slide, "timeline-title")) == 1


# --- 5 skip 섹션 제외 --------------------------------------------------------------

def test_skipped_section_absent(built):
    assert "관리자 안내" in built["md"].read_text(encoding="utf-8")  # 원고에는 있다
    assert "관리자 안내" not in all_text(built["prs"])
    assert "계정 관리" not in all_text(built["prs"])


# --- 6 visual 주석 JSON 오류 -------------------------------------------------------

@pytest.mark.parametrize("payload", ['{"layout": "cards"', '["x"]'])
def test_visual_json_error_stops(tmp_path, assets, payload):
    md = assets / "bad.md"
    md.write_text(
        f"# 교육 자료\n\n## 1. 섹션\n\n### 카드 구성\n"
        f"<!-- visual: {payload} -->\n- 항목 하나\n", encoding="utf-8")
    out = assets / "bad.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 1
    assert "카드 구성" in proc.stderr
    assert "visual 주석 JSON 오류" in proc.stderr
    assert not out.exists()


# --- 7 check_bounds 단위 테스트 ----------------------------------------------------

def test_check_bounds_reports_slide_and_title():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(13.0), Inches(1.0), Inches(2.0), Inches(0.5))
    with pytest.raises(ValueError) as ei:
        build_deck.check_bounds(prs, ["표지 제목"])
    msg = str(ei.value)
    assert "1번 슬라이드" in msg
    assert "'표지 제목'" in msg
    assert "right=" in msg


# --- 8 fit_font_size 단위 테스트 ---------------------------------------------------

def _sk_expected(texts, w, h, mx, mn, check_word=True):
    """SKILL 조건 1·2 수식을 테스트 안에서 다시 계산한 기대값."""
    size = mx
    while size >= mn:
        lines = sum(max(1, math.ceil(text_width_pt(visible_text(t), size) / (w * 72)))
                    for t in texts)
        ok = lines * size * 1.25 <= h * 72
        if ok and check_word:
            ok = max(widest_word_pt(t, size) for t in texts) <= w * 72 * 0.97
        if ok:
            return size
        size -= 0.5
    return mn


def test_fit_short_text_gets_max():
    assert fit_font_size(["짧은 글"], 4.0, 1.0, 18, 12) == 18


def test_fit_follows_line_count_formula():
    text = "가나 다라 마바 사자"
    got = fit_font_size([text], 1.0, 0.62, 18, 12)
    assert got == _sk_expected([text], 1.0, 0.62, 18, 12)
    assert got < 18  # 줄 수(조건 1) 때문에 내려갔다


def test_fit_long_code_word_hit_by_word_check():
    text = "설정 파일은 `parse_config_file,` 이름으로 저장됩니다"
    got = fit_font_size([text], 2.5, 3.0, 18, 12)
    cond1_only = _sk_expected([text], 2.5, 3.0, 18, 12, check_word=False)
    assert got == _sk_expected([text], 2.5, 3.0, 18, 12)
    assert got < cond1_only  # 조건 2(낱말 폭)가 더 작은 크기를 강제한다


def test_fit_falls_back_to_min():
    assert fit_font_size(["아주 긴 본문이 좁은 상자에 들어가는 경우"],
                         0.4, 0.2, 18, 12) == 12


# --- 9 서체 지정 ------------------------------------------------------------------

def _run_fonts(run):
    rPr = run._r.find(qn("a:rPr"))
    latin = run.font.name
    ea = None
    if rPr is not None:
        el = rPr.find(qn("a:ea"))
        ea = el.get("typeface") if el is not None else None
    return latin, ea


def test_font_override_applies_to_all_runs(tmp_path, assets):
    md = assets / "font.md"
    md.write_text(MD, encoding="utf-8")
    out = tmp_path / "font.pptx"
    proc = uv(BUILD, md, "-o", out, "--font", "Apple SD Gothic Neo")
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    seen_code = False
    for slide in prs.slides:
        frames = [sh.text_frame for sh in slide.shapes if sh.has_text_frame]
        frames.extend(cell.text_frame for sh in slide.shapes
                      if getattr(sh, "has_table", False) and sh.has_table
                      for row in sh.table.rows for cell in row.cells)
        if slide.has_notes_slide:
            frames.append(slide.notes_slide.notes_text_frame)
        for tf in frames:
            for p in tf.paragraphs:
                for run in p.runs:
                    latin, ea = _run_fonts(run)
                    assert ea == "Apple SD Gothic Neo", (latin, ea)
                    if latin == "Consolas":  # 코드 span(기본 --mono)
                        seen_code = True
                    else:
                        assert latin == "Apple SD Gothic Neo", (latin, ea)
    assert seen_code  # 코드 span은 mono로, 한글은 기본 서체로 찍힌다


# --- 10 알 수 없는 layout ---------------------------------------------------------

def test_unknown_layout_error(tmp_path, assets):
    md = assets / "layout.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 섹션\n\n### 이상한 배치\n"
        "<!-- visual: {\"layout\": \"grid\"} -->\n- 항목 하나\n", encoding="utf-8")
    out = assets / "layout.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 1
    assert "이상한 배치" in proc.stderr
    assert "grid" in proc.stderr
    assert not out.exists()


# --- 11 그림 배치(비율 경계 2.6) --------------------------------------------------

def test_wide_image_is_above_text(built):
    slide = find_slide(built["prs"], "처리 흐름")
    img = [sh for sh in slide.shapes if sh.name == "image"][0]
    text_top = min(sh.top for sh in slide.shapes if sh.name == "bullet-body")
    assert img.top < text_top


def test_narrow_image_is_left_of_text(built):
    slide = find_slide(built["prs"], "화면 구성")
    img = [sh for sh in slide.shapes if sh.name == "image"][0]
    text_left = min(sh.left for sh in slide.shapes if sh.name == "bullet-body")
    assert img.left + img.width <= text_left + 0.01 * EMU


# --- 부가 검증: 문서 주석(hero·strip), 자산, config, dump --------------------------

def test_doc_comment_hero_and_strip(built):
    cover = built["prs"].slides[0]
    assert any(sh.name == "image" for sh in cover.shapes)      # hero 일러스트
    assert any(sh.name == "subtitle" for sh in cover.shapes)   # 표지 부제
    spotlight = find_slide(built["prs"], "어디까지 왔나")
    assert len(shapes_by_role(spotlight, "pill")) == 4         # strip 단계 4개


def test_missing_png_error_mentions_render_script(tmp_path, assets):
    (assets / "icons" / "doc.png").unlink()
    md = assets / "training.md"
    md.write_text(MD, encoding="utf-8")
    out = assets / "deck.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 1
    assert "doc.png" in proc.stderr
    assert "render_svgs.sh" in proc.stderr
    assert not out.exists()


def test_config_unknown_key_rejected(tmp_path, assets):
    cfg = assets / "deck.yaml"
    cfg.write_text("bogus: 1\n", encoding="utf-8")
    md = assets / "training.md"
    md.write_text(MD, encoding="utf-8")
    proc = uv(BUILD, md, "-o", tmp_path / "deck.pptx", "--config", cfg)
    assert proc.returncode == 1
    assert "bogus" in proc.stderr


def test_config_png_remap_colors_badge_colors(tmp_path, assets):
    (assets / "diagrams" / "flow-wide.png").rename(
        assets / "diagrams" / "remapped.png")
    cfg = assets / "deck.yaml"
    cfg.write_text(
        "png_remap:\n"
        "  flow-wide.svg: remapped.png\n"
        "colors:\n"
        "  secondary: '1B5E20'\n"
        "badge_colors:\n"
        "  승인: emphasis\n",
        encoding="utf-8")
    md = assets / "training.md"
    md.write_text(MD, encoding="utf-8")
    out = assets / "deck.pptx"
    proc = uv(BUILD, md, "-o", out, "--config", cfg)
    assert proc.returncode == 0, proc.stderr  # remapped.png를 찾았다
    prs = Presentation(out)
    slide = find_slide(prs, "문서 종류")
    table = next(sh for sh in slide.shapes if sh.name == "table").table
    fills = {table.cell(r, 0).text: str(table.cell(r, 2).fill.fore_color.rgb)
             for r in range(1, 4)}
    assert fills["보고서"] == "1B5E20"   # colors.secondary 덮어쓰기(기본 배지색)
    assert fills["기획서"] == "1B5E20"
    assert fills["회의록"] == "F2B53A"   # badge_colors의 테마 색 이름(emphasis)


def test_spotlight_without_strip_errors(tmp_path, assets):
    md = assets / "spot.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 섹션\n\n### 현재 위치\n"
        "<!-- visual: {\"layout\": \"spotlight\", \"active\": 1} -->\n- 내용\n",
        encoding="utf-8")
    proc = uv(BUILD, md, "-o", tmp_path / "spot.pptx")
    assert proc.returncode == 1
    assert "현재 위치" in proc.stderr
    assert "strip" in proc.stderr


def test_implicit_slide_no_hero_and_divider_false(tmp_path):
    md = tmp_path / "mini.md"
    md.write_text(
        "# 묶음 교육 자료\n\n"
        "## 1. 첫 묶음\n\n"
        "이 섹션은 '###' 없이 본문이 바로 온다\n\n"
        "## 2. 여러 장 묶음\n"
        "<!-- visual: {\"divider\": false} -->\n\n"
        "### 하나\n- 첫째\n\n### 둘\n- 둘째\n", encoding="utf-8")
    out = tmp_path / "mini.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    # 표지 + 목차 + 구분 0(암묵 1장 섹션, divider:false) + 내용 3.
    assert len(prs.slides) == 1 + 1 + 0 + 3
    assert not any(sh.name == "image" for sh in prs.slides[0].shapes)  # hero 없음
    assert "첫 묶음" in all_text(prs)  # 암묵 슬라이드 제목 = 섹션 제목


def test_dump_prints_shape_geometry(tmp_path, assets):
    md = assets / "training.md"
    md.write_text(MD, encoding="utf-8")
    out = assets / "deck.pptx"
    proc = uv(BUILD, md, "-o", out, "--dump")
    assert proc.returncode == 0, proc.stderr
    assert "slide 1:" in proc.stdout
    assert "title" in proc.stdout
    assert "left=" in proc.stdout and "first=" in proc.stdout


# --- 12 여러 줄 visual 주석 --------------------------------------------------------

def test_multiline_visual_comment_parsed(tmp_path, assets):
    md = assets / "multi.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 기능\n\n### 여러 줄 주석 카드\n"
        "<!-- visual: {\n  \"layout\": \"cards\",\n  \"cols\": 2,\n"
        "  \"icons\": [\"doc\", \"search\"],\n  \"highlight\": [0]\n} -->\n"
        "- **하나**: 첫 기능\n- **둘**: 둘째 기능\n", encoding="utf-8")
    out = assets / "multi.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    slide = find_slide(prs, "여러 줄 주석 카드")
    assert len(shapes_by_role(slide, "card-head")) == 2   # 주석이 슬라이드에 반영됨
    assert len(shapes_by_role(slide, "card-body")) == 2
    assert '"layout"' not in all_text(prs)  # 주석 둘째 줄이 본문이 되지 않음


def test_unclosed_visual_comment_errors(tmp_path, assets):
    md = assets / "unclosed.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 섹션\n\n### 미완성 주석\n"
        "<!-- visual: {\"layout\": \"cards\"\n- 항목 하나\n", encoding="utf-8")
    out = assets / "unclosed.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 1
    assert "미완성 주석" in proc.stderr
    assert "닫히지" in proc.stderr
    assert not out.exists()


# --- 13 코드 펜스 -----------------------------------------------------------------

def test_code_fence_content_not_parsed(tmp_path, assets):
    md = assets / "fence.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 절차\n\n### 코드가 섞인 슬라이드\n"
        "- 첫 글머리\n"
        "```\n"
        "## 펜스 안 가짜 섹션\n"
        "### 펜스 안 가짜 슬라이드\n"
        "- 펜스 안 글머리\n"
        "```\n"
        "- 펜스 뒤 글머리\n"
        "~~~\n- 물결 펜스 안 글머리\n~~~\n", encoding="utf-8")
    out = assets / "fence.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    text = all_text(prs)
    assert "가짜" not in text                    # 펜스 안 '##'·'###'은 구조가 아니다
    assert "펜스 안" not in text                 # 펜스 몸통은 슬라이드 본문에 없다
    slide = find_slide(prs, "코드가 섞인 슬라이드")
    bullets = "\n".join(sh.text_frame.text for sh in slide.shapes
                        if sh.name == "bullet-body")
    assert "첫 글머리" in bullets and "펜스 뒤 글머리" in bullets  # 닫는 펜스 뒤는 남는다
    assert len(prs.slides) == 1 + 1 + 1          # 표지 + 목차 + 내용 1(섹션도 1개)


# --- 14 본문 줄 skip 표시와 문서·섹션 수준 주석 오류 ---------------------------------

def test_body_line_skip_marker_excludes_section(tmp_path, assets):
    md = assets / "skipbody.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 남는 섹션\n\n### 내용\n- 남는 글머리\n\n"
        "## 2. 빠지는 섹션\n\n### 내용\n- 이 섹션은 덱에 넣지 않음\n\n"
        "## 3. 또 남는 섹션\n\n### 내용\n- 또 남는 글머리\n", encoding="utf-8")
    out = assets / "skipbody.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    text = all_text(prs)
    assert "빠지는 섹션" not in text            # 본문 줄 표시 하나로 섹션 전체 제외
    assert "남는 섹션" in text and "또 남는 섹션" in text
    agenda = prs.slides[1]
    agenda_text = "\n".join(sh.text_frame.text for sh in agenda.shapes
                            if sh.has_text_frame)
    assert "빠지는" not in agenda_text           # 목차 카드에서도 빠진다


@pytest.mark.parametrize("name, expect_title", [
    # 문서 수준 오류는 문서 제목을, 섹션 수준 오류는 섹션 제목을 담는다.
    ("doc", "자료 제목"),
    ("section", "첫 섹션"),
])
def test_visual_json_error_has_title(tmp_path, assets, name, expect_title):
    if name == "doc":
        body = "# 자료 제목\n\n<!-- visual: [1] -->\n\n## 1. 섹션\n\n### 내용\n- 항목\n"
    else:
        body = "# 자료 제목\n\n## 1. 첫 섹션\n<!-- visual: 123 -->\n\n### 내용\n- 항목\n"
    md = assets / f"bad-{name}.md"
    md.write_text(body, encoding="utf-8")
    proc = uv(BUILD, md, "-o", assets / f"bad-{name}.pptx")
    assert proc.returncode == 1
    assert expect_title in proc.stderr
    assert "visual 주석 JSON 오류" in proc.stderr


# --- 15 글자 폭·알약 폭 상수(손계산) -------------------------------------------------

def test_char_width_constants():
    assert text_width_pt("가나다라마바사아자차", 10) == 100.0  # 전각 10자 × 1.0em
    assert text_width_pt("abcdefghij", 10) == pytest.approx(55.0)  # 그 밖 10자 × 0.55em
    assert widest_word_pt("abcdefghij", 10) == pytest.approx(56.0)  # 낱말 검사만 0.56em


def test_pill_width_hand_computed():
    # "ab가" @17pt: (2×17×0.55 + 17) = 35.7pt → ×1.1 = 39.27pt → /72 = 0.5454166…in
    # → + 0.15in 여유 = 0.6954166…in
    assert pill_width_in("ab가", 17) == pytest.approx(0.6954166667, abs=1e-9)


# --- 16 그림 배치 비율 경계(2.6) ----------------------------------------------------

def test_image_ratio_boundary(tmp_path, assets):
    write_png(assets / "diagrams" / "edge-exact.png", 520, 200)   # 520/200 = 2.6 정확히
    write_png(assets / "diagrams" / "edge-under.png", 518, 200)   # 518/200 = 2.59
    md = assets / "edge.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 그림\n\n### 비율 경계 넓음\n"
        "<!-- visual: {\"layout\": \"image\"} -->\n![넓게](diagrams/edge-exact.svg)\n"
        "- 그림 아래로 오는 글머리\n\n### 비율 경계 좁음\n"
        "<!-- visual: {\"layout\": \"image\"} -->\n![조금 좁게](diagrams/edge-under.svg)\n"
        "- 그림 오른쪽으로 오는 글머리\n", encoding="utf-8")
    out = assets / "edge.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    wide = find_slide(prs, "비율 경계 넓음")
    wide_img = [sh for sh in wide.shapes if sh.name == "image"][0]
    wide_text_top = min(sh.top for sh in wide.shapes if sh.name == "bullet-body")
    assert wide_img.top < wide_text_top        # 2.6은 이상 → 위 그림·아래 글
    two = find_slide(prs, "비율 경계 좁음")
    two_img = [sh for sh in two.shapes if sh.name == "image"][0]
    two_text_l = min(sh.left for sh in two.shapes if sh.name == "bullet-body")
    assert two_img.left + two_img.width <= two_text_l + 0.01 * EMU  # 2.59 미만 → 두 단


# --- 17 steps: 단계마다 자기 상자로 맞춤(줄 수 합산 회귀 방지) ------------------------

def test_steps_fit_per_column_not_summed(tmp_path, assets):
    # 각 단계는 혼자 24pt에 들어간다(3줄 이내). 합산 버그라면 5단계 15줄이라 최소 15pt.
    md = assets / "steps.md"
    md.write_text(
        "# 교육 자료\n\n## 1. 절차\n\n### 다섯 단계 절차\n"
        "<!-- visual: {\"layout\": \"steps\"} -->\n"
        "- 주제와 독자를 먼저 정합니다\n"
        "- 표준 서식을 골라 초안을 씁니다\n"
        "- 동료 검토를 받아 고칩니다\n"
        "- 최종본을 공유 드라이브에 올립니다\n"
        "- 다음 주 계획을 함께 적어 둡니다\n", encoding="utf-8")
    out = assets / "steps.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    slide = find_slide(prs, "다섯 단계 절차")
    sizes = role_sizes(slide, "step-text")
    assert len(sizes) == 1
    assert sizes == {24.0}                     # 단계 각각이면 상한 24pt 그대로


# --- 18 목차 극단: 섹션 0개·10개 ---------------------------------------------------

def test_agenda_zero_sections_ends_after_cover(tmp_path):
    md = tmp_path / "none.md"
    md.write_text(
        "# 묶음 교육 자료\n\n> 대상: 전 직원\n\n"
        "## 부록. 관리자 안내 (덱에 넣지 않음)\n\n### 계정 관리\n- 관리자 화면\n",
        encoding="utf-8")
    out = tmp_path / "none.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    assert len(prs.slides) == 1                # 섹션 0개 → 목차 없이 표지로 끝난다


def test_agenda_ten_sections_all_shapes_positive(tmp_path, assets):
    parts = ["# 묶음 교육 자료\n\n"]
    for i in range(1, 11):
        parts.append(f"## {i}. 섹션이름{i}\n\n### {i}번 내용\n- 항목 하나\n\n")
    md = assets / "ten.md"
    md.write_text("".join(parts), encoding="utf-8")
    out = assets / "ten.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    for i, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            assert sh.width > 0 and sh.height > 0, (i, sh.name)


# --- 19 check_bounds: 크기 0 이하 + 실제 호출 ---------------------------------------

def test_check_bounds_catches_nonpositive_shape():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(2.0), Inches(0))
    with pytest.raises(ValueError) as ei:
        build_deck.check_bounds(prs, ["제목 슬라이드"])
    msg = str(ei.value)
    assert "제목 슬라이드" in msg
    assert "0 이하" in msg


def test_build_deck_calls_check_bounds(monkeypatch, assets):
    calls: list[int] = []
    monkeypatch.setattr(build_deck, "check_bounds",
                        lambda prs, titles: calls.append(len(titles)))
    doc = parse_doc(MD, DeckConfig())
    ctx = DeckContext(assets=DeckAssets(assets), theme=Theme(),
                      strip=doc.visual.get("strip"))
    prs = build_deck.build_deck(doc, ctx)
    assert calls == [len(prs.slides._sldIdLst)]  # 저장 전에 딱 한 번, 슬라이드 수만큼


# --- 20 목차 카드 이름 크기 통일(긴 섹션 이름 하나) ----------------------------------

def test_agenda_card_body_sizes_unified(tmp_path, assets):
    long_name = " ".join(["긴 이름"] * 40)
    md = assets / "longsec.md"
    md.write_text(
        "# 교육 자료\n\n"
        "## 1. 짧은 이름\n\n### 내용\n- 항목\n\n"
        f"## 2. {long_name}\n\n### 내용\n- 항목\n\n"
        "## 3. 또 짧은 이름\n\n### 내용\n- 항목\n", encoding="utf-8")
    out = assets / "longsec.pptx"
    proc = uv(BUILD, md, "-o", out)
    assert proc.returncode == 0, proc.stderr
    prs = Presentation(out)
    sizes = role_sizes(prs.slides[1], "card-body")
    assert len(sizes) == 1                     # 모든 카드가 같은 크기
    assert next(iter(sizes)) < 18.0            # 긴 이름이 끌어내린 최솟값(짧은 이름만은 18)


# --- 21 render_svgs.sh ---------------------------------------------------------------

def _fake_chrome(tmp_path: Path) -> Path:
    """--screenshot=경로 인자를 받아 그 자리에 작은 PNG를 쓰는 가짜 크롬."""
    script = tmp_path / "fake-chrome.sh"
    script.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do case "$a" in --screenshot=*) out="${a#--screenshot=}";; esac; done\n'
        'printf \'\\211PNG\\r\\n\\032\\n\' > "${out:?screenshot 인자가 없습니다}"\n',
        encoding="utf-8")
    script.chmod(0o755)
    return script


def _run_render(assets_dir: Path, chrome: Path, *args: str):
    return subprocess.run(["/bin/bash", str(RENDER_SVGS), str(assets_dir), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "CHROME": str(chrome)})


def test_render_svgs_no_diagrams_succeeds(tmp_path):
    empty = tmp_path / "assets"
    empty.mkdir()
    proc = _run_render(empty, _fake_chrome(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "렌더 완료" in proc.stdout


def test_render_svgs_usage_error(tmp_path):
    proc = subprocess.run(["/bin/bash", str(RENDER_SVGS)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert "사용법" in proc.stderr


def test_render_svgs_renders_icon_with_fake_chrome(tmp_path):
    assets = tmp_path / "assets"
    (assets / "icons").mkdir(parents=True)
    (assets / "icons" / "a.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"></svg>',
        encoding="utf-8")
    proc = _run_render(assets, _fake_chrome(tmp_path))
    assert proc.returncode == 0, proc.stderr
    png = assets / "icons" / "a.png"
    assert png.is_file() and png.read_bytes().startswith(b"\x89PNG")
    assert "렌더 완료" in proc.stdout
