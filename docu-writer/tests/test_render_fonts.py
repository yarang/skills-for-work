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



def test_link_fonts_twice_replaces_old_links(tmp_path):
    """리뷰 3차 L1: 같은 프로필로 다시 부르면 옛 링크를 갈아 끼웁니다(FileExistsError 없음)."""
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    render.link_fonts(tmp_path / "profile", [fonts])
    links = render.link_fonts(tmp_path / "profile", [fonts])
    assert links[0].is_symlink() and links[0].resolve() == fonts.resolve()


def test_font_family_matches_whole_family_only():
    """리뷰 3차 L1: 「DejaVuSans」는 「DejaVuSans-Bold」와 한 가족이지만 「DejaVuSansMono」와는 다릅니다."""
    fam = render.font_family
    assert fam(render.norm_font("DejaVuSans-Bold")) == fam(render.norm_font("DejaVu Sans")) == "dejavusans"
    assert fam(render.norm_font("DejaVuSansMono")) != "dejavusans"


def test_substituted_chars_ignores_other_family_with_same_prefix():
    import pymupdf

    bundled = [(render.norm_font("DejaVu Sans Mono"), pymupdf.Font("helv"))]
    assert render.substituted_chars([span("BAAAAA+DejaVuSans", "한글")], bundled) == {}


def test_char_kinds_counts_without_echoing_text():
    """리뷰 3차 L1: 빈 글리프 보고에는 글자 대신 종류별 개수만 적습니다(문서 글이 새지 않게)."""
    shown = render.char_kinds({"홍", "길", "漢", "é"})
    assert "홍" not in shown and "漢" not in shown and "é" not in shown
    assert "한글 2자" in shown and "한자 1자" in shown and "기타 1자" in shown


# --- agy 6번 후속 -------------------------------------------------------------------

def test_link_fonts_drops_stale_links_when_dirs_shrink(tmp_path):
    """글꼴 폴더 목록이 줄면 옛 링크가 남아 지금 목록에 없는 폴더를 싣지 않습니다."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    render.link_fonts(tmp_path / "profile", [a, b])
    render.link_fonts(tmp_path / "profile", [a])
    names = sorted(x.name for x in (tmp_path / "profile/user/fonts").iterdir())
    assert names == ["00-a"]


def test_link_fonts_keeps_real_file_and_refuses(tmp_path):
    """링크 자리에 진짜 파일이 있으면 지우지 않고 멈춥니다. 상관없는 파일도 그대로 둡니다."""
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    target = tmp_path / "profile/user/fonts"
    target.mkdir(parents=True)
    (target / "00-fonts").write_text("keep", encoding="utf-8")
    (target / "notes.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(render.RenderError):
        render.link_fonts(tmp_path / "profile", [fonts])
    assert (target / "00-fonts").read_text(encoding="utf-8") == "keep"
    assert (target / "notes.txt").is_file()


def test_font_family_keeps_width_variant_as_other_family():
    """「Narrow」·「Condensed」는 굵기 꼬리가 아니라 다른 가족입니다."""
    fam = render.font_family
    assert fam(render.norm_font("LiberationSansNarrow-Bold")) == "liberationsansnarrow"
    assert fam(render.norm_font("LiberationSans-Bold")) == "liberationsans"


class _FakeFont:
    def __init__(self, name):
        self.name = name

    def has_glyph(self, ch):
        return ch < 0x80


def test_substituted_chars_matches_truncated_bundled_name():
    """pymupdf가 31바이트에서 자른 내장 글꼴 이름도 앞부분으로 맞춥니다."""
    name = "Noto Sans CJK KR Regular Extended"[:31]
    bundled = [(render.norm_font(name), _FakeFont(name))]
    spans = [span("BAAAAA+NotoSansCJKkr-Regular", "A한")]
    assert render.substituted_chars(spans, bundled) == {"NotoSansCJKkr-Regular": {"한"}}


def test_substituted_chars_short_name_needs_whole_family():
    """잘리지 않은 이름은 앞부분 맞추기를 쓰지 않습니다(DejaVuSansMono ≠ DejaVuSans)."""
    bundled = [(render.norm_font("DejaVu Sans Mono"), _FakeFont("DejaVu Sans Mono"))]
    assert render.substituted_chars([span("BAAAAA+DejaVuSans", "한")], bundled) == {}


def test_char_kinds_order_is_fixed():
    assert render.char_kinds({"é", "漢", "홍"}) == "한글 1자, 한자 1자, 기타 1자"
    assert render.char_kinds({"é", "홍"}) == "한글 1자, 기타 1자"


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
