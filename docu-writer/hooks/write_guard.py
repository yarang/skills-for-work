#!/usr/bin/env python3
"""docu-writer PreToolUse hook: 견본·계약 파일 쓰기 보호.

계약: template/skills/template-workflow/SKILL.md 「견본 보호」.
표준 입력 JSON 한 개를 읽고, 막을 때는 permissionDecision: deny JSON을 출력한다.
읽을 수 없는 입력과 예상하지 못한 오류는 종료 코드 2(차단)로 끝낸다. 종료 코드 1은
Claude Code가 막지 않는 오류로 다루므로, 가드는 어떤 경우에도 1로 끝나면 안 된다.
"""
import json
import os
import sys

AGENT_PREFIX = "docu-writer:"
FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path"}
KORDOC_TOOLS = (
    "patch_document", "fill_form", "generate_document",
    "convert_to_hwpx", "extract_profile", "render_document",
)
CONTRACT_NAMES = ("protected-paths", "approved.sha256", "session.yaml")
APPROVED_NAMES = ("profile.yaml", "evidence.yaml")


def target_key(tool_name):
    """검사 대상 도구면 tool_input의 경로 키를, 아니면 None을 돌려준다."""
    if tool_name in FILE_TOOLS:
        return FILE_TOOLS[tool_name]
    if any(tool_name.endswith("kordoc__" + name) for name in KORDOC_TOOLS):
        return "output_path"
    return None


def lexical(path, cwd):
    """cwd 기준 절대 경로로 바꾸고 `../`만 정리한다 (링크는 따라가지 않음)."""
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.normpath(path)


def canonical(path, cwd):
    """cwd 기준 절대 경로로 바꾸고 심볼릭 링크·`../`를 해소한다.

    normpath를 먼저 하면 `link/../x`의 `..`가 링크 목적지가 아니라 링크 이름 기준으로
    지워져 실제 쓰기 위치와 달라진다. realpath는 OS처럼 왼쪽부터 링크를 풀며 `..`를 처리하고,
    없는 경로·끊어진 링크도 목적지 쪽으로 풀어 준다."""
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(path)


def same_file(a, b):
    """경로가 같거나(대소문자 무시), 둘 다 있고 (st_dev, st_ino)가 같으면 참.

    macOS 기본 APFS는 대소문자를 가리지 않으므로 `Profile.YAML`도 `profile.yaml`이다.
    없는 파일끼리는 inode로 비교할 수 없어, 보호 쪽으로 기울도록 casefold로 맞춘다."""
    if a == b or a.casefold() == b.casefold():
        return True
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def is_inside(path, directory):
    return path != directory and path.startswith(directory.rstrip(os.sep) + os.sep)


def forms(path, cwd):
    """링크 자체의 경로와 링크가 가리키는 목적지 (끊어진 링크 포함)."""
    return {lexical(path, cwd), canonical(path, cwd)}


def read_protected(workspace, cwd):
    """protected-paths의 빈 줄·주석(#)이 아닌 줄의 경로 형태들. 읽을 수 없으면 None."""
    try:
        with open(os.path.join(workspace, "protected-paths"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    entries = (line.strip() for line in lines)
    return {f for e in entries if e and not e.startswith("#") for f in forms(e, cwd)}


def workspace_files(workspace, names, cwd):
    return {f for n in names for f in forms(os.path.join(workspace, n), cwd)}


def hits(targets, candidates):
    return any(same_file(t, c) for t in targets for c in candidates)


def decide(role, target, workspace, protected, cwd):
    """(허용 여부, 거부 사유)를 돌려준다. target은 cwd 기준 원래 경로."""
    if role == "reviewer":
        return False, "reviewer는 어떤 파일도 쓸 수 없습니다"
    if protected is None:
        return False, ".docu-writer/protected-paths가 없거나 읽을 수 없어 모든 쓰기를 막습니다"
    real, mine = canonical(target, cwd), forms(target, cwd)
    if hits(mine, protected):
        return False, "견본(protected-paths)은 읽기 전용입니다"
    contract = workspace_files(workspace, CONTRACT_NAMES, cwd)
    if role == "analyst":
        if is_inside(real, workspace) and not hits(mine, contract):
            return True, ""
        return False, "analyst는 .docu-writer/ 안(계약 파일 제외)에만 쓸 수 있습니다"
    if role == "researcher":
        others = contract | workspace_files(workspace, ("profile.yaml",), cwd)
        if same_file(real, os.path.join(workspace, "evidence.yaml")) and not os.path.islink(lexical(target, cwd)) \
                and not hits(mine, others):
            return True, ""
        return False, "researcher는 .docu-writer/evidence.yaml(링크 아님)에만 쓸 수 있습니다"
    if role == "writer":
        if hits(mine, contract | workspace_files(workspace, APPROVED_NAMES, cwd)):
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
    if not isinstance(raw, str) or not raw.strip():
        deny(f"[docu-writer:{role}] {tool} 호출에 {key}가 없어 막습니다")
        return
    cwd = event.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    cwd = os.path.realpath(cwd)
    workspace = canonical(os.path.join(cwd, ".docu-writer"), cwd)
    allowed, reason = decide(role, raw, workspace, read_protected(workspace, cwd), cwd)
    if not allowed:
        deny(f"[docu-writer:{role}] {canonical(raw, cwd)} 쓰기를 막습니다: {reason}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - 가드 오류는 열림이 아니라 차단으로
        sys.stderr.write(f"write_guard: 예상하지 못한 오류로 막습니다: {type(exc).__name__}: {exc}\n")
        sys.exit(2)
