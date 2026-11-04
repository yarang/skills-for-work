# -*- coding: utf-8 -*-
"""skill_log.py(H6)의 테스트와, boundary-check.sh와의 통합 확인.

스크립트를 subprocess로 실행해 stdin에 hook 입력 JSON을 넣고, 기록 파일과
종료 코드를 확인합니다. 입력은 P0 실측 기록의 줄 모양(키 집합)을 따릅니다.
"""

import json
import os
import unittest

import support

STATE_DIR = ".work-standards"


def skill_input(cwd, agent_type="work-standards:developer", skill="work-standards:python-standards", success=True):
    """PostToolUse(Skill) 입력을 만듭니다(P0 실측 R3의 입력·응답 모양)."""
    return support.hook_input(
        cwd,
        "Skill",
        {"skill": skill},
        agent_type=agent_type,
        event="PostToolUse",
        tool_response={"success": success, "commandName": skill},
    )


class SkillLogTestCase(support.HookTestCase):
    """기록 한 줄과 상태 디렉터리 준비."""

    def log_lines(self):
        path = os.path.join(self.repo, STATE_DIR, "skill-log.jsonl")
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def test_records_one_line_with_all_fields(self):
        proc = support.run_hook(support.SKILL_LOG, skill_input(self.repo, success=False))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout, b"")

        records = self.log_lines()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertRegex(record["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(record["session_id"], support.SESSION_ID)
        self.assertEqual(record["agent_id"], support.AGENT_ID)
        self.assertEqual(record["agent_type"], "work-standards:developer")
        self.assertEqual(record["skill"], "work-standards:python-standards")
        self.assertIs(record["success"], False)

    def test_creates_state_dir_with_gitignore(self):
        support.run_hook(support.SKILL_LOG, skill_input(self.repo))
        gitignore = os.path.join(self.repo, STATE_DIR, ".gitignore")
        with open(gitignore, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "*\n")

    def test_does_not_record_main_conversation(self):
        # agent_type 키가 없는 입력은 기록하지 않습니다(P0 실측 R2).
        proc = support.run_hook(support.SKILL_LOG, skill_input(self.repo, agent_type=None))
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, STATE_DIR, "skill-log.jsonl")))

    def test_ignores_non_skill_tools(self):
        data = support.hook_input(
            self.repo,
            "Edit",
            {"file_path": os.path.join(self.repo, "src/calc.py"), "old_string": "a", "new_string": "b"},
            agent_type="work-standards:developer",
            event="PostToolUse",
            tool_response={"success": True},
        )
        support.run_hook(support.SKILL_LOG, data)
        self.assertFalse(os.path.exists(os.path.join(self.repo, STATE_DIR, "skill-log.jsonl")))

    def test_missing_fields_are_null(self):
        data = skill_input(self.repo)
        del data["tool_response"]  # 응답 키가 없으면 null입니다.
        support.run_hook(support.SKILL_LOG, data)
        record = self.log_lines()[0]
        self.assertIsNone(record["success"])
        self.assertEqual(record["skill"], "work-standards:python-standards")


class BoundaryCheckIntegrationTestCase(support.HookTestCase):
    """snapshot → H6 기록 → check 가 통과하는지(「.work-standards 무시」 확인)."""

    def test_skill_log_is_invisible_to_boundary_check(self):
        snapshot = os.path.join(self.base, "h6.snap")  # 저장소 밖에 둡니다.
        taken = support.run_bash(["bash", support.BOUNDARY_CHECK, "snapshot", snapshot], cwd=self.repo)
        self.assertEqual(taken.returncode, 0, taken.stderr.decode("utf-8", "replace"))

        logged = support.run_hook(support.SKILL_LOG, skill_input(self.repo))
        self.assertEqual(logged.returncode, 0, logged.stderr.decode("utf-8", "replace"))

        # .work-standards/ 는 자체 .gitignore(*)로 무시되므로 status에 나오지 않습니다.
        status = support.git(self.repo, "status", "--porcelain")
        self.assertNotIn(STATE_DIR, status)

        checked = support.run_bash(["bash", support.BOUNDARY_CHECK, "check", snapshot], cwd=self.repo)
        self.assertEqual(checked.returncode, 0, checked.stdout.decode("utf-8", "replace"))
        output = checked.stdout.decode("utf-8", "replace")
        self.assertIn("변경 0건", output)
        self.assertIn("위반 0건", output)
        self.assertIn("결과: 통과", output)


class WorktreeStateTestCase(support.HookTestCase):
    """격리 worktree 서브에이전트의 기록 위치(cwd가 조정자 작업 트리 안의 worktree)."""

    def setUp(self):
        super().setUp()
        self.worktree = support.make_worktree(
            self.repo, os.path.join(self.repo, ".claude", "worktrees", "agent-x")
        )

    def test_writes_to_coordinator_state(self):
        # (c) 조정자 작업 트리(repo)에 .work-standards/ 가 이미 있으면 거기에 쌓입니다.
        # (왜: 곧 버려질 격리 worktree에 기록이 흩어지지 않게 합니다.)
        support.write_file(os.path.join(self.repo, ".work-standards", ".gitignore"), "*\n")
        proc = support.run_hook(support.SKILL_LOG, skill_input(self.worktree))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, STATE_DIR, "skill-log.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(self.worktree, STATE_DIR)))

    def test_falls_back_to_nearest_toplevel(self):
        # 아무 후보에도 .work-standards/ 가 없으면 세션 toplevel(여기서는 worktree)에 만듭니다.
        proc = support.run_hook(support.SKILL_LOG, skill_input(self.worktree))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertTrue(os.path.isfile(os.path.join(self.worktree, STATE_DIR, "skill-log.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, STATE_DIR)))


class FailureTestCase(support.HookTestCase):
    """H6의 내부 오류도 fail-open 계약(stderr 한 줄, exit 1)을 따릅니다."""

    def test_state_dir_seat_taken_by_file_fails_open(self):
        # 상태 디렉터리 자리에 일반 파일이 있으면 만들지 못합니다. 조용히 통과시키지
        # 않고 stderr 한 줄과 exit 1로 올립니다(차단 코드 2는 쓰지 않습니다).
        support.write_file(os.path.join(self.repo, STATE_DIR), "not a directory\n")
        proc = support.run_hook(support.SKILL_LOG, skill_input(self.repo))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"")
        self.assertTrue(proc.stderr)


if __name__ == "__main__":
    unittest.main()
