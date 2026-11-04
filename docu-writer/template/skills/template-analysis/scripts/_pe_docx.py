"""DOCX: python-docx와 그 lxml 트리로 표 목록·섹션·스타일·지문 후보·빈칸·개체를 읽음."""
import re
import zipfile
from pathlib import Path

from _pe_common import Candidates, UsageError, cell_text, collapse, table_entry, unique

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
HEADING_RE = re.compile(r"^(?:heading|제목)\s*(\d)$", re.IGNORECASE)
TITLE_NAMES = {"title", "제목"}
BLANK_RE = re.compile(r"^[_\s]*$")


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def open_doc(path: Path):
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        return Document(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise UsageError(f"DOCX를 열 수 없음: {exc}") from exc


def para_text(p) -> str:
    """문단 글: w:t를 잇고 탭·줄바꿈은 공백으로."""
    parts = []
    for el in p.iter(w("t"), w("tab"), w("br")):
        parts.append((el.text or "") if el.tag == w("t") else " ")
    return "".join(parts)


def own_paragraphs(tc):
    """칸 자신의 문단 (안에 든 표의 문단은 뺌)."""
    return list(tc.iterchildren(w("p")))


def tc_text(tc) -> str:
    return cell_text(para_text(p) for p in own_paragraphs(tc))


def grid_rows(tbl):
    """[[(그리드 열 1부터, tc), …], …] — 세로 병합 이어짐 칸은 뺌."""
    rows = []
    for tr in tbl.iterchildren(w("tr")):
        col, cells = 1, []
        for tc in tr.iterchildren(w("tc")):
            span = tc.find(f"{w('tcPr')}/{w('gridSpan')}")
            vmerge = tc.find(f"{w('tcPr')}/{w('vMerge')}")
            if vmerge is None or vmerge.get(w("val")) == "restart":
                cells.append((col, tc))
            col += int(span.get(w("val"))) if span is not None else 1
        rows.append(cells)
    return rows


def table_info(tbl, index, warnings):
    trs = list(tbl.iterchildren(w("tr")))
    grid = tbl.find(w("tblGrid"))
    cols = len(grid.findall(w("gridCol"))) if grid is not None else 0
    tcs = [list(tr.iterchildren(w("tc"))) for tr in trs]
    cols = cols or max((len(r) for r in tcs), default=0)
    first = tc_text(tcs[0][0]) if tcs and tcs[0] else ""
    last_row = [tc_text(tc) for tc in tcs[-1]] if tcs else []
    nested = sum(1 for _ in tbl.iterdescendants(w("tbl")))
    return table_entry(index, len(trs), cols, first, last_row, nested, warnings)


def tables_of(doc):
    warnings = []
    out = [table_info(t._tbl, i, warnings) for i, t in enumerate(doc.tables, 1)]
    return out, warnings


def tables(path: Path):
    return tables_of(open_doc(path))


def heading_level(style_name: str):
    """제목 스타일이면 수준(Title=0), 아니면 None."""
    name = (style_name or "").strip()
    if name.lower() in TITLE_NAMES:
        return 0
    m = HEADING_RE.match(name)
    return int(m.group(1)) if m else None


def paragraph_count(path: Path) -> int:
    return len(open_doc(path).paragraphs)


def heading_texts(path: Path):
    """h:"…" anchor용: 최상위 문단 글 (p:N 순서)."""
    return [para_text(p._p) for p in open_doc(path).paragraphs]


def sections(doc, warnings):
    out = []
    for n, para in enumerate(doc.paragraphs, 1):
        level = heading_level(para.style.name if para.style is not None else "")
        if level is None:
            continue
        title = collapse(para_text(para._p))
        if not title:
            warnings.append(f"p:{n}: 빈 제목 문단이라 섹션에서 뺌")
            continue
        out.append({"title": title, "level": level, "anchor": f"p:{n}"})
    if not out:
        warnings.append("structure.sections: 제목 스타일 문단이 없어 비움")
    return out


def styles_allowed(doc):
    """본문(표 칸 안 포함)에서 실제로 쓰인 문단·글자 스타일 이름."""
    from docx.enum.style import WD_STYLE_TYPE

    names = {s.style_id: s.name for s in doc.styles}
    default = doc.styles.default(WD_STYLE_TYPE.PARAGRAPH)
    used = []
    for p in doc.element.body.iter(w("p")):
        pstyle = p.find(f"{w('pPr')}/{w('pStyle')}")
        sid = pstyle.get(w("val")) if pstyle is not None else None
        used.append(names.get(sid) if sid else (default.name if default is not None else ""))
        for rstyle in p.iter(w("rStyle")):
            used.append(names.get(rstyle.get(w("val")), ""))
    return unique(used)


def table_candidates(tbl, cands):
    rows = list(tbl.iterchildren(w("tr")))
    body_rows = rows if len(rows) == 1 else rows[1:]
    for tr in body_rows:
        for tc in tr.iterchildren(w("tc")):
            cands.add(" ".join(para_text(p) for p in own_paragraphs(tc)))
    for tr in rows:
        for tc in tr.iterchildren(w("tc")):
            for inner in tc.iterchildren(w("tbl")):
                table_candidates(inner, cands)


def candidates(doc):
    """제목 스타일 문단·표 머리행(2행 이상 표의 첫 행)을 뺀 본문 글."""
    cands = Candidates()
    for para in doc.paragraphs:
        if heading_level(para.style.name if para.style is not None else "") is None:
            cands.add(para_text(para._p))
    for table in doc.tables:
        table_candidates(table._tbl, cands)
    return cands.items


def form_fields(doc):
    """빈 칸·밑줄 칸: 이름표는 왼쪽 칸 글, 없으면 같은 열 첫 행 글."""
    fields = []
    for n, table in enumerate(doc.tables, 1):
        rows = grid_rows(table._tbl)
        header = {col: tc_text(tc) for col, tc in rows[0]} if rows else {}
        for r, cells in enumerate(rows, 1):
            for k, (col, tc) in enumerate(cells):
                if not BLANK_RE.match(" ".join(para_text(p) for p in own_paragraphs(tc))):
                    continue
                left = tc_text(cells[k - 1][1]) if k > 0 else ""
                label = left or (header.get(col, "") if r > 1 else "")
                fields.append({"id": f"f{len(fields) + 1}", "label": label,
                               "locator": f"t:{n}/r:{r}/c:{col}", "constraint": ""})
    return fields


OBJECT_TAGS = {
    "txbxContent": "textbox", "textbox": "textbox", "fldSimple": "field",
    "ins": "tracked_change", "del": "tracked_change", "moveFrom": "tracked_change",
    "moveTo": "tracked_change", "commentRangeStart": "comment", "commentReference": "comment",
}


def block_objects(block):
    kinds = []
    for el in block.iter():
        if not isinstance(el.tag, str):
            continue
        local = el.tag.rsplit("}", 1)[-1]
        if local in OBJECT_TAGS:
            kinds.append(OBJECT_TAGS[local])
        elif local == "fldChar" and el.get(w("fldCharType")) == "begin":
            kinds.append("field")
        elif local == "graphicData":
            uri = el.get("uri", "")
            kinds.append("smartart" if "diagram" in uri else "chart" if "chart" in uri else "")
    return unique(kinds)


def objects(doc):
    """편집 불가 개체 위치: 최상위 문단 p:N 또는 표 t:N."""
    out, p_n, t_n = [], 0, 0
    for block in doc.element.body.iterchildren():
        if block.tag == w("p"):
            p_n += 1
            at = f"p:{p_n}"
        elif block.tag == w("tbl"):
            t_n += 1
            at = f"t:{t_n}"
        else:
            continue
        out += [{"kind": kind, "at": at} for kind in block_objects(block)]
    return out


def profile_parts(path: Path, mode: str):
    from _pe_docx_design import design, numbering

    doc = open_doc(path)
    warnings = []
    fields = form_fields(doc) if mode == "form" else []
    if mode == "form" and not fields:
        warnings.append("fields: 빈 칸·밑줄 칸이 있는 표 칸이 없어 비움")
    parts = {
        "sections": sections(doc, warnings),
        "numbering": numbering(doc, warnings),
        "fields": fields,
        "design": design(doc, warnings),
        "candidates": candidates(doc),
        "objects": objects(doc),
        "warnings": warnings,
    }
    parts["design"]["styles_allowed"] = styles_allowed(doc)
    return parts
