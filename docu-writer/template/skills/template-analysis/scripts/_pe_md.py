"""MD: 원문을 줄 단위로 읽음 (제목·파이프 표·목록·앞머리)."""
import re
from pathlib import Path

from _pe_common import Candidates, UsageError, cell_text, collapse, line_marker, table_entry, unique

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
SEP_CELL_RE = re.compile(r"^\s*:?-+:?\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def read_lines(path: Path):
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError) as exc:
        raise UsageError(f"MD를 읽을 수 없음: {exc}") from exc


def front_matter_end(lines) -> int:
    """앞머리(--- … ---)가 있으면 그 다음 줄 번호, 없으면 0."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return i + 1
    return 0


def classify(lines):
    """줄마다 (번호, 글) 중 코드 블록·앞머리 밖의 줄만 냄."""
    out = []
    fence = None
    for i, line in enumerate(lines[front_matter_end(lines):], front_matter_end(lines)):
        m = FENCE_RE.match(line)
        if m:
            mark = m.group(1)[0]
            if fence is None:
                fence = mark
            elif fence == mark:
                fence = None
            continue
        if fence is None:
            out.append((i, line))
    return out


def split_row(line: str):
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def is_separator(line: str) -> bool:
    if "-" not in line:
        return False
    cells = split_row(line)
    return bool(cells) and all(SEP_CELL_RE.match(c) for c in cells)


def strip_inline(text: str) -> str:
    return collapse(re.sub(r"\*\*|__|`", "", text.replace("\\|", "|")))


def find_tables(lines):
    """파이프 표: [{'start': 줄, 'header': [...], 'align': [...], 'rows': [[...], ...]}]."""
    body = classify(lines)
    tables, k = [], 0
    while k < len(body) - 1:
        (i, line), (_, nxt) = body[k], body[k + 1]
        if "|" in line and is_separator(nxt) and len(split_row(nxt)) == len(split_row(line)):
            rows = [split_row(line)]
            k += 2
            while k < len(body) and "|" in body[k][1] and body[k][1].strip():
                rows.append(split_row(body[k][1]))
                k += 1
            tables.append({"start": i, "align": [align_of(c) for c in split_row(nxt)],
                           "rows": [[strip_inline(c) for c in r] for r in rows]})
            continue
        k += 1
    return tables


def align_of(sep: str) -> str:
    s = sep.strip()
    if s.startswith(":") and s.endswith(":"):
        return "center"
    if s.endswith(":"):
        return "right"
    return "left" if s.startswith(":") else ""


def tables(path: Path):
    warnings = []
    out = []
    for t in find_tables(read_lines(path)):
        rows = t["rows"]
        cols = len(rows[0])
        first = cell_text([rows[0][0]]) if rows[0] else ""
        last_row = [cell_text([c]) for c in rows[-1]]
        out.append(table_entry(len(out) + 1, len(rows), cols, first, last_row, 0, warnings))
    return out, warnings


def headings(lines):
    """[(줄 번호, 수준, 제목 글)] — 코드 블록 밖 `#` 제목."""
    out = []
    for i, line in classify(lines):
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), strip_inline(m.group(2))))
    return out


def heading_texts(path: Path):
    return [title for _, _, title in headings(read_lines(path))]


def sections(lines):
    out, seen = [], {}
    for _, level, title in headings(lines):
        seen[title] = seen.get(title, 0) + 1
        anchor = f'h:"{title}"' + (f"#{seen[title]}" if seen[title] > 1 else "")
        out.append({"title": title, "level": level, "anchor": anchor})
    return out


def numbering(lines):
    marks = []
    for _, line in classify(lines):
        m = LIST_RE.match(line)
        if m and not HEADING_RE.match(line):
            marks.append(m.group(2))
    marks += [line_marker(title) for _, _, title in headings(lines)]
    return unique(marks)


def front_matter_fields(lines, warnings):
    end = front_matter_end(lines)
    keys = [m.group(1) for line in lines[1:max(end - 1, 1)]
            if (m := re.match(r"^([A-Za-z0-9_\-가-힣]+)\s*:", line))]
    if keys:
        warnings.append("fields: MD 앞머리 키는 locator 문법이 없어 locator를 비움")
    return [{"id": f"f{n}", "label": k, "locator": "", "constraint": ""}
            for n, k in enumerate(keys, 1)]


def body_candidates(lines, table_list):
    cands = Candidates()
    table_lines = set()
    for t in table_list:
        table_lines.update(range(t["start"], t["start"] + len(t["rows"]) + 1))
        for row in t["rows"][1:]:
            for c in row:
                cands.add(c)
    for i, line in classify(lines):
        if i in table_lines or HEADING_RE.match(line) or not line.strip():
            continue
        m = LIST_RE.match(line)
        text = m.group(3) if m else re.sub(r"^\s*>+\s*", "", line)
        cands.add(strip_inline(text))
    return cands.items


def profile_parts(path: Path, mode: str):
    lines = read_lines(path)
    warnings = []
    table_list = find_tables(lines)
    fields = front_matter_fields(lines, warnings) if mode == "form" else []
    if mode == "form" and not fields:
        warnings.append("fields: MD 앞머리 키가 없어 비움")
    warnings.append("design.page·type·color·styles_allowed: MD에는 서식 정보가 없어 비움")
    return {
        "sections": sections(lines),
        "numbering": numbering(lines),
        "fields": fields,
        "design": {"page": {}, "type": {}, "color": {},
                   "table": {"align": {f"t:{n}": t["align"] for n, t in enumerate(table_list, 1)}},
                   "styles_allowed": []},
        "candidates": body_candidates(lines, table_list),
        "objects": [],
        "warnings": warnings,
    }
