#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill_log.py — work-standards 서브에이전트의 Skill 호출을 기록합니다 (H6).

PostToolUse(Skill)에서 실행됩니다. 상태 디렉터리(_common.state_dir)의
skill-log.jsonl에 한 줄을 추가하고 아무것도 출력하지 않습니다. 절대 차단하지
않습니다. 격리 worktree 서브에이전트는 후보(가까운 toplevel부터) 중 이미
.work-standards/ 디렉터리가 있는 첫 곳, 없으면 세션 toplevel에 기록합니다.

알아 둘 것(P0 실측 R4): 에이전트 frontmatter의 skills: 로 미리 로드한 스킬은
Skill 이벤트를 만들지 않으므로 이 기록에 없습니다. 기록을 설계서의 스킬 목록과
대조할 때(trace-check.sh 등)는 에이전트 frontmatter의 미리 로드 목록을 읽어
합쳐야 합니다.

기록 형식(입력에 키가 없으면 null):
{"ts", "session_id", "agent_id", "agent_type", "skill", "success"}
"""

import datetime
import json
import os
import sys

import _common

LOG_NAME = "skill-log.jsonl"


def main():
    data = _common.read_input()
    if not _common.is_plugin_agent(data):
        return  # 메인 대화가 직접 부른 스킬은 기록 대상이 아닙니다.
    if data.get("hook_event_name") != "PostToolUse" or data.get("tool_name") != "Skill":
        return
    candidates = _common.state_candidates(_common.input_cwd(data))
    append(os.path.join(_common.state_dir(candidates), LOG_NAME), build_record(data))


def build_record(data):
    """기록 한 줄을 만듭니다. 필드가 없으면 null을 넣습니다."""
    tool_input = data.get("tool_input")
    tool_response = data.get("tool_response")
    if not isinstance(tool_input, dict):
        tool_input = {}
    if not isinstance(tool_response, dict):
        tool_response = {}
    return {
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": data.get("session_id"),
        "agent_id": data.get("agent_id"),
        "agent_type": data.get("agent_type"),
        "skill": tool_input.get("skill"),
        "success": tool_response.get("success"),
    }


def append(path, record):
    """기록 한 줄을 O_APPEND로 한 번에 씁니다.

    (왜: 병렬로 띄운 서브에이전트가 같은 순간에 써도, write(2) 한 번은
    O_APPEND로 통째로 덧붙어 줄이 섞이지 않습니다.)
    """
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


if __name__ == "__main__":
    _common.run_hook(main)
