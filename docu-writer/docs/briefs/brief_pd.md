Implement skills/format-docx/scripts/patch_docx.py in this repository (cwd = docu-writer plugin root).

Contract — read fully, do NOT edit: skills/format-docx/SKILL.md section "작성 (⑤) — patch_docx.py" (dump, edits.yaml, apply, exit codes, stdout JSON). Locator grammar and counting rules: docs/design.md §5.

Acceptance tests (do NOT edit tests/): tests/test_patch_docx.py, fixtures in tests/conftest.py. Run:
  uv run --python 3.13 --with pytest,pyyaml,python-docx pytest tests/test_patch_docx.py -q

Requirements:
- PEP 723 inline metadata: requires-python ">=3.13", dependencies python-docx, pyyaml, lxml. Invoked as `uv run --python 3.13 patch_docx.py ...`.
- Subcommands: `dump <sample.docx> --out <skeleton.yaml>` and `apply <sample.docx> --edits <edits.yaml> --profile <profile.yaml> --out <out.docx>`.
- Exit codes: 0 ok; 1 apply had failed edits (then write NO output file); 2 usage/env error, missing file, --out already exists, or --out resolves to the same file as the sample (compare realpath and os.path.samefile when both exist). argparse errors exit 2. Never modify the sample: load it, edit in memory, save only to --out.
- Locators (must agree with profile_extract.py in template/skills/template-analysis/scripts/): p:N = 1-based index among DIRECT w:p children of w:body (empty paragraphs count). t:N = 1-based index among DIRECT w:tbl children of w:body (header/footer tables and tables nested inside cells are not numbered). Cell = t:N/r:R/c:C, 1-based, by w:tr / w:tc order in the XML (do not use python-docx merged-cell expansion).
- dump output: a YAML list (allow_unicode, sort_keys=False) in body order. Paragraph block {at, style, text}. For a table, one block per cell {at: "t:N/r:R/c:C", style, text}; cell text = the cell's DIRECT w:p paragraphs joined with "\n"? NO — join with " " and strip; exclude text of tables nested in the cell. Paragraphs containing w:txbxContent, w:fldSimple/w:fldChar, w:ins/w:del, or mc:AlternateContent get kind: textbox|field|tracked and editable: false. Nested tables inside cells: emit nothing for them.
- edits.yaml: a YAML list of edit dicts. Ops: replace{at,text} (paragraph or cell; for a cell edit the cell's first direct paragraph and remove the cell's other direct paragraphs' text runs), insert_after{at,like,text} (deepcopy the `like` paragraph element, set its text, insert after the `at` paragraph), delete{at}, row_add{table,like_row,after,cells} (deepcopy row like_row, set each cell's text, insert after row `after`), row_delete{table,row}.
- Setting text: keep the first w:r (its w:rPr) and put the text in it; remove the other runs' w:t content (remove the other w:r elements). If the paragraph has no run, add one.
- Validation BEFORE mutating anything: resolve every locator against the original document (all locators are dump-time); collect failures: unknown op, missing fields, locator not found, row out of range, "\n" in text, target editable: false, `like` paragraph style name not in profile design.styles_allowed (if profile has a non-empty styles_allowed). If any failure → print JSON and exit 1 without writing.
- Then apply edits using element references resolved up front (so insertions/deletions don't shift later edits).
- stdout: exactly one JSON object {"applied": N, "failed": [{"op","at","reason"}], "warnings": [...]}, ensure_ascii=False. For row ops, "at" = the table locator.
- Functions < 50 lines, file < 800 lines, no debug prints.

Only create files under skills/format-docx/scripts/. Run the tests until they pass and report results.
