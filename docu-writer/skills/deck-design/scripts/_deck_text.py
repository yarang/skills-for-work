"""글자 계산: 인라인 마크업 분해, 글자 폭 추정, 글자 크기 맞춤(fit), 알약 폭.

fit 규칙은 SKILL.md 「글자 크기 맞춤」 그대로.
- 조건 1(줄 수): Σ(문단별 ⌈글 폭 ÷ (상자 폭×72)⌉) × 크기 × 1.25 / 72 ≤ 상자 높이.
  문단 간격은 더하지 않는다.
- 조건 2(가장 긴 낱말): 가장 넓은 낱말 ≤ 상자 폭×72×0.97(이 검사에서만 0.56em).
- 조건 3(통일): 호출 쪽에서 역할별 최솟값으로 맞춘다(unified_min 헬퍼).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from _deck_theme import (FIT_STEP_PT, LINE_GAP, NARROW_EM, ONE_LINE_MARGIN,
                         PILL_PAD_IN, PILL_HEIGHT_PAD_IN, WIDE_EM,
                         WORD_CHECK_EM, WORD_WIDTH_LIMIT)

# ── 인라인 마크업: **굵게**, `코드`, [링크](url) ────────────────

BOLD_SPAN = re.compile(r"(\*\*.+?\*\*)")
CODE_OR_LINK = re.compile(r"(`[^`]+`|\[[^\]]+\]\([^)]+\))")


@dataclass
class Token:
    text: str
    bold: bool = False
    code: bool = False


def parse_inline(text: str) -> list[Token]:
    """굵게 → (내부) 코드·링크 순으로 2단계 분해. **`code`** 중첩도 처리한다."""
    tokens: list[Token] = []
    for part in BOLD_SPAN.split(text):
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        inner = part[2:-2] if bold else part
        for token in _code_link_tokens(inner):
            token.bold = token.bold or bold
            tokens.append(token)
    return tokens


def _code_link_tokens(text: str) -> list[Token]:
    tokens: list[Token] = []
    for part in CODE_OR_LINK.split(text):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            tokens.append(Token(part[1:-1], code=True))
        elif part.startswith("[") and "](" in part:
            tokens.append(Token(part[1:part.index("]")]))
        else:
            tokens.append(Token(part))
    return tokens


def visible_text(text: str) -> str:
    """마크업을 벗겨낸 보이는 텍스트."""
    return "".join(t.text for t in parse_inline(text))


# ── 글자 폭 추정 ────────────────────────────────────────────────

def char_width_pt(ch: str, pt: float, narrow: float = NARROW_EM) -> float:
    """글자 하나의 폭 추정: 전각(한글·CJK) 1.0em, 그 밖 narrow em."""
    return pt if unicodedata.east_asian_width(ch) in ("W", "F") else pt * narrow


def text_width_pt(text: str, pt: float) -> float:
    return sum(char_width_pt(c, pt) for c in text)


def wrap_lines(text: str, pt: float, box_w_in: float) -> int:
    """글자 폭 추정으로 상자 폭에 필요한 줄 수(문단 하나)."""
    width = text_width_pt(visible_text(text), pt)
    return max(1, math.ceil(width / (box_w_in * 72)))


def widest_word_pt(text: str, pt: float) -> float:
    """공백으로 나눈 낱말 가운데 가장 넓은 것의 폭 추정.

    이 검사에서만 전각이 아닌 글자를 0.56em으로 잡는다. 끊을 곳이 없는
    코드 이름은 PowerPoint가 낱말 중간에서 꺾는다.
    """
    words = visible_text(text).split()
    if not words:
        return 0.0
    return max(sum(char_width_pt(c, pt, narrow=WORD_CHECK_EM) for c in w)
               for w in words)


# ── 글자 크기 맞춤 ──────────────────────────────────────────────

def fit_font_size(texts: list[str], box_w_in: float, box_h_in: float,
                  max_pt: float, min_pt: float) -> float:
    """문단들이 상자 안에 드는 가장 큰 글자 크기(0.5pt 단위)를 고른다.

    조건 1(줄 수, 문단 간격 없음)과 조건 2(가장 긴 낱말 ≤ 상자 폭 97%)를
    모두 만족하는 첫 크기. 없으면 하한(min_pt).
    """
    if not texts:
        return max_pt
    box_w_pt = max(box_w_in * 72.0, 1.0)
    box_h_pt = max(box_h_in * 72.0, 1.0)
    size = max_pt
    while size >= min_pt:
        lines = sum(wrap_lines(t, size, box_w_in) for t in texts)
        widest = max(widest_word_pt(t, size) for t in texts)
        if lines * size * LINE_GAP <= box_h_pt and widest <= box_w_pt * WORD_WIDTH_LIMIT:
            return size
        size -= FIT_STEP_PT
    return min_pt


def fit_one_line_pt(text: str, box_w_in: float, max_pt: float, min_pt: float) -> float:
    """한 줄로만 놓을 글자 크기: 추정 폭 × 1.1 ≤ 상자 폭인 가장 큰 값."""
    width_pt = box_w_in * 72
    size = max_pt
    while size >= min_pt:
        if text_width_pt(visible_text(text), size) * ONE_LINE_MARGIN <= width_pt:
            return size
        size -= FIT_STEP_PT
    return min_pt


def unified_min(sizes: list[float | None]) -> float | None:
    """같은 역할 통일: 각자 맞춘 값의 최솟값(None 은 빼고, 전부 None 이면 None)."""
    values = [s for s in sizes if s is not None]
    return min(values) if values else None


# ── 알약 치수 ───────────────────────────────────────────────────

def pill_width_in(text: str, size: float) -> float:
    """알약 폭: 추정 폭 × 1.1(렌더 여유) + 0.15in."""
    return text_width_pt(visible_text(text), size) * ONE_LINE_MARGIN / 72.0 + PILL_PAD_IN


def pill_height_in(size: float) -> float:
    return size / 72.0 + PILL_HEIGHT_PAD_IN
