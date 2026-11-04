"""Edit validation and execution for patch_pptx.py apply.

Every edit is validated against the original deck first (locators are dump-time).
Execution runs in three phases: slide_dup, then text/row/notes edits, then slide_delete,
so duplicates copy the sample content and deletions never shift other edits.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from _pp_locate import LocError, Resolver, Target
from _pp_slides import delete_slide, duplicate_slide, renumber_slide_parts, set_notes, sld_id_of
from _pp_xml import NS as _NS, body_text, para_text, paragraphs, row_cells, set_body_text, set_para_text

OPS = {
    "replace": ("at", "text"),
    "insert_after": ("at", "like", "text"),
    "delete": ("at",),
    "slide_dup": ("like", "after"),
    "slide_delete": ("at",),
    "row_add": ("table", "like_row", "after", "cells"),
    "row_delete": ("table", "row"),
    "notes": ("at", "text"),
}
OVERFLOW_RATIO = 1.3
_SL_RE = re.compile(r"^sl:\d+$")
_SLIDE_RE = re.compile(r"^(sl|new):(\d+)$")


class EditError(Exception):
    """An edit that cannot be applied; the message is the failure reason."""


@dataclass
class Ref:
    loc: str
    target: Target
    deferred: bool


def edit_at(edit) -> object:
    if not isinstance(edit, dict):
        return None
    op = edit.get("op")
    if op in ("row_add", "row_delete"):
        return edit.get("table")
    if op == "slide_dup":
        return edit.get("like")
    return edit.get("at")


def _text(edit, name="text") -> str:
    value = edit[name]
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise EditError(f"{name} must be a string")
    value = str(value)
    if "\n" in value or "\r" in value:
        raise EditError(f"line break in {name}; use insert_after for a new paragraph")
    return value


def _int(edit, name) -> int:
    value = edit[name]
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError(f"{name} must be an integer")
    return value


def _text_target(ref: Ref, kinds: tuple) -> Target:
    t = ref.target
    if not t.editable:
        raise EditError(f"{ref.loc} is editable: false ({t.shape_kind})")
    if t.kind not in kinds:
        raise EditError(f"{ref.loc} is a {t.kind} target, expected {' or '.join(kinds)}")
    return t


class Planner:
    """Validate edits into jobs, then run them in phase order."""

    def __init__(self, prs, styles_allowed):
        self.prs = prs
        slides = list(prs.slides)
        self.check = Resolver(slides)  # new:K -> the `like` slide, for structural checks
        self.live = Resolver(slides)   # new:K -> the real duplicate, after phase 0
        self.allowed = list(styles_allowed or [])
        self.dup_seq = 0
        self.refs: list[Ref] = []
        self.jobs: list[tuple] = []
        self.warnings: list[str] = []
        self.counts: dict = {}
        self.gone: set = set()
        self.slides_gone: set = set()     # slide keys ("sl"|"new", N) queued for slide_delete
        self.slides_touched: set = set()  # slide keys that text/row/notes edits point into
        self.tails: dict = {}
        self.slide_tails: dict = {}       # p:sldId -> last p:sldId inserted after it

    # --- validation ------------------------------------------------------------

    def add(self, edit) -> None:
        """Validate one edit and queue its job; raise EditError on failure."""
        if not isinstance(edit, dict):
            raise EditError("edit must be a mapping")
        op = edit.get("op")
        if op not in OPS:
            raise EditError(f"unknown op: {op!r}")
        missing = [f for f in OPS[op] if edit.get(f) is None]
        if missing:
            raise EditError(f"missing field(s): {', '.join(missing)}")
        if op == "slide_dup":
            self.dup_seq += 1
        job = getattr(self, f"_v_{op}")(edit)
        self.jobs.append((2 if op == "slide_delete" else 0 if op == "slide_dup" else 1,
                          job, op, edit_at(edit)))

    def _ref(self, loc, guard=True) -> Ref:
        """Resolve loc. guard=False is for slide_dup/slide_delete, which may name a slide
        that is (or will be) deleted — dup then delete is how a slide is moved."""
        try:
            target = self.check.resolve(loc)
        except LocError as exc:
            raise EditError(str(exc)) from exc
        if guard:
            if target.slide_key in self.slides_gone:
                raise EditError(f"{loc} is on a slide deleted by an earlier edit")
            self.slides_touched.add(target.slide_key)
        ref = Ref(loc, target, loc.startswith("new:"))
        if ref.deferred:
            self.refs.append(ref)
        return ref

    def _count(self, key, initial: int) -> int:
        return self.counts.setdefault(key, initial)

    def _v_replace(self, edit):
        text = _text(edit)
        ref = self._ref(edit["at"])
        t = _text_target(ref, ("frame", "para"))
        orig = body_text(t.el) if t.kind == "frame" else para_text(t.el)
        if len(text) > OVERFLOW_RATIO * len(orig):
            self.warnings.append(f"overflow? {ref.loc}: {len(text)} chars vs {len(orig)}")
        if t.kind == "frame":
            return lambda: set_body_text(ref.target.el, text)
        return lambda: set_para_text(ref.target.el, text)

    def _v_insert_after(self, edit):
        text = _text(edit)
        at, like = self._ref(edit["at"]), self._ref(edit["like"])
        ta, tl = _text_target(at, ("para",)), _text_target(like, ("para",))
        if ta.slide_key != tl.slide_key or ta.el.getparent() is not tl.el.getparent():
            raise EditError("like paragraph must be in the same text body as at")
        if (ta.slide_key, ta.el) in self.gone:
            raise EditError(f"{at.loc} is deleted by an earlier edit")
        key = (ta.slide_key, ta.el.getparent())
        self.counts[key] = self._count(key, len(paragraphs(key[1]))) + 1
        return lambda: self._insert(at.target.el, copy.deepcopy(like.target.el), text)

    def _insert(self, anchor, new_p, text) -> None:
        set_para_text(new_p, text)
        self.tails.get(anchor, anchor).addnext(new_p)
        self.tails[anchor] = new_p

    def _v_delete(self, edit):
        ref = self._ref(edit["at"])
        t = _text_target(ref, ("para",))
        key = (t.slide_key, t.el.getparent())
        if (t.slide_key, t.el) in self.gone:
            raise EditError(f"{ref.loc} is already deleted by an earlier edit")
        left = self._count(key, len(paragraphs(key[1])))
        if left <= 1:
            raise EditError(f"{ref.loc} is the only paragraph left in its text body")
        self.counts[key] = left - 1
        self.gone.add((t.slide_key, t.el))
        return lambda: _detach(ref.target.el)

    def _slide_ref(self, loc, allow_new=True, guard=True) -> Ref:
        if not isinstance(loc, str) or not (_SLIDE_RE.match(loc) if allow_new else _SL_RE.match(loc)):
            raise EditError(f"{loc!r} must be {'sl:N or new:K' if allow_new else 'sl:N'}")
        return self._ref(loc, guard)

    def _v_slide_dup(self, edit):
        seq = self.dup_seq
        like = self._slide_ref(edit["like"], allow_new=False, guard=False)
        after = self._slide_ref(edit["after"], guard=False)
        layout = like.target.el.slide_layout.name
        if self.allowed and layout not in self.allowed:
            raise EditError(f"layout {layout!r} of {like.loc} is not in design.styles_allowed")
        self.check.new_slides[seq] = like.target.el
        after_id = None if after.deferred else sld_id_of(self.prs, after.target.el)

        def run():
            anchor = after_id if after_id is not None else sld_id_of(self.prs, self.live.slide(
                "new", int(after.loc.split(":")[1])))
            new = duplicate_slide(self.prs, like.target.el, self._slide_tail(anchor))
            self.slide_tails[anchor] = sld_id_of(self.prs, new)
            self.live.new_slides[seq] = new
        return run

    def _slide_tail(self, sld_id):
        """Last slide already chained after sld_id (following chains), so several dups
        after the same slide keep their listed order instead of reversing it."""
        while sld_id in self.slide_tails:
            sld_id = self.slide_tails[sld_id]
        return sld_id

    def _v_slide_delete(self, edit):
        ref = self._slide_ref(edit["at"], guard=False)
        key = ref.target.slide_key
        if key in self.slides_gone:
            raise EditError(f"{ref.loc} is already deleted by an earlier edit")
        if key in self.slides_touched:
            raise EditError(f"{ref.loc} has other edits; deleting it would discard them")
        if len(self.check.slides) + self.dup_seq - len(self.slides_gone) <= 1:
            raise EditError(f"{ref.loc} is the only slide left in the deck")
        self.slides_gone.add(key)
        return lambda: delete_slide(self.prs, ref.target.el)

    def _v_notes(self, edit):
        text = _text(edit)
        ref = self._slide_ref(edit["at"])
        return lambda: set_notes(ref.target.el, text)

    def _table(self, edit) -> Ref:
        ref = self._ref(edit["table"])
        if ref.target.kind != "table":
            raise EditError(f"{ref.loc} is not a table (use sl:N/sh:S or t:N)")
        return ref

    def _row(self, ref: Ref, edit, name, key) -> int:
        n = _int(edit, name)
        rows = ref.target.rows
        if not 1 <= n <= len(rows):
            raise EditError(f"{name} {n} out of range (1..{len(rows)})")
        if (key[0], rows[n - 1]) in self.gone:
            raise EditError(f"{name} {n} is deleted by an earlier edit")
        return n

    def _v_row_add(self, edit):
        ref = self._table(edit)
        key = (ref.target.slide_key, ref.target.el)
        like_row, after = self._row(ref, edit, "like_row", key), self._row(ref, edit, "after", key)
        cells = edit["cells"]
        if not isinstance(cells, list):
            raise EditError("cells must be a list")
        texts = [_text({"cell": c}, "cell") for c in cells]
        width = len(row_cells(ref.target.rows[like_row - 1]))
        if len(texts) != width:
            raise EditError(f"cells has {len(texts)} values, row {like_row} has {width} cells")
        self.counts[key] = self._count(key, len(ref.target.rows)) + 1
        return lambda: self._add_row(ref.target.rows, like_row, after, texts)

    def _add_row(self, rows, like_row, after, texts) -> None:
        new_tr = copy.deepcopy(rows[like_row - 1])
        for tc, text in zip(row_cells(new_tr), texts):
            body = tc.find("a:txBody", _NS)
            if body is None:
                raise EditError("table cell has no text body")
            set_body_text(body, text)
        anchor = rows[after - 1]
        self.tails.get(anchor, anchor).addnext(new_tr)
        self.tails[anchor] = new_tr

    def _v_row_delete(self, edit):
        ref = self._table(edit)
        key = (ref.target.slide_key, ref.target.el)
        n = self._row(ref, edit, "row", key)
        left = self._count(key, len(ref.target.rows))
        if left <= 1:
            raise EditError(f"row {n} is the only row left in {ref.loc}")
        self.counts[key] = left - 1
        self.gone.add((key[0], ref.target.rows[n - 1]))
        return lambda: _detach(ref.target.rows[n - 1])

    # --- execution -------------------------------------------------------------

    def run(self) -> list[dict]:
        """Execute queued jobs by phase; return runtime failures (normally none)."""
        failed = []
        renumber_slide_parts(self.prs)
        for phase in (0, 1, 2):
            if phase == 1:
                failed += self._rebind()
            for job_phase, job, op, at in self.jobs:
                if job_phase != phase:
                    continue
                try:
                    job()
                except Exception as exc:  # noqa: BLE001 - reported as a failed edit
                    failed.append({"op": op, "at": at, "reason": f"apply error: {exc}"})
        renumber_slide_parts(self.prs)
        return failed

    def _rebind(self) -> list[dict]:
        """Point new:K references at the real duplicated slides."""
        failed = []
        for ref in self.refs:
            try:
                ref.target = self.live.resolve(ref.loc)
            except LocError as exc:
                failed.append({"op": "rebind", "at": ref.loc, "reason": str(exc)})
        return failed


def _detach(el) -> None:
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)
