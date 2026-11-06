"""doc_verify.py 내용 검사 — hash·residue·markup·placeholder·fields·scope·length.

계약: skills/doc-verify/SKILL.md 「검사 항목」·「검사 세부」.
각 검사는 Ctx를 받아 {id, status, detail, locations} 하나를 돌려줍니다.
"""
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from _locate import field_text, scope_texts, section_ranges, sections_of
from _readers import Doc, block_items, doc_search_items, nows

CIRCLES = set("○ㅇᄋ◦")


@dataclass
class Ctx:
    profile: dict
    mode: str
    source: Path | None   # mode: new는 None — 견본 없음
    expect: str | None
    output: Path
    src: Doc
    out: Doc
    placeholders: list | None
    pages: list | None
    pages_dir: Path | None


def entry(cid: str, status: str, detail: str, locations=None) -> dict:
    return {"id": cid, "status": status, "detail": detail, "locations": list(locations or [])}


def new_mode_skip(cid: str, why: str) -> dict:
    """mode: new에서 하지 않는 검사 — detail에 「신규 모드」를 적습니다(SKILL.md 「신규 모드」)."""
    return entry(cid, "skip", f"신규 모드 — {why}")


def brief(items: list, limit: int = 3) -> str:
    shown = ", ".join(str(x) for x in items[:limit])
    return shown + (" …" if len(items) > limit else "")


def _unique(items) -> list:
    return list(dict.fromkeys(x for x in items if x))


# --- hash ------------------------------------------------------------------------

def check_hash(ctx: Ctx) -> dict:
    if ctx.mode == "new":
        return new_mode_skip("hash", "견본 없음 (원본 보호는 materials.sha256이 맡음)")
    got = hashlib.sha256(ctx.source.read_bytes()).hexdigest()
    if got == ctx.expect.strip().lower():
        return entry("hash", "pass", "견본 sha256 일치")
    detail = f"견본 sha256 불일치 (기대 {ctx.expect[:12]}…, 실제 {got[:12]}…) — CRITICAL: 원본이 바뀜"
    return entry("hash", "fail", detail)


# --- residue ---------------------------------------------------------------------

def _pages_with(ctx: Ctx, phrase: str) -> list:
    key = nows(phrase)
    return [i for i, text in enumerate(ctx.pages or [], 1) if key in nows(text)]


def check_residue(ctx: Ctx) -> dict:
    if ctx.mode == "new":
        return new_mode_skip("residue", "견본 문구 없음")
    if ctx.mode != "sample":
        return entry("residue", "skip", f"{ctx.mode} 모드는 검사하지 않음")
    raw = [s for s in ctx.profile.get("sample_text") or [] if isinstance(s, str)]
    phrases = [s for s in raw if nows(s) and not set(nows(s)) <= CIRCLES]
    if not phrases:
        return entry("residue", "skip", "sample_text 없음")
    items = doc_search_items(ctx.out)
    hits, locs = [], []
    for phrase in phrases:
        found = [loc for text, loc in items if nows(phrase) in nows(text)]
        if not found:
            continue
        locs.extend(found)
        pages = _pages_with(ctx, phrase)
        hits.append(f'"{phrase}"' + (f" ({pages[0]}쪽)" if pages else ""))
    if hits:
        return entry("residue", "fail", f"{len(hits)}건: {brief(hits)}", _unique(locs))
    return entry("residue", "pass", f"견본 문구 {len(phrases)}개 모두 없음")


# --- markup ----------------------------------------------------------------------

# 편집본 마크다운의 표지가 글자로 새어 든 자리 (종단 시험 F12: kordoc patch_document가
# 요약 상자 글 앞에 「> 」를 그대로 넣음). 견본에 같은 꼴이 있으면 그 종류는 문서의 글로 봅니다.
MARKUP = {
    "인용 >": re.compile(r"^\s*>\s"),
    "제목 #": re.compile(r"^\s*#{1,6}\s"),
    "굵게 **": re.compile(r"\*\*[^*\s][^*]*\*\*|__[^_\s][^_]*__"),
    "탈출 \\": re.compile(r"\\[~*_#>|\[\]`-]"),
    "표 |": re.compile(r"^\s*\|.*\|\s*$"),
}


def _markup_kinds(text: str) -> list:
    return [kind for kind, pattern in MARKUP.items() if pattern.search(text)]


def check_markup(ctx: Ctx) -> dict:
    # 신규 모드는 견본이 없으므로 「견본에 같은 꼴이 있으면 뺀다」 예외 없이 모든 표지를 봅니다.
    # 다만 MD 출력은 마크다운 자체가 출력 형식이라 표지가 모두 정상 문법이므로 보지 않습니다.
    if ctx.mode == "new" and ctx.out.fmt == "md":
        return new_mode_skip("markup", "MD 출력은 마크다운이 곧 형식")
    known = set() if ctx.mode == "new" else {
        kind for text, _ in doc_search_items(ctx.src) for kind in _markup_kinds(text)}
    hits, locs = [], []
    for text, loc in doc_search_items(ctx.out):
        kinds = [k for k in _markup_kinds(text) if k not in known]
        hit = kinds and f'{kinds[0]} "{text.strip()[:30]}"'
        if hit and hit not in hits:  # 표 칸 글은 칸·행·표 단위로 여러 번 나오므로 한 번만 셉니다
            hits.append(hit)
            locs.append(loc)
    if hits:
        return entry("markup", "fail", f"{len(hits)}건: {brief(hits)}", _unique(locs))
    return entry("markup", "pass", "마크다운 표지 없음")


# --- placeholder -----------------------------------------------------------------

def check_placeholder(ctx: Ctx) -> dict:
    if ctx.placeholders is None:
        return entry("placeholder", "skip", "--placeholders 없음")
    if not ctx.placeholders:
        return entry("placeholder", "skip", "자리표시 없음")
    missing, locs = [], []
    for item in ctx.placeholders:
        expect = str(item.get("expect") or "")
        loc = item.get("locator")
        texts, scope = scope_texts(ctx.out, ctx.src, ctx.profile, loc)
        if nows(expect) and any(nows(expect) in nows(t) for t in texts):
            continue
        where = f"{loc} 안" if scope else "문서 전체"
        missing.append(f'"{expect}" ({where}에 없음)')
        locs.append(str(loc or ""))
    if missing:
        return entry("placeholder", "fail", f"{len(missing)}건: {brief(missing)}", _unique(locs))
    return entry("placeholder", "pass", f"자리표시 {len(ctx.placeholders)}개 모두 있음")


# --- fields ----------------------------------------------------------------------

def _field_problem(ctx: Ctx, field: dict, notes: list) -> str | None:
    """칸 하나를 봅니다. 문제가 있으면 설명을, 없으면 None. 판정 못 한 것은 notes에."""
    fid = field.get("id")
    text = field_text(ctx.out, field.get("locator"))
    if text is None:
        notes.append(f"{fid} locator 「{field.get('locator')}」를 풀 수 없음")
        return None
    text = text.strip()
    if not text:
        return f"{fid} 빈칸"
    constraint = str(field.get("constraint") or "").strip()
    if constraint.startswith("re:"):
        try:
            ok = re.fullmatch(constraint[3:], text) is not None
        except re.error as exc:
            return f"{fid} constraint 정규식 오류 ({exc})"
        # 칸 값은 개인정보일 수 있어 보고에 값 대신 글자 수만 냅니다 (kordoc fields_file 마스킹과 같게).
        return None if ok else f"{fid} 값({len(text)}자)이 {constraint}에 맞지 않음"
    if constraint:
        notes.append(f"{fid} constraint 「{constraint}」는 판정하지 않음 — ⑦ 리뷰어 확인")
    return None


def check_fields(ctx: Ctx) -> dict:
    if ctx.mode == "new":
        return new_mode_skip("fields", "양식 칸 없음")
    if ctx.mode != "form":
        return entry("fields", "skip", f"{ctx.mode} 모드는 검사하지 않음")
    fields = [f for f in ctx.profile.get("fields") or [] if isinstance(f, dict)]
    if not fields:
        return entry("fields", "skip", "fields 없음")
    exempt = {str(p.get("locator")) for p in ctx.placeholders or []}
    problems, locs, notes = [], [], []
    for field in fields:
        fid = str(field.get("id"))
        if fid in exempt or str(field.get("locator")) in exempt:
            notes.append(f"{fid} 자리표시 목록에 있음")
            continue
        problem = _field_problem(ctx, field, notes)
        if problem:
            problems.append(problem)
            locs.append(fid)
    if problems:
        return entry("fields", "fail", "; ".join(problems + notes), locs)
    unresolved = any("풀 수 없음" in n for n in notes)
    detail = "; ".join([f"칸 {len(fields)}개 확인"] + notes)
    return entry("fields", "warn" if unresolved else "pass", detail)


# --- scope -----------------------------------------------------------------------

def _diff_at(a: list, b: list) -> str | None:
    """두 [(글, loc)] 목록이 다르면 결과 쪽 처음 다른 위치를, 같으면 None."""
    for i in range(max(len(a), len(b))):
        ta = a[i][0] if i < len(a) else None
        tb = b[i][0] if i < len(b) else None
        if ta != tb:
            return (b[i][1] if i < len(b) else None) or (a[i][1] if i < len(a) else None) or "?"
    return None


def _scope_regions(ctx: Ctx, sections: list, updated: set) -> list:
    src_r = section_ranges(ctx.src, ctx.src, sections)
    out_r = section_ranges(ctx.out, ctx.src, sections)
    regions = [("첫 섹션 앞", (0, src_r["first"]), (0, out_r["first"]))]
    for s in sections:
        sid = s.get("id")
        if sid not in updated:
            regions.append((str(sid), src_r["ranges"].get(sid), out_r["ranges"].get(sid)))
    return regions


def check_scope(ctx: Ctx) -> dict:
    if ctx.mode == "new":
        return new_mode_skip("scope", "갱신 범위 대조할 견본 없음")
    if ctx.mode != "update":
        return entry("scope", "skip", f"{ctx.mode} 모드는 검사하지 않음")
    sections = sections_of(ctx.profile)
    updated = {str(s) for s in (ctx.profile.get("update") or {}).get("sections") or []}
    if not sections:
        return entry("scope", "skip", "structure.sections 없음")
    problems, locs = [], []
    for name, a, b in _scope_regions(ctx, sections, updated):
        if a is None or b is None:
            side = "견본" if a is None else "결과"
            problems.append(f"{name}: {side}에서 섹션 시작(anchor)을 찾지 못함")
            locs.append(name)
            continue
        where = _diff_at(block_items(ctx.src.blocks[a[0]:a[1]]), block_items(ctx.out.blocks[b[0]:b[1]]))
        if where:
            problems.append(f"{name}: 견본과 다름 ({where})")
            locs.append(where)
    if problems:
        return entry("scope", "fail", brief(problems, 5), _unique(locs))
    return entry("scope", "pass", f"갱신 범위({', '.join(sorted(updated)) or '없음'}) 밖 변경 없음")


# --- length ----------------------------------------------------------------------

def _upper(value):
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _chars(blocks) -> int:
    return sum(len(nows(t)) for t, _ in block_items(blocks))


def _doc_length(ctx: Ctx, spec: dict, res: dict) -> None:
    fmt = ctx.out.fmt
    if "pages" in spec:
        if fmt == "md":
            res["notes"].append("MD는 쪽 기준을 보지 않음")
        elif ctx.pages is None:
            res["notes"].append("렌더 없음 — 쪽 수 skip")
        else:
            _judge(res, "문서 쪽", len(ctx.pages), spec["pages"], "쪽")
    if "slides" in spec:
        if fmt == "pptx":
            _judge(res, "문서 장", ctx.out.slides, spec["slides"], "장")
        else:
            res["notes"].append(f"{fmt.upper()}는 장 수가 없음")
    if "chars" in spec:
        _judge(res, "문서 글자", _chars(ctx.out.blocks), spec["chars"], "자")
    if "lines" in spec:
        res["notes"].append("문서 줄 수는 ⑦ 리뷰어 확인")


def _judge(res: dict, name: str, value, limit, unit: str, loc: str | None = None) -> None:
    upper = _upper(limit)
    if upper is None or value is None:
        res["notes"].append(f"{name} 상한을 읽을 수 없음")
        return
    res["checked"] += 1
    if value > upper:
        res["over"].append(f"{name} {value}{unit} > {upper}{unit}")
        if loc:
            res["locs"].append(loc)


def _section_length(ctx: Ctx, res: dict) -> None:
    sections = [s for s in sections_of(ctx.profile) if isinstance(s.get("length"), dict)]
    if not sections:
        return
    if ctx.mode == "form":
        # 양식 섹션은 문서 끝까지(표 포함) 이어져 글자 수가 양식 전체가 됩니다 — 최상위 length만 봅니다.
        res["notes"].append("form 모드는 섹션 분량을 보지 않음")
        return
    loose = ctx.mode == "new"  # 신규 모드는 제목 앞 장 번호(Ⅰ.·1)·가.)를 빼고 h: anchor와 맞춥니다
    ranges = section_ranges(ctx.out, ctx.src, sections_of(ctx.profile), loose)["ranges"]
    for s in sections:
        sid, spec = str(s.get("id")), s["length"]
        rng = ranges.get(s.get("id"))
        if "chars" in spec:
            if rng is None:
                res["notes"].append(f"{sid} 섹션 시작을 찾지 못해 글자 수 skip")
            else:
                _judge(res, f"{sid} 글자", _chars(ctx.out.blocks[rng[0]:rng[1]]), spec["chars"], "자", sid)
        for key in ("lines", "pages", "slides"):
            if key in spec:
                res["notes"].append(f"{sid} {key}는 ⑦ 리뷰어 확인")


def check_length(ctx: Ctx) -> dict:
    spec = ctx.profile.get("length") if isinstance(ctx.profile.get("length"), dict) else {}
    has_sections = any(isinstance(s.get("length"), dict) for s in sections_of(ctx.profile))
    if not spec and not has_sections:
        return entry("length", "skip", "length 없음")
    res = {"checked": 0, "over": [], "notes": [], "locs": []}
    _doc_length(ctx, spec, res)
    _section_length(ctx, res)
    notes = "; ".join(res["notes"])
    if res["over"]:
        return entry("length", "fail", "; ".join(res["over"] + res["notes"]), _unique(res["locs"]))
    if res["checked"]:
        return entry("length", "pass", f"상한 {res['checked']}개 안" + (f"; {notes}" if notes else ""))
    return entry("length", "skip", notes or "볼 수 있는 분량 기준 없음")
