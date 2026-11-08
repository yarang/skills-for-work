"""doc-verify 리더·로케이터 회귀 테스트 (codex·antigravity 리뷰 지적).

리더(_readers)와 로케이터(_locate)는 프로파일 추출과 같은 대상을 같은 규칙으로 읽어야
검사가 견본과 결과를 같은 잣대로 비교합니다. 여기서는 모듈을 직접 불러 확인합니다.
"""
import copy
import dataclasses
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from conftest import PATCH_PPTX, PROFILE_EXTRACT, ROOT, uv

sys.path.insert(0, str(ROOT / "skills/doc-verify/scripts"))
sys.dont_write_bytecode = True

import _locate  # noqa: E402
import _readers  # noqa: E402
from _readers import HP, Para, Table, nows  # noqa: E402


# --- MD ----------------------------------------------------------------------------

MD = """---
title: 앞머리 제목
---
# 개요

## `코드` 제목

구분 | 내용
--- | ---
가 | 나

```
# 코드 안 제목은 제목이 아님
```
"""


def test_md_front_matter_fence_and_inline(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(MD, encoding="utf-8")
    doc = _readers.read_doc(p)
    assert "title: 앞머리 제목" in doc.extra
    assert "# 코드 안 제목은 제목이 아님" in doc.extra
    assert [k for k, _ in _locate.anchor_items(doc)] == ["개요", "코드제목"]
    tables = [b for b in doc.blocks if isinstance(b, Table)]
    assert [t.rows for t in tables] == [[["구분", "내용"], ["가", "나"]]]


def test_md_delimiter_column_count_must_match(tmp_path):
    p = tmp_path / "b.md"
    p.write_text("a | b | c\n--- | ---\n", encoding="utf-8")
    assert not [b for b in _readers.read_doc(p).blocks if isinstance(b, Table)]


# --- PPTX --------------------------------------------------------------------------

def test_pptx_theme_font_reference_resolved(tmp_path):
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    run = slide.shapes.title.text_frame.paragraphs[0].add_run()
    run.text = "제목"
    run.font.name = "+mn-lt"
    rpr = run._r.get_or_add_rPr()
    ea = rpr.makeelement(f"{_readers.A_NS}ea", {"typeface": "+mn-ea"})
    rpr.append(ea)
    path = tmp_path / "theme.pptx"
    prs.save(path)
    doc = _readers.read_doc(path)
    runs = [r for p in _readers.all_paras(doc) for r in p.runs if r.text == "제목"]
    # 기본 테마의 minor latin은 Calibri, minor ea는 비어 있어 비교에서 빠집니다.
    assert [r.fonts for r in runs] == [("Calibri",)]


def test_slide_anchor_survives_title_change(samples, tmp_path):
    from pptx import Presentation

    out = tmp_path / "changed.pptx"
    prs = Presentation(samples["pptx"])
    prs.slides[1].shapes.title.text_frame.text = "바뀐 제목"
    prs.save(out)
    src, doc = _readers.read_doc(samples["pptx"]), _readers.read_doc(out)
    starts = _locate.section_starts(doc, src, [{"id": "s1", "anchor": "sl:2"}])
    assert starts[0] is not None
    assert doc.blocks[starts[0]].slide == 2


def _dup_slide2(samples, tmp_path):
    edits = tmp_path / "dup.yaml"
    edits.write_text('- {op: slide_dup, like: "sl:2", after: "sl:2"}\n', encoding="utf-8")
    out = tmp_path / "dup.pptx"
    prof = tmp_path / "profile.yaml"
    prof.write_text("profile_version: 1\ndesign: {styles_allowed: [Title Slide, Title and Content, Title Only]}\n",
                    encoding="utf-8")
    proc = uv(PATCH_PPTX, "apply", samples["pptx"], "--edits", edits, "--profile", prof, "--out", out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return _readers.read_doc(samples["pptx"]), _readers.read_doc(out)


def test_slide_anchor_follows_slide_identity_after_dup(samples, tmp_path):
    """종단 시험 F8: sl:2 뒤에 장을 복제하면 견본 sl:3(실적)은 결과 4번째 장입니다."""
    src, doc = _dup_slide2(samples, tmp_path)
    assert len(doc.slide_ids) == len(src.slide_ids) + 1
    assert [_locate.slide_anchor(doc, src, f"sl:{n}") for n in (1, 2, 3)] == [1, 2, 4]
    assert _locate.slide_anchor(doc, src, "t:1") is None


def test_slide_anchor_missing_slide_is_zero(samples, tmp_path):
    src, doc = _dup_slide2(samples, tmp_path)
    gone = dataclasses.replace(doc, slide_ids=tuple(i for i in doc.slide_ids if i != src.slide_ids[2]))
    assert _locate.slide_anchor(gone, src, "sl:3") == 0


def test_slide_anchor_falls_back_to_position_when_ids_renumbered(samples, tmp_path):
    """다른 프로그램이 다시 저장해 id가 하나도 겹치지 않으면 자리 N으로 찾습니다."""
    src, doc = _dup_slide2(samples, tmp_path)
    renumbered = dataclasses.replace(doc, slide_ids=tuple(i + 1000 for i in doc.slide_ids))
    assert _locate.slide_anchor(renumbered, src, "sl:3") == 3


def _four_slide_deck(path: Path) -> None:
    """s1=1장, s2=2·3장, s3=4장인 견본 (리뷰 3차 M3)."""
    from pptx import Presentation

    prs = Presentation()
    for title in ("표지", "추진 일정", "추진 일정 (계속)", "실적"):
        prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = title
    prs.save(path)


def _drop_slide(src: Path, dst: Path, n: int) -> None:
    from pptx import Presentation

    prs = Presentation(src)
    ids = prs.slides._sldIdLst
    sld = ids[n - 1]
    prs.part.drop_rel(sld.rId)
    ids.remove(sld)
    prs.save(dst)


DECK_SECTIONS = [{"id": "s1", "anchor": "sl:1"}, {"id": "s2", "anchor": "sl:2"}, {"id": "s3", "anchor": "sl:4"}]


def test_slide_anchor_deleted_first_slide_falls_to_next_slide_of_section(tmp_path):
    """s2 첫 장(sl:2)을 지워도 s2의 남은 장(견본 sl:3)이 s2 시작입니다 — s1에 빨려 들어가면
    scope가 「s1 변경」으로 거짓 실패합니다."""
    src_path, out_path = tmp_path / "src.pptx", tmp_path / "out.pptx"
    _four_slide_deck(src_path)
    _drop_slide(src_path, out_path, 2)
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    ranges = _locate.section_ranges(doc, src, DECK_SECTIONS)["ranges"]
    s1, s2 = ranges["s1"], ranges["s2"]
    assert s1 and s2, ranges
    assert {doc.blocks[i].slide for i in range(*s1)} == {1}
    assert doc.blocks[s2[0]].slide == 2


def test_slide_anchor_whole_section_deleted_is_zero(tmp_path):
    src_path, mid, out_path = tmp_path / "src.pptx", tmp_path / "mid.pptx", tmp_path / "out.pptx"
    _four_slide_deck(src_path)
    _drop_slide(src_path, mid, 3)
    _drop_slide(mid, out_path, 2)
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    assert _locate.section_starts(doc, src, DECK_SECTIONS)[1] is None


def _deck(path: Path, titles: list) -> None:
    """titles 차례로 제목 슬라이드를 만듭니다. None은 글 없는 빈 슬라이드(그림만 둔 장과 같음)."""
    from pptx import Presentation

    prs = Presentation()
    for title in titles:
        if title is None:
            prs.slides.add_slide(prs.slide_layouts[6])
        else:
            prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = title
    prs.save(path)


def _move_slide(src: Path, dst: Path, n: int, to: int) -> None:
    from pptx import Presentation

    prs = Presentation(src)
    ids = prs.slides._sldIdLst
    sld = ids[n - 1]
    ids.remove(sld)
    ids.insert(to - 1, sld)
    prs.save(dst)


def test_slide_fallback_stops_at_next_heading_section(tmp_path):
    """다음 섹션이 h: anchor여도 그 장을 앞 섹션 대체 시작으로 쓰지 않습니다 — 보호 섹션 s2(2장)를
    지웠는데 같은 제목인 s3의 3장이 s2로 잡히면 scope가 통과합니다 (리뷰 3차 M3 재검토)."""
    src_path, out_path = tmp_path / "src.pptx", tmp_path / "out.pptx"
    _deck(src_path, ["표지", "같은 제목", "같은 제목", "실적"])
    _drop_slide(src_path, out_path, 2)
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    sections = [{"id": "s1", "anchor": "sl:1"}, {"id": "s2", "anchor": "sl:2"},
                {"id": "s3", "anchor": 'h:"같은 제목"#2'}, {"id": "s4", "anchor": "sl:4"}]
    assert _locate._section_last_slides(doc, src, sections) == [1, 2, None, 4]
    assert _locate.section_starts(doc, src, sections)[1] is None


def test_slide_fallback_uses_earliest_surviving_slide_in_output(tmp_path):
    """s2 첫 장을 지우고 남은 장 순서를 바꾸면 결과에서 앞선 장이 s2 시작입니다 — 견본 순서로 고르면
    그 앞 장이 s1에 들어가 「s1 변경」 거짓 실패가 납니다."""
    src_path, mid, out_path = tmp_path / "src.pptx", tmp_path / "mid.pptx", tmp_path / "out.pptx"
    _deck(src_path, ["A", "B", "C", "D", "E"])
    _drop_slide(src_path, mid, 2)            # A C D E
    _move_slide(mid, out_path, 3, 2)         # A D C E
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    sections = [{"id": "s1", "anchor": "sl:1"}, {"id": "s2", "anchor": "sl:2"}, {"id": "s3", "anchor": "sl:5"}]
    ranges = _locate.section_ranges(doc, src, sections)["ranges"]
    assert {doc.blocks[i].slide for i in range(*ranges["s1"])} == {1}
    assert doc.blocks[ranges["s2"][0]].slide == 2


def test_slide_fallback_skips_slide_without_text(tmp_path):
    """s2 첫 장을 지웠고 다음 남은 장이 글 없는 장이면 그다음 남은 장이 s2 시작입니다."""
    src_path, out_path = tmp_path / "src.pptx", tmp_path / "out.pptx"
    _deck(src_path, ["A", "B", None, "C", "D"])
    _drop_slide(src_path, out_path, 2)       # A (빈 장) C D
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    assert not any(getattr(b, "slide", None) == 2 for b in doc.blocks)
    sections = [{"id": "s1", "anchor": "sl:1"}, {"id": "s2", "anchor": "sl:2"}, {"id": "s3", "anchor": "sl:5"}]
    ranges = _locate.section_ranges(doc, src, sections)["ranges"]
    assert {doc.blocks[i].slide for i in range(*ranges["s1"])} == {1}
    assert doc.blocks[ranges["s2"][0]].slide == 3


def test_slide_fallback_blocked_for_protected_section(tmp_path):
    """리뷰 3차 재검토(agy HIGH3-1): 보호 섹션 s2(편집 범위 밖)의 첫 장을 지우면 남은 장으로 대체
    시작을 잡지 않습니다 — 잡으면 s2 첫 장 삭제가 scope에서 「s2 변경」 대신 조용히 넘어갑니다.
    편집 범위를 주지 않으면(분량 등) 지금처럼 남은 장에서 시작합니다."""
    src_path, out_path = tmp_path / "src.pptx", tmp_path / "out.pptx"
    _four_slide_deck(src_path)
    _drop_slide(src_path, out_path, 2)
    src, doc = _readers.read_doc(src_path), _readers.read_doc(out_path)
    assert _locate.section_ranges(doc, src, DECK_SECTIONS, editable={"s1"})["ranges"]["s2"] is None
    assert _locate.section_ranges(doc, src, DECK_SECTIONS, editable={"s2"})["ranges"]["s2"]
    assert _locate.section_ranges(doc, src, DECK_SECTIONS)["ranges"]["s2"]


def test_slide_anchor_position_beyond_deck_is_zero(samples, tmp_path):
    """id가 다 바뀐 결과에서 자리 N이 장 수보다 크면 0(찾지 못함)입니다 — N을 그대로 돌려주면
    없는 장을 찾다가 엉뚱한 블록을 잡습니다."""
    src, doc = _dup_slide2(samples, tmp_path)
    renumbered = dataclasses.replace(doc, slide_ids=tuple(i + 1000 for i in doc.slide_ids))
    assert _locate.slide_anchor(renumbered, src, f"sl:{len(doc.slide_ids) + 1}") == 0


@pytest.mark.parametrize("anchor", ["sl:0", "sl:00"])
def test_slide_anchor_below_one_is_zero(samples, anchor):
    """sl:0이 견본 slide_ids[-1](마지막 장)로 풀리면 엉뚱한 섹션을 잡습니다."""
    src = _readers.read_doc(samples["pptx"])
    assert _locate.slide_anchor(src, src, anchor) == 0


# --- 신규 모드 느슨한 제목 맞추기 (리뷰 3차 H3) ----------------------------------------

LOOSE_MD = """# 보고서

## □ 추진 배경

본문 하나

## ○ 1. 현황

본문 둘
"""


@pytest.mark.parametrize("key", ["추진배경", "현황"])
def test_loose_heading_strips_bullet_marks(tmp_path, key):
    p = tmp_path / "loose.md"
    p.write_text(LOOSE_MD, encoding="utf-8")
    doc = _readers.read_doc(p)
    idx = _locate.find_para(doc, key, 1, 0, loose=True)
    assert idx is not None and key in nows(doc.blocks[idx].text)
    assert _locate.find_para(doc, key, 1, 0) is None  # 갱신 모드(엄격)는 그대로


def test_loose_bullet_alone_is_not_stripped():
    assert _locate.chapter_stripped("□") == "□"
    assert _locate.chapter_stripped("12개월 계획") == "12개월계획"
    assert _locate.chapter_stripped("○○사업 추진계획(안)") == "○○사업추진계획(안)"  # 붙은 ○는 글머리표 아님
    assert _locate.chapter_stripped("□ Ⅰ. 개요") == "개요"


def _hwpx_replace_text(src: Path, dst: Path, old: str, new: str) -> None:
    with zipfile.ZipFile(src) as zf:
        items = [(i, zf.read(i.filename)) for i in zf.infolist()]
    with zipfile.ZipFile(dst, "w") as zf:
        for info, data in items:
            if info.filename == "Contents/section0.xml":
                data = data.replace(old.encode(), new.encode(), 1)
            zf.writestr(info, data)


def test_hwpx_table_heading_chapter_without_period_matches_loose(samples, tmp_path):
    """띠 표 안 제목 「1 추진 배경」 — 표 안 anchor는 원래 글(공백 포함)로 장 번호를 찾아야 합니다."""
    dst = tmp_path / "band.hwpx"
    _hwpx_replace_text(samples["hwpx"], dst, "○○사업 추진계획(안)", "1 추진 배경")
    doc = _readers.read_doc(dst)
    idx = _locate.find_para(doc, "추진배경", 1, 0, loose=True)
    assert idx is not None
    assert isinstance(doc.blocks[idx], Table) and doc.blocks[idx].at == "t:1"


def test_loose_stray_match_before_previous_section_falls_forward(tmp_path):
    """요약 상자의 「현황」 한 줄이 s1 제목보다 앞에 있어도 s2는 그 뒤 「Ⅱ. 현황」에서 찾습니다.
    전에는 앞줄이 첫 번째로 세어져 None → length가 fail 대신 skip이 됐습니다."""
    from docx import Document

    path = tmp_path / "new.docx"
    d = Document()
    d.add_paragraph("보고서", style="Title")
    d.add_paragraph("현황")
    d.add_paragraph("Ⅰ. 개요", style="Heading 1")
    d.add_paragraph("본문 하나")
    d.add_paragraph("Ⅱ. 현황", style="Heading 1")
    d.add_paragraph("본문 둘")
    d.save(path)
    doc = _readers.read_doc(path)
    sections = [{"id": "s1", "anchor": 'h:"개요"'}, {"id": "s2", "anchor": 'h:"현황"'}]
    s1, s2 = _locate.section_starts(doc, doc, sections, loose=True)
    assert doc.blocks[s1].text == "Ⅰ. 개요"
    assert s2 is not None and doc.blocks[s2].text == "Ⅱ. 현황"
    strict = [{"id": "s1", "anchor": 'h:"Ⅰ. 개요"'}, {"id": "s2", "anchor": 'h:"현황"'}]
    assert _locate.section_starts(doc, doc, strict)[1] is None  # 갱신 모드는 순서 어긋남을 그대로 알림


# --- HWPX --------------------------------------------------------------------------

def test_hwpx_band_table_title_is_anchor(samples):
    doc = _readers.read_doc(samples["hwpx"])
    idx = _locate.find_para(doc, nows("○○사업 추진계획(안)"), 1, 0)
    assert idx is not None
    assert isinstance(doc.blocks[idx], Table) and doc.blocks[idx].at == "t:1"


def _inject_header_table(src: Path, dst: Path) -> None:
    """t:5를 담은 최상위 문단을 복사해 첫 문단의 머리말(hp:header/hp:subList) 안에 넣습니다."""
    from lxml import etree

    with zipfile.ZipFile(src) as zf:
        items = [(i, zf.read(i.filename)) for i in zf.infolist()]
    out = []
    for info, data in items:
        if info.filename == "Contents/section0.xml":
            root = etree.fromstring(data)
            tops = list(root.iterchildren(f"{HP}p"))
            holder = next(p for p in tops if len(list(p.iter(f"{HP}tbl"))) and
                          "운영팀" in "".join(p.itertext()))
            run = etree.SubElement(tops[0], f"{HP}run")
            sub = etree.SubElement(etree.SubElement(etree.SubElement(run, f"{HP}ctrl"),
                                                    f"{HP}header"), f"{HP}subList")
            sub.append(copy.deepcopy(holder))
            data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        out.append((info, data))
    with zipfile.ZipFile(dst, "w") as zf:
        for info, data in out:
            zf.writestr(info, data)


def test_hwpx_header_table_is_not_body(samples, tmp_path):
    dst = tmp_path / "header.hwpx"
    _inject_header_table(samples["hwpx"], dst)
    doc = _readers.read_doc(dst)
    assert [b.at for b in doc.blocks if isinstance(b, Table)] == ["t:1", "t:2", "t:3", "t:4", "t:5"]
    # 머리말 안 문단은 anchor 대상이 아니므로 "운영팀"은 본문 t:5 한 곳에서만 잡힙니다.
    assert sum(1 for k, _ in _locate.anchor_items(doc) if k == "운영팀") == 1
    proc = uv(PROFILE_EXTRACT, "tables", dst)
    assert proc.returncode == 0, proc.stderr
    assert [t["at"] for t in yaml.safe_load(proc.stdout)["tables"]] == ["t:1", "t:2", "t:3", "t:4", "t:5"]


# --- zip 폭탄 ----------------------------------------------------------------------

def test_zip_ratio_bomb_rejected(samples, tmp_path):
    bomb = tmp_path / "bomb.docx"
    shutil.copy(samples["docx"], bomb)
    with zipfile.ZipFile(bomb, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/media/zeros.bin", b"\0" * (11 << 20))
    assert "압축률" in (_readers.zip_problem(bomb) or "")
    with pytest.raises(_readers.PackageRejected):
        _readers.read_doc(bomb)


def test_zip_problem_none_for_normal_package(samples):
    assert _readers.zip_problem(samples["docx"]) is None
    assert _readers.zip_problem(samples["hwpx"]) is None


def test_para_anchor_items_default_to_top_level_paragraphs(samples):
    doc = _readers.read_doc(samples["docx"])
    items = _locate.anchor_items(doc)
    assert items and all(isinstance(doc.blocks[i], Para) for _, i in items)


# --- R1 쪽 글 대조 (종단 시험 F6) ----------------------------------------------------

def test_r1_cell_found_when_fallback_font_reorders_page_text():
    """LibreOffice가 ○를 대체 글꼴로 그리면 pymupdf 쪽 글 순서가 「○○○ 부서장 (서명)」으로 바뀝니다."""
    import _checks_design

    pages = [nows("성명 홍길동 부서장 확인 ○○○ 부서장 (서명)")]
    assert _checks_design._table_pages(pages, "성명", "부서장 ○○○ (서명)", 0)[:2] == (0, 0)


def test_r1_cell_token_fallback_needs_every_token_on_page():
    import _checks_design

    pages = [nows("성명 홍길동 부서장 확인"), nows("○○○ (서명)")]
    pf, pl, _ = _checks_design._table_pages(pages, "성명", "부서장 ○○○ (서명)", 0)
    assert (pf, pl) == (0, None)



def test_r1_plain_cell_needs_whole_text_on_page():
    """리뷰 3차 M4: 기호 없는 칸은 낱말 맞추기를 쓰지 않습니다 — 앞 쪽의 「계획 검토 후 예산 수립」이
    다음 쪽 끝 칸 「계획 수립」을 대신 찾아 쪽 나뉨을 놓치면 안 됩니다."""
    import _checks_design

    pages = [nows("구분 내용 계획 검토 후 예산 수립"), nows("계획 수립")]
    pf, pl, _ = _checks_design._table_pages(pages, "구분", "계획 수립", 0)
    assert (pf, pl) == (0, 1)


def test_r1_symbol_cell_still_uses_word_fallback():
    import _checks_design

    assert _checks_design._on_page(nows("○○○ 부서장 (서명)"), "부서장 ○○○ (서명)", loose=True)
    assert not _checks_design._on_page(nows("○○○ 부서장 (서명)"), "부서장 ○○○ (서명)")
    assert not _checks_design._on_page(nows("수립 계획"), "계획 수립", loose=True)


def test_r1_symbol_cell_without_space_uses_piece_fallback():
    """공백 없는 「※비고」도 기호를 뺀 조각으로 찾습니다 (agy 6번 후속)."""
    import _checks_design

    assert _checks_design._on_page(nows("비고 ※"), "※비고", loose=True)
    assert not _checks_design._on_page(nows("참고"), "※비고", loose=True)


def test_r1_strict_first_page_is_kept_when_last_needs_fallback():
    """글 그대로 찾은 첫 칸 쪽은 느슨한 다시 찾기로 앞쪽에 끌려가지 않습니다 (agy 6번 후속)."""
    import _checks_design

    pages = [nows("※ 참고 비고 담당 확인 ○○○"), nows("비고※ 표 첫 줄"), nows("○○○ 담당 확인")]
    pf, pl, nxt = _checks_design._table_pages(pages, "비고 ※", "담당 ○○○ 확인", 0)
    assert (pf, pl, nxt) == (1, 2, 2)

# --- R6 날짜는 번호가 아님 (종단 시험 F10) ------------------------------------------

@pytest.mark.parametrize("text, shape", [
    ("2026. 11. 12. 14:00~16:00", None),
    ("2026.11.12. 회의", None),
    ("1. 추진 배경", "1."),
    ("1.1 현황", "1.1"),
    ("12. 기타", "1."),
    # 리뷰 3차 M13: 로마 숫자·영문 괄호 번호는 번호, 법인 표기·가나다 밖 한글은 번호가 아님
    ("Ⅰ. 개요", "Ⅰ."),
    ("Ⅳ 결론", "Ⅰ."),
    ("A) 첫째", "A)"),
    ("(사) 한국협회", None),
    ("(주)회사", None),
    ("카. 열한째", "가."),
    ("힣. 글", None),
    ("(힣) 글", None),
])
def test_r6_year_is_not_marker(text, shape):
    import _checks_design

    assert _checks_design.shape_of(text.split()[0]) == shape


def test_profile_extract_marker_matches_verify_rule():
    """profile_extract와 doc-verify가 같은 줄 머리 규칙을 써야 numbering이 견본과 결과에서 맞습니다."""
    sys.path.insert(0, str(ROOT / "template/skills/template-analysis/scripts"))
    import _checks_design
    import _pe_common

    # 「1.1 현황」: 끝 점 없는 다단 번호를 추출만 놓치면 손대지 않은 결과가 R6에서 실패했습니다 (F11).
    for text in ("2026. 11. 12. 14:00", "2026.11.12. 회의", "1. 배경", "1.1 현황", "1.2. 계획", "가. 목적",
                 "(1) 세부", "3) 셋째", "(주) 회사", "(사) 협회", "카. 열한째", "힣. 글", "(가) 항목"):
        assert bool(_pe_common.line_marker(text)) == (_checks_design.shape_of(text.split()[0]) is not None), text


# --- R4 토큰 값 꼴 (리뷰 3차 M8) ------------------------------------------------------

@pytest.mark.parametrize("token", [
    {"font": None, "pt": None, "bold": None},
    {"line_spacing": 1.5},
    {"font": "  ", "pt": True, "bold": "yes"},
])
def test_r4_unusable_token_is_not_compared(token):
    """null·빈 글·bool pt 같은 토큰은 비교하지 않은 것으로 칩니다(신규 모드 skip 판정의 바탕)."""
    import _checks_design

    assert _checks_design._token_mismatch("h1", ("맑은 고딕", 16.0, True), token) == (None, False)


@pytest.mark.parametrize("name, value", [
    ("font", "확인 못 함"), ("font", "미확인"), ("font", "N/A"), ("font", "-"),
    ("pt", 0), ("pt", -3), ("pt", float("nan")), ("pt", float("inf")),
])
def test_r4_placeholder_or_nonpositive_token_is_not_usable(name, value):
    """「확인 못 함」 같은 글과 0 이하·무한 pt는 비교하지 않습니다 (SKILL.md R5, agy 6번 후속)."""
    import _checks_design

    assert not _checks_design._usable(name, value)


@pytest.mark.parametrize("value, want", [
    ("1f4e79", "#1F4E79"), (" #1F4E79 ", "#1F4E79"), ("확인 못 함", None), ("파랑", None),
    ("#12345", None), ("#1234567", None), (None, None),
])
def test_r5_color_needs_six_hex_digits(value, want):
    import _checks_design

    assert _checks_design._color(value) == want


def test_r4_token_bold_compares_as_bool():
    import _checks_design

    assert _checks_design._token_mismatch("h1", ("맑은 고딕", 16.0, None), {"bold": False}) == (None, False)
    bad, did = _checks_design._token_mismatch("h1", ("맑은 고딕", 16.0, False), {"bold": False})
    assert did and bad is None
    bad, did = _checks_design._token_mismatch("h1", ("맑은 고딕", 16.0, True), {"bold": False})
    assert did and bad


def test_r5_token_sets_skip_unusable_values():
    import _checks_design

    fonts, pts, _ = _checks_design._token_sets(
        {"type": {"a": {"font": None, "pt": True}, "b": {"font": "바탕", "pt": 11}}})
    assert fonts == {"바탕"} and pts == {11.0}


# --- markup 오탐·중복 (agy F-05) -------------------------------------------------------

def _markup(out_blocks):
    from _checks_content import Ctx, check_markup
    from _readers import Doc

    ctx = Ctx({}, "sample", None, None, Path("out.hwpx"), Doc("hwpx", [Para("견본 글")]),
              Doc("hwpx", out_blocks), None, None, None)
    return check_markup(ctx)


@pytest.mark.parametrize("text", [r"자료는 C:\_work\보고 폴더에 둔다", r"\\서버\_공유\자료",
                                  "서명 ___서명___ 날짜", "__init__ 함수를 고친다", "a__b__c"])
def test_markup_path_signature_identifier_pass(text):
    assert _markup([Para(text)])["status"] == "pass", text


def test_markup_double_underscore_bold_still_fails():
    assert _markup([Para("신청 __135건__ 접수")])["status"] == "fail"


def test_markup_multi_paragraph_cell_counted_once():
    """여러 문단 칸은 칸 글과 문단 글로 두 번 읽히지만 한 건입니다."""
    table = Table("t:1", [["**준비**\n둘째 줄"]], texts=["**준비**", "둘째 줄"])
    r = _markup([table])
    assert r["status"] == "fail" and r["detail"].startswith("1건"), r


# --- markup (agy 6번 후속) ---------------------------------------------------------------

@pytest.mark.parametrize("text", ["신청 __135건__을 받았다", "__MVP__ 범위", "할 일 __TODO__ 남음"])
def test_markup_bold_with_korean_particle_or_upper_fails(text):
    """한글 조사가 붙은 「__」 굵게와 대문자 「__MVP__」도 마크다운 잔존입니다."""
    assert _markup([Para(text)])["status"] == "fail", text


@pytest.mark.parametrize("text", [r">C:\_work\보고", r"#__init__ 고침"])
def test_markup_removed_path_does_not_make_fake_marker(text):
    """경로·식별자를 지운 자리가 공백이 되어 「> 」·「# 」 표지처럼 보이지 않습니다."""
    assert _markup([Para(text)])["status"] == "pass", text


def test_markup_table_row_after_path_still_fails():
    """Windows 경로 글자에 「|」는 없으므로 경로 뒤 표 줄 표지가 지워지지 않습니다."""
    assert _markup([Para(r"|C:\a|b|")])["status"] == "fail"


def test_markup_same_text_in_two_cells_counts_twice():
    """다른 칸에 같은 잔존이 있으면 두 곳입니다 — 칸 글·표 문단 글 겹침은 한 번만 셉니다."""
    table = Table("t:1", [["**준비**", "**준비**"]], texts=["**준비**", "**준비**"])
    r = _markup([table])
    assert r["status"] == "fail" and r["detail"].startswith("2건"), r
    assert r["locations"] == ["t:1/r:1/c:1", "t:1/r:1/c:2"], r


def test_markup_contained_text_with_new_kind_still_counts():
    """이미 센 글 안에 들어 있어도 거기서 못 센 종류(줄 머리 「> 」)가 나오면 셉니다."""
    from _checks_content import Ctx, check_markup
    from _readers import Doc

    out = Doc("hwpx", [Para("**굵게** 참고 > 인용")], extra=["> 인용"])
    ctx = Ctx({}, "sample", None, None, Path("out.hwpx"), Doc("hwpx", [Para("견본 글")]),
              out, None, None, None)
    r = check_markup(ctx)
    assert r["detail"].startswith("2건") and "인용 >" in r["detail"], r


def test_markup_multi_kind_item_counted_once():
    """한 문단에 표지가 두 종류여도 건수는 한 번이고, 그 문단의 일부인 표 문단 글도 다시 세지 않습니다."""
    table = Table("t:1", [["# 제목 **굵게**\n둘째"]], texts=["# 제목 **굵게**", "둘째"])
    r = _markup([table])
    assert r["detail"].startswith("1건"), r
    assert "제목 #" in r["detail"] and "굵게 **" in r["detail"], r
