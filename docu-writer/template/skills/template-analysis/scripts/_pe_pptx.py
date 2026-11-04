"""PPTX: python-pptx로 표 목록·슬라이드 섹션·레이아웃·지문 후보·빈 플레이스홀더·개체를 읽음."""
import zipfile
from pathlib import Path

from _pe_common import Candidates, UsageError, cell_text, collapse, line_marker, table_entry, unique

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


def open_prs(path: Path):
    from pptx import Presentation
    from pptx.exc import PackageNotFoundError

    try:
        return Presentation(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise UsageError(f"PPTX를 열 수 없음: {exc}") from exc


def iter_shapes(shapes):
    """도형 트리 순서로 모든 도형 (그룹 안 도형 포함, 그룹 자신도 냄)."""
    from pptx.shapes.group import GroupShape

    for shape in shapes:
        yield shape
        if isinstance(shape, GroupShape):
            yield from iter_shapes(shape.shapes)


def pptx_cell_text(cell) -> str:
    return cell_text(p.text for p in cell.text_frame.paragraphs)


def slide_tables(prs):
    """[(슬라이드 번호, 표 도형)] — 슬라이드 순서·도형 트리 순서."""
    out = []
    for n, slide in enumerate(prs.slides, 1):
        for shape in iter_shapes(slide.shapes):
            if getattr(shape, "has_table", False) and shape.has_table:
                out.append((n, shape))
    return out


def tables(path: Path):
    warnings, out = [], []
    for n, shape in slide_tables(open_prs(path)):
        table = shape.table
        rows, cols = len(table.rows), len(table.columns)
        first = pptx_cell_text(table.cell(0, 0)) if rows and cols else ""
        last_row = [pptx_cell_text(table.cell(rows - 1, c)) for c in range(cols)] if rows else []
        out.append(table_entry(len(out) + 1, rows, cols, first, last_row, 0, warnings, slide=n))
    return out, warnings


def slide_count(path: Path) -> int:
    return len(open_prs(path).slides)


def is_title(shape) -> bool:
    from pptx.enum.shapes import PP_PLACEHOLDER

    if not shape.is_placeholder:
        return False
    return shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)


def heading_texts(path: Path):
    """h:"…" anchor용: 슬라이드 제목 글."""
    out = []
    for slide in open_prs(path).slides:
        title = slide.shapes.title
        out.append(collapse(title.text_frame.text) if title is not None else "")
    return out


def sections(prs, warnings):
    out = []
    for n, slide in enumerate(prs.slides, 1):
        title = slide.shapes.title
        text = collapse(title.text_frame.text) if title is not None else ""
        if not text:
            warnings.append(f"sl:{n}: 제목 플레이스홀더 글이 없어 title을 비움")
        out.append({"title": text, "level": 1, "anchor": f"sl:{n}"})
    return out


def body_paragraphs(prs):
    """제목이 아닌 글 도형의 문단 (슬라이드 번호, 문단)."""
    for n, slide in enumerate(prs.slides, 1):
        for shape in iter_shapes(slide.shapes):
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame and not is_title(shape):
                for para in shape.text_frame.paragraphs:
                    yield n, para


def master_bullets(prs):
    """마스터 bodyStyle 수준별 buChar {수준(0부터): 부호}."""
    master = prs.slide_masters[0] if len(prs.slide_masters) else None
    if master is None:
        return {}
    out = {}
    for lvl in range(9):
        found = master.element.xpath(f"./p:txStyles/p:bodyStyle/a:lvl{lvl + 1}pPr/a:buChar/@char")
        if found:
            out[lvl] = str(found[0])
    return out


def para_bullet(para, defaults) -> str:
    ppr = para._p.find(a("pPr"))
    if ppr is not None:
        if ppr.find(a("buNone")) is not None:
            return ""
        ch = ppr.find(a("buChar"))
        if ch is not None:
            return ch.get("char", "")
        if ppr.find(a("buAutoNum")) is not None:
            return "1."
    return defaults.get(para.level, "")


def numbering(prs, warnings):
    defaults = master_bullets(prs)
    marks = []
    for _, para in body_paragraphs(prs):
        if para.text.strip():
            marks += [para_bullet(para, defaults), line_marker(para.text)]
    marks = unique(marks)
    if not marks:
        warnings.append("structure.numbering: 본문 줄 머리 부호가 없어 비움")
    return marks


def form_fields(prs):
    fields = []
    for n, slide in enumerate(prs.slides, 1):
        for ph in slide.placeholders:
            if ph.has_text_frame and not ph.text_frame.text.strip():
                fields.append({"id": f"f{len(fields) + 1}", "label": ph.name,
                               "locator": f"sl:{n}/ph:{ph.placeholder_format.idx}", "constraint": ""})
    return fields


def candidates(prs):
    """제목 플레이스홀더·표 머리행(2행 이상 표의 첫 행)을 뺀 글."""
    cands = Candidates()
    for _, para in body_paragraphs(prs):
        cands.add(para.text)
    for _, shape in slide_tables(prs):
        rows = list(shape.table.rows)
        for row in rows if len(rows) == 1 else rows[1:]:
            for cell in row.cells:
                cands.add(" ".join(p.text for p in cell.text_frame.paragraphs))
    return cands.items


def shape_kind(shape) -> str:
    from pptx.shapes.group import GroupShape

    if isinstance(shape, GroupShape):
        return "group"
    if getattr(shape, "has_chart", False) and shape.has_chart:
        return "chart"
    uris = shape._element.xpath(".//a:graphicData/@uri")
    if any("diagram" in str(u) for u in uris):
        return "smartart"
    if shape._element.xpath(".//a:videoFile|.//a:audioFile|.//a:quickTimeFile"):
        return "media"
    return ""


def objects(prs):
    out = []
    for n, slide in enumerate(prs.slides, 1):
        for shape in iter_shapes(slide.shapes):
            kind = shape_kind(shape)
            if kind:
                out.append({"kind": kind, "at": f"sl:{n}/sh:{shape.shape_id}"})
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None \
                and slide.notes_slide.notes_text_frame.text.strip():
            out.append({"kind": "notes", "at": f"sl:{n}"})
    return out


def layouts_used(prs):
    return unique(slide.slide_layout.name for slide in prs.slides)


def profile_parts(path: Path, mode: str):
    from _pe_pptx_design import design

    prs = open_prs(path)
    warnings = []
    fields = form_fields(prs) if mode == "form" else []
    if mode == "form" and not fields:
        warnings.append("fields: 비어 있는 플레이스홀더가 없어 비움")
    parts = {
        "sections": sections(prs, warnings),
        "numbering": numbering(prs, warnings),
        "fields": fields,
        "design": design(prs, warnings),
        "candidates": candidates(prs),
        "objects": objects(prs),
        "warnings": warnings,
    }
    parts["design"]["styles_allowed"] = layouts_used(prs)
    return parts
