# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-docx",
# ]
# ///
"""기본 docx 테마(default.docx)를 pandoc 기본 reference.docx에서 만듭니다.

계약: docs/design.md §9.5, docs/briefs/brief_newdoc.md N3.

    build_default.py [--out <경로>]      (기본: 이 파일 옆 default.docx)

pandoc 스타일 이름은 그대로 두고 한국어 글꼴(맑은 고딕)·A4·여백 20 mm만 바꿉니다.
테마 글꼴 속성(asciiTheme 등)은 지웁니다 — 남겨 두면 명시한 글꼴 이름보다 앞섭니다.
결과는 default.tokens.yaml과 같아야 합니다(tests/test_theme_default.py가 재추출로 검사).

종료 코드: 0 성공, 2 사용법 오류·pandoc 없음·--out이 이미 있음.
"""
import argparse
import io
import shutil
import subprocess
import sys
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips

FONT = "맑은 고딕"
BODY_PT = 10.5
HEADINGS = {"Heading 1": 16, "Heading 2": 13, "Heading 3": 11}
THEME_ATTRS = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")
A4_TWIPS = (11906, 16838)
MARGIN_TWIPS = 1134  # 20 mm
EDGE_TWIPS = 709  # 머리말·꼬리말 거리 12.5 mm


class UsageError(Exception):
    """사용자에게 보여 줄 오류(종료 코드 2)."""


def pandoc_reference() -> bytes:
    pandoc = shutil.which("pandoc") or shutil.which("pandoc", path="/opt/homebrew/bin")
    if pandoc is None:
        raise UsageError("pandoc을 찾을 수 없습니다")
    proc = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"],
                          capture_output=True, timeout=120)
    if proc.returncode != 0 or not proc.stdout:
        raise UsageError("pandoc 기본 reference.docx를 꺼내지 못했습니다")
    return proc.stdout


def child(parent, tag: str):
    """parent 아래 tag 요소를 찾고, 없으면 만들어 붙인다."""
    node = parent.find(qn(tag))
    if node is None:
        node = OxmlElement(tag)
        parent.append(node)
    return node


def set_fonts(rpr) -> None:
    fonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        fonts.set(qn(attr), FONT)


def strip_theme_fonts(styles_element) -> None:
    for fonts in styles_element.iter(qn("w:rFonts")):
        for attr in THEME_ATTRS:
            fonts.attrib.pop(qn(attr), None)


def set_doc_defaults(styles_element) -> None:
    defaults = child(styles_element, "w:docDefaults")
    rpr = child(child(defaults, "w:rPrDefault"), "w:rPr")
    set_fonts(rpr)
    child(rpr, "w:sz").set(qn("w:val"), str(int(BODY_PT * 2)))
    child(rpr, "w:szCs").set(qn("w:val"), str(int(BODY_PT * 2)))
    child(rpr, "w:lang").set(qn("w:eastAsia"), "ko-KR")


def set_style(document, name: str, pt: float, bold: bool | None) -> None:
    style = document.styles[name]
    style.font.size = Pt(pt)
    if bold is not None:
        style.font.bold = bold
    set_fonts(style.element.get_or_add_rPr())


def set_page(document) -> None:
    for section in document.sections:
        section.page_width, section.page_height = (Twips(v) for v in A4_TWIPS)
        for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
            setattr(section, side, Twips(MARGIN_TWIPS))
        section.header_distance = section.footer_distance = Twips(EDGE_TWIPS)
        section.gutter = Twips(0)


def build(data: bytes):
    document = docx.Document(io.BytesIO(data))
    styles_element = document.styles.element
    strip_theme_fonts(styles_element)
    set_doc_defaults(styles_element)
    set_style(document, "Normal", BODY_PT, None)
    set_style(document, "Body Text", BODY_PT, None)
    for name, pt in HEADINGS.items():
        set_style(document, name, pt, True)
    set_page(document)
    return document


def save_new(document, out: Path) -> None:
    buffer = io.BytesIO()
    document.save(buffer)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "xb") as handle:
        handle.write(buffer.getvalue())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build_default.py", description="기본 docx 테마 만들기")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "default.docx",
                        help="만들 파일(기본: 이 파일 옆 default.docx). 이미 있으면 거부합니다.")
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise UsageError(f"이미 있는 파일은 덮어쓰지 않습니다: {args.out}")
        save_new(build(pandoc_reference()), args.out)
    except UsageError as err:
        print(f"오류: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
