"""check 신규 모드(mode: new): 견본 없이 planner가 낸 프로파일을 점검.

계약: template-analysis SKILL.md 「프로파일 점검」 「신규 모드」, 설계서 §9.6.
견본이 없으므로 anchor 풀이·순서와 표 범위는 보지 않고, 꼴과 design.route만 봅니다.
"""
import os
import re

from _pe_check import (LOCATOR_ROOTS, check_conflicts, check_section_keys,
                       get_sections, walk_strings)
from _pe_common import no_space

NEW_ANCHOR_RE = re.compile(r'^h:"(.*)"$')
SPACED_T_LOC_RE = re.compile(r"(?:^|[/\s])(t:\d+)")  # 공백 섞인 글 안의 t:N도 찾음 (리뷰 3차 M12)
FORBIDDEN_KEYS = ("source", "fields", "update")
PATH_KEYS = ("reference_doc", "template_path", "pack_path")
GD_CHOICES = ("preset", "template_path", "pack_path")
ROUTE_KEYS = {
    "pandoc": {"reference_doc"},
    "generate_document": {"preset", "gate", "template_path", "pack_path"},
    "copy": set(),
}


def check_new_header(prof, fails):
    if prof.get("profile_version") != 1:
        fails.append(f"profile_version이 1이 아님: {prof.get('profile_version')!r}")
    for key in FORBIDDEN_KEYS:
        if key in prof:
            fails.append(f"신규 모드인데 {key} 키가 있음 (없어야 함)")
    items = prof.get("sample_text")
    if items not in (None, []):
        fails.append(f"신규 모드인데 sample_text가 비어 있지 않음: {items!r}")


def check_new_anchors(sections, fails):
    seen = {}
    for i, s in enumerate(sections, 1):
        label = s.get("id") or f"섹션 {i}"
        anchor = s.get("anchor")
        m = NEW_ANCHOR_RE.match(anchor.strip()) if isinstance(anchor, str) else None
        if m is None:
            if anchor not in (None, ""):
                fails.append(f'{label}: anchor {anchor!r}가 h:"…" 꼴이 아님 (신규 모드)')
            continue
        key = no_space(m.group(1))
        if not key:
            fails.append(f"{label}: anchor {anchor!r}의 제목 글이 비어 있음")
        elif key in seen:
            fails.append(f"{label}: anchor {anchor!r}가 {seen[key]}와 겹침")
        else:
            seen[key] = label
        if key and key != no_space(str(s.get("title") or "")):
            # writer는 title을 그대로 제목으로 쓰고 doc-verify는 anchor 글로 섹션을 찾습니다 — 다르면 못 찾음
            fails.append(f"{label}: anchor {anchor!r}의 제목 글이 title과 다름 (신규 모드는 같아야 함)")


def check_no_table_locators(prof, fails):
    for root in LOCATOR_ROOTS:
        for text in walk_strings(prof.get(root), spaced=True):
            m = SPACED_T_LOC_RE.search(text)
            if m:  # 글 전체가 아닌 찾은 locator만 보고 (guide 같은 긴 글을 되풀이하지 않음)
                fails.append(f"{root}: {m.group(1)} — 신규 모드에는 표 locator(t:N)가 없어야 함")


def get_route(prof, fails):
    design = prof.get("design")
    route = design.get("route") if isinstance(design, dict) else None
    if not isinstance(route, dict):
        fails.append("신규 모드인데 design.route가 없음")
        return None
    tool = route.get("tool")
    if not isinstance(tool, str) or tool not in ROUTE_KEYS:
        fails.append(f"design.route.tool이 pandoc·generate_document·copy 가운데 하나가 아님: {tool!r}")
        return None
    return route


def check_route_keys(route, fails):
    tool = route["tool"]
    extra = sorted(k for k in route if k != "tool" and k not in ROUTE_KEYS[tool])
    if extra:
        fails.append(f"design.route: {tool}에 쓸 수 없는 키 — {', '.join(map(str, extra))}")
    if tool != "generate_document":
        return
    chosen = [k for k in GD_CHOICES if k in route]
    if len(chosen) > 1:
        fails.append(f"design.route: generate_document는 {', '.join(chosen)} 가운데 하나만 씀")
    if "preset" in route and (not isinstance(route["preset"], str) or not route["preset"].strip()):
        fails.append(f"design.route.preset이 비었거나 글이 아님: {route['preset']!r}")
    if "gate" in route:
        if "preset" not in route:
            fails.append("design.route.gate는 preset과 함께만 씀")
        if not isinstance(route["gate"], bool):
            fails.append(f"design.route.gate가 참·거짓 값이 아님: {route['gate']!r}")


def check_route_paths(route, fails):
    for key in PATH_KEYS:
        if key not in route:
            continue
        value = route[key]
        if not isinstance(value, str) or not os.path.isabs(value):
            fails.append(f"design.route.{key}가 절대 경로가 아님: {value!r}")
        elif not os.path.isfile(value):
            fails.append(f"design.route.{key} 파일이 없음: {value}")


def run_check_new(prof):
    """신규 모드 프로파일(이미 읽은 사전)의 실패 항목 목록."""
    fails = []
    check_new_header(prof, fails)
    sections = get_sections(prof, fails)
    check_section_keys(sections, fails, "new")
    check_new_anchors(sections, fails)
    check_no_table_locators(prof, fails)
    route = get_route(prof, fails)
    if route is not None:
        check_route_keys(route, fails)
        check_route_paths(route, fails)
    check_conflicts(prof, fails)
    return fails
