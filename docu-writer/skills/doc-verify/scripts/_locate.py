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
# 신규 모드 제목 앞 글머리표·장 번호 — 「□」「○」 뒤 「Ⅰ.」「1.」「1)」「가.」「가)」와 점 없는 꼴
# (SKILL.md 「신규 모드」). 글머리표와 점·괄호가 없는 숫자·한글 번호는 뒤에 공백이 있을 때만 뺍니다
# (「○○사업」·「12개월」·「가나다」를 자르지 않음).
# 제목 스타일이 없는 문서(HWPX)는 항목 제목 표지(□ 등)만 뺍니다 — ○·•는 본문 목록 줄에도 붙어
# 「○ 현황」 본문 줄이 h:"현황" 섹션 시작으로 잡힙니다(리뷰 3차 H3 재검토, agy).
HEAD_BULLETS = "□■◆◇▶▷"
LIST_BULLETS = "○●◎•▪"
NUMBER = r"(?:[Ⅰ-Ⅹ][.)]?|(?:\d{1,2}|[가나다라마바사아자차카타파하])(?:[.)]|(?=\s)))\s*"
CHAPTER = re.compile(rf"\s*(?:[{HEAD_BULLETS}{LIST_BULLETS}]\s+)?(?:{NUMBER})?")
HEAD_CHAPTER = re.compile(rf"\s*(?:[{HEAD_BULLETS}]\s+)?(?:{NUMBER})?")


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
        return [(a[0], a[1]) for a in doc.anchors]
    return [(nows(b.text), i) for i, b in enumerate(doc.blocks) if isinstance(b, Para)]


def chapter_stripped(text: str, pattern: re.Pattern = CHAPTER) -> str:
    """앞 글머리표·장 번호를 뺀 공백 없는 글. 없거나 빼면 아무 글도 남지 않으면 그대로."""
    m = pattern.match(text or "")
    rest = nows(text[m.end():]) if m and m.end() else ""
    return rest or nows(text)


def _raw_text(doc: Doc, k: int, text: str, i: int) -> str:
    """k번째 anchor의 공백을 빼기 전 글. 리더가 적어 둔 원래 글(표 안 문단·여러 줄 제목)을
    먼저 쓰고, 없으면 그 블록 문단 글, 그것도 맞지 않으면 공백 뺀 글 그대로입니다."""
    if doc.anchors is not None and len(doc.anchors[k]) > 2:
        return doc.anchors[k][2]
    block = doc.blocks[i] if 0 <= i < len(doc.blocks) else None
    return block.text if isinstance(block, Para) and nows(block.text) == text else text


def _heading_of(doc: Doc, i: int) -> str | None:
    block = doc.blocks[i] if 0 <= i < len(doc.blocks) else None
    return block.heading if isinstance(block, Para) else None


def _loose_matches(doc: Doc, key: str) -> list:
    """신규 모드에서 key와 맞는 anchor 대상의 블록 번호들(문서 순서).

    맞는다 = 공백 뺀 글이 같거나, 원래 글에서 앞 글머리표·장 번호를 뺀 글이 같음(점 없는
    「1 추진 배경」은 뒤 공백으로만 번호임을 알므로 공백을 빼기 전 글로 봅니다).

    결과에 제목 스타일 문단(Heading N)이 있으면 글마다 정합니다 (리뷰 3차 H3 재검토, agy·codex):
    - 제목(Heading N·Title) 가운데 맞는 것이 있으면 제목만 셉니다 — 목차·요약 줄 「1. 추진 배경」
      이나 본문 「○ 현황」이 섹션 시작을 가로채 앞 섹션이 잘리면 분량 초과가 숨습니다.
    - 없으면 일반 문단을 글이 똑같을 때만 셉니다(번호·글머리표를 빼고 맞추지 않음) — 제목을
      일반 스타일로 쓴 섹션도 찾되, 제목을 고친 섹션이 본문 「○ 현황」에 잡히지는 않습니다.
    제목 스타일이 없는 문서(HWPX 등)는 모든 문단이 대상이고 항목 제목 표지(□■◆◇▶▷)만 뺍니다."""
    items = [(text, i, _raw_text(doc, k, text, i)) for k, (text, i) in enumerate(anchor_items(doc))]
    styled = any((_heading_of(doc, i) or "").startswith("h") for _, i, _ in items)
    pattern = CHAPTER if styled or doc.fmt in ("md", "pptx") else HEAD_CHAPTER

    def hit(text, raw):
        return text == key or chapter_stripped(raw, pattern) == key

    if not styled:
        return [i for text, i, raw in items if hit(text, raw)]
    heads = [i for text, i, raw in items if _heading_of(doc, i) and hit(text, raw)]
    return heads or [i for text, i, _ in items if text == key]


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


def _slide_no(anchor) -> int | None:
    m = re.fullmatch(r"sl:(\d+)", anchor.strip()) if isinstance(anchor, str) else None
    return int(m.group(1)) if m else None


def slide_candidates(doc: Doc, src: Doc, anchor, last: int | None = None) -> list | None:
    """PPTX `sl:N` → 섹션 시작 후보 결과 슬라이드 번호들(결과 순서). 슬라이드 anchor가 아니면 None.

    견본 N번 슬라이드의 id(p:sldId)를 결과에서 찾습니다. 그래서 제목 글이 바뀌어도, slide_dup·
    slide_delete로 앞 슬라이드가 늘거나 줄어도 섹션이 밀리지 않습니다(종단 시험 F8). 견본 id가
    결과에 하나도 없으면(다른 프로그램이 다시 저장해 id를 새로 매김) 자리 N으로 찾습니다.

    last(견본 슬라이드 번호)를 주면 N…last 가운데 결과에 남은 장을 모두 후보로 내고, 결과에서
    앞선 장부터 놓습니다 — 섹션 첫 장을 지우거나 섹션 안 순서를 바꿔도 그 섹션의 남은 장이
    시작이 됩니다(리뷰 3차 M3). 하나도 없거나 N < 1이면 빈 목록입니다."""
    if doc.fmt != "pptx":
        return None
    n = _slide_no(anchor)
    if n is None:
        return None
    if n < 1:
        return []
    if not set(src.slide_ids) & set(doc.slide_ids):
        return [n] if n <= len(doc.slide_ids) else []
    span = src.slide_ids[n - 1:min(max(last or n, n), len(src.slide_ids))]
    return sorted(doc.slide_ids.index(sid) + 1 for sid in span if sid in doc.slide_ids)


def slide_anchor(doc: Doc, src: Doc, anchor, last: int | None = None) -> int | None:
    """PPTX `sl:N` → 결과 슬라이드 번호(slide_candidates의 첫 후보). 아니면 None, 없으면 0."""
    found = slide_candidates(doc, src, anchor, last)
    return None if found is None else (found[0] if found else 0)


def _find_para(doc: Doc, key: str, occ: int, start: int, loose: bool = False) -> tuple[int | None, bool]:
    """(블록 번호 | None, 뒤로 찾았나). find_para 참고."""
    matches = _loose_matches(doc, key) if loose else [i for t, i in anchor_items(doc) if t == key]
    for n, i in enumerate(matches, 1):
        if n == occ:
            if i >= start or not loose:
                return (i if i >= start else None), False
        elif n > occ and i >= start:
            return i, True
    return None, False


def find_para(doc: Doc, key: str, occ: int, start: int, loose: bool = False) -> int | None:
    """key 글의 occ번째 anchor 대상을 담은 블록 번호. start 앞이면 None.

    loose(신규 모드)면 글이 같거나, 앞 글머리표·장 번호를 뺀 글이 같은 문단도 맞는 것으로 셉니다.
    결과에 제목 스타일 문단이 있으면 글마다 제목을 먼저 셉니다(_loose_matches).
    그리고 occ번째가 start 앞이면(앞 섹션 제목보다 먼저 나온 요약·목차 줄) None 대신 그 뒤 처음
    맞는 문단을 씁니다 — 결과 문서는 새로 쓴 글이라 앞쪽 같은 글 한 줄 때문에 섹션을 놓치면
    length가 fail 대신 skip이 됩니다(리뷰 3차 H3). 이렇게 뒤로 찾은 문단은 제목이 아닌 본문 줄일 수
    있어 앞 섹션 끝으로 쓰지 않습니다(section_ranges). 갱신 모드는 순서가 어긋나면 None 그대로입니다."""
    return _find_para(doc, key, occ, start, loose)[0]


def find_slide(doc: Doc, sn: int, start: int) -> int | None:
    """슬라이드 sn의 첫 블록 번호. 블록이 없거나 start 앞이면 None."""
    idx = next((i for i, b in enumerate(doc.blocks) if getattr(b, "slide", None) == sn), None)
    return idx if idx is not None and idx >= start else None


def _source_slide(src: Doc, anchor) -> int | None:
    """섹션 anchor가 견본에서 시작하는 슬라이드 번호. `sl:N`은 N, 글 anchor는 그 문단의 장."""
    n = _slide_no(anchor)
    if n is not None:
        return n
    key = anchor_key(src, anchor)
    idx = find_para(src, key[0], key[1], 0) if key else None
    return getattr(src.blocks[idx], "slide", None) if idx is not None and 0 <= idx < len(src.blocks) else None


def _first_gone(doc: Doc, src: Doc, n: int) -> bool:
    """견본 n번 슬라이드가 결과에서 지워졌나. id로 볼 수 없으면(id를 새로 매김) False."""
    shared = set(src.slide_ids) & set(doc.slide_ids)
    return bool(shared) and 1 <= n <= len(src.slide_ids) and src.slide_ids[n - 1] not in shared


def _section_last_slides(doc: Doc, src: Doc, sections: list, editable: set | None = None) -> list:
    """섹션마다 견본에서 그 섹션이 차지하는 마지막 슬라이드 번호(다른 섹션 시작 앞 장).

    다른 섹션은 anchor 종류(`sl:`·`h:`)와 목록 순서에 관계없이 견본 시작 장으로 셉니다 — 다음
    섹션의 장을 이 섹션 대체 시작으로 쓰면 지운 보호 섹션이 통과합니다(리뷰 3차 M3 재검토).
    슬라이드 anchor가 아닌 섹션은 None이고, 그 섹션은 첫 장이 지워지면 찾지 못함입니다.

    editable(갱신 모드 scope의 update.sections)을 주면 그 밖 섹션은 첫 장이 결과에 남았을 때만
    span을 씁니다(첫 장이 글 없는 장일 때). 첫 장을 지운 보호 섹션이 남은 장으로 풀려 scope를
    통과하면 안 됩니다(리뷰 3차 M3 재검토, agy) — 그때 마지막 장은 0이라 후보가 없습니다."""
    if src.fmt != "pptx":
        return [None] * len(sections)
    firsts = [_source_slide(src, s.get("anchor")) for s in sections]
    lasts = []
    for s, n in zip(sections, firsts):
        if _slide_no(s.get("anchor")) is None or n is None:
            lasts.append(None)
            continue
        if editable is not None and str(s.get("id")) not in editable and _first_gone(doc, src, n):
            lasts.append(0)
            continue
        after = [m for m in firsts if m is not None and m > n]
        lasts.append(min(after) - 1 if after else len(src.slide_ids))
    return lasts


def _section_starts(doc: Doc, src: Doc, sections: list, loose: bool = False,
                    editable: set | None = None) -> list:
    """[(시작 블록 | None, 뒤로 찾았나)] — 섹션 순서대로. editable은 _section_last_slides 참고."""
    starts, prev = [], 0
    for s, last in zip(sections, _section_last_slides(doc, src, sections, editable)):
        found = slide_candidates(doc, src, s.get("anchor"), last)
        forward = False
        if found is not None:
            # 글 없는 장(그림만)은 블록이 없으니 그 섹션의 다음 남은 장으로 넘어갑니다.
            idx = next((i for i in (find_slide(doc, sn, prev) for sn in found) if i is not None), None)
        else:
            key = anchor_key(src, s.get("anchor"))
            idx, forward = _find_para(doc, key[0], key[1], prev, loose) if key else (None, False)
        starts.append((idx, forward))
        if idx is not None:
            prev = idx
    return starts


def section_starts(doc: Doc, src: Doc, sections: list, loose: bool = False) -> list:
    return [idx for idx, _ in _section_starts(doc, src, sections, loose)]


def section_ranges(doc: Doc, src: Doc, sections: list, loose: bool = False,
                   editable: set | None = None) -> dict:
    """{섹션 id: (시작 블록, 끝 블록) | None}과 첫 섹션 시작 블록. loose는 find_para,
    editable(갱신 모드 scope)은 _section_last_slides 참고.

    섹션 끝은 다음 섹션 시작 앞이되, 뒤로 찾은 시작(find_para)은 끝으로 쓰지 않습니다 — 그 줄이
    제목 아닌 본문이면 앞 섹션이 잘려 분량 초과가 숨습니다(리뷰 3차 H3 재검토). 그래서 뒤로 찾은
    섹션이 있으면 앞 섹션 범위는 그 섹션을 못 찾았을 때와 같습니다."""
    starts = _section_starts(doc, src, sections, loose, editable)
    resolved = sorted(i for i, _ in starts if i is not None)
    bounds = sorted(i for i, fwd in starts if i is not None and not fwd)
    ranges = {}
    for s, (idx, _) in zip(sections, starts):
        if idx is None:
            ranges[s.get("id")] = None
            continue
        end = next((j for j in bounds if j > idx), len(doc.blocks))
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
        loose = profile.get("mode") == "new"
        rng = section_ranges(out, src, sections_of(profile), loose)["ranges"].get(loc)
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
