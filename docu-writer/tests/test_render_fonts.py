"""render.py 글꼴 회귀 테스트 (종단 시험 F3).

macOS의 LibreOffice가 headless 변환에서 시스템 글꼴을 찾지 못하면 한글이 내장 글꼴의
빈 글리프로 찍히고, pages.json 글은 멀쩡해 검사가 이를 알아채지 못했습니다.
render.py는 이제 글꼴 폴더를 전용 프로필에 링크하고, 그래도 빈 글리프가 남으면 종료 코드 2로 멈춥니다.
"""
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "skills/doc-verify/scripts"))
sys.dont_write_bytecode = True

import render  # noqa: E402


def span(font, text):
    return {"font": font, "chars": [(ord(c), i + 1, (0, 0), (0, 0, 1, 1)) for i, c in enumerate(text)]}


@pytest.fixture
def bundled():
    import pymupdf

    # helv(Helvetica 대체)는 한글이 없고 é는 있습니다 — 내장 Latin 글꼴의 대역입니다.
    return [(render.norm_font("Linux Libertine G Regular"), pymupdf.Font("helv"))]


def test_norm_font_strips_subset_prefix_and_punctuation():
    assert render.norm_font("BAAAAA+LinuxLibertineG") == "linuxlibertineg"
    assert render.norm_font("Caladea-Regular") == "caladearegular"


def test_substituted_chars_flags_missing_glyph_in_bundled_font(bundled):
    spans = [span("BAAAAA+LinuxLibertineG", "A 한글é")]
    assert render.substituted_chars(spans, bundled) == {"LinuxLibertineG": {"한", "글"}}


def test_substituted_chars_ignores_system_fonts(bundled):
    spans = [span("CAAAAA+AppleSDGothicNeo-Regular", "한글")]
    assert render.substituted_chars(spans, bundled) == {}


def test_font_dirs_env_first_and_existing_only(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    monkeypatch.setenv(render.FONT_ENV, f"{a}{render.os.pathsep}{b}")
    dirs = render.font_dirs()
    assert dirs[0] == a and b not in dirs


def test_link_fonts_makes_directory_links(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "x.ttf").write_bytes(b"")
    links = render.link_fonts(tmp_path / "profile", [fonts])
    assert [p.parent for p in links] == [tmp_path / "profile/user/fonts"]
    assert links[0].is_symlink() and (links[0] / "x.ttf").is_file()


needs_soffice = pytest.mark.skipif(
    not (shutil.which("soffice") or Path("/Applications/LibreOffice.app").exists()), reason="soffice 없음")


@needs_soffice
def test_fontless_profile_detected_or_environment_fine(samples, tmp_path, monkeypatch):
    """글꼴 링크 없이 변환했을 때 빈 글리프가 나는 환경이면 check_glyphs가 반드시 잡아야 합니다."""
    soffice = render.find_tool("soffice")
    monkeypatch.setattr(render, "font_dirs", lambda: [])
    pdf = render.to_pdf(samples["docx"], tmp_path, soffice)
    import pymupdf

    bundled = render.bundled_fonts(soffice)
    with pymupdf.open(str(pdf)) as doc:
        broken = any(render.substituted_chars(p.get_texttrace(), bundled) for p in doc)
    if not broken:
        pytest.skip("이 환경의 LibreOffice는 글꼴 링크 없이도 한글 글꼴을 찾습니다")
    with pytest.raises(render.RenderError, match=render.FONT_ENV):
        render.check_glyphs(pdf, soffice)


@needs_soffice
def test_render_with_font_links_has_no_substituted_glyphs(samples, tmp_path):
    soffice = render.find_tool("soffice")
    pdf = render.to_pdf(samples["docx"], tmp_path, soffice)
    render.check_glyphs(pdf, soffice)  # RenderError 없이 끝나야 합니다
