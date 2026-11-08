# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""템플릿 카탈로그에서 신규 작성 경로를 고르고, 카탈로그를 보여 주고, 점검합니다.

계약: docs/design.md §9.3, newdoc/skills/newdoc-workflow/SKILL.md ①,
docs/briefs/brief_newdoc.md N2.

    catalog.py match --type <문서 종류> --format md|docx|hwpx --out <route.json>
    catalog.py list [--format md|docx|hwpx]
    catalog.py check [<catalog.yaml>]

플러그인 카탈로그는 newdoc/templates/catalog.yaml, 사용자 카탈로그는
$DOCU_WRITER_TEMPLATES/catalog.yaml(없으면 ~/.config/docu-writer/templates/catalog.yaml)입니다.
match는 보호할 파일의 realpath를 한 줄에 하나씩 표준 출력에 냅니다.

종료 코드: 0 성공(match는 none 경로도 0), 1 check가 문제를 찾음,
2 사용법·YAML 문법·catalog_version·파일 없음·--out이 이미 있음. 오류가 나면 파일을 쓰지 않고
표준 출력에 아무것도 내지 않습니다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _cat_check import problems  # noqa: E402
from _cat_load import (  # noqa: E402
    FORMATS, CatalogError, load_all, load_catalog, merged_fixed, merged_themes, normalize, one_line,
    resolve,
)
from _cat_match import choose  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="catalog.py", description="템플릿 카탈로그 도구")
    parser.add_argument("--plugin-catalog", type=Path, default=None,
                        help="플러그인 카탈로그 대신 읽을 catalog.yaml (테스트 전용 — "
                             "작업 흐름은 이 옵션을 넘기지 않습니다)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_match = sub.add_parser("match", help="문서 종류·형식으로 경로를 골라 route.json을 씁니다")
    p_match.add_argument("--type", required=True, dest="doc_type", help="문서 종류(공백은 무시)")
    p_match.add_argument("--format", required=True, choices=FORMATS)
    p_match.add_argument("--out", required=True, type=Path, help="route.json 경로(이미 있으면 거부)")
    p_list = sub.add_parser("list", help="합친 카탈로그 항목을 한 줄에 하나씩 보여 줍니다")
    p_list.add_argument("--format", choices=FORMATS, default=None)
    p_check = sub.add_parser("check", help="카탈로그 항목 규칙을 점검합니다")
    p_check.add_argument("catalog", nargs="?", type=Path, default=None,
                         help="점검할 catalog.yaml (없으면 플러그인·사용자 카탈로그 둘 다)")
    return parser


def cmd_match(args) -> int:
    if not normalize(args.doc_type):
        raise CatalogError("--type이 비어 있습니다")
    catalogs = load_all(args.plugin_catalog)
    found = [line for catalog in catalogs for line in problems(catalog, files=False)]
    if found:
        raise CatalogError("카탈로그 항목이 잘못되었습니다(check로 확인하세요): " + "; ".join(found))
    route, protected = choose(merged_fixed(catalogs), merged_themes(catalogs), args.format, args.doc_type)
    bad = [path for path in protected if not one_line(path)]
    if bad:
        raise CatalogError("줄바꿈·앞뒤 공백이 든 경로가 있어 보호 목록(한 줄에 경로 하나)을 쓸 수 없습니다: "
                           + repr(bad[0]))
    if args.out.exists():
        raise CatalogError(f"이미 있는 파일은 덮어쓰지 않습니다: {args.out}")
    text = json.dumps(route, ensure_ascii=False, indent=2) + "\n"
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        handle = open(args.out, "x", encoding="utf-8")
    except OSError as err:
        # 여기서 실패하면 이 실행이 만든 파일이 없습니다 — 그사이 남이 만든 route.json(FileExistsError)을
        # 지우지 않도록 unlink는 「x」로 연 뒤의 쓰기 실패에서만 합니다 (리뷰 3차 M7)
        raise CatalogError(f"route.json을 쓸 수 없습니다: {args.out}: {err}") from err
    try:
        with handle:
            handle.write(text)
    except OSError as err:
        try:
            args.out.unlink(missing_ok=True)
        except OSError:
            pass
        raise CatalogError(f"route.json을 쓸 수 없습니다: {args.out}: {err}") from err
    sys.stdout.write("".join(f"{path}\n" for path in protected))
    return 0


def _describe(entry, catalog) -> str:
    if not isinstance(entry, dict):
        return "(끔)" if entry is None else repr(entry)
    parts = []
    for key, value in entry.items():
        if key == "preset_map" and isinstance(value, dict):
            parts.append("preset_map=" + ",".join(map(str, value)))
        elif key == "doc_type" and isinstance(value, list):
            parts.append("doc_type=" + ",".join(map(str, value)))
        elif key in ("reference_doc", "tokens", "template_path", "pack_path", "file", "profile") \
                and isinstance(value, str):
            parts.append(f"{key}={resolve(catalog, value)}")
        elif key != "id":
            parts.append(f"{key}={value}")
    return " ".join(parts)


def cmd_list(args) -> int:
    catalogs = load_all(args.plugin_catalog)
    out = []
    for key, item in merged_themes(catalogs).items():
        if args.format in (None, key.split("/", 1)[0]):
            out.append(f"theme {key} {item.catalog.source} {_describe(item.entry, item.catalog)}")
    for item in merged_fixed(catalogs):
        fmt = item.entry.get("format") if isinstance(item.entry, dict) else None
        if args.format in (None, fmt):
            out.append(f"fixed {item.key} {item.catalog.source} {_describe(item.entry, item.catalog)}")
    sys.stdout.write("".join(f"{line}\n" for line in out))
    return 0


def cmd_check(args) -> int:
    if args.catalog is not None:
        catalogs = [load_catalog(args.catalog, "지정")]
    else:
        catalogs = load_all(args.plugin_catalog)
    found = [line for catalog in catalogs for line in problems(catalog)]
    if found:
        sys.stdout.write(f"check: 실패 {len(found)}건\n" + "".join(f"- {line}\n" for line in found))
        return 1
    sys.stdout.write("check: 통과\n")
    return 0


COMMANDS = {"match": cmd_match, "list": cmd_list, "check": cmd_check}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except CatalogError as err:
        print(f"오류: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
