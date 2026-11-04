"""DOCX 디자인 토큰·번호 매기기: 쪽 설정, 스타일 서체, 색, 표 머리행, 줄 머리 부호.

스타일 상속을 따라가도 값이 없으면 짐작하지 않고 비운 뒤 경고를 남깁니다.
"""
import re

from _pe_common import emu_to_mm, line_marker, paper_size, unique
from _pe_docx import grid_rows, heading_level, own_paragraphs, para_text, w

NUMBER_RE = re.compile(r"^[-+]?[\d,]+(?:\.\d+)?\s*[%건원명개회]?$")
NUM_FMT_SAMPLE = {
    "decimal": "1", "ganada": "가", "chosung": "ㄱ", "upperRoman": "Ⅰ", "lowerRoman": "i",
    "upperLetter": "A", "lowerLetter": "a", "decimalEnclosedCircle": "①",
}


def page(doc, warnings):
    secs = doc.sections
    if not secs or secs[0].page_width is None:
        warnings.append("design.page: 섹션 설정이 없어 비움")
        return {}
    s = secs[0]
    width, height = emu_to_mm(s.page_width), emu_to_mm(s.page_height)
    margins = [s.top_margin, s.bottom_margin, s.left_margin, s.right_margin]
    if len(secs) > 1:
        warnings.append("design.page: 섹션이 여럿이라 첫 섹션 설정만 적음")
    return {
        "size": paper_size(width, height),
        "orientation": "landscape" if width > height else "portrait",
        "margins_mm": [emu_to_mm(m) if m is not None else None for m in margins],
    }


def doc_defaults(doc):
    """docDefaults의 서체(테마 서체가 아닌 것)와 크기(pt)."""
    rpr = doc.styles.element.find(f"{w('docDefaults')}/{w('rPrDefault')}/{w('rPr')}")
    if rpr is None:
        return "", None
    fonts = rpr.find(w("rFonts"))
    font = ""
    if fonts is not None:
        font = fonts.get(w("eastAsia")) or fonts.get(w("ascii")) or ""
    sz = rpr.find(w("sz"))
    pt = int(sz.get(w("val"))) / 2 if sz is not None and sz.get(w("val")) else None
    return font, pt


def style_font_name(style) -> str:
    rpr = style.element.rPr
    fonts = rpr.find(w("rFonts")) if rpr is not None else None
    if fonts is not None and (fonts.get(w("eastAsia")) or fonts.get(w("ascii"))):
        return fonts.get(w("eastAsia")) or fonts.get(w("ascii"))
    return ""


def line_spacing(style):
    s = style
    while s is not None:
        value = s.paragraph_format.line_spacing
        if value is not None:
            return int(round(value * 100)) if isinstance(value, float) else f"{value.pt:g}pt"
        s = s.base_style
    return ""


def style_token(doc, style, key, warnings):
    """스타일 상속을 따라 서체·크기·굵기·줄 간격을 모음."""
    font, pt, bold, s = "", None, None, style
    while s is not None:
        font = font or style_font_name(s)
        pt = pt if pt is not None else (s.font.size.pt if s.font.size is not None else None)
        bold = bold if bold is not None else s.font.bold
        s = s.base_style
    def_font, def_pt = doc_defaults(doc)
    font, pt = font or def_font, pt if pt is not None else def_pt
    if not font:
        warnings.append(f"design.type.{key}.font: 테마 서체라 이름을 확인 못 해 비움")
    if pt is None:
        warnings.append(f"design.type.{key}.pt: 크기를 확인 못 해 비움")
    return {"font": font, "pt": float(pt) if pt is not None else "",
            "bold": bool(bold), "line_spacing": line_spacing(style)}


def used_heading_styles(doc):
    out = {}
    for para in doc.paragraphs:
        style = para.style
        level = heading_level(style.name if style is not None else "")
        if level is not None:
            out.setdefault("title" if level == 0 else f"h{level}", style)
    return out


def type_tokens(doc, warnings):
    from docx.enum.style import WD_STYLE_TYPE

    tokens = {}
    body = doc.styles.default(WD_STYLE_TYPE.PARAGRAPH)
    if body is not None:
        tokens["body"] = style_token(doc, body, "body", warnings)
    for key, style in used_heading_styles(doc).items():
        tokens[key] = style_token(doc, style, key, warnings)
    return tokens


def text_color(doc, warnings) -> str:
    from docx.enum.style import WD_STYLE_TYPE

    s = doc.styles.default(WD_STYLE_TYPE.PARAGRAPH)
    while s is not None:
        rgb = s.font.color.rgb if s.font.color is not None and s.font.color.type is not None else None
        if rgb is not None:
            return f"#{rgb}"
        s = s.base_style
    warnings.append("design.color.text: 본문 스타일에 글자색이 없어(자동) 비움")
    return ""


def header_table(doc):
    for table in doc.tables:
        if len(table._tbl.findall(w("tr"))) >= 2:
            return table._tbl
    return None


def cell_fill(tc) -> str:
    shd = tc.find(f"{w('tcPr')}/{w('shd')}")
    fill = shd.get(w("fill")) if shd is not None else None
    return f"#{fill.upper()}" if fill and fill.lower() != "auto" else ""


def row_bold(tr) -> bool:
    runs = list(tr.iter(w("r")))
    for r in runs:
        b = r.find(f"{w('rPr')}/{w('b')}")
        if b is not None and b.get(w("val")) not in ("0", "false"):
            return True
    return False


def number_alignment(tbl) -> str:
    aligns = []
    for cells in grid_rows(tbl)[1:]:
        for _, tc in cells:
            for p in own_paragraphs(tc):
                if NUMBER_RE.match(para_text(p).strip()):
                    jc = p.find(f"{w('pPr')}/{w('jc')}")
                    aligns.append(jc.get(w("val")) if jc is not None else "left")
    return aligns[0] if aligns and len(set(aligns)) == 1 else ""


def table_tokens(doc, warnings):
    tbl = header_table(doc)
    if tbl is None:
        warnings.append("design.table: 2행 이상인 표가 없어 비움")
        return {}, ""
    first = tbl.find(w("tr"))
    tcs = list(first.iterchildren(w("tc")))
    bg = cell_fill(tcs[0]) if tcs else ""
    numbers = number_alignment(tbl)
    if not numbers:
        warnings.append("design.table.numbers: 숫자 칸 정렬을 정하지 못해 비움")
    return {"header_bold": row_bold(first), "header_bg": bg, "numbers": numbers}, bg


def design(doc, warnings):
    table, header_bg = table_tokens(doc, warnings)
    if not header_bg:
        warnings.append("design.color.table_header_bg: 머리행 바탕색이 없어 비움")
    return {
        "page": page(doc, warnings),
        "type": type_tokens(doc, warnings),
        "color": {"text": text_color(doc, warnings), "table_header_bg": header_bg},
        "table": table,
        "styles_allowed": [],
    }


def lvl_marker(lvl) -> str:
    fmt_el, text_el = lvl.find(w("numFmt")), lvl.find(w("lvlText"))
    fmt = fmt_el.get(w("val")) if fmt_el is not None else ""
    text = text_el.get(w("val")) if text_el is not None else ""
    if fmt == "bullet":
        return text if text and not ("" <= text[0] <= "") else "•"
    return re.sub(r"%\d", NUM_FMT_SAMPLE.get(fmt, "1"), text) if text else ""


def style_num_pr(para):
    s = para.style
    while s is not None:
        ppr = s.element.pPr
        num_pr = ppr.find(w("numPr")) if ppr is not None else None
        if num_pr is not None:
            return num_pr
        s = s.base_style
    return None


def auto_markers(doc):
    """자동 번호(numPr)의 부호를 수준 순서로."""
    try:
        numbering_el = doc.part.numbering_part.element
    except (KeyError, NotImplementedError, AttributeError):
        return []
    found = []
    for para in doc.paragraphs:
        ppr = para._p.pPr
        num_pr = ppr.find(w("numPr")) if ppr is not None else None
        num_pr = num_pr if num_pr is not None else style_num_pr(para)
        if num_pr is None:
            continue
        num_id = num_pr.find(w("numId"))
        ilvl = num_pr.find(w("ilvl"))
        found.append((int(num_id.get(w("val"))) if num_id is not None else 0,
                      int(ilvl.get(w("val"))) if ilvl is not None else 0))
    ordered = sorted(set(found), key=lambda pair: (pair[1], pair[0]))
    return [lookup_marker(numbering_el, num_id, ilvl) for num_id, ilvl in ordered]


def lookup_marker(numbering_el, num_id: int, ilvl: int) -> str:
    abstract = numbering_el.xpath(f'./w:num[@w:numId="{int(num_id)}"]/w:abstractNumId/@w:val')
    if not abstract:
        return ""
    lvls = numbering_el.xpath(
        f'./w:abstractNum[@w:abstractNumId="{int(abstract[0])}"]/w:lvl[@w:ilvl="{int(ilvl)}"]')
    return lvl_marker(lvls[0]) if lvls else ""


def numbering(doc, warnings):
    marks = auto_markers(doc) + [line_marker(para_text(p._p)) for p in doc.paragraphs]
    marks = unique(marks)
    if not marks:
        warnings.append("structure.numbering: 번호 매기기·줄 머리 부호가 없어 비움")
    return marks
