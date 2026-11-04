"""patch_docx.py 수용 테스트.

계약: skills/format-docx/SKILL.md 「작성 (⑤) — patch_docx.py」.
locator는 dump 시점 기준이고, 실패한 편집이 하나라도 있으면 파일을 쓰지 않습니다.
"""
import hashlib
import json

import pytest
import yaml

from conftest import BODY_SENTENCE, EXPECTED_TABLES, PATCH_DOCX, uv

ALLOWED = ["Normal", "Title", "Heading 1", "List Bullet"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(samples, tmp_path):
    out = tmp_path / "skeleton.yaml"
    proc = uv(PATCH_DOCX, "dump", samples["docx"], "--out", out)
    assert proc.returncode == 0, proc.stderr
    return yaml.safe_load(out.read_text(encoding="utf-8"))


def by_at(blocks):
    return {b["at"]: b for b in blocks}


def write_profile(tmp_path, allowed=ALLOWED):
    p = tmp_path / "profile.yaml"
    p.write_text(yaml.safe_dump({"profile_version": 1, "design": {"styles_allowed": allowed}},
                                allow_unicode=True), encoding="utf-8")
    return p


def apply(samples, tmp_path, edits, allowed=ALLOWED, out_name="out.docx"):
    e = tmp_path / "edits.yaml"
    e.write_text(yaml.safe_dump(edits, allow_unicode=True), encoding="utf-8")
    out = tmp_path / out_name
    proc = uv(PATCH_DOCX, "apply", samples["docx"], "--edits", e,
              "--profile", write_profile(tmp_path, allowed), "--out", out)
    return proc, out


def body_paras(path):
    from docx import Document
    from docx.oxml.ns import qn
    body = Document(path).element.body
    return ["".join(t.text or "" for t in p.iter(qn("w:t"))) for p in body.iterchildren(qn("w:p"))]


def cell(path, t, r, c):
    from docx import Document
    return Document(path).tables[t - 1].rows[r - 1].cells[c - 1].paragraphs[0].text


# --- dump ------------------------------------------------------------------------

def test_dump_paragraph_locators_match_oracle(samples, tmp_path):
    blocks = by_at(dump(samples, tmp_path))
    for text, at in samples["docx_paras"].items():
        assert blocks[at]["text"] == text, at
    assert blocks[samples["docx_paras"]["1. 추진 배경"]]["style"] == "Heading 1"


def test_dump_cell_locators(samples, tmp_path):
    blocks = by_at(dump(samples, tmp_path))
    assert blocks["t:1/r:1/c:1"]["text"] == "구분"
    assert blocks["t:1/r:3/c:2"]["text"] == "120건"
    assert blocks["t:2/r:2/c:2"]["text"] == "운영팀 담당"  # 안쪽 표 글은 넣지 않음
    assert blocks["t:3/r:1/c:1"]["text"] == "요약 상자 글입니다"


def test_dump_table_grid_matches_shared_numbering(samples, tmp_path):
    """profile_extract tables와 같은 t:N 번호·행·열."""
    blocks = dump(samples, tmp_path)
    for want in EXPECTED_TABLES["docx"]:
        cells = [b["at"] for b in blocks if b["at"].startswith(want["at"] + "/")]
        rows = {int(a.split("/")[1][2:]) for a in cells}
        cols = {int(a.split("/")[2][2:]) for a in cells}
        assert (max(rows), max(cols)) == (want["rows"], want["cols"]), want["at"]


def test_dump_skips_header_table(samples, tmp_path):
    assert all("머리글 표" not in (b.get("text") or "") for b in dump(samples, tmp_path))


def test_dump_out_exists(samples, tmp_path):
    out = tmp_path / "skeleton.yaml"
    out.write_text("keep", encoding="utf-8")
    assert uv(PATCH_DOCX, "dump", samples["docx"], "--out", out).returncode == 2
    assert out.read_text(encoding="utf-8") == "keep"


# --- apply: 성공 -----------------------------------------------------------------

def test_apply_replace_paragraph_and_cell(samples, tmp_path):
    p = samples["docx_paras"]
    proc, out = apply(samples, tmp_path, [
        {"op": "replace", "at": p[BODY_SENTENCE], "text": "새 본문 문장이다."},
        {"op": "replace", "at": "t:1/r:3/c:3", "text": "기획팀"},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["applied"] == 2 and report["failed"] == []
    paras = body_paras(out)
    assert paras[int(p[BODY_SENTENCE][2:]) - 1] == "새 본문 문장이다."
    assert cell(out, 1, 3, 3) == "기획팀"


def test_apply_locators_resolved_at_dump_time(samples, tmp_path):
    """앞 편집이 문단을 늘려도 뒤 편집의 p:N은 dump 시점 문단을 가리킴."""
    p = samples["docx_paras"]
    proc, out = apply(samples, tmp_path, [
        {"op": "insert_after", "at": p[BODY_SENTENCE], "like": p[BODY_SENTENCE], "text": "덧붙인 문장이다."},
        {"op": "replace", "at": p["2. 추진 일정"], "text": "2. 일정"},
        {"op": "delete", "at": p[""]},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    paras = body_paras(out)
    i = paras.index(BODY_SENTENCE)
    assert paras[i + 1] == "덧붙인 문장이다."
    assert "2. 일정" in paras and "2. 추진 일정" not in paras
    assert "" not in paras[: paras.index("2. 일정")]


def test_insert_after_copies_like_style(samples, tmp_path):
    from docx import Document
    p = samples["docx_paras"]
    bullet = p["준비 단계는 1월에 기획팀이 맡는다"]
    proc, out = apply(samples, tmp_path, [
        {"op": "insert_after", "at": bullet, "like": bullet, "text": "시행 단계는 2~6월이다"},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    styles = {q.text: q.style.name for q in Document(out).paragraphs}
    assert styles["시행 단계는 2~6월이다"] == "List Bullet"


def test_row_add_and_row_delete(samples, tmp_path):
    from docx import Document
    proc, out = apply(samples, tmp_path, [
        {"op": "row_add", "table": "t:1", "like_row": 2, "after": 2, "cells": ["시행", "2~6월", "운영팀"]},
        {"op": "row_delete", "table": "t:2", "row": 2},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    doc = Document(out)
    assert len(doc.tables[0].rows) == 4
    assert [c.text for c in doc.tables[0].rows[2].cells] == ["시행", "2~6월", "운영팀"]
    assert doc.tables[0].rows[3].cells[0].text == "합계"
    assert len(doc.tables[1].rows) == 1


def test_apply_does_not_modify_sample(samples, tmp_path):
    before = sha256(samples["docx"])
    apply(samples, tmp_path, [{"op": "replace", "at": "t:1/r:1/c:1", "text": "항목"}])
    assert sha256(samples["docx"]) == before


# --- apply: 실패 -----------------------------------------------------------------

@pytest.mark.parametrize("edit", [
    {"op": "replace", "at": "p:999", "text": "x"},
    {"op": "replace", "at": "t:9/r:1/c:1", "text": "x"},
    {"op": "replace", "at": "p:3", "text": "두 줄\n글"},
    {"op": "row_delete", "table": "t:1", "row": 9},
    {"op": "unknown", "at": "p:3"},
])
def test_failed_edit_exit_1_no_file(samples, tmp_path, edit):
    proc, out = apply(samples, tmp_path, [{"op": "replace", "at": "t:1/r:1/c:1", "text": "항목"}, edit])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()
    report = json.loads(proc.stdout)
    assert len(report["failed"]) == 1
    assert {"op", "at", "reason"} <= set(report["failed"][0])


def test_style_outside_profile_fails(samples, tmp_path):
    p = samples["docx_paras"]
    bullet = p["준비 단계는 1월에 기획팀이 맡는다"]
    proc, out = apply(samples, tmp_path, [
        {"op": "insert_after", "at": bullet, "like": bullet, "text": "추가"},
    ], allowed=["Normal", "Title", "Heading 1"])
    assert proc.returncode == 1
    assert not out.exists()


def test_out_equals_sample_exit_2(samples, tmp_path):
    e = tmp_path / "edits.yaml"
    e.write_text("[]", encoding="utf-8")
    before = sha256(samples["docx"])
    proc = uv(PATCH_DOCX, "apply", samples["docx"], "--edits", e,
              "--profile", write_profile(tmp_path), "--out", samples["docx"])
    assert proc.returncode == 2
    assert sha256(samples["docx"]) == before


def test_out_exists_exit_2(samples, tmp_path):
    out = tmp_path / "out.docx"
    out.write_bytes(b"keep")
    proc, _ = apply(samples, tmp_path, [{"op": "replace", "at": "t:1/r:1/c:1", "text": "항목"}])
    assert proc.returncode == 2
    assert out.read_bytes() == b"keep"


# --- 리뷰 회귀: 이중 삭제·세로 병합 ----------------------------------------------------

def test_double_delete_same_paragraph_rejected(samples, tmp_path):
    proc, out = apply(samples, tmp_path, [{"op": "delete", "at": "p:3"}, {"op": "delete", "at": "p:3"}])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()


def test_double_row_delete_rejected(samples, tmp_path):
    proc, out = apply(samples, tmp_path, [{"op": "row_delete", "table": "t:1", "row": 2},
                                          {"op": "row_delete", "table": "t:1", "row": 2}])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()


@pytest.fixture
def merged(tmp_path):
    """표 t:1 4행 2열, 1열의 2~3행이 세로 병합(2행 restart, 3행 continue)."""
    from docx import Document
    doc = Document()
    t = doc.add_table(rows=4, cols=2)
    for r, row in enumerate([["구분", "값"], ["준비", "1"], ["", "2"], ["합계", "3"]]):
        for c, text in enumerate(row):
            t.cell(r, c).text = text
    t.cell(1, 0).merge(t.cell(2, 0))
    path = tmp_path / "merged.docx"
    doc.save(path)
    return path


def apply_to(src, tmp_path, edits):
    e = tmp_path / "edits.yaml"
    e.write_text(yaml.safe_dump(edits, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "merged_out.docx"
    proc = uv(PATCH_DOCX, "apply", src, "--edits", e, "--profile", write_profile(tmp_path), "--out", out)
    return proc, out


@pytest.mark.parametrize("edit", [
    {"op": "row_delete", "table": "t:1", "row": 2},
    {"op": "row_add", "table": "t:1", "like_row": 4, "after": 2, "cells": ["a", "b"]},
])
def test_vmerge_breaking_edits_rejected(merged, tmp_path, edit):
    proc, out = apply_to(merged, tmp_path, [edit])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()


def test_row_add_cloned_from_merged_row_drops_vmerge(merged, tmp_path):
    from docx import Document
    from docx.oxml.ns import qn
    proc, out = apply_to(merged, tmp_path, [
        {"op": "row_add", "table": "t:1", "like_row": 2, "after": 3, "cells": ["시행", "4"]}])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    tr = Document(out).tables[0]._tbl.tr_lst[3]
    assert not list(tr.iter(qn("w:vMerge")))
    assert [c.text for c in Document(out).tables[0].rows[3].cells] == ["시행", "4"]
