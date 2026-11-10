# shared

여러 플러그인이 함께 쓰는 공통 스킬을 두는 플러그인입니다. 두 번째 사용처가 생기는 스킬을 이곳으로 옮깁니다.

## 구성

| 이름 | 종류 | 하는 일 |
|---|---|---|
| `shared:review-packet` | 절차 스킬 | 검토 역할과 실행 provider를 나누는 절차 — 검토 꾸러미 형식(`templates/packet.md`), provider 능력표, 판정 확인 절차, provider 실행기(`scripts/run_agy.sh`, `scripts/exaone_review.py`) |

## 어느 플러그인이 쓰는지

- **work-standards** — `dev-workflow` ⑧-1 외부 검토가 `shared:review-packet`대로 꾸러미를 만듭니다.
- **book-writer** — `book-workflow` ⑤ 초안 검토의 외부 검토(Antigravity, 선택: EXAONE)가 `shared:review-packet`을 씁니다.

두 플러그인의 외부 검토를 쓰려면 이 `shared` 플러그인을 함께 설치해야 합니다.

## 필요한 도구

| 도구 | 쓰는 곳 | 비고 |
|---|---|---|
| `agy` (Antigravity CLI) | `run_agy.sh` | 설치 경로: https://antigravity.google/ |
| `python3` (표준 라이브러리만) | `exaone_review.py` | |
| `EXAONE_API_KEY` | `exaone_review.py` | 환경 변수 또는 `LLM_ENV_FILE`(기본 `~/.config/server-guardian/llm.env`)의 `EXAONE_API_KEY=` 줄. 스크립트는 그 줄만 읽습니다 |

## 사용

```
claude plugin marketplace add <이 저장소>
claude plugin install shared@skills-for-work
```

시험 삼아 띄울 때는 `--plugin-dir <이 저장소>/shared`로 가리킵니다.

테스트 실행:

```
cd shared && uv run --python 3.13 --with pytest pytest skills/review-packet/tests -q
```

테스트는 가짜 SSE 서버와 가짜 `agy` 실행 파일만 쓰고, 실제 API는 부르지 않습니다.
