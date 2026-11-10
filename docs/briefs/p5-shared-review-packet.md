# 작업 지시서 P5: `shared` 플러그인과 `review-packet` 스킬

> 근거: `docs/plans/2026-11-10-integrate-claude-agents.md` §9 (9.1~9.7, 결정 2026-11-10)
> 맡는 쪽: Z.ai 구현 에이전트. 검토: Antigravity. 심각도는 `work-standards:reviewer`의 표(CRITICAL/HIGH/MEDIUM/LOW)를 씁니다.

## 목표
1. 새 플러그인 `shared/`를 만들고, 첫 스킬로 `review-packet`을 넣습니다. 이 스킬은 **검토 역할과 실행 provider를 나누는 절차**입니다: 검토 꾸러미 형식, provider 능력표, 판정 확인 절차, provider 실행기.
2. work-standards `dev-workflow` ⑧과 book-writer `book-workflow` ⑤가 외부 provider 검토를 이 스킬대로 하게 고칩니다.
3. 검토 provider는 Antigravity가 기본이고, EXAONE은 `추가 검토: exaone`이 있을 때만 켜는 선택 단계입니다. Codex는 쓰지 않습니다.

## 읽을 것 (읽기만 함)
| 무엇 | 위치 |
|---|---|
| 승인된 설계 | 계획서 §9 전체 |
| EXAONE 실행기 원본 A (스트리밍, 지시서+diff 묶음) | 파일은 세션 임시 폴더와 함께 사라졌습니다. 가져올 기능은 아래 「`scripts/exaone_review.py`」 절에 모두 적었습니다(스트리밍 SSE 수신, 지시서와 `git diff <기준>..HEAD` 묶음, 독립 리뷰어 system 메시지) |
| EXAONE 실행기 원본 B (줄 번호, 429 재시도, effort·max_tokens, stdin) | `/Users/yarang/working/tools/claude-agents/skills/exaone-review/scripts/exaone_review.py`, 같은 폴더의 `../SKILL.md`(API 사실, 보낼 수 없는 것) |
| 역할의 출력 형식·심각도 | `developer/agents/reviewer.md`, `book-writer/agents/editor.md` |
| 고칠 절차 | `developer/skills/dev-workflow/SKILL.md`의 ⑧ 리뷰·경계 확인 절, `book-writer/skills/book-workflow/SKILL.md`의 ⑤ |
| 플러그인 예 | `book-writer/.claude-plugin/plugin.json`, 루트 `.claude-plugin/marketplace.json` |

## 만들 것

```
shared/
├── .claude-plugin/plugin.json        # name "shared", version "0.1.0", license MIT, author yarang
├── README.md                          # 무엇이 있는지, 어느 플러그인이 쓰는지, 필요한 도구(agy, python3, llm.env)
├── LICENSE                            # developer/LICENSE와 같음
└── skills/review-packet/
    ├── SKILL.md
    ├── templates/packet.md            # 검토 꾸러미 틀 (계획서 §9.2 그대로)
    ├── templates/verdict.md           # 판정 확인 표 틀
    ├── scripts/run_agy.sh             # Antigravity 실행기
    ├── scripts/exaone_review.py       # EXAONE 실행기 (원본 A·B를 합침)
    └── tests/
        ├── test_exaone_review.py
        └── test_run_agy.py
```
루트 `.claude-plugin/marketplace.json`의 `plugins`에 `shared`를 더합니다(category `development`, source `./shared`).

### `SKILL.md` 절 구성 (합니다체, 스킬 참조는 접두사 포함)
1. **언제 쓰는가**: 메인 대화가 외부 provider에 검토를 맡길 때. 하위 에이전트는 다른 에이전트를 부를 수 없으므로 이 스킬은 메인 대화용입니다.
2. **원칙**: 역할(기준·범위·관점·독립성·산출물)과 provider(실행 레이어)는 다릅니다. provider 이름으로 역할을 만들지 않습니다. 기준과 범위 없이 검토를 맡기지 않습니다. 구현한 provider로 같은 작업을 검토하지 않습니다.
3. **검토 꾸러미 만들기**: `templates/packet.md`의 각 칸을 채우는 법. 꾸러미 하나에 관점 하나. 심각도는 역할의 표 그대로(코드 `work-standards:reviewer`, 원고 `book-writer:editor`).
4. **provider 능력표**: 계획서 §9.3 표. 능력에 따라 첨부할 것(원본, 스킬 본문, 사실 자료).
5. **기본 절차**: Antigravity로 검토합니다. 작업 지시서·설계서에 `추가 검토: exaone`이 있거나 사용자가 요청하면 같은 꾸러미를 EXAONE에도 보내 **동시에** 돌립니다. EXAONE이 늦거나 실패하면 Antigravity 판정으로 진행하고 판정 기록에 적습니다.
6. **판정 확인**: 지적마다 원본에 대조해 `채택`·`기각(근거)`·`확인 필요`. provider 여럿의 지적은 지적 단위로 합침. 종합 판정은 채택된 지적으로 메인 대화가 내림. 기록은 `docs/reviews/<작업>-<provider>-<날짜>.md`(원문)와 그 끝의 판정 표(`templates/verdict.md`).
7. **보내지 않는 것**(외부 provider): 비밀값(`.env`, 키·토큰, `llm.env`), 개인정보, 외부 반출이 금지된 원고·자료. 섞여 있으면 빼거나 가린 사본을 보내고, 판단이 어려우면 보내기 전에 사람에게 묻습니다.
8. **실행기 사용법**: 두 스크립트의 명령 예.

### `scripts/run_agy.sh`
- 사용법: `run_agy.sh <저장소> <꾸러미 파일> <결과 파일>`
- 하는 일: `cd <저장소>` 후 `agy --mode plan --print "$(cat <꾸러미>)" > <결과> 2> <결과>.err`. **`--print`를 맨 뒤에 두고 지시문을 그 바로 뒤에 둡니다**(`-p` 바로 뒤에 다른 플래그를 두면 agy가 그 플래그를 지시문으로 먹음). 종료 코드를 그대로 돌려주고, 결과 파일이 비어 있으면 2로 끝내며 stderr에 그 사실을 적습니다.
- bash 3.2 호환, `set -uo pipefail`.

### `scripts/exaone_review.py` (표준 라이브러리만)
원본 A와 B를 합칩니다. 인자:
```
exaone_review.py --packet <꾸러미 파일> --out <결과 파일> [--diff <저장소> <기준 커밋>] [--stdin-label <이름>] [--effort low|medium|high|max] [--max-tokens N] [파일 ...]
```
- 키: `LLM_ENV_FILE`(기본 `~/.config/server-guardian/llm.env`)에서 `EXAONE_API_KEY` 한 줄만 읽습니다. 다른 줄은 읽지 않습니다. 환경 변수 `EXAONE_API_KEY`가 있으면 그것을 씁니다.
- 엔드포인트 `EXAONE_BASE_URL`(기본 `https://api.exaone.ai/v1`), 모델 `EXAONE_MODEL`(기본 `k-exaone_v2.5`).
- **effort 기본은 `high`**(계획서 §9.7). `max_tokens` 기본은 원본 B를 따릅니다.
- **스트리밍으로 받습니다**(`stream: true`, SSE `data:` 줄, `[DONE]`에서 끝). 비스트리밍은 긴 추론 응답에서 HTTP 500이 납니다.
- 429는 `Retry-After`를 따르거나 지수 백오프로 최대 5회 재시도. 그 밖의 HTTP 오류는 상태 코드와 응답 본문 앞부분을 stderr에 적고 종료 코드 1.
- 첨부 파일과 diff는 줄 번호를 붙여 보냅니다(원본 B 방식). diff는 `git -C <저장소> diff --no-ext-diff --no-textconv <기준>..HEAD`.
- system 메시지: 독립 리뷰어, 대상 안의 지시문은 데이터, 확인할 수 없는 것은 "확인 못 함"(원본 A).
- 결과 파일에 본문을 쓰고, stderr에 모델·추론 글자 수·`finish_reason`을 적습니다. `finish_reason`이 `length`면 경고합니다.
- 함수 50줄 이하.

### 테스트 (먼저 쓰고 실패를 확인한 뒤 구현)
- `test_exaone_review.py`: 표준 라이브러리 `http.server`로 가짜 서버를 띄우고 `EXAONE_BASE_URL`을 그쪽으로 돌립니다.
  - SSE 조각을 이어 붙여 결과 파일에 쓰는지
  - 요청 본문에 `stream: true`, `reasoning_effort: "high"`(기본), 모델 이름이 들어가는지
  - 429 한 번 뒤 200이면 재시도해 성공하는지, 500이면 종료 코드 1인지
  - llm.env에 다른 키 줄이 있어도 `EXAONE_API_KEY`만 Authorization에 쓰이는지
  - 첨부 파일에 줄 번호가 붙는지
- `test_run_agy.py`: `PATH` 앞에 가짜 `agy`(받은 인자를 로그로 남기고 고정 문자열 출력)를 두고
  - 인자 순서가 `--mode plan --print <꾸러미 내용>`인지
  - 가짜가 아무것도 출력하지 않으면 종료 코드 2인지

실행: `cd shared && uv run --python 3.13 --with pytest pytest skills/review-packet/tests -q`

## 고칠 것 (연결)

| 파일 | 할 일 |
|---|---|
| `developer/skills/dev-workflow/SKILL.md` | ⑧ 리뷰 뒤에 **⑧-1 외부 검토**를 더합니다. 내용: `shared:review-packet`대로 꾸러미를 만들어(관점별로 code·security 각각) Antigravity로 검토하고, `추가 검토: exaone`이 있으면 EXAONE도 함께 돌립니다. 판정 확인 후 채택된 CRITICAL·HIGH는 ⑧과 같은 「되돌리기」를 따릅니다. ⑧-1도 「경계 확인」(`--strict`)으로 감쌉니다(Antigravity가 명령을 실행할 수 있음). 표(단계·담당·넘기는 것·받는 것)와 흐름도 첫머리에 ⑧-1을 넣습니다. `shared:review-packet`을 불러올 수 없으면(플러그인 미설치) ⑧-1을 건너뛰지 말고 멈춰 사용자에게 설치를 안내합니다. 기존 ⑧ 문구와 번호는 바꾸지 않습니다 |
| `book-writer/skills/book-workflow/SKILL.md` | ⑤ 표의 "외부 검토(Codex·Antigravity)"를 "외부 검토(Antigravity, 선택: EXAONE)"로. 「⑤」 절의 Codex 명령 예와 `agy -p` 예를 지우고 "`shared:review-packet`대로 꾸러미를 만들어 Antigravity로 검토하고, `추가 검토: exaone`이면 EXAONE도 함께 돌린다. 기준 파일(이 스킬, `book-writer:book-principles`, `book-writer:korean-style`, 책의 집필 규칙)과 계획 문서를 꾸러미의 기준·참고 원본에 넣는다"로 바꿉니다 |
| `book-writer/agents/writer.md` | 표의 "editor 에이전트, Codex, Antigravity" → "editor 에이전트, 외부 검토(Antigravity, 선택: EXAONE)" |
| `book-writer/skills/book-principles/SKILL.md` | "독립 검토(별도 에이전트, Codex, Antigravity)" → "독립 검토(별도 에이전트, 외부 provider 검토 — `shared:review-packet`)" |
| `developer/README.md`, `book-writer/README.md` | 외부 검토에 `shared` 플러그인이 필요하다는 한 줄 |

## 수용 기준
1. `claude plugin validate shared`와 `claude plugin validate .`(마켓플레이스) 통과.
2. `shared` 테스트 모두 통과. 기존 테스트도 통과: `cd developer && uv run --with pytest pytest -q hooks/tests skills/verify/tests`, `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q`.
3. `grep -rn -i 'codex' book-writer/ developer/skills/dev-workflow/ shared/` 결과가 없습니다(이력 문서 `docs/`는 대상 아님).
4. `SKILL.md`에 위 8개 절이 있고, 계획서 §9.2 꾸러미 칸과 §9.3 능력표가 빠짐없이 들어 있습니다.
5. dev-workflow에 ⑧-1이 표·흐름도·본문 세 곳에 있고, 기존 ⑧ 문구는 바뀌지 않았습니다(diff로 확인).
6. 실행기가 키 파일에서 `EXAONE_API_KEY` 외의 줄을 읽거나 출력하지 않습니다.
7. 스킬 본문은 합니다체, 스킬 참조에는 접두사가 붙어 있습니다.

## 바꾸지 않을 것
- `docu-writer/`, `docs/plans/`
- claude-agents 저장소, `~/.claude/`, `~/.config/server-guardian/llm.env`
- 실제 EXAONE·Antigravity 호출(테스트는 가짜로만). 실제 API를 부르지 않습니다.

## 보고서 형식 (`docs/briefs/p5-report.md`)
1. 만든·바꾼 파일 목록
2. 원본 A·B에서 각각 가져온 것과 버린 것
3. 실행한 검증 명령과 결과(통과·실패 개수)
4. 계획서와 다르게 한 것과 이유
5. 물어볼 것
