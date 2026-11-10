# -*- coding: utf-8 -*-
"""verify.sh·boundary-check.sh의 bun 잠금 파일 지원 테스트.

가짜 패키지 매니저 실행 파일을 PATH 앞에 두고 verify.sh를 실행해, 어떤 명령이
불렸는지 로그로 확인합니다. boundary-check.sh는 스크립트 사용법(snapshot →
check)대로 직접 호출해 bun.lock 보호를 확인합니다. 표준 라이브러리와 pytest만
씁니다.
"""

import os
import subprocess

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFY_DIR = os.path.dirname(TESTS_DIR)  # skills/verify
SKILLS_DIR = os.path.dirname(VERIFY_DIR)  # skills
VERIFY_SH = os.path.join(VERIFY_DIR, "scripts", "verify.sh")
BOUNDARY_CHECK = os.path.join(SKILLS_DIR, "dev-workflow", "scripts", "boundary-check.sh")

PACKAGE_JSON = (
    '{"name": "fixture", "scripts": {"typecheck": "tsc --noEmit", '
    '"lint": "eslint .", "test": "vitest run"}}\n'
)

# scripts에 test가 없는 package.json: 스크립트 존재 확인(건너뜀) 분기 검증용.
PACKAGE_JSON_NO_TEST = (
    '{"name": "fixture", "scripts": {"typecheck": "tsc --noEmit", '
    '"lint": "eslint ."}}\n'
)


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


# 가짜 패키지 매니저 실행 파일(python3). 호출을 $CALLS_LOG에 한 줄로 남깁니다.
# -e <코드>로 불리면 verify.sh의 스크립트 존재 확인(probe)이므로, 코드에 든 스크립트
# 이름(s['<이름>'])을 뽑아 현재 디렉터리 package.json의 scripts에 있으면 0, 없으면 1을
# 돌려줍니다. 그 밖의 호출(bun run test 등)은 언제나 0입니다.
FAKE_BIN = r'''#!/usr/bin/env python3
import json
import os
import re
import sys

name = os.path.basename(sys.argv[0])
with open(os.environ["CALLS_LOG"], "a", encoding="utf-8") as handle:
    handle.write(name + " " + " ".join(sys.argv[1:]) + "\n")

args = sys.argv[1:]
if len(args) >= 2 and args[0] == "-e":
    match = re.search(r"s\['([^']+)'\]", args[1])
    if match:
        try:
            with open("package.json", encoding="utf-8") as handle:
                scripts = json.load(handle).get("scripts") or {}
        except (OSError, ValueError):
            sys.exit(1)
        sys.exit(0 if match.group(1) in scripts else 1)
sys.exit(0)
'''

# 호출되면 호출 로그에 한 줄 남기고 exit 1 하는 가짜 실행 파일. verify.sh이 그
# 도구를 절대 불러서는 안 된다는 것을, "불렸다면 로그에 흔적이 남는다"로 잡을 때 씁니다.
FAIL_BIN = r'''#!/usr/bin/env python3
import os
import sys

with open(os.environ["CALLS_LOG"], "a", encoding="utf-8") as handle:
    handle.write(os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]) + "\n")
sys.exit(1)
'''


class FakePM:
    """가짜 패키지 매니저 실행 파일과 호출 로그."""

    # names: 만들 가짜 실행 파일 이름. failing: 그중 호출되면 로그만 남기고
    # exit 1 하는 파일(FAKE_BIN 대신 FAIL_BIN으로 만듦).
    def __init__(self, base, names, failing=()):
        self.bin_dir = os.path.join(str(base), "fake-bin")
        self.log = os.path.join(str(base), "calls.log")
        os.makedirs(self.bin_dir)
        for name in names:
            script = os.path.join(self.bin_dir, name)
            write_file(script, FAIL_BIN if name in failing else FAKE_BIN)
            os.chmod(script, 0o755)

    def run_verify(self, target):
        env = dict(os.environ)
        env["PATH"] = self.bin_dir + os.pathsep + "/usr/bin:/bin:/usr/sbin:/sbin"
        env["CALLS_LOG"] = self.log
        return subprocess.run(
            ["/bin/bash", VERIFY_SH, str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=120,
        )

    def calls(self):
        # 도구가 한 번도 불리지 않으면 로그 파일이 없습니다.
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().splitlines()


def test_bun_lock_runs_bun_run_test(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(pkg, "bun.lock"), "# bun lock\n")
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    assert "bun run test" in calls
    # bun이면 node가 없어도 되므로 node를 부르지 않습니다(있는 것은 bun만 확인).
    assert not [c for c in calls if c.startswith("node")]
    # package.json 스크립트 존재 확인도 bun -e로 합니다.
    assert any(c.startswith("bun -e ") for c in calls)
    assert "건너뜀" not in output


def test_bun_lockb_runs_bun_run_test(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(pkg, "bun.lockb"), "# bun lock (binary 자리)\n")
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    assert "bun run test" in calls
    assert not [c for c in calls if c.startswith("node")]


def test_bun_lock_without_bun_skips_as_bun(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(pkg, "bun.lock"), "# bun lock\n")
    pm = FakePM(tmp_path, ("node", "npm", "pnpm"))  # PATH에 bun이 없습니다.
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    # skip도 차단하는 임시 기본 정책이므로 종료 코드는 1입니다.
    assert proc.returncode == 1, output
    # 검사 이름이 node가 아니라 bun으로 기록되어야 합니다.
    assert "건너뜀: bun — bun이 없음" in output
    assert "건너뜀: node" not in output
    # bun이 없으면 어떤 패키지 매니저도 부르지 않습니다.
    assert pm.calls() == []


def test_bun_lock_with_node_on_path_still_runs_bun(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(pkg, "bun.lock"), "# bun lock\n")
    # 시스템 node가 PATH에 있어도 전제가 깨지지 않게, 호출되면 로그를 남기고
    # exit 1 하는 가짜 node를 PATH 앞에 둡니다. bun 분기가 node를 불렀다면
    # 로그에 흔적이 남고 검사도 실패합니다.
    pm = FakePM(tmp_path, ("bun", "node"), failing=("node",))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    assert "bun run test" in calls
    # node 호출 로그가 비어 있어야 합니다(bun 분기는 node를 부르지 않음).
    assert not [c for c in calls if c.startswith("node")]
    assert "건너뜀" not in output


def test_bun_lock_without_test_script_skips_bun_run_test(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON_NO_TEST)
    write_file(os.path.join(pkg, "bun.lock"), "# bun lock\n")
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    # 있는 스크립트(typecheck, lint)는 실행하고, test는 건너뜁니다.
    # skip도 차단하는 임시 기본 정책이므로 종료 코드는 1입니다.
    assert proc.returncode == 1, output
    calls = pm.calls()
    assert "bun run typecheck" in calls
    assert "bun run test" not in calls
    assert "건너뜀" in output
    assert "test 스크립트가 없음" in output


def test_child_package_lock_wins_over_parent_bun_lock(tmp_path):
    parent = os.path.join(str(tmp_path), "repo")
    child = os.path.join(parent, "pkg")
    write_file(os.path.join(parent, "bun.lock"), "# bun lock\n")
    write_file(os.path.join(child, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(child, "package-lock.json"), "# npm lock\n")
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(child)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    # 가장 가까운 잠금 파일(하위의 package-lock.json)이 이깁니다.
    assert "npm run test" in calls
    assert not [c for c in calls if c.startswith("bun ")]


def test_no_lock_file_uses_npm_as_before(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    assert "npm run test" in calls
    assert not [c for c in calls if c.startswith(("pnpm ", "yarn ", "bun "))]


def test_bun_lock_wins_over_npm_pnpm_locks_in_same_dir(tmp_path):
    pkg = os.path.join(str(tmp_path), "pkg")
    write_file(os.path.join(pkg, "package.json"), PACKAGE_JSON)
    write_file(os.path.join(pkg, "bun.lock"), "# bun lock\n")
    write_file(os.path.join(pkg, "package-lock.json"), "# npm lock\n")
    write_file(os.path.join(pkg, "pnpm-lock.yaml"), "# pnpm lock\n")
    pm = FakePM(tmp_path, ("bun", "node", "npm", "pnpm"))
    proc = pm.run_verify(pkg)
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    calls = pm.calls()
    # 같은 디렉터리에 잠금 파일이 여럿이면 bun → pnpm → yarn → npm 순서로 bun이 이깁니다.
    assert "bun run test" in calls
    assert not [c for c in calls if c.startswith(("npm ", "pnpm "))]


@pytest.mark.parametrize("lock_name", ["bun.lock", "bun.lockb"])
def test_boundary_check_blocks_bun_lock_change(tmp_path, lock_name):
    repo = os.path.join(str(tmp_path), "repo")
    write_file(os.path.join(repo, "pkg", "package.json"), PACKAGE_JSON)
    write_file(os.path.join(repo, "pkg", lock_name), "# lock v1\n")
    write_file(os.path.join(repo, "pkg", "src", "main.js"), "export function main() {\n  return 1;\n}\n")

    def git(*args):
        subprocess.run(
            ["git", "-C", repo] + list(args),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )

    def run_bc(*args):
        return subprocess.run(
            ["/bin/bash", BOUNDARY_CHECK] + list(args),
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "tester")
    git("config", "commit.gpgsign", "false")
    git("add", "-A")
    git("commit", "-q", "-m", "fixture")

    # 스냅숏 파일은 저장소 밖에 둡니다(스크립트 사용법).
    snap = os.path.join(str(tmp_path), "outside.snap")
    assert run_bc("snapshot", snap).returncode == 0

    write_file(os.path.join(repo, "pkg", lock_name), "# lock v2\n")

    # 행 디렉터리 안의 변경이므로 --allow만으로는 통과합니다.
    allowed = run_bc("check", snap, "--allow=pkg")
    assert allowed.returncode == 0, allowed.stdout.decode("utf-8", "replace")

    # 잠금 파일을 --protect에 넣으면 보호 경로 위반(block)으로 판정합니다.
    blocked = run_bc("check", snap, "--allow=pkg", "--protect=pkg/" + lock_name)
    output = blocked.stdout.decode("utf-8", "replace")
    assert blocked.returncode == 1, output
    assert "보호 경로" in output
    assert "pkg/" + lock_name in output
