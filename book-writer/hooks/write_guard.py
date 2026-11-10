#!/usr/bin/env python3
"""book-writer PreToolUse hook: 역할별 원고 쓰기 보호.

계약: docs/design.md 「쓰기 보호」.
표준 입력 JSON 한 개를 읽고, 막을 때는 permissionDecision: deny JSON을 출력합니다.
입력이 잘못된 JSON이면 stderr에 메시지를 쓰고 종료 코드 2로 끝납니다. 종료 코드 1은
Claude Code가 막지 않는 오류로 다루므로, 가드는 어떤 경우에도 1로 끝나면 안 됩니다.
"""
import json
import os
import re
import sys

AGENT_PREFIX = "book-writer:"
FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path"}
GUARD_DIR = ".book-writer"
# 역할별 기본 허용 목록 (원고 루트 기준 상대 경로, `/` 구분).
DEFAULT_ALLOWLIST = {
    "planner": ["plans/**"],
    "writer": ["manuscript/**", "manifest.md", "examples/**"],
    "editor": ["reviews/**"],
    "researcher": ["research/**"],
    "capturer": ["manuscript/**/images/**", "research/measure-*.md"],
}
# 승인 상태 표시: `상태: 승인`, `> 상태: **승인** (날짜)` 등을 잡습니다.
APPROVED_LINE = re.compile(r"^\s*>?\s*상태\s*:\s*\**\s*승인")


def resolve(path):
    """realpath. 없는 경로(아직 만들 대상)는 존재하는 부모까지 풀고 이름을 붙입니다."""
    if os.path.lexists(path):
        return os.path.realpath(path)
    head, tail = os.path.split(path)
    return os.path.join(os.path.realpath(head), tail)


def absolute(path, cwd):
    """상대 경로를 cwd 기준 절대 경로로 바꾸고 링크를 해소합니다."""
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return resolve(path)


def find_root(cwd):
    """cwd에서 위로 올라가며 처음 만나는 manifest.md가 있는 디렉터리. 없으면 cwd."""
    cur = cwd
    while True:
        if os.path.isfile(os.path.join(cur, "manifest.md")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return cwd
        cur = parent


def segment_regex(segment):
    """한 세그먼트용 정규식: `*`는 `/` 외 모든 문자, `?`는 한 글자, 나머지는 그대로."""
    parts = []
    for ch in segment:
        if ch == "*":
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def match_parts(pattern, parts):
    """패턴 세그먼트 목록과 경로 세그먼트 목록을 맞댑니다. `**`는 0개 이상 디렉터리."""
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(match_parts(pattern[1:], parts[i:]) for i in range(len(parts) + 1))
    if not parts:
        return False
    head = re.fullmatch(segment_regex(pattern[0]), parts[0])
    return head is not None and match_parts(pattern[1:], parts[1:])


def glob_match(pattern, rel):
    """`**`는 0개 이상의 디렉터리, `*`는 `/`를 넘지 않는 글자에만 대응합니다."""
    return match_parts(pattern.split("/"), rel.split("/"))


def is_approved(path):
    """파일이 있고 첫 10줄 안에 승인 상태 줄이 있으면 참."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [fh.readline() for _ in range(10)]
    except (OSError, UnicodeDecodeError):
        return False
    return any(APPROVED_LINE.search(line) for line in lines)


def load_overrides(root):
    """{역할: [glob, ...]} 덮어쓰기 목록. 파일이 없으면 {}. 형식이 틀리면 None."""
    path = os.path.join(root, GUARD_DIR, "paths.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(isinstance(v, list) and all(isinstance(g, str) for g in v)
               for v in data.values()):
        return None
    return data


def allowed_globs(role, root):
    """그 역할의 허용 glob 목록. paths.json이 있으면 교체, 없으면 기본값."""
    overrides = load_overrides(root)
    if overrides is None:
        return None
    if role in overrides:
        return overrides[role]
    return DEFAULT_ALLOWLIST.get(role)


def decide(role, raw, cwd):
    """(허용 여부, 거부 사유). raw는 cwd 기준 원래 경로 문자열."""
    target = absolute(raw, cwd)
    root = find_root(cwd)
    try:
        rel = os.path.relpath(target, root)
    except ValueError:  # 서로 다른 볼륨 — 루트 밖으로 칩니다.
        return False, f"원고 저장소({root}) 밖 경로입니다"
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return False, f"원고 저장소({root}) 밖 경로입니다"
    rel = rel.replace(os.sep, "/")
    if rel.split("/")[0] == GUARD_DIR:
        return False, f"{GUARD_DIR}/ 아래 파일은 어떤 역할도 쓸 수 없습니다"
    if load_overrides(root) is None:
        return False, f"{GUARD_DIR}/paths.json이 올바른 JSON이 아니어서 모든 쓰기를 막습니다"
    globs = allowed_globs(role, root)
    if globs is None:
        return False, f"역할 `{role}`은(는) 쓸 수 있는 경로가 정의되어 있지 않습니다"
    if not any(glob_match(g, rel) for g in globs):
        return False, f"{role}는 {', '.join(globs)} 아래에만 쓸 수 있습니다 ({rel})"
    if role == "planner" and is_approved(target):
        return False, "승인된 계획 문서는 고칠 수 없습니다 — 수정안은 `<문서>.rev<N>.md`에 씁니다"
    return True, ""


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))


def load_event():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"write_guard: 입력 JSON을 읽을 수 없습니다: {exc}\n")
        sys.exit(2)
    if not isinstance(event, dict):
        sys.stderr.write("write_guard: 입력이 JSON 객체가 아닙니다\n")
        sys.exit(2)
    return event


def main():
    event = load_event()
    agent = event.get("agent_type")
    if not isinstance(agent, str) or not agent.startswith(AGENT_PREFIX):
        return
    tool = event.get("tool_name")
    key = FILE_TOOLS.get(tool) if isinstance(tool, str) else None
    if key is None:
        return
    role = agent[len(AGENT_PREFIX):]
    tool_input = event.get("tool_input")
    raw = tool_input.get(key) if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        deny(f"[book-writer:{role}] {tool} 호출에 {key}가 없어 막습니다")
        return
    cwd = event.get("cwd")
    cwd = os.path.realpath(cwd) if isinstance(cwd, str) and cwd else os.getcwd()
    allowed, reason = decide(role, raw, cwd)
    if not allowed:
        deny(f"[book-writer:{role}] {raw} 쓰기를 막습니다: {reason}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - 가드 오류는 열림이 아니라 차단으로
        sys.stderr.write(f"write_guard: 예상하지 못한 오류로 막습니다: {type(exc).__name__}: {exc}\n")
        sys.exit(2)
