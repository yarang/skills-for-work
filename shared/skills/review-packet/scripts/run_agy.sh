#!/usr/bin/env bash
# Antigravity(agy)로 검토 꾸러미를 보내 결과를 받는 실행기.
# 사용법: run_agy.sh <저장소> <꾸러미 파일> <결과 파일>
# --print를 맨 뒤에 두고 지시문을 그 바로 뒤에 둔다(-p 바로 뒤에 다른 플래그를 두면
# agy가 그 플래그를 지시문으로 먹는다). 종료 코드는 agy의 것을 그대로 돌려주고,
# 결과 파일이 비어 있으면 2로 끝낸다(stderr에 그 사실을 적는다).
set -uo pipefail

usage() {
  echo "사용법: run_agy.sh <저장소> <꾸러미 파일> <결과 파일>" >&2
  exit 2
}

[ "$#" -eq 3 ] || usage
repo=$1
packet=$2
out=$3

[ -d "$repo" ] || { echo "저장소가 없습니다: $repo" >&2; exit 2; }
[ -f "$packet" ] || { echo "꾸러미 파일이 없습니다: $packet" >&2; exit 2; }

cd "$repo" || exit 1
agy --mode plan --print "$(cat "$packet")" > "$out" 2> "$out.err"
status=$?

if [ ! -s "$out" ]; then
  echo "결과 파일이 비어 있습니다: $out (agy 종료 코드 $status, stderr는 $out.err 참고)" >&2
  exit 2
fi
exit "$status"
