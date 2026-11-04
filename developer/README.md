# work-standards

조사 → 설계 → 테스트 → 구현 → 검증 → 리뷰로 이어지는 개발 파이프라인을 Claude Code 플러그인으로 묶었습니다.

**역할은 에이전트 5개**로 나눕니다. **분야 지식**(계층·언어·프레임워크)은 스킬로 확장합니다. 언어가 하나 늘어도 에이전트는 늘지 않고, 스킬 하나만 추가하면 됩니다.

## 구성

| 종류 | 이름 | 하는 일 |
|---|---|---|
| 에이전트 | `researcher` | 기존 구현·문서·라이브러리를 조사해 결론만 돌려줌 (haiku) |
| 에이전트 | `architect` | 작업 분해표·스킬 목록·계약·인수 조건이 담긴 설계서 작성 (opus) |
| 에이전트 | `tester` | 계약만 보고 인수 테스트를 먼저 쓰고 RED 확인 |
| 에이전트 | `developer` | 지정된 스킬을 불러와 인수 테스트를 GREEN으로 |
| 에이전트 | `reviewer` | 읽기 전용 리뷰, `관점: code` 또는 `관점: security` |
| 절차 | `dev-workflow` | 메인 대화가 파이프라인을 진행하는 방법 (+ 경계 확인 스크립트) |
| 공통 | `code-principles` | 불변 규칙과 구조 원칙 |
| 계층 | `backend-principles`, `frontend-principles` | 서비스·화면 계층 규칙 |
| 언어 | `typescript-standards`, `python-standards`, `go-standards`, `rust-standards` | 언어별 규칙 |
| 프레임워크 | `react-standards`, `fastapi-standards`, `mcp-server`, `axum-standards`, `tauri-standards` | 프레임워크별 규칙 |
| 도구 | `stack-detection` | 매니페스트를 보고 불러올 스킬 목록을 정함 |
| 도구 | `verify` | 포맷·린트·타입·테스트를 한 번에 돌리는 스크립트 |
| 도구 | `security-review` | 보안 리뷰 점검표 |

규칙이 겹치면 **프레임워크 > 언어 > 계층 > 공통** 순서로 따릅니다. 단, `code-principles`의 불변 규칙(비밀 보호, 경계 검증, 에러 삼키기 금지, 매개변수화)은 어느 계층도 풀 수 없습니다.

## 사용

```bash
claude --plugin-dir /path/to/skills_for_work/developer
```

플러그인 루트는 저장소 최상위가 아니라 `developer/` 디렉터리입니다.

대화에서 "설계부터 해서 이 기능 만들어줘"처럼 요청하면 `dev-workflow` 스킬이 파이프라인을 진행합니다. 에이전트는 `work-standards:developer`처럼 이름 앞에 플러그인 이름이 붙습니다.

## 검증 스크립트 정책

`skills/verify/scripts/verify.sh`의 `decide_exit` 함수가 차단 정책을 정합니다. 기본값은 가장 엄격해서, 실패나 건너뛴 검사가 하나라도 있으면 차단합니다. 팀 정책에 맞게 바꾸세요.

## 경계 확인 정책

에이전트 본문의 금지 규칙(읽기 전용, 인수 테스트 수정 금지, 행 밖 수정 금지)은 플러그인 에이전트에서 강제할 수 없습니다. 그래서 메인 대화가 서브에이전트 앞뒤로 `skills/dev-workflow/scripts/boundary-check.sh`를 실행해, 바뀐 경로를 허용 범위·보호 경로와 비교합니다.

허용 범위 밖 경로를 어떻게 다룰지는 같은 스크립트의 `classify_out_of_scope` 함수가 정합니다(`allow` / `report` / `block`). 기본값은 모두 `block`입니다. 잠금 파일, 워크스페이스 루트 매니페스트, 공용 설정을 팀 정책에 맞게 나누세요.

설계 배경은 [docs/design.md](docs/design.md)에 있습니다.
