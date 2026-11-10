# skills-for-work

[English](#english) · [한국어](#한국어)

A Claude Code plugin marketplace for everyday work: shipping code, writing documents, and writing hands-on IT books.

---

## English

### Why

These plugins grew out of building a multi-agent system ([Server Guardian](https://github.com/yarang/server-guardian-public)). Along the way I needed tools around it — a fixed process for writing code, a way to produce documents that follow a template, and a pipeline for writing a book — so I built them on the same principles:

- **No single decider.** The agent that implements never reviews its own work. Reviews go to a different model with the same criteria, scope, and severity table.
- **Guardrails in code, not just prompts.** Write-guard hooks keep each role inside its own paths.
- **Expensive decisions belong to a person.** Plans and designs wait for human approval before work starts.

The core structure is **roles as agents, knowledge as skills**. Each plugin splits work into role agents with clear inputs, outputs, and permissions. Domain knowledge (languages, frameworks, document formats) loads as a skill only when a task needs it.

### Plugins

| Plugin | What it does | Agents | Skills |
|---|---|---|---|
| [`work-standards`](developer/) | Development pipeline: research → design → tests first → implement → verify → review → docs. Stack skills for Python, TypeScript, Rust, Go, React, FastAPI, axum, Tauri, MCP servers | 6 | 18 |
| [`docu-writer`](docu-writer/) | Template-first documents. Extracts a profile from your sample (HWPX, DOCX, PPTX, Markdown), changes only the content, and checks rendered pages against design rules | 5 | 14 |
| [`book-writer`](book-writer/) | Six-stage pipeline for hands-on IT books: story → content → outline → draft → review → done, with human approval gates | 5 | 5 |
| [`shared`](shared/) | Review packets and runners for external reviewer models (Antigravity, EXAONE) | — | 1 |

`work-standards` and `book-writer` use `shared` for external review, so install it with them.

### Install

```
claude plugin marketplace add yarang/skills-for-work
claude plugin install work-standards@skills-for-work
claude plugin install shared@skills-for-work
```

Install `docu-writer` or `book-writer` the same way. Each plugin's README lists the tools it needs (for example, `docu-writer` uses `uv`, LibreOffice, `pandoc`, and the kordoc MCP for HWPX).

### Language

Skills and agent prompts are written in **Korean**, because they target Korean writing conventions and formats such as HWPX. The structure carries over to any language.

### Design records

`docs/` keeps the design plans, work briefs, and review records behind each change.

### License

MIT — see [LICENSE](LICENSE).

---

## 한국어

### 만든 이유

이 플러그인들은 멀티 에이전트 시스템([Server Guardian](https://github.com/yarang/server-guardian-public))을 만들다가 필요해서 추가로 만든 것들입니다. 정해진 절차로 코드를 짜고, 견본을 따르는 문서를 만들고, 책을 쓰는 도구가 필요했습니다. 그래서 같은 원칙으로 만들었습니다.

- **혼자 결정하지 않습니다.** 구현한 에이전트는 자기 결과를 검토하지 않습니다. 검토는 다른 모델이 같은 기준·범위·심각도 표로 합니다.
- **안전장치는 프롬프트만이 아니라 코드로 둡니다.** 쓰기 가드 hook이 역할마다 쓸 수 있는 경로를 제한합니다.
- **되돌리기 비싼 결정은 사람이 합니다.** 계획과 설계는 사람이 승인해야 작업이 시작됩니다.

핵심 구조는 **역할은 에이전트로, 지식은 스킬로**입니다. 플러그인마다 일을 역할 에이전트로 나누고, 역할마다 입력·산출물·권한을 정했습니다. 언어·프레임워크·문서 형식 같은 분야 지식은 필요할 때만 스킬로 불러옵니다.

### 플러그인

| 플러그인 | 하는 일 | 에이전트 | 스킬 |
|---|---|---|---|
| [`work-standards`](developer/) | 조사 → 설계 → 테스트 먼저 → 구현 → 검증 → 리뷰 → 문서 개발 파이프라인. Python·TypeScript·Rust·Go·React·FastAPI·axum·Tauri·MCP 서버 스킬 | 6 | 18 |
| [`docu-writer`](docu-writer/) | 견본을 먼저 따르는 문서 작성. HWPX·DOCX·PPTX·Markdown 견본에서 양식을 뽑아 내용만 바꾸고, 렌더 결과를 디자인 규칙으로 검수 | 5 | 14 |
| [`book-writer`](book-writer/) | 실습형 IT 교재를 스토리 → 내용 → 구조 → 집필 → 검토 → 완료 6단계로 진행. 사람 승인 관문 포함 | 5 | 5 |
| [`shared`](shared/) | 외부 리뷰 모델(Antigravity, EXAONE)용 검토 꾸러미와 실행기 | — | 1 |

`work-standards`와 `book-writer`는 외부 검토에 `shared`를 쓰므로 함께 설치합니다.

### 설치

```
claude plugin marketplace add yarang/skills-for-work
claude plugin install work-standards@skills-for-work
claude plugin install shared@skills-for-work
```

`docu-writer`, `book-writer`도 같은 방법으로 설치합니다. 플러그인마다 필요한 도구는 각 README에 있습니다(예: `docu-writer`는 `uv`, LibreOffice, `pandoc`, HWPX용 kordoc MCP).

### 언어

스킬과 에이전트 본문은 **한국어**로 썼습니다. 한국어 표기 규칙과 HWPX 같은 국내 문서 형식을 다루기 때문입니다. 구조는 다른 언어에도 그대로 옮겨 쓸 수 있습니다.

### 설계 기록

`docs/`에 변경마다의 설계 계획, 작업 지시서, 검토 기록을 남겨 두었습니다.

### 라이선스

MIT — [LICENSE](LICENSE)를 보십시오.
