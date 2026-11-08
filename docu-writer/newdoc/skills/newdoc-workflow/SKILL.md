---
name: newdoc-workflow
description: 견본 없이 새 문서(보고서·계획서·기안문·회의록·기술 문서 등)를 요구사항 → 목차 설계 → 근거 조사 → 승인 → 작성 → 검증 → 리뷰 → 전달 파이프라인으로 만들 때 쓰는 절차입니다. 견본 우선 워크플로(template-workflow)와 같은 공유층(writer·doc-verify·reviewer)을 쓰고, ②의 analyst 자리에 planner가 들어가 문서 종류와 목적에서 같은 형식의 프로파일(mode: new)을 만듭니다. 사용자가 「견본 없이 새로」 문서를 만들 때 부릅니다.
disable-model-invocation: true
---

# 신규 문서 워크플로 (2단계)

메인 대화가 이 절차를 따릅니다. **견본 우선 워크플로(`docu-writer:template-workflow`)를 먼저 불러옵니다.** 이 문서는 그 절차에서 **달라지는 점만** 적습니다. 적지 않은 것(작업 디렉터리, 승인 명령, hook, ⑥ 순서, ⑦ 되돌리기, ⑧ 보고)은 template-workflow를 그대로 따릅니다.

> **자동으로 불리지 않습니다.** 워크플로 스킬은 설명(description) 비용을 아끼려고 `disable-model-invocation: true`로 둡니다(`docs/design.md` §9.2). 사용자가 「견본 없이 새 문서」를 요청하면 메인 대화가 이 스킬을 직접 불러옵니다. 경로가 셋으로 갈리는 모습은 `docs/diagrams/newdoc-routes.svg`에 있습니다.

## 파이프라인

```
① 요구사항 (메인) → ② planner (종류·목적 → 프로파일, mode: new)
→ ③ researcher (섹션별 근거) → ④ 승인 (사용자)
→ ⑤ writer (Markdown 작성 → 출력 형식으로 변환) → ⑥ 검증 (메인)
→ ⑦ reviewer(fact) + reviewer(style) + reviewer(design) → ⑧ 전달 (메인)
```

| 단계 | template-workflow와 다른 점 |
|---|---|
| ① | 견본이 없습니다. 문서 종류·목적·독자·출력 형식을 받고, **카탈로그에서 경로**(`fixed`·`theme`·`none`)를 찾습니다. `fixed`면 template-workflow로 넘깁니다. `protected-paths`에는 참고 자료와 테마 파일을 적습니다(비워도 파일은 만듭니다). |
| ② | `docu-writer:analyst` 대신 `docu-writer:planner`. 견본 렌더(`render/source/`)가 없습니다. |
| ③·④ | 같습니다. ④ 표에 「편집 불가 개체」 대신 「경로·테마·변환 방법」을 보여 줍니다. |
| ⑤ | writer가 `.docu-writer/work/draft.md`에 쓴 뒤 테마를 입혀 출력 형식으로 변환합니다(아래 「⑤ 변환 경로」). |
| ⑥ | `doc_verify.py`에 `--source`·`--expect-sha256`을 주지 않습니다(신규 모드 지원 뒤). 견본 해시 대신 참고 자료 해시를 봅니다. |
| ⑦ | design 리뷰어는 견본과 비교하지 않고 프로파일 토큰·R1~R6만 봅니다. |
| ⑧ | 원본 교체가 없습니다(update 모드 없음). |

## ① 요구사항

서브에이전트는 되물을 수 없으므로 여기서 모두 받습니다.

1. **견본이 정말 없는지 확인합니다.** 사용자에게 비슷한 이전 문서·부서 서식이 있으면 template-workflow(`sample`)가 더 정확합니다. 한 번 묻고, 없다고 하면 신규 모드로 갑니다.
2. **문서 종류**를 받습니다: 보고서, 계획서, 기안문, 회의록, 업무보고, 보도자료, 기술 문서, 안내서 등. 모르는 종류면 사용자 말 그대로 적습니다.
3. **목적·독자·분량**을 받습니다: 누가 읽고 무엇을 결정하는지, 쪽수 상한(없으면 planner가 종류에 맞게 제안).
4. **출력 형식**을 정합니다. 첫 판은 `md`·`docx`·`hwpx`만 받습니다. PPTX는 아직 아닙니다(빈 슬라이드에서 레이아웃을 고르는 경로가 없음 — 견본 PPTX가 있으면 template-workflow).

   | 출력 | 확인할 도구 | 형식 스킬 |
   |---|---|---|
   | `.md` | `uv`, `pandoc`, `soffice` (렌더) | `format-markdown` |
   | `.docx` | `uv`, `pandoc`, `soffice` | `format-docx` |
   | `.hwpx` | kordoc 도구(`generate_document`·`render_document`) | `format-hwpx` |

5. **출력 경로**를 정합니다. 이미 있는 파일이면 다른 이름을 받습니다.
6. **자료 위치**와 웹 허용 여부를 받습니다(기본 금지). 자료가 하나도 없으면 사실 칸은 모두 자리표시(`○○`)가 된다고 미리 알립니다.
7. **경로를 찾고 기록합니다.** 템플릿 카탈로그(`docs/design.md` §9.3)에서 이 종류·형식에 맞는 고정 견본이나 테마를 찾습니다. 찾기는 스크립트가 합니다. 메인 대화가 `catalog.yaml`을 읽고 고르지 않습니다.

```bash
mkdir -p .docu-writer/{work,render,verify,backup} && printf '*\n' > .docu-writer/.gitignore
: > .docu-writer/protected-paths                                   # 자료가 없어도 빈 파일은 꼭 만듦
rm -f .docu-writer/route.json .docu-writer/materials.sha256       # ①을 다시 할 때 — catalog.py는 있는 파일을 덮어쓰지 않고, 옛 해시가 남으면 ⑥이 지난 자료를 대조함
for m in <자료 경로…>; do find "$m" -type f -exec realpath {} \; >> .docu-writer/protected-paths; done   # 경로마다 따옴표, 자료가 없으면 비움 — hook은 파일 단위로 비교
uv run "${CLAUDE_SKILL_DIR}/scripts/catalog.py" match --type "<문서 종류>" --format <md|docx|hwpx> \
  --out .docu-writer/route.json >> .docu-writer/protected-paths     # 표준 출력 = 보호할 테마·견본 파일(실제 경로, 한 줄에 하나)
if [ -s .docu-writer/protected-paths ]; then                      # 빈 파일이면 shasum이 표준 입력을 기다리므로 건너뜀
  tr '\n' '\0' < .docu-writer/protected-paths | xargs -0 shasum -a 256 > .docu-writer/materials.sha256
fi
```

`protected-paths` 파일이 **없으면** hook이 모든 서브에이전트 쓰기를 막습니다. 빈 파일은 「보호할 것 없음」입니다.

`catalog.py`의 종료 코드가 2(카탈로그 문법 오류·파일 없음·`route.json`이 이미 있음)면 그 메시지를 사용자에게 보이고, 기본 서식(`none`)으로 갈지 묻습니다. `route.json`이 이미 있다는 오류는 위 `rm -f`를 빠뜨린 것이므로 지우고 다시 부릅니다. `route.json`의 `route`로 갈라집니다.

| `route` | 다음 |
|---|---|
| `fixed` | **신규 절차를 끝내고 template-workflow로 넘깁니다. 모드는 `route.json`의 `mode`(`sample` 견본 · `form` 빈칸 양식)이며 다시 묻지 않습니다.** `route.json`의 `file`을 견본으로 삼아 template-workflow ①부터 다시 기록하되, 기록 명령은 「newdoc fixed 경로에서 넘어옴」 블록을 씁니다. 이 블록은 위에서 쓴 `protected-paths`·`route.json`·`materials.sha256`을 지우지 않고 견본 줄만 덧붙이며, template ⑥이 `materials.sha256`으로 자료와 견본을 대조합니다. ②는 아래 「경로 B — 동봉 프로파일」을 먼저 봅니다. |
| `theme` | 이 절차를 계속합니다. 테마 파일(`reference_doc`·`tokens`·`template_path`)은 위 명령으로 이미 보호됐습니다. |
| `none` | 이 절차를 계속합니다. 변환 도구의 기본 서식을 쓰며 ④에서 「기본 서식」이라고 알립니다. |

```yaml
# .docu-writer/session.yaml — source 없음
mode: new
doc_type: 보고서
purpose: "○○ 시스템 장애 원인과 재발 방지 대책을 국장 결재로 올림"
audience: 국장, 관련 과장
length: { pages: 3 }
output: /abs/결과.hwpx
materials: [ /abs/자료/, "웹: 금지" ]
format_skill: docu-writer:format-hwpx
route: theme                  # route.json의 route (fixed | theme | none)
theme: hwpx/default           # theme일 때 — 형식/이름
# catalog_id: 우리과-기안문    # fixed일 때 — 고정 견본 id (mode는 route.json의 mode)
```

### 경로 B — 동봉 프로파일

고정 견본 항목에 `profile`이 있으면, template-workflow ②에서 analyst를 부르기 전에 메인 대화가 다음을 합니다.

1. `route.json`의 `profile`을 `.docu-writer/profile.yaml`로 복사하고 `source.path`를 견본의 실제 경로로 바꿉니다.
2. template-analysis 「프로파일 점검」의 `profile_extract.py check`를 `--source <견본>`과 함께 실행합니다.
3. 종료 코드 0이면 analyst를 건너뛰고 ③으로 갑니다. 1·2면(견본이 바뀌어 `source.sha256`이 어긋남 등) 복사본을 지우고 analyst가 1단계 그대로 분석합니다.

`profile`이 없으면 1단계 ② 그대로입니다.

## 핸드오프 프롬프트

③ researcher와 ⑦ reviewer는 template-workflow의 프롬프트를 그대로 씁니다. ②와 ⑤만 다릅니다.

**② planner**

```
## 문서 종류
<session.yaml doc_type>

## 목적·독자
- 목적: <purpose>
- 독자: <audience>
- 분량: <length>

## 출력 형식
<md | docx | hwpx>

## 경로
.docu-writer/route.json   (route · theme · 테마 파일 실제 경로 · tokens · preset — planner가 design에 옮김)

## 자료 위치            (목차를 정하는 데 참고만 — 사실은 ③이 모읍니다)
- <materials>

## 불러올 스킬
- <format_skill>
```

**⑤ writer** — template-workflow의 ⑤에 한 줄을 더합니다.

```
## 모드
new — 견본 복사본이 없습니다. .docu-writer/work/draft.md에 쓴 뒤 「변환 경로」로 출력합니다.

## 출력 경로
<session.yaml output>

## 변환 경로
<profile.yaml design.route 그대로 — 예: { tool: pandoc, reference_doc: /abs/…/default.docx }>

## 불러올 스킬
- <format_skill>
- docu-writer:diagram-standards     (kind: 도표 섹션이 있을 때)

## 사용자 지시
- <④에서 정한 것>
```

## ② 목차 설계 — planner가 내는 프로파일

planner는 template-analysis의 프로파일 계약(`docs/design.md` §5)과 **같은 형식**을 씁니다. 다른 점은 다음뿐입니다.

| 키 | 신규 모드에서 |
|---|---|
| `source` | 없음 |
| `mode` | `new` |
| `structure.sections[].anchor` | `h:"제목"`만 씁니다. 결과 문서의 제목 글로 섹션을 찾으므로 writer는 `title`을 **그대로** 제목으로 씁니다(번호는 붙이지 않음 — 번호는 변환 경로가 붙임). |
| `sample_text` | `[]` (잔존 검사할 견본 문구가 없음) |
| `fields`·`update` | 없음 |
| `design` | 변환 경로가 정하는 값만 적고 나머지는 비웁니다(아래). 추측한 서체·pt를 적지 않습니다. |
| `design.route` | 신규 모드 전용 키. writer가 쓸 변환 경로와 프리셋. |
| `conflicts` | 사용자 요구와 문서 종류의 관례가 어긋날 때(예: 결재 보고서인데 「배경 없이 결론만」) `handling: report`로 적고 ④에서 묻습니다. |

**목차는 왜 → 무엇을 → 어떻게 순서로 짭니다.** 배경은 사실로, 문제점마다 방안 한 짝, 기대효과는 목표치로 씁니다. 종류별 필수 섹션은 `planner` 에이전트의 「종류별 필수 섹션」을 따르고, 목차·분량 배분은 `info-design` 「신규 모드」를 따릅니다.

**디자인 토큰은 테마에서 옮깁니다.** planner는 서식을 고르지 않습니다. `route.json`이 가리키는 값을 그대로 적고, 없는 값은 비웁니다.

| 경로·출력 | `design`에 적는 것 | `design.route` |
|---|---|---|
| `theme` · `docx` | 테마 `tokens` 파일(서체·pt·여백·`styles_allowed`)을 그대로 복사 | `{ tool: pandoc, reference_doc: <실제 경로> }` |
| `theme` · `hwpx` (`preset_map`) | 서체·pt는 프리셋이 정하므로 비움. `structure.numbering`은 `["□", "ㅇ", "-"]` | `{ tool: generate_document, preset: <프리셋>, gate: <결재용이면 true> }` |
| `theme` · `hwpx` (`template_path`·`pack_path`) | 위와 같음 | `{ tool: generate_document, template_path: <실제 경로> }` 또는 `pack_path` |
| `none` · `docx` | `styles_allowed`만: pandoc 기본 스타일 이름(`Title`, `Heading 1`~`3`, `Body Text`, `First Paragraph`, `Compact`, `Table`) | `{ tool: pandoc }` |
| `none` · `hwpx` | 비움 | `{ tool: generate_document }` (preset 없이 범용 변환) |
| `md` | 비움 (MD는 r4·r5·표 머리·r1 검사를 건너뜀) | `{ tool: copy }` |

planner는 template-analysis 「프로파일 점검」의 신규 모드 규칙으로 `profile_extract.py check .docu-writer/profile.yaml`을 `--source` 없이 통과시킨 뒤 보고합니다.

## ③·④

template-workflow 그대로입니다. ④에서 승인 해시를 고정하는 명령도 같습니다.

```bash
shasum -a 256 .docu-writer/profile.yaml .docu-writer/evidence.yaml > .docu-writer/approved.sha256.tmp \
  && mv .docu-writer/approved.sha256.tmp .docu-writer/approved.sha256
```

④ 표에는 섹션 표(id · 제목 · kind · 분량 · 근거 수 · 근거 없음)와 함께 **경로와 테마**(`theme: docx/default` 또는 「기본 서식 — 카탈로그에 이 종류의 테마 없음」), **변환 방법**(`design.route`), **비운 토큰**, **자리표시로 남을 칸**을 보여 줍니다. 신규 문서는 견본이 없어 사용자가 목차를 처음 보는 자리이므로, 섹션 순서와 빠진 섹션을 꼭 확인받습니다.

## ⑤ 변환 경로

writer는 먼저 `.docu-writer/work/draft.md`에 씁니다. 섹션 제목은 프로파일 `title` 그대로, 수준은 `level`대로(`level: 1` → `##`). 본문에는 `####` 이하 제목과 펜스 코드 블록을 쓰지 않습니다. pandoc이 `Heading 4`·`Source Code`를 만들어 `styles_allowed` 밖이 되므로 `r5_tokens`가 `fail`합니다. 더 나눌 내용은 목록 2단으로 씁니다. `pandoc` 경로에서는 `>` 인용도 쓰지 않습니다(`Block Text`가 되어 같은 이유로 `fail`). 요약 상자 `> …하고자 함`은 HWPX 프리셋 전용입니다. DOCX에서 문서 제목 `#`은 `Heading 1`(16pt), `level: 1` 섹션은 `Heading 2`, `level: 2`는 `Heading 3`이 됩니다. 그다음 출력 형식으로 바꿉니다.

| `design.route.tool` | 경로 |
|---|---|
| `copy` | `draft.md`를 출력 경로로 복사 |
| `pandoc` | `pandoc .docu-writer/work/draft.md --reference-doc=<route.reference_doc> -o <출력 경로>`. `reference_doc`이 없으면(`none`) 옵션 없이. `format-docx` 「신규 작성」 |
| `generate_document` | kordoc `generate_document`(`markdown`: draft.md 내용, `output_path`: 작업 폴더의 `docu-writer-out/<이름>.hwpx`) → 출력 경로로 옮김. 옵션은 route에 적힌 것만 넘깁니다: `preset`(+`gate`) **또는** `template_path` **또는** `pack_path`. 셋을 섞지 않고, route에 아무것도 없으면 preset 없이 부릅니다 |

HWPX 프리셋의 Markdown 대응: `#` 제목, `##` 장, `###` □ 항목, 그 아래 목록 1단 ㅇ·2단 - (`###` 없이 `##` 바로 아래 둔 목록은 한 단씩 올라가 1단 □·2단 ㅇ이 되므로, ㅇ 항목을 쓰려면 `###`를 둡니다), `> …하고자 함` 요약 상자, `※` 참고. 보고서·계획서 프리셋은 `##` 장 제목을 번호 칸(Ⅰ·Ⅱ)과 제목 칸으로 나눕니다. writer는 번호를 쓰지 않고 `title`만 씁니다. 신규 모드에서는 writer가 `generate_document`를 쓰기 전에 멈추지 않습니다(④에서 경로를 승인받았으므로).

**테마 파일은 고치지 않습니다.** `reference_doc`·`template_path`는 `protected-paths`에 있어 hook이 막습니다. 결과가 테마와 다르게 보이면 writer는 보고하고 멈춥니다.

## ⑥ 검증

template-workflow ⑥의 순서를 따르되 다음이 다릅니다.

1. `shasum -c .docu-writer/approved.sha256` — 같음.
2. `materials.sha256`이 있으면 `shasum -c .docu-writer/materials.sha256` — 견본 해시 대신 이것으로 참고 자료와 테마 파일에 대해 「원본에 쓰지 않음」을 확인합니다.
3. 렌더 — 같음(`render/source/`는 없음). HWPX는 `render.py`가 거절하므로 `docu-writer:format-hwpx` 「렌더 (⑥)」의 명령 그대로 이전 쪽을 지우고 kordoc `render_document`를 svg·png로 불러 `page.svg`(한 쪽)나 `page_page_NNN.svg`(여러 쪽)를 `.docu-writer/render/`에 둡니다 — 이 파일이 없으면 `length`(쪽수)·`r1_tables`가 `skip`됩니다.
4. `doc_verify.py` — `--source`·`--expect-sha256` 없이 실행합니다. 프로파일의 `mode: new`를 보고 신규 모드 규칙으로 검사합니다(`docu-writer:doc-verify` 「신규 모드」). 견본이 없어 `skip`되는 항목(r4, 토큰이 빈 r5, MD의 markup)은 렌더 PNG로 직접 확인하고 ⑧에 적습니다.

   명령은 `docu-writer:doc-verify` 스킬 「실행」의 2번에서 `--source …` `--expect-sha256 …` 줄만 뺀 것입니다(스크립트 경로는 그 스킬을 불러 얻습니다).
5. 결과 파일 해시 `verify/output.sha256` — 같음.

## ⑦·⑧

template-workflow 그대로입니다. 다만 ⑦에서 지적이 **목차 자체**(섹션 누락·순서)를 문제 삼으면 ②(planner)로 되돌리고 ④를 다시 받습니다. ⑧ 보고에 「견본 없이 만든 문서 — 부서 서식이 있으면 그 견본으로 template-workflow를 다시 돌릴 수 있음」을 한 줄 덧붙입니다.

## 단계를 줄여도 되는 경우

| 작업 | 생략 가능 |
|---|---|
| 회의록처럼 내용을 사용자가 대화로 모두 줌 | ③ — 메인 대화가 `evidence.yaml`을 `source: 사용자`로 적음 |
| `md` 출력이고 표·도표 없음 | ⑦의 design 관점 |

①, ④ 승인, ⑥의 해시 대조는 생략하지 않습니다.
