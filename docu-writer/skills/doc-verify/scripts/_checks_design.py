"""doc_verify.py 디자인 검사 — r4_headings·r5_tokens·r6_numbering·table_header·r1_tables·rewrite.

계약: skills/doc-verify/SKILL.md 「검사 항목」·「검사 세부」.
"""
import re
from collections import Counter

from _checks_content import Ctx, _unique, brief, entry
from _readers import Para, all_paras, first_last, nows

SYMBOLS = set("□■◇◆○ㅇᄋ◦●-–•·※▶☞")
SYMBOL_ALIAS = {"ㅇ": "○", "ᄋ": "○", "◦": "○", "·": "•"}
YEAR = re.compile(r"\d{4}\.")  # 「2026. 11. 12.」·「2026.11.12.」 — 날짜의 연도는 번호가 아님 (종단 시험 F10)
SHAPES = [
    (re.compile(r"\d+(\.\d+)+\.?"), "1.1"),
    (re.compile(r"\d+\."), "1."),
    (re.compile(r"\d+\)"), "1)"),
    (re.compile(r"\(\d+\)"), "(1)"),
    (re.compile(r"[①-⑳]"), "①"),
    (re.compile(r"[가-힣]\."), "가."),
    (re.compile(r"[가-힣]\)"), "가)"),
    (re.compile(r"\([가-힣]\)"), "(가)"),
    (re.compile(r"[A-Za-z]\."), "A."),
]


def _hwpx_new_ids(ctx: Ctx) -> list:
    """결과 HWPX가 견본에 없던 글자·문단 모양 id를 쓰면 그 목록."""
    src_c, src_p = ctx.src.ids or (set(), set())
    out_c, out_p = ctx.out.ids or (set(), set())
    new = [f"charPr {i}" for i in sorted(out_c - src_c)] + [f"paraPr {i}" for i in sorted(out_p - src_p)]
    return new


def _hwpx_ids_check(ctx: Ctx, cid: str) -> dict:
    if ctx.mode == "new":
        # 견본 모양 id가 없으면 모든 id가 「새 id」가 되어 늘 fail입니다 — 읽을 수 없는 항목으로 skip.
        return entry(cid, "skip", "신규 모드 — 견본이 없어 HWPX 글자·문단 모양 id를 비교할 수 없음")
    new = _hwpx_new_ids(ctx)
    if new:
        return entry(cid, "fail", f"견본에 없는 모양 id {len(new)}개: {brief(new)}", new)
    return entry(cid, "pass", "견본에 있는 글자·문단 모양 id만 씀")


# --- R4 제목 ---------------------------------------------------------------------

def _heading_styles(ctx: Ctx) -> dict:
    """{제목 키: {eff 튜플: [loc]}} — 글이 있는 run만."""
    groups: dict = {}
    for p in ctx.out.paras:
        if not p.heading:
            continue
        for r in p.runs:
            if r.text.strip():
                groups.setdefault(p.heading, {}).setdefault(r.eff, []).append(p.loc)
    return groups


def _token_mismatch(key: str, eff: tuple, token: dict) -> str | None:
    for i, name in enumerate(("font", "pt", "bold")):
        want, got = token.get(name), eff[i]
        if want is None or want == "" or got is None:
            continue
        if name == "pt":
            same = float(want) == float(got)
        elif name == "bold":
            same = bool(want) == bool(got)
        else:
            same = nows(str(want)) == nows(str(got))
        if not same:
            return f"{key} {name} {got} ≠ 토큰 {want}"
    return None


def check_r4(ctx: Ctx) -> dict:
    fmt = ctx.out.fmt
    if fmt == "md":
        return entry("r4_headings", "skip", "MD는 서체 정보 없음")
    if fmt == "hwpx":
        return _hwpx_ids_check(ctx, "r4_headings")
    groups = _heading_styles(ctx)
    if not groups:
        return entry("r4_headings", "skip", "제목 문단 없음")
    types = (ctx.profile.get("design") or {}).get("type") or {}
    problems, locs, compared = [], [], False
    for key, effs in groups.items():
        if len(effs) > 1:
            shown = [f"{e[0]}/{e[1]}pt/{'굵게' if e[2] else '보통'}" for e in effs]
            problems.append(f"{key} 서식 {len(effs)}가지 섞임 ({brief(shown)})")
            locs.extend(loc for v in effs.values() for loc in v)
        token = types.get(key) if isinstance(types.get(key), dict) else None
        compared = compared or bool(token)
        for eff, where in effs.items() if token else []:
            bad = _token_mismatch(key, eff, token)
            if bad:
                problems.append(bad)
                locs.extend(where)
    if problems:
        return entry("r4_headings", "fail", brief(problems, 5), _unique(locs))
    if ctx.mode == "new" and not compared:
        # 신규 모드는 견본이 없어 섞임 검사만으로 통과라 말할 근거가 없음 (SKILL.md 「신규 모드」 빈 토큰)
        return entry("r4_headings", "skip", "비교할 토큰 없음 (design.type에 제목 토큰 없음)")
    return entry("r4_headings", "pass", f"제목 {len(groups)}종 서식 한 가지씩")


# --- R5 토큰 ---------------------------------------------------------------------

def _color(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip().upper()
    return v if v.startswith("#") else f"#{v}"


def _token_sets(design: dict) -> tuple[set, set, set]:
    types = design.get("type") or {}
    tokens = [t for t in types.values() if isinstance(t, dict)] if isinstance(types, dict) else []
    fonts = {nows(str(t["font"])) for t in tokens if t.get("font")}
    pts = {float(t["pt"]) for t in tokens if isinstance(t.get("pt"), (int, float))}
    raw = design.get("color") or {}
    values = raw.values() if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    colors = {c for c in (_color(v) for v in values) if c}
    return fonts, pts, colors


def _run_problems(ctx: Ctx, fonts: set, pts: set, colors: set) -> tuple[list, list]:
    problems, locs = [], []
    for p in all_paras(ctx.out):
        for r in p.runs:
            if not r.text.strip():
                continue
            found = [f"서체 {f}" for f in r.fonts if fonts and nows(f) not in fonts]
            if pts and r.pt is not None and float(r.pt) not in pts:
                found.append(f"크기 {r.pt}pt")
            if colors and r.color and r.color not in colors:
                found.append(f"색 {r.color}")
            if found:
                problems.extend(found)
                locs.append(p.loc)
    return problems, locs


def check_r5(ctx: Ctx) -> dict:
    fmt = ctx.out.fmt
    if fmt == "md":
        return entry("r5_tokens", "skip", "MD는 서식 토큰 없음")
    if fmt == "hwpx":
        return _hwpx_ids_check(ctx, "r5_tokens")
    design = ctx.profile.get("design") or {}
    allowed = [str(s) for s in design.get("styles_allowed") or []]
    tokens = _token_sets(design)
    if not allowed and not any(tokens):
        return entry("r5_tokens", "skip", "비교할 토큰 없음 (styles_allowed·design.type·design.color 비어 있음)")
    problems, locs = [], []
    if allowed:
        for name, loc in ctx.out.styles:
            if name not in allowed:
                problems.append(f"스타일 「{name}」")
                locs.append(loc)
    run_problems, run_locs = _run_problems(ctx, *tokens)
    problems += run_problems
    locs += run_locs
    if problems:
        uniq = _unique(problems)
        return entry("r5_tokens", "fail", f"토큰 밖 {len(problems)}건: {brief(uniq)}", _unique(locs))
    return entry("r5_tokens", "pass", "스타일·서체·크기·색이 토큰 안")


# --- R6 번호 ---------------------------------------------------------------------

def shape_of(token: str) -> str | None:
    """번호·부호 토큰의 모양. 번호가 아니면 None."""
    if len(token) == 1 and token in SYMBOLS:
        return SYMBOL_ALIAS.get(token, token)
    if YEAR.match(token):
        return None
    for pattern, shape in SHAPES:
        if pattern.fullmatch(token):
            return shape
    return None


def _marker(p: Para) -> str | None:
    parts = p.text.split()
    return shape_of(parts[0]) if parts else None


def check_r6(ctx: Ctx) -> dict:
    numbering = [str(n).strip() for n in (ctx.profile.get("structure") or {}).get("numbering") or []]
    allowed = {shape_of(n) or n for n in numbering if n}
    by_level: dict = {}
    problems, locs = [], []
    for p in ctx.out.paras:
        shape = _marker(p)
        if shape is None:
            continue
        by_level.setdefault(p.level, Counter())[shape] += 1
        if allowed and shape not in allowed:
            problems.append(f"「{p.text.split()[0]}」 번호 체계 밖")
            locs.append(p.loc or nows(p.text)[:20])
    for level, counts in by_level.items():
        if len(counts) > 1:
            problems.append(f"같은 단계에 부호 섞임 ({', '.join(counts)})")
    if problems:
        return entry("r6_numbering", "fail", brief(_unique(problems), 5), _unique(locs))
    if allowed and not by_level:
        # 자동 번호(DOCX numPr)·HWPX 프리셋 부호는 문단 속성이라 글에 나타나지 않습니다 — 통과로 볼 근거가 없음
        return entry("r6_numbering", "skip",
                     "글에 줄 머리 부호 없음 — 자동 번호·문단 번호 속성이면 글에 나타나지 않으므로 렌더로 확인 (⑦ 리뷰어 확인)")
    used = sorted({s for c in by_level.values() for s in c})
    return entry("r6_numbering", "pass", f"부호 {', '.join(used) or '없음'}")


# --- 표 머리행 -------------------------------------------------------------------

def check_table_header(ctx: Ctx) -> dict:
    if ctx.out.fmt == "md":
        return entry("table_header", "skip", "MD는 표 서식 없음")
    tables = [t for t in ctx.out.tables if len(t.rows) >= 2 and t.header is not None]
    if not tables:
        return entry("table_header", "skip", "머리행 있는 표 없음")
    sigs = Counter(t.header for t in tables)
    if len(sigs) == 1:
        return entry("table_header", "pass", f"표 {len(tables)}개 머리행 서식 같음")
    common = sigs.most_common(1)[0][0]
    odd = [t.at for t in tables if t.header != common]
    return entry("table_header", "fail", f"머리행 서식 {len(sigs)}가지: {brief(odd)}가 다름", odd)


# --- R1 표 쪽 나뉨 ----------------------------------------------------------------

def _on_page(page: str, cell: str) -> bool:
    """칸 글이 쪽 글(공백 없앰)에 있는지. 통째로 없으면 공백으로 나눈 낱말이 모두 있는지 봅니다.

    LibreOffice가 ○·※ 같은 기호를 대체 글꼴로 그리면 pymupdf가 그 조각을 다른 줄로 떼어
    쪽 글 순서가 바뀝니다(「부서장 ○○○ (서명)」→「○○○부서장(서명)」).
    """
    if nows(cell) in page:
        return True
    words = [nows(w) for w in cell.split()]
    return len(words) > 1 and all(w in page for w in words)


def _first_page(pages: list, cell: str, start: int) -> int | None:
    return next((i for i in range(start, len(pages)) if _on_page(pages[i], cell)), None)


def _table_pages(pages: list, first: str, last: str, cursor: int) -> tuple[int | None, int | None, int]:
    """(첫 칸 쪽, 끝 칸 쪽, 다음 커서). 한 쪽에 다 있으면 두 쪽 번호가 같습니다.

    pages는 공백을 없앤 쪽 글, first·last는 칸 글 그대로입니다.
    """
    both = next((i for i in range(cursor, len(pages))
                 if _on_page(pages[i], first) and _on_page(pages[i], last)), None)
    if both is not None:
        return both, both, both
    pf = _first_page(pages, first, cursor)
    if pf is None:
        pf = _first_page(pages, first, 0)
    if pf is None:
        return None, None, cursor
    pl = _first_page(pages, last, pf)
    return pf, pl, pl if pl is not None else pf


def check_r1(ctx: Ctx) -> dict:
    if ctx.out.fmt == "md":
        return entry("r1_tables", "skip", "MD는 쪽이 없음")
    if ctx.pages_dir is None or not ctx.pages:
        return entry("r1_tables", "skip", "렌더 없음 (--pages-dir 없음)" if ctx.pages_dir is None else "쪽별 글 없음")
    pages = [nows(t) for t in ctx.pages]
    suspects, locs, notes, cursor, seen = [], [], [], 0, 0
    for table in ctx.out.tables:
        first, last = first_last(table)
        if not nows(first) or not nows(last):
            notes.append(f"{table.at} 첫·끝 칸 비어 건너뜀")
            continue
        pf, pl, cursor = _table_pages(pages, first, last, cursor)
        if pf is None or pl is None:
            notes.append(f"{table.at} 쪽에서 찾지 못해 건너뜀")
            continue
        seen += 1
        if pf != pl:
            suspects.append(f"표 {table.at} 「{first_last(table)[0]}」 첫 칸 {pf + 1}쪽, 끝 칸 {pl + 1}쪽")
            locs.append(table.at)
    if suspects:
        return entry("r1_tables", "warn", "; ".join(suspects + notes), locs)
    if not seen:
        return entry("r1_tables", "skip", "; ".join(notes) or "표 없음")
    return entry("r1_tables", "pass", "; ".join([f"표 {seen}개 쪽 나뉨 없음"] + notes))


# --- rewrite ---------------------------------------------------------------------

def check_rewrite(ctx: Ctx) -> dict:
    if ctx.out.fmt != "hwpx":
        return entry("rewrite", "skip", f"{ctx.out.fmt.upper()}는 대체본이 없음")
    out = ctx.output
    found = [p for p in (out.with_name(out.name + ".rewrite.hwpx"), out.with_name(out.stem + ".rewrite.hwpx"))
             if p.exists()]
    if found:
        names = ", ".join(p.name for p in _unique(found))
        return entry("rewrite", "fail", f"대체본 {names} 있음 — 제자리 반영 못 한 편집이 남음", [str(p) for p in found])
    return entry("rewrite", "pass", "대체본(.rewrite.hwpx) 없음")
