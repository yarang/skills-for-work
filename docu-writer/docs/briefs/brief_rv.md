Implement two scripts in this repository (cwd = docu-writer plugin root):
  skills/doc-verify/scripts/render.py
  skills/doc-verify/scripts/doc_verify.py

Contract — read fully, do NOT edit: skills/doc-verify/SKILL.md (sections 실행, 렌더, 검사 항목, 검사 세부, 입력 파일, 출력).
Profile schema and locator grammar: docs/design.md §5 (profile.yaml block, locator 문법, t:N / p:N counting rules).
Shared table numbering and first/last cell rule: template/skills/template-analysis/SKILL.md 「locator와 anchor」 and tests/conftest.py EXPECTED_TABLES.

Acceptance tests (do NOT edit tests):
  tests/test_render.py      (needs soffice + pandoc, both in /opt/homebrew/bin)
  tests/test_doc_verify.py
Run: uv run --python 3.13 --with pytest,python-docx,python-pptx,pyyaml,lxml,pymupdf pytest tests/test_render.py tests/test_doc_verify.py -q

Requirements:
- Each script starts with a PEP 723 block: requires-python = ">=3.13", dependencies from {pymupdf, python-docx, python-pptx, pyyaml, lxml} as needed. Run as `uv run <script>`.
- render.py <input> <out-dir>: DOCX/PPTX via `soffice --headless --convert-to pdf --outdir <tmp>`; MD via `pandoc -o <tmp>.docx` then the same. HWPX, missing file, other extensions -> exit 2. Ghostscript is NOT installed: rasterize with pymupdf at 150 dpi. Before writing, delete only page_* files and pages.json directly in <out-dir>; never touch subdirectories or other files. Never modify the input.
- doc_verify.py: argparse with --profile --source --expect-sha256 --output [--placeholders] [--pages-dir] --out-dir. Exit 0 / 1 / 2 exactly as the SKILL.md table. report.json is a JSON list of 12 entries in the 검사 항목 table order, each {id, status, detail, locations}. Print the 「### 문서 검증」 summary to stdout.
- Format readers: DOCX python-docx (body top-level paragraphs and top-level tables in body order; nested-table text not counted as the outer cell text; header/footer ignored). PPTX python-pptx (recurse group shapes). MD raw text (pipe tables outside fenced code). HWPX zip Contents/section*.xml with lxml.
- Pages text: pages.json if present, else page_NNN.svg <text> elements, else no render.
- Keep functions under 50 lines and files under 800 lines; split helpers into a sibling module (e.g. skills/doc-verify/scripts/_readers.py) if needed and import it via sys.path of the script dir.
- No print debugging left behind. Do not edit SKILL.md, docs, or tests. If a test seems to contradict SKILL.md, stop and report it instead of changing either.
Finish by running the test command above and pasting the final pytest summary line.
