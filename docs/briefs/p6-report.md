# P6 보고서: work-standards 문서 관리 역할 `documenter`와 ⑧-2 문서

> 작업 지시서: `docs/briefs/p6-documenter.md` · 근거: 계획서 §8 (2026-11-10 결정)
> 실행: Z.ai 구현 에이전트 (TDD — 쓰기 가드 테스트 먼저 작성, RED 확인 뒤 구현)

## 1. 만든·바꾼 파일 목록

### 만든 파일
| 파일 | 내용 |
|---|---|
| `developer/agents/documenter.md` | 문서 관리 역할. `repo` 모드(저장소 문서 갱신)·`kb` 모드(지식 저장소 초안). tools: Read, Write, Edit, Grep, Glob, Bash, Skill — wiki·Notion·MCP 쓰기 도구 없음. skills: `work-standards:repo-docs`, `work-standards:knowledge-sync`, `work-standards:stack-detection` |
| `developer/skills/repo-docs/SKILL.md` | 문서별 갱신 시기(README·MANUAL·CHANGELOG·하위 README), ADR 쓸 조건·형식·대체 규칙, 코드-문서 어긋남 찾는 법, 쓰지 않는 것 |
| `developer/skills/knowledge-sync/SKILL.md` | 지식 저장소에 둘 것, wiki(기술 참조)·Notion(업무 기록) 구분, 중복 확인, 출처, 올리지 않음(초안까지) |

### 바꾼 파일
| 파일 | 할 일 |
|---|---|
| `developer/hooks/write_guard.py` | `ROLES`에 `documenter` 추가, `h3_violation`에 role 기반 kb-outbox 예외(선택 파라미터), `h7_violation` 신규, 모듈 머리말 갱신 |
| `developer/hooks/tests/support.py` | `DOCUMENTER` 상수 추가 |
| `developer/hooks/tests/test_write_guard.py` | `H7DocumenterTestCase` 7건 추가 (구현 전 RED 확인) |
| `developer/hooks/hooks.json` | `description`에 documenter 쓰기 범위(H7) 추가 (매처 그대로) |
| `developer/skills/dev-workflow/SKILL.md` | ⑧-2를 흐름도·단계 표·본문 절·경계 확인 표 네 곳에 추가, ⑨에 문서 diff 한 줄 |
| `developer/docs/design.md` | §3 트리에 documenter·repo-docs·knowledge-sync, §4 흐름도·요점·경계 확인 표에 ⑧-2 |
| `developer/README.md` | 에이전트 목록에 documenter, "5개"→"6개", 구성 표에 스킬 2개 |
| `developer/.claude-plugin/plugin.json` | `version` 0.2.0→0.3.0, description "5개로"→"6개로" |

## 2. 쓰기 가드에 더한 규칙과 테스트

### 규칙 (H7 — `h7_violation`)
- **허용**: 저장소 루트 기준 이름이 `README`·`CHANGELOG`·`MANUAL`로 시작하는 파일(casefold 비교, 어느 디렉터리든, 확장자 무관), `docs/` 아래, `.work-standards/kb-outbox/` 아래.
- **거부**: `docs/designs/` 아래(승인된 설계서) — 이유에 규칙 이름·경로·대신할 행동(「물어볼 것」에 적기) 포함. 그 밖의 모든 경로(코드·테스트·설정) — 이유에 허용 범위와 대신할 행동 포함.
- **H3 예외**: `h3_violation(ctx, role=None)` — role이 `documenter`이고 대상이 `.work-standards/kb-outbox/` 아래일 때만 통과. developer·tester는 기존대로 H3 거부. 기존 호출(파라미터 없음)은 기존 판정 그대로.
- H3의 나머지(.git/, 저장소 밖, .env)는 documenter에도 그대로 적용.

### 테스트 (`H7DocumenterTestCase`, 7건)
| 테스트 | 기대 |
|---|---|
| `test_allows_document_paths` | README.md·sub/README.md·CHANGELOG.md·MANUAL.md·docs/a.md·docs/adr/0001-x.md·.work-standards/kb-outbox/x.md 허용 |
| `test_denies_non_document_paths` | docs/designs/x.md·src/a.py·tests/test_a.py·package.json·.work-standards/protected-paths·.env 거부 |
| `test_denies_designs_with_h7_reason` | docs/designs 거부 이유에 H7·경로·「물어볼 것」 |
| `test_allows_lowercase_readme` | readme.md 허용 (대소문자 무시) |
| `test_denies_outside_repository` | 저장소 밖 거부 (H3 적용) |
| `test_denies_dotdot_escape_from_docs` | docs/../src/a.py → src/a.py 로 정규화되어 거부 |
| `test_h3_allows_kb_outbox_only_for_documenter` | kb-outbox 예외는 documenter 전용, developer·tester는 H3 거부 |

## 3. 실행한 검증 명령과 결과

| 명령 | 결과 |
|---|---|
| `cd developer && uv run --with pytest pytest -q hooks/tests skills/verify/tests` (구현 전) | **78 passed** — 기준선. 이후 H7 테스트만 추가해 재실행: 5 failed(거부 계열, documenter 미구현으로 통과해버림) — 올바른 RED 확인 |
| 같은 명령 (구현 후) | **85 passed** (기존 78 + H7 7건, 실패 0) |
| `claude plugin validate developer` | 통과 (icon 경고·마켓플레이스 설치 줄 조언은 2026-11-03 검증 기록부터 있던 것) |
| `claude plugin validate .` | 통과 |
| `git diff -- developer/skills/dev-workflow/SKILL.md` | ⑧·⑧-1 절 본문은 변경 없음. ⑧-2는 흐름도·단계 표·본문·경계 확인 표 네 곳에 삽입. ⑨는 문서 diff 한 줄만 추가 |
| 수용 기준 3 (도구 목록) | documenter tools에 wiki·Notion·MCP 쓰기 도구 없음 확인 |
| 수용 기준 7 | `plugin.json` version 0.3.0 확인 |

## 4. 계획서와 다르게 한 것과 이유

1. **dev-workflow frontmatter `description`의 에이전트 나열에 documenter 추가** — 지시서의 "네 곳"에 없지만, 나열이 역할 6개 시점과 어긋나 틀린 설명이 되므로.
2. **경계 확인 총괄 문장("②·⑤·⑥·⑧의 서브에이전트 호출…")·경계 확인 절 헤딩·같은 절 끝의 플러그인 hook 문단에 ⑧-2·documenter·H7 반영** — ⑧-2도 경계 확인으로 감싸는 것이 지시서의 경계 확인 표 추가 의도이므로, ⑧-2가 그 목록과 hook 설명에서 빠지면 절차 설명이 모순됨. 기존 ⑧·⑧-1 고유 문구는 그대로.
3. **README.md의 "역할은 에이전트 5개"를 "6개"로** — plugin.json description 수정과 같은 맥락. 숫자를 두면 틀린 설명이 됨.
4. **README 구성 표·design.md §3 트리에 `repo-docs`·`knowledge-sync` 스킬 행 추가** — 지시서가 명시한 것은 "에이전트 목록에 documenter"이지만, 이 스킬 둘은 documenter의 필수 스킬인데 구성 목록에 빠지면 어긋남.
5. **`h3_violation` 시그니처에 선택적 `role=None` 파라미터** — 기존 테스트가 이 함수를 파라미터 없이 직접 호출하고 기존 H3 판정 결과 유지가 「바꾸지 않을 것」이므로, 기본값으로 기존 동작을 그대로 두고 documenter 예외만 추가하는 최소 형태를 택함.
6. **⑨ 한 줄을 새 문단(`**⑨ 통합**: …`)으로 추가** — 기존 SKILL.md에 ⑨ 본문 절이 없어서, 지시서의 "⑨ 본문에 한 줄만 더합니다"를 ⑧-2 절 바로 뒤의 한 줄 문단으로 반영.

## 5. 물어볼 것

- 없음. `.work-standards/kb-outbox/` 는 hook 상태 디렉터리의 자체 `.gitignore`(`*`) 때문에 git에 올라가지 않는데, 이는 "올리기 전 승인 대기 초안" 설계(§8.4-1)와 맞으므로 그대로 두었습니다.
