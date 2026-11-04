"""doc_verify.py locator 풀기 — 설계서 §5 「locator 문법」.

- 섹션 범위: 견본에서 anchor 문단 글을 얻고, 결과에서 같은 글(공백 무시)의 문단을 찾아
  그 블록부터 다음 섹션 시작 블록 앞까지입니다.
- 칸: `t:N/r:R/c:C` (모든 형식), `sl:N/sh:K/t/r:R/c:C` (PPTX).
- 문단: `p:N` (DOCX), `sl:N`·`sl:N/ph:K`·`sl:N/ph:K/p:M`·`sl:N/sh:K/p:M` (PPTX).
"""
import re

from _readers import Doc, Para, nows, search_items

CELL = re.compile(r"t:(\d+)/r:(\d+)/c:(\d+)")
SHAPE_CELL = re.compile(r"(sl:\d+/sh:\d+)/t/r:(\d+)/c:(\d+)")
HEADING = re.compile(r'h:"(.*)"(?:#(\d+))?')
SECTION_ID = re.compile(r"s\d+")
FIELD_ID = re.compile(r"f\d+")


def _cell(table, r: int, c: int) -> str | None:
    if 1 <= r <= len(table.rows) and 1 <= c <= len(table.rows[r - 1]):
        return table.rows[r - 1][c - 1]
    return None


def cell_text(doc: Doc, loc: str) -> str | None:
    m = CELL.fullmatch(loc)
    if m:
        n, r, c = map(int, m.groups())
        tables = doc.tables
        return _cell(tables[n - 1], r, c) if 1 <= n <= len(tables) else None
    m = SHAPE_CELL.fullmatch(loc)
    if m:
        table = next((t for t in doc.tables if t.alias == m.group(1)), None)
        return _cell(table, int(m.group(2)), int(m.group(3))) if table else None
    return None


def para_text(doc: Doc, loc: str) -> str | None:
    """DOCX `p:N`과 PPTX `sl:…` 문단 locator. 여러 문단이면 줄바꿈으로 잇습니다."""
    if doc.fmt == "docx" and re.fullmatch(r"p:\d+", loc):
        return next((p.text for p in doc.paras if p.loc == loc), None)
    if doc.fmt == "pptx" and re.fullmatch(r"sl:\d+(/(ph|sh):\d+(/p:\d+)?)?", loc):
        hits = [p.text for p in doc.paras if p.loc == loc or p.loc.startswith(loc + "/")]
        return "\n".join(hits) if hits else None
    return None


def field_text(doc: Doc, loc: str | None) -> str | None:
    if not loc:
        return None
    text = cell_text(doc, loc)
    return text if text is not None else para_text(doc, loc)


# --- 섹션 ------------------------------------------------------------------------

def anchor_items(doc: Doc) -> list:
    """h:"…" anchor 대상 [(공백 뺀 글, 블록 번호)] — 프로파일 추출의 heading_texts와 같은 대상.

    Doc.anchors가 없으면(DOCX) 최상위 문단입니다."""
    if doc.anchors is not None:
        return doc.anchors
    return [(nows(b.text), i) for i, b in enumerate(doc.blocks) if isinstance(b, Para)]


def _occurrence(items: list, key: str, idx: int) -> int:
    n = 0
    for text, i in items:
        if text == key:
            n += 1
            if i == idx:
                return n
    return 0


def anchor_key(src: Doc, anchor) -> tuple[str, int] | None:
    """글 anchor(`h:"…"#N`·DOCX `p:N`)를 (공백 뺀 글, 몇 번째)로 바꿉니다. 풀 수 없으면 None.

    PPTX `sl:N`은 글이 아니라 슬라이드 번호로 찾으므로 여기서 다루지 않습니다(slide_anchor)."""
    if not isinstance(anchor, str):
        return None
    m = HEADING.fullmatch(anchor.strip())
    if m:
        return nows(m.group(1)), int(m.group(2) or 1)
    if src.fmt != "docx" or not re.fullmatch(r"p:\d+", anchor):
        return None
    idx = next((i for i, b in enumerate(src.blocks) if isinstance(b, Para) and b.loc == anchor), None)
    if idx is None or not nows(src.blocks[idx].text):
        return None
    key = nows(src.blocks[idx].text)
    return key, _occurrence(anchor_items(src), key, idx)


def slide_anchor(doc: Doc, src: Doc, anchor) -> int | None:
    """PPTX `sl:N` → 결과 슬라이드 번호. 슬라이드 anchor가 아니면 None, 결과에 없으면 0.

    견본 N번 슬라이드의 id(p:sldId)를 결과에서 찾습니다. 그래서 제목 글이 바뀌어도, slide_dup·
    slide_delete로 앞 슬라이드가 늘거나 줄어도 섹션이 밀리지 않습니다(종단 시험 F8). 견본 id가
    결과에 하나도 없으면(다른 프로그램이 다시 저장해 id를 새로 매김) 자리 N으로 찾습니다."""
    if doc.fmt != "pptx" or not isinstance(anchor, str):
        return None
    m = re.fullmatch(r"sl:(\d+)", anchor.strip())
    if not m:
        return None
    n = int(m.group(1))
    if not set(src.slide_ids) & set(doc.slide_ids):
        return n
    sid = src.slide_ids[n - 1] if n <= len(src.slide_ids) else None
    return doc.slide_ids.index(sid) + 1 if sid in doc.slide_ids else 0


def find_para(doc: Doc, key: str, occ: int, start: int) -> int | None:
    """key 글의 occ번째 anchor 대상을 담은 블록 번호. start 앞이면 None."""
    n = 0
    for text, i in anchor_items(doc):
        if text == key:
            n += 1
            if n == occ:
                return i if i >= start else None
    return None


def find_slide(doc: Doc, sn: int, start: int) -> int | None:
    """슬라이드 sn의 첫 블록 번호. 블록이 없거나 start 앞이면 None."""
    idx = next((i for i, b in enumerate(doc.blocks) if getattr(b, "slide", None) == sn), None)
    return idx if idx is not None and idx >= start else None


def section_starts(doc: Doc, src: Doc, sections: list) -> list:
    starts, prev = [], 0
    for s in sections:
        sn = slide_anchor(doc, src, s.get("anchor"))
        if sn is not None:
            idx = find_slide(doc, sn, prev)
        else:
            key = anchor_key(src, s.get("anchor"))
            idx = find_para(doc, key[0], key[1], prev) if key else None
        starts.append(idx)
        if idx is not None:
            prev = idx
    return starts


def section_ranges(doc: Doc, src: Doc, sections: list) -> dict:
    """{섹션 id: (시작 블록, 끝 블록) | None}과 첫 섹션 시작 블록."""
    starts = section_starts(doc, src, sections)
    resolved = sorted(i for i in starts if i is not None)
    ranges = {}
    for s, idx in zip(sections, starts):
        if idx is None:
            ranges[s.get("id")] = None
            continue
        end = next((j for j in resolved if j > idx), len(doc.blocks))
        ranges[s.get("id")] = (idx, end)
    first = resolved[0] if resolved else len(doc.blocks)
    return {"ranges": ranges, "first": first}


def sections_of(profile: dict) -> list:
    secs = (profile.get("structure") or {}).get("sections") or []
    return [s for s in secs if isinstance(s, dict)]


def field_of(profile: dict, fid: str) -> dict | None:
    return next((f for f in profile.get("fields") or [] if isinstance(f, dict) and f.get("id") == fid), None)


def scope_texts(out: Doc, src: Doc, profile: dict, loc) -> tuple[list, str | None]:
    """자리표시를 찾을 글 목록과 범위 설명. 풀 수 없거나 dump locator면 문서 전체."""
    whole = [t for t, _ in search_items(out.blocks)] + list(out.extra)
    loc = str(loc or "").strip()
    if SECTION_ID.fullmatch(loc):
        rng = section_ranges(out, src, sections_of(profile))["ranges"].get(loc)
        if rng:
            return [t for t, _ in search_items(out.blocks[rng[0]:rng[1]])], loc
        return whole, None
    if FIELD_ID.fullmatch(loc):
        field = field_of(profile, loc)
        loc = str((field or {}).get("locator") or "")
    text = cell_text(out, loc) if loc else None
    if text is not None:
        return [text], loc
    return whole, None
