Implement skills/format-pptx/scripts/patch_pptx.py in this repository (cwd = docu-writer plugin root).

Contract — read fully, do NOT edit: skills/format-pptx/SKILL.md section "작성 (⑤) — patch_pptx.py" (dump example, op table, locator bullets, apply). Exit codes and stdout JSON are the same as skills/format-docx/SKILL.md "3) 적용". Locator grammar: docs/design.md §5.

Acceptance tests (do NOT edit tests/): tests/test_patch_pptx.py, fixtures in tests/conftest.py (build_pptx). Run:
  uv run --python 3.13 --with pytest,pyyaml,python-pptx pytest tests/test_patch_pptx.py -q

Requirements:
- PEP 723 inline metadata: requires-python ">=3.13", dependencies python-pptx, pyyaml, lxml. Invoked as `uv run --python 3.13 patch_pptx.py ...`.
- Subcommands: `dump <sample.pptx> --out <skeleton.yaml>`, `apply <sample.pptx> --edits <edits.yaml> --profile <profile.yaml> --out <out.pptx>`.
- Exit codes: 0 ok; 1 failed edits (write NO output file); 2 usage/env error, missing file, --out exists, or --out is the same file as the sample (realpath / os.path.samefile). argparse errors exit 2. Never modify the sample.
- Locators: sl:N = 1-based slide order. ph:N = placeholder_format.idx. sh:N = shape_id (p:cNvPr@id), searched recursively including inside group shapes. Paragraph inside a text shape: <shape>/p:K (1-based). Table cell: <slide>/sh:N/t/r:R/c:C (1-based). Alias t:N/r:R/c:C where t:N = document-wide table number: slides in order, shapes in shape-tree order, recursing into groups (must match profile_extract.py tables output: tests EXPECTED_TABLES["pptx"]). A bare placeholder locator (sl:2/ph:0) means the whole text frame.
- dump: YAML list (allow_unicode, sort_keys=False) in order. Per slide {at: "sl:N", layout: <layout name>}. Per placeholder {at: "sl:N/ph:I", kind: title|body|other, text}; per paragraph of multi-paragraph text frames {at: ".../p:K", level, text}. Non-placeholder text shapes use sh:N the same way. Per table {at: "sl:N/sh:S", kind: table, table: "t:N", rows, cols} followed by each cell {at: "sl:N/sh:S/t/r:R/c:C", text}. Charts, SmartArt (graphicFrame with dgm uri), media → {at, kind: chart|smartart|media, editable: false}.
- edits.yaml: YAML list. Ops: replace{at,text}, insert_after{at,like,text} (deepcopy like a:p incl. a:pPr level), delete{at}, slide_dup{like,after} (duplicate slide like: new slide with same layout, deepcopy the spTree children and relationships needed for pictures; move it right after `after`; it gets name new:1, new:2… in order of slide_dup edits; later edits may target new:K/...), slide_delete{at} (drop the sldId and the rel), row_add{table,like_row,after,cells} and row_delete{table,row} where table is "sl:N/sh:S" or "t:N", notes{at: sl:N, text} (create the notes slide if missing).
- Setting text keeps the first a:r (and its a:rPr) and removes other runs; for a whole-frame replace keep the first paragraph and remove the others.
- Validate everything BEFORE mutating: unknown op, missing fields, locator not found (including new:K not created by an earlier slide_dup in the file), row out of range, "\n" in text, editable:false target, slide_dup `like` slide layout name not in profile design.styles_allowed (when that list is non-empty). Any failure → stdout JSON, exit 1, no file. Resolve all sl:/ph:/sh: locators to element references up front so slide_dup/slide_delete/insert don't shift later edits.
- warnings: for each replace whose new text length > 1.3 × the original text length at that locator, add a string containing the locator, e.g. "overflow? sl:2/ph:0: 28 chars vs 5".
- stdout: one JSON object {"applied","failed":[{"op","at","reason"}],"warnings"}, ensure_ascii=False. For row ops "at" = table locator; for slide_dup "at" = like.
- Functions < 50 lines, file < 800 lines (split helpers into sibling _pp_<topic>.py modules if needed), no debug prints.

Only create files under skills/format-pptx/scripts/. Run the tests until they pass and report results.
