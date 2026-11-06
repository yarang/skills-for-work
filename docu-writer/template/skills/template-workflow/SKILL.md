---
name: template-workflow
description: 견본·양식 파일이 주어진 문서 작업(견본 따라 쓰기, 양식 채우기, 기존 문서 갱신)을 요구사항 → 견본 분석 → 근거 조사 → 승인 → 작성 → 검증 → 리뷰 → 전달 파이프라인으로 진행할 때 사용합니다. 메인 대화가 docu-writer 에이전트(analyst, researcher, writer, reviewer)에게 일을 나눠 맡기고, 모드 판별·승인 관문·렌더·원본 교체를 맡는 절차입니다.
when_to_use: '"이 서식대로 써줘", "이 양식 채워줘", "견본처럼 만들어줘", "이 보고서 일정 부분만 고쳐줘", HWPX·HWP·DOCX·PPTX·MD 견본 파일이 함께 주어진 문서 작성'
---

# 견본 우선 문서 워크플로

메인 대화가 이 절차를 따릅니다. 에이전트는 역할(권한)로만 나뉘고, 형식 지식은 형식 스킬로, 디자인 규칙은 공유 스킬로 불러옵니다. 에이전트 본문의 금지 규칙은 강제되지 않으므로 메인 대화가 **hook(사전)과 해시 대조(사후)**로 확인합니다.

견본이 없는 신규 작성은 2단계(`newdoc`)이며 아직 준비 중입니다. PDF 견본은 편집할 수 없으므로 ①에서 사용자에게 알립니다.

## 파이프라인

```
① 요구사항·모드 판별 (메인) → ② analyst (견본 → 프로파일)
→ ③ researcher (섹션·칸별 근거) → ④ 승인 (사용자)
→ ⑤ writer (견본 복사본에 패치) → ⑥ 검증 (메인: 해시 + 렌더 + doc-verify)
→ ⑦ reviewer(fact) + reviewer(style) + reviewer(design) → ⑧ 전달 (메인)
```

| 단계 | 담당 | 넘기는 것 | 받는 것 |
|---|---|---|---|
| ① 요구사항 | 메인 대화 | — | 견본 경로, 모드, 출력 경로, 자료 위치, 견본 해시 (`session.yaml`) |
| ② 분석 | `docu-writer:analyst` | 견본 + 모드 + 형식 스킬 | `profile.yaml`, 견본 렌더, 편집 불가 개체 |
| ③ 조사 | `docu-writer:researcher` | 섹션·칸 목록 + 자료 위치 | `evidence.yaml`, 근거 없음 목록 |
| ④ 승인 | 사용자 | 프로파일 요약 + 근거 요약 + 충돌 + 자리표시 예정 | 승인 또는 수정 |
| ⑤ 작성 | `docu-writer:writer` | 형식 스킬 + 출력 경로 + 사용자 지시 | 결과 파일, `placeholders.yaml`, 자체 doc-verify 결과 |
| ⑥ 검증 | 메인 대화 (스크립트) | 견본, 결과, 프로파일 | 통과/실패 (사실), 쪽별 PNG |
| ⑦ 리뷰 | `docu-writer:reviewer` ×3 | 결과 + 관점 + 스킬 목록 | 심각도별 지적 |
| ⑧ 전달 | 메인 대화 | — | 결과 파일, 미리보기, 남은 자리표시, (update) 원본 교체 |

## 작업 디렉터리 `.docu-writer/`

메인 대화의 작업 디렉터리(cwd)에 둡니다. ①에서 만들고, 자체 `.gitignore`로 무시합니다.

```
.docu-writer/
├── .gitignore          # *
├── protected-paths     # 견본 원본 절대 경로 — hook이 읽음
├── session.yaml        # ① 기록
├── approved.sha256     # ④ 승인 시점의 profile·evidence 해시
├── profile.yaml        # ② analyst  (④ 승인 대상)
├── evidence.yaml       # ③ researcher (④ 승인 대상)
├── placeholders.yaml   # ⑤ writer
├── work/               # 중간 파일: 변환한 HWPX, skeleton·edits.yaml, 표 서식
├── render/             # ⑥ 결과 쪽별 PNG·SVG, pages.json
│   └── source/         # ② 견본 렌더 1~3쪽
├── verify/             # doc_verify.py 출력 (report.json)
└── backup/             # ⑧ update 모드 원본 백업
```

## ① 요구사항·모드 판별

서브에이전트는 사용자에게 되물을 수 없으므로, 모호함은 여기서 모두 풉니다.

1. **모드를 정합니다.** 파일만 보고 정하지 않습니다. 같은 DOCX라도 「서식만 참고할 견본」인지 「채울 양식」인지 사용자만 압니다.

   | 사용자 말 | 모드 |
   |---|---|
   | 이 서식대로·견본처럼·참고해서 새로 써 줘 | `sample` |
   | 이 양식(신청서·서식) 빈칸 채워 줘 | `form` |
   | 이 문서의 ○○ 부분만 고쳐 줘 | `update` |

2. **형식과 도구를 확인합니다.** HWPX·HWP는 kordoc 도구(`mcp__plugin_moai-officer_kordoc__*`)가 있어야 합니다. 없으면 알리고 멈춥니다. DOCX·PPTX·MD는 `uv`, `soffice`, `pandoc`(MD)를 확인합니다.
3. **출력 경로를 정합니다.** 견본과 같은 경로는 안 됩니다. 이미 있는 파일이면 다른 이름을 받습니다(스크립트가 덮어쓰지 않음). update 모드의 출력은 `.docu-writer/work/<이름>.updated.<확장자>`이고, 원본 교체는 ⑧에서 따로 승인받습니다. kordoc은 숨김 경로에 쓰지 않으므로 HWPX는 `docu-writer-out/`에 낸 뒤 옮깁니다(`format-hwpx` 「kordoc 출력 경로」).
4. **자료 위치를 받습니다.** 파일·디렉터리 경로와, 웹 검색을 허용하는지(`웹: 허용 | 금지`, 기본 금지).
5. **기록합니다.**

```bash
mkdir -p .docu-writer/{work,render/source,verify,backup} && printf '*\n' > .docu-writer/.gitignore
realpath <견본> > .docu-writer/protected-paths          # HWP를 변환하면 원본 HWP도 한 줄 더
shasum -a 256 <견본>                                     # 값을 session.yaml에 적음
```

```yaml
# .docu-writer/session.yaml
source: { path: /abs/견본.hwpx, format: hwpx, sha256: … }
mode: sample
output: /abs/결과.hwpx
materials: [ /abs/자료/, "웹: 금지" ]
format_skill: docu-writer:format-hwpx
```

형식 스킬은 확장자로 정합니다: `.hwpx`·`.hwp` → `format-hwpx`, `.docx` → `format-docx`, `.pptx` → `format-pptx`, `.md` → `format-markdown`.

## 핸드오프 프롬프트

에이전트마다 프롬프트에 다음을 그대로 붙입니다. 파일 경로는 모두 절대 경로로 씁니다.

**② analyst**

```
## 견본
<절대 경로> (형식: <hwpx|docx|pptx|md>)

## 모드
<sample | form | update>

## 갱신 요청            (update일 때만)
- <사용자가 말한 변경 그대로>

## 불러올 스킬
- <format_skill>
```

**③ researcher**: 프로파일에서 섹션·칸 목록만 뽑아 넘깁니다. 디자인 토큰은 넘기지 않습니다.

```
## 조사 대상
| id | 제목 | kind | guide |
<profile.yaml의 structure.sections와 fields>

## 자료 위치
- <session.yaml materials 그대로, 웹 허용 여부 포함>
```

**⑤ writer**

```
## 출력 경로
<session.yaml output>

## 불러올 스킬
- <format_skill>
- docu-writer:diagram-standards     (프로파일에 kind: 도표 섹션이 있을 때)

## 사용자 지시
- <④에서 정한 것: 자리표시로 남길 칸, 노트를 내용으로 다룰지, 줄여도 되는 섹션 …>
```

**⑦ reviewer**: 같은 결과를 관점 3개로 **동시에** 부릅니다(한 메시지에 Agent 호출 3개).

```
관점: fact | style | design

## 결과 파일
<출력 경로>

## 불러올 스킬
- docu-writer:info-design                       (style)
- docu-writer:visual-design, <format_skill>     (design)
```

## ② → ④ 단계별 규칙

**② 분석**: analyst가 낸 「편집 불가 개체」와 「확인 못 함」은 ④에서 그대로 사용자에게 보여 줍니다. HWP 견본이면 analyst가 `.docu-writer/work/`에 HWPX로 바꾸고, 이후 단계의 견본은 그 HWPX입니다. 해시 대조는 원본 HWP와 변환본 둘 다 합니다.

**③ 조사**: 자료 위치가 없고 견본만 있으면(양식 채우기에서 사용자가 값을 대화로 준 경우) ③을 생략하고, 사용자가 준 값을 메인 대화가 `evidence.yaml` 형식으로 적습니다. 출처는 `source: 사용자 (대화, <날짜>)`입니다. 개인정보 값은 evidence에 적지 않고 kordoc `fields_file`용 JSON을 `.docu-writer/work/`에 따로 둡니다.

**④ 승인**: 아래를 한 번에 보여 주고 승인을 받습니다. 승인 전에는 ⑤로 넘어가지 않습니다.
- 모드, 견본, 출력 경로
- 섹션 표(id · 제목 · kind · 분량 · 근거 수 · 근거 없음)와 form 모드의 칸 표
- 비운 디자인 토큰, 편집 불가 개체, 충돌(견본 우선 — 추가하지 않음)
- 자리표시로 남을 칸과 이유. 사용자가 값을 주면 evidence에 `source: 사용자`로 더합니다.

사용자가 고치라고 하면 메인 대화가 `profile.yaml`·`evidence.yaml`을 고칩니다. 승인되면 해시를 고정합니다.

```bash
shasum -a 256 .docu-writer/profile.yaml .docu-writer/evidence.yaml > .docu-writer/approved.sha256.tmp \
  && mv .docu-writer/approved.sha256.tmp .docu-writer/approved.sha256
```

두 파일 중 하나라도 없으면 `shasum`이 실패하고 `approved.sha256`은 만들어지지 않습니다(한 줄만 적힌 해시 파일이 남지 않게 임시 파일을 거칩니다).

## 견본 보호 (②·③·⑤·⑦의 호출마다)

**사전 — hook.** 플러그인 hook이 `docu-writer:*` 서브에이전트의 쓰기 도구 호출을 검사합니다. 메인 대화는 검사하지 않습니다.

| 역할 | 허용되는 쓰기 |
|---|---|
| analyst | `.docu-writer/` 안 (`protected-paths`·`approved.sha256`·`session.yaml` 제외)과 kordoc 출력용 `docu-writer-out/` 안 (폴더가 링크면 막음) |
| planner | analyst와 같음 (2단계 `newdoc-workflow` ②) |
| researcher | `.docu-writer/evidence.yaml` |
| writer | `protected-paths`의 경로, `.docu-writer/protected-paths`·`approved.sha256`·`session.yaml`·`profile.yaml`·`evidence.yaml`을 뺀 곳 |
| reviewer | 없음 |

검사 대상 도구는 `Write`·`Edit`·`MultiEdit`와 kordoc 쓰기 도구(`patch_document`·`fill_form`·`generate_document`·`convert_to_hwpx`·`extract_profile`·`render_document`의 `output_path`)입니다. 경로는 실제 경로로 바꾼 뒤(없는 파일은 부모 디렉터리 기준, `../`·`/private` 심볼릭 링크 해소) 비교하고, 둘 다 있는 파일이면 같은 파일인지(하드 링크·대소문자)도 봅니다. 모르는 `docu-writer:*` 역할, 경로가 빠진 호출, 읽을 수 없는 입력은 막습니다.

**사후 — 해시.** hook은 `Bash`로 쓰는 것을 보지 못하고, 사용자 설정으로 꺼질 수 있습니다. 그래서 ⑥에서 스크립트로 다시 확인합니다. 이것이 최종 그물입니다.
- 견본: `doc_verify.py --expect-sha256` (`hash` 검사)
- 계약: `shasum -c .docu-writer/approved.sha256`

## ⑥ 검증

writer의 보고를 믿지 않고 메인 대화가 다시 실행합니다. 모두 종료 코드로 판정하며, 모델이 결과를 해석해 통과시키지 않습니다. 스크립트 경로를 얻으려면 먼저 `Skill` 도구로 `docu-writer:doc-verify`를 불러옵니다.

1. `shasum -c .docu-writer/approved.sha256` — 실패하면 writer가 계약 파일을 바꾼 것입니다. ⑤로 되돌리기 전에 사용자에게 diff를 보여 줍니다.
2. 렌더 — DOCX·PPTX·MD는 `doc-verify` 스킬의 `render.py`(이전 `page_*`·`pages.json`을 스스로 지우고 냄). HWPX는 먼저 `mkdir -p .docu-writer/render && find .docu-writer/render -maxdepth 1 -type f \( -name 'page*' -o -name pages.json \) -delete`로 writer가 남긴 렌더를 지운 뒤(zsh는 맞는 파일이 없는 `rm -f …/page*`를 오류로 멈추므로 `find`를 씁니다), kordoc `render_document`를 svg와 png로 작업 폴더의 `docu-writer-out/`에 내고 `.docu-writer/render/`로 옮깁니다(kordoc은 숨김 경로에 쓰지 않음 — `format-hwpx` 「렌더」). `render/source/`는 지우지 않습니다.
3. `doc_verify.py` — `doc-verify` 스킬의 「실행」 명령 그대로. 종료 코드 1이면 `fail` 목록을 붙여 ⑤로 되돌립니다. 2이면 원인(경로·도구)을 고쳐 다시 실행합니다. 2는 통과가 아닙니다.
4. 통과하면 결과 파일 해시를 남깁니다: `shasum -a 256 <결과 파일> > .docu-writer/verify/output.sha256`. ⑦ 뒤에 대조합니다.

## ⑦ 리뷰

reviewer 3개를 동시에 부르고, 끝나면 `shasum -c .docu-writer/approved.sha256 .docu-writer/verify/output.sha256`으로 계약 파일과 결과 파일을 다시 확인합니다. 결과 파일이 리뷰 중에 바뀌었으면 읽기 전용 위반입니다.

**되돌리기**: CRITICAL·HIGH가 나오면 지적 목록을 `## 사용자 지시`에 붙여 ⑤로 되돌립니다. 지적이 프로파일 자체(섹션 누락, 토큰 오류)를 문제 삼으면 ②로 되돌리고 ④를 다시 받습니다. 같은 지적이 세 번 되풀이되면 멈추고 사용자에게 보고합니다.

## ⑧ 전달

사용자에게 다음을 보고합니다.
- 결과 파일 경로와 쪽별 미리보기(PNG 1~3쪽은 직접 보여 줌)
- 남은 자리표시 표(`placeholders.yaml`), 「줄인 내용」, 적용하지 못한 편집, 편집 불가 개체 처리 안내(예: 「Word에서 목차 필드 업데이트」, 「차트 데이터는 PowerPoint에서 수정」)
- 남은 MEDIUM·LOW 지적
- 근사 렌더 안내: HWPX는 「한컴에서 열어 쪽 나눔 확인 권장」, DOCX는 R1·R3이 쪽 경계에 걸렸으면 「Word에서 확인 권장」

### update 모드 — 원본 교체

에이전트는 어느 모드에서도 원본에 쓰지 않습니다. 원본 교체는 메인 대화가 **사용자가 ⑧에서 따로 승인한 뒤에만** 합니다. 승인을 물을 때 원본 경로, 백업 경로, 바뀐 섹션을 보여 줍니다.

```bash
SRC=<원본 절대 경로>; OUT=.docu-writer/work/<이름>.updated.<확장자>
# 1. 원본이 ① 이후 바뀌지 않았는지 — 다르면 멈추고 보고 (다른 사람이 고쳤을 수 있음)
shasum -a 256 "$SRC"            # session.yaml의 sha256과 비교
# 2. 백업
B=$(basename "$SRC"); cp -p "$SRC" ".docu-writer/backup/${B%.*}.$(date +%Y%m%d-%H%M%S).${B##*.}"   # 이름.시각.확장자 — 백업도 바로 열림
# 3. 교체 후 확인
cp "$OUT" "$SRC" && shasum -a 256 "$OUT" "$SRC"
```

보고에 백업 경로를 적습니다. 되돌리기는 백업 파일을 원본 경로로 복사하면 됩니다.

## 단계를 줄여도 되는 경우

| 작업 | 생략 가능 |
|---|---|
| 양식 채우기이고 값을 사용자가 대화로 모두 줌 | ③ — 메인 대화가 `evidence.yaml`을 적음 |
| update 모드이고 바꿀 문구를 사용자가 그대로 줌 | ③ — 메인 대화가 사용자가 준 문구를 `evidence.yaml`에 적음, ⑦의 fact 관점 |
| Markdown이고 표·도표 없음 | ⑦의 design 관점 |

①의 모드 판별, ④ 승인, ⑥ 검증(해시·doc-verify)은 생략하지 않습니다. ③을 건너뛰어도 `evidence.yaml`은 있어야 합니다. 없으면 ④의 `shasum`이 실패하면서 `profile.yaml` 줄만 적어 근거가 잠기지 않습니다.
