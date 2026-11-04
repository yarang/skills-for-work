#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""work-standards hook 공용 함수.

write_guard.py(H1·H2·H3)와 skill_log.py(H6)가 함께 쓰는 입력 해석, 대상
에이전트 판정, 경로 정규화, 저장소·상태 디렉터리 계산을 모읍니다. (왜: 판정
규칙을 두 스크립트가 따로 두면 한쪽만 고쳐져 같은 입력에 다른 결과가 나옵니다.)

공통 계약(docs/methodology-analysis.md §8-5):
- 대상은 agent_type이 "work-standards:"로 시작하는 서브에이전트뿐입니다.
  메인 대화의 입력에는 agent_type 키 자체가 없습니다(P0 실측 R2).
- 내부 오류는 fail-open입니다. hook은 앞단 가드레일이고 최종 판정은
  boundary-check.sh가 하므로, 여기서 세션을 멈추게 하지 않습니다(§8-3).

상태 디렉터리 찾기(2026-11-04 실측): isolation: "worktree"로 띄운 서브에이전트의
입력 cwd는 조정자 작업 트리 **안에 중첩된** worktree
(<toplevel>/.claude/worktrees/agent-*)입니다. 세션 toplevel만 보면 조정자가 쓴
.work-standards/ 를 못 찾으므로, state_candidates()가 저장소 조상 방향으로
같은 저장소(common-dir)의 toplevel을 따라 올라간 후보 목록을 만들고 두 hook은
가까운 후보부터 찾습니다.
"""

import json
import os
import subprocess
import sys

PLUGIN_PREFIX = "work-standards:"

# hook timeout이 10초이므로 git 한 번은 그 안에서 끝나야 합니다.
GIT_TIMEOUT_S = 8

# 조상 방향 후보 탐색 상한입니다. (왜: 무한 저장소 중첩에 대한 보험이고, 실제
# 중첩은 세션 toplevel + 격리 worktree 정도로 2~3이므로 절대 닿지 않습니다.)
STATE_MAX_CANDIDATES = 16


class HookError(Exception):
    """예상 못 한 내부 오류. stderr 한 줄과 exit 1(fail-open)로 처리합니다."""


def run_hook(main_fn):
    """main()을 감싸 fail-open으로 끝냅니다.

    (왜: exit 2는 도구 호출을 차단합니다. JSON 파싱 실패, git 실패, 예상 못 한
    예외는 stderr 한 줄만 남기고 exit 1로 통과시킵니다.)
    """
    try:
        main_fn()
    except HookError as exc:
        sys.stderr.write("%s: %s\n" % (main_fn.__module__, exc))
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — 예상 못 한 예외도 통과시킵니다.
        sys.stderr.write("%s: 예상 못 한 오류: %r\n" % (main_fn.__module__, exc))
        sys.exit(1)


def read_input():
    """stdin의 hook 입력 JSON을 dict로 돌려줍니다."""
    raw = sys.stdin.read()
    if not raw.strip():
        raise HookError("hook 입력이 비었습니다")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise HookError("hook 입력을 JSON으로 해석하지 못했습니다: %s" % exc)
    if not isinstance(data, dict):
        raise HookError("hook 입력이 JSON 객체가 아닙니다")
    return data


def is_plugin_agent(data):
    """work-standards 서브에이전트의 호출인지. 메인 대화는 False입니다.

    (왜: 플러그인 hook은 플러그인이 켜진 모든 세션에 걸리므로, 사용자의 다른
    작업과 메인 대화를 건드리지 않게 키가 없거나 접두사가 다르면 통과시킵니다.)
    """
    agent_type = data.get("agent_type")
    return isinstance(agent_type, str) and agent_type.startswith(PLUGIN_PREFIX)


def agent_role(data):
    """agent_type에서 플러그인 접두사를 뗀 역할 이름(developer 등)을 돌려줍니다."""
    return data["agent_type"][len(PLUGIN_PREFIX):]


def target_path(data):
    """쓰기 대상 경로(tool_input.file_path, NotebookEdit는 notebook_path).

    비었거나 없으면 None을 돌려주고, 호출자는 그대로 허용합니다.
    MultiEdit은 다른 쓰기 도구와 같은 file_path 키를 씁니다.
    """
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if data.get("tool_name") == "NotebookEdit":
        keys = ("notebook_path", "file_path")
    else:
        keys = ("file_path", "notebook_path")
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def input_cwd(data):
    """입력의 cwd를 실제 경로로 돌려줍니다. 없거나 비었으면 현재 디렉터리."""
    raw = data.get("cwd")
    if not isinstance(raw, str) or not raw.strip():
        return os.getcwd()
    return canonical_path(raw, os.getcwd())


def canonical_path(raw, cwd):
    """경로를 커널이 여는 실제 경로로 만듭니다. 아직 없는 파일도 다룹니다.

    (왜: normpath를 먼저 하면 링크 뒤의 .. 가 사라져, `link/../victim.py`를
    링크 밖이 아니라 링크 안 파일로 판정합니다. 그래서 join만 하고 3.9의
    realpath(non-strict)로 커널 순서대로 풉니다. 파일 심볼릭 링크와 끊긴 링크,
    아직 없는 구성 요소까지 풀 수 있는 만큼 풀어 돌려줍니다.)
    """
    joined = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
    return _restore_disk_case(os.path.realpath(joined))


def _restore_disk_case(path):
    """존재하는 구성 요소의 이름을 디스크 표기로 되돌립니다.

    (왜: realpath는 심볼릭 링크만 풀고 이름 표기는 입력 그대로 둡니다. macOS의
    대소문자 무시 볼륨에서 src/CALC.py 는 실제 src/calc.py 를 열므로, 정확한
    문자열 비교가 뒤따르는 git ls-files(H2 추적 판정) 앞에서 표기를 복원해야
    합니다. 존재하지 않는 꼬리 구성 요소는 입력 그대로 둡니다.)
    """
    if path == os.sep:
        return path
    names = [name for name in path.split(os.sep) if name]
    current = os.sep if path.startswith(os.sep) else ""
    for name in names:
        current = os.path.join(current, _disk_name(current, name))
    return current or path


def _disk_name(parent, name):
    """parent 안에서 name의 디스크 표기를 돌려줍니다. 못 찾으면 입력 그대로.

    (왜: 정확히 같은 이름이 있으면 그것이 진짜 표기입니다. 없을 때는 casefold가
    같은 항목이 하나뿐일 때만 갈아 엎습니다. 여러 개면 볼륨이 대소문자를
    구분하는 것이므로 입력 표기를 믿습니다.)
    """
    try:
        entries = os.listdir(parent)
    except OSError:
        return name
    if name in entries:
        return name
    folded = name.casefold()
    matches = [entry for entry in entries if entry.casefold() == folded]
    if len(matches) == 1:
        return matches[0]
    return name


def nearest_dir(path):
    """경로에서 가장 가까운 존재하는 디렉터리를 돌려줍니다."""
    cur = path
    while not os.path.isdir(cur):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return cur


def state_candidates(cwd, session=None):
    """상태 디렉터리를 찾을 후보 toplevel 목록을 가까운 순서로 돌려줍니다.

    세션 toplevel T에서 시작해, 다음 후보는 repo_info(dirname(현재 후보))의
    toplevel 중 common-dir이 세션과 같은 것입니다. 저장소가 아니거나
    common-dir이 다르면 멈춥니다. (왜: 격리 worktree의 서브에이전트는 조정자
    작업 트리의 .work-standards/ 를 써야 하는데, git이 만드는 폴더 이름
    (.claude/worktrees)에 의존하지 않고 조정자 worktree를 찾는 일반 규칙입니다.)
    """
    if session is None:
        session = repo_info(cwd)
    if session is not None:
        session_common = session["common"]
        current = session["toplevel"]
    else:
        # git 세션이 아니면 세션 루트는 cwd 자체입니다. 부모가 저장소여도
        # common-dir 비교(None)에서 어차피 멈춥니다.
        session_common = None
        current = canonical_path(cwd, cwd)
    candidates = [current]
    for _ in range(STATE_MAX_CANDIDATES):
        parent = repo_info(os.path.dirname(current))
        if parent is None or parent["common"] != session_common:
            break
        current = parent["toplevel"]
        candidates.append(current)
    return candidates


def state_dir(candidates):
    """후보 중 .work-standards/ 디렉터리가 이미 있는 첫 후보의 상태 디렉터리.

    아무 데도 없으면 첫 후보(세션 toplevel)에 만듭니다. (왜: 격리 worktree
    서브에이전트의 기록이 곧 버려질 worktree에 쌓이지 않게, 조정자가 이미
    만들어 둔 디렉터리를 우선합니다.)
    """
    for candidate in candidates:
        state = os.path.join(candidate, ".work-standards")
        if os.path.isdir(state):
            return state
    return ensure_state_dir(candidates[0])


def ensure_state_dir(session_toplevel):
    """세션 toplevel의 .work-standards/ 를 준비하고 그 경로를 돌려줍니다.

    (왜: hook이 만든 파일을 boundary-check.sh의 `git ls-files --others
    --exclude-standard`가 범위 밖 위반으로 세지 않으려면, 디렉터리 안 전체와
    .gitignore 자신을 `*` 한 줄로 무시시켜야 합니다.)
    """
    state = os.path.join(session_toplevel, ".work-standards")
    os.makedirs(state, exist_ok=True)
    gitignore = os.path.join(state, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w", encoding="utf-8") as handle:
            handle.write("*\n")
    return state


def run_git(args, cwd):
    """git을 실행합니다. 실패 메시지는 영어로 고정합니다(기록·판정용)."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    try:
        return subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=GIT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise HookError("git이 %d초 안에 끝나지 않았습니다: %s" % (GIT_TIMEOUT_S, " ".join(args)))
    except OSError as exc:
        raise HookError("git을 실행하지 못했습니다: %s" % exc)


def repo_info(directory):
    """디렉터리가 속한 저장소의 common-dir과 toplevel을 돌려줍니다.

    저장소 밖이면 None입니다. worktree 안에서는 toplevel이 그 worktree이고
    common-dir이 본 저장소의 .git이므로, common-dir로 같은 저장소를 봅니다.
    """
    out = run_git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"],
        directory,
    )
    if out.returncode == 129:
        # --path-format은 git 2.31부터입니다. 오래된 git에서는 상대 값을 절대로 바꿔 붙입니다.
        out = run_git(["rev-parse", "--git-common-dir", "--show-toplevel"], directory)
    if out.returncode == 128:
        # (왜: 128은 저장소 밖뿐 아니라 손상된 설정·소유권 거부·잘못된 GIT_DIR에서도
        # 나옵니다. 저장소 발견 걸음(부모 디렉터리 나열)이 실패한 것만 「저장소
        # 아님」의 폴백 정책으로 보고, 나머지는 판정을 git 실패로 흐리지 않게
        # HookError(fail-open exit 1)로 올립니다.)
        message = first_line(out.stderr)
        folded = message.casefold()
        if "not a git repository" in folded and "(or any of the parent directories)" in folded:
            return None
        raise HookError("git rev-parse 실패: %s" % message)
    if out.returncode != 0:
        raise HookError("git rev-parse 실패: %s" % first_line(out.stderr))
    lines = [line for line in out.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if len(lines) < 2:
        raise HookError("git rev-parse 출력이 예상과 다릅니다")
    return {
        "common": canonical_path(lines[-2], directory),
        "toplevel": canonical_path(lines[-1], directory),
    }


def build_context(data, raw_path, target=None):
    """쓰기 판정에 필요한 경로·저장소 정보를 한 번에 계산합니다.

    same: 대상이 세션과 같은 저장소인지. rel: 대상 저장소 toplevel 기준 상대 경로.
    target은 호출자가 이미 canonical_path로 푼 대상 경로입니다(write_guard가
    .git 구성 요소 검사를 저장소 판정보다 먼저 하고 넘겨줍니다).
    """
    cwd = input_cwd(data)
    if target is None:
        target = canonical_path(raw_path, cwd)
    session = repo_info(cwd)
    if session is None:
        # cwd가 git 저장소가 아니면 세션 루트를 cwd로 봅니다.
        session_toplevel = cwd
        session_common = cwd
        in_git = False
    else:
        session_toplevel = session["toplevel"]
        session_common = session["common"]
        in_git = True
    same, target_toplevel, rel = _resolve_target(target, in_git, session_common, session_toplevel)
    return {
        "cwd": cwd,
        "target": target,
        "in_git": in_git,
        "session": session,
        "session_toplevel": session_toplevel,
        "session_common": session_common,
        "target_toplevel": target_toplevel,
        "same": same,
        "rel": rel,
    }


def _resolve_target(target, in_git, session_common, session_toplevel):
    """대상이 세션과 같은 저장소인지와 대상 toplevel 기준 상대 경로를 돌려줍니다."""
    if not in_git:
        same = _under(target, session_toplevel)
        return same, (session_toplevel if same else None), (_rel(target, session_toplevel) if same else None)
    target_repo = repo_info(nearest_dir(target))
    if target_repo is None:
        return False, None, None
    # common-dir이 같으면 같은 저장소입니다. 병렬 실행의 worktree는
    # toplevel이 달라도 common-dir이 같으므로 통과시킵니다.
    if target_repo["common"] != session_common:
        return False, None, None
    return True, target_repo["toplevel"], _rel(target, target_repo["toplevel"])


def first_line(text):
    """실패 메시지의 첫 줄만 떼어 냅니다(기록용)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return "(이유 없음)"


def _under(path, root):
    """path가 root와 같거나 그 아래에 있는지."""
    return path == root or path.startswith(root + os.sep)


def _rel(path, root):
    """루트 기준 상대 경로. 구분자는 / 로 통일합니다."""
    return os.path.relpath(path, root).replace(os.sep, "/")
