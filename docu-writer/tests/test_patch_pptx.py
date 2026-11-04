"""patch_pptx.py 수용 테스트.

계약: skills/format-pptx/SKILL.md 「작성 (⑤) — patch_pptx.py」.
픽스처 도형 id: 슬라이드2 표=4, 슬라이드3 표=3·그룹=4·그룹 안 표=5.
"""
import hashlib
import json

import pytest
import yaml

from conftest import EXPECTED_TABLES, PATCH_PPTX, uv

ALLOWED = ["Title Slide", "Title and Content", "Title Only"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(samples, tmp_path):
    out = tmp_path / "skeleton.yaml"
    proc = uv(PATCH_PPTX, "dump", samples["pptx"], "--out", out)
    assert proc.returncode == 0, proc.stderr
    return {b["at"]: b for b in yaml.safe_load(out.read_text(encoding="utf-8"))}


def apply(samples, tmp_path, edits, allowed=ALLOWED):
    e = tmp_path / "edits.yaml"
    e.write_text(yaml.safe_dump(edits, allow_unicode=True), encoding="utf-8")
    prof = tmp_path / "profile.yaml"
    prof.write_text(yaml.safe_dump({"profile_version": 1, "design": {"styles_allowed": allowed}},
                                   allow_unicode=True), encoding="utf-8")
    out = tmp_path / "out.pptx"
    proc = uv(PATCH_PPTX, "apply", samples["pptx"], "--edits", e, "--profile", prof, "--out", out)
    return proc, out


def ok(proc):
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def prs(path):
    from pptx import Presentation
    return Presentation(path)


def ph(slide, idx):
    return next(s for s in slide.placeholders if s.placeholder_format.idx == idx)


def table(slide, shape_id):
    def walk(shapes):
        for s in shapes:
            if s.shape_id == shape_id:
                return s.table
            if s.shape_type == 6:
                found = walk(s.shapes)
                if found is not None:
                    return found
        return None
    return walk(slide.shapes)


# --- dump ------------------------------------------------------------------------

def test_dump_slides_and_placeholders(samples, tmp_path):
    b = dump(samples, tmp_path)
    assert b["sl:2"]["layout"] == "Title and Content"
    assert b["sl:2/ph:0"]["text"] == "추진 일정"
    assert b["sl:2/ph:1/p:2"]["level"] == 1
    assert b["sl:2/ph:1/p:2"]["text"] == "시행 단계는 2~6월에 운영팀이 맡는다"


def test_dump_table_cells_including_group(samples, tmp_path):
    b = dump(samples, tmp_path)
    assert b["sl:2/sh:4/t/r:3/c:3"]["text"] == "운영팀"
    assert b["sl:3/sh:3/t/r:1/c:1"]["text"] == "항목"
    assert b["sl:3/sh:5/t/r:2/c:2"]["text"] == "끝칸"


def test_dump_table_blocks_match_shared_numbering(samples, tmp_path):
    b = dump(samples, tmp_path)
    tables = sorted((v for v in b.values() if v.get("kind") == "table"), key=lambda v: int(v["table"][2:]))
    want = EXPECTED_TABLES["pptx"]
    assert [t["table"] for t in tables] == [w["at"] for w in want]
    for t, w in zip(tables, want):
        assert t["at"].startswith(f"sl:{w['slide']}/sh:")
        assert (t["rows"], t["cols"]) == (w["rows"], w["cols"])


# --- apply: 성공 -----------------------------------------------------------------

def test_replace_title_paragraph_and_cells(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "replace", "at": "sl:2/ph:0", "text": "일정은 6월에 끝난다"},
        {"op": "replace", "at": "sl:2/ph:1/p:1", "text": "준비는 1월"},
        {"op": "replace", "at": "sl:2/sh:4/t/r:2/c:2", "text": "1~2월"},
        {"op": "replace", "at": "t:3/r:1/c:1", "text": "묶음 표"},
    ])[0])
    s2, s3 = prs(tmp_path / "out.pptx").slides[1], prs(tmp_path / "out.pptx").slides[2]
    assert ph(s2, 0).text_frame.text == "일정은 6월에 끝난다"
    assert ph(s2, 1).text_frame.paragraphs[0].text == "준비는 1월"
    assert table(s2, 4).cell(1, 1).text == "1~2월"
    assert table(s3, 5).cell(0, 0).text == "묶음 표"


def test_insert_after_keeps_level(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "insert_after", "at": "sl:2/ph:1/p:2", "like": "sl:2/ph:1/p:2", "text": "평가는 7월"},
    ])[0])
    paras = ph(prs(tmp_path / "out.pptx").slides[1], 1).text_frame.paragraphs
    assert [p.text for p in paras][-1] == "평가는 7월"
    assert paras[-1].level == 1


def test_slide_dup_and_new_locator(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "slide_dup", "like": "sl:2", "after": "sl:2"},
        {"op": "replace", "at": "new:1/ph:0", "text": "추진 일정 (2)"},
    ])[0])
    slides = list(prs(tmp_path / "out.pptx").slides)
    assert len(slides) == 4
    assert ph(slides[1], 0).text_frame.text == "추진 일정"
    assert ph(slides[2], 0).text_frame.text == "추진 일정 (2)"
    assert slides[2].slide_layout.name == "Title and Content"


def test_slide_delete_and_notes(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "slide_delete", "at": "sl:3"},
        {"op": "notes", "at": "sl:2", "text": "일정은 확정 전"},
    ])[0])
    slides = list(prs(tmp_path / "out.pptx").slides)
    assert len(slides) == 2
    assert slides[1].notes_slide.notes_text_frame.text == "일정은 확정 전"


def test_row_add_on_shape_table(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "row_add", "table": "sl:2/sh:4", "like_row": 2, "after": 3, "cells": ["평가", "7월", "기획팀"]},
    ])[0])
    t = table(prs(tmp_path / "out.pptx").slides[1], 4)
    assert len(t.rows) == 4
    assert [t.cell(3, c).text for c in range(3)] == ["평가", "7월", "기획팀"]


def test_overflow_warning(samples, tmp_path):
    report = ok(apply(samples, tmp_path, [
        {"op": "replace", "at": "sl:2/ph:0", "text": "추진 일정은 준비·시행·평가 세 단계로 나누어 진행한다"},
    ])[0])
    assert any("sl:2/ph:0" in str(w) for w in report["warnings"])


def test_no_overflow_warning_for_empty_placeholder(tmp_path):
    """종단 시험: 양식의 빈 플레이스홀더는 견본 글이 0자라 늘 경고가 났습니다."""
    from pptx import Presentation

    src = tmp_path / "form.pptx"
    p = Presentation()
    p.slides.add_slide(p.slide_layouts[0]).shapes.title.text = "회의실 사용 신청"
    p.save(src)
    edits = tmp_path / "e.yaml"
    edits.write_text('- {op: replace, at: "sl:1/ph:1", text: "2026. 11. 12. 14:00~16:00"}\n', encoding="utf-8")
    prof = tmp_path / "profile.yaml"
    prof.write_text("profile_version: 1\ndesign: {styles_allowed: [Title Slide]}\n", encoding="utf-8")
    proc = uv(PATCH_PPTX, "apply", src, "--edits", edits, "--profile", prof, "--out", tmp_path / "o.pptx")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["warnings"] == []


def test_apply_does_not_modify_sample(samples, tmp_path):
    before = sha256(samples["pptx"])
    apply(samples, tmp_path, [{"op": "replace", "at": "sl:2/ph:0", "text": "일정"}])
    assert sha256(samples["pptx"]) == before


# --- apply: 실패 -----------------------------------------------------------------

@pytest.mark.parametrize("edit", [
    {"op": "replace", "at": "sl:9/ph:0", "text": "x"},
    {"op": "replace", "at": "sl:2/ph:7", "text": "x"},
    {"op": "replace", "at": "sl:2/sh:99/t/r:1/c:1", "text": "x"},
    {"op": "replace", "at": "sl:2/ph:0", "text": "두 줄\n제목"},
    {"op": "replace", "at": "new:1/ph:0", "text": "x"},
    {"op": "slide_dup", "like": "sl:9", "after": "sl:2"},
])
def test_failed_edit_exit_1_no_file(samples, tmp_path, edit):
    proc, out = apply(samples, tmp_path, [{"op": "replace", "at": "sl:3/ph:0", "text": "실적 요약"}, edit])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()
    report = json.loads(proc.stdout)
    assert len(report["failed"]) == 1
    assert {"op", "at", "reason"} <= set(report["failed"][0])


def test_slide_dup_layout_not_allowed(samples, tmp_path):
    proc, out = apply(samples, tmp_path, [{"op": "slide_dup", "like": "sl:3", "after": "sl:3"}],
                      allowed=["Title Slide", "Title and Content"])
    assert proc.returncode == 1
    assert not out.exists()


def test_out_equals_sample_exit_2(samples, tmp_path):
    e = tmp_path / "edits.yaml"
    e.write_text("[]", encoding="utf-8")
    before = sha256(samples["pptx"])
    prof = tmp_path / "profile.yaml"
    prof.write_text("profile_version: 1\n", encoding="utf-8")
    proc = uv(PATCH_PPTX, "apply", samples["pptx"], "--edits", e, "--profile", prof, "--out", samples["pptx"])
    assert proc.returncode == 2
    assert sha256(samples["pptx"]) == before


def test_out_exists_exit_2(samples, tmp_path):
    out = tmp_path / "out.pptx"
    out.write_bytes(b"keep")
    proc, _ = apply(samples, tmp_path, [{"op": "replace", "at": "sl:2/ph:0", "text": "일정"}])
    assert proc.returncode == 2
    assert out.read_bytes() == b"keep"


# --- 리뷰 회귀: 슬라이드 복제·삭제 ----------------------------------------------------

def titles(path):
    return [s.shapes.title.text_frame.text for s in prs(path).slides]


def test_repeated_dup_after_same_slide_keeps_order(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "slide_dup", "like": "sl:2", "after": "sl:2"},
        {"op": "slide_dup", "like": "sl:2", "after": "sl:2"},
        {"op": "replace", "at": "new:1/ph:0", "text": "가"},
        {"op": "replace", "at": "new:2/ph:0", "text": "나"},
    ])[0])
    assert titles(tmp_path / "out.pptx") == ["○○사업 추진계획(안)", "추진 일정", "가", "나", "실적"]


def test_move_slide_by_dup_then_delete(samples, tmp_path):
    ok(apply(samples, tmp_path, [
        {"op": "slide_dup", "like": "sl:3", "after": "sl:1"},
        {"op": "slide_delete", "at": "sl:3"},
    ])[0])
    assert titles(tmp_path / "out.pptx") == ["○○사업 추진계획(안)", "실적", "추진 일정"]


@pytest.mark.parametrize("edits", [
    [{"op": "slide_delete", "at": "sl:1"}, {"op": "slide_delete", "at": "sl:2"},
     {"op": "slide_delete", "at": "sl:3"}],
    [{"op": "slide_delete", "at": "sl:3"}, {"op": "replace", "at": "sl:3/ph:0", "text": "x"}],
    [{"op": "replace", "at": "sl:3/ph:0", "text": "x"}, {"op": "slide_delete", "at": "sl:3"}],
    [{"op": "slide_delete", "at": "sl:2"}, {"op": "row_add", "table": "t:1", "like_row": 2,
                                            "after": 2, "cells": ["a", "b", "c"]}],
    [{"op": "slide_delete", "at": "sl:2"}, {"op": "notes", "at": "sl:2", "text": "x"}],
])
def test_slide_delete_conflicts_rejected(samples, tmp_path, edits):
    proc, out = apply(samples, tmp_path, edits)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not out.exists()
