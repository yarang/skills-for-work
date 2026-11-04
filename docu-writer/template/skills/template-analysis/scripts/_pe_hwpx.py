"""HWPX: zip 안 Contents/section*.xml을 lxml로 직접 읽음 (표 목록·anchor 대상 문단)."""
import re
import zipfile
from pathlib import Path

from lxml import etree

from _pe_common import UsageError, cell_text, table_entry

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
SKIP_ANCESTORS = {f"{{{HP}}}header", f"{{{HP}}}footer"}
TBL = f"{{{HP}}}tbl"


def q(tag: str) -> str:
    return f"{{{HP}}}{tag}"


def section_roots(path: Path):
    """section0.xml, section1.xml … 숫자 순서로 루트 요소를 냄."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
            names.sort(key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
            blobs = [zf.read(n) for n in names]
    except (zipfile.BadZipFile, OSError) as exc:
        raise UsageError(f"HWPX를 열 수 없음: {exc}") from exc
    if not blobs:
        raise UsageError("HWPX에 Contents/section*.xml이 없음")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    try:
        return [etree.fromstring(b, parser) for b in blobs]
    except etree.XMLSyntaxError as exc:
        raise UsageError(f"HWPX 본문 XML 오류: {exc}") from exc


def t_text(t) -> str:
    """hp:t 글: 안의 탭·줄바꿈 요소는 공백으로."""
    parts = [t.text or ""]
    for child in t:
        if etree.QName(child).localname in ("tab", "lineBreak"):
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


def para_text(p) -> str:
    """문단에 직접 속한 run의 hp:t 글만 이어 붙임 (안에 든 표·글상자 글은 뺌)."""
    return "".join(t_text(t) for run in p.iterchildren(q("run")) for t in run.iterchildren(q("t")))


def top_level_tables(root):
    out = []
    for tbl in root.iter(TBL):
        ancestors = {a.tag for a in tbl.iterancestors()}
        if TBL in ancestors or ancestors & SKIP_ANCESTORS:
            continue
        out.append(tbl)
    return out


def tc_text(tc) -> str:
    paras = [p for sub in tc.iterchildren(q("subList")) for p in sub.iterchildren(q("p"))]
    return cell_text(para_text(p) for p in paras)


def table_info(tbl, index, warnings):
    rows = [tr for tr in tbl.iterchildren(q("tr"))]
    cells = [list(tr.iterchildren(q("tc"))) for tr in rows]
    row_cnt = int(tbl.get("rowCnt") or len(rows))
    col_cnt = int(tbl.get("colCnt") or max((len(c) for c in cells), default=0))
    first = tc_text(cells[0][0]) if cells and cells[0] else ""
    last_row = [tc_text(tc) for tc in cells[-1]] if cells else []
    nested = sum(1 for _ in tbl.iterdescendants(TBL))
    return table_entry(index, row_cnt, col_cnt, first, last_row, nested, warnings)


def tables(path: Path):
    warnings = []
    out = []
    for root in section_roots(path):
        for tbl in top_level_tables(root):
            out.append(table_info(tbl, len(out) + 1, warnings))
    return out, warnings


def heading_texts(path: Path):
    """anchor 대상: 모든 hp:p의 직접 글 (표 칸 안 문단도 따로 한 문단)."""
    texts = []
    for root in section_roots(path):
        for p in root.iter(q("p")):
            ancestors = {a.tag for a in p.iterancestors()}
            if ancestors & SKIP_ANCESTORS:
                continue
            texts.append(para_text(p))
    return texts
