"""PPTX 디자인 토큰: 슬라이드 크기, 마스터 제목·본문 서체, 테마 색, 표 머리행."""
import re

from lxml import etree

from _pe_common import emu_to_mm
from _pe_pptx import a, pptx_cell_text, slide_tables

NUMBER_RE = re.compile(r"^[-+]?[\d,]+(?:\.\d+)?\s*[%건원명개회]?$")
ASPECTS = {"16:9": 16 / 9, "4:3": 4 / 3, "16:10": 16 / 10}
THEME_SLOTS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4",
               "accent5", "accent6", "hlink", "folHlink")


def page(prs):
    width, height = emu_to_mm(prs.slide_width), emu_to_mm(prs.slide_height)
    ratio = width / height if height else 0
    size = next((name for name, r in ASPECTS.items() if abs(ratio - r) < 0.01), "")
    return {"size": size or f"{width:g}x{height:g}mm", "width_mm": width, "height_mm": height,
            "orientation": "landscape" if width >= height else "portrait"}


def theme_root(prs):
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    try:
        part = prs.slide_masters[0].part.part_related_by(RT.THEME)
    except (KeyError, IndexError):
        return None
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    return etree.fromstring(part.blob, parser)


def theme_fonts(theme):
    """{'+mj-lt': …, '+mj-ea': …, '+mn-lt': …, '+mn-ea': …}."""
    out = {}
    if theme is None:
        return out
    for prefix, tag in (("+mj", "majorFont"), ("+mn", "minorFont")):
        for script, child in (("lt", "latin"), ("ea", "ea")):
            found = theme.findall(f".//{a(tag)}/{a(child)}")
            out[f"{prefix}-{script}"] = found[0].get("typeface", "") if found else ""
    return out


def run_props(master, style: str):
    found = master.element.xpath(f"./p:txStyles/p:{style}/a:lvl1pPr/a:defRPr")
    return found[0] if found else None


def font_of(rpr, fonts) -> str:
    for child in ("ea", "latin"):
        el = rpr.find(a(child))
        face = el.get("typeface", "") if el is not None else ""
        face = fonts.get(face, face) if face.startswith("+") else face
        if face:
            return face
    return ""


def type_token(master, style, key, fonts, warnings):
    rpr = run_props(master, style)
    if rpr is None:
        warnings.append(f"design.type.{key}: 마스터 {style}가 없어 비움")
        return {"font": "", "pt": "", "bold": False}
    font = font_of(rpr, fonts)
    size = rpr.get("sz")
    if not font:
        warnings.append(f"design.type.{key}.font: 서체 이름을 확인 못 해 비움")
    return {"font": font, "pt": int(size) / 100 if size else "",
            "bold": rpr.get("b") in ("1", "true")}


def type_tokens(prs, theme, warnings):
    if not len(prs.slide_masters):
        warnings.append("design.type: 슬라이드 마스터가 없어 비움")
        return {}
    master, fonts = prs.slide_masters[0], theme_fonts(theme)
    return {"title": type_token(master, "titleStyle", "title", fonts, warnings),
            "body": type_token(master, "bodyStyle", "body", fonts, warnings)}


def theme_colors(theme, warnings):
    scheme = theme.find(f".//{a('clrScheme')}") if theme is not None else None
    if scheme is None:
        warnings.append("design.color: 테마 색을 찾지 못해 비움")
        return {}
    out = {}
    for slot in THEME_SLOTS:
        el = scheme.find(a(slot))
        if el is None or not len(el):
            continue
        value = el[0].get("val") if el[0].tag == a("srgbClr") else el[0].get("lastClr")
        if value:
            out[slot] = f"#{value.upper()}"
    return out


def number_alignment(table) -> str:
    aligns = []
    for r in range(1, len(table.rows)):
        for c in range(len(table.columns)):
            cell = table.cell(r, c)
            if NUMBER_RE.match(pptx_cell_text(cell)):
                align = cell.text_frame.paragraphs[0].alignment
                aligns.append(str(align).split(".")[-1].split(" ")[0].lower() if align else "left")
    return aligns[0] if aligns and len(set(aligns)) == 1 else ""


def table_tokens(prs, warnings):
    shape = next((s for _, s in slide_tables(prs) if len(s.table.rows) >= 2), None)
    if shape is None:
        warnings.append("design.table: 2행 이상인 표가 없어 비움")
        return {}
    table = shape.table
    runs = [r for c in range(len(table.columns))
            for p in table.cell(0, c).text_frame.paragraphs for r in p.runs]
    bold = any(r.font.bold for r in runs)
    numbers = number_alignment(table)
    if not numbers:
        warnings.append("design.table.numbers: 숫자 칸 정렬을 정하지 못해 비움")
    return {"header_bold": bold, "header_row_style": bool(table.first_row), "numbers": numbers}


def design(prs, warnings):
    theme = theme_root(prs)
    return {
        "page": page(prs),
        "type": type_tokens(prs, theme, warnings),
        "color": theme_colors(theme, warnings),
        "table": table_tokens(prs, warnings),
        "styles_allowed": [],
    }
