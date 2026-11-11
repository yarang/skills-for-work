"""공통 틀: 문맥, 머리·바닥글·노트, 글머리 분류·알약 줄·말풍선, 표지·목차·구분 슬라이드.

내용 영역: left 0.6in, top 1.4in, 폭 12.13in, 바닥 6.95in(바닥글 7.08in과 겹치지 않음).
'예:' 로 시작하는 글머리는 일반 글머리에서 빼 말풍선으로 그린다.
chips 면 마지막 글머리를 '라벨: a, b, c'로 나눠 알약으로 그린다.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from _deck_parse import Assets, png_size
from _deck_shapes import (add_bullet_par, add_example_bubble, add_icon_circle,
                          add_pill, add_round_rect, add_runs, add_textbox,
                          set_font, set_shape_text)
from _deck_text import fit_font_size, pill_width_in, text_width_pt, unified_min, \
    visible_text
from _deck_theme import (CARD_GAP_IN, CARD_ICON_D_IN, CONTENT_BOTTOM_IN, CONTENT_R_IN,
                         CONTENT_TOP_IN, CONTENT_W_IN, FOOTER_TOP_IN, MARGIN_L_IN,
                         SLIDE_H_IN, PILL_LABEL_PT, PILL_HEIGHT_PAD_IN,
                         TEXT_INSET_IN, Theme, resolve_color)

# ── 문맥 ───────────────────────────────────────────────────────

@dataclass
class DeckContext:
    """한 덱을 그리는 동안 필요한 것 모음(자산·테마·spotlight 단계·배지색)."""

    assets: Assets
    theme: Theme
    strip: list[str] | None = None       # spotlight 단계 이름(문서 주석이 config보다 우선)
    badge_colors: dict[str, str] = field(default_factory=dict)  # 배지 글 → 색

    def badge_color(self, text: str) -> str:
        """배지 색: 지정이 없으면 보조색, 있으면 테마 색 이름 또는 6자리 16진."""
        spec = self.badge_colors.get(visible_text(text), self.theme.secondary)
        return resolve_color(self.theme, spec)


# ── 슬라이드 틀 ────────────────────────────────────────────────

NUM_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")


def new_slide(prs, blank, bg: str):
    slide = prs.slides.add_slide(blank)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string(bg)
    return slide


def display_title(title: str, visual: dict) -> str:
    """badge가 있으면 제목 끝의 ' (...)'를 떼고 보인다."""
    if visual.get("badge"):
        return re.sub(r"\s*\([^()]*\)\s*$", "", title)
    return title


def add_header(slide, title: str, ctx: DeckContext, icon: str | None = None,
               badge: str | None = None, dark: bool = False):
    """섹션 아이콘 원 + 번호(보조색)/제목(주색) 두 run. 강조 막대 선은 없다."""
    theme = ctx.theme
    left = MARGIN_L_IN
    if icon:
        add_icon_circle(slide, ctx.assets, theme, icon, Inches(MARGIN_L_IN),
                        Inches(0.42), Inches(0.6),
                        theme.primary_deep if dark else theme.primary)
        left = 1.4
    width = CONTENT_R_IN - left - (1.7 if badge else 0.2)
    box, tf = add_textbox(slide, Inches(left), Inches(0.32), Inches(width), Inches(0.8))
    box.name = "title"
    tf.word_wrap = False  # 제목은 한 줄(두 줄로 꺾이지 않게)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    m = NUM_PREFIX.match(title)
    if m:
        num, rest = p.add_run(), p.add_run()
        num.text = m.group(1) + " "
        rest.text = m.group(2)
        set_font(num, theme.font, 28, bold=True, color=theme.secondary)
        set_font(rest, theme.font, 28, bold=True,
                 color=theme.white if dark else theme.primary)
    else:
        run = p.add_run()
        run.text = title
        set_font(run, theme.font, 28, bold=True,
                 color=theme.white if dark else theme.primary)
    if badge:
        add_pill(slide, theme, badge, Inches(CONTENT_R_IN), Inches(0.5),
                 theme.emphasis, theme.badge_text, bold=True)


def add_footer(prs, slide, ctx: DeckContext, dark: bool = False):
    box, tf = add_textbox(slide, Inches(12.13), Inches(FOOTER_TOP_IN), Inches(1.0),
                          Inches(0.3))
    box.name = "footer"
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    run = p.add_run()
    run.text = str(len(prs.slides))
    set_font(run, ctx.theme.font, 10,
             color=ctx.theme.tint_text if dark else ctx.theme.text_faint)


def add_notes(slide, notes: list[str], theme: Theme):
    tf = slide.notes_slide.notes_text_frame
    tf.text = "\n".join(visible_text(n) for n in notes)
    for p in tf.paragraphs:
        for run in p.runs:
            set_font(run, theme.font, 12)


# ── 글머리 분류 공통 규칙 ──────────────────────────────────────

def split_bullets(bullets: list[str]) -> tuple[list[str], list[str]]:
    """일반 글머리와 '예:' 글머리(말풍선 행)를 나눈다."""
    normal = [b for b in bullets if not b.startswith("예:")]
    examples = [b for b in bullets if b.startswith("예:")]
    return normal, examples


def take_chips(visual: dict, bullets: list[str], where: str):
    """chips: true면 마지막 글머리를 (라벨, 알약 목록)으로 분리한다."""
    if not visual.get("chips"):
        return None, bullets
    last = bullets[-1] if bullets else ""
    if ":" not in last:
        raise ValueError(f"[{where}] chips 글머리에 ':'가 없습니다: {last or '(글머리 없음)'}")
    label, _, rest = last.partition(":")
    items = [c.strip() for c in rest.split(",") if c.strip()]
    return (label.strip(), items), bullets[:-1]


def check_icons(where: str, visual: dict, expected: int) -> list[str]:
    icons = visual.get("icons")
    got = len(icons) if isinstance(icons, list) else 0
    if not isinstance(icons, list) or got != expected:
        raise ValueError(f"[{where}] icons 개수({got})가 항목 수({expected})와 다릅니다")
    return icons


def draw_chips(slide, ctx: DeckContext, chips, bottom: float) -> float:
    """내용 영역 맨 아래에 라벨(보조색 굵게)+알약(옅은 색)을 그린다. 넘치면 두 줄."""
    theme = ctx.theme
    label, items = chips
    line_h, gap = 0.54, 0.12
    rows: list[list[tuple[float, float, tuple[str, str]]]] = []
    row: list[tuple[float, float, tuple[str, str]]] = []
    x = MARGIN_L_IN

    def place(w: float, ent: tuple[str, str]):
        nonlocal x, row
        if row and x + w > CONTENT_R_IN:
            rows.append(row)
            row, x = [], MARGIN_L_IN
        row.append((x, w, ent))
        x += w + gap

    place(pill_width_in(label, PILL_LABEL_PT), ("label", label))
    for item in items:
        place(pill_width_in(item, PILL_LABEL_PT), ("pill", item))
    rows.append(row)
    top = bottom - line_h * len(rows)
    for i, entries in enumerate(rows):
        y = top + i * line_h
        for cx, w, (kind, text) in entries:
            if kind == "label":
                box, tf = add_textbox(slide, Inches(cx), Inches(y),
                                      Inches(w), Inches(line_h))
                box.name = "pill"
                tf.word_wrap = False
                tf.margin_left = tf.margin_right = 0
                tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                run = tf.paragraphs[0].add_run()
                run.text = text
                set_font(run, theme.font, PILL_LABEL_PT, bold=True,
                         color=theme.secondary)
            else:
                h = PILL_LABEL_PT / 72.0 + PILL_HEIGHT_PAD_IN
                shape = add_round_rect(slide, Inches(cx), Inches(y + (line_h - h) / 2),
                                       Inches(w), Inches(h), theme.tint)
                shape.adjustments[0] = 0.5
                set_shape_text(shape, text, theme, PILL_LABEL_PT, theme.primary,
                               bold=False)
                shape.name = "pill"
    return line_h * len(rows)


def stack_bubbles(slide, examples: list[str], ctx: DeckContext, left: float,
                  top: float, width: float, height: float):
    """예시 말풍선 여러 개를 영역 안에 세로로 나눠 그린다."""
    if not examples:
        return
    gap = 0.14
    h = (height - gap * (len(examples) - 1)) / len(examples)
    for i, ex in enumerate(examples):
        add_example_bubble(slide, ex, Inches(left), Inches(top + i * (h + gap)),
                           Inches(width), Inches(h), ctx.theme)


def draw_bullets(slide, ctx: DeckContext, bullets: list[str], l: float, t: float,
                 w: float, h: float, max_pt: float, min_pt: float,
                 size: float | None = None) -> float:
    """글머리를 fit하여 그리고 쓴 글자 크기를 돌려준다. size를 주면 그대로 쓴다."""
    if size is None:
        size = fit_font_size(bullets, w - 0.45, h, max_pt, min_pt)
    box, tf = add_textbox(slide, Inches(l), Inches(t), Inches(w), Inches(h))
    box.name = "bullet-body"
    for i, b in enumerate(bullets):
        add_bullet_par(tf, b, ctx.theme, size, first=i == 0, space_after=8,
                       bold_color=ctx.theme.primary)
    return size


def centered_cell(slide, ctx: DeckContext, text: str, cx: float, top: float,
                  col_w: float, h: float, size: float, color: str, bold: bool = True,
                  wrap: bool = True, name: str = "step-text"):
    """가운데 정렬 한 칸(타임라인 제목·설명, equation 라벨·연산자 공용)."""
    box, tf = add_textbox(slide, Inches(cx - col_w / 2 + 0.05), Inches(top),
                          Inches(col_w - 0.1), Inches(h))
    box.name = name
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    add_runs(p, text, ctx.theme, size, color, bold=bold)


# ── 표지·목차·구분 슬라이드 ───────────────────────────────────

SECTION_NUM = re.compile(r"^(\d+)\.\s+(.+)$")


def split_section_title(title: str) -> tuple[str, str]:
    """'1. 제목' → ('01', '제목'). 번호가 없으면 ('', 제목)."""
    m = SECTION_NUM.match(title)
    if m:
        return f"{int(m.group(1)):02d}", m.group(2)
    return "", title


def add_title_slide(prs, blank, doc, ctx: DeckContext):
    theme = ctx.theme
    slide = new_slide(prs, blank, theme.primary)
    hero = doc.visual.get("hero")
    if hero:  # 문서 주석에 hero가 없으면 표지에 그림 없이
        png = ctx.assets.illustration_png(hero)
        px_w, px_h = png_size(png)
        w = Inches(5.4)
        pic = slide.shapes.add_picture(str(png), Inches(7.4), Inches(1.2), w,
                                       int(w * px_h / px_w))
        pic.name = "image"
    main, _, sub = doc.title.partition(" — ")
    if sub:
        right = Inches(0.8) + Inches(pill_width_in(sub, PILL_LABEL_PT)) + Inches(0.08)
        add_pill(slide, theme, sub, right, Inches(2.0), theme.secondary, theme.white)
    box, tf = add_textbox(slide, Inches(0.8), Inches(2.55), Inches(6.4), Inches(1.8))
    box.name = "title"
    run = tf.paragraphs[0].add_run()
    run.text = main
    set_font(run, theme.font, 40, bold=True, color=theme.white)
    sbox, stf = add_textbox(slide, Inches(0.8), Inches(4.55), Inches(6.4), Inches(1.3))
    sbox.name = "subtitle"
    for i, line in enumerate(doc.subtitle):
        p = stf.paragraphs[0] if i == 0 else stf.add_paragraph()
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = line
        set_font(run, theme.font, 16, color=theme.tint_text)


def _agenda_grid(n: int) -> tuple[int, float]:
    """섹션 n개를 위한 (열 수, 카드 높이). 카드가 낮아지면 열 수를 늘린다."""
    cols, min_h = 4, 1.8
    while True:
        rows = math.ceil(n / cols)
        card_h = (CONTENT_BOTTOM_IN - CONTENT_TOP_IN - CARD_GAP_IN * (rows - 1)) / rows
        if card_h >= min_h or cols >= 7:
            return cols, card_h
        cols += 1


def add_agenda_slide(prs, blank, doc, ctx: DeckContext):
    theme = ctx.theme
    slide = new_slide(prs, blank, theme.surface)
    add_header(slide, "목차", ctx)
    secs = doc.sections
    cols, card_h = _agenda_grid(len(secs))
    if card_h < 1.2:
        raise ValueError(f"목차를 그릴 수 없습니다: 섹션이 너무 많습니다({len(secs)}개)")
    rows = math.ceil(len(secs) / cols)
    card_w = (CONTENT_W_IN - CARD_GAP_IN * (cols - 1)) / cols
    # 카드 안 배치는 카드 높이에 비례하게: 아이콘·번호를 줄이고 이름이 남은 높이를 쓴다.
    inset = min(0.28, card_w * 0.12, card_h * 0.12)
    icon_d = min(CARD_ICON_D_IN, card_h * 0.35)
    num_h = min(0.5, card_h * 0.22)
    name_top = inset + icon_d + 0.12 + num_h + 0.06
    name_h = card_h - inset - name_top
    if name_h <= 0.05:
        raise ValueError(
            f"목차 카드가 너무 낮아 섹션 이름을 넣을 수 없습니다: 섹션 {len(secs)}개")
    # 이름은 카드마다 자기 상자로 맞춘 뒤 모든 카드에 같은 최솟값으로 통일한다.
    inner_w = card_w - 2 * inset - 2 * TEXT_INSET_IN
    size = unified_min(fit_font_size([split_section_title(s.title)[1]], inner_w,
                                     name_h, 18, 14) for s in secs)
    for i, sec in enumerate(secs):
        r, c = divmod(i, cols)
        x = MARGIN_L_IN + c * (card_w + CARD_GAP_IN)
        y = CONTENT_TOP_IN + r * (card_h + CARD_GAP_IN)
        add_round_rect(slide, Inches(x), Inches(y), Inches(card_w), Inches(card_h),
                       theme.card, line=theme.card_line)
        num, name = split_section_title(sec.title)
        icon = sec.visual.get("icon")
        if icon:
            add_icon_circle(slide, ctx.assets, theme, icon, Inches(x + inset),
                            Inches(y + inset), Inches(icon_d), theme.secondary)
        nbox, ntf = add_textbox(slide, Inches(x + inset), Inches(y + inset + icon_d + 0.12),
                                Inches(card_w - 2 * inset), Inches(num_h))
        nbox.name = "card-head"
        ntf.word_wrap = False
        run = ntf.paragraphs[0].add_run()
        run.text = num
        set_font(run, theme.font, 24, bold=True, color=theme.emphasis_deep)
        nbox2, ntf2 = add_textbox(slide, Inches(x + inset), Inches(y + name_top),
                                  Inches(card_w - 2 * inset), Inches(name_h))
        nbox2.name = "card-body"
        add_runs(ntf2.paragraphs[0], name, theme, size, theme.primary, bold=True)
    add_footer(prs, slide, ctx)


def add_divider_slide(prs, blank, section, ctx: DeckContext):
    theme = ctx.theme
    slide = new_slide(prs, blank, theme.primary)
    icon = section.visual.get("icon")
    if icon:
        add_icon_circle(slide, ctx.assets, theme, icon, Inches(1.2),
                        Inches((SLIDE_H_IN - 1.8) / 2), Inches(1.8), theme.secondary)
    num, name = split_section_title(section.title)
    if num:
        nbox, ntf = add_textbox(slide, Inches(3.5), Inches(2.05), Inches(8.8), Inches(1.1))
        nbox.name = "title"
        ntf.word_wrap = False
        run = ntf.paragraphs[0].add_run()
        run.text = num
        set_font(run, theme.font, 54, bold=True, color=theme.emphasis)
    tbox, tf2 = add_textbox(slide, Inches(3.5), Inches(3.15), Inches(8.8), Inches(1.7))
    tbox.name = "title"
    tf2.word_wrap = False
    run2 = tf2.paragraphs[0].add_run()
    run2.text = name
    set_font(run2, theme.font, 40, bold=True, color=theme.white)
    add_footer(prs, slide, ctx, dark=True)
