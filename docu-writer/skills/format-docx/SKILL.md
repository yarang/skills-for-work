---
name: format-docx
description: DOCX 견본을 다루는 형식 스킬입니다. 견본 골격을 locator가 붙은 목록으로 뽑고(dump), 편집 목록(edits.yaml)을 견본 복사본에 적용하는(apply) patch_docx.py의 호출 계약과, 견본 문단 복제·스타일 보존·styles_allowed 제한·python-docx가 다루지 못하는 개체를 정합니다. 견본이 .docx일 때 사용합니다.
---

# DOCX

이 스킬은 **DOCX 견본을 읽고 복사본에 내용을 넣는 법만** 담습니다. 무엇을 쓸지는 프로파일이, 디자인 규칙은 `design-review`가 정합니다.

## 원칙

- **견본 문단을 복제해 씁니다.** 새 문단은 비슷한 견본 문단(`like`)을 복제한 뒤 글만 바꿉니다. 그래야 스타일·번호 매기기·들여쓰기·run 서식이 그대로 옵니다.
- **직접 서식을 넣지 않습니다.** 글꼴·크기·색을 run에 지정하지 않습니다. 쓸 수 있는 스타일은 프로파일 `design.styles_allowed`뿐입니다(`visual-design`).
- **pandoc `--reference-doc`으로 다시 만들지 않습니다.** 스타일만 옮기고 표지·표 배치·머리글을 버립니다.

## 분석 (②) — `profile_extract.py`

`template-analysis` 스킬의 `profile_extract.py`가 스타일·섹션 설정·표·번호 매기기를 읽어 프로파일 초안을 만듭니다. 이 스킬은 그 결과 가운데 아래를 확인합니다.

- `styles_allowed`에는 견본 본문에서 **실제로 쓰인** 스타일만 들어갔는지.
- 글상자·SmartArt·필드 코드(목차·쪽 번호·상호 참조)·변경 내용 추적·메모가 있으면 ②에서 「편집 불가 개체」로 보고합니다. python-docx는 이 개체 안을 고치지 못하며, 이 스킬도 건드리지 않습니다. 목차 필드는 Word에서 「필드 업데이트」가 필요하다고 ⑧에 적습니다.

## 작성 (⑤) — `patch_docx.py`

### 1) 골격 뽑기

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/patch_docx.py" dump <견본.docx> --out .docu-writer/work/skeleton.yaml
```

본문 순서대로 블록을 냅니다. writer는 이 locator만 씁니다.

```yaml
- {at: "p:12", style: "제목 2", text: "2. 추진 일정"}
- {at: "t:1/r:2/c:3", style: "표 본문", text: "1~3월"}   # 표 1, 행 2, 칸 3 (1부터)
- {at: "p:13", kind: textbox, text: "…", editable: false}
```

### 2) 편집 목록 쓰기 — `.docu-writer/work/edits.yaml`

| op | 필드 | 하는 일 |
|---|---|---|
| `replace` | `at`, `text` | 문단·칸 글을 바꿈. 첫 run 서식을 남기고 나머지 run을 비움 |
| `insert_after` | `at`, `like`, `text` | `like` 문단을 복제해 `at` 뒤에 넣음 |
| `delete` | `at` | 문단 삭제 |
| `row_add` | `table`, `like_row`, `after`, `cells: […]` | 행 복제 후 칸 글 채움 |
| `row_delete` | `table`, `row` | 행 삭제 |

파일은 편집 항목의 목록 한 개입니다.

```yaml
- {op: replace, at: "p:3", text: "2026년 상반기 신청 건수는 135건이다."}
- {op: insert_after, at: "p:3", like: "p:3", text: "…"}
- {op: row_add, table: "t:1", like_row: 2, after: 2, cells: ["시행", "2~6월", "운영팀"]}
- {op: row_delete, table: "t:2", row: 2}
```

- `like` 문단의 스타일이 프로파일 `design.styles_allowed` 밖이면 그 편집은 실패합니다.
- locator는 **dump 시점 기준**입니다. 스크립트가 모든 locator를 먼저 해석한 뒤 적용하므로, 앞 편집 때문에 번호가 밀리는 것을 writer가 계산하지 않습니다.
- `text` 안 줄바꿈은 같은 문단 안 줄바꿈이 아니라 오류입니다. 문단을 늘리려면 `insert_after`를 씁니다.
- 자리표시는 `writing-principles`를 따릅니다(줄 머리에 두지 않음, locator와 함께 `placeholders.yaml`에 기록).

### 3) 적용

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/patch_docx.py" apply <견본.docx> \
  --edits .docu-writer/work/edits.yaml --profile .docu-writer/profile.yaml --out <출력.docx>
```

| 종료 코드 | 뜻 |
|---|---|
| 0 | 모두 적용 |
| 1 | 적용하지 못한 편집이 있음 (`editable: false` 대상, 없는 locator, `styles_allowed` 밖 스타일). **파일은 쓰지 않음** |
| 2 | 사용법·환경 오류. `--out`이 견본 경로와 같거나 이미 있는 파일이면 2 |

표준 출력은 JSON 한 개입니다: `{"applied": N, "failed": [{"op", "at", "reason"}], "warnings": […]}`. `failed`가 있으면 edits를 고쳐 다시 돌리고, 같은 실패가 3번 되풀이되면 멈추고 보고합니다.

## 렌더 (⑥)

`doc-verify` 스킬의 `render.py`가 soffice → PDF → 쪽별 PNG와 `pages.json`을 만듭니다. LibreOffice 렌더는 Word와 쪽 경계가 한두 줄 다를 수 있어, R1·R3 판정이 경계에 걸리면 ⑧에 「Word에서 열어 확인 권장」을 붙입니다.

## 갱신 (`update`)

같은 dump → edits → apply 경로입니다. edits의 locator가 프로파일 `update.sections` 밖이면 doc-verify `scope` 검사가 실패합니다.
