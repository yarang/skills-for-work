"""catalog.py 수용 테스트.

계약: docs/design.md §9.3·§9.5, newdoc/skills/newdoc-workflow/SKILL.md ① 7번,
docs/briefs/brief_newdoc.md N2.

모든 테스트는 tmp_path 카탈로그만 씁니다. 플러그인 카탈로그는 `--plugin-catalog`로 바꾸고,
사용자 카탈로그는 `DOCU_WRITER_TEMPLATES`를 빈 폴더로 두어 이 컴퓨터의
`~/.config/docu-writer/templates/`가 섞이지 않게 합니다.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import ROOT, uv

CATALOG = ROOT / "newdoc/skills/newdoc-workflow/scripts/catalog.py"
ROUTE_KEYS = {
    "route", "format", "doc_type", "theme", "catalog_id", "file", "profile", "reference_doc",
    "tokens", "preset", "template_path", "pack_path", "catalog_source", "mode",
}
PRESETS = {"보고서": "보고서", "계획서": "계획서", "기안문": "기안문", "회의록": "회의록", "보도자료": "보도자료"}


def real(path) -> str:
    return os.path.realpath(path)


def touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_catalog(folder: Path, data, raw: str | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "catalog.yaml"
    text = raw if raw is not None else yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path


def plugin_data(**over) -> dict:
    data = {
        "catalog_version": 1,
        "themes": {
            "docx": {"default": {"reference_doc": "themes/docx/default.docx",
                                 "tokens": "themes/docx/default.tokens.yaml"}},
            "hwpx": {"default": {"preset_map": dict(PRESETS)}},
            "md": {},
        },
        "fixed": [],
    }
    data.update(over)
    return data


@pytest.fixture
def env(tmp_path):
    """플러그인 카탈로그(테마 파일 포함)와 빈 사용자 폴더."""
    plugin = tmp_path / "plugin"
    touch(plugin / "themes/docx/default.docx")
    touch(plugin / "themes/docx/default.tokens.yaml", b"page: {}\n")
    user = tmp_path / "user"
    user.mkdir()
    proc_env = dict(os.environ, DOCU_WRITER_TEMPLATES=str(user))
    return {
        "tmp": tmp_path, "plugin": plugin, "user": user, "env": proc_env,
        "plugin_cat": write_catalog(plugin, plugin_data()), "out": tmp_path / "work/route.json",
    }


def cat(env, *args, cwd=None, proc_env=None):
    return uv(CATALOG, "--plugin-catalog", env["plugin_cat"], *args,
              env=proc_env or env["env"], cwd=cwd)


def match(env, doc_type, fmt, **kw):
    return cat(env, "match", "--type", doc_type, "--format", fmt, "--out", env["out"], **kw)


def route(env) -> dict:
    data = json.loads(env["out"].read_text(encoding="utf-8"))
    assert set(data) == ROUTE_KEYS
    return data


def lines(proc) -> list:
    return proc.stdout.splitlines()


def assert_refused(proc, env):
    assert proc.returncode == 2, proc.stderr
    assert proc.stdout == ""
    assert not env["out"].exists()


# --- 1 docx 테마 -----------------------------------------------------------------

def test_docx_theme_match(env):
    proc = match(env, "보고서", "docx")
    assert proc.returncode == 0, proc.stderr
    ref = real(env["plugin"] / "themes/docx/default.docx")
    tokens = real(env["plugin"] / "themes/docx/default.tokens.yaml")
    assert lines(proc) == [ref, tokens]
    assert route(env) == {
        "route": "theme", "format": "docx", "doc_type": "보고서", "theme": "docx/default",
        "catalog_id": None, "file": None, "profile": None, "reference_doc": ref, "tokens": tokens,
        "preset": None, "template_path": None, "pack_path": None, "catalog_source": "plugin", "mode": None,
    }
    assert "보고서" in env["out"].read_text(encoding="utf-8")  # ensure_ascii=False


def test_docx_theme_without_tokens(env):
    data = plugin_data()
    data["themes"]["docx"]["default"] = {"reference_doc": "themes/docx/default.docx"}
    env["plugin_cat"] = write_catalog(env["plugin"], data)
    proc = match(env, "보고서", "docx")
    assert proc.returncode == 0, proc.stderr
    assert lines(proc) == [real(env["plugin"] / "themes/docx/default.docx")]
    assert route(env)["tokens"] is None


# --- 2 hwpx preset_map -----------------------------------------------------------

@pytest.mark.parametrize("given", ["보고서", " 보 고 서 ", "보고　서"])
def test_hwpx_preset_match(env, given):
    proc = match(env, given, "hwpx")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    got = route(env)
    assert (got["route"], got["theme"], got["preset"]) == ("theme", "hwpx/default", "보고서")
    assert got["doc_type"] == given
    assert got["catalog_source"] == "plugin"
    assert got["template_path"] is None and got["pack_path"] is None


def test_hwpx_preset_no_prefix_match(env):
    proc = match(env, "보고", "hwpx")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    got = route(env)
    assert got["route"] == "none"
    assert got["theme"] is None and got["preset"] is None and got["catalog_source"] is None


@pytest.mark.parametrize("key", ["template_path", "pack_path"])
def test_hwpx_template_theme(env, key):
    touch(env["plugin"] / "themes/hwpx/부서.hwpx")
    data = plugin_data()
    data["themes"]["hwpx"]["default"] = {key: "themes/hwpx/부서.hwpx"}
    env["plugin_cat"] = write_catalog(env["plugin"], data)
    proc = match(env, "아무 종류", "hwpx")
    assert proc.returncode == 0, proc.stderr
    path = real(env["plugin"] / "themes/hwpx/부서.hwpx")
    assert lines(proc) == [path]
    got = route(env)
    assert got["route"] == "theme" and got[key] == path and got["preset"] is None


# --- 3 hwpx 배타 -----------------------------------------------------------------

def test_hwpx_two_kinds_rejected(env):
    touch(env["plugin"] / "themes/hwpx/부서.hwpx")
    data = plugin_data()
    data["themes"]["hwpx"]["default"] = {"preset_map": dict(PRESETS), "template_path": "themes/hwpx/부서.hwpx"}
    env["plugin_cat"] = write_catalog(env["plugin"], data)
    proc = cat(env, "check", env["plugin_cat"])
    assert proc.returncode == 1
    assert "hwpx/default" in proc.stdout + proc.stderr
    assert cat(env, "check").returncode == 1
    assert_refused(match(env, "보고서", "hwpx"), env)


# --- check 규칙 ------------------------------------------------------------------

def _bad_fixed(**over):
    entry = {"id": "a", "doc_type": ["기안문"], "format": "docx", "file": "fixed/a.docx"}
    entry.update(over)
    return [{k: v for k, v in entry.items() if v is not None}]


BAD = {
    "hwpx_zero": lambda d: d["themes"]["hwpx"].update(default={"note": "비어 있음"}),
    "fixed_no_id": lambda d: d.update(fixed=_bad_fixed(id=None)),
    "fixed_no_doc_type": lambda d: d.update(fixed=_bad_fixed(doc_type=None)),
    "fixed_doc_type_str": lambda d: d.update(fixed=_bad_fixed(doc_type="기안문")),
    "fixed_doc_type_empty_item": lambda d: d.update(fixed=_bad_fixed(doc_type=["기안문", " "])),
    "fixed_no_format": lambda d: d.update(fixed=_bad_fixed(format=None)),
    "fixed_bad_format": lambda d: d.update(fixed=_bad_fixed(format="pptx")),
    "fixed_no_file": lambda d: d.update(fixed=_bad_fixed(file=None)),
    "fixed_dup_id": lambda d: d.update(fixed=_bad_fixed() + _bad_fixed()),
    "fixed_bad_mode": lambda d: d.update(fixed=_bad_fixed(mode="update")),
    "theme_bad_format": lambda d: d["themes"].update(pptx={"default": {"reference_doc": "x.pptx"}}),
    "docx_no_reference": lambda d: d["themes"]["docx"].update(default={"tokens": "themes/docx/default.tokens.yaml"}),
    "file_missing": lambda d: d.update(fixed=_bad_fixed(file="fixed/없음.docx")),
    "profile_missing": lambda d: d.update(fixed=_bad_fixed(profile="fixed/없음.profile.yaml")),
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_check_rejects(env, case):
    touch(env["plugin"] / "fixed/a.docx")
    data = plugin_data()
    BAD[case](data)
    env["plugin_cat"] = write_catalog(env["plugin"], data)
    proc = cat(env, "check", env["plugin_cat"])
    assert proc.returncode == 1, (case, proc.stdout, proc.stderr)
    assert proc.stdout.strip()


def test_check_ok(env):
    touch(env["plugin"] / "fixed/a.docx")
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=_bad_fixed()))
    proc = cat(env, "check")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_check_user_dup_of_plugin_id_is_fine(env):
    """id가 겹치는 것은 카탈로그 사이에서는 덮어쓰기이고, 한 카탈로그 안에서만 오류."""
    touch(env["plugin"] / "fixed/a.docx")
    touch(env["user"] / "fixed/a.docx")
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=_bad_fixed()))
    write_catalog(env["user"], {"catalog_version": 1, "fixed": _bad_fixed()})
    assert cat(env, "check").returncode == 0


# --- 4 md ------------------------------------------------------------------------

def test_md_is_none(env):
    proc = match(env, "보고서", "md")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    got = route(env)
    assert got["route"] == "none" and got["format"] == "md" and got["doc_type"] == "보고서"
    assert all(got[k] is None for k in ROUTE_KEYS - {"route", "format", "doc_type"})


# --- 5 우선순위 ------------------------------------------------------------------

def _fixed(fid, fmt="hwpx", file="fixed/기안문.hwpx", profile=None, doc_type=("기안문", "내부 결재")):
    entry = {"id": fid, "doc_type": list(doc_type), "format": fmt, "file": file}
    if profile:
        entry["profile"] = profile
    return entry


def test_fixed_beats_theme(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    touch(env["plugin"] / "fixed/기안문.profile.yaml")
    fixed = [_fixed("우리과-기안문", profile="fixed/기안문.profile.yaml")]
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=fixed))
    proc = match(env, "내부결재", "hwpx")
    assert proc.returncode == 0, proc.stderr
    f, p = real(env["plugin"] / "fixed/기안문.hwpx"), real(env["plugin"] / "fixed/기안문.profile.yaml")
    assert lines(proc) == [f, p]
    got = route(env)
    assert (got["route"], got["catalog_id"], got["file"], got["profile"]) == ("fixed", "우리과-기안문", f, p)
    assert got["catalog_source"] == "plugin" and got["theme"] is None and got["preset"] is None
    assert got["mode"] == "sample"  # mode를 적지 않으면 견본


def test_fixed_needs_same_format(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=[_fixed("a")]))
    proc = match(env, "기안문", "docx")
    assert proc.returncode == 0, proc.stderr
    assert route(env)["route"] == "theme"


def test_user_fixed_same_id_replaces_plugin(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    touch(env["user"] / "fixed/새기안문.hwpx")
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=[_fixed("우리과-기안문")]))
    write_catalog(env["user"], {"catalog_version": 1,
                                "fixed": [_fixed("우리과-기안문", file="fixed/새기안문.hwpx")]})
    proc = match(env, "기안문", "hwpx")
    assert proc.returncode == 0, proc.stderr
    got = route(env)
    assert got["file"] == real(env["user"] / "fixed/새기안문.hwpx")
    assert got["catalog_source"] == "user"
    assert lines(proc) == [got["file"]]


def test_user_fixed_before_plugin_fixed(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    touch(env["user"] / "fixed/b.hwpx")
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=[_fixed("a")]))
    write_catalog(env["user"], {"catalog_version": 1, "fixed": [_fixed("b", file="fixed/b.hwpx")]})
    proc = match(env, "기안문", "hwpx")
    assert proc.returncode == 0, proc.stderr
    assert (route(env)["catalog_id"], route(env)["catalog_source"]) == ("b", "user")


def test_first_fixed_in_catalog_order(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    fixed = [_fixed("첫째"), _fixed("둘째")]
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=fixed))
    assert match(env, "기안문", "hwpx").returncode == 0
    assert route(env)["catalog_id"] == "첫째"


def test_user_theme_replaces_plugin(env):
    touch(env["user"] / "mine.docx")
    write_catalog(env["user"], {"catalog_version": 1,
                                "themes": {"docx": {"default": {"reference_doc": "mine.docx"}}}})
    proc = match(env, "보고서", "docx")
    assert proc.returncode == 0, proc.stderr
    got = route(env)
    assert got["reference_doc"] == real(env["user"] / "mine.docx")
    assert got["tokens"] is None and got["catalog_source"] == "user"
    assert lines(proc) == [got["reference_doc"]]


def test_user_other_theme_keeps_plugin_default(env):
    touch(env["user"] / "mine.docx")
    write_catalog(env["user"], {"catalog_version": 1,
                                "themes": {"docx": {"formal": {"reference_doc": "mine.docx"}}}})
    assert match(env, "보고서", "docx").returncode == 0
    assert route(env)["catalog_source"] == "plugin"


# --- 6 상대 경로 -----------------------------------------------------------------

def test_relative_path_against_user_catalog(env):
    touch(env["user"] / "fixed/x.hwpx")
    decoy = env["tmp"] / "cwd"
    touch(decoy / "fixed/x.hwpx")
    write_catalog(env["user"], {"catalog_version": 1, "fixed": [_fixed("x", file="fixed/x.hwpx")]})
    proc = match(env, "기안문", "hwpx", cwd=decoy)
    assert proc.returncode == 0, proc.stderr
    assert route(env)["file"] == real(env["user"] / "fixed/x.hwpx")


# --- 7·8 파일 없음·덮어쓰기 ------------------------------------------------------

def test_missing_reference_doc(env):
    (env["plugin"] / "themes/docx/default.docx").unlink()
    proc = match(env, "보고서", "docx")
    assert_refused(proc, env)
    assert "default.docx" in proc.stderr


def test_missing_fixed_profile(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    fixed = [_fixed("a", profile="fixed/없음.yaml")]
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=fixed))
    proc = match(env, "기안문", "hwpx")
    assert_refused(proc, env)
    assert "a" in proc.stderr


def test_existing_out_not_overwritten(env):
    touch(env["out"], b"old")
    proc = match(env, "보고서", "docx")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert env["out"].read_bytes() == b"old"


# --- 9 카탈로그 문법 -------------------------------------------------------------

def test_plugin_yaml_syntax_error(env):
    env["plugin_cat"] = write_catalog(env["plugin"], None, raw="catalog_version: 1\nthemes: [\n")
    assert_refused(match(env, "보고서", "docx"), env)


def test_user_yaml_syntax_error(env):
    write_catalog(env["user"], None, raw="catalog_version: 1\nfixed: {: :\n")
    assert_refused(match(env, "보고서", "docx"), env)
    assert cat(env, "check").returncode == 2


@pytest.mark.parametrize("version", [2, None, "1"])
def test_bad_catalog_version(env, version):
    data = plugin_data(catalog_version=version)
    env["plugin_cat"] = write_catalog(env["plugin"], data)
    assert_refused(match(env, "보고서", "docx"), env)
    assert cat(env, "check", env["plugin_cat"]).returncode == 2


def test_missing_plugin_catalog(env):
    env["plugin_cat"].unlink()
    assert_refused(match(env, "보고서", "docx"), env)


def test_templates_env_set_but_missing(env):
    proc_env = dict(env["env"], DOCU_WRITER_TEMPLATES=str(env["tmp"] / "없는폴더"))
    assert_refused(match(env, "보고서", "docx", proc_env=proc_env), env)


def test_templates_dir_without_catalog_is_empty(env):
    assert match(env, "보고서", "docx").returncode == 0
    assert route(env)["catalog_source"] == "plugin"


# --- 10 HOME 기본 위치 -----------------------------------------------------------

def _uv_dirs() -> dict:
    cache = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    py = subprocess.run(["uv", "python", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    return {"UV_CACHE_DIR": cache, "UV_PYTHON_INSTALL_DIR": py}


@pytest.fixture
def home_env(env, monkeypatch):
    dirs = _uv_dirs()
    home = env["tmp"] / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DOCU_WRITER_TEMPLATES", raising=False)
    proc_env = {k: v for k, v in os.environ.items() if k != "DOCU_WRITER_TEMPLATES"}
    proc_env.update(dirs, HOME=str(home))
    return home, proc_env


def test_no_user_catalog_plugin_only(env, home_env):
    _, proc_env = home_env
    proc = match(env, "보고서", "docx", proc_env=proc_env)
    assert proc.returncode == 0, proc.stderr
    assert route(env)["catalog_source"] == "plugin"


def test_home_config_catalog_used(env, home_env):
    home, proc_env = home_env
    folder = home / ".config/docu-writer/templates"
    touch(folder / "mine.docx")
    write_catalog(folder, {"catalog_version": 1, "themes": {"docx": {"default": {"reference_doc": "mine.docx"}}}})
    proc = match(env, "보고서", "docx", proc_env=proc_env)
    assert proc.returncode == 0, proc.stderr
    got = route(env)
    assert got["catalog_source"] == "user" and got["reference_doc"] == real(folder / "mine.docx")


# --- 사용법·list -----------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["match", "--type", "보고서", "--format", "pptx", "--out", "{out}"],
    ["match", "--type", "보고서", "--out", "{out}"],
    ["match", "--type", "  ", "--format", "docx", "--out", "{out}"],
    ["bogus"],
    [],
])
def test_usage_errors(env, args):
    proc = cat(env, *[a.replace("{out}", str(env["out"])) for a in args])
    assert_refused(proc, env)


def test_help_mentions_plugin_catalog():
    proc = uv(CATALOG, "--help")
    assert proc.returncode == 0
    assert "--plugin-catalog" in proc.stdout


def test_list_shows_sources(env):
    touch(env["user"] / "mine.docx")
    touch(env["user"] / "fixed/b.hwpx")
    write_catalog(env["user"], {"catalog_version": 1,
                                "themes": {"docx": {"formal": {"reference_doc": "mine.docx"}}},
                                "fixed": [_fixed("b", file="fixed/b.hwpx")]})
    proc = cat(env, "list")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "docx/default" in out and "docx/formal" in out and "hwpx/default" in out and "b" in out
    assert "plugin" in out and "user" in out
    only = cat(env, "list", "--format", "hwpx").stdout
    assert "hwpx/default" in only and "docx/default" not in only


def test_fixed_mode_form_passes_through(env):
    touch(env["plugin"] / "fixed/기안문.hwpx")
    entry = _fixed("기안문-양식")
    entry["mode"] = "form"
    env["plugin_cat"] = write_catalog(env["plugin"], plugin_data(fixed=[entry]))
    proc = match(env, "기안문", "hwpx")
    assert proc.returncode == 0, proc.stderr
    got = route(env)
    assert (got["route"], got["mode"]) == ("fixed", "form")
