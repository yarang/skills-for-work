Implement template/skills/template-analysis/scripts/profile_extract.py in this repository (cwd = docu-writer plugin root).

Contract — read fully, do NOT edit these documents:
- template/skills/template-analysis/SKILL.md: sections "profile_extract.py 계약", "tables 출력", "profile 출력이 채우는 것", "locator와 anchor", "견본 문구 지문 (sample_text)", "프로파일 점검".
- docs/design.md §5 (profile schema, locator grammar, how t:N and p:N are counted).
- skills/format-pptx/SKILL.md: `ph:N` = placeholder idx, `sh:N` = shape id (p:cNvPr@id).

Acceptance tests (do NOT edit tests/): tests/test_profile_extract.py with fixtures in tests/conftest.py. Run:
  uv run --python 3.13 --with pytest,pyyaml,python-docx,python-pptx pytest tests/test_profile_extract.py -q

Requirements:
- PEP 723 inline script metadata at top: requires-python ">=3.13", dependencies python-docx, python-pptx, pyyaml, lxml. Invoked as `uv run --python 3.13 profile_extract.py ...`.
- argparse subcommands: `tables <sample>`, `profile <sample> --mode sample|form|update --out <path>`, `check <profile> --source <sample> [--tables <tables.yaml>]`.
- Exit codes: 0 ok; 1 check found failures; 2 usage error / unsupported format / missing file / --out exists (never overwrite; write nothing on error). argparse errors must also exit 2 (argparse default is 2 — keep it).
- Never modify the sample. Read HWPX directly from the zip (Contents/section*.xml in numeric order) with lxml; DOCX via python-docx + its lxml element tree; PPTX via python-pptx; MD from text.
- Table counting (t:N): top-level tables only, in document order. HWPX: hp:tbl elements with no hp:tbl ancestor (namespace http://www.hancom.co.kr/hwpml/2011/paragraph), skip tables under header/footer controls (hp:header, hp:footer). DOCX: direct w:tbl children of w:body (document.tables). PPTX: slide order, then shape-tree order, including tables inside group shapes (recurse groups). MD: pipe tables outside fenced code blocks; separator row (---) is not a row.
- Table entry: at, slide (PPTX only), rows, cols, first, last, nested (count of tables inside it). first = first row first cell text; last = last row last cell text, falling back to the last non-empty cell of that row; if the whole row is empty, "" plus a warning. Cell text = the cell's own paragraphs joined with a space, whitespace collapsed, stripped, truncated to 40 chars; text of nested tables inside the cell is NOT included. HWPX cell = hp:tc; DOCX use only direct paragraphs of the cell (exclude nested table text); rows/cols from the actual grid (HWPX rowCnt/colCnt attributes).
- p:N counting (DOCX): direct w:p children of w:body only, 1-based, empty paragraphs included.
- profile: fill per the "profile 출력이 채우는 것" table. sections: DOCX = paragraphs whose style is a heading style ("Heading N" → level N, "Title" → level 0) with anchor p:N; PPTX = one section per slide, anchor sl:N, title = title placeholder text (or "" + warning); MD = each # heading, level = number of #, anchor h:"<text>" (add #2 suffix for duplicate titles). Leave voice/kind/required/guide/length/update/conflicts out or empty (script does not fill them). design.styles_allowed = styles actually used in body paragraphs/runs (DOCX) or layout names actually used (PPTX). sample_text_candidates = body text excluding heading-style paragraphs, table header rows (first row), text shorter than 6 chars, and ○○-only tokens; long sentences may be cut to the first 40 chars. Empty values + reason in top-level `warnings`.
- check: implement every bullet under "check가 보는 것". Resolve anchors: p:N must exist (DOCX), sl:N must exist (PPTX), h:"…" must match some paragraph/heading text after removing ALL whitespace on both sides (HWPX: per hp:p, text of hp:t directly in that paragraph's runs, table-cell paragraphs count as their own paragraphs; MD: # heading lines). Anchors must be in document order. Every t:N/r:R/c:C anywhere in the profile (fields[].locator, sections) must be in range of the tables list (from --tables if given, else compute it). Print a readable list of failures to stdout; exit 1 if any.
- Output YAML with allow_unicode=True, sort_keys=False.
- Keep functions under 50 lines, file under 800 lines; if needed split helpers into sibling modules in the same scripts/ dir named _pe_<topic>.py (sibling import works because the script dir is on sys.path). No debug prints.

Only create files under template/skills/template-analysis/scripts/. Run the tests until they pass and report results.
