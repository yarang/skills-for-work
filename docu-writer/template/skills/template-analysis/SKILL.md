---
name: template-analysis
description: 견본·양식 파일(HWPX·HWP·DOCX·PPTX·MD)을 읽어 양식 프로파일(.docu-writer/profile.yaml)을 만드는 절차와 profile_extract.py 스크립트의 계약입니다. 표 번호 매기기, 섹션 anchor, 문단 번호 세는 법, 견본 문구 지문(sample_text) 고르는 법, 프로파일 점검을 정합니다. 견본 우선 파이프라인 ②단계에서 analyst가 씁니다.
---

# 견본 분석

견본을 프로파일로 옮깁니다. 프로파일의 형식은 설계서 §5가 정하고, 이 스킬은 **어떻게 채우는지**를 정합니다. 기계가 읽을 수 있는 것(표 번호, 스타일, 쪽 설정)은 스크립트가 채우고, 사람이 읽어야 하는 것(문체, 섹션의 쓰임새, 작성 요령)은 analyst가 채웁니다.

## 분석 절차

1. **표 번호 목록**: 형식에 상관없이 먼저 냅니다. 이후 모든 `t:N`은 이 목록의 번호입니다.

   ```bash
   uv run "${CLAUDE_SKILL_DIR}/scripts/profile_extract.py" tables <견본> > .docu-writer/work/tables.yaml
   ```

2. **초안**: 형식에 따라 나뉩니다.

   | 형식 | 초안 |
   |---|---|
   | DOCX·PPTX·MD | `profile_extract.py profile <견본> --mode <모드> --out .docu-writer/work/profile-draft.yaml` |
   | HWPX | 스크립트 초안 없음. 형식 스킬 「분석」 표의 kordoc 도구로 읽어 직접 씁니다 |

3. **형식 스킬 확인**: 형식 스킬의 「분석」 항목(편집 불가 개체, `styles_allowed`, 노트 등)을 확인합니다.
4. **견본 렌더**: 1~3쪽을 `.docu-writer/render/source/`에 냅니다. DOCX·PPTX·MD는 `doc-verify` 스킬의 `render.py`, HWPX는 kordoc `render_document(format: "png", pages: "1-3")`. 이 이미지로 서체 분위기, 강조 방식, 표 모양을 봅니다.
5. **사람이 채우는 칸**: 아래 「analyst가 채우는 칸」.
6. **점검**: 「프로파일 점검」을 통과시키고 `.docu-writer/profile.yaml`로 씁니다.

## `profile_extract.py` 계약

PEP 723 인라인 의존성(python-docx, python-pptx, pyyaml, lxml)을 적고 `uv run --python 3.13`으로 돕니다. 견본은 읽기만 하고, 출력 파일이 이미 있으면 덮어쓰지 않고 종료 코드 2로 끝납니다.

| 명령 | 형식 | 출력 |
|---|---|---|
| `tables <견본>` | HWPX·DOCX·PPTX·MD | 표준 출력에 YAML 표 목록 |
| `profile <견본> --mode <sample\|form\|update> --out <경로>` | DOCX·PPTX·MD | 프로파일 초안 YAML |
| `check <프로파일> --source <견본> [--tables <tables.yaml>]` | 모두 | 표준 출력에 점검 결과 |

| 종료 코드 | 뜻 |
|---|---|
| 0 | 성공 (`warnings`는 있을 수 있음) |
| 1 | `check`에서 실패 항목이 있음 |
| 2 | 사용법 오류, 지원하지 않는 형식(`profile`에 HWPX 등), 파일 없음, `--out`이 이미 있음 |

### `tables` 출력

```yaml
tables:
  - at: "t:1"
    slide: 3            # PPTX만
    rows: 4
    cols: 3
    first: "구분"        # 첫 행 첫 칸 글 (앞뒤 공백 제거, 40자까지)
    last: "합계 1,234"   # 마지막 행 마지막 칸 글
    nested: 0           # 이 표 안에 든 표의 수 — 번호에는 넣지 않음
warnings: []
```

**세는 법**은 설계서 §5 「표 번호」 그대로입니다. 본문의 **최상위 표**를 나오는 순서대로 1부터 셉니다. 틀 표(제목 상자·요약 상자·결재란)도 세고, 표 안의 표와 머리글·바닥글의 표는 세지 않습니다.

| 형식 | 순서 |
|---|---|
| HWPX | `Contents/section0.xml`, `section1.xml` … 차례로, 각 파일 안에서 문서 순서의 최상위 `hp:tbl` |
| DOCX | `document.tables` (본문 직속 `w:tbl`) |
| PPTX | 슬라이드 순서, 슬라이드 안에서는 도형 트리 순서. 그룹 도형 안의 표도 셉니다 |
| MD | 파이프 표가 나오는 순서. 코드 블록 안은 세지 않음 |

`first`·`last`는 `doc_verify.py`의 `r1_tables` 검사(첫 칸 글과 끝 칸 글이 같은 쪽에 있는가)가 그대로 씁니다. 칸이 비어 있으면 그 행에서 글이 있는 마지막 칸을 쓰고, 모두 비면 `""`와 경고를 냅니다.

### `profile` 출력이 채우는 것

| 프로파일 칸 | DOCX | PPTX | MD |
|---|---|---|---|
| `source` (경로·형식·sha256) | ○ | ○ | ○ |
| `structure.sections[].title·level·anchor` | 제목 스타일 문단 (`p:N`) | 슬라이드마다 (`sl:N`) | `#` 제목 (`h:"…"`) |
| `structure.numbering` | 번호 매기기 형식·줄 머리 부호 | 본문 플레이스홀더 줄 머리 부호 | 목록 부호·제목 번호 |
| `fields` (form) | 빈 칸·밑줄 칸이 있는 표 칸 | 비어 있는 플레이스홀더 | 앞머리 키 |
| `design.page` | 섹션 설정(용지·방향·여백) | 슬라이드 크기 | 비움 |
| `design.type` | 본문·제목 N 스타일의 서체·크기·굵기·줄 간격 | 레이아웃 제목·본문 서체·크기 | 비움 |
| `design.color` | 본문 글자색, 표 머리행 바탕색 | 테마 색 | 비움 |
| `design.table` | 머리행 굵기·바탕색, 숫자 칸 정렬 | 같음 | 정렬 표기 |
| `design.styles_allowed` | 본문에서 실제로 쓰인 문단·글자 스타일 | 쓰인 레이아웃 이름 | 비움 |
| `sample_text_candidates` | 아래 「견본 문구 지문」 | 같음 | 같음 |
| `objects` | 글상자·SmartArt·필드·변경 추적·메모 위치 | SmartArt·차트·그룹·동영상·노트 | — |

채우지 않는 칸은 빈 값(`""`, `[]`)으로 두고 이유를 `warnings`에 적습니다. `voice`, `kind`, `required`, `guide`, `length`, `update`, `conflicts`는 스크립트가 채우지 않습니다.

## locator와 anchor

locator 문법은 설계서 §5입니다. 섹션 `anchor`는 형식마다 하나로 정합니다.

| 형식 | anchor | 예 |
|---|---|---|
| DOCX | 문단 번호 `p:N` | `p:12` |
| PPTX | 슬라이드 `sl:N` (섹션 하나 = 슬라이드 하나 이상) | `sl:3` |
| HWPX·MD | 제목 글 `h:"…"` | `h:"2. 추진 일정"` |

**문단 번호 `p:N` 세는 법.** 본문의 **최상위 문단**만 나오는 순서대로 1부터 셉니다. 표 안의 문단, 머리글·바닥글, 각주, 글상자 안의 문단은 세지 않습니다(글상자를 품은 본문 문단 자체는 셉니다). 빈 문단도 셉니다. `profile_extract.py`와 `format-docx`의 `patch_docx.py dump`가 같은 방식으로 세므로, 프로파일의 `p:12`와 skeleton의 `p:12`는 같은 문단입니다. 표 칸은 `t:N/r:R/c:C`로 따로 가리킵니다.

**제목 글 `h:"…"`.** 문서에 보이는 제목 글을 그대로 씁니다. 번호와 부호(`Ⅰ.`, `1.`, `□`)를 포함하고, 마크다운 표지(`#`, `**`)와 앞뒤 공백은 뺍니다. 같은 제목 글이 두 번 나오면 `h:"추진 일정"#2`처럼 몇 번째인지 붙입니다. 스크립트는 anchor를 풀 때 공백을 모두 빼고 문단 글 전체와 비교합니다(`h:"□ 현황"`과 `h:"□현황"`은 같음). HWPX는 `hp:p`마다 그 문단에 직접 속한 `hp:t` 글을 이어 붙인 것(표 칸 안 문단은 따로 한 문단), MD는 `#` 제목 줄의 글이 비교 대상입니다.

섹션 범위는 `anchor`부터 다음 섹션 `anchor` 바로 앞까지입니다. 그래서 anchor는 문서 순서대로 늘어서야 합니다.

## analyst가 채우는 칸

| 칸 | 채우는 법 |
|---|---|
| `voice.style·ending` | 견본 본문 문장 10개 이상을 보고 정합니다. 섞여 있으면 `혼합`이고, 어디서 무엇을 쓰는지 `guide`에 적습니다 |
| `voice.terms` | 견본이 일관되게 쓰는 용어만. 한 번 나온 말은 넣지 않습니다 |
| `sections[].kind` | 섹션 본문이 주로 무엇인지: 서술·목록·표·도표·칸 |
| `sections[].required` | sample 모드는 견본에 있는 섹션 모두 `true`. 견본 안 안내문이 「해당 시 작성」이라고 하면 `false` |
| `sections[].guide` | 견본 글이 **하는 일**을 요약합니다(「사실(일자·건수)로 시작, 문제점 3개」). 견본 글을 옮기지 않습니다 |
| `sections[].length` | 견본 분량을 기준으로 범위를 둡니다. 줄(`lines`)·글자(`chars`)·장(`slides`)·쪽(`pages`) 가운데 그 형식이 잴 수 있는 것 |
| `fields[].constraint` | 칸 이름표와 주변 안내문에서 읽습니다(「한글 2~10자」, 「YYYY.MM.DD」). 안내가 없으면 비웁니다 |
| `update.sections·requests` | 갱신 요청을 섹션 id에 대응시킵니다. 요청이 여러 섹션에 걸치면 모두 적고, 대응할 섹션이 없으면 `conflicts`에 적습니다 |
| `conflicts` | 사용자 요청이 견본과 어긋나는 점. 항상 `handling: report` |

## 견본 문구 지문 (`sample_text`)

`doc-verify`의 `residue` 검사가 결과에 견본 글이 남았는지 볼 때 쓰는 목록입니다. **결과에 정당하게 남아야 하는 글은 넣지 않습니다.** 넣으면 올바른 결과가 실패합니다.

넣는 것:
- 내용 문장·구절: 견본에 예시로 채워진 본문, 표의 데이터 칸, 예시 수치·일자·기관명

빼는 것:
- 섹션 제목, 표 머리행 칸, 칸 이름표(「성명」, 「소속」), 쪽 번호·머리글
- `○○`만으로 된 토큰, 부호만 있는 줄
- 6자 미만의 짧은 글(「합계」, 「비고」처럼 결과에도 흔히 나오는 말)

DOCX·PPTX·MD는 스크립트의 `sample_text_candidates`(제목 스타일·표 머리행을 뺀 본문 글)에서 고르고, HWPX는 `parse_document` 결과에서 고릅니다. 문장이 길면 앞 20~40자의 구절 하나로 줄입니다. 지문은 찾기용이므로 문장 전체가 필요하지 않습니다.

## 프로파일 점검

`check`가 기계적으로 보는 것과 analyst가 눈으로 보는 것으로 나뉩니다. 둘 다 통과해야 보고합니다.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/profile_extract.py" check .docu-writer/profile.yaml \
  --source <견본> --tables .docu-writer/work/tables.yaml
```

**`check`가 보는 것** (실패하면 종료 코드 1):
- YAML로 읽히고 `profile_version: 1`, `mode`가 sample·form·update 가운데 하나
- `source.sha256`이 견본 파일의 실제 값과 같음
- 섹션마다 `id·title·level·anchor·kind·required·guide·length`가 있고, `id`가 겹치지 않음
- anchor가 견본에서 풀리고(문단·슬라이드·제목 글이 있음) 문서 순서대로 늘어섬
- 모든 `t:N/r:R/c:C`가 표 목록 범위 안(`N ≤ 표 수`, `R ≤ rows`, `C ≤ cols`)
- form 모드는 `fields`가 하나 이상, update 모드는 `update.sections`의 id가 모두 섹션에 있고 `requests`가 비어 있지 않음
- `sample_text`에 `○○`만 있는 토큰, 6자 미만 글, 섹션 제목과 같은 글이 없음
- `guide` 글이 `sample_text`의 어느 항목도 포함하지 않음 (견본 글을 옮기지 않음)
- `conflicts[].handling`이 모두 `report`

**analyst가 보는 것**:
- 렌더로 확인할 수 없는 서체 이름·pt를 짐작해 적지 않았는가 (비우고 「확인 못 함」에 적음)
- `styles_allowed`에 실제로 쓰이지 않은 스타일이 섞이지 않았는가
- `structure.numbering`의 수준 순서가 견본 렌더에서 보이는 들여쓰기 순서와 같은가
- 편집 불가 개체(`objects`, 형식 스킬 「분석」)를 모두 보고 목록에 옮겼는가
