# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf"]
# ///
"""DOCX·PPTX·MD 결과 파일을 쪽별 PNG(150dpi)와 pages.json으로 렌더합니다.

계약: skills/doc-verify/SKILL.md 「렌더 (render.py)」.

    uv run render.py <결과 파일> <out-dir>

DOCX·PPTX는 soffice로 PDF를 만들고, MD는 pandoc으로 DOCX를 만든 뒤 같은 길을 갑니다.
PDF는 pymupdf로 쪽별 PNG와 쪽별 글로 바꿉니다. HWPX는 렌더하지 않습니다(종료 코드 2).
입력 파일은 고치지 않고, <out-dir> 바로 아래의 page_*·pages.json만 지운 뒤 씁니다.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUPPORTED = {".docx", ".pptx", ".md"}
FALLBACK_DIRS = [Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
                 Path("/Applications/LibreOffice.app/Contents/MacOS")]
DPI = 150
TIMEOUT = 300


class RenderError(Exception):
    """사용법·환경 오류 — 종료 코드 2."""


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for d in FALLBACK_DIRS:
        cand = d / name
        if cand.is_file():
            return str(cand)
    raise RenderError(f"{name}을(를) 찾을 수 없습니다")


def check_input(src: Path) -> None:
    if not src.is_file():
        raise RenderError(f"입력 파일이 없습니다: {src}")
    ext = src.suffix.lower()
    if ext == ".hwpx":
        raise RenderError("HWPX는 render.py가 렌더하지 않습니다 — kordoc render_document를 쓰십시오")
    if ext not in SUPPORTED:
        raise RenderError(f"지원하지 않는 형식입니다: {ext or '(확장자 없음)'}")


def run_tool(cmd: list[str], what: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"{what} 시간 초과({TIMEOUT}초)") from exc
    except OSError as exc:
        raise RenderError(f"{what} 실행 실패: {exc}") from exc


def md_to_docx(src: Path, work: Path, pandoc: str) -> Path:
    dst = work / f"{src.stem}.docx"
    proc = run_tool([pandoc, str(src), "-o", str(dst), f"--resource-path={src.parent}"], "pandoc")
    if proc.returncode != 0 or not dst.is_file():
        raise RenderError(f"pandoc 변환 실패: {proc.stderr.strip()}")
    return dst


def to_pdf(src: Path, work: Path, soffice: str) -> Path:
    """입력 복사본을 전용 LibreOffice 프로필로 변환합니다(실행 중인 인스턴스·잠긴 프로필 회피)."""
    staged_dir = work / "in"
    staged_dir.mkdir(exist_ok=True)
    staged = staged_dir / src.name
    shutil.copyfile(src, staged)
    outdir = work / "pdf"
    outdir.mkdir(exist_ok=True)
    profile = (work / "lo-profile").resolve()
    cmd = [soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore",
           "--convert-to", "pdf", "--outdir", str(outdir), str(staged)]
    proc = run_tool(cmd, "soffice")
    pdf = outdir / f"{staged.stem}.pdf"
    if not pdf.is_file():
        msg = (proc.stderr or proc.stdout).strip()
        raise RenderError(f"soffice PDF 변환 실패(종료 코드 {proc.returncode}): {msg}")
    return pdf


def prepare_out_dir(out_dir: Path) -> None:
    if out_dir.exists() and not out_dir.is_dir():
        raise RenderError(f"출력 경로가 디렉터리가 아닙니다: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)


def is_same(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def clean_out_dir(out_dir: Path, keep: Path) -> None:
    """바로 아래의 page_* 파일과 pages.json만 지웁니다. 입력 파일(keep)과 하위 디렉터리는 건드리지 않습니다."""
    for f in out_dir.iterdir():
        if not (f.name.startswith("page_") or f.name == "pages.json"):
            continue
        if (f.is_file() or f.is_symlink()) and not is_same(f, keep):
            f.unlink()


def publish(staged: Path, out_dir: Path, keep: Path) -> None:
    """다 만든 결과만 게시합니다. 같은 볼륨 안의 os.replace라 링크를 따라 쓰지 않습니다."""
    clean_out_dir(out_dir, keep)
    for f in sorted(staged.iterdir()):
        os.replace(f, out_dir / f.name)


def rasterize(pdf: Path, out_dir: Path) -> int:
    import pymupdf

    pages = []
    with pymupdf.open(str(pdf)) as doc:
        for i, page in enumerate(doc, 1):
            page.get_pixmap(dpi=DPI).save(str(out_dir / f"page_{i:03d}.png"))
            pages.append({"page": i, "text": page.get_text()})
    if not pages:
        raise RenderError("PDF에 쪽이 없습니다")
    (out_dir / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(pages)


def render(src: Path, out_dir: Path) -> int:
    check_input(src)
    soffice = find_tool("soffice")
    pandoc = find_tool("pandoc") if src.suffix.lower() == ".md" else None
    prepare_out_dir(out_dir)
    with tempfile.TemporaryDirectory(prefix="docu-render-") as tmp:
        work = Path(tmp)
        office_src = md_to_docx(src, work, pandoc) if pandoc else src
        pdf = to_pdf(office_src, work, soffice)
        # 변환·래스터화가 끝까지 성공한 뒤에만 기존 렌더 결과를 바꿉니다.
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=out_dir) as stage:
            count = rasterize(pdf, Path(stage))
            publish(Path(stage), out_dir, src)
        return count


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DOCX·PPTX·MD를 쪽별 PNG와 pages.json으로 렌더")
    ap.add_argument("input", type=Path, help="결과 파일 (.docx .pptx .md)")
    ap.add_argument("out_dir", type=Path, help="출력 디렉터리 (예: .docu-writer/render/)")
    args = ap.parse_args(argv)
    try:
        count = render(args.input.resolve(), args.out_dir.resolve())
    except (RenderError, OSError) as exc:
        print(f"render.py: {exc}", file=sys.stderr)
        return 2
    print(f"{count}쪽 → {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
