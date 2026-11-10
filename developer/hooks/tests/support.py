# -*- coding: utf-8 -*-
"""hook 테스트 공용 도구.

hook 스크립트를 subprocess로 실행하고, stdin에 P0 실측(hook-log.jsonl)과 같은
키 집합의 JSON을 넣어 출력·종료 코드를 확인합니다. 세션·경로 값은 각 테스트가
만드는 임시 git 저장소로 채웁니다(개인 경로는 넣지 않습니다).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.dirname(HOOKS_DIR)
WRITE_GUARD = os.path.join(HOOKS_DIR, "write_guard.py")
SKILL_LOG = os.path.join(HOOKS_DIR, "skill_log.py")
BOUNDARY_CHECK = os.path.join(PLUGIN_ROOT, "skills", "dev-workflow", "scripts", "boundary-check.sh")

# 판정 함수의 단위 검사(casefold 비교 등)를 위해 모듈을 임포트할 수 있게 합니다.
sys.path.insert(0, HOOKS_DIR)

DEVELOPER = "work-standards:developer"
TESTER = "work-standards:tester"
DOCUMENTER = "work-standards:documenter"

# 값은 P0 실측 기록의 모양(형식)만 따옵니다.
SESSION_ID = "d9695227-a7b8-4117-af9f-6f8e8721c561"
AGENT_ID = "a504552771524dc49"
PROMPT_ID = "9e18c5b0-0c1d-4eb1-969f-9dc05d6a23a6"
TRANSCRIPT_PATH = "/tmp/work-standards-hook-test/transcript.jsonl"


def hook_input(cwd, tool_name, tool_input, agent_type=DEVELOPER, event="PreToolUse", tool_response=None):
    """hook 입력을 만듭니다.

    agent_type=None이면 메인 대화처럼 agent_type·agent_id 키 자체를 뺍니다(P0 실측 R2).
    """
    data = {
        "session_id": SESSION_ID,
        "transcript_path": TRANSCRIPT_PATH,
        "cwd": cwd,
        "prompt_id": PROMPT_ID,
        "permission_mode": "acceptEdits",
        "effort": {"level": "high"},
        "hook_event_name": event,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_use_id": "call_47f73cd5bd0849b1bbd51f7e",
    }
    if agent_type is not None:
        data["agent_id"] = AGENT_ID
        data["agent_type"] = agent_type
    if event == "PostToolUse":
        data["duration_ms"] = 5
        data["tool_response"] = tool_response if tool_response is not None else {"success": True}
    return data


def run_hook(script_path, data, env=None):
    """hook 스크립트를 실행합니다. stdin에 JSON을 넣습니다.

    env는 테스트 프로세스 환경에 덧씌웁니다(GIT_DIR 같은 환경 장애를 흉내 낼 때).
    """
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, script_path],
        input=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=merged,
        timeout=30,
    )


def run_bash(args, cwd):
    return subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def git(repo, *args):
    """테스트 저장소에서 git을 실행합니다. 실패하면 테스트를 멈춥니다."""
    proc = subprocess.run(
        ["git", "-C", repo] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
        timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError("git %s 실패: %s" % (" ".join(args), proc.stderr.decode("utf-8", "replace")))
    return proc.stdout.decode("utf-8")


def git_env():
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    return env


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def volume_is_case_insensitive(base):
    """이 볼륨이 대소문자를 무시하는지 임시 디렉터리에서 판별합니다.

    (왜: 대소문자 별칭 경로(.Env, SRC/CALC.py)의 동작은 볼륨 성질이라, 구분하는
    볼륨에서는 그 테스트를 건너뜁니다.)
    """
    probe = os.path.join(base, "ws-case-probe")
    write_file(probe, "probe\n")
    return os.path.exists(probe.upper())


def make_worktree(repo, path):
    """저장소 작업 트리 안에 중첩된 worktree를 만듭니다(격리 서브에이전트 흉내).

    (왜: 실측상 isolation: "worktree"의 서브에이전트 cwd는
    <toplevel>/.claude/worktrees/agent-* 처럼 조정자 작업 트리 안의 worktree입니다.)
    """
    os.makedirs(path, exist_ok=True)
    os.rmdir(path)  # worktree add가 최종 디렉터리를 직접 만들게 둡니다.
    git(repo, "worktree", "add", "-q", "-b", "wt-" + os.path.basename(path), path)
    return path


def make_repo(base, name, files):
    """임시 git 저장소를 만들고 fixture 파일을 커밋합니다."""
    repo = os.path.join(base, name)
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "tester")
    git(repo, "config", "commit.gpgsign", "false")
    for rel, content in files.items():
        write_file(os.path.join(repo, rel), content)
    commit_all(repo)
    return repo


def commit_all(repo):
    flags = ["-c", "user.email=test@example.com", "-c", "user.name=tester", "-c", "commit.gpgsign=false"]
    git(repo, *(flags + ["add", "-A"]))
    git(repo, *(flags + ["commit", "-q", "-m", "fixture"]))


class HookTestCase(unittest.TestCase):
    """임시 저장소를 만들고 hook의 출력을 단정하는 기본 클래스."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="work-standards-hook-test-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo = make_repo(
            self.base,
            "repo",
            {
                "src/calc.py": "def add(a, b):\n    return a + b\n",
                "tests/test_add.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            },
        )

    def write_input(self, path, agent_type=DEVELOPER, cwd=None):
        """PreToolUse(Edit) 입력을 만듭니다. 경로만 판정 대상입니다."""
        return hook_input(
            cwd or self.repo,
            "Edit",
            {"file_path": path, "old_string": "a", "new_string": "b", "replace_all": False},
            agent_type=agent_type,
        )

    def fixture(self, rel):
        """세션 저장소 기준 상대 경로를 절대 경로로 만듭니다."""
        return os.path.join(self.repo, rel)

    def protect(self, text):
        """보호 경로 목록(protected-paths)을 세션 toplevel에 씁니다."""
        write_file(os.path.join(self.repo, ".work-standards", "protected-paths"), text)

    def assert_allow(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout, b"", proc.stdout.decode("utf-8", "replace"))

    def assert_deny(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        data = json.loads(proc.stdout.decode("utf-8"))
        output = data["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertTrue(output["permissionDecisionReason"])
        return output["permissionDecisionReason"]
