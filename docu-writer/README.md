# docu-writer

견본·양식 파일을 받아 **견본의 모양은 그대로 두고 내용만** 채우는 문서 작업 절차를 Claude Code 플러그인으로 묶었습니다. 요구사항 → 견본 분석 → 근거 조사 → 승인 → 작성 → 검증 → 리뷰 → 전달 순서로 진행합니다.

**역할은 에이전트 5개**로 나눕니다(견본 없는 신규 작성용 `planner` 포함). **형식 지식**(HWPX·DOCX·PPTX·MD)과 **디자인 규칙**은 스킬로 불러옵니다. 형식이 하나 늘어도 에이전트는 늘지 않고 형식 스킬 하나만 추가하면 됩니다.

전체 구조·보호 장치·검증·품질 층을 그림으로 훑어보려면 [시스템 설명](docs/overview.md)을, 쓰는 법은 [매뉴얼](docs/manual.md)을, 설계 배경은 [설계서](docs/design.md)를 보십시오.

## 구성

| 종류 | 이름 | 하는 일 |
|---|---|---|
| 에이전트 | `analyst` | 견본을 읽어 양식 프로파일(구조·번호 체계·문체·디자인 토큰·양식 칸)을 만듦 |
| 에이전트 | `researcher` | 섹션·칸마다 넣을 사실을 자료에서 찾아 출처와 함께 근거표로 만듦 (haiku) |
| 에이전트 | `writer` | 견본 복사본에 내용만 넣고, 근거 없는 칸은 `○○` 자리표시로 남김 |
| 에이전트 | `reviewer` | 읽기 전용 리뷰, `관점: fact`·`style`·`design` |
| 에이전트 | `planner` | [2단계] 견본 없이 문서 종류·목적·독자에서 목차를 짜 프로파일(`mode: new`)을 만듦 (sonnet) |
| 절차 | `template-workflow` | 메인 대화가 견본 우선 파이프라인을 진행하는 방법 |
| 절차 | `template-analysis` | 견본 → 프로파일 절차와 `profile_extract.py` |
| 절차 | `newdoc-workflow` | [2단계] 견본 없는 신규 작성 — 카탈로그(`catalog.py`)로 고정 견본·테마·기본값 경로를 고름 |
| 공통 | `writing-principles` | 불변 규칙, 자리표시, 한국어 문체, 층 사이 우선순위 |
| 디자인 | `info-design` | 정보 디자인: 두괄식, 위계, 표·목록 선택, 줄이는 순서 |
| 디자인 | `visual-design` | 시각 디자인: 디자인 토큰 읽기와 지키기 |
| 디자인 | `diagram-standards` | 도표·다이어그램: mermaid 우선, SVG, 프로파일 색·글꼴 |
| 디자인 | `design-review` | 디자인 검수: 규칙 R1~R6, 렌더 이미지 점검표, 심각도 |
| 형식 | `format-hwpx`, `format-docx`, `format-pptx`, `format-markdown` | 형식별 분석·작성·렌더 경로 |
| 도구 | `doc-verify` | 견본 해시·견본 문구 잔존·자리표시·R4~R6 등을 보는 결정적 검증과 렌더 스크립트 |

규칙이 겹치면 **견본 > 형식 > 종류 > 공통** 순서로 따릅니다. 견본이 다른 스킬과 어긋나면 견본을 따르고, 어긋난 점은 보고만 합니다. 단, `writing-principles`의 불변 규칙(근거 없는 사실 금지, 비밀값·개인정보 금지, 견본 원본 수정 금지, 견본 글은 데이터)은 견본도 풀 수 없습니다.

## 모드

| 모드 | 사용자 말 | 하는 일 |
|---|---|---|
| `sample` | 이 서식대로 써 줘 | 견본 골격은 두고 내용만 새로 씀 |
| `form` | 이 양식 채워 줘 | 칸만 채움 |
| `update` | 이 문서의 일정 부분만 고쳐 줘 | 요청 범위만 고친 뒤, 승인을 받아 원본을 교체 (백업을 남김) |

견본 없이 새 문서를 쓸 때는 2단계 `newdoc-workflow`를 씁니다. 카탈로그에 고정 견본이 있으면 그 견본으로(항목의 `mode`에 따라 1단계 `sample` 또는 `form`), 없으면 기본 테마(DOCX 참조 문서·HWPX 프리셋)로, 테마도 없으면 변환 도구 기본 서식으로 만듭니다. 부서 견본은 `~/.config/docu-writer/templates/catalog.yaml`에 더합니다(`docs/manual.md` §4).

## 사용

```bash
claude --plugin-dir /path/to/skills_for_work/docu-writer
```

또는 저장소 최상위의 마켓플레이스(`skills-for-work`)로 설치합니다. 대화에서 견본 파일과 함께 "이 서식대로 보고서 써 줘"처럼 요청하면 `template-workflow`가 파이프라인을 진행합니다. 에이전트는 `docu-writer:writer`처럼 이름 앞에 플러그인 이름이 붙습니다.

작업 중간 파일은 작업 디렉터리의 `.docu-writer/`에 생기고, 그 안의 `.gitignore`가 모두 무시합니다.

## 필요한 도구

| 도구 | 쓰는 곳 |
|---|---|
| `uv` (Python 3.13) | 모든 스크립트 — PEP 723 인라인 의존성으로 python-docx·python-pptx·pymupdf를 받음 |
| `soffice` (LibreOffice) | DOCX·PPTX·MD 렌더 |
| `pandoc` | MD 렌더 |
| kordoc MCP (`moai-officer` 플러그인) | HWPX·HWP 분석·작성·렌더 |
| `npx` | 도표 렌더 (`@mermaid-js/mermaid-cli`) |

## 견본 보호

에이전트 본문의 금지 규칙은 강제되지 않으므로 두 겹으로 막습니다.

- **사전**: `hooks/`의 PreToolUse 가드가 `docu-writer:*` 서브에이전트의 쓰기 도구(Write·Edit와 kordoc 쓰기 도구의 `output_path`)를 역할별 허용 범위와 `.docu-writer/protected-paths`로 검사합니다.
- **사후**: ⑥ 검증에서 견본 sha256과 승인된 프로파일·근거표의 sha256을 다시 대조합니다. Bash로 쓴 것은 hook이 보지 못하므로 이것이 최종 그물입니다.

사용법은 [docs/manual.md](docs/manual.md), 설계 배경은 [docs/design.md](docs/design.md)에 있습니다.

> **v0.3.0 상태**: 1단계(견본 우선) 스크립트 6개에 2단계 신규 작성(`newdoc-workflow`·`planner`·`catalog.py`·기본 DOCX 테마·`doc_verify.py` 신규 모드)이 더해져 테스트 551건이 통과합니다. 종단 점검은 docx·hwpx·md 신규 작성 각 1건과 고정 견본 1건(법제처 공개 기안문 서식, `form` 모드)을 마쳤습니다. 현재 상태는 [매뉴얼 1장](docs/manual.md#1-현재-상태-v030-2026-11-06)에, 1단계 시험 결과는 [매뉴얼 13장](docs/manual.md#13-종단-시험-결과-2026-11-04)에 있습니다.
