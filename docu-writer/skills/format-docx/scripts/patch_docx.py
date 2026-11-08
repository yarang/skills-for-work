# /// script
# requires-python = ">=3.13"
# dependencies = ["python-docx", "pyyaml", "lxml"]
# ///
"""DOCX 견본 골격 뽑기(dump)와 편집 목록 적용(apply).

locator는 dump 시점 기준이며, 적용 전에 모두 요소 참조로 풀어 둡니다.
  p:N        w:body 직계 w:p의 N번째 (빈 문단 포함, 1부터)
  t:N        w:body 직계 w:tbl의 N번째 (머리글·바닥글 표, 칸 안쪽 표는 세지 않음)
  t:N/r:R/c:C  R번째 w:tr의 그리드 열 C (gridBefore·gridSpan 반영, 프로파일·doc_verify와 같은 좌표).
               가로 병합 칸은 차지한 열 어디로든 찾고, 세로 병합의 이어짐 칸은 거부합니다.
종료 코드: 0 성공, 1 적용하지 못한 편집이 있음(파일 안 씀), 2 사용법·환경 오류.
"""
import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

import yaml
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

W_P, W_TBL, W_TR, W_TC = qn("w:p"), qn("w:tbl"), qn("w:tr"), qn("w:tc")
W_R, W_T, W_RPR = qn("w:r"), qn("w:t"), qn("w:rPr")
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
MC_ALT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
KIND_MARKERS = (
    ("textbox", (qn("w:txbxContent"),)),
    ("field", (qn("w:fldSimple"), qn("w:fldChar"))),
    ("tracked", (qn("w:ins"), qn("w:del"), MC_ALT)),
)
MEDIA_TAGS = {qn("w:drawing"), qn("w:pict"), qn("w:object")}
RE_P = re.compile(r"^p:(\d+)$")
RE_T = re.compile(r"^t:(\d+)$")
RE_CELL = re.compile(r"^t:(\d+)/r:(\d+)/c:(\d+)$")
OPS = {"replace", "insert_after", "delete", "row_add", "row_delete"}


class UsageError(Exception):
    """사용법·환경 오류 (종료 코드 2)."""


class EditError(Exception):
    """편집 하나가 적용될 수 없는 이유 (종료 코드 1)."""


# --- 문서 구조 읽기 ----------------------------------------------------------------

def para_text(p):
    return "".join(t.text or "" for t in p.iter(W_T))


def para_kind(p):
    for kind, tags in KIND_MARKERS:
        if any(next(p.iter(tag), None) is not None for tag in tags):
            return kind
    return None


def cell_paras(tc):
    return tc.findall(W_P)


def cell_text(tc):
    texts = [para_text(p) for p in cell_paras(tc)]
    return " ".join(t for t in texts if t).strip()


def _int_val(el, default):
    try:
        return max(int(el.get(qn("w:val"))), 0) if el is not None else default
    except (TypeError, ValueError):
        return default


def row_grid(tr):
    """[(시작 그리드 열 1부터, 차지한 열 수, tc), …] — gridBefore·gridSpan 반영."""
    col = _int_val(tr.find(f"{qn('w:trPr')}/{qn('w:gridBefore')}"), 0) + 1
    out = []
    for tc in tr.findall(W_TC):
        width = max(_int_val(tc.find(f"{qn('w:tcPr')}/{qn('w:gridSpan')}"), 1), 1)
        out.append((col, width, tc))
        col += width
    return out


def is_vmerge_continue(tc):
    vm = tc.find(f"{qn('w:tcPr')}/{qn('w:vMerge')}")
    return vm is not None and vm.get(qn("w:val"), "continue") == "continue"


def is_vmerge_restart(tc):
    vm = tc.find(f"{qn('w:tcPr')}/{qn('w:vMerge')}")
    return vm is not None and vm.get(qn("w:val")) == "restart"


def continues_merge(tr):
    """이 행에 세로 병합 이어짐 칸이 있으면 참 — 위 행과 병합으로 묶여 있음."""
    return tr is not None and any(is_vmerge_continue(tc) for tc in tr.findall(W_TC))


def strip_vmerge(tr):
    for vm in list(tr.iter(qn("w:vMerge"))):
        vm.getparent().remove(vm)


def cell_kind(tc):
    return next((k for k in map(para_kind, cell_paras(tc)) if k), None)


def style_name(doc, p):
    return Paragraph(p, doc._body).style.name


def body_index(doc):
    body = doc.element.body
    return list(body.findall(W_P)), list(body.findall(W_TBL))


# --- dump ---------------------------------------------------------------------------

def block(at, style, text, kind):
    out = {"at": at, "style": style, "text": text}
    if kind:
        out.update(kind=kind, editable=False)
    return out


def dump_table(doc, n, tbl):
    blocks = []
    for r, tr in enumerate(tbl.findall(W_TR), 1):
        for c, _, tc in row_grid(tr):
            if is_vmerge_continue(tc):
                continue
            paras = cell_paras(tc)
            style = style_name(doc, paras[0]) if paras else ""
            blocks.append(block(f"t:{n}/r:{r}/c:{c}", style, cell_text(tc), cell_kind(tc)))
    return blocks


def dump_blocks(doc):
    blocks, p_no, t_no = [], 0, 0
    for el in doc.element.body.iterchildren():
        if el.tag == W_P:
            p_no += 1
            blocks.append(block(f"p:{p_no}", style_name(doc, el), para_text(el), para_kind(el)))
        elif el.tag == W_TBL:
            t_no += 1
            blocks.extend(dump_table(doc, t_no, el))
    return blocks


# --- 글 바꾸기 ----------------------------------------------------------------------

def new_run(p):
    run = OxmlElement("w:r")
    p.append(run)
    return run


def write_run_text(run, text):
    for child in list(run):
        if child.tag != W_RPR:
            run.remove(child)
    t = OxmlElement("w:t")
    t.set(XML_SPACE, "preserve")
    t.text = text
    run.append(t)


def drop_runs(p, keep, warnings):
    for run in list(p.iter(W_R)):
        if run is keep:
            continue
        if any(el.tag in MEDIA_TAGS for el in run.iter()):
            warnings.append("그림·개체가 든 run을 지웠습니다")
        run.getparent().remove(run)


def set_para_text(p, text, warnings):
    """첫 run(서식 유지)에 글을 넣고 나머지 run은 지웁니다. run이 없으면 새로 만듭니다."""
    keep = next(iter(p.findall(W_R)), None)
    if keep is None:
        keep = next(p.iter(W_R), None)
    if keep is None:
        keep = new_run(p)
    drop_runs(p, keep, warnings)
    write_run_text(keep, text)


def set_cell_text(tc, text, warnings):
    paras = cell_paras(tc)
    if not paras:
        paras = [tc.makeelement(W_P)]
        tc.append(paras[0])
    set_para_text(paras[0], text, warnings)
    for extra in paras[1:]:
        for run in list(extra.iter(W_R)):
            run.getparent().remove(run)


def strip_bookmarks(el):
    for tag in ("w:bookmarkStart", "w:bookmarkEnd"):
        for node in list(el.iter(qn(tag))):
            node.getparent().remove(node)


# --- locator 풀이 -------------------------------------------------------------------

class Ctx:
    def __init__(self, doc, allowed):
        self.doc = doc
        self.allowed = set(allowed)
        self.paras, self.tables = body_index(doc)
        self.warnings = []
        self.chain = {}
        self.row_deletes = {}
        self.gone = set()            # 지우기로 계획된 문단·행 — 겹친 지우기를 거부

    def para(self, loc):
        m = RE_P.match(loc) if isinstance(loc, str) else None
        if not m or not 1 <= int(m[1]) <= len(self.paras):
            raise EditError(f"문단 locator를 찾을 수 없음: {loc!r}")
        return self.paras[int(m[1]) - 1]

    def table(self, loc):
        m = RE_T.match(loc) if isinstance(loc, str) else None
        if not m or not 1 <= int(m[1]) <= len(self.tables):
            raise EditError(f"표 locator를 찾을 수 없음: {loc!r}")
        return self.tables[int(m[1]) - 1]

    def cell(self, loc):
        m = RE_CELL.match(loc)
        if not m:
            raise EditError(f"locator를 찾을 수 없음: {loc!r}")
        tbl = self.tables[int(m[1]) - 1] if 1 <= int(m[1]) <= len(self.tables) else None
        rows = tbl.findall(W_TR) if tbl is not None else []
        if not 1 <= int(m[2]) <= len(rows):
            raise EditError(f"locator를 찾을 수 없음: {loc!r}")
        col = int(m[3])
        tc = next((tc for start, width, tc in row_grid(rows[int(m[2]) - 1])
                   if start <= col < start + width), None)
        if tc is None:
            raise EditError(f"locator를 찾을 수 없음: {loc!r}")
        if is_vmerge_continue(tc):
            raise EditError(f"세로 병합의 이어짐 칸: {loc!r} — 병합이 시작되는 행의 locator를 쓰십시오")
        return tc

    def row(self, tbl, n, field):
        rows = tbl.findall(W_TR)
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(rows):
            raise EditError(f"{field}가 범위 밖: {n!r} (행 {len(rows)}개)")
        return rows[n - 1]

    def insert_after(self, anchor, new):
        self.chain.get(anchor, anchor).addnext(new)
        self.chain[anchor] = new


def need_text(e):
    text = e.get("text")
    if not isinstance(text, str):
        raise EditError("text가 문자열이 아님")
    if "\n" in text or "\r" in text:
        raise EditError("text에 줄바꿈이 있음 (문단을 늘리려면 insert_after)")
    return text


def need_editable(kind, loc):
    if kind:
        raise EditError(f"편집 불가 개체({kind}): {loc}")


# --- 편집 종류별 풀이: 각각 (지금 적용할 함수, 마지막에 미룰지) 를 돌려줌 -------------------

def plan_replace(ctx, e):
    text, loc = need_text(e), e.get("at")
    if isinstance(loc, str) and RE_CELL.match(loc):
        tc = ctx.cell(loc)
        need_editable(cell_kind(tc), loc)
        return (lambda: set_cell_text(tc, text, ctx.warnings)), False
    p = ctx.para(loc)
    need_editable(para_kind(p), loc)
    return (lambda: set_para_text(p, text, ctx.warnings)), False


def plan_insert_after(ctx, e):
    text = need_text(e)
    anchor, like = ctx.para(e.get("at")), ctx.para(e.get("like"))
    need_editable(para_kind(like), e["like"])
    name = style_name(ctx.doc, like)
    if ctx.allowed and name not in ctx.allowed:
        raise EditError(f"스타일 '{name}'이 styles_allowed 밖")
    clone = copy.deepcopy(like)
    strip_bookmarks(clone)
    for sect in list(clone.iter(qn("w:sectPr"))):
        sect.getparent().remove(sect)
    set_para_text(clone, text, ctx.warnings)
    return (lambda: ctx.insert_after(anchor, clone)), False


def plan_delete(ctx, e):
    p = ctx.para(e.get("at"))
    if next(p.iter(qn("w:sectPr")), None) is not None:
        raise EditError("구역 나눔이 든 문단은 지울 수 없음")
    if p in ctx.gone:
        raise EditError(f"이미 지우기로 한 문단: {e.get('at')}")
    ctx.gone.add(p)
    return (lambda: p.getparent().remove(p)), True


def plan_row_add(ctx, e):
    tbl = ctx.table(e.get("table"))
    like = ctx.row(tbl, e.get("like_row"), "like_row")
    anchor = ctx.row(tbl, e.get("after"), "after")
    cells = e.get("cells")
    if not isinstance(cells, list) or not all(isinstance(c, str) for c in cells):
        raise EditError("cells가 문자열 목록이 아님")
    if any("\n" in c or "\r" in c for c in cells):
        raise EditError("cells에 줄바꿈이 있음")
    if continues_merge(anchor.getnext()):
        raise EditError(f"행 {e.get('after')} 뒤는 세로 병합 중간이라 행을 넣을 수 없음")
    clone = copy.deepcopy(like)
    strip_bookmarks(clone)
    # 견본 행의 세로 병합 표시를 그대로 두면 새 칸 글이 위 칸에 묻히거나 아래 행을 끌어들입니다.
    strip_vmerge(clone)
    fill_row(ctx, clone, cells)
    return (lambda: ctx.insert_after(anchor, clone)), False


def fill_row(ctx, tr, cells):
    tcs = tr.findall(W_TC)
    if len(cells) > len(tcs):
        raise EditError(f"cells {len(cells)}개가 칸 {len(tcs)}개보다 많음")
    if len(cells) < len(tcs):
        ctx.warnings.append(f"cells {len(cells)}개 < 칸 {len(tcs)}개: 나머지 칸은 비움")
    for i, tc in enumerate(tcs):
        for nested in tc.findall(W_TBL):
            tc.remove(nested)
        set_cell_text(tc, cells[i] if i < len(cells) else "", ctx.warnings)
        # 새 행은 한 칸 한 문단으로 둡니다. 견본 행(병합 시작 칸 등)의 빈 문단이 남으면 행이 높아집니다.
        for extra in cell_paras(tc)[1:]:
            tc.remove(extra)


def plan_row_delete(ctx, e):
    tbl = ctx.table(e.get("table"))
    tr = ctx.row(tbl, e.get("row"), "row")
    if tr in ctx.gone:
        raise EditError(f"이미 지우기로 한 행: {e.get('row')}")
    if any(is_vmerge_restart(tc) for tc in tr.findall(W_TC)) and continues_merge(tr.getnext()):
        raise EditError(f"행 {e.get('row')}은 세로 병합이 시작되는 행이라 지울 수 없음 (이어진 행이 고아가 됨)")
    done = ctx.row_deletes.setdefault(tbl, set())
    done.add(tr)
    ctx.gone.add(tr)
    if len(done) >= len(tbl.findall(W_TR)):
        raise EditError("표의 모든 행을 지울 수 없음")
    return (lambda: tr.getparent().remove(tr)), True


PLANNERS = {
    "replace": plan_replace, "insert_after": plan_insert_after, "delete": plan_delete,
    "row_add": plan_row_add, "row_delete": plan_row_delete,
}


def build_plan(ctx, edits):
    """모든 편집을 원본 기준으로 풀어 (실행 목록, 실패 목록)을 돌려줍니다. 문서는 바꾸지 않습니다."""
    now, last, failed = [], [], []
    for e in edits:
        op = e.get("op") if isinstance(e, dict) else None
        at = e.get("at", e.get("table")) if isinstance(e, dict) else None
        try:
            if op not in OPS:
                raise EditError(f"알 수 없는 op: {op!r}")
            fn, defer = PLANNERS[op](ctx, e)
            (last if defer else now).append(fn)
        except EditError as exc:
            failed.append({"op": op, "at": at, "reason": str(exc)})
    return now + last, failed


# --- 명령 ---------------------------------------------------------------------------

def yaml_error_brief(exc: Exception) -> str:
    """YAML 읽기 오류를 원문 없이 — PyYAML 메시지는 틀린 줄을 그대로 보여 주므로(개인정보·비밀값)
    종류와 위치만 남깁니다(리뷰 3차 M9). 파일 오류(OSError)는 경로만 담으므로 그대로 둡니다."""
    if isinstance(exc, OSError):
        return str(exc)
    if isinstance(exc, UnicodeDecodeError):
        return f"UTF-8로 읽을 수 없음 ({exc.start}번째 바이트)"
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is not None:
        return f"{type(exc).__name__} ({mark.line + 1}행 {mark.column + 1}열)"
    position = getattr(exc, "position", None)
    if position is not None:
        return f"{type(exc).__name__} ({position}번째 글자)"
    return type(exc).__name__


def load_yaml(path, what):
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise UsageError(f"{what}을 읽을 수 없음: {path} ({yaml_error_brief(exc)})") from exc


def open_sample(path):
    if not Path(path).is_file():
        raise UsageError(f"견본 파일이 없음: {path}")
    try:
        return Document(path)
    except Exception as exc:  # python-docx가 내는 오류 종류가 여러 가지
        raise UsageError(f"DOCX를 열 수 없음: {path} ({exc})") from exc


def check_out(sample, out):
    same = os.path.realpath(sample) == os.path.realpath(out)
    if not same and os.path.exists(out) and os.path.exists(sample):
        same = os.path.samefile(sample, out)
    if same:
        raise UsageError("--out이 견본과 같은 파일")
    if os.path.lexists(out):
        raise UsageError(f"--out이 이미 있음: {out}")
    Path(out).resolve().parent.mkdir(parents=True, exist_ok=True)


def cmd_dump(args):
    check_out(args.sample, args.out)
    doc = open_sample(args.sample)
    text = yaml.safe_dump(dump_blocks(doc), allow_unicode=True, sort_keys=False)
    with open(args.out, "x", encoding="utf-8") as fh:
        fh.write(text)
    return 0


def cmd_apply(args):
    check_out(args.sample, args.out)
    doc = open_sample(args.sample)
    edits = load_yaml(args.edits, "edits") or []
    if not isinstance(edits, list):
        raise UsageError("edits.yaml은 편집 항목의 목록이어야 함")
    profile = load_yaml(args.profile, "profile") or {}
    allowed = ((profile.get("design") or {}).get("styles_allowed") or []) if isinstance(profile, dict) else []
    ctx = Ctx(doc, allowed)
    steps, failed = build_plan(ctx, edits)
    if not failed:
        for step in steps:
            step()
        save(doc, args.out)
    report = {"applied": 0 if failed else len(steps), "failed": failed, "warnings": ctx.warnings}
    print(json.dumps(report, ensure_ascii=False))
    return 1 if failed else 0


def save(doc, out):
    """배타적으로 만든 출력에만 쓰고, 실패하면 그 파일을 지웁니다 (종료 코드 2)."""
    try:
        fh = open(out, "xb")
    except OSError as exc:
        raise UsageError(f"출력 파일을 만들 수 없음: {out} ({exc})") from exc
    try:
        with fh:
            doc.save(fh)
    except Exception as exc:  # noqa: BLE001 - 부분 파일을 남기지 않음
        Path(out).unlink(missing_ok=True)
        raise UsageError(f"출력 파일을 쓰지 못함: {out} ({exc})") from exc
    except BaseException:  # Ctrl-C 등에서도 부분 파일을 남기지 않음
        Path(out).unlink(missing_ok=True)
        raise


def make_parser():
    parser = argparse.ArgumentParser(description="DOCX 견본 dump / apply")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="견본 골격을 locator가 붙은 YAML로 뽑기")
    d.add_argument("sample")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_dump)
    a = sub.add_parser("apply", help="edits.yaml을 견본 복사본에 적용")
    a.add_argument("sample")
    a.add_argument("--edits", required=True)
    a.add_argument("--profile", required=True)
    a.add_argument("--out", required=True)
    a.set_defaults(func=cmd_apply)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UsageError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
