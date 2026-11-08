# /// script
# requires-python = ">=3.13"
# dependencies = ["python-docx", "python-pptx", "pyyaml", "lxml"]
# ///
"""결과 문서를 프로파일·견본과 대조해 13개 검사를 돌리고 report.json과 요약을 냅니다.

계약: skills/doc-verify/SKILL.md 「검사 항목」·「검사 세부」·「출력」.

    uv run doc_verify.py --profile P [--source S --expect-sha256 H] --output O \\
        [--placeholders F] [--pages-dir D] --out-dir R

--source·--expect-sha256은 mode: new에서만 뺄 수 있습니다(SKILL.md 「신규 모드」).

종료 코드: 0 = pass·warn·skip만, 1 = fail 하나 이상, 2 = 사용법·환경 오류.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True  # 스킬 디렉터리에 __pycache__를 남기지 않습니다.

import yaml  # noqa: E402

from _checks_content import (Ctx, check_fields, check_hash, check_length,  # noqa: E402
                             check_markup, check_placeholder, check_residue, check_scope,
                             entry)
from _checks_design import (check_r1, check_r4, check_r5, check_r6,  # noqa: E402
                            check_rewrite, check_table_header)
from _readers import Doc, doc_format, read_doc  # noqa: E402

MODES = {"sample", "form", "update", "new"}
CHECKS = [
    ("hash", check_hash), ("residue", check_residue), ("markup", check_markup),
    ("placeholder", check_placeholder),
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


def yaml_error_brief(exc: Exception) -> str:
    """YAML 읽기 오류를 원문 없이 — PyYAML 메시지는 틀린 줄을 그대로 보여 주므로(개인정보·비밀값)
    종류와 위치만 남깁니다(리뷰 3차 M9). 파일 오류(OSError)는 경로만 담으므로 그대로 둡니다."""
    if isinstance(exc, OSError):
        return str(exc)
    if isinstance(exc, UnicodeDecodeError):
        return f"UTF-8로 읽을 수 없음 ({exc.start}번째 바이트)"
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is not None:
        return f"{type(exc).__name__} ({mark.line + 1}행 {mark.column + 1}열)"
    position = getattr(exc, "position", None)
    if position is not None:
        return f"{type(exc).__name__} ({position}번째 글자)"
    return type(exc).__name__


def _load_yaml(path: Path, what: str):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise UsageError(f"{what}을(를) 읽을 수 없습니다: {yaml_error_brief(exc)}") from exc


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

    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, load_dtd=False)
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
    single = pages_dir / "page.svg"  # kordoc은 한 쪽만 렌더하면 _page_NNN 접미 없이 냅니다 (종단 시험 F14)
    if single.is_file():
        if svgs:
            raise UsageError(f"{pages_dir}에 page.svg와 page_NNN.svg가 섞여 있습니다 — 이전 렌더를 지우고 다시 렌더하십시오")
        svgs = [single]
    return [_svg_text(p) for p in svgs] or None


def _source_args(args, mode: str) -> Path | None:
    """--source·--expect-sha256 조합을 모드에 맞게 확인합니다. 견본을 쓸 때만 경로를 돌려줍니다.

    mode: new는 둘 다 없거나 둘 다 있어야 하고(있어도 견본 대조는 하지 않음), 다른 모드는 둘 다 필수입니다."""
    given = [name for name, value in (("--source", args.source), ("--expect-sha256", args.expect_sha256))
             if value is not None]
    if mode == "new":
        if len(given) == 1:
            raise UsageError(f"mode: new에서는 --source와 --expect-sha256을 함께 주거나 둘 다 빼야 합니다 "
                             f"(받은 인자: {given[0]})")
        return _need_doc(args.source, "견본") if given else None
    missing = [n for n in ("--source", "--expect-sha256") if n not in given]
    if missing:
        raise UsageError(f"mode: {mode}에서는 다음 인자가 필요합니다: {', '.join(missing)}")
    return _need_doc(args.source, "견본")


def build_ctx(args) -> Ctx:
    prof = load_profile(args.profile)
    mode = prof["mode"]
    source = _source_args(args, mode)
    output = _need_doc(args.output, "결과")
    placeholders = load_placeholders(args.placeholders)
    pages = load_pages(args.pages_dir)
    try:
        out = read_doc(output)
        # 신규 모드는 견본이 없습니다. 견본 자리에는 빈 문서를 두고 검사는 mode로 가릅니다.
        src = Doc(out.fmt, []) if mode == "new" else read_doc(source)
    except Exception as exc:  # 형식 라이브러리 오류는 종류가 많아 한데 받습니다.
        raise UsageError(f"문서를 읽을 수 없습니다: {exc}") from exc
    expect = args.expect_sha256 if mode != "new" else None
    return Ctx(prof, mode, source if mode != "new" else None, expect, output, src, out,
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
    ap.add_argument("--source", type=Path, help="견본 파일 (mode: new는 선택)")
    ap.add_argument("--expect-sha256", help="견본의 기대 sha256 (mode: new는 선택)")
    ap.add_argument("--output", type=Path, required=True, help="결과 파일")
    ap.add_argument("--placeholders", type=Path, help="자리표시 목록 YAML")
    ap.add_argument("--pages-dir", type=Path, help="렌더 디렉터리 (pages.json 또는 page_NNN.svg)")
    ap.add_argument("--out-dir", type=Path, required=True, help="report.json을 쓸 디렉터리")
    return ap.parse_args(argv)


def write_report(out_dir: Path, report: list) -> None:
    """임시 파일에 다 쓴 뒤 os.replace로 바꿉니다. report.json이 견본을 가리키는
    심볼릭 링크나 하드 링크여도 링크 자체만 바뀌고 견본은 그대로입니다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".report-", suffix=".json", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, out_dir / "report.json")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ctx = build_ctx(args)
        report = run_checks(ctx)
        write_report(args.out_dir, report)
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
