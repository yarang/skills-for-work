"""catalog.py 도우미: 카탈로그 위치 찾기·읽기·합치기.

계약: docs/design.md §9.3. 사용자 항목이 같은 키(테마 `<형식>/<이름>`, 고정 `id`)의
플러그인 항목을 덮어씁니다. 상대 경로는 그 항목을 정의한 catalog.yaml 폴더 기준입니다.
"""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

FORMATS = ("md", "docx", "hwpx")
PLUGIN_CATALOG = Path(__file__).resolve().parent.parent.parent.parent / "templates/catalog.yaml"
USER_ENV = "DOCU_WRITER_TEMPLATES"


class CatalogError(Exception):
    """사용법·카탈로그 문법·파일 오류(종료 코드 2)."""


@dataclass(frozen=True)
class Catalog:
    source: str  # plugin | user
    path: Path
    data: dict

    @property
    def base(self) -> Path:
        return self.path.parent


@dataclass(frozen=True)
class Item:
    """합친 뒤의 항목 하나와 그 출처."""
    key: str
    entry: object
    catalog: Catalog


def normalize(text: str) -> str:
    """공백(전각 공백 포함)을 모두 지운다."""
    return "".join(str(text).split())


def resolve(catalog: Catalog, value: str) -> str:
    """정의한 카탈로그 폴더 기준으로 경로를 풀어 realpath로 돌려준다."""
    return os.path.realpath(catalog.base / Path(value).expanduser())


def user_catalog_path() -> Path | None:
    """사용자 카탈로그 경로. 파일이 없으면 None(빈 카탈로그)."""
    folder = os.environ.get(USER_ENV, "")
    if folder:
        base = Path(folder).expanduser()
        if not base.is_dir():
            raise CatalogError(f"{USER_ENV}가 가리키는 폴더가 없습니다: {base}")
    else:
        base = Path.home() / ".config/docu-writer/templates"
    path = base / "catalog.yaml"
    return path if path.is_file() else None


def load_catalog(path: Path, source: str) -> Catalog:
    """YAML 문법·최상위 형태·catalog_version만 본다. 나머지는 _cat_check가 본다."""
    if not path.is_file():
        raise CatalogError(f"카탈로그 파일이 없습니다: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as err:
        raise CatalogError(f"카탈로그를 읽을 수 없습니다: {path}: {err}") from err
    if not isinstance(data, dict):
        raise CatalogError(f"카탈로그 최상위가 매핑이 아닙니다: {path}")
    version = data.get("catalog_version")
    if type(version) is not int or version != 1:
        raise CatalogError(f"catalog_version은 1이어야 합니다({version!r}): {path}")
    return Catalog(source, path, data)


def load_all(plugin_path: Path | None) -> list[Catalog]:
    """[플러그인, 사용자(있으면)] 순서."""
    catalogs = [load_catalog(plugin_path or PLUGIN_CATALOG, "plugin")]
    user = user_catalog_path()
    if user is not None:
        catalogs.append(load_catalog(user, "user"))
    return catalogs


def theme_items(catalog: Catalog) -> list[Item]:
    themes = catalog.data.get("themes") or {}
    if not isinstance(themes, dict):
        return []
    items = []
    for fmt, named in themes.items():
        if isinstance(named, dict):
            items.extend(Item(f"{fmt}/{name}", entry, catalog) for name, entry in named.items())
    return items


def fixed_items(catalog: Catalog) -> list[Item]:
    fixed = catalog.data.get("fixed") or []
    if not isinstance(fixed, list):
        return []
    return [Item(str(e.get("id")) if isinstance(e, dict) else "", e, catalog) for e in fixed]


def merged_themes(catalogs: list[Catalog]) -> dict[str, Item]:
    merged: dict[str, Item] = {}
    for catalog in catalogs:  # 뒤(사용자)가 앞(플러그인)을 덮어쓴다
        merged.update((item.key, item) for item in theme_items(catalog))
    return merged


def merged_fixed(catalogs: list[Catalog]) -> list[Item]:
    """사용자 항목(카탈로그 순서) 다음에 덮이지 않은 플러그인 항목."""
    ordered: list[Item] = []
    taken: set[str] = set()
    for catalog in reversed(catalogs):
        for item in fixed_items(catalog):
            if item.key not in taken:
                ordered.append(item)
        taken.update(item.key for item in fixed_items(catalog))
    return ordered
