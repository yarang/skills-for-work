"""profile_extract.py 수용 테스트.

계약: template/skills/template-analysis/SKILL.md 「profile_extract.py 계약」·
「locator와 anchor」·「견본 문구 지문」·「프로파일 점검」.
"""
import hashlib
from pathlib import Path

import pytest
import yaml

from conftest import BODY_SENTENCE, EXPECTED_TABLES, FIXTURES, PII_YAML, PROFILE_EXTRACT, assert_no_pii, uv


def tables(path):
    proc = uv(PROFILE_EXTRACT, "tables", path)
    assert proc.returncode == 0, proc.stderr
    return yaml.safe_load(proc.stdout)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- tables ----------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["hwpx", "docx", "pptx", "md"])
def test_tables_numbering(samples, fmt):
    out = tables(samples[fmt])
    got = out["tables"]
    want = EXPECTED_TABLES[fmt]
    assert [t["at"] for t in got] == [t["at"] for t in want]
    for g, w in zip(got, want):
        for key, value in w.items():
            assert g[key] == value, (g["at"], key)
    assert "warnings" in out


def test_tables_hwpx_counts_frame_tables(samples):
    """kordoc 마크다운은 표 1개만 보이지만 최상위 hp:tbl은 5개."""
    assert len(tables(samples["hwpx"])["tables"]) == 5


def test_tables_empty_last_cell_falls_back(samples):
    t1 = tables(samples["docx"])["tables"][0]
    assert t1["last"] == "120건"


@pytest.mark.parametrize("args", [
    ["tables", "/nonexistent/x.docx"],
    ["tables"],
    ["bogus"],
])
def test_usage_errors_exit_2(args):
    assert uv(PROFILE_EXTRACT, *args).returncode == 2


def test_tables_unsupported_format(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert uv(PROFILE_EXTRACT, "tables", f).returncode == 2


# --- profile ---------------------------------------------------------------------

def make_profile(samples, fmt, tmp_path, mode="sample"):
    out = tmp_path / f"profile-{fmt}.yaml"
    proc = uv(PROFILE_EXTRACT, "profile", samples[fmt], "--mode", mode, "--out", out)
    assert proc.returncode == 0, proc.stderr
    return out, yaml.safe_load(out.read_text(encoding="utf-8"))


def test_profile_docx(samples, tmp_path):
    _, prof = make_profile(samples, "docx", tmp_path)
    assert prof["profile_version"] == 1
    assert prof["mode"] == "sample"
    assert prof["source"]["format"] == "docx"
    assert prof["source"]["sha256"] == sha256(samples["docx"])
    paras = samples["docx_paras"]
    anchors = {s["anchor"]: s for s in prof["structure"]["sections"]}
    assert anchors[paras["1. 추진 배경"]]["title"] == "1. 추진 배경"
    assert anchors[paras["2. 추진 일정"]]["level"] == 1
    order = [int(s["anchor"].split(":")[1]) for s in prof["structure"]["sections"]]
    assert order == sorted(order)
    assert "Heading 1" in prof["design"]["styles_allowed"]
    assert "Heading 9" not in prof["design"]["styles_allowed"]


def test_profile_sample_text_candidates(samples, tmp_path):
    _, prof = make_profile(samples, "docx", tmp_path)
    cands = prof["sample_text_candidates"]
    assert any(BODY_SENTENCE in c or c in BODY_SENTENCE for c in cands)
    for bad in ("1. 추진 배경", "구분", "합계", "기간"):
        assert bad not in cands


def test_profile_pptx_sections_per_slide(samples, tmp_path):
    _, prof = make_profile(samples, "pptx", tmp_path)
    anchors = [s["anchor"] for s in prof["structure"]["sections"]]
    assert anchors[:3] == ["sl:1", "sl:2", "sl:3"]
    assert prof["design"]["page"]  # 슬라이드 크기


def test_profile_md_heading_anchors(samples, tmp_path):
    _, prof = make_profile(samples, "md", tmp_path)
    anchors = [s["anchor"] for s in prof["structure"]["sections"]]
    assert 'h:"1. 추진 배경"' in anchors
    assert anchors.index('h:"1. 추진 배경"') < anchors.index('h:"2. 실적"')


def test_profile_form_mode(samples, tmp_path):
    _, prof = make_profile(samples, "docx", tmp_path, mode="form")
    assert prof["mode"] == "form"
    assert isinstance(prof["fields"], list)


def test_profile_form_labels_not_candidates(tmp_path):
    """종단 시험 F4: 양식의 칸 이름표(6자 이상)가 sample_text 후보로 새면 안 됩니다."""
    from docx import Document

    doc = Document()
    doc.add_paragraph("아래 칸을 빠짐없이 적어 주십시오.")
    table = doc.add_table(rows=3, cols=2)
    for r, label in enumerate(["성명", "부서장 확인", "신청 사유 요약"]):
        table.cell(r, 0).text = label
    src = tmp_path / "form.docx"
    doc.save(src)
    out = tmp_path / "p.yaml"
    proc = uv(PROFILE_EXTRACT, "profile", src, "--mode", "form", "--out", out)
    assert proc.returncode == 0, proc.stderr
    prof = yaml.safe_load(out.read_text(encoding="utf-8"))
    labels = {f["label"] for f in prof["fields"]}
    assert {"부서장 확인", "신청 사유 요약"} <= labels
    cands = prof["sample_text_candidates"]
    assert "아래 칸을 빠짐없이 적어 주십시오." in cands
    assert not labels & set(cands)


def test_profile_hwpx_unsupported(samples, tmp_path):
    proc = uv(PROFILE_EXTRACT, "profile", samples["hwpx"], "--mode", "sample", "--out", tmp_path / "p.yaml")
    assert proc.returncode == 2
    assert not (tmp_path / "p.yaml").exists()


def test_profile_out_exists_not_overwritten(samples, tmp_path):
    out = tmp_path / "p.yaml"
    out.write_text("keep", encoding="utf-8")
    proc = uv(PROFILE_EXTRACT, "profile", samples["docx"], "--mode", "sample", "--out", out)
    assert proc.returncode == 2
    assert out.read_text(encoding="utf-8") == "keep"


def test_profile_does_not_modify_sample(samples, tmp_path):
    before = sha256(samples["docx"])
    make_profile(samples, "docx", tmp_path)
    assert sha256(samples["docx"]) == before


# --- check -----------------------------------------------------------------------

def completed(prof):
    """analyst가 채우는 칸을 채운 유효한 프로파일."""
    for i, s in enumerate(prof["structure"]["sections"], 1):
        s.update(id=f"s{i}", kind="서술", required=True, guide="사실로 시작해 문제점을 적음",
                 length={"lines": [1, 5]})
    prof["sample_text"] = [BODY_SENTENCE[:20]]
    prof["conflicts"] = [{"item": "검토한 대안", "from": "tech-docs", "handling": "report"}]
    prof.setdefault("voice", {"style": "서술식", "ending": "-다", "terms": {}})
    return prof


def check(samples, fmt, prof, tmp_path, with_tables=True):
    p = tmp_path / "checked.yaml"
    p.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
    args = ["check", p, "--source", samples[fmt]]
    if with_tables:
        t = tmp_path / "tables.yaml"
        t.write_text(uv(PROFILE_EXTRACT, "tables", samples[fmt]).stdout, encoding="utf-8")
        args += ["--tables", t]
    return uv(PROFILE_EXTRACT, *args)


@pytest.fixture
def valid(samples, tmp_path):
    _, prof = make_profile(samples, "docx", tmp_path)
    return completed(prof)


def test_check_valid_passes(samples, valid, tmp_path):
    proc = check(samples, "docx", valid, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def mutate_sha(p):
    p["source"]["sha256"] = "0" * 64


def mutate_dup_id(p):
    p["structure"]["sections"][1]["id"] = p["structure"]["sections"][0]["id"]


def mutate_missing_guide(p):
    del p["structure"]["sections"][0]["guide"]


def mutate_bad_anchor(p):
    p["structure"]["sections"][0]["anchor"] = "p:999"


def mutate_anchor_order(p):
    s = p["structure"]["sections"]
    s[0]["anchor"], s[1]["anchor"] = s[1]["anchor"], s[0]["anchor"]


def mutate_table_range(p):
    p["mode"] = "form"
    p["fields"] = [{"id": "f1", "label": "담당", "locator": "t:9/r:1/c:1", "constraint": ""}]


def mutate_cell_range(p):
    p["mode"] = "form"
    p["fields"] = [{"id": "f1", "label": "담당", "locator": "t:1/r:4/c:1", "constraint": ""}]


def mutate_form_without_fields(p):
    p["mode"] = "form"
    p["fields"] = []


def mutate_update_unknown_section(p):
    p["mode"] = "update"
    p["update"] = {"sections": ["s99"], "requests": ["일정 수정"]}


def mutate_update_no_requests(p):
    p["mode"] = "update"
    p["update"] = {"sections": ["s1"], "requests": []}


def mutate_short_sample_text(p):
    p["sample_text"].append("합계")


def mutate_placeholder_sample_text(p):
    p["sample_text"].append("○○○○○○○")


def mutate_sample_text_is_title(p):
    p["sample_text"].append(p["structure"]["sections"][0]["title"])


def mutate_guide_copies_sample(p):
    p["structure"]["sections"][0]["guide"] = "예: " + p["sample_text"][0]


def mutate_conflict_handling(p):
    p["conflicts"][0]["handling"] = "add"


def mutate_version(p):
    p["profile_version"] = 2


def mutate_mode(p):
    p["mode"] = "bogus"


@pytest.mark.parametrize("mutate", [
    mutate_sha, mutate_dup_id, mutate_missing_guide, mutate_bad_anchor, mutate_anchor_order,
    mutate_table_range, mutate_cell_range, mutate_form_without_fields,
    mutate_update_unknown_section, mutate_update_no_requests, mutate_short_sample_text,
    mutate_placeholder_sample_text, mutate_sample_text_is_title, mutate_guide_copies_sample,
    mutate_conflict_handling, mutate_version, mutate_mode,
])
def test_check_failures_exit_1(samples, valid, tmp_path, mutate):
    mutate(valid)
    proc = check(samples, "docx", valid, tmp_path)
    assert proc.returncode == 1, (mutate.__name__, proc.stdout, proc.stderr)



def test_check_form_sections_need_no_length(samples, valid, tmp_path):
    """종단 시험 F7: form 섹션은 쓰는 글이 아니므로 length를 요구하지 않습니다. sample은 계속 요구합니다."""
    for s in valid["structure"]["sections"]:
        s.pop("length")
    proc = check(samples, "docx", valid, tmp_path)
    assert proc.returncode == 1 and "length" in proc.stdout
    valid["mode"] = "form"
    valid["fields"] = [{"id": "f1", "label": "담당", "locator": "t:1/r:3/c:3", "constraint": ""}]
    proc = check(samples, "docx", valid, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr

def test_check_hwpx_heading_anchor(samples, tmp_path):
    """HWPX 프로파일은 analyst가 직접 쓰고, check는 h:"…"를 공백 무시로 풉니다."""
    prof = {
        "profile_version": 1,
        "mode": "sample",
        "source": {"path": str(samples["hwpx"]), "format": "hwpx", "sha256": sha256(samples["hwpx"])},
        "structure": {"numbering": ["□", "ㅇ"], "sections": [
            {"id": "s1", "title": "현황", "level": 2, "anchor": 'h:"□ 현황"', "kind": "목록",
             "required": True, "guide": "건수와 인력 문제를 적음", "length": {"lines": [2, 4]}},
            {"id": "s2", "title": "일정", "level": 2, "anchor": 'h:"□일정"', "kind": "표",
             "required": True, "guide": "단계별 기간과 담당", "length": {"lines": [1, 3]}},
        ]},
        "sample_text": ["2026년 상반기 신청 건수 120건"],
        "conflicts": [],
    }
    assert check(samples, "hwpx", prof, tmp_path).returncode == 0
    prof["structure"]["sections"][1]["anchor"] = 'h:"없는 제목"'
    assert check(samples, "hwpx", prof, tmp_path).returncode == 1


# --- check: 신규 모드 (mode: new) -------------------------------------------------
# 계약: template-analysis SKILL 「프로파일 점검」 「신규 모드」, 설계서 §9.6.

NEW_PROFILE = FIXTURES / "new" / "profile_extract" / "new_profile.yaml"


@pytest.fixture
def new_prof():
    return yaml.safe_load(NEW_PROFILE.read_text(encoding="utf-8"))


@pytest.fixture
def theme(tmp_path):
    """route 경로 값으로 쓸 실제 파일 (절대 경로)."""
    d = tmp_path / "theme"
    d.mkdir()
    files = {"docx": d / "default.docx", "hwpx": d / "서식.hwpx", "pack": d / "pack.json"}
    for f in files.values():
        f.write_bytes(b"x")
    return {k: str(v.resolve()) for k, v in files.items()}


def check_new(prof, tmp_path, *extra):
    p = tmp_path / "new-profile.yaml"
    p.write_text(yaml.safe_dump(prof, allow_unicode=True), encoding="utf-8")
    return uv(PROFILE_EXTRACT, "check", p, *extra)


VALID_ROUTES = {
    "pandoc_reference_doc": lambda t: {"tool": "pandoc", "reference_doc": t["docx"]},
    "pandoc_bare": lambda t: {"tool": "pandoc"},
    "gd_preset_gate": lambda t: {"tool": "generate_document", "preset": "보고서", "gate": True},
    "gd_preset": lambda t: {"tool": "generate_document", "preset": "계획서"},
    "gd_template_path": lambda t: {"tool": "generate_document", "template_path": t["hwpx"]},
    "gd_pack_path": lambda t: {"tool": "generate_document", "pack_path": t["pack"]},
    "gd_bare": lambda t: {"tool": "generate_document"},
    "copy": lambda t: {"tool": "copy"},
}


@pytest.mark.parametrize("name", list(VALID_ROUTES))
def test_check_new_valid_routes(new_prof, theme, tmp_path, name):
    new_prof["design"]["route"] = VALID_ROUTES[name](theme)
    proc = check_new(new_prof, tmp_path)
    assert proc.returncode == 0, (name, proc.stdout, proc.stderr)


def set_route(route):
    def mutate(p, t):
        p["design"]["route"] = route(t) if callable(route) else route
    return mutate


def set_anchor(i, anchor):
    def mutate(p, t):
        p["structure"]["sections"][i]["anchor"] = anchor
    return mutate


def set_key(key, value):
    def mutate(p, t):
        p[key] = value
    return mutate


def del_section_key(key):
    def mutate(p, t):
        del p["structure"]["sections"][0][key]
    return mutate


def add_table_locator(p, t):
    p["structure"]["sections"][0]["locator"] = "t:1/r:1/c:1"


def del_design(p, t):
    del p["design"]


def del_route(p, t):
    del p["design"]["route"]


NEW_VIOLATIONS = {
    "version": (set_key("profile_version", 2), "profile_version"),
    "source_key": (set_key("source", {"path": "/x.docx", "format": "docx", "sha256": "0" * 64}), "source"),
    "missing_guide": (del_section_key("guide"), "guide"),
    "missing_length": (del_section_key("length"), "length"),
    "anchor_p_form": (set_anchor(0, "p:3"), "anchor"),
    "anchor_empty": (set_anchor(0, 'h:""'), "anchor"),
    "anchor_blank": (set_anchor(0, 'h:"   "'), "anchor"),
    "anchor_nth": (set_anchor(1, 'h:"추진 배경"#2'), "anchor"),
    "anchor_duplicate": (set_anchor(1, 'h:"추진배경"'), "anchor"),
    "table_locator": (add_table_locator, "t:1"),
    "sample_text": (set_key("sample_text", ["2026년 상반기 신청 건수 120건"]), "sample_text"),
    "fields": (set_key("fields", [{"id": "f1", "label": "담당"}]), "fields"),
    "fields_empty": (set_key("fields", []), "fields"),
    "update": (set_key("update", {"sections": ["s1"], "requests": ["일정"]}), "update"),
    "conflict_handling": (set_key("conflicts", [{"item": "x", "handling": "add"}]), "conflicts"),
    "no_design": (del_design, "design.route"),
    "no_route": (del_route, "design.route"),
    "tool_unknown": (set_route({"tool": "soffice"}), "tool"),
    "tool_missing": (set_route({"reference_doc": "/x.docx"}), "tool"),
    "tool_list": (set_route({"tool": ["pandoc"]}), "tool"),
    "tool_map": (set_route({"tool": {"pandoc": None}}), "tool"),
    "pandoc_preset": (set_route({"tool": "pandoc", "preset": "보고서"}), "preset"),
    "pandoc_template": (set_route(lambda t: {"tool": "pandoc", "template_path": t["hwpx"]}), "template_path"),
    "gd_preset_and_template": (set_route(lambda t: {"tool": "generate_document", "preset": "보고서",
                                                    "template_path": t["hwpx"]}), "template_path"),
    "gd_template_and_pack": (set_route(lambda t: {"tool": "generate_document", "template_path": t["hwpx"],
                                                  "pack_path": t["pack"]}), "pack_path"),
    "gd_gate_without_preset": (set_route({"tool": "generate_document", "gate": True}), "gate"),
    "gd_gate_with_template": (set_route(lambda t: {"tool": "generate_document", "gate": True,
                                                   "template_path": t["hwpx"]}), "gate"),
    "gd_gate_not_bool": (set_route({"tool": "generate_document", "preset": "보고서", "gate": "yes"}), "gate"),
    "gd_preset_empty": (set_route({"tool": "generate_document", "preset": ""}), "preset"),
    "gd_unknown_key": (set_route({"tool": "generate_document", "reference_doc": "/x.docx"}), "reference_doc"),
    "copy_extra_key": (set_route(lambda t: {"tool": "copy", "reference_doc": t["docx"]}), "reference_doc"),
    "path_relative": (set_route({"tool": "pandoc", "reference_doc": "themes/docx/default.docx"}), "절대"),
    "path_missing": (set_route(lambda t: {"tool": "pandoc", "reference_doc": t["docx"] + ".none"}), "없"),
    "path_dir": (set_route(lambda t: {"tool": "generate_document",
                                      "pack_path": str(Path(t["pack"]).parent)}), "pack_path"),
}


@pytest.mark.parametrize("name", list(NEW_VIOLATIONS))
def test_check_new_violations_exit_1(new_prof, theme, tmp_path, name):
    mutate, reason = NEW_VIOLATIONS[name]
    mutate(new_prof, theme)
    proc = check_new(new_prof, tmp_path)
    assert proc.returncode == 1, (name, proc.stdout, proc.stderr)
    assert reason in proc.stdout, (name, proc.stdout)


def test_check_new_with_source_is_usage_error(new_prof, samples, tmp_path):
    proc = check_new(new_prof, tmp_path, "--source", samples["docx"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout == ""


def test_check_new_with_tables_is_usage_error(new_prof, tmp_path):
    t = tmp_path / "tables.yaml"
    t.write_text("tables: []\n", encoding="utf-8")
    proc = check_new(new_prof, tmp_path, "--tables", t)
    assert proc.returncode == 2, proc.stdout + proc.stderr


@pytest.mark.parametrize("mode", ["sample", "form", "update"])
def test_check_other_modes_need_source(valid, tmp_path, mode):
    valid["mode"] = mode
    proc = check_new(valid, tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout == ""


def test_check_missing_profile_without_source(tmp_path):
    assert uv(PROFILE_EXTRACT, "check", tmp_path / "none.yaml").returncode == 2


@pytest.mark.parametrize("with_source", [True, False])
def test_check_broken_yaml_profile_is_usage_error(samples, tmp_path, with_source):
    """YAML 문법 오류는 mode를 알 수 없어도 사용 오류(exit 2, 빈 표준 출력) — check 실패(exit 1)가 아님."""
    p = tmp_path / "broken.yaml"
    p.write_text("profile_version: [\n", encoding="utf-8")
    args = ["check", p] + (["--source", samples["docx"]] if with_source else [])
    proc = uv(PROFILE_EXTRACT, *args)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout == ""
    assert "YAML" in proc.stderr


def test_check_broken_profile_reports_line_only(tmp_path):
    """프로파일 YAML 오류 보고는 줄·열만 — 원문 조각은 옮기지 않습니다 (리뷰 3차 M9)."""
    p = tmp_path / "broken.yaml"
    p.write_text(PII_YAML, encoding="utf-8")
    proc = uv(PROFILE_EXTRACT, "check", p)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert_no_pii(proc.stdout + proc.stderr)


def test_check_broken_tables_reports_line_only(valid, samples, tmp_path):
    p = tmp_path / "checked.yaml"
    p.write_text(yaml.safe_dump(valid, allow_unicode=True), encoding="utf-8")
    t = tmp_path / "tables.yaml"
    t.write_text(PII_YAML, encoding="utf-8")
    proc = uv(PROFILE_EXTRACT, "check", p, "--source", samples["docx"], "--tables", t)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert_no_pii(proc.stdout + proc.stderr)
