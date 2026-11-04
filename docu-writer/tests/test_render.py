"""render.py 수용 테스트 (soffice·pandoc 필요).

계약: skills/doc-verify/SKILL.md 「렌더 (render.py)」.
"""
import json
import shutil

import pytest

from conftest import RENDER, uv

pytestmark = pytest.mark.skipif(
    not (shutil.which("soffice") and shutil.which("pandoc")), reason="soffice·pandoc 없음"
)


def render(src, out_dir):
    proc = uv(RENDER, src, out_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    pages = json.loads((out_dir / "pages.json").read_text(encoding="utf-8"))
    return pages


def test_render_docx(samples, tmp_path):
    out = tmp_path / "render"
    pages = render(samples["docx"], out)
    assert [p["page"] for p in pages] == list(range(1, len(pages) + 1))
    assert "추진배경" in "".join(p["text"] for p in pages).replace(" ", "")
    assert sorted(f.name for f in out.glob("page_*.png")) == [f"page_{i:03d}.png" for i in range(1, len(pages) + 1)]


def test_render_pptx_one_page_per_slide(samples, tmp_path):
    pages = render(samples["pptx"], tmp_path / "render")
    assert len(pages) == 3
    assert "실적" in pages[2]["text"]


def test_render_md_via_pandoc(samples, tmp_path):
    pages = render(samples["md"], tmp_path / "render")
    assert "추진배경" in "".join(p["text"] for p in pages).replace(" ", "")


def test_render_cleans_only_previous_pages(samples, tmp_path):
    out = tmp_path / "render"
    (out / "source").mkdir(parents=True)
    (out / "source" / "page.svg").write_text("<svg/>", encoding="utf-8")
    (out / "page_099.png").write_bytes(b"old")
    (out / "notes.txt").write_text("keep", encoding="utf-8")
    pages = render(samples["pptx"], out)
    assert not (out / "page_099.png").exists()
    assert len(list(out.glob("page_*.png"))) == len(pages)
    assert (out / "source" / "page.svg").read_text(encoding="utf-8") == "<svg/>"
    assert (out / "notes.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("name", ["sample.hwpx", "missing.docx", "a.txt"])
def test_render_unsupported_or_missing_exit_2(samples, tmp_path, name):
    src = samples["hwpx"] if name == "sample.hwpx" else tmp_path / name
    if name == "a.txt":
        src.write_text("x", encoding="utf-8")
    assert uv(RENDER, src, tmp_path / "render").returncode == 2


def test_render_does_not_touch_input(samples, tmp_path):
    before = samples["docx"].read_bytes()
    render(samples["docx"], tmp_path / "render")
    assert samples["docx"].read_bytes() == before
