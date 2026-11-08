"""doc_verify.py 형식별 읽기 — DOCX·PPTX·MD·HWPX를 같은 모델(Doc)로 바꿉니다.

모델: Doc.blocks는 본문 순서의 최상위 문단(Para)과 최상위 표(Table)입니다.
표 번호 `t:N`은 설계서 §5 「표 번호」, 문단 번호 `p:N`은 「문단 번호」 규칙을 따릅니다.
"""
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

WS = re.compile(r"\s+")
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
FORMATS = {".docx": "docx", ".pptx": "pptx", ".md": "md", ".hwpx": "hwpx"}


# 압축 폭탄 방지: 선언된 압축 해제 크기를 먼저 봅니다. zipfile은 항목을 읽을 때
# 선언 크기를 넘겨 풀지 않으므로(ZipExtFile), 선언 크기 검사로 상한이 지켜집니다.
ZIP_MAX_ENTRIES = 20_000
ZIP_MAX_TOTAL = 1 << 30          # 압축을 푼 전체 크기 1 GiB
ZIP_MAX_RATIO = 200              # 10 MiB를 넘는 항목의 압축률 상한


def zip_problem(path) -> str | None:
    """OOXML·HWPX 패키지가 지나치게 크거나 압축률이 비정상이면 그 이유를 돌려줍니다."""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
    except (zipfile.BadZipFile, OSError):
        return None              # 열 수 없는 파일은 형식별 로더가 원래 오류로 보고합니다
    if len(infos) > ZIP_MAX_ENTRIES:
        return f"zip 항목이 너무 많습니다 ({len(infos)}개 > {ZIP_MAX_ENTRIES})"
    total = sum(i.file_size for i in infos)
    if total > ZIP_MAX_TOTAL:
        return f"압축을 푼 크기가 너무 큽니다 ({total} 바이트 > {ZIP_MAX_TOTAL})"
    for i in infos:
        if i.file_size > 10 << 20 and i.file_size > ZIP_MAX_RATIO * max(i.compress_size, 1):
            return f"압축률이 비정상입니다: {i.filename}"
    return None


def nows(text: str) -> str:
    """공백을 모두 뺀 글 — 비교용."""
    return WS.sub("", text or "")


@dataclass
class Run:
    text: str
    fonts: tuple = ()          # run에 직접 적힌 서체 이름
    pt: float | None = None    # run에 직접 적힌 크기
    color: str | None = None   # run에 직접 적힌 색 (#RRGGBB)
    eff: tuple = (None, None, None)  # 물려받은 값까지 푼 (서체, 크기, 굵기) — R4


@dataclass
class Para:
    text: str
    loc: str | None = None
    style: str | None = None
    level: tuple = ()
    heading: str | None = None   # "title" | "h1" … | None
    runs: list = field(default_factory=list)
    slide: int | None = None


@dataclass
class Table:
    at: str
    rows: list                   # 행마다 칸 글 (칸 바로 아래 문단만, 앞뒤 공백 제거)
    texts: list = field(default_factory=list)   # 표 안 모든 문단 글 (안쪽 표 포함)
    paras: list = field(default_factory=list)   # 표 안 문단 (스타일·run 서식)
    header: tuple | None = None  # 머리행 서식 (굵기 집합, 바탕색 집합)
    slide: int | None = None
    alias: str | None = None     # PPTX `sl:N/sh:K`


@dataclass
class Doc:
    fmt: str
    blocks: list
    extra: list = field(default_factory=list)   # 블록 밖 글 (글상자 등) — 잔존 찾기용
    styles: list = field(default_factory=list)  # [(스타일·레이아웃 이름, locator)]
    ids: tuple | None = None                    # HWPX (글자 모양 id 집합, 문단 모양 id 집합)
    slides: int | None = None
    anchors: list | None = None                 # h:"…" anchor 대상 [(공백 뺀 글, 블록 번호[, 원래 글])]. None = 최상위 문단
    slide_ids: tuple = ()                       # PPTX 슬라이드 순서대로 p:sldId/@id — sl:N anchor를 정체성으로 찾음

    @property
    def tables(self) -> list:
        return [b for b in self.blocks if isinstance(b, Table)]

    @property
    def paras(self) -> list:
        return [b for b in self.blocks if isinstance(b, Para)]


def doc_format(path: Path) -> str | None:
    return FORMATS.get(path.suffix.lower())


class PackageRejected(ValueError):
    """패키지를 열지 않기로 한 이유 (doc_verify가 종료 코드 2로 보고)."""


def safe_parser():
    from lxml import etree

    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def read_doc(path: Path) -> Doc:
    fmt = doc_format(path)
    problem = zip_problem(path) if fmt in ("docx", "pptx", "hwpx") else None
    if problem:
        raise PackageRejected(f"{path.name}: {problem}")
    reader = {"docx": read_docx, "pptx": read_pptx, "md": read_md, "hwpx": read_hwpx}[fmt]
    return reader(path)


def all_paras(doc: Doc):
    """최상위 문단과 표 안 문단 모두."""
    for b in doc.blocks:
        if isinstance(b, Para):
            yield b
        else:
            yield from b.paras


def cell_items(table: Table):
    for r, row in enumerate(table.rows, 1):
        for c, text in enumerate(row, 1):
            yield text, f"{table.at}/r:{r}/c:{c}"


def block_items(blocks) -> list:
    """[(글, locator)] — 문단 글과 표 칸 글, 본문 순서. scope 비교·분량 셈에 씁니다."""
    items = []
    for b in blocks:
        if isinstance(b, Para):
            items.append((b.text.strip(), b.loc))
        else:
            items.extend(cell_items(b))
    return items


def search_items(blocks) -> list:
    """[(글, locator)] — 찾기용. 표는 칸 글에 더해 안쪽 표 글까지."""
    items = block_items(blocks)
    for b in blocks:
        if isinstance(b, Table):
            items.extend((t, b.at) for t in b.texts)
    return items


def doc_search_items(doc: Doc) -> list:
    return search_items(doc.blocks) + [(t, None) for t in doc.extra]


def first_last(table: Table) -> tuple[str, str]:
    """profile_extract.py tables와 같은 규칙: 40자 자름, 빈 끝 칸은 그 행의 마지막 빈 아닌 칸."""
    if not table.rows or not table.rows[0]:
        return "", ""
    first = table.rows[0][0].strip()[:40]
    last_row = [t.strip() for t in table.rows[-1]]
    last = next((t for t in reversed(last_row) if t), "")
    return first, last[:40]


# --- DOCX ------------------------------------------------------------------------

def _qn(tag: str) -> str:
    from docx.oxml.ns import qn
    return qn(tag)


def _on(el) -> bool | None:
    if el is None:
        return None
    return el.get(_qn("w:val"), "true") not in ("0", "false", "off")


def _rpr_vals(rpr) -> tuple:
    """rPr 요소에서 (서체, 크기, 굵기). 없는 값은 None."""
    if rpr is None:
        return None, None, None
    rf = rpr.find(_qn("w:rFonts"))
    font = None
    if rf is not None:
        font = rf.get(_qn("w:eastAsia")) or rf.get(_qn("w:ascii"))
    sz = rpr.find(_qn("w:sz"))
    pt = int(sz.get(_qn("w:val"))) / 2 if sz is not None and sz.get(_qn("w:val")) else None
    return font, pt, _on(rpr.find(_qn("w:b")))


def _rpr_direct(rpr) -> tuple:
    """R5용 run 직접 값: (서체 이름들, 크기, 색)."""
    if rpr is None:
        return (), None, None
    rf = rpr.find(_qn("w:rFonts"))
    fonts = ()
    if rf is not None:
        keys = ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs")
        fonts = tuple(dict.fromkeys(v for k in keys if (v := rf.get(_qn(k)))))
    _, pt, _ = _rpr_vals(rpr)
    col = rpr.find(_qn("w:color"))
    val = col.get(_qn("w:val")) if col is not None else None
    color = f"#{val.upper()}" if val and val.lower() != "auto" else None
    return fonts, pt, color


def _style_layers(style) -> list:
    layers = []
    while style is not None:
        layers.append(style.element.find(_qn("w:rPr")))
        style = style.base_style
    return layers


def _merge(layers: list) -> tuple:
    vals = [None, None, None]
    for rpr in layers:
        for i, v in enumerate(_rpr_vals(rpr)):
            if vals[i] is None and v is not None:
                vals[i] = v
    if vals[2] is None:
        vals[2] = False
    return tuple(vals)


def _docx_heading(name: str | None) -> str | None:
    if not name:
        return None
    m = re.fullmatch(r"(?:Heading|heading|제목)\s*(\d)", name)
    if m:
        return f"h{m.group(1)}"
    return "title" if name in ("Title", "제목") else None


def _docx_para(p, loc: str | None, defaults) -> Para:
    style = p.style
    name = style.name if style is not None else None
    layers = _style_layers(style) + [defaults]
    runs = []
    for r in p.runs:
        rpr = r._element.rPr
        fonts, pt, color = _rpr_direct(rpr)
        runs.append(Run(r.text, fonts, pt, color, _merge([rpr] + layers)))
    indent = p.paragraph_format.left_indent
    return Para(p.text, loc, name, (name, indent), _docx_heading(name), runs)


def _docx_header(table, defaults) -> tuple:
    from docx.text.paragraph import Paragraph

    tr = table._tbl.tr_lst[0]
    bolds, fills = set(), set()
    for tc in tr.iterchildren(_qn("w:tc")):
        shd = tc.find(f"{_qn('w:tcPr')}/{_qn('w:shd')}")
        fill = shd.get(_qn("w:fill")) if shd is not None else None
        fills.add((fill or "none").upper())
        for p in tc.iterchildren(_qn("w:p")):
            para = _docx_para(Paragraph(p, table._parent), None, defaults)
            bolds.update(bool(r.eff[2]) for r in para.runs if r.text.strip())
    return tuple(sorted(bolds)), tuple(sorted(fills))


def _docx_table(table, at: str, defaults) -> Table:
    from docx.text.paragraph import Paragraph

    rows = [[c.text.strip() for c in row.cells] for row in table.rows]
    paras = [_docx_para(Paragraph(p, table._parent), at, defaults) for p in table._tbl.iter(_qn("w:p"))]
    header = _docx_header(table, defaults) if rows else None
    return Table(at, rows, [p.text for p in paras], paras, header)


def read_docx(path: Path) -> Doc:
    from docx import Document
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    defaults = doc.styles.element.find(f"{_qn('w:docDefaults')}/{_qn('w:rPrDefault')}/{_qn('w:rPr')}")
    blocks, pn, tn = [], 0, 0
    for item in doc.iter_inner_content():
        if isinstance(item, DocxTable):
            tn += 1
            blocks.append(_docx_table(item, f"t:{tn}", defaults))
        else:
            pn += 1
            blocks.append(_docx_para(item, f"p:{pn}", defaults))
    body = doc.element.body
    extra = [Paragraph(p, doc._body).text for box in body.iter(_qn("w:txbxContent"))
             for p in box.iter(_qn("w:p"))]
    out = Doc("docx", blocks, extra)
    out.styles = [(p.style, p.loc) for p in all_paras(out) if p.style]
    return out


# --- PPTX ------------------------------------------------------------------------

def _walk_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk_shapes(sh.shapes)
        else:
            yield sh


def _pptx_theme_fonts(prs) -> dict:
    """첫 슬라이드 마스터 테마의 `+mj-lt`·`+mj-ea`·`+mn-lt`·`+mn-ea` → 실제 서체 이름.

    프로파일 추출(_pe_pptx_design.theme_fonts)과 같은 규칙이라야 R5가 같은 이름끼리 비교합니다."""
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    try:
        part = prs.slide_masters[0].part.part_related_by(RT.THEME)
        theme = etree.fromstring(part.blob, safe_parser())
    except (KeyError, IndexError, etree.XMLSyntaxError):
        return {}
    out = {}
    for prefix, tag in (("+mj", "majorFont"), ("+mn", "minorFont")):
        for script, child in (("lt", "latin"), ("ea", "ea"), ("cs", "cs")):
            found = theme.findall(f".//{A_NS}{tag}/{A_NS}{child}")
            face = found[0].get("typeface", "") if found else ""
            if face:
                out[f"{prefix}-{script}"] = face
    return out


def _pptx_run(run, theme: dict | None = None) -> Run:
    from pptx.enum.dml import MSO_COLOR_TYPE

    theme = theme or {}
    f = run.font
    fonts = [f.name] if f.name else []
    rpr = run._r.find(f"{A_NS}rPr")
    if rpr is not None:
        for tag in ("ea", "cs"):
            el = rpr.find(f"{A_NS}{tag}")
            if el is not None and el.get("typeface"):
                fonts.append(el.get("typeface"))
    # 테마 서체 참조(+mn-ea 등)는 실제 이름으로 바꿉니다. 풀 수 없는 참조는 비교에서 뺍니다.
    fonts = [theme.get(x, "") if x.startswith("+") else x for x in fonts]
    fonts = [x for x in fonts if x]
    pt = f.size.pt if f.size is not None else None
    color = None
    if f.color is not None and f.color.type == MSO_COLOR_TYPE.RGB:
        color = f"#{str(f.color.rgb).upper()}"
    fonts = tuple(dict.fromkeys(fonts))
    return Run(run.text, fonts, pt, color, (fonts[0] if fonts else None, pt, f.bold))


def _pptx_heading(shape) -> str | None:
    from pptx.enum.shapes import PP_PLACEHOLDER

    if not shape.is_placeholder:
        return None
    kind = shape.placeholder_format.type
    if kind == PP_PLACEHOLDER.CENTER_TITLE:
        return "title"
    return "h1" if kind == PP_PLACEHOLDER.TITLE else None


def _pptx_paras(shape, sn: int, theme: dict) -> list:
    if shape.is_placeholder:
        base = f"sl:{sn}/ph:{shape.placeholder_format.idx}"
    else:
        base = f"sl:{sn}/sh:{shape.shape_id}"
    heading = _pptx_heading(shape)
    out = []
    for k, p in enumerate(shape.text_frame.paragraphs, 1):
        runs = [_pptx_run(r, theme) for r in p.runs]
        # p.text는 a:fld(슬라이드 번호·날짜 필드) 글도 담습니다.
        out.append(Para(p.text, f"{base}/p:{k}", None, ("lvl", p.level), heading, runs, sn))
    return out


A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _pptx_header(table) -> tuple:
    bolds, fills = set(), set()
    for cell in table.rows[0].cells:
        clr = cell._tc.find(f"{A_NS}tcPr/{A_NS}solidFill/{A_NS}srgbClr")
        fills.add((clr.get("val") if clr is not None else "none").upper())
        for p in cell.text_frame.paragraphs:
            bolds.update(bool(r.font.bold) for r in p.runs if r.text.strip())
    return tuple(sorted(bolds)), tuple(sorted(fills))


def _pptx_table(shape, sn: int, at: str, theme: dict) -> Table:
    table = shape.table
    rows, paras = [], []
    for row in table.rows:
        rows.append([c.text.strip() for c in row.cells])
        for c in row.cells:
            for p in c.text_frame.paragraphs:
                runs = [_pptx_run(r, theme) for r in p.runs]
                paras.append(Para(p.text, at, None, ("lvl", p.level), None, runs, sn))
    header = _pptx_header(table) if rows else None
    return Table(at, rows, [p.text for p in paras], paras, header, sn, f"sl:{sn}/sh:{shape.shape_id}")


def read_pptx(path: Path) -> Doc:
    from pptx import Presentation

    prs = Presentation(str(path))
    theme = _pptx_theme_fonts(prs)
    blocks, styles, anchors, tn = [], [], [], 0
    for sn, slide in enumerate(prs.slides, 1):
        styles.append((slide.slide_layout.name, f"sl:{sn}"))
        title = slide.shapes.title
        for shape in _walk_shapes(slide.shapes):
            if getattr(shape, "has_table", False) and shape.has_table:
                tn += 1
                blocks.append(_pptx_table(shape, sn, f"t:{tn}", theme))
            elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                if title is not None and shape.shape_id == title.shape_id:
                    # h:"…" anchor는 슬라이드 제목 글입니다 (_pe_pptx.heading_texts와 같은 대상).
                    # 원래 글은 신규 모드 장 번호 빼기용 — 여러 문단 제목은 첫 블록 글과 다릅니다.
                    anchors.append((nows(title.text_frame.text), len(blocks), title.text_frame.text))
                blocks.extend(_pptx_paras(shape, sn, theme))
    return Doc("pptx", blocks, [], styles, None, len(prs.slides), anchors,
               tuple(s.slide_id for s in prs.slides))


# --- MD --------------------------------------------------------------------------

# 규칙은 프로파일 추출(_pe_md)과 같아야 anchor·표 번호·칸 글이 맞습니다.
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
MD_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
MD_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _md_cells(line: str) -> list:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [_md_inline(c) for c in re.split(r"(?<!\\)\|", body)]


def _md_inline(text: str) -> str:
    """_pe_md.strip_inline과 같은 정리: 굵게·밑줄 굵게·코드 표시를 빼고 공백을 한 칸으로."""
    return WS.sub(" ", re.sub(r"\*\*|__|`", "", text.replace("\\|", "|"))).strip()


def _md_front_matter_end(lines: list) -> int:
    """앞머리(--- … ---)가 있으면 그 다음 줄 번호, 없으면 0."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return i + 1
    return 0


def _md_table(lines: list, i: int) -> int:
    """i에서 파이프 표가 시작하면 표 끝(다음 줄 번호)을, 아니면 i를 돌려줍니다."""
    if i + 1 >= len(lines) or "|" not in lines[i] or not MD_DELIM.match(lines[i + 1]):
        return i
    if "|" not in lines[i + 1] or len(_md_cells(lines[i + 1])) != len(_md_cells(lines[i])):
        return i
    j = i + 2
    while j < len(lines) and "|" in lines[j] and lines[j].strip() and not FENCE.match(lines[j]):
        j += 1
    return j


def _md_para(line: str) -> Para:
    m = MD_HEADING.match(line)
    if m:
        text = _md_inline(m.group(2))
        return Para(text, None, None, ("h", len(m.group(1))), f"h{len(m.group(1))}")
    indent = len(line) - len(line.lstrip(" "))
    return Para(line.strip(), None, None, ("indent", indent))


def read_md(path: Path) -> Doc:
    lines = path.read_text(encoding="utf-8").splitlines()
    i = _md_front_matter_end(lines)
    blocks, extra, fence, tn = [], list(lines[:i]), None, 0
    while i < len(lines):
        line = lines[i]
        if m := FENCE.match(line):
            mark = m.group(1)[0]
            fence = mark if fence is None else (None if fence == mark else fence)
        elif fence is not None:
            extra.append(line)
        elif (end := _md_table(lines, i)) > i:
            tn += 1
            rows = [_md_cells(lines[i])] + [_md_cells(x) for x in lines[i + 2:end]]
            blocks.append(Table(f"t:{tn}", rows, [c for r in rows for c in r]))
            i = end
            continue
        elif line.strip():
            blocks.append(_md_para(line))
        i += 1
    anchors = [(nows(b.text), k) for k, b in enumerate(blocks) if isinstance(b, Para) and b.heading]
    return Doc("md", blocks, extra, anchors=anchors)


# --- HWPX ------------------------------------------------------------------------

def _nearest(el, tag: str):
    el = el.getparent()
    while el is not None and el.tag != tag:
        el = el.getparent()
    return el


HWPX_SKIP = (f"{HP}header", f"{HP}footer")


def _in_header_footer(el) -> bool:
    return any(a.tag in HWPX_SKIP for a in el.iterancestors())


def _hwpx_ptext(p) -> str:
    return "".join("".join(t.itertext()) for t in p.iter(f"{HP}t") if _nearest(t, f"{HP}p") is p)


def _hwpx_header_maps(zf: zipfile.ZipFile) -> tuple[dict, dict]:
    """header.xml에서 글자 모양 id → 굵기, 테두리·배경 id → 바탕색."""
    from lxml import etree

    bold, fill = {}, {}
    try:
        root = etree.fromstring(zf.read("Contents/header.xml"), safe_parser())
    except KeyError:
        return bold, fill
    for el in root.iter():
        name = etree.QName(el).localname if isinstance(el.tag, str) else ""
        if name == "charPr":
            bold[el.get("id")] = any(etree.QName(c).localname == "bold" for c in el if isinstance(c.tag, str))
        elif name == "borderFill":
            brush = next((c for c in el.iter() if isinstance(c.tag, str)
                          and etree.QName(c).localname == "winBrush"), None)
            fill[el.get("id")] = (brush.get("faceColor") if brush is not None else "none") or "none"
    return bold, fill


def _hwpx_table(tbl, at: str, maps: tuple) -> Table:
    rows = []
    for tr in tbl.findall(f"{HP}tr"):
        row = []
        for tc in tr.findall(f"{HP}tc"):
            texts = [_hwpx_ptext(p) for p in tc.iter(f"{HP}p") if _nearest(p, f"{HP}tbl") is tbl]
            row.append("\n".join(texts).strip())
        rows.append(row)
    texts = [_hwpx_ptext(p) for p in tbl.iter(f"{HP}p")]
    paras = [Para(t, at, None, ("para", p.get("paraPrIDRef"))) for t, p in zip(texts, tbl.iter(f"{HP}p"))]
    return Table(at, rows, texts, paras, _hwpx_header(tbl, maps) if rows else None)


def _hwpx_header(tbl, maps: tuple) -> tuple:
    bold_map, fill_map = maps
    tr = tbl.find(f"{HP}tr")
    bolds, fills = set(), set()
    for tc in tr.findall(f"{HP}tc"):
        fills.add(str(fill_map.get(tc.get("borderFillIDRef"), "none")).upper())
        for run in tc.iter(f"{HP}run"):
            if _nearest(run, f"{HP}tbl") is tbl and "".join(run.itertext()).strip():
                bolds.add(bool(bold_map.get(run.get("charPrIDRef"))))
    return tuple(sorted(bolds)), tuple(sorted(fills))


def _section_names(zf: zipfile.ZipFile) -> list:
    names = [n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    return sorted(names, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))


def read_hwpx(path: Path) -> Doc:
    from lxml import etree

    blocks, extra, anchors, chars, paras, tn = [], [], [], set(), set(), 0
    with zipfile.ZipFile(path) as zf:
        maps = _hwpx_header_maps(zf)
        for name in _section_names(zf):
            root = etree.fromstring(zf.read(name), safe_parser())
            chars.update(r.get("charPrIDRef") for r in root.iter(f"{HP}run"))
            paras.update(p.get("paraPrIDRef") for p in root.iter(f"{HP}p"))
            extra.extend(_hwpx_ptext(p) for p in root.iter(f"{HP}p"))
            for p in root.iterchildren(f"{HP}p"):
                tn = _hwpx_top_para(p, blocks, anchors, tn, maps)
    return Doc("hwpx", blocks, extra, [], (chars - {None}, paras - {None}), None, anchors)


def _hwpx_top_para(p, blocks: list, anchors: list, tn: int, maps: tuple) -> int:
    """최상위 문단 하나와 그 안의 최상위 표를 블록으로 넣고, 마지막 표 번호를 돌려줍니다.

    머리말·꼬리말 안의 표는 본문 표가 아니므로 뺍니다(_pe_hwpx.top_level_tables와 같은 규칙).
    anchor 대상은 머리말·꼬리말 밖의 모든 hp:p(표 칸 안 문단 포함)이고, 그 문단을 담은
    블록 번호로 이어 줍니다 — 띠 표(한 줄 표) 안 제목도 섹션 시작이 됩니다."""
    tbl_tag = f"{HP}tbl"
    para_idx = len(blocks)
    blocks.append(Para(_hwpx_ptext(p), None, None, ("para", p.get("paraPrIDRef"))))
    owner = {}
    for tbl in p.iter(tbl_tag):
        if _nearest(tbl, tbl_tag) is None and not _in_header_footer(tbl):
            tn += 1
            owner[tbl] = len(blocks)
            blocks.append(_hwpx_table(tbl, f"t:{tn}", maps))
    for q in p.iter(f"{HP}p"):
        if _in_header_footer(q):
            continue
        top = next((a for a in reversed(list(q.iterancestors(tbl_tag))) if a in owner), None)
        text = _hwpx_ptext(q)  # 표 안 문단은 블록이 Table이라 원래 글을 따로 적어 둡니다
        anchors.append((nows(text), owner[top] if top is not None else para_idx, text))
    return tn
