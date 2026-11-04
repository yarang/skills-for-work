"""Skeleton dump for patch_pptx.py: locator-tagged blocks in slide and shape-tree order."""
from __future__ import annotations

from _pp_xml import (
    NS, body_text, graphic_tbl, iter_shapes, para_level, para_text, paragraphs,
    ph_info, placeholder_kind, row_cells, shape_id, shape_kind, sp_tree, table_cols, table_rows,
)


def dump_blocks(prs) -> list[dict]:
    blocks: list[dict] = []
    counter = [0]
    for no, slide in enumerate(prs.slides, 1):
        prefix = f"sl:{no}"
        blocks.append({"at": prefix, "layout": slide.slide_layout.name})
        for el in iter_shapes(sp_tree(slide)):
            blocks.extend(_shape_blocks(prefix, el, counter))
    return blocks


def _shape_blocks(prefix: str, el, counter: list) -> list[dict]:
    kind = shape_kind(el)
    sid = shape_id(el)
    if kind == "text":
        return _text_blocks(prefix, el, sid)
    if kind == "table":
        counter[0] += 1
        return _table_blocks(f"{prefix}/sh:{sid}", graphic_tbl(el), counter[0])
    if kind in ("chart", "smartart", "media", "other"):
        return [{"at": f"{prefix}/sh:{sid}", "kind": kind, "editable": False}]
    return []


def _text_blocks(prefix: str, el, sid) -> list[dict]:
    info = ph_info(el)
    if info is not None:
        at, kind = f"{prefix}/ph:{info[0]}", placeholder_kind(info[1])
    else:
        at, kind = f"{prefix}/sh:{sid}", "text"
    tx_body = el.find("p:txBody", NS)
    blocks = [{"at": at, "kind": kind, "text": body_text(tx_body)}]
    paras = paragraphs(tx_body)
    if len(paras) > 1:
        blocks += [{"at": f"{at}/p:{k}", "level": para_level(p), "text": para_text(p)}
                   for k, p in enumerate(paras, 1)]
    return blocks


def _table_blocks(at: str, tbl, number: int) -> list[dict]:
    rows = table_rows(tbl)
    blocks = [{"at": at, "kind": "table", "table": f"t:{number}",
               "rows": len(rows), "cols": table_cols(tbl)}]
    for r, tr in enumerate(rows, 1):
        for c, tc in enumerate(row_cells(tr), 1):
            body = tc.find("a:txBody", NS)
            blocks.append({"at": f"{at}/t/r:{r}/c:{c}",
                           "text": body_text(body) if body is not None else ""})
    return blocks
