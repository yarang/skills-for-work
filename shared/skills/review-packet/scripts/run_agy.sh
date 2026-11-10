#!/usr/bin/env bash
# Antigravity(agy)로 검토 꾸러미를 보내 결과를 받는 실행기.
# 사용법: run_agy.sh <저장소> <꾸러미 파일> <결과 파일>
# --print를 맨 뒤에 두고 지시문을 그 바로 뒤에 둔다(-p 바로 뒤에 다른 플래그를 두면
# agy가 그 플래그를 지시문으로 먹는다). 종료 코드는 agy의 것을 그대로 돌려주고,
# 결과 파일이 비어 있으면 2로 끝낸다(stderr에 그 사실을 적는다).
# 꾸러미·결과 경로는 cd 전에 절대 경로로 바꾼다(호출 위치 ≠ 저장소여도 호출 위치 기준).
# agy는 --sandbox(단말 제한)로 부른다. 꾸러미가 AGY_MAX_PACKET_BYTES(기본 200000바이트)를
# 넘으면 실행하지 않고 종료 코드 2로 끝낸다(명령행 인자 길이 제한 보호).
# bash 3.2 호환 — readlink -f 대신 cd+pwd로 절대 경로를 만든다.
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

# 꾸러미 크기 상한 — 꾸러미를 통째로 명령행 인자로 넘기므로 ARG_MAX를 보호한다.
max_bytes=${AGY_MAX_PACKET_BYTES:-200000}
case $max_bytes in
  ''|*[!0-9]*)
    echo "AGY_MAX_PACKET_BYTES가 숫자가 아닙니다: $max_bytes" >&2
    exit 2
    ;;
esac
size=$(wc -c < "$packet") || { echo "꾸러미 크기를 읽지 못했습니다: $packet" >&2; exit 2; }
size=$((size + 0))  # wc가 남기는 앞뒤 공백을 걷는다
if [ "$size" -gt "$max_bytes" ]; then
  echo "꾸러미가 크기 상한(${max_bytes}바이트, AGY_MAX_PACKET_BYTES)을 넘었습니다: ${size}바이트." \
    "diff 본문 대신 범위(커밋)로 가리키고 나눠 검토하세요." >&2
  exit 2
fi

# cd 전에 절대 경로로 바꾼다 — cd 뒤에는 저장소 기준으로 풀리면 안 된다.
packet=$(cd "$(dirname -- "$packet")" && pwd)/$(basename -- "$packet")
out_dir=$(dirname -- "$out")
[ -d "$out_dir" ] || { echo "결과 파일의 디렉터리가 없습니다: $out_dir" >&2; exit 2; }
out=$(cd "$out_dir" && pwd)/$(basename -- "$out")

cd "$repo" || exit 1
agy --sandbox --mode plan --print "$(cat "$packet")" > "$out" 2> "$out.err"
status=$?

if [ ! -s "$out" ]; then
  echo "결과 파일이 비어 있습니다: $out (agy 종료 코드 $status, stderr는 $out.err 참고)" >&2
  exit 2
fi
exit "$status"
