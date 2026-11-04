#!/usr/bin/env bash
# verify.sh — 대상 디렉터리의 매니페스트를 보고 포맷·린트·타입·테스트 검사를 돌립니다.
#
# 사용법: verify.sh [대상 디렉터리]
# 종료 코드: 0 통과, 1 차단, 2 사용법 오류(디렉터리·매니페스트 없음)
#
# macOS 기본 bash(3.2)에서도 돌도록 연관 배열과 빈 배열 펼치기를 쓰지 않습니다.
set -uo pipefail

TARGET="${1:-.}"
[ -d "$TARGET" ] || { echo "디렉터리가 없습니다: $TARGET" >&2; exit 2; }
cd "$TARGET" || exit 2

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/verify.XXXXXX")"
trap 'rm -rf "$LOG_DIR"' EXIT

# 테스트 러너가 감시(watch) 모드로 멈추지 않게 합니다.
export CI=true

# 검사 결과: 같은 인덱스끼리 한 건입니다.
NAMES=()    # 검사 이름
KINDS=()    # format | lint | type | test
RESULTS=()  # pass | fail | skip

has() { command -v "$1" >/dev/null 2>&1; }

record() {
  NAMES+=("$1")
  KINDS+=("$2")
  RESULTS+=("$3")
}

# run_check <이름> <종류> <명령...>
run_check() {
  local name="$1" kind="$2"
  shift 2
  local log="$LOG_DIR/${#NAMES[@]}.log"
  if "$@" >"$log" 2>&1; then
    record "$name" "$kind" pass
  else
    record "$name" "$kind" fail
    echo "── 실패: $name"
    echo "   명령: $*"
    tail -n 40 "$log" | sed 's/^/   /'
  fi
}

# skip_check <이름> <종류> <이유>
skip_check() {
  record "$1" "$2" skip
  echo "── 건너뜀: $1 — $3"
}

check_node() {
  [ -f package.json ] || return 0
  local pm=npm
  if [ -f pnpm-lock.yaml ]; then
    pm=pnpm
  elif [ -f yarn.lock ]; then
    pm=yarn
  fi
  if ! has node || ! has "$pm"; then
    skip_check "node" test "node 또는 $pm 이 없음"
    return 0
  fi

  local pair script kind
  for pair in typecheck:type lint:lint test:test; do
    script="${pair%%:*}"
    kind="${pair##*:}"
    if node -e 'const s=require("./package.json").scripts||{};process.exit(s[process.argv[1]]?0:1)' "$script"; then
      run_check "$pm run $script" "$kind" "$pm" run "$script"
    else
      skip_check "$pm run $script" "$kind" "package.json에 $script 스크립트가 없음"
    fi
  done
}

check_python() {
  [ -f pyproject.toml ] || [ -f requirements.txt ] || return 0

  # uv 프로젝트면 가상환경 안에서 실행합니다. 일부러 따옴표 없이 펼칩니다.
  local run=""
  if [ -f uv.lock ] && has uv; then
    run="uv run"
  fi
  py_has() { $run sh -c "command -v $1" >/dev/null 2>&1; }

  if py_has ruff; then
    run_check "ruff format" format $run ruff format --check .
    run_check "ruff check" lint $run ruff check .
  else
    skip_check "ruff" lint "ruff가 설치되지 않음"
  fi

  if [ -f mypy.ini ] || grep -q '^\[tool\.mypy\]' pyproject.toml 2>/dev/null; then
    run_check "mypy" type $run mypy .
  elif [ -f pyrightconfig.json ] || grep -q '^\[tool\.pyright\]' pyproject.toml 2>/dev/null; then
    run_check "pyright" type $run pyright
  else
    skip_check "타입 검사" type "mypy·pyright 설정이 없음"
  fi

  if py_has pytest; then
    run_check "pytest" test $run pytest -q
  else
    skip_check "pytest" test "pytest가 설치되지 않음"
  fi
}

check_go() {
  [ -f go.mod ] || return 0
  if ! has go; then
    skip_check "go" test "go가 없음"
    return 0
  fi

  run_check "gofmt" format sh -c 'out=$(gofmt -l .); [ -z "$out" ] || { echo "포맷이 안 된 파일:"; echo "$out"; exit 1; }'
  run_check "go vet" lint go vet ./...
  if [ -f .golangci.yml ] || [ -f .golangci.yaml ] || [ -f .golangci.toml ]; then
    if has golangci-lint; then
      run_check "golangci-lint" lint golangci-lint run
    else
      skip_check "golangci-lint" lint "설정은 있으나 도구가 없음"
    fi
  fi
  run_check "go test -race" test go test -race ./...
}

check_rust() {
  [ -f Cargo.toml ] || return 0
  if ! has cargo; then
    skip_check "cargo" test "cargo가 없음"
    return 0
  fi

  run_check "cargo fmt" format cargo fmt --all --check
  run_check "cargo clippy" lint cargo clippy --all-targets --all-features -- -D warnings
  if [ -f .config/nextest.toml ] && cargo nextest --version >/dev/null 2>&1; then
    run_check "cargo nextest" test cargo nextest run --all-features
  else
    run_check "cargo test" test cargo test --all-features
  fi
}

print_summary() {
  echo
  echo "## 검증 요약: $(pwd)"
  local i
  for i in "${!NAMES[@]}"; do
    printf '%-5s %-7s %s\n' "${RESULTS[$i]}" "${KINDS[$i]}" "${NAMES[$i]}"
  done
}

# 차단 정책: 모인 검사 결과를 보고 통과(0)인지 차단(1)인지 정합니다.
# 입력: 전역 배열 NAMES, KINDS(format|lint|type|test), RESULTS(pass|fail|skip)
#
# TODO(사용자): 팀의 차단 정책으로 바꾸세요. 정할 것:
#   - skip(도구 없음, 스크립트 없음)을 통과로 볼지, 차단으로 볼지
#   - format 실패만 있을 때도 차단할지 (자동으로 고칠 수 있는 문제)
#   - test 종류 검사가 하나도 pass하지 않았으면(전부 skip) 차단할지
#
# 지금은 임시 기본값(가장 엄격)입니다: fail이나 skip이 하나라도 있으면 차단합니다.
decide_exit() {
  local i
  for i in "${!RESULTS[@]}"; do
    case "${RESULTS[$i]}" in
      fail | skip) return 1 ;;
    esac
  done
  return 0
}

main() {
  check_node
  check_python
  check_go
  check_rust

  if [ "${#NAMES[@]}" -eq 0 ]; then
    echo "매니페스트(package.json, pyproject.toml, requirements.txt, go.mod, Cargo.toml)가 없습니다: $(pwd)" >&2
    exit 2
  fi

  print_summary
  if decide_exit; then
    echo "결과: 통과"
    exit 0
  fi
  echo "결과: 차단"
  exit 1
}

main
