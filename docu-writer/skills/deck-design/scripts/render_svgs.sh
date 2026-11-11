#!/usr/bin/env bash
# 자산 폴더의 SVG를 헤드리스 크롬으로 PNG로 만든다.
#
#   render_svgs.sh <자산폴더> [다이어그램 이름...]
#     <자산폴더>/icons/*.svg         -> icons/<이름>.png         (512x512, 투명 배경)
#     <자산폴더>/illustrations/*.svg -> illustrations/<이름>.png (SVG 폭x높이의 2배, 투명)
#     <자산폴더>/diagrams/*.svg      -> diagrams/<이름>.png      (viewBox 크기의 2배, 흰 바탕)
#
# 다이어그램 이름을 주면 그것만, 안 주면 전부 만든다(다이어그램 SVG가 하나도
# 없으면 다이어그램 단계는 건너뛴다). 크롬 경로는 CHROME 환경 변수로 바꿀 수 있다.
# 렌더에 실패하면 기존 PNG를 지키기 위해 임시 파일에 만들었다가 옮긴다.
# macOS 기본 /bin/bash(3.2)에서도 돌아야 한다(빈 배열 확장 주의).
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "사용법: render_svgs.sh <자산폴더> [다이어그램 이름...]" >&2
    exit 2
fi

ASSETS_DIR="$1"
shift
if [ ! -d "$ASSETS_DIR" ]; then
    echo "자산 폴더가 없습니다: $ASSETS_DIR" >&2
    exit 1
fi
ASSETS_DIR="$(cd "$ASSETS_DIR" && pwd)"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [ ! -x "$CHROME" ]; then
    echo "크롬을 실행할 수 없습니다: $CHROME (CHROME 환경 변수로 지정하세요)" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
# 실패 시에도 임시 폴더는 지우되, 실패한 종료 코드를 덮어쓰지 않게 trap 안에서 보존한다.
trap 'rc=$?; rm -rf "$TMP_DIR"; exit $rc' EXIT
shopt -s nullglob

# SVG 루트 요소의 width/height 속성을 읽어 "W H"를 돌려준다.
# 앞에 공백을 요구해 stroke-width="3" 같은 다른 속성에 걸리지 않게 한다.
read_svg_size() {
    python3 -I -c '
import re, sys
svg = open(sys.argv[1], encoding="utf-8").read()
def attr(name):
    m = re.search(r"[ \t\r\n]" + name + r"\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]", svg)
    if not m:
        sys.exit(f"{name} attribute not found in " + sys.argv[1])
    return float(m.group(1))
w, h = attr("width"), attr("height")
if not (w > 0 and h > 0):
    sys.exit("width/height must be positive: " + sys.argv[1])
print(int(w), int(h))
' "$1"
}

# SVG viewBox에서 폭·높이(3·4번째 값)를 읽어 올림한 정수로 돌려준다: "W H"
read_viewbox_size() {
    python3 -I -c '
import math, re, sys
svg = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"viewBox\s*=\s*([\"\x27])([^\"\x27]+)\1", svg)
if not m:
    sys.exit("viewBox not found in " + sys.argv[1])
parts = m.group(2).replace(",", " ").split()
if len(parts) != 4:
    sys.exit("viewBox must have 4 numbers: " + m.group(2))
w, h = float(parts[2]), float(parts[3])
if not (w > 0 and h > 0):
    sys.exit("viewBox width/height must be positive: " + sys.argv[1])
print(math.ceil(w), math.ceil(h))
' "$1"
}

# 크기 읽기: 실패를 숨기지 않는다. 첫째 방법이 실패하면 viewBox로, 그래도 없으면
# 파일 이름을 담아 실패한다. 인자 viewbox를 주면 viewBox를 먼저 본다(다이어그램).
read_size() {
    local svg="$1" prefer="${2:-attrs}" size
    if [ "$prefer" = "viewbox" ]; then
        size="$(read_viewbox_size "$svg" 2>/dev/null || true)"
        [ -z "$size" ] && size="$(read_svg_size "$svg" 2>/dev/null || true)"
    else
        size="$(read_svg_size "$svg" 2>/dev/null || true)"
        [ -z "$size" ] && size="$(read_viewbox_size "$svg" 2>/dev/null || true)"
    fi
    if [ -z "$size" ]; then
        echo "SVG 크기(width/height/viewBox)를 읽을 수 없습니다: $svg" >&2
        return 1
    fi
    echo "$size"
}

# 공백·한글·특수문자가 있어도 안전한 file:// URL. 둘째 인자가 html이면 속성용 이스케이프.
file_url() {
    python3 -I -c '
import html, pathlib, sys
url = pathlib.Path(sys.argv[1]).resolve().as_uri()
print(html.escape(url, quote=True) if sys.argv[2:] == ["html"] else url)
' "$@"
}

# shot <tmp> <width> <height> <svg>: 2배 배율로 찍는다(투명 배경).
# 크롬의 stderr는 그대로 두고, 실패하면 어떤 SVG에서 실패했는지 찍는다.
shot() {
    local tmp="$1" w="$2" h="$3" svg="$4"
    if ! "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
            --default-background-color=00000000 \
            --force-device-scale-factor=2 --window-size="$w,$h" \
            --screenshot="$tmp" "file://$svg"; then
        echo "크롬 렌더 실패: $svg" >&2
        return 1
    fi
    if [ ! -s "$tmp" ]; then
        echo "PNG가 만들어지지 않았습니다: $svg" >&2
        return 1
    fi
}

count=0

# 아이콘: 256x256 창을 2배로 찍는다(512x512, 투명).
for svg in "$ASSETS_DIR"/icons/*.svg; do
    out="${svg%.svg}.png"
    shot "$TMP_DIR/icon.png" 256 256 "$svg"
    mv "$TMP_DIR/icon.png" "$out"
    count=$((count + 1))
done

# 일러스트: SVG width/height(viewBox 대체)를 2배로 찍는다(투명).
for svg in "$ASSETS_DIR"/illustrations/*.svg; do
    out="${svg%.svg}.png"
    size="$(read_size "$svg")"
    read -r w h <<<"$size"
    shot "$TMP_DIR/illus.png" "$w" "$h" "$svg"
    mv "$TMP_DIR/illus.png" "$out"
    count=$((count + 1))
done

# 다이어그램: 이름을 주면 그것만, 안 주면 전부. 흰 바탕으로 찍는다.
if [ "$#" -gt 0 ]; then
    names=("$@")
else
    names=()
    for svg in "$ASSETS_DIR"/diagrams/*.svg; do
        names+=("$(basename "${svg%.svg}")")
    done
fi

# 다이어그램이 하나도 없으면 이 단계는 건너뛴다(bash 3.2의 빈 배열 확장 안전하게).
for arg in ${names[@]+"${names[@]}"}; do
    name="$(basename "${arg%.svg}")"   # "diagrams/x.svg" 처럼 줘도 이름만 쓴다
    svg="$ASSETS_DIR/diagrams/$name.svg"
    png="$ASSETS_DIR/diagrams/$name.png"
    if [ ! -f "$svg" ]; then
        echo "SVG가 없습니다: $svg" >&2
        exit 1
    fi
    size="$(read_size "$svg" viewbox)"
    read -r width height <<<"$size"
    wrapper="$TMP_DIR/$name.html"
    svg_url="$(file_url "$svg" html)"
    cat >"$wrapper" <<HTML
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; background: #ffffff; }
  img { display: block; width: ${width}px; height: ${height}px; }
</style>
</head>
<body>
<img src="$svg_url" width="$width" height="$height">
</body>
</html>
HTML

    echo "렌더: $name (${width}x${height}) -> $png"
    tmp_png="$TMP_DIR/$name.png"   # 실패해도 기존 PNG는 남도록 임시 파일에 먼저 만든다
    if ! "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
            --force-device-scale-factor=2 --window-size="$width,$height" \
            --screenshot="$tmp_png" "$(file_url "$wrapper")"; then
        echo "크롬 렌더 실패: $svg" >&2
        exit 1
    fi
    if [ ! -s "$tmp_png" ]; then
        echo "PNG가 만들어지지 않았습니다: $name (기존 파일은 그대로 둡니다)" >&2
        exit 1
    fi
    mv "$tmp_png" "$png"
    count=$((count + 1))
done

echo "렌더 완료: PNG ${count}개"
