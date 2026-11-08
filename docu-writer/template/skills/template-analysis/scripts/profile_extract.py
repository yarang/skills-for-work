# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-docx",
#     "python-pptx",
#     "pyyaml",
#     "lxml",
# ]
# ///
"""견본에서 표 목록·프로파일 초안을 뽑고, 프로파일을 점검합니다.

계약: template/skills/template-analysis/SKILL.md 「profile_extract.py 계약」.

    profile_extract.py tables <견본>
    profile_extract.py profile <견본> --mode sample|form|update --out <경로>
    profile_extract.py check <프로파일> --source <견본> [--tables <tables.yaml>]
    profile_extract.py check <프로파일>            (mode: new — 견본 없음, --source·--tables 받지 않음)

종료 코드: 0 성공, 1 check 실패 항목 있음, 2 사용법·형식·파일 오류(--out이 이미 있음 포함).
견본은 읽기만 하고, 오류가 나면 아무 파일도 쓰지 않습니다.
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pe_common import (UsageError, detect_format, dump_yaml, format_module, sha256_of,  # noqa: E402
                        yaml_error_brief)

PROFILE_FORMATS = ("docx", "pptx", "md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile_extract.py", description="견본 분석 도구")
    sub = parser.add_subparsers(dest="command", required=True)
    p_tables = sub.add_parser("tables", help="최상위 표 목록 (YAML, 표준 출력)")
    p_tables.add_argument("sample", type=Path)
    p_profile = sub.add_parser("profile", help="프로파일 초안 (DOCX·PPTX·MD)")
    p_profile.add_argument("sample", type=Path)
    p_profile.add_argument("--mode", required=True, choices=["sample", "form", "update"])
    p_profile.add_argument("--out", required=True, type=Path)
    p_check = sub.add_parser("check", help="프로파일 점검 (mode: new는 --source·--tables 없이)")
    p_check.add_argument("profile", type=Path)
    p_check.add_argument("--source", type=Path, help="견본 (mode: new가 아니면 필수)")
    p_check.add_argument("--tables", type=Path)
    return parser


def cmd_tables(args) -> int:
    fmt = detect_format(args.sample)
    tables, warnings = format_module(fmt).tables(args.sample)
    sys.stdout.write(dump_yaml({"tables": tables, "warnings": warnings}))
    return 0


def drop_field_labels(cands: list, fields: list) -> list:
    """칸 이름표는 견본 문구가 아니라 양식 뼈대이므로 후보에서 뺌 (공백 무시 비교)."""
    labels = {"".join(str(f.get("label") or "").split()) for f in fields}
    return [c for c in cands if "".join(c.split()) not in labels]


def assemble_profile(sample: Path, fmt: str, mode: str, parts: dict) -> dict:
    """형식 모듈이 뽑은 조각을 설계서 §5 순서의 프로파일 초안으로 묶음."""
    profile = {
        "profile_version": 1,
        "source": {"path": str(sample), "format": fmt, "sha256": sha256_of(sample)},
        "mode": mode,
        "structure": {"numbering": parts["numbering"], "sections": parts["sections"]},
        "fields": parts["fields"],
        "design": parts["design"],
        "sample_text": [],
        "sample_text_candidates": drop_field_labels(parts["candidates"], parts["fields"]),
        "objects": parts["objects"],
        "warnings": list(parts["warnings"]),
    }
    profile["warnings"].append("sample_text: analyst가 sample_text_candidates에서 골라 채움")
    if mode == "update":
        profile["warnings"].append("update: 갱신 요청은 analyst가 채움")
    return profile


def cmd_profile(args) -> int:
    fmt = detect_format(args.sample)
    if fmt not in PROFILE_FORMATS:
        raise UsageError(f"profile은 {fmt.upper()}를 지원하지 않음 (DOCX·PPTX·MD만)")
    if args.out.exists():
        raise UsageError(f"출력 파일이 이미 있음 (덮어쓰지 않음): {args.out}")
    parts = format_module(fmt).profile_parts(args.sample, args.mode)
    text = dump_yaml(assemble_profile(args.sample, fmt, args.mode, parts))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(args.out, "x", encoding="utf-8") as fh:
            fh.write(text)
    except FileExistsError as exc:
        raise UsageError(f"출력 파일이 이미 있음 (덮어쓰지 않음): {args.out}") from exc
    return 0


def profile_mode(path: Path):
    """(mode, 프로파일 사전). 파일이 없거나 YAML 문법이 틀리면 UsageError, 사전이 아니면 (None, None)."""
    if not path.is_file():
        raise UsageError(f"프로파일 파일 없음: {path}")
    try:
        prof = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise UsageError(f"프로파일 YAML 오류: {yaml_error_brief(exc)}") from exc
    return (prof.get("mode"), prof) if isinstance(prof, dict) else (None, None)


def check_fails(args) -> list:
    """모드에 맞게 --source·--tables를 확인하고 점검. 맞지 않으면 UsageError."""
    mode, prof = profile_mode(args.profile)
    if mode == "new":
        if args.source is not None or args.tables is not None:
            raise UsageError("mode: new 프로파일에는 --source·--tables를 주지 않음 (견본 없음)")
        from _pe_check_new import run_check_new

        return run_check_new(prof)
    if args.source is None and prof is None:
        raise UsageError(f"프로파일이 YAML 사전으로 읽히지 않아 mode를 알 수 없음: {args.profile}")
    if args.source is None:
        raise UsageError("--source가 필요함 (mode: new가 아닌 프로파일)")
    from _pe_check import run_check

    return run_check(args.profile, args.source, args.tables)


def cmd_check(args) -> int:
    fails = check_fails(args)
    if fails:
        print(f"check: 실패 {len(fails)}건")
        for fail in fails:
            print(f"- {fail}")
        return 1
    print("check: 통과")
    return 0


COMMANDS = {"tables": cmd_tables, "profile": cmd_profile, "check": cmd_check}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except UsageError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
