"""doc-verify 리더·로케이터 회귀 테스트 (codex·antigravity 리뷰 지적).

리더(_readers)와 로케이터(_locate)는 프로파일 추출과 같은 대상을 같은 규칙으로 읽어야
검사가 견본과 결과를 같은 잣대로 비교합니다. 여기서는 모듈을 직접 불러 확인합니다.
"""
import copy
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from conftest import PROFILE_EXTRACT, ROOT, uv

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
