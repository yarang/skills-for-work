Implement stage-2 "new document" support (N2–N6) in this repository (cwd = docu-writer plugin root).

Work **tests first**: for each part write the listed acceptance tests, run them and see them fail (RED), then implement until they pass (GREEN). Do not weaken a test to make it pass. Existing tests must keep passing; do NOT edit existing test files except where a part below says "add to".

Contract — read fully, do NOT edit:
- docs/design.md §9 (9.1–9.7) and §11 risk 7
- newdoc/skills/newdoc-workflow/SKILL.md (① step 7 snippet, route table, 「경로 B — 동봉 프로파일」, ⑤ route table)
- skills/doc-verify/SKILL.md 「### 신규 모드 (`mode: new`)」
- template/skills/template-analysis/SKILL.md 「## 프로파일 점검」 incl. 「신규 모드」 block
- template/skills/template-workflow/SKILL.md 「## 견본 보호」 role table (planner row)
- skills/format-docx/SKILL.md 「신규 작성」

Run all tests:
  uv run --with pytest --with python-docx --with python-pptx --with pymupdf pytest -q -p no:cacheprovider

Common requirements (all scripts):
- PEP 723 header, `requires-python = ">=3.13"`, dependencies declared there (pyyaml where YAML is read).
- argparse; exit codes 0 = ok, 1 = check failed / no match problems found, 2 = usage error, YAML syntax error, missing file. argparse errors must exit 2.
- Never overwrite an existing output file (exit 2). On any error write nothing.
- Functions < 50 lines, files < 800 lines; split helpers into sibling `_x.py` modules. No debug prints. Messages to stderr in Korean.

---

## N2 — newdoc/skills/newdoc-workflow/scripts/catalog.py

Subcommands:
- `match --type <종류> --format <md|docx|hwpx> --out <route.json>`
- `list [--format <형식>]` — prints merged themes and fixed entries (one per line, human readable; source = plugin|user).
- `check [<catalog.yaml>]` — validates a catalog (default: both catalogs); exit 1 with a reason per bad entry.

Catalog loading:
- Plugin catalog = `<this file>/../../../templates/catalog.yaml` resolved from `__file__` (i.e. `newdoc/templates/catalog.yaml`). Do NOT use CLAUDE_SKILL_DIR.
- User catalog = `$DOCU_WRITER_TEMPLATES/catalog.yaml` if the env var is set, else `~/.config/docu-writer/templates/catalog.yaml`. Missing user catalog = empty (not an error). Missing plugin catalog = exit 2. Set-but-missing `$DOCU_WRITER_TEMPLATES` dir = exit 2.
- Merge: themes keyed by `<format>/<name>`, fixed keyed by `id`; user entry replaces plugin entry with the same key.
- Relative paths in an entry resolve against the folder of the catalog.yaml that defined it; output paths are `os.path.realpath`.
- `catalog_version` must be 1 (else exit 2).

Matching (`match`):
- Normalize type: remove all whitespace. A fixed entry matches if its `format` equals `--format` and any normalized `doc_type` item equals the normalized type exactly (no fuzzy/prefix matching). Several matches → user before plugin, then catalog order; take the first.
- Else theme: use `themes.<format>.default` (if present and non-empty).
  - docx: `reference_doc` (+ `tokens`) → route theme.
  - hwpx: exactly one of `preset_map` / `template_path` / `pack_path`. With `preset_map`: type found (normalized key) → route theme with `preset`; not found → route none. With `template_path`/`pack_path` → route theme.
- `md` → always none (unless a fixed entry matched).
- No theme → none.
- route.json (UTF-8, `ensure_ascii=False`): `{"route": "fixed|theme|none", "format": ..., "doc_type": <as given>, "theme": "<format>/<name>" | null, "catalog_id": <id> | null, "file": ..., "profile": ..., "reference_doc": ..., "tokens": ..., "preset": ..., "template_path": ..., "pack_path": ..., "catalog_source": "plugin|user" | null}` — keys not applicable are null.
- stdout: the realpaths that must be protected, one per line, nothing else: fixed → `file` and `profile` (if any); docx theme → `reference_doc` and `tokens`; hwpx theme → `template_path` or `pack_path` (preset prints nothing); none → nothing.
- Every referenced file of the chosen entry must exist; a missing file → exit 2 (message names entry and path).

`check` rejects (exit 1): hwpx theme with zero or more than one of preset_map/template_path/pack_path; fixed entry without id/doc_type(list of non-empty strings)/format/file; format not in md|docx|hwpx; duplicate id within one catalog; docx theme without reference_doc; referenced file missing.

Acceptance tests — create tests/test_catalog.py (use tmp_path catalogs; point the plugin catalog at a temp copy by running a temp copy of the script, or add a hidden `--plugin-catalog` option used only by tests — document it in --help as for tests):
1. docx theme match → route theme, stdout = realpaths of reference_doc and tokens, route.json fields correct.
2. hwpx preset_map: 「보고서」 → theme + preset; 「 보 고 서 」 (spaces) → same; 「보고」 → none.
3. hwpx theme with both preset_map and template_path → `check` exit 1; `match` exit 2.
4. md → none, empty stdout.
5. fixed match beats theme; user fixed with same id replaces plugin fixed; user theme `docx/default` replaces plugin one.
6. Relative path in user catalog resolves against the user catalog folder (not cwd).
7. Missing referenced file → exit 2 and route.json not written.
8. Existing `--out` → exit 2, file unchanged.
9. YAML syntax error → exit 2; `catalog_version: 2` → exit 2.
10. `DOCU_WRITER_TEMPLATES` unset and no ~/.config catalog → plugin only (monkeypatch HOME to tmp_path).

## N3 — default theme and catalog

Create:
- `newdoc/templates/catalog.yaml`:
  ```yaml
  catalog_version: 1
  themes:
    docx:
      default: { reference_doc: themes/docx/default.docx, tokens: themes/docx/default.tokens.yaml }
    hwpx:
      default: { preset_map: { 보고서: 보고서, 계획서: 계획서, 기안문: 기안문, 회의록: 회의록, 보도자료: 보도자료 } }
    md: {}
  fixed: []
  ```
  Before writing preset_map, check which preset names kordoc `generate_document` accepts (its tool schema / docs); keep only names it accepts and report any you dropped.
- `newdoc/templates/themes/docx/default.docx`: start from `pandoc -o default.docx --print-default-data-file reference.docx`, then with python-docx set: A4 (210×297 mm), margins 20 mm top/bottom, 20 mm left/right; Korean fonts — body style `Normal`/`Body Text` 「맑은 고딕」 10.5 pt (eastAsia + ascii + hAnsi), headings `Heading 1..3` 「맑은 고딕」 bold 16/13/11 pt. Keep pandoc's style names. Put the generating script in `newdoc/templates/themes/docx/build_default.py` (PEP 723) so the theme is reproducible.
- `newdoc/templates/themes/docx/default.tokens.yaml`: same shape as the profile `design` block in design.md §5 (`page: {size: A4, orientation: portrait, margins_mm: [top, bottom, left, right]}`, `type.body`/`type.h1..h3` = `{font, pt, bold?}`, `color: {}` left empty, `styles_allowed` = style names a pandoc-converted document uses: Normal, Body Text, First Paragraph, Compact, Heading 1–3, Title, Table, Source Code etc. — list exactly what you include).

Acceptance tests — add tests/test_theme_default.py:
1. Re-extract tokens from default.docx with python-docx and compare to default.tokens.yaml (drift → fail).
2. `catalog.py check` on the plugin catalog → exit 0.
3. If `pandoc` is on PATH (else skip): convert a small Markdown with `--reference-doc default.docx`, open with python-docx, assert every paragraph style used is in `styles_allowed` and section page size is A4.

## N4 — doc_verify.py new mode (skills/doc-verify/scripts/)

Implement exactly the doc-verify SKILL 「신규 모드」 block:
- `--source` and `--expect-sha256` become optional at argparse level; validate after loading the profile: profile `mode: new` → both absent OK, exactly one given → exit 2; other modes → both required (exit 2 if missing, same message style as today).
- In new mode: `hash`, `residue`, `scope`, `fields` → status `skip`, detail contains 「신규 모드」.
- `markup`: no sample-based exception (check all markers).
- `h:` anchors: locate a section in the OUTPUT document by a paragraph whose text, with all whitespace removed and a leading chapter number stripped (`Ⅰ.`–`Ⅹ.`, `1.`, `1)`, `가.`, `가)` and the same without the dot, followed by optional spaces), equals the anchor text with whitespace removed. Sections not found → their `length` sub-check `skip` with the section id in detail.
- Empty tokens: empty `design.type.*`, `design.color`, `styles_allowed` → that item is not compared; if nothing at all is comparable `r4_headings`/`r5_tokens` → `skip`.
- Exit-code contract and the 13 report ids unchanged.

Acceptance tests — add to tests/test_doc_verify.py (new test functions only; fixtures under tests/fixtures/new/):
1. new-mode DOCX profile + output without --source → exit 0, hash/residue/scope/fields = skip.
2. new mode with only --source → exit 2. sample mode without --source → exit 2.
3. heading 「Ⅰ. 추진 배경」 in output matches anchor `h:"추진배경"`; 「1) 현황」 matches `h:"현황"`.
4. Missing section → length sub-check skip, overall not fail for that reason.
5. Leftover marker 「○○」 not in placeholders.yaml → markup fail (no sample exception).
6. Profile with empty design.type → r5_tokens skip.

## N5 — _pe_check.py `mode: new` (template/skills/template-analysis/scripts/)

Implement the template-analysis SKILL 「신규 모드」 block:
- `MODES` += `"new"`.
- `profile_extract.py check <profile>`: `mode: new` with `--source` or `--tables` → exit 2; other modes without `--source` → exit 2.
- new mode checks: no `source` key; sections keep the key check; every anchor matches `h:"…"` with non-empty text, no duplicate anchors between sections; any `t:N` locator → fail; `sample_text` must be `[]`; `fields` and `update` absent; `design.route` present with `tool` in pandoc|generate_document|copy; pandoc allows only `reference_doc`; generate_document allows at most one of `preset`(+optional `gate` bool)/`template_path`/`pack_path`; copy allows no other key; every path value absolute and existing.
- Other modes unchanged.

Acceptance tests — add to tests/test_profile_extract.py (new functions; fixture profiles under tests/fixtures/new/):
1. valid new-mode profile per route form (pandoc+reference_doc, generate_document+preset+gate, generate_document+template_path, generate_document bare, copy) → exit 0.
2. each violation above → exit 1 with the reason in output (one test per rule, parametrize ok).
3. new mode + --source → exit 2; sample mode without --source → exit 2.

## N6 — hooks/write_guard.py planner role

- Role `planner` behaves exactly like `analyst` (same allow/deny, same reason text with the role name).
Acceptance tests — add to tests/test_write_guard.py: parametrize the existing analyst cases over `["analyst", "planner"]` (or add mirrored planner cases). Do not change any other existing assertion.

---

Only create/modify files under: newdoc/, skills/doc-verify/scripts/, template/skills/template-analysis/scripts/, hooks/write_guard.py, tests/. Do not edit any SKILL.md, agents/*.md or docs/.

Run the full suite until it passes and report: files created/changed, test counts (before 256 → after), any contract point you could not meet and why, and the kordoc preset names you kept/dropped.
