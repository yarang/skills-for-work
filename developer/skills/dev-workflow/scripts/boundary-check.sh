#!/usr/bin/env bash
# boundary-check.sh — 서브에이전트가 맡은 범위 밖의 파일을 바꿨는지 git 상태로 확인합니다.
#
# 사용법:
#   boundary-check.sh snapshot <스냅숏 파일>
#   boundary-check.sh check <스냅숏 파일 | --base=<커밋>> [--allow=<경로>]... [--protect=<경로>]... [--strict]
#
#   snapshot  에이전트를 부르기 전에 지금 상태를 기록합니다. 스냅숏 파일은 저장소 밖에 둡니다.
#   check     스냅숏(또는 --base 커밋) 이후 바뀐 경로를 범위와 비교합니다.
#             --base=<커밋>은 그 커밋에서 갓 만든 worktree처럼 깨끗한 상태에서 시작했을 때 씁니다.
#   --allow   바꿔도 되는 디렉터리나 파일 (여러 번). 없으면 모든 변경이 범위 밖입니다.
#   --protect 바꾸면 안 되는 경로 (여러 번). --allow보다 우선합니다.
#   --strict  범위 밖 정책을 적용하지 않고, 허용 범위 밖 변경을 모두 위반으로 셉니다 (읽기 전용 역할).
#
# 경로는 저장소 루트 기준입니다(디렉터리 칸의 심볼릭 링크는 풀어서 비교하고, 저장소 밖이면 2).
# 보호 경로는 대소문자까지 디스크와 같아야 합니다. 줄바꿈이 든 경로는 지원하지 않습니다.
# 커밋(HEAD 이동)과 브랜치 변경도 위반입니다. .gitignore로 무시된 경로는 보지 않습니다.
# 종료 코드: 0 통과, 1 위반, 2 사용법·경로 오류 (없는 보호 경로, 대소문자 다름, 저장소 밖)
#
# macOS 기본 bash(3.2)에서도 돌도록 연관 배열과 빈 배열 펼치기를 쓰지 않습니다.
set -uo pipefail

usage() {
  sed -n '4,18p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

ALLOW=()
PROTECT=()
STRICT=0
BASE=-

# 저장소 루트 기준의 상대 경로로 맞춥니다. 결과는 "." 또는 루트 기준 상대 경로이고,
# 저장소 밖이면 "/"로 시작하는 절대 경로가 남습니다(cmd_check가 종료 코드 2로 거부).
# 커널이 경로를 여는 순서대로 앞에서부터 한 칸씩 따라갑니다.
#  - 상대 경로는 루트(물리 경로) 기준입니다. 빈 칸과 "."은 건너뜁니다.
#  - 디렉터리로 있는 칸까지 오면 그 자리를 물리 경로로 바꿉니다(pwd -P). 그래서 macOS의
#    /tmp → /private/tmp 같은 별칭도, 저장소 안 심볼릭 링크 디렉터리(acceptance → tests/acceptance)도
#    git이 돌려주는 실제 경로와 같아집니다.
#  - ".."은 지금까지 푼 물리 경로의 부모입니다. 심볼릭 링크 뒤의 ".."을 문자열로 먼저 접으면
#    커널이 여는 곳과 달라지기 때문입니다. 아직 없는 칸 뒤의 ".."만 글자대로 지웁니다.
# 두 번째 인수가 1이면 마지막 칸은 풀지 않습니다(심볼릭 링크 자체를 가리키도록). 끝이 "/"이면
# 디렉터리를 뜻하므로 그때도 끝까지 풉니다.
normalize() {
  local p="$1" cur rest="$1" last="" c d
  case "$p" in /*) cur=/ ;; *) cur="$ROOT" ;; esac
  if [ "${2:-0}" = 1 ]; then
    case "$p" in
      */ | . | .. | */. | */..) ;;
      */*) last="${p##*/}" rest="${p%/*}" ;;
      *) last="$p" rest="" ;;
    esac
  fi
  while [ -n "$rest" ]; do
    c="${rest%%/*}"
    case "$rest" in */*) rest="${rest#*/}" ;; *) rest="" ;; esac
    case "$c" in
      "" | .) continue ;;
      ..) cur="${cur%/*}" cur="${cur:-/}" ;;
      *) cur="${cur%/}/$c" ;;
    esac
    if [ -d "$cur" ] && d="$(cd -P "$cur" 2>/dev/null && pwd -P)"; then
      cur="$d"
    fi
  done
  [ -z "$last" ] || cur="${cur%/}/$last"
  case "$cur" in
    "$ROOT") cur="." ;;
    "$ROOT"/*) cur="${cur#"$ROOT"/}" ;;
  esac
  printf '%s' "$cur"
}

# exists_exact <경로>: 대소문자까지 디스크와 똑같은 이름으로 있는지. macOS(APFS)는 대소문자를
# 무시하므로 [ -e Tests/a.py ]가 tests/a.py를 찾아 참이 되지만, git이 돌려주는 경로와는
# 문자열이 달라 보호 경로 비교에서 빠집니다. find -name은 디렉터리 항목 이름을 대소문자 구분으로 맞춥니다.
exists_exact() {
  local rest="$1" d="." c
  [ "$rest" = "." ] && return 0
  while [ -n "$rest" ]; do
    c="${rest%%/*}"
    case "$rest" in */*) rest="${rest#*/}" ;; *) rest="" ;; esac
    [ -n "$(find "$d" -mindepth 1 -maxdepth 1 -name "$(printf '%s' "$c" | sed 's/[][*?\\]/\\&/g')" -print -quit 2>/dev/null)" ] || return 1
    d="$d/$c"
  done
}

# under <경로> <범위>: 경로가 범위(파일 또는 디렉터리)와 같거나 그 아래에 있는지
under() {
  [ "$2" = "." ] && return 0
  [ "$1" = "$2" ] && return 0
  case "$1" in
    "$2"/*) return 0 ;;
  esac
  return 1
}

# in_list <경로> <배열 이름>
in_list() {
  local path="$1" name="$2" n i item
  eval "n=\${#$name[@]}"
  i=0
  while [ "$i" -lt "$n" ]; do
    eval "item=\${$name[$i]}"
    under "$path" "$item" && return 0
    i=$((i + 1))
  done
  return 1
}

hash_of() {
  if [ -L "$1" ]; then
    readlink "$1" | git hash-object --stdin
  elif [ -f "$1" ]; then
    git hash-object -- "$1"
  elif [ -d "$1" ]; then
    # 추적되지 않은 중첩 저장소나 서브모듈: 안의 파일 이름과 내용 해시를 모아 하나로 해시합니다.
    local files
    files="$(find "$1" -name .git -prune -o -type f -print | LC_ALL=C sort)"
    {
      echo DIR
      if [ -n "$files" ]; then
        printf '%s\n' "$files"
        printf '%s\n' "$files" | git hash-object --stdin-paths
      fi
    } | git hash-object --stdin
  else
    echo DELETED
  fi
}

# 기준 커밋과 내용이 다른 경로(추적 중인 변경·삭제 + 무시되지 않은 새 파일)를 한 줄에 하나씩 출력합니다.
# git 명령이 실패하면 0이 아닌 상태로 끝납니다(pipefail).
list_candidates() {
  {
    if [ "$1" = "-" ]; then
      git ls-files -z --cached --others --exclude-standard || exit 2
    else
      git diff --name-only -z --no-renames "$1" -- || exit 2
      git ls-files -z --others --exclude-standard || exit 2
    fi
  } | tr '\0' '\n' | sort -u
}

# 기준 커밋에 있던 경로인지 (추적 중인 파일은 산출물로 보지 않기 위해)
in_base() {
  [ "$BASE" != "-" ] && git cat-file -e "$BASE:$1" 2>/dev/null
}

# 스냅숏에 그 경로(또는 그 아래 경로)가 있었는지 (추적하지 않던 보호 파일이 지워진 경우)
in_snap() {
  # DELETED 줄은 스냅숏 때 이미 없던 경로이므로 세지 않습니다.
  P="$1" awk -F'\t' '$1 != "DELETED" {
      q = substr($0, index($0, "\t") + 1)
      if (q == ENVIRON["P"] || index(q, ENVIRON["P"] "/") == 1) { f = 1; exit }
    }
    END { exit !f }' "$SNAP"
}

# 테스트를 돌리면 생기는 캐시입니다. 기준 커밋에 없던 경로일 때만 통과시킵니다.
# target/, node_modules/, coverage/ 는 소스 디렉터리 이름과 겹칠 수 있어 넣지 않습니다.
# 그런 산출물은 저장소의 .gitignore로 빼 두세요(무시된 경로는 처음부터 비교하지 않습니다).
is_test_artifact() {
  in_base "$1" && return 1
  case "$1" in
    .pytest_cache/* | */.pytest_cache/* | __pycache__/* | */__pycache__/* | *.pyc) return 0 ;;
    .mypy_cache/* | */.mypy_cache/* | .ruff_cache/* | */.ruff_cache/*) return 0 ;;
    .coverage | */.coverage | .coverage.* | */.coverage.* | htmlcov/* | */htmlcov/*) return 0 ;;
  esac
  return 1
}

# 범위 밖 변경 정책: 보호 경로·테스트 산출물·허용 범위 어디에도 들지 않는 경로를 받아
# allow(조용히 통과) | report(통과하되 목록에 남김) | block(위반) 중 하나를 출력합니다.
#
# TODO(사용자): 팀의 정책으로 바꾸세요. 정할 것:
#   - 잠금 파일(bun.lock, bun.lockb, package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock, uv.lock, poetry.lock, Cargo.lock, go.sum):
#     의존성은 ④-1에서 메인 대화가 적용하므로 ⑥에서는 바뀌면 안 됩니다. 행 디렉터리 안과
#     워크스페이스 루트의 잠금 파일은 dev-workflow가 --protect로 넘기므로 이 정책보다 먼저
#     BLOCK됩니다. 여기서 allow나 report로 두지 마세요.
#   - 워크스페이스 루트 매니페스트(루트 package.json, pnpm-workspace.yaml, Cargo.toml, go.work):
#     모든 행에 영향을 줍니다.
#   - 공용 설정(.gitignore, tsconfig.json, .editorconfig): 행 하나의 일로 바꿔도 되는지
#   report로 둔 경로는 메인 대화가 developer 보고서의 「디렉터리 밖 변경」과 맞춰 봅니다.
#
# 지금은 임시 기본값(가장 엄격)입니다: 모두 block입니다.
classify_out_of_scope() {
  echo block
}

current_ref() {
  git symbolic-ref -q HEAD || echo detached
}

cmd_snapshot() {
  [ $# -eq 1 ] || usage
  local out="$1" base path
  case "$out" in
    /*) ;;
    *) out="$START_DIR/$out" ;;
  esac
  case "$(normalize "$out" 1)" in
    /*) ;;
    *) echo "스냅숏 파일은 저장소 밖에 두세요: $out" >&2; exit 2 ;;
  esac

  base="$(git rev-parse --verify -q HEAD || echo -)"
  {
    printf 'base\t%s\n' "$base"
    printf 'ref\t%s\n' "$(current_ref)"
    list_candidates "$base" | while IFS= read -r path; do
      printf '%s\t%s\n' "$(hash_of "$path")" "$path"
    done
  } >"$out" || { echo "git 상태를 읽지 못했습니다" >&2; exit 2; }
  echo "스냅숏을 기록했습니다: $out (기준 $base)"
}

cmd_check() {
  [ $# -ge 1 ] || usage
  local source="$1" ref_before=""
  shift

  local arg full link
  for arg in "$@"; do
    case "$arg" in
      --allow=?*) ALLOW+=("$(normalize "${arg#--allow=}")") ;;
      --protect=?*)
        # 끝까지 푼 경로(링크가 가리키는 곳)와 마지막 칸을 풀지 않은 경로(링크 자체)를 둘 다 보호합니다.
        # 링크가 저장소 밖을 가리키면 링크 자체만 보호합니다.
        full="$(normalize "${arg#--protect=}")"
        link="$(normalize "${arg#--protect=}" 1)"
        if [ "$link" = "$full" ]; then
          PROTECT+=("$full")
        else
          case "$full" in /*) ;; *) PROTECT+=("$full") ;; esac
          PROTECT+=("$link")
        fi
        ;;
      --strict) STRICT=1 ;;
      *) usage ;;
    esac
  done
  for arg in ${ALLOW[@]+"${ALLOW[@]}"} ${PROTECT[@]+"${PROTECT[@]}"}; do
    case "$arg" in
      /*) echo "저장소 밖 경로입니다 (저장소 루트 기준으로 주세요): $arg" >&2; exit 2 ;;
    esac
  done

  SNAP="$(mktemp "${TMPDIR:-/tmp}/boundary.XXXXXX")"
  trap 'rm -f "$SNAP" "$SNAP.paths"' EXIT
  case "$source" in
    --base=?*)
      BASE="${source#--base=}"
      : >"$SNAP"
      ;;
    --*) usage ;;
    *)
      case "$source" in
        /*) ;;
        *) source="$START_DIR/$source" ;;
      esac
      [ -f "$source" ] || { echo "스냅숏 파일이 없습니다: $source" >&2; exit 2; }
      BASE="$(awk -F'\t' 'NR == 1 && $1 == "base" { print $2 }' "$source")"
      ref_before="$(awk -F'\t' 'NR == 2 && $1 == "ref" { print $2 }' "$source")"
      [ -n "$BASE" ] && [ -n "$ref_before" ] || { echo "스냅숏 형식이 아닙니다: $source" >&2; exit 2; }
      sed '1,2d' "$source" >"$SNAP"
      ;;
  esac
  if [ "$BASE" != "-" ]; then
    BASE="$(git rev-parse --verify -q "$BASE^{commit}")" || { echo "기준 커밋이 없습니다: ${source#--base=}" >&2; exit 2; }
  fi

  # 보호 경로가 기준에도, 스냅숏에도, 지금에도 없으면 경로를 잘못 준 것입니다 (예: 행 디렉터리 기준 상대 경로).
  # 스냅숏에만 있던 경로는 그 사이에 지워진 것이므로 아래 비교에서 보호 경로 위반으로 잡힙니다.
  local p i=0
  while [ "$i" -lt "${#PROTECT[@]}" ]; do
    p="${PROTECT[$i]}"
    if [ -e "$p" ] || [ -L "$p" ]; then
      exists_exact "$p" || { echo "보호 경로의 대소문자가 디스크와 다릅니다: $p" >&2; exit 2; }
    else
      in_base "$p" || in_snap "$p" || { echo "보호 경로가 없습니다 (저장소 루트 기준인지 확인하세요): $p" >&2; exit 2; }
    fi
    i=$((i + 1))
  done

  # 스냅숏에 있던 경로와 지금 바뀐 경로를 합쳐 하나씩 비교합니다.
  { cut -f2- "$SNAP" && list_candidates "$BASE"; } | sort -u >"$SNAP.paths" ||
    { echo "git 상태를 읽지 못했습니다" >&2; exit 2; }

  local path before after status reason violations=0 reports=0 changes=0 artifacts=0
  local lines="" line

  # 커밋하거나 브랜치를 바꾼 것도 위반입니다. 커밋하면 git diff에서 변경이 사라지기 때문입니다.
  local head ref_after
  head="$(git rev-parse --verify -q HEAD || echo -)"
  ref_after="$(current_ref)"
  if [ "$head" != "$BASE" ]; then
    violations=$((violations + 1))
    lines="${lines}$(printf '%-6s %s  %s' BLOCK "HEAD 이동" "$BASE -> $head")
"
  fi
  if [ -n "$ref_before" ] && [ "$ref_before" != "$ref_after" ]; then
    violations=$((violations + 1))
    lines="${lines}$(printf '%-6s %s  %s' BLOCK "브랜치 변경" "$ref_before -> $ref_after")
"
  fi

  while IFS= read -r path; do
    [ -n "$path" ] || continue
    before="$(P="$path" awk -F'\t' 'substr($0, index($0, "\t") + 1) == ENVIRON["P"] { print $1; exit }' "$SNAP")"
    after="$(hash_of "$path")"
    [ -n "$before" ] && [ "$before" = "$after" ] && continue
    changes=$((changes + 1))

    if in_list "$path" PROTECT; then
      status=BLOCK reason="보호 경로"
    elif is_test_artifact "$path"; then
      artifacts=$((artifacts + 1))
      continue
    elif in_list "$path" ALLOW; then
      status=ok reason="범위 안"
    elif [ "$STRICT" -eq 1 ]; then
      # 읽기 전용 역할에는 범위 밖 정책을 적용하지 않습니다.
      status=BLOCK reason="범위 밖"
    else
      case "$(classify_out_of_scope "$path")" in
        allow) status=ok reason="정책 허용" ;;
        report) status=report reason="범위 밖" ;;
        *) status=BLOCK reason="범위 밖" ;;
      esac
    fi
    [ "$status" = BLOCK ] && violations=$((violations + 1))
    [ "$status" = report ] && reports=$((reports + 1))
    lines="$lines$(printf '%-6s %s  %s' "$status" "$reason" "$path")
"
  done <"$SNAP.paths"

  echo "## 경계 확인: $ROOT"
  echo "- 기준 커밋: $BASE"
  printf -- '- 허용 범위:'
  [ "${#ALLOW[@]}" -gt 0 ] && printf ' %s' "${ALLOW[@]}" || printf ' 없음'
  echo
  printf -- '- 보호 경로:'
  [ "${#PROTECT[@]}" -gt 0 ] && printf ' %s' "${PROTECT[@]}" || printf ' 없음'
  echo
  echo "- 변경 ${changes}건 (테스트 산출물 ${artifacts}건 제외), 보고 ${reports}건, 위반 ${violations}건"
  [ -n "$lines" ] && printf '\n%s' "$lines"

  if [ "$violations" -gt 0 ]; then
    echo "결과: 위반"
    exit 1
  fi
  echo "결과: 통과"
  exit 0
}

main() {
  [ $# -ge 1 ] || usage
  START_DIR="$(pwd -P)"
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "git 저장소가 아닙니다: $START_DIR" >&2; exit 2; }
  cd "$ROOT" || exit 2

  local cmd="$1"
  shift
  case "$cmd" in
    snapshot) cmd_snapshot "$@" ;;
    check) cmd_check "$@" ;;
    *) usage ;;
  esac
}

main "$@"
