"""내용 슬라이드 레이아웃 9종과 선택기.

레이아웃: icon-rows, spotlight, cards, steps, image, table, timeline, equation, bullets.
layout을 적지 않으면 그림 → 표 → 글머리 순서로 고른다.
spotlight 단계 이름(strip)은 문서 주석 또는 config에서 온다(둘 다 없으면 오류).
"""

from __future__ import annotations

import math
import re

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from _deck_layouts import (DeckContext, centered_cell, check_icons, draw_bullets,
                           draw_chips, split_bullets, stack_bubbles, take_chips)
from _deck_parse import png_size
from _deck_shapes import (add_bullet_par, add_circle, add_icon_circle, add_rect,
                          add_round_rect, add_runs, add_textbox, fit_size,
                          set_font, set_shape_text)
from _deck_text import (fit_font_size, fit_one_line_pt, parse_inline, pill_width_in,
                        unified_min, visible_text, wrap_lines)
from _deck_theme import (CARD_BODY_PT, CARD_BODY_SOLO_PT, CARD_GAP_IN, CARD_HEAD_PT,
                         CARD_ICON_D_IN, CARD_PAD_IN, CHIPS_TOP_GAP_IN,
                         CONTENT_BOTTOM_IN, CONTENT_R_IN, CONTENT_TOP_IN,
                         CONTENT_W_IN, COUNT_BADGE_D_IN, COUNT_BADGE_PT,
                         FIT_STEP_PT, FOOTER_TOP_IN, HEADLESS_BODY_W_IN,
                         HEADLESS_CARD_MAX_H_IN, IMAGE_BULLET_PT, IMAGE_SHARE,
                         IMAGE_TEXT_GAP_IN, IMAGE_WIDE_RATIO, LINE_GAP, MARGIN_L_IN,
                         PILL_LABEL_PT, SPOTLIGHT_MIN_PT, STEP_BUBBLE_GAP_IN,
                         STEP_CIRCLE_D_IN, STEP_NUM_PT, STEP_TEXT_PT,
                         TABLE_ROW_H_IN, TABLE_ROW_H_MIN_IN, TABLE_UNDER_PT,
                         TEXT_INSET_IN, TIMELINE_CARD_PAD_IN, TIMELINE_DESC_PT,
                         TIMELINE_LINE_GAP, TIMELINE_TITLE_PT)

CARD_HEAD = re.compile(r"^\*\*(.+?)\*\*:\s*(.*)$")


# ── 레이아웃: icon-rows ────────────────────────────────────────

def layout_icon_rows(slide, data, ctx: DeckContext):
    visual = data.visual
    where = data.title
    theme = ctx.theme
    items, examples = split_bullets(data.bullets)
    chips, items = take_chips(visual, items, where)
    icons = check_icons(where, visual, len(items))
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if examples:
        ex_h = min(2.0, 1.15 * len(examples))
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN, bottom - ex_h, CONTENT_W_IN,
                      ex_h)
        bottom -= ex_h + 0.15
    stat = visual.get("stat")
    n = len(items)
    if not n:
        raise ValueError(f"[{where}] icon-rows 레이아웃에는 글머리 항목이 필요합니다")
    # 예 블록·알약 줄을 뺀 나머지 높이를 행마다 나눠 각 행의 상자로 삼는다.
    row_h = (bottom - CONTENT_TOP_IN) / n
    circle_d = 0.62
    text_l = MARGIN_L_IN + circle_d + 0.25
    text_r = 7.9 if stat else CONTENT_R_IN
    # 행마다 자기 상자(행 높이×안쪽 글 폭)로 맞춘 뒤 최솟값으로 통일(SKILL 조건 1·3).
    size = unified_min(fit_font_size([t], text_r - text_l - 2 * TEXT_INSET_IN, row_h,
                                     22, 15) for t in items)
    for i, (text, icon) in enumerate(zip(items, icons)):
        y = CONTENT_TOP_IN + i * row_h
        add_icon_circle(slide, ctx.assets, theme, icon, Inches(MARGIN_L_IN),
                        Inches(y + (row_h - circle_d) / 2), Inches(circle_d),
                        theme.secondary)
        box, tf = add_textbox(slide, Inches(text_l), Inches(y),
                              Inches(text_r - text_l), Inches(row_h))
        box.name = "bullet-body"
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        add_runs(tf.paragraphs[0], text, theme, size, theme.text,
                 bold_color=theme.primary)
    if stat:
        add_stat_card(slide, ctx, stat, bottom)


def add_stat_card(slide, ctx: DeckContext, stat: dict, bottom: float):
    theme = ctx.theme
    l, w = 8.9, 3.83
    t, h = CONTENT_TOP_IN, bottom - CONTENT_TOP_IN
    add_round_rect(slide, Inches(l), Inches(t), Inches(w), Inches(h), theme.card,
                   line=theme.card_line)
    box, tf = add_textbox(slide, Inches(l + 0.25), Inches(t + 0.5), Inches(w - 0.5),
                          Inches(h - 1.0))
    box.name = "stat"
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    rows = [(stat.get("value", ""), 54, theme.primary, True),
            (stat.get("label", ""), 18, theme.text_sub, False),
            (stat.get("note", ""), 12, theme.text_faint, False)]
    for i, (text, size, color, bold) in enumerate(rows):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(0 if i == 0 else 8)
        run = p.add_run()
        run.text = visible_text(text)
        set_font(run, theme.font, size, bold=bold, color=color)


# ── 레이아웃: spotlight ────────────────────────────────────────

def draw_strip(slide, ctx: DeckContext, active, where: str) -> float:
    """단계 띠: active 번째는 주색+흰 굵게, 나머지는 옅은 색+회색, 사이 '›'.

    알약은 등분 폭이 아니라 라벨에 맞는 폭(pill_width_in)으로 그리고
    줄 전체를 내용 폭 가운데에 둔다. 폭이 넘으면 13pt까지 0.5pt씩 줄인다.
    """
    theme = ctx.theme
    names = ctx.strip or []
    n = len(names)
    h, sep_w = 0.42, 0.3
    size = PILL_LABEL_PT
    while True:
        widths = [pill_width_in(name, size) for name in names]
        total = sum(widths) + sep_w * (n - 1)
        if total <= CONTENT_W_IN:
            break
        size -= FIT_STEP_PT
        if size < SPOTLIGHT_MIN_PT:
            raise ValueError(
                f"[{where}] spotlight 단계 띠가 내용 폭({CONTENT_W_IN}in)을 넘습니다 "
                f"— 크기를 {SPOTLIGHT_MIN_PT}pt까지 줄여도 모자랍니다(단계 {n}개)")
    x = MARGIN_L_IN + (CONTENT_W_IN - total) / 2
    for i, (name, w) in enumerate(zip(names, widths)):
        on = i == active
        shape = add_round_rect(slide, Inches(x), Inches(CONTENT_TOP_IN), Inches(w),
                               Inches(h), theme.primary if on else theme.tint)
        shape.adjustments[0] = 0.5
        set_shape_text(shape, name, theme, size, theme.white if on else theme.text_sub,
                       bold=on)
        shape.name = "pill"
        x += w
        if i < n - 1:
            box, tf = add_textbox(slide, Inches(x), Inches(CONTENT_TOP_IN),
                                  Inches(sep_w), Inches(h))
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = "›"
            set_font(run, theme.font, 16, color=theme.text_sub)
            x += sep_w
    return CONTENT_TOP_IN + h


def layout_spotlight(slide, data, ctx: DeckContext):
    visual = data.visual
    theme = ctx.theme
    if not ctx.strip:
        raise ValueError(
            f"[{data.title}] spotlight 레이아웃에는 단계 이름(strip)이 필요합니다"
            " — 문서 주석 {\"strip\": [...]} 또는 config spotlight_strip")
    strip_bottom = draw_strip(slide, ctx, visual.get("active"), data.title)
    icon = visual.get("icon")
    circle_top = 2.4
    if icon:
        add_icon_circle(slide, ctx.assets, theme, icon, Inches(0.9), Inches(circle_top),
                        Inches(2.4), theme.primary)
    items, examples = split_bullets(data.bullets)
    chips, items = take_chips(visual, items, data.title)
    left, top, width = 4.0, max(circle_top, strip_bottom + 0.4), 8.7
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if examples:
        ex_h = min(2.0, 1.15 * len(examples))
        stack_bubbles(slide, examples, ctx, left, bottom - ex_h, width, ex_h)
        bottom -= ex_h + 0.15
    draw_bullets(slide, ctx, items, left, top, width, bottom - top, 22, 15)


# ── 레이아웃: cards ────────────────────────────────────────────

def layout_cards(slide, data, ctx: DeckContext):
    visual = data.visual
    where = data.title
    items, examples = split_bullets(data.bullets)
    chips, items = take_chips(visual, items, where)
    icons = check_icons(where, visual, len(items))
    cols = int(visual.get("cols", 2))
    rows = math.ceil(len(items) / cols)
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if examples:
        ex_h = min(1.8, 1.1 * len(examples))
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN, bottom - ex_h, CONTENT_W_IN,
                      ex_h)
        bottom -= ex_h + 0.15
    card_w = (CONTENT_W_IN - CARD_GAP_IN * (cols - 1)) / cols
    full_h = (bottom - CONTENT_TOP_IN - CARD_GAP_IN * (rows - 1)) / rows
    # 머리 없는 카드 묶음은 카드가 길쭉해지지 않게 높이를 제한하고 세로 가운데에 둔다.
    card_h = full_h if any(CARD_HEAD.match(i) for i in items) else min(
        full_h, HEADLESS_CARD_MAX_H_IN)
    grid_h = rows * card_h + CARD_GAP_IN * (rows - 1)
    grid_top = CONTENT_TOP_IN + (bottom - CONTENT_TOP_IN - grid_h) / 2
    highlight = set(visual.get("highlight") or [])
    # 같은 슬라이드의 같은 역할은 최솟값 하나로 통일해 함께 쓴다(SKILL 조건 3).
    fits = [card_fit_sizes(item, card_w, card_h) for item in items]
    head_pt = unified_min([f[0] for f in fits])
    body_pt = unified_min([f[1] for f in fits])
    for i, (item, icon) in enumerate(zip(items, icons)):
        r, c = divmod(i, cols)
        x = MARGIN_L_IN + c * (card_w + CARD_GAP_IN)
        y = grid_top + r * (card_h + CARD_GAP_IN)
        draw_card(slide, ctx, item, icon, x, y, card_w, card_h,
                  highlighted=i in highlight, dark=bool(visual.get("dark")),
                  count_badge=bool(visual.get("count_badge")),
                  head_pt=head_pt, body_pt=body_pt)


def card_fit_sizes(item: str, w: float, h: float) -> tuple[float | None, float | None]:
    """카드 하나의 (머리글, 본문) 글자 크기를 fit해서 돌려준다(없는 쪽은 None).

    fit 폭은 글상자 폭에서 좌우 안쪽 여백(2×TEXT_INSET_IN)을 뺀 안쪽 폭이다.
    """
    pad, d = CARD_PAD_IN, CARD_ICON_D_IN
    inset_w = 2 * TEXT_INSET_IN
    m = CARD_HEAD.match(item)
    head, body = (m.group(1), m.group(2)) if m else (None, item)
    if head:
        head_w = w - pad * 2 - d - 0.2  # 아이콘 오른쪽 0.2in부터 카드 안쪽 오른쪽 끝까지
        head_pt = fit_one_line_pt(head, head_w - inset_w, CARD_HEAD_PT[1],
                                  CARD_HEAD_PT[0])
        if not visible_text(body):
            return head_pt, None
        body_h = h - pad * 2 - d - 0.1
        return head_pt, fit_font_size([body], w - pad * 2 - inset_w, body_h - 0.05,
                                      CARD_BODY_PT[1], CARD_BODY_PT[0])
    if not visible_text(body):
        return None, None
    body_w = w - pad * 2 - d - 0.2
    if body_w >= HEADLESS_BODY_W_IN:  # 머리 없는 카드: 본문을 아이콘과 나란히
        return None, fit_font_size([body], body_w - inset_w, h - pad * 2 - 0.05,
                                   CARD_BODY_SOLO_PT[1], CARD_BODY_SOLO_PT[0])
    # 폭이 좁으면 본문을 아이콘 아래에 둔다.
    return None, fit_font_size([body], w - pad * 2 - inset_w, h - pad * 2 - d - 0.2,
                               CARD_BODY_SOLO_PT[1], CARD_BODY_SOLO_PT[0])


def draw_card_icon(slide, ctx: DeckContext, icon: str, body: str, l: float, t: float,
                   d: float, count_badge: bool):
    """카드 아이콘 원. count_badge면 본문 코드 span 개수를 원의 오른쪽 위에 알림 배지로 단다."""
    add_icon_circle(slide, ctx.assets, ctx.theme, icon, Inches(l), Inches(t),
                    Inches(d), ctx.theme.secondary)
    if not count_badge:
        return
    codes = [tok for tok in parse_inline(body) if tok.code]
    if not codes:
        return
    bd = COUNT_BADGE_D_IN
    cx, cy = l + d - 0.06, t + 0.06  # 원의 오른쪽 위 모서리
    badge = add_circle(slide, Inches(cx - bd / 2), Inches(cy - bd / 2), Inches(bd),
                       ctx.theme.emphasis)
    set_shape_text(badge, str(len(codes)), ctx.theme, COUNT_BADGE_PT,
                   ctx.theme.badge_text, bold=True)
    badge.name = "count-badge"


def draw_card(slide, ctx: DeckContext, item: str, icon: str, x: float, y: float,
              w: float, h: float, highlighted: bool, dark: bool, count_badge: bool,
              head_pt: float | None = None, body_pt: float | None = None):
    theme = ctx.theme
    if dark:
        fill, line, head_c, body_c, bold_c = theme.primary_deep, None, theme.white, \
            theme.white, theme.white
    elif highlighted:
        fill, line, head_c, body_c, bold_c = theme.secondary_tint, theme.secondary, \
            theme.primary, theme.text, theme.primary
    else:
        fill, line, head_c, body_c, bold_c = theme.card, theme.card_line, \
            theme.primary, theme.text, theme.primary
    add_round_rect(slide, Inches(x), Inches(y), Inches(w), Inches(h), fill,
                   line=line, line_w=2.25 if highlighted else 1)
    pad, d = CARD_PAD_IN, CARD_ICON_D_IN
    m = CARD_HEAD.match(item)
    head, body = (m.group(1), m.group(2)) if m else (None, item)
    if head_pt is None or body_pt is None:  # 크기를 못 받았으면 이 카드만 fit
        fit_head, fit_body = card_fit_sizes(item, w, h)
        head_pt = fit_head if head_pt is None else head_pt
        body_pt = fit_body if body_pt is None else body_pt
    if head:
        # 머리 있는 카드: 위 아이콘+머리(한 줄), 아래 본문.
        draw_card_icon(slide, ctx, icon, body, x + pad, y + pad, d, count_badge)
        head_w = w - pad * 2 - d - 0.2
        box, tf = add_textbox(slide, Inches(x + pad + d + 0.2), Inches(y + pad),
                              Inches(head_w), Inches(d))
        box.name = "card-head"
        tf.word_wrap = False  # 머리글은 한 줄 강제
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        add_runs(tf.paragraphs[0], head, theme, head_pt, head_c)
        body_top = y + pad + d + 0.1
        body_h = y + h - pad - body_top
        if visible_text(body):
            bbox, btf = add_textbox(slide, Inches(x + pad), Inches(body_top),
                                    Inches(w - pad * 2), Inches(body_h))
            bbox.name = "card-body"
            btf.vertical_anchor = MSO_ANCHOR.MIDDLE
            add_runs(btf.paragraphs[0], body, theme, body_pt, body_c,
                     bold_color=bold_c)
        return
    if not visible_text(body):  # 본문 없는 카드: 아이콘만 세로 가운데
        draw_card_icon(slide, ctx, icon, body, x + pad, y + (h - d) / 2, d,
                       count_badge)
        return
    # 머리 없는 카드: 본문을 아이콘과 나란히(또는 폭이 좁으면 아래에) 둔다.
    body_w = w - pad * 2 - d - 0.2
    if body_w >= HEADLESS_BODY_W_IN:
        draw_card_icon(slide, ctx, icon, body, x + pad, y + (h - d) / 2, d,
                       count_badge)
        bbox, btf = add_textbox(slide, Inches(x + pad + d + 0.2), Inches(y + pad),
                                Inches(body_w), Inches(h - pad * 2))
        bbox.name = "card-body"
        btf.vertical_anchor = MSO_ANCHOR.MIDDLE
        add_runs(btf.paragraphs[0], body, theme, body_pt, body_c, bold_color=bold_c)
    else:
        draw_card_icon(slide, ctx, icon, body, x + (w - d) / 2, y + pad, d,
                       count_badge)
        top = y + pad + d + 0.15
        bbox, btf = add_textbox(slide, Inches(x + pad), Inches(top),
                                Inches(w - pad * 2), Inches(y + h - pad - top))
        bbox.name = "card-body"
        btf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = btf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        add_runs(p, body, theme, body_pt, body_c, bold_color=bold_c)


# ── 레이아웃: steps ────────────────────────────────────────────

def layout_steps(slide, data, ctx: DeckContext):
    visual = data.visual
    where = data.title
    theme = ctx.theme
    steps, examples = split_bullets(data.bullets)
    chips, steps = take_chips(visual, steps, where)
    n = len(steps)
    if not 2 <= n <= 5:
        raise ValueError(f"[{where}] steps 레이아웃은 단계 2~5개가 필요한데 {n}개입니다")
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    ex_h = min(1.7, 1.05 * len(examples)) if examples else 0.0
    d = STEP_CIRCLE_D_IN
    col_w = CONTENT_W_IN / n
    # 단계마다 자기 열의 글상자(폭 col_w-0.35, 높이 2.6)로 맞춘 뒤 최솟값으로 통일한다.
    # (모든 단계의 줄을 한 상자에 합쳐 맞추면 단계 수가 많을 때만 작아지는 버그가 있다.)
    size = unified_min(fit_font_size([s], col_w - 0.35, 2.6, STEP_TEXT_PT[1],
                                     STEP_TEXT_PT[0]) for s in steps)
    text_h = max(wrap_lines(s, size, col_w - 0.35) for s in steps) * size * \
        LINE_GAP / 72
    # [원+0.2+글] 묶음과 0.45in 띄운 말풍선을 남은 세로 공간 가운데에 둔다.
    group_h = d + 0.2 + text_h + ((STEP_BUBBLE_GAP_IN + ex_h) if examples else 0.0)
    top = CONTENT_TOP_IN + (bottom - CONTENT_TOP_IN - group_h) / 2
    cy = top + d / 2
    for i, step in enumerate(steps):
        cx = MARGIN_L_IN + col_w * (i + 0.5)
        circle = add_circle(slide, Inches(cx - d / 2), Inches(cy - d / 2), Inches(d),
                            theme.primary)
        set_shape_text(circle, str(i + 1), theme, STEP_NUM_PT, theme.white, bold=True)
        circle.name = "step-num"
        if i < n - 1:
            x0 = cx + d / 2 + 0.05
            x1 = MARGIN_L_IN + col_w * (i + 1.5) - d / 2 - 0.05
            add_rect(slide, Inches(x0), Inches(cy - 0.014), Inches(x1 - x0),
                     Inches(0.028), theme.secondary)
        centered_cell(slide, ctx, step, cx, cy + d / 2 + 0.2, col_w, text_h, size,
                      theme.text, bold=False, name="step-text")
    if examples:
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN,
                      cy + d / 2 + 0.2 + text_h + STEP_BUBBLE_GAP_IN, CONTENT_W_IN,
                      ex_h)


# ── 레이아웃: image ────────────────────────────────────────────

def estimate_text_h(normal: list[str], examples: list[str]) -> float:
    """그림 아래에 남겨 둘 글 영역 높이 추정(in)."""
    if not normal and not examples:
        return 0.0
    w = CONTENT_W_IN * (0.58 if examples else 1.0)
    size = fit_font_size(normal, w - 0.45, 4.5, IMAGE_BULLET_PT[1], IMAGE_BULLET_PT[0])
    lines = sum(wrap_lines(b, size, w - 0.45) for b in normal)
    h = lines * size * 1.3 / 72 + 0.2
    if examples:
        h = max(h, min(1.9, 1.05 * len(examples)))
    return min(max(h, 1.0), 2.4)


def _image_card(slide, ctx: DeckContext, png, l: float, t: float, w: float, h: float):
    """그림을 0.12in 감싼 흰 카드와 함께 (l,t,w,h는 인치) 가운데 놓는다."""
    theme = ctx.theme
    add_round_rect(slide, int(Inches(l - 0.12)), int(Inches(t - 0.12)),
                   int(Inches(w + 0.24)), int(Inches(h + 0.24)), theme.card,
                   line=theme.card_line)
    pic = slide.shapes.add_picture(str(png), int(Inches(l)), int(Inches(t)),
                                   int(Inches(w)), int(Inches(h)))
    pic.name = "image"


def _image_wide(slide, ctx: DeckContext, png, px_w: int, px_h: int, normal, examples,
                bottom: float):
    """넓은 그림(가로÷세로 ≥ 2.6): 위에 그림, 아래에 글·말풍선."""
    img_h = max(CONTENT_BOTTOM_IN - 0.5 - estimate_text_h(normal, examples)
                - CONTENT_TOP_IN, 3.2)
    w, h = fit_size(px_w, px_h, int(Inches(CONTENT_W_IN - 0.3)), int(Inches(img_h)))
    img_l = int(Inches(MARGIN_L_IN) + (Inches(CONTENT_W_IN) - w) / 2)
    add_round_rect(slide, img_l - Inches(0.12), int(Inches(CONTENT_TOP_IN)) - Inches(0.12),
                   w + Inches(0.24), h + Inches(0.24), ctx.theme.card,
                   line=ctx.theme.card_line)
    pic = slide.shapes.add_picture(str(png), img_l, int(Inches(CONTENT_TOP_IN)), w, h)
    pic.name = "image"
    if not normal and not examples:
        return
    top = CONTENT_TOP_IN + h / 914400 + 0.38
    if examples:
        left_w = CONTENT_W_IN * 0.58
        bh = max(min(bottom - top, 2.3), 0.8)
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN + left_w + 0.25, top,
                      CONTENT_W_IN - left_w - 0.25, bh)
        text_w = left_w
    else:
        text_w = CONTENT_W_IN
    if normal:
        draw_bullets(slide, ctx, normal, MARGIN_L_IN, top, text_w, bottom - top,
                     IMAGE_BULLET_PT[1], IMAGE_BULLET_PT[0])


def _image_two_col(slide, ctx: DeckContext, png, px_w: int, px_h: int, normal,
                   examples, bottom: float):
    """보통 그림(비율 < 2.6): 왼쪽 64%에 그림, 0.35in 띄우고 오른쪽에 글·말풍선."""
    area_h = bottom - CONTENT_TOP_IN
    if not normal and not examples:
        # 글이 없으면 그림을 전체 폭으로 가운데에 크게 둔다.
        w, h = fit_size(px_w, px_h, int(Inches(CONTENT_W_IN)), int(Inches(area_h)))
        _image_card(slide, ctx, png, MARGIN_L_IN + (CONTENT_W_IN - w / 914400) / 2,
                    CONTENT_TOP_IN + (area_h - h / 914400) / 2, w / 914400,
                    h / 914400)
        return
    img_area_w = CONTENT_W_IN * IMAGE_SHARE
    w, h = fit_size(px_w, px_h, int(Inches(img_area_w - 0.24)),
                    int(Inches(area_h - 0.24)))
    w_in, h_in = w / 914400, h / 914400
    _image_card(slide, ctx, png, MARGIN_L_IN + (img_area_w - w_in) / 2,
                CONTENT_TOP_IN + (area_h - h_in) / 2, w_in, h_in)
    text_l = MARGIN_L_IN + img_area_w + IMAGE_TEXT_GAP_IN
    text_w = CONTENT_R_IN - text_l
    ex_h = min(1.2 * len(examples), 2.6) if examples else 0.0
    gap = 0.25 if (normal and examples) else 0.0
    if normal:
        size = fit_font_size(normal, text_w - 0.45, max(area_h - ex_h - gap - 0.15, 0.5),
                             IMAGE_BULLET_PT[1], IMAGE_BULLET_PT[0])
        lines = sum(wrap_lines(b, size, text_w - 0.45) for b in normal)
        text_h = lines * size * LINE_GAP / 72 + 0.05
    else:
        size, text_h = 0.0, 0.0
    block_h = text_h + gap + ex_h
    block_top = CONTENT_TOP_IN + (area_h - block_h) / 2
    if normal:
        draw_bullets(slide, ctx, normal, text_l, block_top, text_w, text_h + 0.1,
                     IMAGE_BULLET_PT[1], IMAGE_BULLET_PT[0], size=size)
    if examples:
        stack_bubbles(slide, examples, ctx, text_l, block_top + text_h + gap,
                      text_w, ex_h)


def layout_image(slide, data, ctx: DeckContext):
    if data.image is None:
        raise ValueError(f"[{data.title}] image 레이아웃에는 그림이 필요합니다")
    png = ctx.assets.diagram_png(data.image)
    px_w, px_h = png_size(png)
    normal, examples = split_bullets(data.bullets)
    chips, normal = take_chips(data.visual, normal, data.title)
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if px_w / px_h >= IMAGE_WIDE_RATIO:
        _image_wide(slide, ctx, png, px_w, px_h, normal, examples, bottom)
    else:
        _image_two_col(slide, ctx, png, px_w, px_h, normal, examples, bottom)


# ── 레이아웃: table ────────────────────────────────────────────

def column_widths(table, total: float = CONTENT_W_IN, min_w: float = 1.5) -> list[float]:
    cols = len(table.header)
    lens = []
    for c in range(cols):
        cells = [table.header[c]] + [row[c] for row in table.rows]
        lens.append(max(len(visible_text(cell)) for cell in cells) or 1)
    scale = sum(lens)
    widths = [max(min_w, total * n / scale) for n in lens]
    excess = sum(widths) - total
    if excess > 1e-6:  # 최소 폭 보장으로 넘친 만큼 여유 있는 열에서 감산
        flex = [i for i, w in enumerate(widths) if w > min_w]
        room = sum(widths[i] - min_w for i in flex)
        for i in flex:
            widths[i] -= excess * (widths[i] - min_w) / room
    return widths


def fill_cell(cell, md_text: str, theme, size: float, bold: bool, fg: str, bg: str,
              center: bool = False):
    cell.fill.solid()
    cell.fill.fore_color.rgb = RGBColor.from_string(bg)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = Inches(0.08)
    cell.margin_right = Inches(0.08)
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    if center:
        p.alignment = PP_ALIGN.CENTER
    add_runs(p, md_text, theme, size, fg, bold=bold)


def _under_text_height(data, pt: float) -> float:
    """표 아래 글머리·문단이 필요로 하는 높이 추정(in)."""
    texts = list(data.bullets) + list(data.paragraphs)
    if not texts:
        return 0.0
    w = CONTENT_W_IN - 0.5  # 글상자 안쪽 폭에서 글머리 내어쓰기까지 넉넉히 뺀 폭
    lines = sum(wrap_lines(t, pt, w) for t in texts)
    return lines * pt * LINE_GAP / 72 + 0.1


def _under_room(row_h_in: float, n_rows: int) -> float:
    """표 아래에서 바닥글 시작선 직전까지 남는 높이(in)."""
    return FOOTER_TOP_IN - 0.08 - (CONTENT_TOP_IN + row_h_in * n_rows + 0.12)


def layout_table(slide, data, ctx: DeckContext):
    theme = ctx.theme
    if data.table is None:
        raise ValueError(f"[{data.title}] table 레이아웃에는 표가 필요합니다")
    table = data.table
    badge_col = data.visual.get("badge_col")
    n_rows = len(table.rows) + 1
    size = 18 if len(table.rows) <= 6 else 16
    row_h_in, text_pt = TABLE_ROW_H_IN, TABLE_UNDER_PT[1]
    if data.bullets or data.paragraphs:
        # 표 아래 글이 바닥글 시작선 위에 들어가게 글 크기·행 높이부터 줄인다.
        while _under_text_height(data, text_pt) > _under_room(row_h_in, n_rows):
            if text_pt > TABLE_UNDER_PT[0]:
                text_pt -= 1
            elif row_h_in > TABLE_ROW_H_MIN_IN:
                row_h_in = round(row_h_in - 0.05, 2)
            else:
                raise ValueError(
                    f"[{data.title}] 표 {n_rows}행 아래 글을 바닥글 위에 둘 공간이 "
                    "없습니다 — 표를 줄이거나 글을 다른 슬라이드로 나눠 주세요")
    row_h = Inches(row_h_in)
    frame = slide.shapes.add_table(n_rows, len(table.header), Inches(MARGIN_L_IN),
                                   Inches(CONTENT_TOP_IN), Inches(CONTENT_W_IN),
                                   row_h * n_rows)
    frame.name = "table"
    t = frame.table
    t.first_row = False
    t.horz_banding = False
    for i, w in enumerate(column_widths(table)):
        t.columns[i].width = Inches(w)
    for r in range(n_rows):
        t.rows[r].height = row_h
    for c, cell_text in enumerate(table.header):
        fill_cell(t.cell(0, c), cell_text, theme, size, bold=True, fg=theme.white,
                  bg=theme.primary)
    for r, row in enumerate(table.rows, start=1):
        bg = theme.white if r % 2 == 1 else theme.row_alt
        for c, cell_text in enumerate(row):
            if c == badge_col:
                color = ctx.badge_color(cell_text)
                fill_cell(t.cell(r, c), cell_text, theme, size, bold=True,
                          fg=(theme.badge_text if color == theme.emphasis
                              else theme.white),
                          bg=color, center=True)
            else:
                fill_cell(t.cell(r, c), cell_text, theme, size, bold=False,
                          fg=theme.text, bg=bg)
    add_under_table(slide, ctx, data, CONTENT_TOP_IN + row_h_in * n_rows, text_pt)


def add_under_table(slide, ctx: DeckContext, data, top: float, pt: float):
    if not (data.bullets or data.paragraphs):
        return
    theme = ctx.theme
    height = max(FOOTER_TOP_IN - 0.08 - (top + 0.12), 0.0)
    box, tf = add_textbox(slide, Inches(MARGIN_L_IN), Inches(top + 0.12),
                          Inches(CONTENT_W_IN), Inches(height))
    box.name = "bullet-body"
    for i, bullet in enumerate(data.bullets):
        add_bullet_par(tf, bullet, theme, pt, first=i == 0, space_after=6)
    for para in data.paragraphs:
        p = tf.add_paragraph()
        p.space_after = Pt(6)
        add_runs(p, para, theme, pt, theme.text)


# ── 레이아웃: timeline ─────────────────────────────────────────

def layout_timeline(slide, data, ctx: DeckContext):
    theme = ctx.theme
    where = data.title
    if data.table is None:
        raise ValueError(f"[{where}] timeline 레이아웃에는 표가 필요합니다")
    rows = data.table.rows
    icons = check_icons(where, data.visual, len(rows))
    n = len(rows)
    col_w = CONTENT_W_IN / n
    d = 0.9
    num_h = 0.36  # 번호 칸: 원 위 0.36in 지점부터
    col1 = [r[0] for r in rows]
    col2 = [r[1] for r in rows]
    # 제목은 모든 제목이 한 줄에 들어가는(추정 폭×1.1) 가장 큰 크기 한 개로 통일한다.
    s1 = min(fit_one_line_pt(t, col_w - 0.3, TIMELINE_TITLE_PT[1], TIMELINE_TITLE_PT[0])
             for t in col1)
    h1 = s1 * LINE_GAP / 72
    card_w = col_w - 0.16
    card_text_w = card_w - 0.2
    # 번호+원+제목은 고정 높이, 남는 공간이 설명 카드의 글자 상한이다.
    fixed = num_h + d + 0.14 + h1 + 0.18
    cap2 = max(CONTENT_BOTTOM_IN - CONTENT_TOP_IN - fixed - 0.16, 0.5)
    # 설명은 열마다 별도 상자에 들어가므로 각자 자기 상자로 맞춘 뒤 최솟값으로 통일한다
    # (가장 긴 낱말 검사도 모든 항목에 적용된다).
    s2 = unified_min(fit_font_size([t], card_text_w - 2 * TEXT_INSET_IN, cap2,
                                   TIMELINE_DESC_PT[1], TIMELINE_DESC_PT[0])
                     for t in col2)
    card_h = max(wrap_lines(t, s2, card_text_w) for t in col2) * s2 * \
        TIMELINE_LINE_GAP / 72 + TIMELINE_CARD_PAD_IN
    # [번호+원+제목+카드] 묶음 전체를 세로 가운데에 둔다.
    total = fixed + card_h
    line_y = CONTENT_TOP_IN + (CONTENT_BOTTOM_IN - CONTENT_TOP_IN - total) / 2 + \
        num_h + d / 2
    add_rect(slide, Inches(MARGIN_L_IN), Inches(line_y - 0.02), Inches(CONTENT_W_IN),
             Inches(0.04), theme.secondary)
    card_top = line_y + d / 2 + 0.14 + h1 + 0.18
    for i, row in enumerate(rows):
        cx = MARGIN_L_IN + col_w * (i + 0.5)
        circle_top = line_y - d / 2
        add_icon_circle(slide, ctx.assets, theme, icons[i], Inches(cx - d / 2),
                        Inches(circle_top), Inches(d), theme.primary)
        nbox, ntf = add_textbox(slide, Inches(cx - 0.5), Inches(circle_top - num_h),
                                Inches(1.0), Inches(0.32))
        nbox.name = "step-num"
        run = ntf.paragraphs[0].add_run()
        run.text = str(i + 1)
        set_font(run, theme.font, 14, bold=True, color=theme.emphasis)
        ntf.paragraphs[0].alignment = PP_ALIGN.CENTER
        centered_cell(slide, ctx, row[0], cx, line_y + d / 2 + 0.14, col_w, h1, s1,
                      theme.primary, wrap=False, name="timeline-title")
        add_round_rect(slide, Inches(cx - card_w / 2), Inches(card_top),
                       Inches(card_w), Inches(card_h), theme.card,
                       line=theme.card_line)
        dbox, dtf = add_textbox(slide, Inches(cx - card_text_w / 2),
                                Inches(card_top + 0.08), Inches(card_text_w),
                                Inches(card_h - 0.16))
        dbox.name = "timeline-desc"
        dtf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = dtf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        add_runs(p, row[1], theme, s2, theme.text)


# ── 레이아웃: equation ─────────────────────────────────────────

def layout_equation(slide, data, ctx: DeckContext):
    visual = data.visual
    where = data.title
    theme = ctx.theme
    terms = visual.get("terms") or []
    result = visual.get("result") or {}
    if not terms or not result.get("icon"):
        raise ValueError(f"[{where}] equation 레이아웃에는 terms와 result.icon이 필요합니다")
    term_w, op_w, res_w, d, rd = 1.9, 0.5, 2.5, 1.25, 1.55
    cy = 2.35
    labels = [t.get("label", "") for t in terms]
    # 라벨 상자(폭 term_w-0.1)마다 자기 안쪽 폭·높이로 맞춘 뒤 최솟값으로 통일한다.
    label_size = unified_min(fit_font_size([lb], term_w - 0.1 - 2 * TEXT_INSET_IN, 0.75,
                                           16, 12) for lb in labels)
    x = MARGIN_L_IN
    for i, term in enumerate(terms):
        cx = x + term_w / 2
        add_icon_circle(slide, ctx.assets, theme, term["icon"], Inches(cx - d / 2),
                        Inches(cy - d / 2), Inches(d), theme.secondary)
        centered_cell(slide, ctx, labels[i], cx, cy + d / 2 + 0.08, term_w, 0.75,
                      label_size, theme.primary)
        op = "=" if i == len(terms) - 1 else "+"
        centered_cell(slide, ctx, op, x + term_w + op_w / 2, cy - 0.45, op_w, 0.9, 40,
                      theme.emphasis, wrap=False, name="equation-op")
        x += term_w + op_w
    add_circle(slide, Inches(x + (res_w - rd) / 2), Inches(cy - rd / 2), Inches(rd),
               theme.primary, line=theme.emphasis, line_w=4)
    add_icon_circle(slide, ctx.assets, theme, result["icon"],
                    Inches(x + (res_w - d) / 2), Inches(cy - d / 2), Inches(d),
                    theme.primary)
    centered_cell(slide, ctx, result.get("label", ""), x + res_w / 2,
                  cy + rd / 2 + 0.08, res_w, 0.75, 18, theme.primary)
    items, examples = split_bullets(data.bullets)
    chips, items = take_chips(visual, items, where)
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if examples:
        ex_h = min(1.6, 1.1 * len(examples))
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN, bottom - ex_h, CONTENT_W_IN,
                      ex_h)
        bottom -= ex_h + 0.15
    draw_bullets(slide, ctx, items, MARGIN_L_IN, 4.35, CONTENT_W_IN, bottom - 4.35,
                 20, 14)


# ── 레이아웃: bullets(기본) ────────────────────────────────────

def layout_bullets(slide, data, ctx: DeckContext):
    theme = ctx.theme
    items, examples = split_bullets(data.bullets)
    chips, items = take_chips(data.visual, items, data.title)
    icon = data.visual.get("icon")
    bottom = CONTENT_BOTTOM_IN
    if chips:
        bottom -= draw_chips(slide, ctx, chips, bottom) + CHIPS_TOP_GAP_IN
    if examples:
        ex_h = min(2.0, 1.15 * len(examples))
        stack_bubbles(slide, examples, ctx, MARGIN_L_IN, bottom - ex_h, CONTENT_W_IN,
                      ex_h)
        bottom -= ex_h + 0.15
    card_l, card_w = MARGIN_L_IN, CONTENT_W_IN
    if icon:
        # 글머리만 있는 슬라이드도 시각 요소 하나: 색 원 아이콘을 글 영역 왼쪽에 둔다.
        d = 1.2
        add_icon_circle(slide, ctx.assets, theme, icon, Inches(MARGIN_L_IN),
                        Inches(CONTENT_TOP_IN + (bottom - CONTENT_TOP_IN - d) / 2),
                        Inches(d), theme.secondary)
        card_l = MARGIN_L_IN + d + 0.35
        card_w = CONTENT_R_IN - card_l
    add_round_rect(slide, Inches(card_l), Inches(CONTENT_TOP_IN),
                   Inches(card_w), Inches(bottom - CONTENT_TOP_IN), theme.card,
                   line=theme.card_line)
    pad = 0.35
    size = fit_font_size(items + data.paragraphs, card_w - pad * 2 - 0.3,
                         bottom - CONTENT_TOP_IN - 0.3, 22, 15)
    box, tf = add_textbox(slide, Inches(card_l + pad), Inches(CONTENT_TOP_IN + pad / 2),
                          Inches(card_w - pad * 2),
                          Inches(bottom - CONTENT_TOP_IN - pad))
    box.name = "bullet-body"
    for i, b in enumerate(items):
        add_bullet_par(tf, b, theme, size, first=i == 0, space_after=10,
                       bold_color=theme.primary)
    for para in data.paragraphs:
        p = tf.add_paragraph()
        p.space_after = Pt(8)
        add_runs(p, para, theme, size - 2, theme.text)


LAYOUTS = {
    "icon-rows": layout_icon_rows,
    "spotlight": layout_spotlight,
    "cards": layout_cards,
    "steps": layout_steps,
    "image": layout_image,
    "table": layout_table,
    "timeline": layout_timeline,
    "equation": layout_equation,
    "bullets": layout_bullets,
}


def layout_content(slide, data, ctx: DeckContext):
    visual = data.visual
    name = visual.get("layout")
    if name is None:  # visual 없는 슬라이드: 그림 → 표 → 글머리 순
        name = "image" if data.image is not None else (
            "table" if data.table is not None else "bullets")
    fn = LAYOUTS.get(name)
    if fn is None:
        raise ValueError(f"[{data.title}] 알 수 없는 layout: {name}")
    fn(slide, data, ctx)
