# book-writer

한국어 실습형 IT 교재(초보자~중급자 대상)를 6단계로 쓰는 집필 플러그인입니다. 역할 에이전트 5개가 각자 맡은 산출물만 쓰고, 쓰기 가드 hook이 역할별 허용 경로를 지킵니다.

## 설치

이 저장소를 마켓플레이스로 추가하고 플러그인을 설치합니다.

```
claude plugin marketplace add <이 저장소>
claude plugin install book-writer@skills-for-work
```

시험 삼아 띄울 때는 원고 저장소에서 `--plugin-dir`로 가리키면 됩니다.

```
claude --plugin-dir <이 저장소>/book-writer
```

## 에이전트 5개

| 에이전트 | 모델 | 하는 일 | 쓰는 곳 |
|---|---|---|---|
| `book-writer:planner` | opus | ①②③ 계획 문서(story·content·outline)와 승인된 계획의 수정안(`rev`) | `plans/` |
| `book-writer:writer` | sonnet | ④ 집필(`draft`), ⑤⑥ 반영(`revise`), 표기 정리(`polish`) | `manuscript/`, `manifest.md`, `examples/` |
| `book-writer:editor` | sonnet | ⑤ 독립 검토 — 지적과 판정만 남김 | `reviews/` |
| `book-writer:researcher` | sonnet | 기술 사실·규격·표기 근거 조사 | `research/` |
| `book-writer:capturer` | sonnet | 화면 실측·캡처. `probe`(원고 없이 동작 확인)와 `shoot`(촬영) 두 모드 | `manuscript/**/images/`, `research/measure-*.md` |

모델은 사람과 논의할 안을 만드는 planner만 opus이고, 나머지는 sonnet입니다. 스킬 배정과 상세 설계는 `docs/design.md`에 있습니다.

## 6단계 절차

메인 대화가 `book-writer:book-workflow` 스킬을 따라 진행합니다.

| 단계 | 산출물 | 맡는 쪽 | 관문 |
|---|---|---|---|
| ① 스토리 | `plans/vol<N>/ch<NN>/story.md` | planner 제안 → 메인 세션 논의 | 사람 승인 |
| ② 내용 | `plans/vol<N>/ch<NN>/content.md` | planner + researcher + capturer(`probe`) | 사람 승인 |
| ③ 구조 | `plans/vol<N>/ch<NN>/outline.md` | planner | 사람 확인 → 메인 세션이 승인 기록 |
| ④ 집필 | `manuscript/…/chNN.md` | writer(`draft`) | 변경 범위 검증 |
| ⑤ 검토 | `reviews/editor-vol<N>-ch<NN>-<날짜>-r<회차>.md` | editor + 외부 검토 → writer(`revise`) | blocker 0, major 반영 또는 사유 |
| ⑥ 완료 | manifest `완료` | capturer(`shoot`) → writer → editor(변경분 재검토) | 완료 검증 + 사람 승인 |

앞붙이(머리말, 이 책을 읽는 방법, Part 도입)도 같은 단계로 지나되, 계획은 `plans/front/<이름>/`에 `story.md`(의도)와 `outline.md`만 둡니다.

## 원고 저장소에 필요한 파일

| 파일·폴더 | 역할 |
|---|---|
| `manifest.md` | 장별 상태(`미착수/스토리/내용/구조/초안/검토/완료`)와 분량. 쓰기 가드가 이 파일이 있는 디렉터리를 원고 루트로 삼습니다 |
| `CLAUDE.md` → `WRITING.md` | 그 책의 집필 규칙(권·Part 구성, 톤, 분량, 도구, 예외) |
| `DECISIONS.md` | 사람이 확정한 구조·범위·표기 결정 |
| `plans/`, `manuscript/`, `reviews/`, `research/`, `examples/` | 단계별 산출물 폴더(없으면 처음 쓸 때 만듭니다) |
| `.book-writer/paths.json` (선택) | 책마다 경로가 다를 때 역할별 허용 목록을 덮어씁니다. 예: `{"capturer": ["shots/**"]}` |

## 쓰기 보호

`hooks/write_guard.py`(PreToolUse)가 `book-writer:*` 서브에이전트의 `Write`·`Edit`·`MultiEdit`·`NotebookEdit`을 역할별 허용 경로와 비교해 막습니다. 메인 대화와 다른 플러그인은 검사하지 않습니다. 원고 루트 밖 쓰기, `.book-writer/` 쓰기, 승인된 계획 문서 수정(planner)을 모든 역할에서 막습니다. 계약은 `docs/design.md` 「쓰기 보호」에 있습니다.

테스트 실행:

```
cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q
```
