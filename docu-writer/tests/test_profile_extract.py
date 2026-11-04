"""profile_extract.py 수용 테스트.

계약: template/skills/template-analysis/SKILL.md 「profile_extract.py 계약」·
「locator와 anchor」·「견본 문구 지문」·「프로파일 점검」.
"""
import hashlib

import pytest
import yaml

from conftest import BODY_SENTENCE, EXPECTED_TABLES, PROFILE_EXTRACT, uv


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
    p["mode"] = "new"


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
