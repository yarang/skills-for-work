# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-pptx",
#     "pyyaml",
#     "lxml",
# ]
# ///
"""PPTX sample patcher: `dump` a locator-tagged skeleton, `apply` an edit list to a copy.

Contract: skills/format-pptx/SKILL.md 「작성 (⑤) — patch_pptx.py」.
Exit codes: 0 all applied; 1 failed edits (no output written); 2 usage/environment error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from pptx import Presentation  # noqa: E402

from _pp_dump import dump_blocks  # noqa: E402
from _pp_ops import EditError, Planner, edit_at  # noqa: E402


class UsageError(Exception):
    """Usage or environment problem (exit 2)."""


def same_file(a: Path, b: Path) -> bool:
    if os.path.realpath(a) == os.path.realpath(b):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def require_file(path: Path, what: str) -> None:
    if not path.is_file():
        raise UsageError(f"{what} not found: {path}")


def load_pptx(path: Path):
    require_file(path, "sample")
    try:
        return Presentation(str(path))
    except Exception as exc:  # noqa: BLE001 - any parse failure is an input error
        raise UsageError(f"cannot open {path} as PPTX: {exc}") from exc


def load_yaml(path: Path, what: str):
    require_file(path, what)
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise UsageError(f"cannot parse {what} {path}: {exc}") from exc


def check_out(sample: Path, out: Path) -> None:
    if same_file(sample, out):
        raise UsageError(f"--out is the sample itself: {out}")
    if os.path.lexists(out):
        raise UsageError(f"--out already exists: {out}")
    try:
        out.resolve().parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UsageError(f"cannot create --out directory: {exc}") from exc


def styles_allowed(profile) -> list:
    if profile is None:
        return []
    if not isinstance(profile, dict):
        raise UsageError("profile must be a mapping")
    allowed = (profile.get("design") or {}).get("styles_allowed") or []
    if not isinstance(allowed, list):
        raise UsageError("profile design.styles_allowed must be a list")
    return [str(s) for s in allowed]


def cmd_dump(args) -> int:
    sample, out = Path(args.sample), Path(args.out)
    check_out(sample, out)
    blocks = dump_blocks(load_pptx(sample))
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(yaml.safe_dump(blocks, allow_unicode=True, sort_keys=False))
    return 0


def plan_edits(prs, edits, allowed) -> tuple[Planner, list[dict]]:
    planner = Planner(prs, allowed)
    failed = []
    for edit in edits:
        try:
            planner.add(edit)
        except EditError as exc:
            op = edit.get("op") if isinstance(edit, dict) else None
            failed.append({"op": op, "at": edit_at(edit), "reason": str(exc)})
    return planner, failed


def report(applied: int, failed: list, warnings: list) -> None:
    print(json.dumps({"applied": applied, "failed": failed, "warnings": warnings},
                     ensure_ascii=False))


def cmd_apply(args) -> int:
    sample, out = Path(args.sample), Path(args.out)
    check_out(sample, out)
    prs = load_pptx(sample)
    edits = load_yaml(Path(args.edits), "edits")
    if edits is None:
        edits = []
    if not isinstance(edits, list):
        raise UsageError("edits file must be a YAML list")
    allowed = styles_allowed(load_yaml(Path(args.profile), "profile"))
    planner, failed = plan_edits(prs, edits, allowed)
    if not failed:
        failed = planner.run()
    if failed:
        report(0, failed, planner.warnings)
        return 1
    save(prs, out)
    report(len(edits), [], planner.warnings)
    return 0


def save(prs, out: Path) -> None:
    """Create the output exclusively, so a file or link that appeared after
    check_out() is never overwritten; on failure remove only our own file."""
    try:
        fh = open(out, "xb")
    except OSError as exc:
        raise UsageError(f"cannot create {out}: {exc}") from exc
    try:
        with fh:
            prs.save(fh)
    except Exception as exc:  # noqa: BLE001 - leave no partial output behind
        out.unlink(missing_ok=True)
        raise UsageError(f"cannot write {out}: {exc}") from exc
    except BaseException:  # Ctrl-C etc.: still leave no partial output behind
        out.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patch_pptx.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="write the locator skeleton of a sample deck")
    d.add_argument("sample")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_dump)
    a = sub.add_parser("apply", help="apply edits.yaml to a copy of the sample deck")
    a.add_argument("sample")
    a.add_argument("--edits", required=True)
    a.add_argument("--profile", required=True)
    a.add_argument("--out", required=True)
    a.set_defaults(func=cmd_apply)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UsageError, OSError) as exc:
        print(f"patch_pptx: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
