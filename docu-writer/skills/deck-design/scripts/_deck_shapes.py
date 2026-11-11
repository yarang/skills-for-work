"""도형·글자 헬퍼: 서체 지정, run 채우기, 원·아이콘 원·둥근 사각형·알약·말풍선.

모든 run에 latin/ea/cs 서체를 지정한다(한글 렌더링에 a:ea가 필수).
도형은 그림자 없이, 선이 필요 없으면 아예 긋지 않는다.
글이나 그림을 가진 도형에는 호출 쪽에서 role()로 역할 이름을 붙인다.
"""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from _deck_text import (fit_font_size, parse_inline, pill_height_in, pill_width_in,
                        visible_text)
from _deck_theme import EMU_PER_IN, PILL_LABEL_PT, TEXT_INSET_IN, Theme

# 글머리 기호를 새로 달기 전에 지울 기존 기호 요소들(색·크기·서체·모양)
BULLET_TAGS = (
    "a:buClrTx", "a:buClr", "a:buSzTx", "a:buSzPct", "a:buSzPts",
    "a:buFontTx", "a:buFont", "a:buNone", "a:buAutoNum", "a:buChar", "a:buBlip",
)
A_NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def role(shape, name: str):
    """도형에 역할 이름을 붙인다(테스트·렌더 검수가 shape.name으로 찾는다)."""
    shape.name = name
    return shape


# ── 글자 헬퍼 ──────────────────────────────────────────────────

def set_font(run, name: str, size: float, bold: bool = False, color: str | None = None,
             ea: str | None = None):
    """run에 latin/ea/cs 서체를 모두 지정한다.

    ea를 주면 한글(a:ea)·복합문자(a:cs)는 그 서체, 라틴(a:latin)은 name을 쓴다.
    코드 서체에 한글 글리프가 없어 대체 글꼴로 찍히는 것을 막으려고 쓴다.
    """
    font = run.font
    font.name = name  # a:latin
    font.size = Pt(size)
    font.bold = bold
    if color is not None:
        font.color.rgb = RGBColor.from_string(color)
    ea_name = ea or name
    rPr = run._r.get_or_add_rPr()
    anchor = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = parse_xml(f"<{tag} {A_NS}/>")
            if anchor is None:
                rPr.append(el)
            else:
                anchor.addnext(el)  # 스키마 순서: latin -> ea -> cs
        el.set("typeface", ea_name)
        anchor = el


def add_runs(paragraph, md_text: str, theme: Theme, size: float, color: str,
             bold: bool = False, code_color: str | None = None,
             bold_color: str | None = None):
    """마크다운 인라인(굵게·코드·링크)을 run들로 풀어 넣는다.

    코드 span은 latin=코드 서체·한글=기본 서체, 색은 theme.code.
    """
    for token in parse_inline(md_text):
        run = paragraph.add_run()
        run.text = token.text
        if token.code:
            set_font(run, theme.mono, size, bold=bold or token.bold,
                     color=code_color or theme.code, ea=theme.font)
        else:
            set_font(run, theme.font, size, bold=bold or token.bold,
                     color=(bold_color if token.bold and bold_color else color))


def set_bullet(p, size: float, font: str, color: str) -> None:
    """진짜 글머리 기호 + 내어쓰기: 넘친 줄이 기호 뒤 본문 위치에 맞춰진다."""
    p_pr = p._p.get_or_add_pPr()
    hang = int(Pt(size) * 1.1)
    p_pr.set("marL", str(hang))
    p_pr.set("indent", str(-hang))
    for tag in BULLET_TAGS:
        for old in p_pr.findall(qn(tag)):
            p_pr.remove(old)
    bu_clr = OxmlElement("a:buClr")  # 없으면 첫 run 색(코드 span 색)을 따라간다
    srgb = OxmlElement("a:srgbClr")
    srgb.set("val", color)
    bu_clr.append(srgb)
    bu_font = OxmlElement("a:buFont")
    bu_font.set("typeface", font)
    bu_char = OxmlElement("a:buChar")
    bu_char.set("char", "•")
    # 스키마 순서: 간격(lnSpc·spcBef·spcAft) 뒤, tabLst·defRPr·extLst 앞
    for el in (bu_clr, bu_font, bu_char):
        p_pr.insert_element_before(el, "a:tabLst", "a:defRPr", "a:extLst")


def add_bullet_par(tf, md_text: str, theme: Theme, size: float, first: bool,
                   space_after: float = 10, color: str | None = None,
                   bold_color: str | None = None, code_color: str | None = None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(space_after)
    set_bullet(p, size, theme.font, theme.text)
    add_runs(p, md_text, theme, size, color or theme.text,
             bold_color=bold_color, code_color=code_color)


# ── 그림 크기 헬퍼 ─────────────────────────────────────────────

def fit_size(px_w: int, px_h: int, box_w: int, box_h: int) -> tuple[int, int]:
    """박스 안에 들어가는 최대 크기(종횡비 유지, EMU)."""
    if box_w * px_h >= box_h * px_w:  # 박스가 더 넓으면 높이가 기준
        height = box_h
        width = int(box_h * px_w / px_h)
    else:
        width = box_w
        height = int(box_w * px_h / px_w)
    return width, height


# ── 도형 헬퍼 ──────────────────────────────────────────────────

def add_textbox(slide, l, t, w, h):
    """word_wrap True 글상자를 만들어 (상자, text_frame)을 돌려준다.

    좌우 안쪽 여백을 TEXT_INSET_IN(PowerPoint 기본값)으로 명시해 둔다.
    fit 계산은 상자 폭에서 이 여백을 뺀 안쪽 폭으로 해야 실제 렌더와 같아진다.
    알약 라벨처럼 여백 0이 필요한 쪽은 만든 뒤에 0으로 덮어쓴다.
    """
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(TEXT_INSET_IN)
    return box, tf


def add_rect(slide, left, top, width, height, color: str):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def add_circle(slide, left, top, diameter, fill: str, line: str | None = None,
               line_w: float = 1):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, diameter, diameter)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = RGBColor.from_string(line)
        shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    return shape


def add_icon_circle(slide, assets, theme: Theme, name: str, left, top, diameter,
                    fill: str) -> None:
    """반복 모티프: 색 원 + 그 지름의 60% 크기인 가운데 흰 아이콘(역할 card-icon)."""
    add_circle(slide, left, top, diameter, fill).name = "card-icon"
    png = assets.icon_png(name)
    icon = int(diameter * 0.6)
    offset = int((diameter - icon) / 2)
    pic = slide.shapes.add_picture(str(png), left + offset, top + offset, icon, icon)
    pic.name = "card-icon"


def add_round_rect(slide, l, t, w, h, fill: str, line: str | None = None,
                   line_w: float = 1):
    """모서리가 살짝 둥근(반경 0.08) 사각형."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    shape.adjustments[0] = 0.08
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = RGBColor.from_string(line)
        shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    return shape


def set_shape_text(shape, text: str, theme: Theme, size: float, color: str,
                   bold: bool = False):
    """도형 안의 한 줄 글자: 가운데 정렬·세로 가운데·여백 없음(word_wrap 끔)."""
    tf = shape.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = visible_text(text)
    set_font(run, theme.font, size, bold=bold, color=color)


def add_pill(slide, theme: Theme, text: str, right, top, fill: str, fg: str,
             bold: bool = True, border: str | None = None):
    """둥근 알약. right는 오른쪽 끝(EMU). 라벨 17pt 고정, 여백 0, 폭 = 추정×1.1+0.15in."""
    w = Inches(pill_width_in(text, PILL_LABEL_PT))
    h = Inches(pill_height_in(PILL_LABEL_PT))
    shape = add_round_rect(slide, int(right - w), top, int(w), int(h), fill, border)
    shape.adjustments[0] = 0.5  # 알약 모양
    set_shape_text(shape, text, theme, PILL_LABEL_PT, fg, bold=bold)
    shape.name = "pill"
    return shape


def add_example_bubble(slide, text: str, l, t, w, h, theme: Theme):
    """말풍선 예시 카드: 첫 줄 '예시', 다음 줄에 본문(코드 span은 주색)."""
    body = text.split(":", 1)[1].strip() if text.startswith("예:") else text
    w_in, h_in = w / EMU_PER_IN, h / EMU_PER_IN
    # '예시' 라벨+여백 약 0.4in만 빼고 본문에 넉넉히 쓰게 한다.
    size = fit_font_size([body], w_in - 0.55, h_in - 0.5, 17, 13)
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGULAR_CALLOUT, l, t, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(theme.secondary_tint)
    shape.line.color.rgb = RGBColor.from_string(theme.secondary)
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    shape.name = "bubble"
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.16)
    tf.margin_top = Inches(0.08)
    tf.margin_bottom = Inches(0.06)
    head = tf.paragraphs[0]
    head.space_after = Pt(3)
    run = head.add_run()
    run.text = "예시"
    set_font(run, theme.font, 12, bold=True, color=theme.secondary)
    add_runs(tf.add_paragraph(), body, theme, size, theme.text,
             code_color=theme.primary)
    return shape
