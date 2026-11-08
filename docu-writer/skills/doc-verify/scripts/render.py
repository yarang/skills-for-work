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
import re
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
# macOS의 LibreOffice는 headless 변환에서 시스템 글꼴을 하나도 찾지 못하고 내장 글꼴로만 그리는 일이
# 있습니다(종단 시험: 한글이 LinuxLibertineG의 빈 글리프로 찍힘). 전용 프로필의 user/fonts에 글꼴
# 폴더 링크를 두면 그 글꼴을 읽으므로, 있는 폴더를 모두 링크합니다.
FONT_ENV = "DOCU_WRITER_FONT_DIRS"
MAC_FONT_DIRS = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
BUNDLED_FONT_DIRS = ["../Resources/fonts/truetype", "../share/fonts/truetype"]  # soffice 기준
FONT_FILES = {".ttf", ".otf", ".ttc"}


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


def font_dirs() -> list[Path]:
    """FONT_ENV(경로 구분자로 나눔)와 macOS 표준 글꼴 폴더 중 실제로 있는 디렉터리."""
    extra = [Path(p).expanduser() for p in os.environ.get(FONT_ENV, "").split(os.pathsep) if p]
    system = MAC_FONT_DIRS if sys.platform == "darwin" else []
    return [d for d in dict.fromkeys([*extra, *system]) if d.is_dir()]


def link_fonts(profile: Path, dirs: list[Path]) -> list[Path]:
    """<profile>/user/fonts/ 아래에 글꼴 폴더 링크를 만듭니다. 글꼴 파일은 복사하지 않습니다."""
    target = profile / "user" / "fonts"
    target.mkdir(parents=True, exist_ok=True)
    links = []
    for i, d in enumerate(dirs):
        link = target / f"{i:02d}-{d.name or 'fonts'}"
        if link.is_symlink() or link.is_file():  # 다시 부른 프로필의 옛 링크 — FileExistsError 대신 갈아 끼움 (L1)
            link.unlink()
        link.symlink_to(d.resolve(), target_is_directory=True)
        links.append(link)
    return links


def to_pdf(src: Path, work: Path, soffice: str) -> Path:
    """입력 복사본을 전용 LibreOffice 프로필로 변환합니다(실행 중인 인스턴스·잠긴 프로필 회피)."""
    staged_dir = work / "in"
    staged_dir.mkdir(exist_ok=True)
    staged = staged_dir / src.name
    shutil.copyfile(src, staged)
    outdir = work / "pdf"
    outdir.mkdir(exist_ok=True)
    profile = (work / "lo-profile").resolve()
    link_fonts(profile, font_dirs())
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


def norm_font(name: str) -> str:
    """서브셋 접두어(ABCDEF+)를 떼고 소문자 영숫자만 남깁니다. PDF의 PostScript 이름과
    글꼴 파일의 전체 이름("Linux Libertine G Regular")을 같은 잣대로 맞추기 위해서입니다."""
    return re.sub(r"[^0-9a-z]", "", name.split("+", 1)[-1].lower())


STYLE_SUFFIX = re.compile(r"(?:regular|book|roman|normal|medium|bold|italic|oblique|light|semi|demi|extra"
                          r"|ultra|black|heavy|thin|condensed|narrow)+$")


def font_family(norm: str) -> str:
    """norm_font 이름에서 끝의 굵기·기울기 꼬리를 뗀 글꼴 가족 이름("caladearegular"→"caladea")."""
    return STYLE_SUFFIX.sub("", norm) or norm


def bundled_fonts(soffice: str) -> list[tuple[str, object]]:
    """LibreOffice가 함께 싣는 글꼴 (정규화한 이름, pymupdf.Font). 폴더를 못 찾으면 빈 목록."""
    import pymupdf

    base = Path(soffice).resolve().parent
    dirs = [(base / rel).resolve() for rel in BUNDLED_FONT_DIRS]
    dirs += [d.parent / "Resources/fonts/truetype" for d in FALLBACK_DIRS if d.name == "MacOS"]
    fonts = []
    for d in dict.fromkeys(dirs):
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in FONT_FILES:
                continue
            try:
                font = pymupdf.Font(fontfile=str(f))
            except Exception:  # noqa: BLE001 - 읽지 못한 글꼴은 판정에서 뺍니다
                continue
            fonts.append((norm_font(font.name), font))
    return fonts


def substituted_chars(trace_spans, bundled) -> dict[str, set[str]]:
    """내장 글꼴로 찍혔는데 그 내장 글꼴에 없는 비ASCII 글자를 {글꼴: 글자들}로 돌려줍니다.

    PDF 안 서브셋 글꼴은 cmap이 없어 직접 물을 수 없으므로, 같은 이름의 원본 글꼴 파일에
    글리프가 있는지 봅니다. 시스템 글꼴(내장 목록에 없는 이름)은 판정하지 않습니다."""
    missing: dict[str, set[str]] = {}
    for span in trace_spans:
        key = font_family(norm_font(span["font"]))
        # 가족 이름이 같은 것만 — 앞부분 맞추기는 「DejaVuSans」가 「DejaVuSansMono」까지 잡았습니다 (L1)
        cands = [f for n, f in bundled if key and font_family(n) == key]
        if not cands:
            continue
        for ch, *_ in span["chars"]:
            if ch < 0x80 or chr(ch).isspace():
                continue
            if not any(f.has_glyph(ch) for f in cands):
                missing.setdefault(span["font"].split("+", 1)[-1], set()).add(chr(ch))
    return missing


def char_kinds(chars) -> str:
    """글자 모음을 「한글 12자, 기타 3자」처럼 종류별 개수로."""
    counts: dict[str, int] = {}
    for ch in chars:
        o = ord(ch)
        kind = ("한글" if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F
                else "한자" if 0x4E00 <= o <= 0x9FFF else "기타")
        counts[kind] = counts.get(kind, 0) + 1
    return ", ".join(f"{k} {n}자" for k, n in counts.items())


def check_glyphs(pdf: Path, soffice: str) -> None:
    """빈 글리프로 찍힌 글자가 있으면 RenderError — PNG가 내용을 보여 주지 못하기 때문입니다."""
    import pymupdf

    bundled = bundled_fonts(soffice)
    if not bundled:
        return
    missing: dict[str, set[str]] = {}
    with pymupdf.open(str(pdf)) as doc:
        for page in doc:
            for font, chars in substituted_chars(page.get_texttrace(), bundled).items():
                missing.setdefault(font, set()).update(chars)
    if missing:
        # 글자 자체는 보고하지 않습니다 — 문서 글이 오류 메시지로 새지 않도록 종류별 개수만 (리뷰 3차 L1)
        detail = "; ".join(f"{f}: {char_kinds(c)}" for f, c in sorted(missing.items()))
        raise RenderError(
            f"LibreOffice가 글꼴을 찾지 못해 글자를 빈 글리프로 그렸습니다({detail}). "
            f"한글 글꼴이 든 폴더를 {FONT_ENV}에 적고(여럿이면 '{os.pathsep}'로 구분) 다시 실행하십시오")


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
        check_glyphs(pdf, soffice)
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
