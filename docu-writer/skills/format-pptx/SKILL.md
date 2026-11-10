---
name: format-pptx
description: PPTX 견본을 다루는 형식 스킬입니다. 슬라이드·플레이스홀더·도형을 locator가 붙은 목록으로 뽑고(dump), 편집 목록(edits.yaml)을 견본 복사본에 적용하는(apply) patch_pptx.py의 호출 계약과, 견본 슬라이드 복제·레이아웃 제한·한 슬라이드 분량·python-pptx가 다루지 못하는 개체를 정합니다. 견본이 .pptx일 때 사용합니다.
---

# PPTX

이 스킬은 **PPTX 견본을 읽고 복사본에 내용을 넣는 법만** 담습니다. 무엇을 쓸지는 프로파일이, 디자인 규칙은 `design-review`가 정합니다. 편집 목록의 모양은 `format-docx`와 같고, locator와 op만 다릅니다.

## 원칙

- **견본 슬라이드를 복제해 씁니다.** 새 슬라이드는 같은 역할의 견본 슬라이드(`like`)를 복제한 뒤 글만 바꿉니다. 빈 레이아웃에서 새로 그리지 않습니다(견본이 없는 새 덱은 `deck-design`).
- **레이아웃은 프로파일 `design.styles_allowed`(레이아웃 이름) 안에서만** 고릅니다. 도형 위치·크기·색을 바꾸지 않습니다.
- **한 슬라이드에 메시지 하나.** 제목은 결론 문장으로 씁니다. 넘치면 글자를 줄이지 말고 슬라이드를 나눕니다(`info-design` 「줄이는 순서」 3단계에 해당).

## 분석 (②) — `profile_extract.py`

`template-analysis`의 `profile_extract.py`가 슬라이드 크기·레이아웃·플레이스홀더·테마 색을 읽습니다. 이 스킬은 아래를 확인합니다.

- 슬라이드마다 역할(표지·목차·간지·본문·표·마무리)을 붙여 프로파일 `structure.sections`에 적었는지.
- SmartArt·차트·그룹 도형 안 글·동영상·애니메이션은 ②에서 「편집 불가 개체」로 보고합니다. python-pptx는 SmartArt와 차트 데이터를 고치지 못합니다. 차트는 ⑧에서 사용자가 PowerPoint로 데이터를 고치도록 위치와 새 값을 적어 둡니다.
- 슬라이드 노트가 있으면 노트도 내용으로 다룰지 ④에서 묻습니다.

## 작성 (⑤) — `patch_pptx.py`

### 1) 골격 뽑기

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/patch_pptx.py" dump <견본.pptx> --out .docu-writer/work/skeleton.yaml
```

```yaml
- {at: "sl:3", layout: "제목 및 내용", role: body}
- {at: "sl:3/ph:0", kind: title, text: "추진 일정"}
- {at: "sl:3/ph:1/p:2", level: 1, text: "2단계: 3~5월"}      # 플레이스홀더 1의 문단 2
- {at: "sl:3/sh:7", kind: table, table: "t:2", rows: 3, cols: 3}  # 문서 전체 표 번호
- {at: "sl:3/sh:7/t/r:2/c:1", text: "1~3월"}                 # 도형 7의 표, 행 2, 칸 1
- {at: "sl:4/sh:5", kind: smartart, editable: false}
```

### 2) 편집 목록 — `.docu-writer/work/edits.yaml`

| op | 필드 | 하는 일 |
|---|---|---|
| `replace` | `at`, `text` | 문단·칸·제목 글 바꿈. 첫 run 서식 유지 |
| `insert_after` | `at`, `like`, `text` | 같은 플레이스홀더 안 `like` 문단(수준 포함)을 복제해 넣음 |
| `delete` | `at` | 문단 삭제 |
| `slide_dup` | `like`, `after` | 슬라이드 복제. 새 슬라이드는 `new:1`, `new:2`…로 이후 op에서 가리킴 |
| `slide_delete` | `at` | 슬라이드 삭제 |
| `row_add` · `row_delete` | `format-docx`와 같음 | 표 행 |
| `notes` | `at`, `text` | 슬라이드 노트 글 바꿈 |

- `ph:N`은 플레이스홀더 `idx`, `sh:N`은 도형 id(`p:cNvPr@id`)입니다. 둘 다 슬라이드 안에서 겹치지 않고 그룹 안 도형도 같은 방식으로 가리킵니다. 표 칸은 `t:N/r:R/c:C`(문서 전체 표 번호)로도 가리킬 수 있고, 두 표기는 같은 칸을 뜻합니다.
- locator는 dump 시점 기준이고, 스크립트가 먼저 모두 해석합니다. 복제한 슬라이드 안은 `new:1/ph:1/p:1`처럼 씁니다.
- 편집 목록 파일은 `format-docx`처럼 편집 항목의 목록 한 개입니다. `slide_dup`의 `like`·`after`는 `sl:N`, `new:N`은 파일 안 `slide_dup` 순서대로 1부터 붙습니다.
- `like` 슬라이드의 레이아웃 이름이 `design.styles_allowed` 밖이면 `slide_dup`은 실패합니다.
- 슬라이드 순서 바꾸기는 op가 없습니다. 견본 구조 변경이므로 필요하면 보고합니다.

### 3) 적용

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/patch_pptx.py" apply <견본.pptx> \
  --edits .docu-writer/work/edits.yaml --profile .docu-writer/profile.yaml --out <출력.pptx>
```

종료 코드(0·1·2)와 표준 출력 JSON은 `format-docx`와 같습니다. 1이면 파일을 쓰지 않습니다. 추가로 `warnings`에 **글이 플레이스홀더를 넘칠 것 같은 곳**(글자 수가 견본 같은 자리의 1.3배 초과)을 냅니다. 이 경고는 ⑥ 렌더에서 확인합니다.

## 렌더 (⑥)

`doc-verify`의 `render.py`가 슬라이드별 PNG와 `pages.json`을 만듭니다(1쪽 = 1슬라이드). 슬라이드에서는 **잘림 = 넘침**이므로 R1·R2를 쪽 경계가 아니라 플레이스홀더 밖으로 나간 글로 봅니다. 자동 맞춤(글자 줄이기)이 켜진 플레이스홀더는 R5 위반 후보로 ⑦ design 리뷰어에게 넘깁니다.

## 갱신 (`update`)

같은 경로입니다. `update.sections`는 프로파일 섹션 id로 적고, 섹션마다 `anchor: "sl:N"`이 범위를 정합니다. 그 밖 편집은 doc-verify `scope`가 잡습니다.

`sl:N` anchor는 견본 N번째 **슬라이드 자체**(`p:sldId`)를 가리킵니다. 고치는 섹션 안에서 `slide_dup`으로 장을 늘리거나 `slide_delete`로 줄여도 뒤 섹션의 시작이 함께 따라가므로, 뒤 섹션이 밀렸다고 `scope`가 실패하지 않습니다. 복제한 장은 `after`가 가리킨 장이 속한 섹션 몫입니다. 고치지 않는 섹션의 장을 지우거나 그 섹션 안에 장을 끼우면 `scope`가 실패합니다. `patch_pptx.py`는 이를 막지 않으니, 장을 늘리고 줄이는 일은 `update.sections` 안에서만 합니다.

고치는 섹션의 **첫 장은 지우지 말고 제자리에서 고칩니다.** 다른 레이아웃이 필요해 `slide_dup` 후 첫 장을 `slide_delete`하면, 새 장은 견본 id가 없어 섹션 시작으로 잡히지 않고 남은 장이 시작이 됩니다. 그러면 새 장이 앞 섹션 몫으로 셈해져 앞 섹션이 보호 섹션일 때 `scope`가 실패합니다(섹션 장을 모두 바꾼 경우도 같음). 레이아웃을 바꿔야 하면 복제한 장을 섹션에 남는 장 **뒤**(`after`)에 두고, 첫 장은 남깁니다.
