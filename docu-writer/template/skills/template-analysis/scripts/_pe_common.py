"""profile_extract.py 공용 도구: 오류, 형식 판별, 글 정리, YAML 출력."""
import hashlib
import importlib
import re
from pathlib import Path

import yaml

FORMATS = {".hwpx": "hwpx", ".docx": "docx", ".pptx": "pptx", ".md": "md", ".markdown": "md"}
CELL_LIMIT = 40
CANDIDATE_LIMIT = 40
MIN_SAMPLE_LEN = 6
PLACEHOLDER_CHARS = set("○◯〇")

# 줄 머리 부호: 기호 한 글자 또는 번호 모양 (doc-verify R6와 같은 모양)
MARKER_RE = re.compile(
    r"^(?:[□■◇◆○ㅇᄋ◦●\-–•·※▶☞]|\d+(?:\.\d+)*[.)]|\(\d+\)|[①-⑳]"
    r"|[가-하][.)]|\([가-하]\)|[A-Za-z][.)]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\.?)$"
)


class UsageError(Exception):
    """종료 코드 2로 끝나는 오류 (사용법·형식·파일)."""


def detect_format(path: Path) -> str:
    if not path.is_file():
        raise UsageError(f"파일 없음: {path}")
    fmt = FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise UsageError(f"지원하지 않는 형식: {path.suffix or path.name}")
    return fmt


def format_module(fmt: str):
    """형식별 모듈 (_pe_docx·_pe_pptx·_pe_hwpx·_pe_md): tables·heading_texts·profile_parts."""
    return importlib.import_module(f"_pe_{fmt}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def cell_text(paragraph_texts) -> str:
    """칸 글: 칸 자신의 문단을 공백으로 잇고 공백을 줄여 40자까지."""
    return collapse(" ".join(paragraph_texts))[:CELL_LIMIT]


def no_space(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def placeholder_only(text: str) -> bool:
    """`○○`만으로 된 토큰인가 (공백·문장부호는 무시)."""
    core = re.sub(r"[\s\W_]+", "", text or "")
    stripped = no_space(text)
    if not stripped:
        return False
    return all(ch in PLACEHOLDER_CHARS for ch in core or stripped)


def table_entry(index, rows, cols, first, last_row, nested, warnings, slide=None):
    """표 목록 한 줄. last_row는 마지막 행 칸 글 목록."""
    entry = {"at": f"t:{index}"}
    if slide is not None:
        entry["slide"] = int(slide)
    entry.update(rows=int(rows), cols=int(cols), first=first)
    entry["last"] = last_cell(last_row, f"t:{index}", warnings)
    entry["nested"] = int(nested)
    return entry


def last_cell(texts, at, warnings) -> str:
    for text in reversed(list(texts)):
        if text:
            return text
    warnings.append(f"{at}: 마지막 행의 칸이 모두 비어 last를 비움")
    return ""


def line_marker(text: str) -> str:
    """문단 글의 첫 공백 앞 토큰이 부호 모양이면 그 토큰 (doc-verify R6 규칙)."""
    parts = (text or "").split()
    if parts and MARKER_RE.match(parts[0]):
        return parts[0]
    return ""


class Candidates:
    """sample_text_candidates 모음: 짧은 글·○○ 토큰을 빼고 순서대로 중복 제거."""

    def __init__(self):
        self.items = []
        self._seen = set()

    def add(self, text: str) -> None:
        text = collapse(text)
        if len(text) < MIN_SAMPLE_LEN or placeholder_only(text):
            return
        text = text[:CANDIDATE_LIMIT].rstrip()
        if text not in self._seen:
            self._seen.add(text)
            self.items.append(text)


def unique(seq):
    out = []
    for item in seq:
        if item and item not in out:
            out.append(item)
    return out


def plain(value):
    """yaml.safe_dump가 받는 기본형으로 바꿈 (Length·RGBColor·lxml 문자열 등)."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if type(value) in (list, tuple):
        return [plain(v) for v in value]
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return str(value)


def dump_yaml(data) -> str:
    return yaml.safe_dump(plain(data), allow_unicode=True, sort_keys=False)


def emu_to_mm(emu) -> float:
    return round(int(emu) / 36000, 1)


def paper_size(width_mm: float, height_mm: float) -> str:
    short, long_ = sorted((width_mm, height_mm))
    for name, (w, h) in {"A4": (210, 297), "A3": (297, 420), "B5": (182, 257),
                         "Letter": (215.9, 279.4)}.items():
        if abs(short - w) < 2 and abs(long_ - h) < 2:
            return name
    return f"{width_mm:g}x{height_mm:g}mm"
