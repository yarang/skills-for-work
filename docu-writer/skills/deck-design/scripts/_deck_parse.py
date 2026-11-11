"""원고 마크다운 파서와 config·자산 해석.

원고 구조는 SKILL.md 「원고와 visual 주석」 표를 따른다.
- `# 제목` + `> 대상:`·`> 기준:`(subtitle_prefixes) → 표지
- 문서 수준 주석(첫 `##` 전): {"hero": ...}, {"strip": [...]}
- `## 섹션` → 구분 슬라이드 + 목차 한 줄. 제목이나 본문 줄에 skip_marker가
  있으면 섹션 전체를 덱과 목차에서 뺀다.
- `### 슬라이드` → 내용 슬라이드. `##` 바로 아래 본문은 섹션 제목의 암묵 슬라이드에.

visual 주석은 `<!-- visual:` 로 시작하는 줄을 `-->` 가 나올 때까지 이어 붙여
json.loads 한다(여러 줄 JSON도 되고, 문서·섹션·슬라이드 수준 모두 같은 규칙).
JSON 오류이거나 객체가 아니면 제목을 담은 오류로 멈춘다(조용히 넘어가지 않는다).
```/~~~ 코드 펜스 안의 줄은 제목·글머리·주석으로 해석하지 않는다.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

import yaml

H2 = re.compile(r"^## +(.+)$")
H3 = re.compile(r"^### +(.+)$")
IMG_LINE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
VISUAL_START = re.compile(r"<!--\s*visual:")
FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
NOTE_PREFIX = "> 발표 노트:"

RENDER_SCRIPT = "skills/deck-design/scripts/render_svgs.sh"


# ── config ─────────────────────────────────────────────────────

@dataclass
class Config:
    png_remap: dict[str, str] = field(default_factory=dict)
    badge_colors: dict[str, str] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    skip_marker: str = "덱에 넣지 않음"
    subtitle_prefixes: list[str] = field(default_factory=lambda: ["대상:", "기준:"])
    spotlight_strip: list[str] | None = None


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return Config()
    if not isinstance(raw, dict):
        raise ValueError(f"config는 YAML 객체여야 합니다: {path}")
    unknown = set(raw) - set(Config().__dataclass_fields__)
    if unknown:
        raise ValueError(f"알 수 없는 config 키: {', '.join(sorted(unknown))}")
    cfg = Config(**raw)
    for key in ("png_remap", "badge_colors", "colors"):
        value = getattr(cfg, key)
        if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise ValueError(f"config의 {key}는 글자→글자 사전이어야 합니다")
    if not isinstance(cfg.skip_marker, str) or not cfg.skip_marker.strip():
        raise ValueError("config의 skip_marker는 비지 않은 문자열이어야 합니다")
    for key in ("subtitle_prefixes", "spotlight_strip"):
        value = getattr(cfg, key)
        if value is None:
            continue
        if not isinstance(value, list) or not value or not all(
                isinstance(v, str) and v for v in value):
            raise ValueError(f"config의 {key}는 비지 않은 문자열 목록이어야 합니다")
    return cfg


# ── 자산(아이콘·일러스트·다이어그램 PNG) ───────────────────────

@dataclass
class Assets:
    """자산 폴더. 아이콘·일러스트는 <root>/<종류>/<이름>.png, 다이어그램은
    원고의 `![..](diagrams/x.svg)` 경로와 같은 폴더의 같은 이름 .png(png_remap 적용)."""

    root: Path
    remap: dict[str, str] = field(default_factory=dict)

    def _hint(self) -> str:
        return f"먼저 'bash {RENDER_SCRIPT} {self.root}'를 실행해 주세요."

    def _find(self, path: Path, what: str) -> Path:
        if not path.is_file():
            raise FileNotFoundError(f"{what} 없음: {path}\n{self._hint()}")
        return path

    def icon_png(self, name: str) -> Path:
        return self._find(self.root / "icons" / f"{name}.png", "아이콘 PNG")

    def illustration_png(self, name: str) -> Path:
        return self._find(self.root / "illustrations" / f"{name}.png", "일러스트 PNG")

    def diagram_png(self, svg_rel: str) -> Path:
        rel = Path(svg_rel)
        png_name = self.remap.get(rel.name, rel.stem + ".png")
        return self._find(self.root / rel.parent / png_name, "다이어그램 PNG")


def png_size(path: Path) -> tuple[int, int]:
    """PNG IHDR 청크에서 (폭, 높이) 픽셀 수를 읽는다."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"PNG 헤더를 읽을 수 없습니다: {path}")
    return struct.unpack(">II", head[16:24])


# ── 마크다운 모델 ──────────────────────────────────────────────

@dataclass
class MdTable:
    header: list[str]
    rows: list[list[str]]


@dataclass
class MdSlide:
    title: str
    bullets: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    table_lines: list[str] = field(default_factory=list)
    table: MdTable | None = None
    image: str | None = None
    visual: dict = field(default_factory=dict)


@dataclass
class MdSection:
    title: str
    skip: bool = False
    slides: list[MdSlide] = field(default_factory=list)
    visual: dict = field(default_factory=dict)


@dataclass
class Doc:
    title: str
    subtitle: list[str]
    visual: dict = field(default_factory=dict)
    sections: list[MdSection] = field(default_factory=list)


# ── 파서 ───────────────────────────────────────────────────────

class FenceTracker:
    """```/~~~ 코드 펜스 상태. 펜스 줄과 펜스 안 줄은 구조 해석에서 뺀다."""

    def __init__(self):
        self.marker = ""   # 여는 마커 문자("`" 또는 "~")
        self.length = 0    # 여는 마커 길이

    def is_open(self) -> bool:
        return self.length > 0

    def feed(self, line: str) -> bool:
        """줄 하나를 먹여, 펜스 몸통(건너뛸 줄)이면 True를 돌려준다."""
        m = FENCE.match(line.strip())
        if self.is_open():
            if (m and m.group(1)[0] == self.marker and len(m.group(1)) >= self.length
                    and not m.group(2).strip()):
                self.marker, self.length = "", 0  # 닫는 펜스
            return True
        if m:  # 여는 펜스(뒤에 정보 문자열이 붙어도 연다)
            self.marker, self.length = m.group(1)[0], len(m.group(1))
            return True
        return False


def take_visual(lines: list[str], i: int, where: str) -> tuple[dict, int]:
    """lines[i]의 visual 주석을 `-->`가 나올 때까지 모아 (주석 객체, 다음 줄 인덱스).

    원고 끝까지 닫는 표시가 없으면 제목을 담은 ValueError로 멈춘다.
    """
    buf = [lines[i]]
    j = i
    while "-->" not in buf[-1]:
        j += 1
        if j >= len(lines):
            raise ValueError(f"[{where}] visual 주석이 닫히지 않았습니다('-->'가 없습니다)")
        buf.append(lines[j])
    body = "\n".join(buf)
    m = VISUAL_START.search(body)
    return parse_visual(body[m.end():body.index("-->", m.end())].strip(), where), j + 1


def parse_visual(payload: str, where: str) -> dict:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"[{where}] visual 주석 JSON 오류: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"[{where}] visual 주석 JSON 오류: JSON 객체여야 합니다")
    return value


def parse_doc(text: str, config: Config | None = None) -> Doc:
    config = config or Config()
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("마크다운이 '# 제목' 줄로 시작해야 합니다.")
    title = lines[0][2:].strip()
    header: list[str] = []
    doc_visual: dict = {}
    fence = FenceTracker()
    i = 1
    # 첫 '##' 전까지: 인용 줄은 부제 후보, visual 주석은 문서 수준(hero·strip).
    while i < len(lines) and not lines[i].startswith("## "):
        if fence.feed(lines[i]):
            i += 1
            continue
        stripped = lines[i].strip()
        if VISUAL_START.match(stripped):
            payload, i = take_visual(lines, i, title)
            doc_visual.update(payload)
        elif stripped.startswith(">"):
            header.append(stripped[1:].strip())
        i += 1  # '---' 구분선 등은 무시
    subtitle = [h for h in header if h.startswith(tuple(config.subtitle_prefixes))]
    sections = [s for s in parse_sections(lines[i:], config) if not s.skip]
    return Doc(title=title, subtitle=subtitle, visual=doc_visual, sections=sections)


def parse_sections(lines: list[str], config: Config) -> list[MdSection]:
    sections: list[MdSection] = []
    current: MdSection | None = None
    fence = FenceTracker()
    i = 0
    while i < len(lines):
        line = lines[i]
        if fence.feed(line):  # 펜스 안의 '##'·글머리·주석은 구조로 읽지 않는다
            i += 1
            continue
        stripped = line.strip()
        if not stripped or stripped == "---":
            i += 1
            continue  # 암묵 슬라이드가 빈 줄로 생기지 않게 먼저 걸러낸다
        m = H2.match(line)
        if m:
            name = m.group(1).strip()
            current = None if config.skip_marker in name else MdSection(name)
            if current is not None:
                sections.append(current)
            i += 1
            continue
        if current is None:
            i += 1
            continue
        if config.skip_marker in stripped:
            current.skip = True  # 본문 어느 줄에 표시가 있으면 섹션 전체 제외
            i += 1
            continue
        if VISUAL_START.match(stripped):
            where = current.slides[-1].title if current.slides else current.title
            payload, i = take_visual(lines, i, where)
            if current.slides:
                current.slides[-1].visual.update(payload)
            else:
                current.visual.update(payload)
            continue
        m = H3.match(line)
        if m:
            current.slides.append(MdSlide(title=m.group(1).strip()))
            i += 1
            continue
        feed_line(current.slides[-1] if current.slides else implicit_slide(current),
                  line)
        i += 1
    for section in sections:
        for slide in section.slides:
            finalize_table(slide)
    return sections


def implicit_slide(section: MdSection) -> MdSlide:
    """'##' 바로 아래 본문을 담을, 섹션 제목 이름의 슬라이드."""
    if not section.slides:
        section.slides.append(MdSlide(title=section.title))
    return section.slides[-1]


def feed_line(slide: MdSlide, line: str) -> None:
    stripped = line.strip()
    if not stripped or stripped == "---":
        return
    if stripped.startswith(NOTE_PREFIX):
        slide.notes.append(stripped[len(NOTE_PREFIX):].strip())
    elif stripped.startswith((">", "<!--")):
        return  # 그 외 인용 줄·HTML 주석은 본문에서 무시
    elif stripped.startswith("- "):
        slide.bullets.append(stripped[2:].strip())
    elif IMG_LINE.match(stripped):
        slide.image = IMG_LINE.match(stripped).group(1)
    elif stripped.startswith("|"):
        slide.table_lines.append(stripped)
    else:
        slide.paragraphs.append(stripped)


def finalize_table(slide: MdSlide) -> None:
    if slide.table_lines:
        slide.table = parse_table(slide.table_lines)
        slide.table_lines = []


def parse_table(raw: list[str]) -> MdTable:
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in raw]
    header = rows[0]
    body = []
    for row in rows[1:]:
        if row and all(set(c) <= set("-: ") for c in row if c):
            continue  # |---| 구분 행
        body.append((row + [""] * len(header))[: len(header)])
    return MdTable(header=header, rows=body)
