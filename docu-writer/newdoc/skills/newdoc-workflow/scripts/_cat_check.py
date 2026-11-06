"""catalog.py 도우미: 카탈로그 한 개의 항목 규칙 점검.

계약: docs/briefs/brief_newdoc.md N2 `check`. 문제마다 사람이 읽을 이유 한 줄을 돌려줍니다.
`files=False`이면 구조만 보고, 참조 파일이 있는지는 보지 않습니다(match는 고른 항목만 따로 봄).
"""
from pathlib import Path

from _cat_load import FORMATS, Catalog, normalize, resolve

HWPX_KINDS = ("preset_map", "template_path", "pack_path")


def _text(value) -> bool:
    return isinstance(value, str) and normalize(value) != ""


def _missing(catalog: Catalog, label: str, entry: dict, keys) -> list[str]:
    out = []
    for key in keys:
        value = entry.get(key)
        if _text(value) and not Path(resolve(catalog, value)).exists():
            out.append(f"{label}: {key} 파일이 없습니다: {resolve(catalog, value)}")
    return out


def _paths_are_text(label: str, entry: dict, keys) -> list[str]:
    return [f"{label}: {key}는 비어 있지 않은 문자열이어야 합니다"
            for key in keys if key in entry and not _text(entry[key])]


def _preset_map(label: str, value) -> list[str]:
    if not isinstance(value, dict) or not value:
        return [f"{label}: preset_map은 비어 있지 않은 매핑이어야 합니다"]
    if not all(_text(k) and _text(v) for k, v in value.items()):
        return [f"{label}: preset_map의 키·값은 비어 있지 않은 문자열이어야 합니다"]
    return []


def _hwpx_theme(label: str, entry: dict) -> list[str]:
    kinds = [k for k in HWPX_KINDS if k in entry]
    if len(kinds) != 1:
        return [f"{label}: preset_map·template_path·pack_path 중 정확히 하나가 있어야 합니다({len(kinds)}개)"]
    if kinds[0] == "preset_map":
        return _preset_map(label, entry["preset_map"])
    return _paths_are_text(label, entry, kinds)


def _docx_theme(label: str, entry: dict) -> list[str]:
    if "reference_doc" not in entry:
        return [f"{label}: reference_doc이 없습니다"]
    return _paths_are_text(label, entry, ("reference_doc", "tokens"))


def _theme(catalog: Catalog, fmt: str, name: str, entry, files: bool) -> list[str]:
    label = f"테마 {fmt}/{name}"
    if entry is None:  # 이름만 남기고 끈 테마(플러그인 항목 덮어쓰기용)
        return []
    if not isinstance(entry, dict):
        return [f"{label}: 매핑이어야 합니다"]
    if fmt == "docx":
        found = _docx_theme(label, entry)
        keys = ("reference_doc", "tokens")
    elif fmt == "hwpx":
        found = _hwpx_theme(label, entry)
        keys = ("template_path", "pack_path")
    else:
        return []
    return found or (_missing(catalog, label, entry, keys) if files else [])


def _themes(catalog: Catalog, files: bool) -> list[str]:
    themes = catalog.data.get("themes")
    if themes is None:
        return []
    if not isinstance(themes, dict):
        return ["themes는 매핑이어야 합니다"]
    out = []
    for fmt, named in themes.items():
        if fmt not in FORMATS:
            out.append(f"themes.{fmt}: 형식은 {'|'.join(FORMATS)} 중 하나여야 합니다")
        elif named is not None and not isinstance(named, dict):
            out.append(f"themes.{fmt}: 매핑이어야 합니다")
        else:
            for name, entry in (named or {}).items():
                out.extend(_theme(catalog, fmt, name, entry, files))
    return out


def _fixed_entry(index: int, entry) -> list[str]:
    if not isinstance(entry, dict):
        return [f"fixed[{index}]: 매핑이어야 합니다"]
    label = f"고정 {entry.get('id')!s}" if _text(entry.get("id")) else f"fixed[{index}]"
    out = [] if _text(entry.get("id")) else [f"{label}: id가 없습니다"]
    doc_type = entry.get("doc_type")
    if not isinstance(doc_type, list) or not doc_type or not all(_text(d) for d in doc_type):
        out.append(f"{label}: doc_type은 비어 있지 않은 문자열의 목록이어야 합니다")
    if entry.get("format") not in FORMATS:
        out.append(f"{label}: format은 {'|'.join(FORMATS)} 중 하나여야 합니다({entry.get('format')!r})")
    if not _text(entry.get("file")):
        out.append(f"{label}: file이 없습니다")
    out.extend(_paths_are_text(label, entry, ("profile",)))
    return out


def _fixed(catalog: Catalog, files: bool) -> list[str]:
    fixed = catalog.data.get("fixed")
    if fixed is None:
        return []
    if not isinstance(fixed, list):
        return ["fixed는 목록이어야 합니다"]
    out, seen = [], set()
    for index, entry in enumerate(fixed):
        found = _fixed_entry(index, entry)
        fid = entry.get("id") if isinstance(entry, dict) else None
        if _text(fid) and fid in seen:
            found.append(f"고정 {fid}: 같은 카탈로그 안에서 id가 겹칩니다")
        if _text(fid):
            seen.add(fid)
        if files and not found:
            found = _missing(catalog, f"고정 {fid}", entry, ("file", "profile"))
        out.extend(found)
    return out


def problems(catalog: Catalog, files: bool = True) -> list[str]:
    """카탈로그 한 개의 문제 목록. 각 줄 앞에 출처와 경로를 붙인다."""
    found = _themes(catalog, files) + _fixed(catalog, files)
    return [f"{catalog.source} {catalog.path}: {line}" for line in found]
