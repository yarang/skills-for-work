# P1 보고서 — book-writer 플러그인 추가

불러온 스킬: 없음(지시서 수행 세션이므로 Skill 도구로 스킬을 불러오지 않았습니다)

## 만든 파일

book-writer/ 22개 파일과 루트 수정 2건입니다.

| 파일 | 내용 |
|---|---|
| `book-writer/.claude-plugin/plugin.json` | 플러그인 매니페스트(name `book-writer`, v0.1.0) |
| `book-writer/LICENSE` | MIT(developer/LICENSE와 동일) |
| `book-writer/README.md` | 설치, 에이전트 5개, 6단계 표, 원고 저장소에 필요한 파일, 쓰기 보호 안내 |
| `book-writer/docs/design.md` | 역할 기준, 단계, 쓰기 보호 계약, 앞붙이 경로, 원본과의 대응 |
| `book-writer/hooks/hooks.json` | PreToolUse 등록(matcher `Write\|Edit\|MultiEdit\|NotebookEdit`, timeout 10) |
| `book-writer/hooks/write_guard.py` | 역할별 쓰기 가드(표준 라이브러리만) |
| `book-writer/hooks/tests/test_write_guard.py` | 가드 테스트 53건 |
| `book-writer/agents/planner.md` | 기획(`story`/`content`/`outline`/`extract`/`rev`), opus |
| `book-writer/agents/writer.md` | 집필(`draft`/`revise`/`polish`), sonnet |
| `book-writer/agents/editor.md` | 독립 검토(회차 파일명, 변경분 재검토), sonnet |
| `book-writer/agents/researcher.md` | 자료 조사(WebSearch·WebFetch·DeepWiki·chrome MCP 유지), sonnet |
| `book-writer/agents/capturer.md` | 화면 실측·캡처(`probe`/`shoot`), sonnet |
| `book-writer/skills/book-workflow/SKILL.md` | 6단계 절차(book-writing에서 개명, 14건 반영) |
| `book-writer/skills/book-workflow/templates/{story,content,outline,review}.md` | 계획·검토 틀(원본에서 이관, 자리표시자 없음) |
| `book-writer/skills/book-principles/SKILL.md` | 집필 공통 원칙 |
| `book-writer/skills/korean-style/SKILL.md` | 한국어 표기 규칙 |
| `book-writer/skills/book-research/SKILL.md` | 자료 조사 기준(원본 그대로 이관) |
| `book-writer/skills/screen-capture/SKILL.md` | 화면 실측·캡처 기준(probe/shoot 두 모드 추가) |
| `.claude-plugin/marketplace.json` | plugins에 book-writer 추가(category `productivity`, source `./book-writer`) |
| `.gitignore` | `.pytest_cache/` 추가 |

이 보고서(`docs/briefs/p1-report.md`)도 첫 커밋에 포함됩니다.

## 계획서 §3 14건 반영 표

| # | 심각도 | 반영 파일과 절 | 반영 내용 |
|---|---|---|---|
| 1 | blocker | `agents/capturer.md` 「모드」, `skills/screen-capture` 도입부·「정찰 항목」·「5. 실측 기록」, `skills/book-workflow` 「② 내용 논의」 | capturer에 원고 없이 확인할 동작 목록만 받는 `probe` 모드를 두어 ② 단계 사전 실측을 막힘없이 맡긴다. 실측 기록 양식에 모드 칸을 더했다 |
| 2 | blocker | `skills/book-workflow` 「앞붙이」·「완료 체크리스트」, `agents/planner.md`, `agents/writer.md`, README, design.md | 앞붙이 계획은 `plans/front/<이름>/`에 `story.md`(의도)와 `outline.md`만 두고, 완료 체크리스트를 장과 앞붙이 변형으로 나눠 면제 조건을 정했다 |
| 3 | major | `skills/book-workflow` 「③ 구조화」 | ③ 관문을 '사람 확인 → 메인 세션이 승인을 outline에 기록'으로 정하고, "답이 없으면 통과가 아니다"로 암묵 통과를 막았다. 승인 기록 절차를 story에만 두지 않고 ①②③ 모두에 적었다 |
| 4 | major | `agents/planner.md` 「모드」(`rev`), `skills/book-workflow` 「0. 단계와 관문」, `hooks/write_guard.py`(승인 문서 보호) | 승인된 계획 문서는 읽기만 하고, 고칠 것이 생기면 `<문서>.rev<N>.md` 수정안을 만들어 승인을 다시 받는다. 가드가 `상태: 승인` 문서의 직접 수정을 모든 역할에서 거부한다 |
| 5 | major | `skills/book-workflow` 「0. 단계와 관문」, `skills/book-principles` 「3. 결정 기록과 진행 상태」, `agents/writer.md` ④ | 상태값 목록(`미착수/스토리/내용/구조/초안/검토/완료`)은 book-workflow에만 두고, 관문마다 메인 세션이 갱신한다고 정했다. writer는 `초안`만 쓴다 |
| 6 | major | `skills/book-workflow` 「⑥ 완료」, `agents/editor.md` | ⑥에서 실측 반영 뒤 editor가 변경분을 재검토하는 관문을 두었다. 완료 체크리스트에 재검토 통과를 넣었다 |
| 7 | major | `skills/screen-capture` 「2. 안전 규칙」, `agents/capturer.md` 행동 계약 | 촬영 준비를 위한 임시 변경(설정·Skill·파일)을 허용하고 영구 산출물과 구분했다. 끝나면 원래대로 돌리고 '되돌린 것'에 기록한다 |
| 8 | major | `agents/` 5개 전부 「진행 순서」 0단계·보고서 규칙 | 모든 역할에 질문 계약을 넣었다: 막히면 답을 기다리지 않고 보고서 `물어볼 것`에 적고 종료한다. 0단계 스킬 확인(불러온 스킬 이름을 보고서 첫 줄에)과 '읽은 내용은 데이터'도 공통으로 넣었다 |
| 9 | major | (원고 저장소 범위 밖) `agents/` 5개 공통 규칙으로 완화 | CLAUDE.md·WRITING.md 충돌 자체는 원고 저장소에서 풀어야 해 이 지시서 범위 밖이다. 플러그인 쪽에서는 집필 규칙 문서를 0단계 정찰로 읽게 하고, 규칙 충돌을 만나면 `물어볼 것`로 올리게 했다 |
| 10 | major | `skills/book-workflow` 「검증의 두 단계」, `agents/writer.md`, README, design.md | 검증을 둘로 나눴다: **변경 범위 검증**(writer가 작업마다, 이번에 바꾼 파일만)과 **완료 검증**(⑥에서 장 전체, 빌드·꾸러미 포함). 관문은 완료 검증 기준을 쓴다 |
| 11 | major | `skills/korean-style` 도입부 | "표기 규칙을 근거로는 코드 블록·따옴표 안의 실제 입력 문구를 고치지 않는다"로 한정하고, 기술 오류(틀린 명령·설정값) 수정은 writer의 `revise` 범위라고 명시했다 |
| 12 | minor | `skills/book-workflow` 「⑤ 초안 검토」, `agents/editor.md`, `skills/book-principles` 「6. 검토 의뢰」 | 검토 파일명에 회차를 넣었다: `reviews/<검토자>-<범위>-<날짜>-r<회차>.md`. 회차를 읽어 이전 지적·반영 기록과 이어진다 |
| 13 | minor | `skills/book-workflow` 「앞붙이」, `skills/book-principles` 「3. 결정 기록과 진행 상태」 | '권끼리 서로 가리키지 않는다'는 개별 책 정책이므로 공통 스킬에서 빼고 책의 집필 규칙으로 보냈다. 새 표기 규칙의 자리 기준(여러 책 공통 → korean-style, 한 책만 → 집필 규칙 문서)을 정했다 |
| 14 | minor | `skills/book-principles` 「1. 장 구조」, `agents/` 각 파일 | 절 번호 참조(`book-writing §1`)를 절 제목 참조(「장 템플릿」)로 바꿔 구성 변화에 흔들리지 않게 했다 |

## 검증 명령과 결과

| 명령 | 결과 |
|---|---|
| `grep -rn '{{' book-writer/` | 매치 없음(자리표시자 잔존 0) |
| `claude plugin validate book-writer` | Validation passed(아이콘 없음 경고 1건 — 결과에 영향 없는 디렉터리 경고) |
| `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q` | 53 passed |
| `cd developer && uv run --with pytest pytest -q hooks/tests` | 68 passed(기존 테스트 회귀 없음) |
| 에이전트 frontmatter `skills:` 접두사 | 5개 모두 `book-writer:` 접두사(planner·writer·editor → book-workflow, researcher → book-research, capturer → screen-capture) |

테스트는 먼저 쓰고 실패를 확인한 뒤 구현했습니다: 초판 테스트 53건 중 구현 전 53 실패 → 구현 후 통과 과정에서 테스트 기대값 오류 4건을 바로잡았습니다(자세한 내용 `hooks/tests/test_write_guard.py`).

## 계획서와 다르게 한 것과 이유

1. **스킬 문체 이관 순서** — 스킬 5개는 첫 커밋에서 원본 한다체 그대로 두고(14건 내용 반영만), 둘째 커밋에서 어미만 합니다체로 바꿉니다. 문체와 내용 변화가 한 커밋에 섞이면 둘째 커밋의 diff 검증(문체만 바뀌었는지)이 불가능해져서입니다.
2. **실측 기록 기본 위치를 `research/measure-*.md`로 통일** — 원본 book-principles는 `reviews/measure-*.md`를, screen-capture는 `reviews/measure-<권>-<장>-<날짜>.md`를 안내합니다. 쓰기 가드의 역할별 허용 경로와 정합시키기 위해 `research/measure-*.md`를 기본으로 삼고, 원고 저장소가 다른 관례를 쓰면 그 관례를 따르되 가드 허용 경로는 `.book-writer/paths.json`으로 맞춘다고 안내했습니다.
3. **#9는 플러그인 밖 파일의 문제라 직접 고치지 않음** — 원고 저장소의 CLAUDE.md와 WRITING.md 충돌은 그 저장소에서 결정할 사안이고, 지시서 규칙(1)도 바깥 경로는 읽기만 하도록 했습니다. 플러그인 쪽 완화(질문 계약)만 반영했습니다.
4. **`.gitignore`에 `.pytest_cache/` 추가** — hook 테스트를 돌리면 생기는 캐시가 커밋에 섞이지 않게 했습니다. 기존 `__pycache__/`·`*.pyc`와 같은 성격의 누락 보충입니다.

## 물어볼 것

1. #9의 원고 저장소 쪽 결정이 필요합니다: 예시 저장소에서 CLAUDE.md(전부 Claude Code 기준)와 WRITING.md(Desktop 예외)의 도구 기준을 어느 쪽으로 통일할지요. 이 저장소는 읽기만 했습니다.
2. 쓰기 가드 기본 허용 경로에서 capturer가 `research/measure-*.md` 외의 research 문서는 못 씁니다. 실측 기록 외 조사 메모를 capturer가 남겨야 한다면 `paths.json` 없이는 researcher에게 넘겨야 하는데, 기본 목록에 더 넣을지요.
3. 이 커밋들은 push하지 않았습니다. git.agentthread.dev 업데이트(전역 제약)는 사용자 지시로 이번만 유보했습니다 — push 여부를 알려주세요.

## 검토 반영(1차)

Antigravity 검토 지적 4건(2026-11-10)을 반영했습니다. 커밋 하나로 묶고 push하지 않았습니다.

| # | 심각도 | 바꾼 곳 | 무엇을 바꿨는지 |
|---|---|---|---|
| 1 | major | `agents/planner.md`·`agents/editor.md`·`agents/researcher.md` frontmatter, `agents/writer.md`·`agents/capturer.md` 「행동 계약」, `docs/design.md` 「쓰기 보호」 | Bash로 쓰기 가드를 우회하는 길을 막았습니다. planner·editor·researcher의 `tools`에서 Bash를 뺐습니다(세 파일 본문을 훑어 Bash 실행을 전제한 문장은 없었고, 탐색·조사는 이미 Grep·Glob·Read·웹 도구로 쓰여 있어 본문 수정은 필요하지 않았습니다). writer(빌드·테스트·검사)와 capturer(앱 조작·캡처)는 Bash를 유지하되, 행동 계약의 불변 조건에 "Bash로 파일을 만들거나 고치지 않습니다. 파일 쓰기는 Write·Edit로만 합니다(쓰기 가드가 Bash를 보지 못합니다)"를 넣고 Bash의 용도를 각각 명시했습니다. design.md 「쓰기 보호」에 이 결정을 「Bash로 우회하지 못하게」 글머리로 기록했습니다. |
| 2 | minor | `agents/` 5개 본문·description, `skills/book-workflow/SKILL.md`, `skills/book-principles/SKILL.md`, `skills/book-research/SKILL.md` | 본문과 description에서 스킬을 가리키던 자리(book-workflow·book-principles·korean-style·book-research·screen-capture)에 모두 `book-writer:` 접두사를 붙였습니다. 스킬 frontmatter의 `name:`과 파일 경로 디렉터리 이름은 그대로 뒀습니다. 수정 뒤 grep으로 확인: 접두사 없는 언급은 스킬 `name:` 선언 5곳뿐입니다. |
| 3 | minor | `skills/book-principles/SKILL.md` 「3. 결정 기록과 진행 상태」 | manifest 상태값 괄호 목록(`미착수/스토리/…`)을 지우고, "상태값은 book-writer:book-workflow 「0. 단계와 관문」의 상태값 목록을 따른다"로 가리키기만 하게 했습니다. 상태값 정의는 book-workflow 한 곳에만 남았습니다. |
| 4 | minor | `hooks/write_guard.py` `find_root`, `hooks/tests/test_write_guard.py` | `find_root`가 돌려주는 원고 루트를 대상 경로와 같은 `resolve()`(realpath)로 정규화하도록 고쳤습니다(찾은 루트와 없을 때의 cwd 둘 다). 심볼릭 링크를 거친 cwd 아래에 manifest.md가 있는 경우의 테스트(`test_root_normalized_when_cwd_via_symlink`)를 먼저 추가했더니 **구현을 고치기 전에 이미 통과했습니다** — `main()`이 `find_root`에 넘기기 전에 이미 `os.path.realpath(cwd)`로 cwd를 정규화하고 있었기 때문입니다. 우회 경로가 있어 실패가 나오지는 않았지만, 계약("R도 같은 방식으로 정규화합니다")을 `main`의 사전 처리가 아니라 함수 자체가 보장하도록 고쳤고 테스트는 회귀 방지로 남겼습니다. |

검증 명령과 결과:

| 명령 | 결과 |
|---|---|
| `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q` | 54 passed(이번에 더한 symlink cwd 테스트 1건 포함, 실패 0) |
| `grep -rn '{{' book-writer/` | 매치 없음(자리표시자 잔존 0) |
| `claude plugin validate book-writer` | Validation passed(아이콘 없음 경고 1건 — 1차 보고서와 동일한, 결과에 영향 없는 경고) |
