---
name: format-hwpx
description: HWPX·HWP 견본을 다루는 형식 스킬입니다. kordoc MCP 도구로 견본을 읽고(parse_document·parse_form), 견본 서식 그대로 내용을 바꾸고(patch_document), 양식 칸을 채우고(fill_form), 쪽별로 렌더(render_document)하는 경로와 함정(대체본 .rewrite.hwpx, 줄 머리 ○, HWP 문단 수 제한, 근사 렌더)을 정합니다. 견본이 .hwpx·.hwp일 때 사용합니다.
---

# HWPX·HWP

이 스킬은 **한글 문서를 kordoc으로 읽고 쓰는 법만** 담습니다. 무엇을 쓸지는 프로파일이, 디자인 규칙은 `design-review`가 정합니다. kordoc은 moai-officer 플러그인의 MCP입니다. 도구(`mcp__plugin_moai-officer_kordoc__*`)가 없으면 ①에서 사용자에게 알리고 멈춥니다.

## 준비

- **HWP(5.x)는 먼저 HWPX로 바꿉니다.** `convert_to_hwpx(file_path, output_path=docu-writer-out/<이름>.hwpx)` 뒤 `.docu-writer/work/`로 옮깁니다. HWP는 제자리 수정에서 문단을 늘리거나 줄일 수 없습니다. 바꾼 HWPX를 이후 단계의 견본으로 쓰고, 원본 HWP의 sha256도 ①에서 기록합니다.
- **kordoc 출력 경로.** kordoc 쓰기 도구(`patch_document`·`fill_form`·`convert_to_hwpx`·`extract_profile`·`render_document`)는 숨김 경로(`.`으로 시작하는 폴더·파일)에 쓰지 않습니다(종단 시험 F13·F15). `.docu-writer/` 안에 둘 파일은 작업 폴더의 보이는 `docu-writer-out/`에 낸 뒤 `Bash`로 옮기고, 다 옮기면 `rmdir docu-writer-out`으로 지웁니다. hook은 analyst에게 `.docu-writer/`와 이 폴더만 열어 둡니다. 읽기(`parse_document`·`fields_file`)는 숨김 경로도 됩니다.
- 결과는 HWPX로 냅니다. 사용자가 HWP 결과를 꼭 원하면 ①에서 알려 줍니다(줄 수를 견본과 같게 맞춰야 함).

## 분석 (②, analyst)

| 할 일 | 도구 |
|---|---|
| 골격·문단 부호·표 읽기 | `parse_document(file_path, keep_layout_tables: true)` |
| 양식 칸 (form 모드) | `parse_form(file_path)` → 프로파일 `fields` |
| 표 서식 토큰 | `extract_profile(hwpx_path, output_path=docu-writer-out/table-profile.json)` → `.docu-writer/work/`로 옮김 → 프로파일 `design.table` |
| 표 번호(`t:N`) 목록 | `profile_extract.py tables <견본>` — kordoc 마크다운의 표 개수로 세지 않음(설계서 §5) |
| 쪽 모양 보기 | `render_document(file_path, format: "png", pages: "1-3")` |

- `parse_document` 결과의 부호(□·ㅇ·-·※·1.·가.)가 프로파일 `structure.numbering`입니다.
- 서체·크기는 렌더 이미지와 `extract_profile` 결과로 읽습니다. 확인할 수 없는 토큰은 비워 두고 ④에서 보고합니다.
- 글상자·그림·도형은 `patch_document`가 그대로 둡니다. 그 안의 글을 바꿔야 하면 ②에서 「편집 불가 개체 가능성」으로 보고합니다.

## 작성 (⑤, writer)

### 견본 따라 쓰기 (`sample`) — `patch_document`

1. `parse_document(견본, keep_layout_tables: true)`의 마크다운을 받습니다.
2. **골격은 두고 내용만 바꿉니다.** 표지·결재란 표, 제목, 문단 부호와 들여쓰기, `**` 강조 표지, 표 표기(`<table>`이면 HTML 꼴 그대로), 이미지 줄은 건드리지 않습니다.
3. 문단은 늘리고 줄일 수 있습니다. **새 줄은 같은 부호로 시작**해야 그 부호의 견본 문단 서식이 복제됩니다. 블록 순서는 바꿀 수 없습니다.
4. 표는 칸 글만 바꾸고, 행은 더하거나 뺍니다.
5. `patch_document(file_path=견본, edited_markdown=<전체 마크다운>, output_path=<출력 경로>)`.

`generate_document(template_path=견본)`는 견본과 표·항목 구조가 크게 달라 patch로 맞출 수 없을 때만 씁니다. 글상자·그림을 옮기지 않아 견본 분위기가 바뀌므로, 쓰기 전에 ⑤ 보고에 이유를 적고 메인 대화가 사용자 확인을 받게 합니다. 기본 경로가 아닙니다.

### 양식 채우기 (`form`) — `fill_form`

- `fill_form(file_path=견본, fields={라벨: 값}, output_format: "hwpx-preserve", output_path, require_unique: true)`.
- 개인정보가 든 값은 `fields_file`(JSON 파일 경로)로 넘겨 대화에 값이 남지 않게 합니다. 근거 없는 칸은 `○○`가 아니라 앞에 글을 둔 자리표시로 채웁니다(`writing-principles`).

### 문서 갱신 (`update`) — `patch_document(structure: false)`

- 프로파일 `update.sections` 안의 문구만 고칩니다. 줄 수를 바꿔야 하면 `structure`를 빼고(기본 true) 그 사실을 보고합니다.
- 출력은 언제나 복사본입니다. `patch_document(..., output_path=docu-writer-out/<이름>.updated.hwpx)`로 낸 뒤 `mkdir -p .docu-writer/work && mv docu-writer-out/<이름>.updated.hwpx .docu-writer/work/`로 옮깁니다. 원본 교체는 ⑧에서 메인 대화가 합니다.
- 고칠 섹션 밖은 줄 하나도 바꾸지 않습니다. 요약 상자 줄도 `> `만 떼고 글은 그대로 둡니다(「함정」). doc-verify `scope`가 섹션 밖 변경을 잡습니다.

## 신규 작성 (`mode: new`)

견본이 없으므로 writer는 `.docu-writer/work/draft.md`를 쓰고 `generate_document`로 만듭니다. 위 「작성」의 `template_path` 제한(사용자 확인)은 견본 복사본에 대한 것이며, 신규 모드는 ④에서 경로를 승인받았으므로 멈추지 않습니다.

- 옵션은 프로파일 `design.route`에 적힌 것만 넘깁니다: `preset`(+`gate`) **또는** `template_path` **또는** `pack_path`. kordoc은 `template_path`·`pack_path`를 `preset`·서식 옵션과 함께 받지 않습니다. route에 셋 다 없으면 preset 없이(범용 변환) 부릅니다.
- `output_path`는 작업 폴더의 `docu-writer-out/`에 두었다가 출력 경로로 옮깁니다(「kordoc 출력 경로」).
- Markdown 대응: `#` 제목, `##` 장, `###` □ 항목, 목록 1단 ㅇ·2단 -, `> …하고자 함` 요약 상자, `※` 참고.
- 보고서·계획서 프리셋은 `##` 장 제목을 번호 칸(Ⅰ·Ⅱ)과 제목 칸으로 나눕니다. 장 제목에 번호를 쓰지 않습니다. 결과에서 `h:` anchor가 제목 칸 글로 찾히는지는 `docs/design.md` §11 위험 7.

## 함정

- **대체본 `<출력>.rewrite.hwpx`.** `patch_document`가 일부 편집을 제자리에 반영하지 못하면 원본 서식으로 새로 쓴 대체본을 함께 만듭니다. 대체본이 생기면 어느 파일이 결과인지 정해 ⑤ 보고에 적습니다(편집이 다 들어간 쪽은 대체본, 서식이 정확한 쪽은 출력 파일). doc-verify `rewrite` 검사가 이를 잡습니다.
- **줄 머리 `○`.** 줄을 `○`로 시작하면 글머리표로 먹힐 수 있습니다. 자리표시는 `총 ○○건`처럼 앞에 글을 둡니다.
- **부호 글자.** kordoc은 2수준 부호를 `ㅇ`(U+3147)이나 `ᄋ`(U+110B)로 낼 수 있습니다. 견본이 낸 글자를 그대로 복사해 씁니다. 다른 글자를 쓰면 다른 서식 견본이 골라집니다.
- **요약 상자 줄은 `> ` 없이 씁니다.** `parse_document`는 제목 아래 요약 상자 글을 `> …`로 보여 주지만, 그대로 `patch_document`에 넘기면 `> `가 글자로 상자 안에 들어갑니다(kordoc 문제, 종단 시험 F12). 그 줄은 `> `를 떼고 글만 적으면 같은 상자에 들어갑니다. 이때도 patch가 「반영 안 된 편집 있음 (수정 1)」을 보고할 수 있으니 결과 글로 확인하고, 새어 든 표지는 doc-verify `markup` 검사가 잡습니다.
- **서식을 맞추려고 내용을 빼지 않습니다.** 넣을 내용은 그대로 넣고 렌더로 확인합니다. 줄이는 것은 `info-design`의 「줄이는 순서」를 따릅니다.

## 렌더 (⑥)

```
render_document(file_path=<결과>, format: "svg", pages: "1-N", output_path: docu-writer-out/page.svg)
render_document(file_path=<결과>, format: "png", pages: "1-N", output_path: docu-writer-out/page.png)
mkdir -p .docu-writer/render && mv docu-writer-out/page* .docu-writer/render/ && rmdir docu-writer-out
```

- kordoc은 숨김 경로에 쓰지 않으므로 보이는 `docu-writer-out/`에 낸 뒤 `.docu-writer/render/`로 옮깁니다(「준비」의 「kordoc 출력 경로」).
- 여러 쪽이면 `page_page_NNN.svg`처럼 `_page_NNN` 접미가 붙고, 한 쪽뿐이면 접미 없이 `page.svg` 하나입니다. 그래서 옮기고 지울 때 `page_*`가 아니라 `page*`를 씁니다(zsh는 맞는 파일이 없으면 명령 전체를 멈춥니다). doc-verify는 둘 다 읽고, 섞여 있으면 이전 렌더가 남은 것으로 보고 멈춥니다. SVG의 `<text>`가 doc-verify의 쪽별 글이 됩니다.
- 쪽 수는 `parse_document` 머리 줄(`페이지: N`)에서 읽습니다. 이미지 응답은 한 번에 8쪽까지라 그보다 길면 나눠 부릅니다.
- **AI가 만든 HWPX는 근사 렌더입니다**(조판 캐시 없음, reflow). 쪽 경계에 걸린 판정(R1·R3)은 ⑧에서 「한컴에서 열어 확인 권장」을 붙입니다.
- `highlights`로 바꾼 문구나 자리표시를 표시해 렌더하면 ⑦ 리뷰어가 위치를 찾기 쉽습니다.

## 검토 보조 (⑦, reviewer `관점: style`)

`lint_document(file_path=<결과>, munche: true, slop: true, numbers: true)`로 표기법·개조식 문체·본문↔표 수치를 검사합니다. 예산 문서면 `budget: true`. 결과는 참고 자료이며, 견본이 쓰는 표기와 충돌하면 견본을 따릅니다.
