# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-pptx",
#     "pyyaml",
# ]
# ///
"""원고 마크다운 + `<!-- visual: {...} -->` 주석 → 16:9 PPTX 덱 생성기.

사용 예:
    uv run build_deck.py 원고.md -o 덱.pptx
    uv run build_deck.py 원고.md -o 덱.pptx --assets 자산폴더 --config deck.yaml
    uv run build_deck.py 원고.md -o 덱.pptx --font "Apple SD Gothic Neo" --dump

원고 구조·레이아웃·글자 크기 규칙은 SKILL.md 참고.
--assets 기본값은 원고 파일이 있는 폴더. 그 아래 icons/<이름>.png,
illustrations/<이름>.png, 그리고 원고의 `![..](diagrams/x.svg)`와 같은 폴더의
같은 이름 .png를 찾는다. PNG가 없으면 render_svgs.sh 안내와 함께 실패한다.

종료 코드: 0 성공, 1 원고·주석·경계·자산 오류, 2 사용법 오류.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pptx import Presentation  # noqa: E402
from pptx.util import Inches  # noqa: E402

from _deck_layouts import (DeckContext, add_agenda_slide, add_divider_slide,  # noqa: E402
                           add_footer, add_header, add_notes, add_title_slide,
                           display_title, new_slide)
from _deck_layouts2 import layout_content  # noqa: E402
from _deck_parse import Assets, Config, load_config, parse_doc  # noqa: E402
from _deck_theme import (BOUNDS_TOL_IN, DEFAULT_FONT, EMU_PER_IN, MONO_FONT,  # noqa: E402
                         SLIDE_H_IN, SLIDE_W_IN, Theme)

EMU_EPS = int(BOUNDS_TOL_IN * EMU_PER_IN)


# ── 덱 조립 ────────────────────────────────────────────────────

def add_content_slide(prs, blank, data, section, ctx: DeckContext):
    visual = data.visual
    dark = bool(visual.get("dark"))
    slide = new_slide(prs, blank, ctx.theme.primary if dark else ctx.theme.surface)
    try:
        add_header(slide, display_title(data.title, visual), ctx,
                   icon=section.visual.get("icon"), badge=visual.get("badge"), dark=dark)
        layout_content(slide, data, ctx)
    except FileNotFoundError as exc:
        # 자산 없음: 종류는 그대로 두되 어느 슬라이드인지 제목을 붙인다.
        if str(exc).startswith(f"[{data.title}]"):
            raise
        raise FileNotFoundError(f"[{data.title}] {exc}") from exc
    except (ValueError, TypeError, KeyError) as exc:
        # 레이아웃이 visual 값을 읽다 낸 오류에 슬라이드 제목을 붙여 올린다.
        if str(exc).startswith(f"[{data.title}]"):
            raise
        raise ValueError(f"[{data.title}] {exc}") from exc
    if data.notes:
        add_notes(slide, data.notes, ctx.theme)
    add_footer(prs, slide, ctx, dark=dark)
    return slide


def build_deck(doc, ctx: DeckContext) -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W_IN)
    prs.slide_height = Inches(SLIDE_H_IN)
    blank = prs.slide_layouts[6]
    add_title_slide(prs, blank, doc, ctx)
    titles = [doc.title]
    if doc.sections:  # 섹션이 모두 제외되면 목차 없이 표지로 끝낸다
        add_agenda_slide(prs, blank, doc, ctx)
        titles.append("목차")
    for section in doc.sections:
        # 내용 슬라이드가 1장뿐인 섹션과 divider:false 섹션은 구분 슬라이드를
        # 만들지 않는다(목차에는 남는다).
        if section.visual.get("divider", True) and len(section.slides) > 1:
            add_divider_slide(prs, blank, section, ctx)
            titles.append(section.title)
        for data in section.slides:
            add_content_slide(prs, blank, data, section, ctx)
            titles.append(data.title)
    check_bounds(prs, titles)
    return prs


def check_bounds(prs: Presentation, titles: list[str]) -> None:
    """모든 슬라이드의 모든 도형이 13.333x7.5in 안에 있는지 검사한다(허용 오차 0.01in)."""
    width, height = Inches(SLIDE_W_IN), Inches(SLIDE_H_IN)
    for idx, (title, slide) in enumerate(zip(titles, prs.slides), 1):
        for shape in slide.shapes:
            l, t, w, h = shape.left, shape.top, shape.width, shape.height
            if None in (l, t, w, h):
                continue
            if w <= 0 or h <= 0:
                raise ValueError(
                    f"{idx}번 슬라이드 '{title}' 도형 크기가 0 이하: "
                    f"{shape.name} w={w / EMU_PER_IN:.2f}in h={h / EMU_PER_IN:.2f}in")
            over = []
            if l < -EMU_EPS:
                over.append(f"left={l / EMU_PER_IN:.2f}in")
            if t < -EMU_EPS:
                over.append(f"top={t / EMU_PER_IN:.2f}in")
            if l + w > width + EMU_EPS:
                over.append(f"right={(l + w) / EMU_PER_IN:.2f}in")
            if t + h > height + EMU_EPS:
                over.append(f"bottom={(t + h) / EMU_PER_IN:.2f}in")
            if over:
                raise ValueError(
                    f"{idx}번 슬라이드 '{title}' 도형이 화면 밖: {', '.join(over)}")


# ── 렌더 검수 덤프 ─────────────────────────────────────────────

def _first_size_pt(shape) -> str:
    """도형의 첫 run 글자 크기(pt). 없으면 '-'."""
    frames = []
    if shape.has_text_frame:
        frames.append(shape.text_frame)
    if getattr(shape, "has_table", False) and shape.has_table:
        frames.extend(cell.text_frame for row in shape.table.rows
                      for cell in row.cells)
    for tf in frames:
        for p in tf.paragraphs:
            for run in p.runs:
                if run.font.size:
                    return f"{run.font.size.pt:g}pt"
    return "-"


def dump_deck(prs: Presentation) -> None:
    """슬라이드마다 도형 이름·위치·크기(in)·첫 run 글자 크기(pt)를 줄 단위로 찍는다."""
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            l = shape.left / EMU_PER_IN if shape.left is not None else float("nan")
            t = shape.top / EMU_PER_IN if shape.top is not None else float("nan")
            w = shape.width / EMU_PER_IN if shape.width is not None else float("nan")
            h = shape.height / EMU_PER_IN if shape.height is not None else float("nan")
            print(f"slide {i}: {shape.name} left={l:.2f} top={t:.2f} "
                  f"w={w:.2f} h={h:.2f} first={_first_size_pt(shape)}")


# ── 진입점 ─────────────────────────────────────────────────────

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="원고 마크다운과 visual 주석으로 16:9 PPTX 덱을 만든다")
    parser.add_argument("md", help="원고 마크다운 파일")
    parser.add_argument("-o", "--output", required=True, help="출력 PPTX 파일")
    parser.add_argument("--assets", help="자산 폴더(기본: 원고 파일이 있는 폴더)")
    parser.add_argument("--config", help="deck.yaml(png_remap·badge_colors·colors 등)")
    parser.add_argument("--font", default=DEFAULT_FONT, help="기본 서체")
    parser.add_argument("--mono", default=MONO_FONT, help="코드 span 서체(latin)")
    parser.add_argument("--dump", action="store_true",
                        help="저장 후 슬라이드별 도형·글자 크기를 표준 출력에 찍는다")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(Path(args.config)) if args.config else Config()
        md_path = Path(args.md)
        doc = parse_doc(md_path.read_text(encoding="utf-8"), config)
        theme = Theme(font=args.font, mono=args.mono).with_colors(config.colors)
        assets_dir = Path(args.assets) if args.assets else md_path.resolve().parent
        ctx = DeckContext(assets=Assets(Path(assets_dir), config.png_remap),
                          theme=theme,
                          strip=doc.visual.get("strip") or config.spotlight_strip,
                          badge_colors=config.badge_colors)
        prs = build_deck(doc, ctx)
        prs.save(args.output)
    except (ValueError, TypeError, KeyError, FileNotFoundError, OSError,
            yaml.YAMLError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(f"만들었음: {args.output} ({len(prs.slides)} slides)")
    if args.dump:
        dump_deck(prs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
