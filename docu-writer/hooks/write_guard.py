#!/usr/bin/env python3
"""docu-writer PreToolUse hook: 견본·계약 파일 쓰기 보호.

계약: template/skills/template-workflow/SKILL.md 「견본 보호」.
표준 입력 JSON 한 개를 읽고, 막을 때는 permissionDecision: deny JSON을 출력한다.
읽을 수 없는 입력은 종료 코드 2로 끝낸다.
"""
import json
import os
import sys

AGENT_PREFIX = "docu-writer:"
FILE_TOOLS = {"Write", "Edit", "MultiEdit"}
KORDOC_TOOLS = (
    "patch_document", "fill_form", "generate_document",
    "convert_to_hwpx", "extract_profile", "render_document",
)
CONTRACT_NAMES = ("protected-paths", "approved.sha256", "session.yaml")


def target_key(tool_name):
    """검사 대상 도구면 tool_input의 경로 키를, 아니면 None을 돌려준다."""
    if tool_name in FILE_TOOLS:
        return "file_path"
    if any(tool_name.endswith("kordoc__" + name) for name in KORDOC_TOOLS):
        return "output_path"
    return None


def canonical(path, cwd):
    """cwd 기준 절대 경로로 바꾸고 심볼릭 링크·`../`를 해소한다."""
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    path = os.path.normpath(path)
    if os.path.lexists(path):
        return os.path.realpath(path)
    parent, name = os.path.split(path)
    return os.path.join(os.path.realpath(parent), name)


def same_file(a, b):
    """경로가 같거나, 둘 다 있고 (st_dev, st_ino)가 같으면 참."""
    if a == b:
        return True
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def is_inside(path, directory):
    return path != directory and path.startswith(directory.rstrip(os.sep) + os.sep)


def read_protected(workspace, cwd):
    """protected-paths의 빈 줄·주석(#)이 아닌 줄을 정규화해 돌려준다."""
    try:
        with open(os.path.join(workspace, "protected-paths"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    entries = (line.strip() for line in lines)
    return [canonical(e, cwd) for e in entries if e and not e.startswith("#")]


def matches_any(target, candidates):
    return any(same_file(target, c) for c in candidates)


def decide(role, target, workspace, protected):
    """(허용 여부, 거부 사유)를 돌려준다."""
    contract = [os.path.join(workspace, n) for n in CONTRACT_NAMES]
    if role == "reviewer":
        return False, "reviewer는 어떤 파일도 쓸 수 없습니다"
    if matches_any(target, protected):
        return False, "견본(protected-paths)은 읽기 전용입니다"
    if role == "analyst":
        if is_inside(target, workspace) and not matches_any(target, contract):
            return True, ""
        return False, "analyst는 .docu-writer/ 안(계약 파일 제외)에만 쓸 수 있습니다"
    if role == "researcher":
        if same_file(target, os.path.join(workspace, "evidence.yaml")):
            return True, ""
        return False, "researcher는 .docu-writer/evidence.yaml에만 쓸 수 있습니다"
    if role == "writer":
        locked = contract + [os.path.join(workspace, n) for n in ("profile.yaml", "evidence.yaml")]
        if matches_any(target, locked):
            return False, "writer는 계약 파일과 profile.yaml·evidence.yaml을 쓸 수 없습니다"
        return True, ""
    return False, "알 수 없는 docu-writer 역할입니다"


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
    key = target_key(tool) if isinstance(tool, str) else None
    if key is None:
        return
    role = agent[len(AGENT_PREFIX):]
    tool_input = event.get("tool_input")
    raw = tool_input.get(key) if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw:
        deny(f"[docu-writer:{role}] {tool} 호출에 {key}가 없어 막습니다")
        return
    cwd = event.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    cwd = os.path.realpath(cwd)
    workspace = canonical(os.path.join(cwd, ".docu-writer"), cwd)
    target = canonical(raw, cwd)
    allowed, reason = decide(role, target, workspace, read_protected(workspace, cwd))
    if not allowed:
        deny(f"[docu-writer:{role}] {target} 쓰기를 막습니다: {reason}")


if __name__ == "__main__":
    main()
