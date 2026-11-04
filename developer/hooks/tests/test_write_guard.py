# -*- coding: utf-8 -*-
"""write_guard.py(H1·H2·H3)의 테스트.

스크립트를 subprocess로 실행해 stdin에 hook 입력 JSON을 넣고, 출력과 종료
코드를 확인합니다. 입력은 P0 실측 기록의 줄 모양(키 집합)을 따릅니다.
"""

import os
import subprocess
import sys
import unittest

import support
import write_guard


class GateTestCase(support.HookTestCase):
    """대상 판정(공통 계약): 검사 대상이 아니면 아무것도 출력하지 않습니다."""

    def test_main_conversation_without_agent_type_key_passes(self):
        # 메인 대화의 입력에는 agent_type 키 자체가 없습니다(P0 실측 R2).
        for agent_type in (None, "claude:some-agent"):
            proc = support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py"), agent_type))
            self.assert_allow(proc)

    def test_other_work_standards_roles_pass(self):
        # H5(reviewer·researcher의 쓰기 차단)는 P2 항목이라 지금은 통과입니다.
        proc = support.run_hook(
            support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py"), agent_type="work-standards:reviewer")
        )
        self.assert_allow(proc)

    def test_write_input_without_file_path_passes(self):
        data = support.hook_input(self.repo, "Edit", {"old_string": "a", "new_string": "b"})
        self.assert_allow(support.run_hook(support.WRITE_GUARD, data))

    def test_deny_output_is_valid_json_with_korean_reason(self):
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(".env"))))
        self.assertIn("H3", reason)
        self.assertIn(".env", reason)

    def test_broken_json_fails_open_with_exit_1(self):
        # exit 2는 도구 호출을 차단하므로 쓰지 않습니다(fail-open).
        proc = subprocess.run(
            [sys.executable, support.WRITE_GUARD],
            input=b"{not json",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"")
        self.assertTrue(proc.stderr)


class H3TestCase(support.HookTestCase):
    """H3 공통 불변식(developer·tester)."""

    def test_denies_absolute_path_outside_repository(self):
        outside = os.path.join(self.base, "outside.txt")
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(outside)))

    def test_denies_dotdot_escape(self):
        path = os.path.join(self.repo, "src", "..", "..", "outside.txt")
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))
        self.assertIn("저장소 밖", reason)

    def test_denies_directory_symlinked_outside(self):
        # 저장소 안의 디렉터리 심볼릭 링크로 저장소 밖을 가리킵니다.
        os.symlink(self.base, os.path.join(self.repo, "escape"))
        path = os.path.join(self.repo, "escape", "secret.txt")
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))

    def test_denies_git_internal_config(self):
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(".git/config"))))

    def test_denies_nested_git_directory(self):
        # 커밋되지 않은 중첩 저장소 흉내입니다.
        os.makedirs(os.path.join(self.repo, "pkg", ".git"), exist_ok=True)
        path = self.fixture("pkg/.git/config")
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))

    def test_denies_hook_state_directory(self):
        path = self.fixture(".work-standards/protected-paths")
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))
        self.assertIn(".work-standards", reason)

    def test_denies_env_files_and_allows_examples(self):
        for name in (".env", ".env.local"):
            self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(name))))
        self.assert_allow(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(".env.example"))))

    def test_applies_to_tester_too(self):
        self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(".env"), agent_type=support.TESTER))
        )

    def test_allows_worktree_of_same_repository(self):
        # 병렬 실행의 worktree: toplevel은 다르지만 common-dir이 같으므로 허용입니다.
        worktree = os.path.join(self.base, "repo-wt")
        support.git(self.repo, "worktree", "add", "-q", "-b", "wt-row", worktree)
        proc = support.run_hook(support.WRITE_GUARD, self.write_input(os.path.join(worktree, "src/calc.py")))
        self.assert_allow(proc)

    def test_denies_other_repository(self):
        other = support.make_repo(self.base, "other", {"src/other.py": "x = 1\n"})
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(os.path.join(other, "src/other.py"))))

    def test_non_git_session_allows_target_under_cwd_and_denies_outside(self):
        plain = os.path.join(self.base, "plain")
        os.makedirs(plain, exist_ok=True)
        self.assert_allow(
            support.run_hook(support.WRITE_GUARD, self.write_input(os.path.join(plain, "note.txt"), cwd=plain))
        )
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.repo, cwd=plain)))


class H1TestCase(support.HookTestCase):
    """H1 developer의 보호 경로(protected-paths)."""

    def test_passes_without_protected_paths_file(self):
        # developer의 새 단위 테스트는 목록과 무관하게 통과입니다.
        self.assert_allow(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/unit/test_new.py"))))

    def test_denies_protected_file(self):
        self.protect("# 인수 테스트\n\ntests/test_add.py\n")
        path = self.fixture("tests/test_add.py")
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))
        self.assertIn("H1", reason)
        self.assertIn("계약 문제", reason)

    def test_denies_file_under_protected_directory(self):
        self.protect("tests/integration/\n")
        path = self.fixture("tests/integration/test_flow.py")
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))

    def test_ignores_prefix_only_match(self):
        # tests/acc 는 tests/accx.py 를 거부하지 않습니다(경로 구성 요소 경계).
        self.protect("tests/acc\n")
        self.assert_allow(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/accx.py"))))

    def test_strips_comment_blank_line_dot_slash_and_trailing_slash(self):
        self.protect("\n# 행 밖 잠금 파일\n./src/calc.py\n\ntests/spec/\n")
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py"))))
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/spec/test_x.py"))))

    def test_does_not_apply_to_tester(self):
        # H1은 developer 전용입니다. tester의 새 파일은 H2 정책(새 파일 허용)으로 판정합니다.
        self.protect("src/stub.py\n")
        proc = support.run_hook(
            support.WRITE_GUARD, self.write_input(self.fixture("src/stub.py"), agent_type=support.TESTER)
        )
        self.assert_allow(proc)


class H2TestCase(support.HookTestCase):
    """H2 tester의 쓰기 범위."""

    def test_allows_tracked_test_directory_paths(self):
        # git이 추적 중인 테스트 파일도 고칠 수 있습니다.
        path = self.fixture("tests/test_add.py")
        proc = support.run_hook(support.WRITE_GUARD, self.write_input(path, agent_type=support.TESTER))
        self.assert_allow(proc)

    def test_allows_tracked_test_file_names_outside_test_directories(self):
        # 디렉터리가 아니라 파일 이름 규칙으로 테스트 경로로 봅니다.
        names = ("test_root.py", "run_test.go", "conftest.py", "src/runner.test.js", "src/app.spec.tsx")
        for name in names:
            support.write_file(self.fixture(name), "fixture\n")
        support.commit_all(self.repo)
        for name in names:
            proc = support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(name), agent_type=support.TESTER))
            self.assert_allow(proc)

    def test_denies_tracked_implementation_file(self):
        path = self.fixture("src/calc.py")
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(path, agent_type=support.TESTER))
        )
        self.assertIn("H2", reason)
        self.assertIn("빈 껍데기", reason)

    def test_allows_new_stub_file(self):
        # 계약 시그니처 그대로의 빈 껍데기(새 파일)는 허용입니다.
        path = self.fixture("src/stub.py")
        proc = support.run_hook(support.WRITE_GUARD, self.write_input(path, agent_type=support.TESTER))
        self.assert_allow(proc)

    def test_does_not_apply_to_developer(self):
        # developer의 구현 파일 수정은 H1(보호 목록)으로만 판정합니다.
        proc = support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py")))
        self.assert_allow(proc)


class CanonicalPathTestCase(support.HookTestCase):
    """파일 심볼릭 링크·끊긴 링크·링크 뒤의 .. (정규화는 커널 순서대로)."""

    def test_denies_file_symlink_to_outside_file(self):
        outside = os.path.join(self.base, "outside", "secret.py")
        support.write_file(outside, "x = 1\n")
        os.symlink(outside, self.fixture("link.py"))
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("link.py"))))

    def test_denies_dangling_symlink_outside(self):
        # 끊긴 링크라도 대상이 저장소 밖이면 같은 판정입니다(그 자리에 만들어질 파일).
        os.symlink(os.path.join(self.base, "gone", "x.txt"), self.fixture("dangling.py"))
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("dangling.py"))))

    def test_denies_symlink_to_env_file(self):
        # src/e -> ../.env : 이름은 평범해도 실제 대상은 비밀값 파일입니다.
        os.symlink(os.path.join("..", ".env"), self.fixture("src/e"))
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/e"))))
        self.assertIn(".env", reason)

    def test_denies_symlink_to_protected_test_for_developer(self):
        self.protect("tests/acc/test_a.py\n")
        os.symlink(os.path.join("..", "tests", "acc", "test_a.py"), self.fixture("src/link.py"))
        self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/link.py"))))

    def test_denies_test_named_symlink_to_tracked_code_for_tester(self):
        # 테스트 이름의 링크로 추적 중인 구현 파일을 겨냥합니다(H2 우회).
        os.symlink(os.path.join("..", "src", "calc.py"), self.fixture("tests/test_link.py"))
        self.assert_deny(support.run_hook(
            support.WRITE_GUARD, self.write_input(self.fixture("tests/test_link.py"), agent_type=support.TESTER)
        ))

    def test_denies_dotdot_after_symlink_outside(self):
        # repo/link -> <밖>/sub 일 때 link/../victim.py 는 커널이 <밖>/victim.py 로 엽니다.
        # normpath를 먼저 하면 repo/victim.py 로 줄어들어 허용되던 경우입니다.
        sub = os.path.join(self.base, "outside", "sub")
        os.makedirs(sub, exist_ok=True)
        os.symlink(sub, self.fixture("link"))
        path = self.fixture("link/../victim.py")
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))
        self.assertIn("저장소 밖", reason)

    def test_allows_lexical_dotdot_inside_repository(self):
        # src/../src/a.py 는 실제로 저장소 안이므로 허용입니다(거짓 거부 금지).
        path = self.fixture("src/../src/a.py")
        self.assert_allow(support.run_hook(support.WRITE_GUARD, self.write_input(path)))


class WorktreeStateTestCase(support.HookTestCase):
    """격리 worktree 서브에이전트: cwd가 조정자 작업 트리 안에 중첩된 worktree."""

    def setUp(self):
        super().setUp()
        self.worktree = support.make_worktree(
            self.repo, os.path.join(self.repo, ".claude", "worktrees", "agent-x")
        )

    def write_in_worktree(self, rel, agent_type=support.DEVELOPER):
        return support.run_hook(
            support.WRITE_GUARD,
            self.write_input(os.path.join(self.worktree, rel), agent_type=agent_type, cwd=self.worktree),
        )

    def test_h1_reads_coordinator_list_when_only_repo_has_it(self):
        # (a) protected-paths가 repo(조정자 작업 트리)에만 있어도, worktree 안의
        # 보호 경로 쓰기는 거부입니다. 목록이 없어 조용히 통과하던 허점입니다.
        self.protect("src/calc.py\n")
        reason = self.assert_deny(self.write_in_worktree("src/calc.py"))
        self.assertIn("H1", reason)

    def test_worktree_own_list_wins(self):
        # (b) 후보 중 가까운 worktree 자신의 목록이 우선합니다.
        support.write_file(os.path.join(self.worktree, ".work-standards", "protected-paths"), "src/calc.py\n")
        self.protect("tests/test_add.py\n")
        self.assert_deny(self.write_in_worktree("src/calc.py"))
        # repo 목록에만 있는 경로는 이 목록으로 막히지 않습니다(우선의 증거).
        self.assert_allow(self.write_in_worktree("tests/test_add.py"))

    def test_plain_write_in_worktree_passes(self):
        self.protect("tests/test_add.py\n")
        self.assert_allow(self.write_in_worktree("src/new_impl.py"))

    def test_tester_in_worktree_keeps_h2_against_worktree_toplevel(self):
        # H2의 추적 판정은 대상 worktree의 toplevel을 씁니다.
        self.assert_deny(self.write_in_worktree("src/calc.py", agent_type=support.TESTER))
        self.assert_allow(self.write_in_worktree("src/stub.py", agent_type=support.TESTER))


class GitFailureTestCase(support.HookTestCase):
    """git 발견 실패는 판정으로 흐리지 않고 fail-open(exit 1)으로 올립니다."""

    def assert_fails_open(self, proc):
        self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout, b"")
        self.assertTrue(proc.stderr)

    def test_corrupted_session_config_fails_open(self):
        # (세션 쪽) 손상된 .git/config: rev-parse가 128로 끝나지만 「저장소 아님」이 아닙니다.
        support.write_file(self.fixture(".git/config"), "this is not a config\n[[\n")
        self.assert_fails_open(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py")))
        )

    def test_corrupted_target_repo_config_fails_open(self):
        # (대상 쪽) 대상이 속한 중첩 저장소의 설정이 망가졌으면 대상 저장소 판정이 실패합니다.
        nested = os.path.join(self.repo, "vendor", "pkg")
        os.makedirs(nested, exist_ok=True)
        support.git(nested, "init", "-q")
        support.write_file(os.path.join(nested, ".git", "config"), "broken\n[[\n")
        self.assert_fails_open(
            support.run_hook(support.WRITE_GUARD, self.write_input(os.path.join(nested, "newfile.py")))
        )

    def test_bogus_git_dir_env_fails_open(self):
        # GIT_DIR이 잘못됐으면 git 발견이 전부 실패합니다. 「저장소 아님」 폴백 정책으로
        # 흐리지 않고 HookError(exit 1)로 올립니다.
        proc = support.run_hook(
            support.WRITE_GUARD,
            self.write_input(self.fixture("src/calc.py")),
            env={"GIT_DIR": os.path.join(self.base, "no-such-dir")},
        )
        self.assert_fails_open(proc)


class InputShapeTestCase(support.HookTestCase):
    """MultiEdit(file_path + edits)·NotebookEdit(notebook_path) 입력 모양."""

    def multi_edit_input(self, path):
        return support.hook_input(
            self.repo,
            "MultiEdit",
            {"file_path": path, "edits": [{"old_string": "a", "new_string": "b", "replace_all": False}]},
        )

    def notebook_input(self, path):
        return support.hook_input(
            self.repo,
            "NotebookEdit",
            {"notebook_path": path, "cell_id": "cell-1", "new_source": "print(1)"},
        )

    def test_multi_edit_on_protected_path_denied(self):
        self.protect("tests/test_add.py\n")
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.multi_edit_input(self.fixture("tests/test_add.py")))
        )
        self.assertIn("H1", reason)

    def test_multi_edit_on_plain_path_passes(self):
        self.assert_allow(
            support.run_hook(support.WRITE_GUARD, self.multi_edit_input(self.fixture("src/calc.py")))
        )

    def test_notebook_edit_inside_git_denied(self):
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.notebook_input(self.fixture(".git/config")))
        )
        self.assertIn("git 내부", reason)

    def test_notebook_edit_on_protected_path_denied(self):
        self.protect("tests/integration\n")
        self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.notebook_input(self.fixture("tests/integration/flow.ipynb")))
        )


class NestedRepoTestCase(support.HookTestCase):
    """중첩 저장소와 서브모듈: common-dir이 다르면 같은 저장소가 아닙니다."""

    def test_denies_untracked_nested_repository(self):
        # 커밋되지 않은 실제 중첩 저장소입니다(빈 .git 디렉터리 흉내가 아님).
        nested = os.path.join(self.repo, "vendor", "pkg")
        os.makedirs(nested, exist_ok=True)
        support.git(nested, "init", "-q")
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(os.path.join(nested, "calc.py")))
        )
        self.assertIn("저장소 밖", reason)

    def test_denies_write_in_submodule(self):
        child = support.make_repo(self.base, "child", {"calc.py": "x = 1\n"})
        support.git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", child, "sub")
        reason = self.assert_deny(support.run_hook(
            support.WRITE_GUARD, self.write_input(self.fixture("sub/calc.py"), agent_type=support.TESTER)
        ))
        self.assertIn("저장소 밖", reason)

    def test_denies_submodule_git_file_target(self):
        # 서브모듈의 .git은 파일입니다. 이 대상도 .git 구성 요소 검사로 막힙니다.
        child = support.make_repo(self.base, "child2", {"calc.py": "x = 1\n"})
        support.git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", child, "sub2")
        self.assertTrue(os.path.isfile(self.fixture("sub2/.git")))
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("sub2/.git/config")))
        )
        self.assertIn("git 내부", reason)


class ProtectEntryTestCase(support.HookTestCase):
    """보호 항목 표현: '.', './', 절대 루트는 전체 보호(boundary-check.sh와 같게)."""

    def test_root_entries_protect_everything(self):
        for text in (".\n", "./\n", self.repo + "\n"):
            self.protect(text)
            self.assert_deny(
                support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("src/calc.py")))
            )
            self.assert_deny(
                support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/test_add.py")))
            )
            self.protect("")  # 다음 반복을 위해 목록을 비웁니다.

    def test_symlinked_dir_entry_protects_both_names(self):
        # 항목이 심볼릭 링크 이름이면, 적힌 이름과 풀린 실제 디렉터리를 모두 보호합니다.
        os.makedirs(self.fixture("tests/acceptance"), exist_ok=True)
        os.symlink(os.path.join("tests", "acceptance"), self.fixture("acceptance"))
        self.protect("acceptance\n")
        self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("acceptance/test_login.py")))
        )
        self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/acceptance/test_login.py")))
        )

    def test_paths_outside_the_entry_still_pass(self):
        os.makedirs(self.fixture("tests/acceptance"), exist_ok=True)
        os.symlink(os.path.join("tests", "acceptance"), self.fixture("acceptance"))
        self.protect("acceptance\n")
        self.assert_allow(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("tests/test_add.py")))
        )


class CaseAliasTestCase(support.HookTestCase):
    """대소문자 무시 볼륨의 별칭 경로(구분하는 볼륨에서는 건너뜁니다)."""

    def setUp(self):
        super().setUp()
        if not support.volume_is_case_insensitive(self.base):
            self.skipTest("대소문자를 구분하는 볼륨입니다")

    def test_denies_env_case_aliases(self):
        for name in (".Env", ".ENV.local"):
            self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(name))))
        # 허용 예외도 대소문자와 무관하게 허용됩니다.
        self.assert_allow(support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture(".ENV.EXAMPLE"))))

    def test_denies_state_dir_case_alias(self):
        path = self.fixture(".WORK-STANDARDS/protected-paths")
        reason = self.assert_deny(support.run_hook(support.WRITE_GUARD, self.write_input(path)))
        self.assertIn(".WORK-STANDARDS/protected-paths", reason)

    def test_denies_protected_path_case_variant(self):
        self.protect("src/calc.py\n")
        reason = self.assert_deny(
            support.run_hook(support.WRITE_GUARD, self.write_input(self.fixture("SRC/CALC.py")))
        )
        self.assertIn("H1", reason)

    def test_tester_case_alias_of_tracked_file_denied(self):
        # 디스크 표기를 복원해 추적 판정을 정확히 합니다(SRC/CALC.py → src/calc.py).
        self.assert_deny(support.run_hook(
            support.WRITE_GUARD, self.write_input(self.fixture("SRC/CALC.py"), agent_type=support.TESTER)
        ))


class CaseFoldComparisonTestCase(support.HookTestCase):
    """거부 쪽 casefold 비교 자체(볼륨 성질과 무관한 단위 검사)."""

    def test_h3_denies_case_aliases(self):
        for rel in (".Env", ".ENV.local", ".WORK-STANDARDS/protected-paths", ".Work-Standards/skill-log.jsonl"):
            self.assertTrue(write_guard.h3_violation({"same": True, "rel": rel}), rel)

    def test_h3_allows_env_examples_case_insensitively(self):
        for rel in (".ENV.EXAMPLE", ".Env.Sample", ".env.template"):
            self.assertIsNone(write_guard.h3_violation({"same": True, "rel": rel}), rel)

    def test_h3_git_component_is_casefold(self):
        for target in ("/repo/.GIT/config", "/repo/pkg/.Git/hooks/x", "/wt/.git"):
            self.assertTrue(write_guard.h3_git_target(target), target)
        self.assertIsNone(write_guard.h3_git_target("/repo/src/gitignore"))

    def test_match_protected_is_casefold_with_component_boundary(self):
        entries = ["tests/Acc", "src/calc.py"]
        self.assertEqual(write_guard.match_protected("TESTS/ACC/x.py", entries), "tests/Acc")
        self.assertEqual(write_guard.match_protected("SRC/CALC.py", entries), "src/calc.py")
        self.assertIsNone(write_guard.match_protected("tests/accx.py", entries))


if __name__ == "__main__":
    unittest.main()
