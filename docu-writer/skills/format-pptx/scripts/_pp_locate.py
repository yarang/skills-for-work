"""Locator parsing and resolution for patch_pptx.py (docs/design.md §5, format-pptx SKILL.md)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from _pp_xml import (
    NS, NON_EDITABLE, graphic_tbl, iter_shapes, paragraphs, ph_info, row_cells,
    shape_id, shape_kind, sp_tree, table_index, table_rows,
)

_SLIDE = r"(?P<sk>sl|new):(?P<sn>\d+)"
_SHAPE = r"(?:/(?P<hk>ph|sh):(?P<hn>\d+))?"
_CELL = r"/t/r:(?P<r>\d+)/c:(?P<c>\d+)(?:/p:(?P<cp>\d+))?"
_TAIL = rf"(?:/p:(?P<p>\d+)|{_CELL})?"
FULL_RE = re.compile(rf"^{_SLIDE}{_SHAPE}{_TAIL}$")
ALIAS_RE = re.compile(r"^t:(?P<t>\d+)(?:/r:(?P<r>\d+)/c:(?P<c>\d+)(?:/p:(?P<cp>\d+))?)?$")


class LocError(Exception):
    """A locator that does not parse or does not point at anything."""


@dataclass
class Target:
    """kind: slide | frame | para | table | object.

    el: Slide (slide), a:txBody (frame), a:p (para), a:tbl (table), shape element (object).
    """
    kind: str
    slide_key: tuple
    el: object
    shape: object = None
    shape_kind: str = ""
    rows: list = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.shape_kind not in NON_EDITABLE


class Resolver:
    """Resolve locators against the original slides; new:K maps through `new_slides`."""

    def __init__(self, slides):
        self.slides = list(slides)
        self.tables = table_index(self.slides)
        self.new_slides: dict[int, object] = {}

    def slide(self, kind: str, n: int):
        if kind == "sl":
            if 1 <= n <= len(self.slides):
                return self.slides[n - 1]
            raise LocError(f"slide sl:{n} not found ({len(self.slides)} slides)")
        if n in self.new_slides:
            return self.new_slides[n]
        raise LocError(f"new:{n} is not created by an earlier slide_dup")

    def resolve(self, loc) -> Target:
        if not isinstance(loc, str) or not loc:
            raise LocError("locator missing or not a string")
        m = ALIAS_RE.match(loc)
        if m:
            return self._resolve_alias(m)
        m = FULL_RE.match(loc)
        if not m:
            raise LocError(f"bad locator syntax: {loc}")
        key = (m["sk"], int(m["sn"]))
        slide = self.slide(*key)
        if m["hk"] is None:
            if m["p"] or m["r"]:
                raise LocError(f"bad locator syntax: {loc}")
            return Target("slide", key, slide)
        shape = find_shape(slide, m["hk"], int(m["hn"]))
        return descend(key, shape, m)

    def _resolve_alias(self, m) -> Target:
        n = int(m["t"])
        if not 1 <= n <= len(self.tables):
            raise LocError(f"table t:{n} not found ({len(self.tables)} tables)")
        no, _slide, shape, _tbl = self.tables[n - 1]
        return descend(("sl", no), shape, m)


def find_shape(slide, kind: str, n: int):
    for el in iter_shapes(sp_tree(slide)):
        if kind == "sh" and shape_id(el) == n:
            return el
        if kind == "ph":
            info = ph_info(el)
            if info is not None and info[0] == n:
                return el
    raise LocError(f"{kind}:{n} not found on slide")


def _pick(items, n: int, what: str):
    if 1 <= n <= len(items):
        return items[n - 1]
    raise LocError(f"{what} {n} out of range (1..{len(items)})")


def descend(key: tuple, shape, m) -> Target:
    """Turn a shape plus the locator tail (p:K or t/r:R/c:C[/p:K]) into a Target."""
    kind = shape_kind(shape)
    gd = m.groupdict()
    if gd.get("r"):
        if kind != "table":
            raise LocError("cell locator on a shape that is not a table")
        tc = _pick(row_cells(_pick(table_rows(graphic_tbl(shape)), int(gd["r"]), "row")),
                   int(gd["c"]), "column")
        return _text_target(key, shape, kind, tc.find("a:txBody", NS), gd.get("cp"))
    if kind == "text":
        return _text_target(key, shape, kind, shape.find("p:txBody", NS), gd.get("p"))
    if gd.get("p"):
        raise LocError(f"paragraph locator on a {kind} shape")
    if kind == "table":
        tbl = graphic_tbl(shape)
        return Target("table", key, tbl, shape, kind, list(table_rows(tbl)))
    return Target("object", key, shape, shape, kind)


def _text_target(key, shape, kind, tx_body, para_no) -> Target:
    if tx_body is None:
        raise LocError("target has no text body")
    if para_no is None:
        return Target("frame", key, tx_body, shape, kind)
    p = _pick(paragraphs(tx_body), int(para_no), "paragraph")
    return Target("para", key, p, shape, kind)
