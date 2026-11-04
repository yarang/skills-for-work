"""Slide-level operations for patch_pptx.py: duplicate, delete, notes."""
from __future__ import annotations

import copy

from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from _pp_xml import NS, qn, remap_rids, set_body_text, sp_tree

_SKIP_RELS = {RT.SLIDE_LAYOUT, RT.NOTES_SLIDE}
_KEEP_TREE = {qn("p:nvGrpSpPr"), qn("p:grpSpPr")}


def sld_id_of(prs, slide):
    """The p:sldId element in presentation.xml that points at `slide`."""
    want = str(slide.slide_id)
    for sld_id in prs.slides._sldIdLst:
        if sld_id.get("id") == want:
            return sld_id
    raise LookupError(f"slide id {want} is not in the slide list")


def _copy_rels(src, dst) -> dict:
    """Relate `dst` to every part `src` uses (pictures, media, links); return old→new rId."""
    rid_map = {}
    for rel in src.part.rels.values():
        if rel.reltype in _SKIP_RELS:
            continue
        if rel.is_external:
            new_rid = dst.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            new_rid = dst.part.relate_to(rel.target_part, rel.reltype)
        rid_map[rel.rId] = new_rid
    return rid_map


def _copy_background(src, dst, rid_map) -> None:
    bg = src._element.cSld.find("p:bg", NS)
    if bg is None:
        return
    new_bg = copy.deepcopy(bg)
    remap_rids(new_bg, rid_map)
    old = dst._element.cSld.find("p:bg", NS)
    if old is not None:
        dst._element.cSld.remove(old)
    dst._element.cSld.insert(0, new_bg)


def duplicate_slide(prs, src, after_sld_id):
    """New slide with `src`'s layout and a deep copy of its shape tree, placed after `after_sld_id`."""
    new = prs.slides.add_slide(src.slide_layout)
    tree = sp_tree(new)
    for child in list(tree):
        if child.tag not in _KEEP_TREE:
            tree.remove(child)
    rid_map = _copy_rels(src, new)
    for child in sp_tree(src):
        if child.tag in _KEEP_TREE:
            continue
        clone = copy.deepcopy(child)
        remap_rids(clone, rid_map)
        tree.append(clone)
    _copy_background(src, new, rid_map)
    new_sld_id = sld_id_of(prs, new)
    after_sld_id.addnext(new_sld_id)
    return new


def delete_slide(prs, slide) -> None:
    """Drop the p:sldId entry and the presentation's relationship to the slide."""
    sld_id = sld_id_of(prs, slide)
    rid = sld_id.get(qn("r:id"))
    sld_id.getparent().remove(sld_id)
    prs.part.drop_rel(rid)


def set_notes(slide, text: str) -> None:
    """Set the notes text, creating the notes slide when missing."""
    frame = slide.notes_slide.notes_text_frame
    if frame is None:
        raise ValueError("notes slide has no body placeholder")
    set_body_text(frame._txBody, text)


def renumber_slide_parts(prs) -> None:
    """Give slide parts consecutive names in deck order so add_slide never reuses a name."""
    prs.part.rename_slide_parts([s.get(qn("r:id")) for s in prs.slides._sldIdLst])
