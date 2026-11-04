"""PPTX XML helpers for patch_pptx.py: namespaces, shape walk, text get/set."""
from __future__ import annotations

import copy

from lxml import etree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
URI_TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"
URI_CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
URI_DIAGRAM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"

TITLE_TYPES = {"title", "ctrTitle"}
BODY_TYPES = {None, "body", "subTitle", "obj"}
NON_EDITABLE = {"chart", "smartart", "media", "other"}


def qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


SHAPE_TAGS = {qn("p:sp"), qn("p:grpSp"), qn("p:graphicFrame"), qn("p:pic"), qn("p:cxnSp")}
R_PREFIX = "{" + NS["r"] + "}"


def iter_shapes(container):
    """Yield shapes in tree order, recursing into group shapes (group first, then children)."""
    for child in container:
        if child.tag not in SHAPE_TAGS:
            continue
        yield child
        if child.tag == qn("p:grpSp"):
            yield from iter_shapes(child)


def sp_tree(slide):
    return slide.shapes._spTree


def shape_id(el) -> int | None:
    c_nv_pr = el.find("./*/p:cNvPr", NS)
    if c_nv_pr is None:
        return None
    try:
        return int(c_nv_pr.get("id"))
    except (TypeError, ValueError):
        return None


def ph_info(el):
    """Return (idx, type) for a placeholder shape, else None."""
    ph = el.find("./*/p:nvPr/p:ph", NS)
    if ph is None:
        return None
    try:
        idx = int(ph.get("idx", "0"))
    except ValueError:
        idx = 0
    return idx, ph.get("type")


def graphic_tbl(el):
    return el.find("./a:graphic/a:graphicData/a:tbl", NS)


def shape_kind(el) -> str:
    """text | table | chart | smartart | media | group | connector | shape | other."""
    tag = el.tag
    if tag == qn("p:sp"):
        return "text" if el.find("p:txBody", NS) is not None else "shape"
    if tag == qn("p:grpSp"):
        return "group"
    if tag == qn("p:cxnSp"):
        return "connector"
    if tag == qn("p:pic"):
        return "media"
    data = el.find("./a:graphic/a:graphicData", NS)
    uri = data.get("uri") if data is not None else None
    return {URI_TABLE: "table", URI_CHART: "chart", URI_DIAGRAM: "smartart"}.get(uri, "other")


def placeholder_kind(ph_type) -> str:
    if ph_type in TITLE_TYPES:
        return "title"
    if ph_type in BODY_TYPES:
        return "body"
    return "other"


def table_index(slides):
    """Document-wide tables: list of (slide_no, slide, shape_el, tbl) in t:N order."""
    found = []
    for no, slide in enumerate(slides, 1):
        for el in iter_shapes(sp_tree(slide)):
            if el.tag == qn("p:graphicFrame") and shape_kind(el) == "table":
                tbl = graphic_tbl(el)
                if tbl is not None:
                    found.append((no, slide, el, tbl))
    return found


def table_rows(tbl):
    return tbl.findall("a:tr", NS)


def row_cells(tr):
    return tr.findall("a:tc", NS)


def table_cols(tbl) -> int:
    grid = tbl.findall("./a:tblGrid/a:gridCol", NS)
    if grid:
        return len(grid)
    rows = table_rows(tbl)
    return len(row_cells(rows[0])) if rows else 0


def paragraphs(tx_body):
    return tx_body.findall("a:p", NS)


def para_level(p) -> int:
    ppr = p.find("a:pPr", NS)
    try:
        return int(ppr.get("lvl", "0")) if ppr is not None else 0
    except ValueError:
        return 0


def para_text(p) -> str:
    parts = []
    for child in p:
        if child.tag in (qn("a:r"), qn("a:fld")):
            t = child.find("a:t", NS)
            parts.append(t.text or "" if t is not None else "")
        elif child.tag == qn("a:br"):
            parts.append("\v")
    return "".join(parts)


def body_text(tx_body) -> str:
    return "\n".join(para_text(p) for p in paragraphs(tx_body))


def _new_run(p):
    run = p.makeelement(qn("a:r"), {})
    end = p.find("a:endParaRPr", NS)
    if end is not None:
        rpr = copy.deepcopy(end)
        rpr.tag = qn("a:rPr")
        for ext in rpr.findall("a:extLst", NS):
            rpr.remove(ext)
        run.append(rpr)
        end.addprevious(run)
    else:
        p.append(run)
    return run


def set_para_text(p, text: str) -> None:
    """Keep the first a:r (with its a:rPr), drop other runs/breaks/fields, set its text."""
    first = p.find("a:r", NS)
    for child in list(p):
        if child.tag in (qn("a:r"), qn("a:br"), qn("a:fld")) and child is not first:
            p.remove(child)
    run = first if first is not None else _new_run(p)
    t = run.find("a:t", NS)
    if t is None:
        t = run.makeelement(qn("a:t"), {})
        run.append(t)
    t.text = text


def set_body_text(tx_body, text: str) -> None:
    """Whole-frame text: keep the first paragraph, remove the others."""
    paras = paragraphs(tx_body)
    if not paras:
        p = tx_body.makeelement(qn("a:p"), {})
        tx_body.append(p)
        paras = [p]
    for extra in paras[1:]:
        tx_body.remove(extra)
    set_para_text(paras[0], text)


def remap_rids(el, rid_map: dict) -> None:
    """Rewrite every r:* attribute value in `el` (and descendants) through `rid_map`, once."""
    for node in el.iter(etree.Element):
        for name, value in list(node.attrib.items()):
            if name.startswith(R_PREFIX) and value in rid_map:
                node.set(name, rid_map[value])
