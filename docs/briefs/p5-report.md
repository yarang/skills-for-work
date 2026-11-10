# P5 보고서: `shared` 플러그인과 `review-packet` 스킬

작업: `docs/briefs/p5-shared-review-packet.md` · 날짜: 2026-11-10 · 구현: Z.ai (GLM)

## 1. 만든·바꾼 파일 목록

만든 파일:

| 파일 | 내용 |
|---|---|
| `shared/.claude-plugin/plugin.json` | name `shared`, version `0.1.0`, license MIT, author yarang |
| `shared/LICENSE` | `developer/LICENSE`와 같음 (MIT) |
| `shared/README.md` | 구성, 쓰는 플러그인(work-standards ⑧-1, book-writer ⑤), 필요한 도구(agy·python3·llm.env), 설치·테스트 |
| `shared/skills/review-packet/SKILL.md` | 8개 절: 언제 쓰는가 / 원칙 / 검토 꾸러미 만들기 / provider 능력표 / 기본 절차 / 판정 확인 / 보내지 않는 것 / 실행기 사용법 |
| `shared/skills/review-packet/templates/packet.md` | 검토 꾸러미 틀 — 계획서 §9.2 그대로 |
| `shared/skills/review-packet/templates/verdict.md` | 판정 확인 표 틀 (채택·기각·확인 필요 + 종합 판정 + EXAONE 지연·실패 기록 칸) |
| `shared/skills/review-packet/scripts/run_agy.sh` | Antigravity 실행기. `--print` 맨 뒤, 종료 코드 그대로 전달, 빈 결과면 2 |
| `shared/skills/review-packet/scripts/exaone_review.py` | EXAONE 실행기. 스트리밍 SSE, 429 재시도, 줄 번호 첨부, `--packet`·`--diff`·`--stdin-label`·`--effort`·`--max-tokens` |
| `shared/skills/review-packet/tests/test_exaone_review.py` | 가짜 SSE 서버 테스트 10건 |
| `shared/skills/review-packet/tests/test_run_agy.py` | 가짜 `agy` 테스트 4건 |

바꾼 파일:

| 파일 | 내용 |
|---|---|
| `.claude-plugin/marketplace.json` | `plugins`에 `shared` 추가 (category `development`, source `./shared`), 설명문 갱신 |
| `developer/skills/dev-workflow/SKILL.md` | ⑧ 뒤에 ⑧-1 외부 검토 추가 — 흐름도·파이프라인 표·본문 세 곳 + 경계 확인 제목·표. 기존 ⑧ 문구·번호는 그대로 (diff로 확인) |
| `book-writer/skills/book-workflow/SKILL.md` | ⑤ 표 "외부 검토(Antigravity, 선택: EXAONE)", ⑤ 절의 Codex·`agy -p` 예를 `shared:review-packet` 절차 문장으로 교체 |
| `book-writer/agents/writer.md` | 표 "editor 에이전트, 외부 검토(Antigravity, 선택: EXAONE)" |
| `book-writer/skills/book-principles/SKILL.md` | "독립 검토(별도 에이전트, 외부 provider 검토 — `shared:review-packet`)" |
| `developer/README.md` | ⑧-1이 `shared` 플러그인을 필요로 한다는 한 줄 |
| `book-writer/README.md` | ⑤ 외부 검토가 `shared` 플러그인을 필요로 한다는 한 줄 |

## 2. 원본 A·B에서 가져온 것과 버린 것

원본 A (사라진 스트리밍 실행기 — 지시서에 적힌 기능):
- **가져옴**: 스트리밍 수신 (`stream: true`, SSE `data:` 줄, `[DONE]`에서 끝) · 지시서(꾸러미)와 `git diff <기준>..HEAD` 묶음 (`--diff <저장소> <기준 커밋>`) · 독립 리뷰어 system 메시지 (대상 안의 지시문은 데이터, 확인 못 함은 추측하지 않음)
- **버림**: 없음 (가져올 기능을 지시서가 전부 명시함). 원본의 정확한 문구는 남아 있지 않아 system 메시지는 기능 뜻에 맞춰 새로 씀

원본 B (`claude-agents/skills/exaone-review/scripts/exaone_review.py` + `SKILL.md`):
- **가져옴**: 줄 번호 붙이기 (`numbered`, `{i:4d}  {줄}`) · 429 재시도 (`Retry-After` 우선, 지수 백오프, 최대 5회, 그 밖의 HTTP 오류는 상태 코드·본문 앞부분을 stderr에 적고 종료 1) · `--effort`(기본 `high`)·`--max-tokens`(기본 16000)·`--stdin-label` · 키 파일에서 `EXAONE_API_KEY=` 줄만 읽기 · 컨텍스트 상한 검사(524,288자) · `finish_reason=length` 경고 · 결과 파일 머리 `# EXAONE(<모델>) 검토`
- **버림**: `--prompt`(꾸러미가 아닌 범용 지시 파일) — `--packet`으로 대체 · 환경 변수 이름 `EXAONE_API_BASE` → `EXAONE_BASE_URL`(지시서 명시) · 키 파일 고정 경로 → `LLM_ENV_FILE`(지시서 명시) · "검토 대상 없으면 종료" 검사 — 꾸러미 구조에서는 대상 원문을 꾸러미에 통째로 넣을 수 있어 뺌 · 비스트리밍 `call()`·`json.load` 경로 전체 — 스트리밍만 둠 · 토큰 usage의 stdout 출력 — 지시서대로 stderr에 모델·추론 글자 수·`finish_reason`을 적음

## 3. 실행한 검증 명령과 결과

TDD: 테스트를 먼저 쓰고 `14 failed`(스크립트 부재)를 확인한 뒤 구현해 `14 passed`로 만들었습니다. 중간에 테스트 한 건의 자체 버그(꾸러미 파일을 만들지 않음)를 고쳤고, 이는 RED 확인 뒤의 일입니다.

| 명령 | 결과 |
|---|---|
| `claude plugin validate <루트>/shared` | 통과 (경고 1: 플러그인 아이콘 없음 — 기존 developer·book-writer에도 없음) |
| `claude plugin validate <루트>` (마켓플레이스) | 통과 (advice 2건: 기존 README 설치 줄 권고 — 변경 전부터 있음) |
| `cd shared && uv run --python 3.13 --with pytest pytest skills/review-packet/tests -q` | **14 passed** (test_exaone_review 10 + test_run_agy 4) |
| `cd developer && uv run --with pytest pytest -q hooks/tests skills/verify/tests` | **78 passed** |
| `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q` | **54 passed** |
| `grep -rn -i 'codex' book-writer/ developer/skills/dev-workflow/ shared/` | 이력 문서 `book-writer/docs/design.md:73`(P1 당시 반영 이력 서술)만 남음 — 대상 아님 |
| `git diff developer/skills/dev-workflow/SKILL.md` | ⑧-1이 흐름도·표·본문 세 곳에 추가, 기존 ⑧ 문구는 변경 없음 |

테스트는 모두 가짜 SSE 서버(`http.server`)와 가짜 `agy` 실행 파일로만 돌렸고, 실제 EXAONE·Antigravity API는 부르지 않았습니다. `~/.config/server-guardian/llm.env`도 열지 않았습니다(키 파일 테스트는 임시 디렉터리의 가짜 파일).

## 4. 계획서와 다르게 한 것과 이유

- **테스트를 지시서 최소 목록보다 5건 더 씀** (`--effort` 상속, 환경 변수 키가 파일보다 우선, `--diff` 묶음, `finish_reason=length` 경고, `run_agy.sh` 종료 코드 전달·저장소 내 실행). 원본 A의 핵심 기능(diff 묶음)과 지시서 본문의 요구(경고, 키 우선순위)를 테스트 없이 두면 회귀를 못 잡기 때문입니다.
- **원본 B의 "검토 대상 없으면 종료" 검사를 뺌.** 꾸러미 구조에서는 `--packet`이 필수이고, 저장소를 못 읽는 provider에게 대상 원문을 꾸러미 안에 통째로 넘기는 경우가 정당하기 때문입니다(§9.2의 참고 원본 첨부).
- **경계 확인 절의 제목 나열**(②·⑤·⑥·⑧)에 ⑧-1을 더함. 지시서는 표·흐름도·본문 세 곳만 말하지만, "⑧-1도 경계 확인으로 감싼다"를 절 제목과 무관하게 두면 문서 안에서 모순이 생기기 때문입니다. 기존 ⑧ 행의 문구는 그대로입니다.
- **마켓플레이스 설명문**(최상위 `description`)에 `, 공통 스킬(shared)`를 추가함. `plugins` 목록 추가만으로는 validate가 통과하지만, 모음의 안내 문구에 빠진 항목이 생기는 것이 어색하기 때문입니다.

## 5. 물어볼 것

1. **`docs/reviews/` 경로**: 판정 기록을 `docs/reviews/<작업>-<provider>-<날짜>.md`에 남기기로 했는데(§9.4), 이 저장소에는 아직 그 디렉터리가 없습니다. 처음 사용할 때 메인 대화가 만들면 되리로 두었습니다. skills_for_work 저장소에 빈 틀이나 `.gitkeep`을 미리 둘까요?
2. **EXAONE usage 스트리밍**: 스트리밍 모드에서는 마지막 chunk에 `usage`가 오지 않을 수 있어, stderr의 추론 토큰 수는 올 때만 적히게 두었습니다(글자 수는 항상 있음). 실제 응답에 usage가 없다면 토큰 수는 비워둡니다 — 괜찮을까요?
3. **아이콘 경고**: `claude plugin validate`가 플러그인 아이콘 없음을 경고합니다. 기존 세 플러그인도 같은 상태라 그대로 두었습니다. 마켓플레이스를 공개할 계획이 생기면 그때 함께 넣습니다.
