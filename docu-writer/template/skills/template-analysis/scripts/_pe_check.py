"""check: 프로파일을 견본·표 목록에 대어 기계적으로 점검 (SKILL.md 「check가 보는 것」)."""
import re
from pathlib import Path

import yaml

from _pe_common import (MIN_SAMPLE_LEN, UsageError, detect_format, format_module, no_space,
                        placeholder_only, sha256_of)

MODES = ("sample", "form", "update")
SECTION_KEYS = ("id", "title", "level", "anchor", "kind", "required", "guide", "length")
H_ANCHOR_RE = re.compile(r'^h:"(.*)"(?:#(\d+))?$')
P_ANCHOR_RE = re.compile(r"^(p|sl):(\d+)$")
T_LOC_RE = re.compile(r"(?:^|/)t:(\d+)(?:/r:(\d+))?(?:/c:(\d+))?(?=/|$)")
LOCATOR_ROOTS = ("fields", "structure", "update", "objects")


def missing(value) -> bool:
    if value is None or value == "":
        return True
    return isinstance(value, (list, dict)) and not value


def load_yaml_file(path: Path, what: str):
    if not path.is_file():
        raise UsageError(f"{what} 파일 없음: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_tables(tables_path, source: Path, fmt: str):
    if tables_path is None:
        return format_module(fmt).tables(source)[0]
    try:
        data = load_yaml_file(Path(tables_path), "--tables")
    except yaml.YAMLError as exc:
        raise UsageError(f"--tables YAML 오류: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tables"), list):
        raise UsageError("--tables에 tables 목록이 없음")
    return data["tables"]


def check_header(prof, source: Path, fails):
    if prof.get("profile_version") != 1:
        fails.append(f"profile_version이 1이 아님: {prof.get('profile_version')!r}")
    if prof.get("mode") not in MODES:
        fails.append(f"mode가 sample·form·update 가운데 하나가 아님: {prof.get('mode')!r}")
    src = prof.get("source") if isinstance(prof.get("source"), dict) else {}
    if src.get("sha256") != sha256_of(source):
        fails.append("source.sha256이 견본 파일의 실제 값과 다름")


def get_sections(prof, fails):
    structure = prof.get("structure")
    sections = structure.get("sections") if isinstance(structure, dict) else None
    if not isinstance(sections, list):
        fails.append("structure.sections 목록이 없음")
        return []
    for s in sections:
        if not isinstance(s, dict):
            fails.append(f"섹션이 사전이 아님: {s!r}")
    return [s for s in sections if isinstance(s, dict)]


def check_section_keys(sections, fails, mode=None):
    # form 섹션은 쓰는 글이 아니라 양식 뼈대라 분량이 없습니다(분량은 최상위 length.pages로 봅니다).
    keys = [k for k in SECTION_KEYS if not (mode == "form" and k == "length")]
    seen = set()
    for i, s in enumerate(sections, 1):
        label = s.get("id") or f"섹션 {i}"
        absent = [k for k in keys if k not in s or missing(s[k])]
        if absent:
            fails.append(f"{label}: 칸이 없거나 비어 있음 — {', '.join(absent)}")
        sid = s.get("id")
        if sid in seen:
            fails.append(f"섹션 id가 겹침: {sid}")
        seen.add(sid)


def anchor_resolver(source: Path, fmt: str):
    """anchor 글 → 문서 위치(정수) 또는 None. 위치가 클수록 뒤."""
    texts = [no_space(t) for t in format_module(fmt).heading_texts(source)]
    kinds = {"docx": "p", "pptx": "sl"}
    limit = len(texts)

    def resolve(anchor):
        m = P_ANCHOR_RE.match(anchor)
        if m:
            n = int(m.group(2))
            return n if m.group(1) == kinds.get(fmt) and 1 <= n <= limit else None
        m = H_ANCHOR_RE.match(anchor)
        if not m:
            return None
        hits = [i for i, t in enumerate(texts, 1) if t and t == no_space(m.group(1))]
        k = int(m.group(2) or 1)
        return hits[k - 1] if 1 <= k <= len(hits) else None

    return resolve


def check_anchors(sections, source: Path, fmt: str, fails):
    resolve = anchor_resolver(source, fmt)
    last = None
    for i, s in enumerate(sections, 1):
        anchor = s.get("anchor")
        if not isinstance(anchor, str) or missing(anchor):
            continue
        pos = resolve(anchor.strip())
        if pos is None:
            fails.append(f"{s.get('id') or f'섹션 {i}'}: anchor {anchor}를 견본에서 찾지 못함")
            continue
        if last is not None and pos <= last:
            fails.append(f"{s.get('id') or f'섹션 {i}'}: anchor {anchor}가 앞 섹션보다 앞에 있음 (문서 순서)")
        last = pos


def walk_strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_strings(v)
    elif isinstance(value, str) and value and not re.search(r"\s", value):
        yield value


def locator_problem(m, tables):
    n, r, c = (int(g) if g else None for g in m.groups())
    if not 1 <= n <= len(tables):
        return f"표 번호가 범위 밖 (표 {len(tables)}개)"
    table = tables[n - 1] if isinstance(tables[n - 1], dict) else {}
    rows, cols = int(table.get("rows") or 0), int(table.get("cols") or 0)
    if r is not None and not 1 <= r <= rows:
        return f"행이 범위 밖 (t:{n}은 {rows}행)"
    if c is not None and not 1 <= c <= cols:
        return f"칸이 범위 밖 (t:{n}은 {cols}열)"
    return ""


def check_locators(prof, tables, fails):
    for root in LOCATOR_ROOTS:
        for text in walk_strings(prof.get(root)):
            for m in T_LOC_RE.finditer(text):
                problem = locator_problem(m, tables)
                if problem:
                    fails.append(f"{root}: {text} — {problem}")


def check_mode(prof, sections, fails):
    mode = prof.get("mode")
    if mode == "form":
        fields = prof.get("fields")
        if not isinstance(fields, list) or not fields:
            fails.append("form 모드인데 fields가 하나도 없음")
    if mode != "update":
        return
    update = prof.get("update") if isinstance(prof.get("update"), dict) else {}
    ids = {s.get("id") for s in sections}
    targets = update.get("sections")
    if not isinstance(targets, list) or not targets:
        fails.append("update 모드인데 update.sections가 비어 있음")
    else:
        unknown = [t for t in targets if t not in ids]
        if unknown:
            fails.append(f"update.sections에 없는 섹션 id: {', '.join(map(str, unknown))}")
    requests = update.get("requests")
    if not isinstance(requests, list) or not requests:
        fails.append("update 모드인데 update.requests가 비어 있음")


def sample_text_list(prof, fails):
    items = prof.get("sample_text", [])
    if items is None:
        return []
    if not isinstance(items, list):
        fails.append("sample_text가 목록이 아님")
        return []
    return items


def check_sample_text(prof, sections, fails):
    titles = {no_space(str(s.get("title") or "")) for s in sections} - {""}
    items = sample_text_list(prof, fails)
    for item in items:
        if not isinstance(item, str):
            fails.append(f"sample_text 항목이 글이 아님: {item!r}")
        elif placeholder_only(item):
            fails.append(f"sample_text에 ○○만 있는 토큰: {item!r}")
        elif len(item.strip()) < MIN_SAMPLE_LEN:
            fails.append(f"sample_text에 {MIN_SAMPLE_LEN}자 미만 글: {item!r}")
        elif no_space(item) in titles:
            fails.append(f"sample_text에 섹션 제목과 같은 글: {item!r}")
    texts = [i.strip() for i in items if isinstance(i, str) and i.strip()]
    for s in sections:
        guide = s.get("guide")
        copied = [t for t in texts if isinstance(guide, str) and t in guide]
        if copied:
            fails.append(f"{s.get('id')}: guide가 견본 글을 옮김 — {copied[0]!r}")


def check_conflicts(prof, fails):
    conflicts = prof.get("conflicts") or []
    if not isinstance(conflicts, list):
        fails.append("conflicts가 목록이 아님")
        return
    for c in conflicts:
        handling = c.get("handling") if isinstance(c, dict) else None
        if handling != "report":
            fails.append(f"conflicts[].handling이 report가 아님: {handling!r}")


def run_check(profile_path: Path, source: Path, tables_path):
    """실패 항목 목록을 돌려줌. 파일 없음·형식 오류는 UsageError."""
    fmt = detect_format(source)
    if not profile_path.is_file():
        raise UsageError(f"프로파일 파일 없음: {profile_path}")
    tables = load_tables(tables_path, source, fmt)
    try:
        prof = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return [f"프로파일이 YAML로 읽히지 않음: {exc}"]
    if not isinstance(prof, dict):
        return ["프로파일 최상위가 사전이 아님"]
    fails = []
    check_header(prof, source, fails)
    sections = get_sections(prof, fails)
    check_section_keys(sections, fails, prof.get("mode"))
    check_anchors(sections, source, fmt, fails)
    check_locators(prof, tables, fails)
    check_mode(prof, sections, fails)
    check_sample_text(prof, sections, fails)
    check_conflicts(prof, fails)
    return fails
