# /// script
# requires-python = ">=3.13"
# dependencies = ["python-docx", "python-pptx", "pyyaml", "lxml"]
# ///
"""결과 문서를 프로파일·견본과 대조해 12개 검사를 돌리고 report.json과 요약을 냅니다.

계약: skills/doc-verify/SKILL.md 「검사 항목」·「검사 세부」·「출력」.

    uv run doc_verify.py --profile P --source S --expect-sha256 H --output O \\
        [--placeholders F] [--pages-dir D] --out-dir R

종료 코드: 0 = pass·warn·skip만, 1 = fail 하나 이상, 2 = 사용법·환경 오류.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True  # 스킬 디렉터리에 __pycache__를 남기지 않습니다.

import yaml  # noqa: E402

from _checks_content import (Ctx, check_fields, check_hash, check_length,  # noqa: E402
                             check_placeholder, check_residue, check_scope, entry)
from _checks_design import (check_r1, check_r4, check_r5, check_r6,  # noqa: E402
                            check_rewrite, check_table_header)
from _readers import doc_format, read_doc  # noqa: E402

MODES = {"sample", "form", "update", "new"}
CHECKS = [
    ("hash", check_hash), ("residue", check_residue), ("placeholder", check_placeholder),
    ("fields", check_fields), ("scope", check_scope), ("r4_headings", check_r4),
    ("r5_tokens", check_r5), ("r6_numbering", check_r6), ("table_header", check_table_header),
    ("length", check_length), ("r1_tables", check_r1), ("rewrite", check_rewrite),
]


class UsageError(Exception):
    """사용법·환경 오류 — 종료 코드 2."""


def _need_file(path: Path, what: str) -> Path:
    if not path.is_file():
        raise UsageError(f"{what} 파일이 없습니다: {path}")
    return path


def _need_doc(path: Path, what: str) -> Path:
    _need_file(path, what)
    if doc_format(path) is None:
        raise UsageError(f"{what} 형식을 지원하지 않습니다: {path.suffix or '(확장자 없음)'}")
    return path


def _load_yaml(path: Path, what: str):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise UsageError(f"{what}을(를) 읽을 수 없습니다: {exc}") from exc


def load_profile(path: Path) -> dict:
    prof = _load_yaml(_need_file(path, "프로파일"), "프로파일")
    if not isinstance(prof, dict):
        raise UsageError("프로파일이 YAML 매핑이 아닙니다")
    if prof.get("mode") not in MODES:
        raise UsageError(f"프로파일 mode가 {sorted(MODES)} 중 하나가 아닙니다: {prof.get('mode')!r}")
    return prof


def load_placeholders(path: Path | None) -> list | None:
    if path is None:
        return None
    data = _load_yaml(_need_file(path, "자리표시 목록"), "자리표시 목록")
    if data is None:
        return []
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise UsageError("자리표시 목록은 {locator, expect} 항목의 YAML 목록이어야 합니다")
    return data


def _svg_text(path: Path) -> str:
    from lxml import etree

    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(path.read_bytes(), parser)
    if root is None:
        return ""
    texts = ["".join(el.itertext()) for el in root.iter()
             if isinstance(el.tag, str) and etree.QName(el).localname == "text"]
    return "\n".join(texts)


def load_pages(pages_dir: Path | None) -> list | None:
    """쪽별 글 목록. pages.json → page_NNN.svg 순. 렌더가 없으면 None."""
    if pages_dir is None or not pages_dir.is_dir():
        return None
    pj = pages_dir / "pages.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UsageError(f"pages.json을 읽을 수 없습니다: {exc}") from exc
        items = sorted((d for d in data if isinstance(d, dict)), key=lambda d: d.get("page", 0))
        return [str(d.get("text") or "") for d in items] or None
    svgs = [p for p in pages_dir.glob("page_*.svg") if re.search(r"\d+", p.stem)]
    svgs.sort(key=lambda p: int(re.search(r"\d+", p.stem).group()))
    return [_svg_text(p) for p in svgs] or None


def build_ctx(args) -> Ctx:
    prof = load_profile(args.profile)
    source = _need_doc(args.source, "견본")
    output = _need_doc(args.output, "결과")
    placeholders = load_placeholders(args.placeholders)
    pages = load_pages(args.pages_dir)
    try:
        src, out = read_doc(source), read_doc(output)
    except Exception as exc:  # 형식 라이브러리 오류는 종류가 많아 한데 받습니다.
        raise UsageError(f"문서를 읽을 수 없습니다: {exc}") from exc
    return Ctx(prof, prof["mode"], source, args.expect_sha256, output, src, out,
               placeholders, pages, args.pages_dir)


def run_checks(ctx: Ctx) -> list:
    report = []
    for cid, check in CHECKS:
        try:
            report.append(check(ctx))
        except Exception as exc:  # 검사 하나의 오류가 나머지 검사를 막지 않게 합니다.
            report.append(entry(cid, "fail", f"검사 오류: {type(exc).__name__}: {exc}"))
    return report


def summary(output: Path, report: list, code: int) -> str:
    verdict = "통과" if code == 0 else "차단"
    lines = [f"### 문서 검증: {output}", f"- 결과: {verdict} (종료 코드 {code})"]
    lines += [f"  {e['status']:<6}{e['id']:<14}{e['detail']}" for e in report]
    return "\n".join(lines)


def parse_args(argv):
    ap = argparse.ArgumentParser(description="결과 문서를 프로파일·견본과 대조해 검증")
    ap.add_argument("--profile", type=Path, required=True, help="profile.yaml")
    ap.add_argument("--source", type=Path, required=True, help="견본 파일")
    ap.add_argument("--expect-sha256", required=True, help="견본의 기대 sha256")
    ap.add_argument("--output", type=Path, required=True, help="결과 파일")
    ap.add_argument("--placeholders", type=Path, help="자리표시 목록 YAML")
    ap.add_argument("--pages-dir", type=Path, help="렌더 디렉터리 (pages.json 또는 page_NNN.svg)")
    ap.add_argument("--out-dir", type=Path, required=True, help="report.json을 쓸 디렉터리")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ctx = build_ctx(args)
        report = run_checks(ctx)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except (UsageError, OSError) as exc:
        print(f"doc_verify.py: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # 입력 결함(깨진 pages.json 등)이 종료 코드 1(차단)로 보이지 않게 합니다.
        print(f"doc_verify.py: 입력을 처리할 수 없습니다: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    code = 1 if any(e["status"] == "fail" for e in report) else 0
    print(summary(args.output, report, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
