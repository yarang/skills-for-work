#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""write_guard.py — developer·tester·documenter의 파일 쓰기를 도구 호출 전에 검사합니다 (H1·H2·H3·H7).

PreToolUse(Write|Edit|MultiEdit|NotebookEdit)에서 실행됩니다.

- H3 공통 불변식(developer·tester·documenter): .git/ 내부, 저장소 밖, .work-standards/, .env.
  documenter만 .work-standards/kb-outbox/ 아래를 예외로 허용합니다(지식 저장소 초안).
- H1 보호 경로(developer): .work-standards/protected-paths 의 경로. 격리
  worktree 서브에이전트는 후보(가까운 toplevel부터)를 따라 조정자 작업 트리의
  목록을 찾습니다(_common.state_candidates 참고).
- H2 쓰기 범위(tester): 테스트 경로 밖에서 git이 이미 추적 중인 파일
- H7 쓰기 범위(documenter): README·CHANGELOG·MANUAL로 시작하는 파일(대소문자·
  확장자 무관, 어느 디렉터리든), docs/ 아래(단 docs/designs/ 는 거부),
  .work-standards/kb-outbox/ 아래만 허용하고 그 밖의 모든 경로는 거부합니다.

거부는 stdout의 JSON(permissionDecision: deny)으로 하고 exit 0으로 끝냅니다.
거부 이유는 서브에이전트가 읽고 행동을 바꿀 수 있게 규칙·경로·대신할 행동을
적습니다. 허용은 출력 없이 exit 0입니다. 내부 오류는 fail-open(_common 참고)이고,
최종 판정은 skills/dev-workflow/scripts/boundary-check.sh가 합니다(§8-3).
문서: docs/methodology-analysis.md §8-4.
"""

import json
import os
import sys

import _common

WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# H1·H2·H7의 대상 역할입니다. H5(reviewer·researcher의 쓰기 차단)는 P2 항목이라 여기에 없습니다.
ROLES = ("developer", "tester", "documenter")

# 예시용으로 허용되는 .env 계열 이름입니다. 거부 판정이 casefold 비교이므로 같은
# 방식으로 내려 둡니다.
ENV_ALLOWED = (".env.example", ".env.sample", ".env.template")
ENV_ALLOWED_FOLDED = tuple(name.casefold() for name in ENV_ALLOWED)

# H7에서 문서 파일로 보는 이름 접두사입니다(대소문자 무시, 확장자 무관).
DOC_NAME_PREFIXES = ("readme", "changelog", "manual")

# documenter가 H3(.work-standards/)의 예외로 쓸 수 있는 초안 디렉터리입니다.
KB_OUTBOX = ".work-standards/kb-outbox"

TEST_DIRS = ("tests", "test", "__tests__", "spec", "testdata", "e2e")
TEST_EXTS = ("js", "jsx", "ts", "tsx", "mjs", "cjs")


def main():
    data = _common.read_input()
    if not _common.is_plugin_agent(data):
        return  # 메인 대화와 다른 플러그인의 호출은 검사하지 않습니다.
    tool_name = data.get("tool_name")
    if tool_name is not None and tool_name not in WRITE_TOOLS:
        return  # 매처가 걸러 주지만, 모양이 다른 입력은 조용히 통과시킵니다.
    if data.get("hook_event_name") != "PreToolUse":
        return
    role = _common.agent_role(data)
    if role not in ROLES:
        return
    reason = judge(data, role)
    if reason:
        deny(reason)


def judge(data, role):
    """거부 이유를 판정합니다. 허용이면 None을 돌려줍니다. H3을 먼저 봅니다."""
    raw = _common.target_path(data)
    if not raw:
        return None  # 대상 경로가 없는 호출은 판정 대상이 아닙니다.
    target = _common.canonical_path(raw, _common.input_cwd(data))
    reason = h3_git_target(target)
    if reason:
        return reason
    ctx = _common.build_context(data, raw, target)
    reason = h3_violation(ctx, role)
    if reason:
        return reason
    if role == "developer":
        return h1_violation(ctx)
    if role == "tester":
        return h2_violation(ctx)
    if role == "documenter":
        return h7_violation(ctx)
    return None


def deny(reason):
    """거부 JSON을 stdout에 쓰고 exit 0으로 끝냅니다(차단 코드 2를 쓰지 않습니다)."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def h3_git_target(target):
    """H3의 .git 대상(정규화 경로의 구성 요소). 저장소 판정 전에 거부합니다.

    (왜: worktree·서브모듈의 .git은 파일이라 대상 쪽 저장소 발견이 그 뒤를
    보기 전에 막는 것이 순서상 자연스럽고, 망가진 .git에서 repo_info가 실패해도
    판정이 흔들리지 않습니다. 대소문자 무시 볼륨에서 .GIT 도 같은 대상이라
    casefold로 비교합니다.)
    """
    for part in target.split(os.sep):
        if part.casefold() == ".git":
            return (
                "H3(공통 불변식): %s 은(는) git 내부 파일입니다. .git/ 는 저장소 메타데이터라 고치지 않습니다. "
                "쓰기를 멈추고 필요한 이유를 보고서의 「계약 문제」에 적으세요." % target
            )
    return None


def h3_violation(ctx, role=None):
    """H3 공통 불변식(developer·tester·documenter). 위반이면 이유, 아니면 None.

    role이 documenter면 .work-standards/kb-outbox/ 아래만 예외로 통과시킵니다.
    (왜: 지식 저장소에 올릴 초안을 두는 유일한 허용 장소이고, 나머지
    .work-standards/ — 보호 목록, 기록 — 은 여전히 막아야 하기 때문입니다.)

    거부 쪽 비교는 casefold로 합니다. (왜: 대소문자 무시 볼륨에서 .Env 나
    .WORK-STANDARDS 는 같은 파일을 여므로, 대소문자를 구분하는 볼륨의 드문
    오탐보다 우회를 막는 쪽을 택합니다.)
    """
    if not ctx["same"]:
        return (
            "H3(공통 불변식): %s 은(는) 세션 저장소 밖입니다. 이 작업은 저장소 안의 경로에만 쓸 수 있습니다. "
            "저장소 밖에 남겨야 할 내용은 쓰지 말고, 보고서의 「계약 문제」에 경로와 이유를 적고 멈추세요."
            % ctx["target"]
        )
    parts = ctx["rel"].split("/")
    if parts[0].casefold() == ".work-standards":
        if role == "documenter" and is_kb_outbox(ctx["rel"]):
            return None
        return (
            "H3(공통 불변식): %s 은(는) hook 상태 디렉터리(.work-standards/) 안입니다. "
            "에이전트는 이 안을 고치지 않습니다(보호 목록을 고쳐 가드를 끄는 일도 막습니다). "
            "보고서의 「계약 문제」에 적고 멈추세요." % ctx["rel"]
        )
    name = parts[-1].casefold()
    if name == ".env" or (name.startswith(".env.") and name not in ENV_ALLOWED_FOLDED):
        return (
            "H3(공통 불변식): %s 은(는) 비밀값 파일입니다. 비밀값을 코드와 함께 두지 않습니다. "
            "예시 값이라면 .env.example에 쓰세요." % ctx["rel"]
        )
    return None


def is_kb_outbox(rel):
    """rel이 .work-standards/kb-outbox 아래인지. casefold로 비교합니다(H3와 같게)."""
    folded = rel.casefold()
    return folded == KB_OUTBOX or folded.startswith(KB_OUTBOX + "/")


def h7_violation(ctx):
    """H7 documenter의 쓰기 범위. 위반이면 이유, 아니면 None을 돌려줍니다.

    허용: README·CHANGELOG·MANUAL로 시작하는 파일 이름(대소문자·확장자 무관,
    어느 디렉터리든), docs/ 아래(kb 초안의 .work-standards/kb-outbox/ 아래는 H3
    예외로 이미 통과했습니다). 거부: docs/designs/(승인된 설계서), 그 밖의 모든
    경로 — 코드·테스트·설정 파일은 documenter가 고치지 않습니다.
    """
    rel = ctx["rel"]
    folded = rel.casefold()
    parts = folded.split("/")
    if parts[0] == "docs":
        if folded == "docs/designs" or folded.startswith("docs/designs/"):
            return (
                "H7(documenter 쓰기 범위): %s 은(는) 승인된 설계서 디렉터리(docs/designs/) 안입니다. "
                "설계서는 고치지 않습니다. 설계가 바뀌어야 한다고 판단되면 "
                "보고서의 「물어볼 것」에 근거와 함께 적으세요." % rel
            )
        return None
    name = parts[-1]
    if name.startswith(DOC_NAME_PREFIXES):
        return None
    if is_kb_outbox(rel):
        return None
    return (
        "H7(documenter 쓰기 범위): %s 은(는) 문서 경로가 아닙니다. documenter는 README·CHANGELOG·MANUAL로 "
        "시작하는 파일, docs/ 아래, .work-standards/kb-outbox/ 아래에만 씁니다. "
        "코드·테스트·설정을 바꿔야 하는 내용이면 보고서의 「물어볼 것」에 적고 직접 바꾸지 마세요." % rel
    )


def h1_violation(ctx):
    """H1 developer의 보호 경로. 위반이면 이유, 아니면 None을 돌려줍니다.

    protected-paths 파일은 후보 toplevel 중 파일이 있는 첫 곳에서 찾습니다.
    (왜: 메인 대화는 이 파일을 자기 작업 트리 toplevel에 쓰고, 격리 worktree
    서브에이전트의 세션 toplevel은 그 안에 중첩된 worktree입니다. 가까운 후보부터
    보면 서브에이전트 자신의 목록이 있을 때는 그것이 우선하고, 없으면 조정자의
    목록을 찾습니다. boundary-check.sh의 --protect가 최종 그물입니다.)
    """
    candidates = _common.state_candidates(ctx["cwd"], ctx["session"])
    path = protected_file(candidates)
    if path is None:
        return None
    protect_all, entries = protected_entries(path, ctx["session_toplevel"], ctx["target_toplevel"])
    entry = match_protected(ctx["rel"], entries)
    if protect_all or entry is not None:
        return (
            "H1(보호 경로): %s 은(는) 이 호출의 보호 경로(%s)입니다. 인수·통합 테스트와 잠금 파일은 수정 금지입니다. "
            "테스트가 틀렸거나 의존성 변경이 필요하다고 판단되면 구현을 멈추고, 근거를 보고서의 「계약 문제」에 적으세요."
            % (ctx["rel"], entry or ".")
        )
    return None


def protected_file(candidates):
    """후보 toplevel 중 .work-standards/protected-paths 파일이 있는 첫 경로.

    파일이 없으면 H1은 아무것도 하지 않습니다(None).
    """
    for candidate in candidates:
        path = os.path.join(candidate, ".work-standards", "protected-paths")
        if os.path.isfile(path):
            return path
    return None


def protected_entries(path, session_toplevel, target_toplevel):
    """protected-paths를 비교용 목록으로 바꿉니다. (전체 보호 여부, 항목 목록).

    각 항목은 두 모양으로 남깁니다: 적힌 그대로(lexical)와 대상 toplevel로 푼
    실제 경로의 상대 값. (왜: 항목이 심볼릭 링크 이름이면 대상 경로는 풀린 모양으로
    오므로 canonical만 두면 새고, 반대로 lexical을 지우면 다른 이름으로 쓴 같은
    파일이 새므로 둘 다 필요합니다.) '.', './', 절대 루트 항목은 boundary-check.sh의
    under와 같게 전체 보호로 봅니다.
    """
    protect_all = False
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry = _normalize_entry(line.strip(), session_toplevel)
            if entry in ("", "."):
                protect_all = True
                continue
            entries.append(entry)
            entries.append(_canonical_rel(entry, target_toplevel))
    return protect_all, entries


def _normalize_entry(line, root):
    """한 줄을 경로 하나로 만듭니다. 빈 줄과 # 주석은 버립니다.

    boundary-check.sh의 normalize와 같은 규칙(루트 접두, 앞의 ./, 뒤의 / 를
    뗍니다). 절대 루트 항목은 canonical 경로로 비교합니다. (왜: 항목에 /var,
    /tmp 같은 링크 접두가 섞여도 세션 toplevel과 같은 루트로 봐야 전체 보호로
    바뀝니다.)
    """
    if not line or line.startswith("#"):
        return ""
    root_canonical = _common.canonical_path(root, root)
    canonical = _common.canonical_path(line, root)
    if canonical == root_canonical:
        return "."
    if canonical.startswith(root_canonical + os.sep):
        line = canonical[len(root_canonical) + 1:]
    while line.startswith("./"):
        line = line[2:]
    while line.endswith("/"):
        line = line[:-1]
    return line


def _canonical_rel(entry, target_toplevel):
    """항목을 대상 toplevel 기준 상대 경로로 푼 모양을 돌려줍니다."""
    canonical = _common.canonical_path(entry, target_toplevel)
    return os.path.relpath(canonical, target_toplevel).replace(os.sep, "/")


def match_protected(rel, entries):
    """rel이 항목과 같거나 그 아래면 해당 항목을, 아니면 None을 돌려줍니다.

    비교는 casefold로 합니다. 접두는 경로 구성 요소 경계에서만 인정합니다
    (tests/acc 는 tests/accx.py 를 걸르지 않습니다).
    """
    folded = rel.casefold()
    for entry in entries:
        entry_folded = entry.casefold()
        if folded == entry_folded or folded.startswith(entry_folded + "/"):
            return entry
    return None


def h2_violation(ctx):
    """H2 tester의 쓰기 범위. 위반이면 이유, 아니면 None을 돌려줍니다."""
    rel = ctx["rel"]
    if is_test_path(rel):
        return None
    if ctx["in_git"]:
        tracked = is_tracked(ctx["target_toplevel"], rel)
    else:
        # 세션이 git이 아니면 추적 여부를 알 수 없으므로 존재로 봅니다.
        tracked = os.path.exists(ctx["target"])
    if tester_may_write_non_test(rel, os.path.exists(ctx["target"]), tracked):
        return None
    return (
        "H2(tester 쓰기 범위): %s 은(는) 테스트 경로가 아니고 git이 추적 중인 기존 파일입니다. "
        "tester는 구현 코드를 고치지 않습니다. 테스트는 테스트 위치에 쓰고, "
        "계약 시그니처의 빈 껍데기가 필요하면 새 파일로 만들어 보고서의 「만든 빈 껍데기」에 적으세요. "
        "이 경로를 꼭 바꿔야 한다면 멈추고 보고서의 「계약 문제」에 적으세요." % rel
    )


def is_test_path(rel):
    """tester의 쓰기 범위에서 테스트 경로인지.

    디렉터리 구성 요소와 파일 이름 규칙을 모두 봅니다. 거부 쪽 판정과 달리
    정확 비교를 유지합니다. (왜: tester에게 테스트 경로는 허용이고, 허용 쪽을
    넓히는 방향으로 비교를 내리면 구현 파일을 통과시킬 수 있습니다.)
    """
    parts = rel.split("/")
    if any(part in TEST_DIRS for part in parts[:-1]):
        return True
    return is_test_name(parts[-1])


def is_test_name(name):
    """테스트 파일 이름 규칙.

    (왜: 이 함수로 통과시키는 것은 tester뿐입니다. developer는 H1 목록으로만
    판정하므로 파일 이름 패턴을 쓰지 않습니다.)
    """
    if name == "conftest.py":
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test.go"):
        return True
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        if ext in TEST_EXTS and (stem.endswith(".test") or stem.endswith(".spec")):
            return True
    return False


def is_tracked(toplevel, rel):
    """git이 이 경로를 추적 중인지.

    (왜: tester의 빈 껍데기는 새 파일만 허용하므로, 이미 저장소에 있는
    구현 파일과 구별해야 합니다. pathspec을 :(literal)로 넘겨 rel 안의
    [ ] * ? 문자가 glob으로 풀려 다른 추적 파일에 걸리지 않게 합니다.)
    """
    out = _common.run_git(["ls-files", "--error-unmatch", "--", ":(literal)" + rel], toplevel)
    if out.returncode == 0:
        return True
    if out.returncode == 1:
        return False  # ls-files --error-unmatch는 못 찾으면 1로 끝납니다.
    raise _common.HookError("git ls-files 실패: %s" % _common.first_line(out.stderr))


# TODO(사용자): 팀 정책으로 바꾸세요. tester가 테스트 밖 경로에 쓸 때 정할 것:
#   - 기본값: git이 추적 중인 파일은 거부, 새 파일(추적되지 않음)은 허용.
#     (왜: tester는 컴파일 언어에서 계약 시그니처 그대로의 빈 껍데기를 만들 수
#     있습니다. 기존 구현을 고치는 것은 RED 단계에 구현이 섞이는 위반이라 막습니다.
#     새 파일로 만든 껍데기가 남긴 틈은 boundary-check의 --allow 목록과 보고서의
#     「만든 빈 껍데기」 대조가 최종적으로 막습니다.)
#   - 대안: 테스트 밖 쓰기를 전부 거부. 빈 껍데기를 메인 대화가 만들어야 해서
#     ⑤→⑥ 왕복이 늘어납니다. 컴파일 언어를 쓰지 않는 팀에 맞습니다.
#   - 대안: 「빈 껍데기로 보이는 파일」(짧고 구현 문이 없는)만 허용. 파일 내용을
#     읽어 판정해야 해서 hook의 비용과 오판이 늘어납니다.
#   - 트레이드오프: 새 파일 허용은 tester가 그 자리에 구현을 몰래 쓰는 것까지
#     허용합니다. 그래서 이 파일 하나로는 부족하고, 경계 확인이 최종 그물입니다.
def tester_may_write_non_test(rel, exists, tracked):
    """tester가 테스트 밖 경로에 쓸 수 있는지. True면 통과시킵니다.

    exists는 대안 정책(존재하는 파일만 막기)을 붙일 때를 위해 받습니다.
    """
    return not tracked


if __name__ == "__main__":
    _common.run_hook(main)
