# docu-writer 사용 매뉴얼

견본·양식 파일을 주면 **견본의 모양은 그대로 두고 내용만** 채워 주는 Claude Code 플러그인입니다. 이 매뉴얼은 설치, 요청하는 법, 중간에 사용자가 답할 곳, 결과를 읽는 법을 다룹니다. 설계 배경은 [design.md](design.md)에 있습니다.

## 1. 현재 상태 (v0.1.0, 2026-11-04)

> **아직 끝까지 돌릴 수 없습니다.** 규칙 문서(스킬 13개·에이전트 4개)와 수용 테스트 171건은 준비됐습니다. 그러나 파이프라인이 부르는 스크립트 6개가 아직 없습니다. 스크립트 구현은 zai(opencode) 에이전트에 맡기는데, 인증이 실패해 멈춰 있습니다.

![구현 상태](diagrams/implementation-status.svg)

| 구분 | 항목 | 상태 |
|---|---|---|
| 규칙 | 에이전트 4개, 스킬 13개(newdoc은 자리만) | 완료 |
| 테스트 | `tests/` 6개 파일, 171건 | 작성 완료. 현재 49 통과 · 104 실패 · 18 오류 (통과는 거짓 양성, 10장) |
| 스크립트 | `hooks/write_guard.py`·`hooks.json`, `profile_extract.py`, `patch_docx.py`, `patch_pptx.py`, `render.py`, `doc_verify.py` | **없음** |
| 시험 | HWPX·DOCX·PPTX × sample·form·update 종단 시험 | 대기 |
| 리뷰·배포 | codex·agy 리뷰, git.agentthread.dev push | 대기 |

스크립트가 없는 지금 할 수 있는 것과 없는 것은 다음과 같습니다.

- **할 수 있음**: ① 요구사항·모드 판별, ③ 근거 조사(researcher는 스크립트를 쓰지 않음). HWPX의 작성·렌더 자체는 kordoc MCP가 맡으므로 스크립트 없이도 돕니다.
- **할 수 없음**: ② 견본 분석. 형식과 상관없이 표 번호 목록(`profile_extract.py tables`)과 프로파일 점검(`check`)이 필요합니다. DOCX·PPTX 작성(`patch_*.py`)과 ⑥ 결정적 검증(`doc_verify.py`)도 없습니다. ②·⑥은 생략할 수 없는 단계라서 **어떤 형식이든 끝까지 통과하지 못합니다.**
- **견본 보호**: hook이 없으므로 사전 차단이 없습니다. 견본은 반드시 복사본을 주십시오.

## 2. 설치

**방법 A — 플러그인 하나만 시험할 때**

```bash
claude --plugin-dir <이 저장소>/docu-writer
```

**방법 B — 마켓플레이스로 설치할 때.** Claude Code 대화창에서 저장소 최상위를 마켓플레이스로 더한 뒤 설치합니다. `work-standards`(developer)도 같은 마켓플레이스에 있습니다.

```text
/plugin marketplace add <이 저장소>
/plugin install docu-writer@skills-for-work
```

설치되면 에이전트는 `docu-writer:analyst`처럼, 스킬은 `docu-writer:template-workflow`처럼 이름 앞에 플러그인 이름이 붙습니다.

## 3. 필요한 도구

| 도구 | 쓰는 곳 | 확인 명령 |
|---|---|---|
| `uv` (Python 3.13) | 모든 스크립트 | `uv --version` |
| LibreOffice `soffice` | DOCX·PPTX·MD 렌더 | `soffice --version` |
| `pandoc` | MD 렌더 | `pandoc --version` |
| kordoc MCP (`moai-officer` 플러그인) | HWPX·HWP 분석·작성·렌더 | 대화에서 `/mcp` 목록에 kordoc |
| `npx` | 도표 렌더 (`@mermaid-js/mermaid-cli`) | `npx -y @mermaid-js/mermaid-cli --version` |

Ghostscript는 필요 없습니다. PDF → PNG는 pymupdf가 맡습니다.

## 4. 빠른 시작

견본 파일 경로와 함께 평소 말로 요청하면 됩니다. 메인 대화가 `template-workflow` 스킬을 불러 모드를 정합니다.

| 하고 싶은 일 | 요청 예 | 모드 |
|---|---|---|
| 같은 서식으로 새 내용 쓰기 | 「`~/견본/주간보고.hwpx` 서식대로 11월 1주 주간보고 써 줘. 자료는 `~/자료/11월/`에 있어」 | `sample` |
| 양식 빈칸 채우기 | 「`신청서.docx` 양식을 이 정보로 채워 줘: 성명 홍길동, 소속 …」 | `form` |
| 문서 일부만 고치기 | 「`사업계획.pptx`의 추진 일정 장만 12월 기준으로 고쳐 줘」 | `update` |

요청에 넣으면 질문이 줄어드는 것:

- **출력 경로** — 견본과 같은 경로는 안 됩니다. 이미 있는 파일 이름이면 다시 묻습니다.
- **자료 위치** — 폴더·파일. 웹 검색을 해도 되는지도 함께 적습니다.
- **분량·줄여도 되는 섹션** — 표가 한 쪽에 안 들어갈 때 무엇을 줄일지 정해 줍니다.

견본 없이 새 문서를 만드는 2단계(`newdoc`)는 아직 없습니다.

## 5. 진행 순서와 사용자가 할 일

사용자가 답하는 곳은 세 군데입니다. **① 질문, ④ 승인, ⑧ 원본 교체 승인(update 모드)**. 나머지는 메인 대화와 에이전트가 진행합니다.

![사용자 관점 흐름](diagrams/user-journey.svg)

| 단계 | 누가 | 사용자가 할 일 |
|---|---|---|
| ① 요구사항·모드 판별 | 메인 대화 | 모드·출력 경로·자료 위치 질문에 답함 |
| ② 견본 분석 | analyst | 없음 |
| ③ 근거 조사 | researcher | 없음 |
| ④ 승인 | 사용자 | 승인 화면을 읽고 승인하거나 고칠 점을 말함 |
| ⑤ 작성 | writer | 없음 |
| ⑥ 검증 | 메인 대화 + 스크립트 | 없음 (실패하면 ⑤로 자동 되돌림) |
| ⑦ 리뷰 | reviewer × 3 | 없음 (같은 지적이 세 번 반복되면 보고받음) |
| ⑧ 전달 | 메인 대화 | 결과 확인. update 모드면 원본 교체 여부를 따로 답함 |

### 5.1 ④ 승인 화면 읽는 법

승인 전에는 작성(⑤)으로 넘어가지 않습니다. 한 번에 다음을 보여 줍니다.

| 항목 | 볼 점 |
|---|---|
| 모드·견본·출력 경로 | 의도와 맞는가 |
| 섹션 표 (id · 제목 · kind · 분량 · 근거 수 · 근거 없음) | 「근거 없음」이 많은 섹션은 자리표시 `○○`로 남습니다. 값을 알면 이때 알려 주십시오 |
| form 모드의 칸 표 | 칸마다 들어갈 값과 제약 |
| 비운 디자인 토큰, 편집 불가 개체 | 글상자·필드·SmartArt처럼 손대지 못하는 것 |
| 충돌 | 요청과 견본이 어긋난 곳. 견본을 따르며, 견본에 없는 섹션은 추가하지 않습니다 |
| 자리표시 예정 | 남을 칸과 이유 |

고칠 점을 말하면 메인 대화가 `profile.yaml`·`evidence.yaml`을 고치고 다시 보여 줍니다. 승인하면 두 파일의 해시를 `approved.sha256`에 고정하고, 이후 에이전트가 바꾸면 ⑥·⑦에서 잡힙니다.

### 5.2 ⑧ 결과 보고 읽는 법

| 받는 것 | 뜻 |
|---|---|
| 결과 파일 경로, 쪽별 미리보기 | 1~3쪽 PNG를 대화에 직접 보여 줍니다 |
| 남은 자리표시 표 | `○○`로 남은 칸. 근거가 없어 지어내지 않은 곳입니다 |
| 줄인 내용 | 표를 한 쪽에 넣으려고 줄인 문장 |
| 적용하지 못한 편집, 편집 불가 개체 안내 | 예: 「Word에서 목차 필드 업데이트」, 「차트 데이터는 PowerPoint에서 수정」 |
| 남은 MEDIUM·LOW 지적 | CRITICAL·HIGH는 ⑤로 되돌려 고친 뒤라 남지 않습니다 |
| 근사 렌더 안내 | HWPX는 「한컴에서 쪽 나눔 확인 권장」 |

검증 결과의 원본은 `.docu-writer/verify/report.json`입니다. 검사 12개가 언제나 모두 들어가며 `status`는 넷 중 하나입니다.

| status | 뜻 |
|---|---|
| `pass` | 통과 |
| `fail` | 차단. 하나라도 있으면 종료 코드 1, ⑤로 되돌림 |
| `warn` | 의심. 예: 표가 쪽 경계에 걸렸을 수 있음(`r1_tables`) → ⑦에서 사람 눈(리뷰어)이 판정 |
| `skip` | 해당 없음. 예: MD에는 서체·쪽 정보가 없음 |

### 5.3 update 모드 — 원본 교체와 되돌리기

에이전트는 어느 모드에서도 원본에 쓰지 않습니다. 고친 결과는 먼저 `.docu-writer/work/<이름>.updated.<확장자>`에 생깁니다. ⑧에서 원본 경로·백업 경로·바뀐 섹션을 보여 주고 **따로 승인을 받은 뒤에만** 메인 대화가 교체합니다.

교체할 때는 순서대로 다음을 합니다.

1. 원본이 ① 이후 바뀌지 않았는지 해시로 확인합니다. 다르면 멈추고 보고합니다(다른 사람이 고쳤을 수 있음).
2. 원본을 `.docu-writer/backup/이름.시각.확장자`로 복사합니다. 예: `사업계획.20261104-153012.pptx`
3. 결과로 원본을 덮고 두 해시가 같은지 확인합니다.

되돌리려면 백업을 원본 경로로 복사합니다.

```bash
cp -p ".docu-writer/backup/사업계획.20261104-153012.pptx" "/경로/사업계획.pptx"
```

## 6. 작업 디렉터리 `.docu-writer/`

작업을 시작한 디렉터리에 `.docu-writer/`가 생깁니다. 안의 `.gitignore`가 전부 무시하므로 저장소에 올라가지 않습니다.

![작업 디렉터리 파일](diagrams/workdir-files.svg)

| 파일 | 만드는 단계 | 내용 |
|---|---|---|
| `session.yaml` | ① | 모드, 견본 경로와 sha256, 출력 경로 |
| `protected-paths` | ① | 에이전트가 쓰면 안 되는 경로(견본 등) |
| `profile.yaml` | ② | 양식 프로파일: 구조·번호 체계·문체·디자인 토큰·칸 |
| `evidence.yaml` | ③ | 섹션·칸별 근거와 출처 |
| `approved.sha256` | ④ | 승인 시점의 profile·evidence 해시 |
| `placeholders.yaml` | ⑤ | 남긴 자리표시 목록 |
| `work/` | ②·⑤ | 표 추출, 골격, 편집 목록, update 결과 |
| `render/` | ②·⑥ | 쪽별 PNG·SVG, `pages.json`. `render/source/`는 견본 렌더 |
| `verify/` | ⑥ | `report.json`, `output.sha256` |
| `backup/` | ⑧ | update 모드 원본 백업 |

작업이 끝나면 지워도 됩니다. 단, update 모드의 `backup/`은 되돌릴 일이 없을 때까지 두십시오.

## 7. 형식별 주의

| 형식 | 경로 | 주의 |
|---|---|---|
| HWPX | kordoc MCP (`patch_document`·`fill_form`·`render_document`) | kordoc 렌더는 근사입니다. 최종 쪽 나눔은 한컴오피스에서 확인하십시오. `<결과>.rewrite.hwpx`가 생기면 제자리 반영에 실패한 것이라 ⑥이 막습니다 |
| HWP | kordoc `convert_to_hwpx`로 바꾼 뒤 HWPX와 같음 | 결과는 HWPX로 나옵니다. 원본 HWP와 변환본 해시를 둘 다 대조합니다 |
| DOCX | `patch_docx.py` (구현 예정) | 글상자·필드·SmartArt는 고치지 못하고 보고만 합니다. 목차는 Word에서 필드 업데이트가 필요합니다 |
| PPTX | `patch_pptx.py` (구현 예정) | 차트 데이터·SmartArt는 PowerPoint에서 고쳐야 합니다. 발표자 노트는 ④에서 내용으로 다룰지 정합니다 |
| Markdown | 직접 편집, 렌더는 pandoc → soffice | 쪽 개념이 없어 쪽·서체 검사는 `skip`입니다 |
| PDF | 견본으로만 읽음 | 고칠 수 없습니다. 원본(HWPX·DOCX 등)을 주십시오 |

## 8. 디자인 규칙 R1~R6

결과물은 다음 여섯 규칙으로 검수합니다. 정본은 `skills/design-review/SKILL.md`입니다.

| 규칙 | 내용 | 검사 |
|---|---|---|
| R1 | 표는 한 쪽 안에 표시합니다. 넘치면 **내용을 줄입니다** | 스크립트(의심) + 리뷰어(판정) |
| R2 | 표·글상자 크기는 가능하면 쪽 안에 모두 들어가야 합니다 | 리뷰어 |
| R3 | 고아 줄을 최대한 줄입니다 | 리뷰어 |
| R4 | 같은 수준의 제목은 같은 크기·서체로 표현합니다 | 스크립트 |
| R5 | 문서 전체의 양식(서체·크기·색·표 서식·여백)을 통일합니다 | 스크립트 + 리뷰어 |
| R6 | 글 번호 양식을 통일합니다 | 스크립트 |

**글자 크기나 여백을 줄여서 맞추지 않습니다.** 표를 한 쪽에 넣으려고 토큰을 바꾸면 R5 위반입니다.

## 9. 스크립트 직접 실행 (구현 예정)

> 아래 스크립트는 아직 없습니다. 계약(인자·종료 코드)은 확정돼 있고 `tests/`가 그 계약을 검사합니다.

플러그인 안에서는 `${CLAUDE_SKILL_DIR}`가 각 스킬 디렉터리를 가리킵니다. 직접 실행할 때는 실제 경로로 바꿉니다.

```bash
# 견본 표 추출과 프로파일 점검 (template-analysis)
uv run template/skills/template-analysis/scripts/profile_extract.py tables <견본> > .docu-writer/work/tables.yaml
uv run template/skills/template-analysis/scripts/profile_extract.py check .docu-writer/profile.yaml \
  --source <견본> --tables .docu-writer/work/tables.yaml

# DOCX·PPTX 골격 덤프와 편집 적용 (format-docx / format-pptx)
uv run skills/format-docx/scripts/patch_docx.py dump <견본.docx> --out .docu-writer/work/skeleton.yaml
uv run skills/format-docx/scripts/patch_docx.py apply <견본.docx> \
  --edits .docu-writer/work/edits.yaml --profile .docu-writer/profile.yaml --out <결과.docx>

# 렌더와 검증 (doc-verify)
uv run skills/doc-verify/scripts/render.py <결과 파일> .docu-writer/render/
uv run skills/doc-verify/scripts/doc_verify.py \
  --profile .docu-writer/profile.yaml \
  --source <견본> --expect-sha256 <①에서 기록한 값> \
  --output <결과 파일> \
  --placeholders .docu-writer/placeholders.yaml \
  --pages-dir .docu-writer/render/ \
  --out-dir .docu-writer/verify/
```

| 종료 코드 | 뜻 |
|---|---|
| 0 | 통과 (`doc_verify`는 `warn`·`skip`만 있을 때) |
| 1 | 차단. `patch_*`는 파일을 쓰지 않음, `doc_verify`는 `fail`이 있음 |
| 2 | 사용법·환경 오류(경로 없음, 도구 없음, 출력 파일이 이미 있음). **통과가 아닙니다** |

## 10. 개발자용 — 테스트

```bash
cd <이 저장소>/docu-writer
uv run --python 3.13 --with pytest,python-docx,python-pptx,pyyaml,lxml,pymupdf pytest tests
```

2026-11-04 실행 결과는 `104 failed, 49 passed, 18 errors`입니다. 스크립트가 없는 RED 단계라 실패는 정상입니다.

**통과 49건은 믿으면 안 됩니다.** 모두 「거부되는가(종료 코드 ≠ 0 또는 2)」를 보는 테스트입니다. 예를 들어 `test_write_guard.py`의 차단 테스트, 각 스크립트의 `exit_2` 테스트가 그렇습니다. 그런데 `uv run`은 스크립트 파일이 없어도 종료 코드 2로 끝나므로 이 테스트들이 저절로 통과합니다. 스크립트가 들어온 뒤의 결과만 의미가 있습니다. 해결하려면 `conftest.py`에서 스크립트 파일이 있는지 먼저 확인하고, 없으면 실패시키면 됩니다.

스크립트별 작업 지시서(zai 위임용)는 [briefs/](briefs/)에 있습니다.

| 지시서 | 대상 |
|---|---|
| `brief_hook.md` | `hooks/write_guard.py`, `hooks/hooks.json` |
| `brief_pe.md` | `profile_extract.py` |
| `brief_pd.md` | `patch_docx.py` |
| `brief_pp.md` | `patch_pptx.py` |
| `brief_rv.md` | `render.py`, `doc_verify.py` |

## 11. 문제 해결

| 증상 | 원인과 조치 |
|---|---|
| 「스크립트를 찾을 수 없음」 | 현재 v0.1.0에는 스크립트가 없습니다(1장). 스크립트가 들어올 때까지 파이프라인은 ②에서 멈춥니다 |
| HWPX 작업이 시작되지 않음 | kordoc MCP가 연결되지 않았습니다. `moai-officer` 플러그인을 켜고 `/mcp`로 확인하십시오 |
| DOCX·PPTX 렌더 실패 (종료 코드 2) | `soffice`가 PATH에 없습니다. LibreOffice를 설치하십시오 |
| 결과에 `○○`가 많음 | 근거 자료가 부족합니다. ④에서 값을 직접 주거나 자료 위치를 더 알려 주십시오 |
| 같은 지적으로 멈춤 | ⑦에서 같은 지적이 세 번 반복되면 멈추고 보고합니다. 견본 자체의 한계(예: 표 칸 부족)인 경우가 많습니다 |
| update 교체가 거부됨 | ① 이후 원본이 바뀌었습니다. 다른 사람이 고친 것인지 확인한 뒤 처음부터 다시 하십시오 |
| zai 「身份验证失败」 | Z.AI 인증 만료입니다. 터미널에서 `opencode auth login`으로 다시 로그인하십시오 |

## 12. 제한 사항

- 견본 없이 새 문서를 쓰는 `newdoc`은 자리만 있습니다.
- 렌더는 근사입니다. HWPX는 한컴, DOCX는 Word에서 최종 확인이 필요합니다.
- hook은 `Bash`로 쓰는 파일을 보지 못합니다. 그래서 ⑥의 해시 대조가 최종 방어선입니다.
- 견본 서식을 바꾸는 일(서체 변경, 섹션 추가)은 하지 않습니다. 견본과 요청이 충돌하면 견본을 따르고 보고만 합니다.
