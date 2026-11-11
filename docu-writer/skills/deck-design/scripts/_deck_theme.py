"""덱 테마 상수: 색 팔레트·서체 기본값·레이아웃 상수·역할별 글자 크기 범위.

SKILL.md 「레이아웃 상수」·「글자 크기 맞춤」·「배치 세부」의 모든 수치는 이름 있는
상수로 이 파일에만 둔다. 다른 모듈은 색·서체를 Theme 인스턴스로만 받고 16진 색
리터럴을 두지 않는다(config `colors`로 Theme 색 필드를 덮어쓸 수 있다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace

# ── 색 팔레트(16진, '#' 없음) ─────────────────────────────────
# 주색 하나(면적 60~70%) + 보조 하나 + 강조 하나. 강조는 배지·하이라이트에만.
NAVY = "1F3864"        # 주색
NAVY_2 = "2A4A7F"      # 어두운 슬라이드의 카드
TEAL = "0F8B8D"        # 보조
TEAL_TINT = "E6F4F4"   # 말풍선·하이라이트 카드 채움
AMBER = "F2B53A"       # 강조·배지
AMBER_DARK = "B7860B"  # 밝은 배경에 쓰는 강조 글자색
BG = "F5F7FA"          # 내용 슬라이드 바탕
CARD = "FFFFFF"
CARD_LINE = "D6E0EE"
ICE = "EEF3FA"
ICE_TEXT = "CADCFC"    # 어두운 슬라이드의 흐린 글자
BODY = "222222"
GRAY = "555555"
FOOT_GRAY = "808080"
WHITE = "FFFFFF"
CODE_COLOR = "C7254E"  # 인라인 코드 span 기본색
BADGE_TEXT = "1F1F1F"  # 강조색 위의 글자색
ROW_ALT = ICE          # 표 줄무늬

DEFAULT_FONT = "Malgun Gothic"  # 기본 서체(Office). 없는 환경은 --font로 바꾼다.
MONO_FONT = "Consolas"          # 코드 span의 latin 서체

EMU_PER_IN = 914400
HEX_COLOR = re.compile(r"^[0-9A-Fa-f]{6}$")


@dataclass
class Theme:
    """서체 + 색. 색은 이 인스턴스를 통해서만 쓴다."""

    font: str = DEFAULT_FONT
    mono: str = MONO_FONT
    primary: str = NAVY
    primary_deep: str = NAVY_2
    secondary: str = TEAL
    secondary_tint: str = TEAL_TINT
    emphasis: str = AMBER
    emphasis_deep: str = AMBER_DARK
    surface: str = BG
    card: str = CARD
    card_line: str = CARD_LINE
    tint: str = ICE
    tint_text: str = ICE_TEXT
    text: str = BODY
    text_sub: str = GRAY
    text_faint: str = FOOT_GRAY
    white: str = WHITE
    code: str = CODE_COLOR
    badge_text: str = BADGE_TEXT
    row_alt: str = ROW_ALT

    def with_colors(self, overrides: dict[str, str]) -> "Theme":
        """config `colors` — 색 필드만 덮어쓴다."""
        color_fields = COLOR_FIELDS
        unknown = set(overrides) - set(color_fields)
        if unknown:
            raise ValueError(
                f"알 수 없는 색 이름: {', '.join(sorted(unknown))} "
                f"(쓸 수 있는 이름: {', '.join(color_fields)})")
        for key, value in overrides.items():
            if not isinstance(value, str) or not HEX_COLOR.match(value):
                raise ValueError(f"색 값은 6자리 16진이어야 합니다: colors.{key} = {value!r}")
        return replace(self, **overrides)


COLOR_FIELDS = tuple(f.name for f in fields(Theme) if f.name not in ("font", "mono"))


def resolve_color(theme: Theme, spec: str) -> str:
    """배지 색 지정: 6자리 16진이면 그대로, 아니면 Theme 색 필드 이름."""
    if HEX_COLOR.match(spec):
        return spec
    if spec in COLOR_FIELDS:
        return getattr(theme, spec)
    raise ValueError(
        f"알 수 없는 색 지정: {spec!r} (6자리 16진 또는 색 이름 {', '.join(COLOR_FIELDS)})")


# ── 레이아웃 상수(in) ──────────────────────────────────────────
SLIDE_W_IN = 13.333            # 16:9 슬라이드 폭
SLIDE_H_IN = 7.5               # 슬라이드 높이
MARGIN_L_IN = 0.6              # 왼쪽 여백
CONTENT_W_IN = 12.13           # 내용 폭
CONTENT_R_IN = MARGIN_L_IN + CONTENT_W_IN  # 오른쪽 끝 12.73
CONTENT_TOP_IN = 1.4           # 내용 시작(제목 아래)
CONTENT_BOTTOM_IN = 6.95       # 내용 끝
FOOTER_TOP_IN = 7.08           # 바닥글 시작선(표 아래 글은 이 위에 끝나야 한다)
TEXT_INSET_IN = 0.1            # 글상자 좌우 안쪽 여백(PowerPoint 기본값과 같은 값을 명시)
CARD_GAP_IN = 0.25             # 카드 간격
CARD_PAD_IN = 0.22             # 카드 안쪽 여백
CARD_ICON_D_IN = 0.6           # 카드 아이콘 원 지름
BOUNDS_TOL_IN = 0.01           # 경계 검사 허용 오차

# ── 글자 크기 맞춤 상수 ────────────────────────────────────────
FIT_STEP_PT = 0.5              # 맞춤 단계
LINE_GAP = 1.25                # 줄 간격(줄 높이 계수)
WIDE_EM = 1.0                  # 전각(한글·CJK) 글자 폭
NARROW_EM = 0.55               # 그 밖 글자 폭(본문 서체 평균)
WORD_CHECK_EM = 0.56           # 가장 긴 낱말 검사에서만 쓰는 폭(코드 서체 여유)
WORD_WIDTH_LIMIT = 0.97        # 낱말 폭 한도(상자 폭의 97%)
ONE_LINE_MARGIN = 1.1          # 한 줄 글 추정 폭 여유

# 고정 글자 크기(pt)
PILL_LABEL_PT = 17             # 알약 라벨
COUNT_BADGE_PT = 12            # 개수 배지
STEP_NUM_PT = 24               # 단계 숫자
SPOTLIGHT_MIN_PT = 13          # spotlight 단계 띠 알약 크기 하한

# ── 배치 세부 상수 ─────────────────────────────────────────────
PILL_PAD_IN = 0.15             # 알약 폭 여유(추정 폭 × 1.1 에 더하는 값)
PILL_HEIGHT_PAD_IN = 0.18      # 알약 높이 여유
COUNT_BADGE_D_IN = 0.34        # 개수 배지 지름
STEP_CIRCLE_D_IN = 0.8         # 단계 원 지름
STEP_BUBBLE_GAP_IN = 0.45      # 단계 [원+글] 묶음과 말풍선 사이
IMAGE_WIDE_RATIO = 2.6         # 그림 가로÷세로 경계(이상=위·아래 배치)
IMAGE_SHARE = 0.64             # 두 단 배치에서 그림이 차지하는 폭 비율
IMAGE_TEXT_GAP_IN = 0.35       # 두 단 배치에서 그림-글 간격
CHIPS_TOP_GAP_IN = 0.35        # 알약 줄과 위 요소 사이 간격
TIMELINE_LINE_GAP = 1.3        # 타임라인 카드 줄 간격(1.25보다 넉넉히)
TIMELINE_CARD_PAD_IN = 0.35    # 타임라인 카드 위아래 여백
HEADLESS_CARD_MAX_H_IN = 2.4   # 머리글 없는 카드 묶음 높이 상한
HEADLESS_BODY_W_IN = 2.6       # 머리글 없는 카드 본문 폭 경계(좁으면 아이콘 위)

# 표: 표 아래 글을 바닥글 위에 두기 위한 상한
TABLE_ROW_H_IN = 0.5           # 표 행 높이 기본값
TABLE_ROW_H_MIN_IN = 0.38      # 행 높이까지 줄일 수 있는 하한
TABLE_UNDER_PT = (13, 15)      # 표 아래 글 크기 (하한, 기본)

# ── 역할별 글자 크기 범위(pt, (min, max)) ─────────────────────
CARD_HEAD_PT = (14, 20)        # 카드 머리글(한 줄)
CARD_BODY_PT = (12, 18)        # 카드 본문(머리글 있음)
CARD_BODY_SOLO_PT = (14, 22)   # 카드 본문(머리글 없음)
IMAGE_BULLET_PT = (13, 18)     # 그림 옆 글머리
STEP_TEXT_PT = (15, 24)        # 단계 글
TIMELINE_TITLE_PT = (13, 18)   # 타임라인 제목(한 줄)
TIMELINE_DESC_PT = (12, 16)    # 타임라인 설명
