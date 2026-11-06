"""catalog.py 도우미: 문서 종류·형식으로 경로(route)를 고릅니다.

계약: docs/design.md §9.3, docs/briefs/brief_newdoc.md N2 `match`.
순서: 고정 항목(사용자 → 플러그인, 카탈로그 순서) → `themes.<형식>.default` → none.
"""
from pathlib import Path

from _cat_load import CatalogError, Catalog, Item, normalize, resolve

ROUTE_KEYS = (
    "route", "format", "doc_type", "theme", "catalog_id", "file", "profile", "reference_doc",
    "tokens", "preset", "template_path", "pack_path", "catalog_source",
)


def empty_route(fmt: str, doc_type: str) -> dict:
    route = dict.fromkeys(ROUTE_KEYS)
    route.update(route="none", format=fmt, doc_type=doc_type)
    return route


def _path(catalog: Catalog, label: str, entry: dict, key: str) -> str | None:
    """참조 파일의 realpath. 값이 없으면 None, 파일이 없으면 CatalogError."""
    value = entry.get(key)
    if value is None:
        return None
    path = resolve(catalog, value)
    if not Path(path).exists():
        raise CatalogError(f"{label}의 {key} 파일이 없습니다: {path}")
    return path


def _fixed_route(route: dict, item: Item) -> tuple[dict, list[str]]:
    label = f"고정 항목 {item.key}"
    file = _path(item.catalog, label, item.entry, "file")
    profile = _path(item.catalog, label, item.entry, "profile")
    route.update(route="fixed", catalog_id=item.key, file=file, profile=profile,
                 catalog_source=item.catalog.source)
    return route, [p for p in (file, profile) if p]


def _preset(preset_map: dict, doc_type: str) -> str | None:
    wanted = normalize(doc_type)
    for key, preset in preset_map.items():
        if normalize(key) == wanted:
            return preset
    return None


def _theme_route(route: dict, item: Item, doc_type: str) -> tuple[dict, list[str]]:
    entry, catalog, label = item.entry, item.catalog, f"테마 {item.key}"
    theme = {"theme": item.key, "catalog_source": catalog.source}
    if route["format"] == "docx":
        ref = _path(catalog, label, entry, "reference_doc")
        tokens = _path(catalog, label, entry, "tokens")
        route.update(route="theme", reference_doc=ref, tokens=tokens, **theme)
        return route, [p for p in (ref, tokens) if p]
    if "preset_map" in entry:
        preset = _preset(entry["preset_map"], doc_type)
        if preset is not None:
            route.update(route="theme", preset=preset, **theme)
        return route, []
    key = "template_path" if "template_path" in entry else "pack_path"
    path = _path(catalog, label, entry, key)
    route.update({"route": "theme", key: path, **theme})
    return route, [path]


def _matches(item: Item, fmt: str, wanted: str) -> bool:
    entry = item.entry
    return entry.get("format") == fmt and any(normalize(d) == wanted for d in entry.get("doc_type", []))


def choose(fixed: list[Item], themes: dict[str, Item], fmt: str, doc_type: str) -> tuple[dict, list[str]]:
    """(route.json 내용, 보호할 경로 목록)."""
    wanted = normalize(doc_type)
    route = empty_route(fmt, doc_type)
    for item in fixed:
        if _matches(item, fmt, wanted):
            return _fixed_route(route, item)
    if fmt == "md":
        return route, []
    theme = themes.get(f"{fmt}/default")
    if theme is None or theme.entry is None:
        return route, []
    return _theme_route(route, theme, doc_type)
