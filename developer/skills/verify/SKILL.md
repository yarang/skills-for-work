---
name: verify
description: 구현을 마친 디렉터리에서 포맷·린트·타입 검사·테스트를 한 번에 돌리는 결정적 검증 스크립트입니다. 매니페스트(package.json, pyproject.toml, go.mod, Cargo.toml)를 보고 도구를 고르며, 종료 코드로 통과·차단을 알려 줍니다. 개발자가 구현을 끝냈다고 보고하기 전, 그리고 메인 대화가 ⑦ 검증의 ⓑ 행 verify에서 다시 실행할 때 사용합니다.
---

# 검증

검증은 판단이 아니라 **스크립트**입니다. 같은 코드에는 언제나 같은 결과가 나와야 하므로 모델이 결과를 해석해 통과시키지 않습니다.

## 실행

작업 행의 디렉터리마다 한 번씩 실행합니다.

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/verify.sh" <작업 디렉터리>
```

| 종료 코드 | 뜻 | 할 일 |
|---|---|---|
| 0 | 통과 | 요약 표를 보고서에 붙입니다 |
| 1 | 차단 | 실패한 검사를 고치고 다시 실행합니다 |
| 2 | 사용법 오류 | 디렉터리나 매니페스트가 없습니다. 경로를 확인합니다 |

## 검사 항목

| 언어 | 포맷 | 린트 | 타입 | 테스트 |
|---|---|---|---|---|
| TypeScript | — (lint 스크립트에 포함) | `<pm> run lint` | `<pm> run typecheck` | `<pm> run test` |
| Python | `ruff format --check` | `ruff check` | `mypy` 또는 `pyright` (설정된 것) | `pytest -q` |
| Go | `gofmt -l` | `go vet`, `golangci-lint`(설정 있을 때) | (컴파일러) | `go test -race ./...` |
| Rust | `cargo fmt --check` | `cargo clippy -D warnings` | (컴파일러) | `cargo test` 또는 `cargo nextest` |

- TypeScript는 패키지 매니저를 잠금 파일로 고르고, `package.json`에 있는 스크립트만 실행합니다. 없는 스크립트는 `skip`으로 기록합니다.
- Python은 대상 디렉터리나 그 위(저장소 루트까지)에 `uv.lock`이 있으면 `uv run --frozen`으로 가상환경 안에서 실행합니다. 워크스페이스 멤버도 루트 잠금 파일로 잡히고, `--frozen`이라 잠금 파일을 고치지 않습니다. Node의 `pnpm-lock.yaml`·`yarn.lock`도 같은 방식으로 찾습니다.
- 도구가 없거나 설정이 없으면 `skip`입니다. `skip`을 통과로 볼지는 스크립트의 `decide_exit` 정책이 정합니다.

## 실패했을 때

- **검사를 약하게 만들어 통과시키지 않습니다.** 린트 규칙 끄기, `# type: ignore`·`@ts-expect-error`·`#[allow]` 추가, 테스트 건너뛰기(`skip`, `xfail`, `.only`), 엄격 옵션 해제는 고친 것이 아닙니다. 꼭 필요하면 이유와 함께 보고서에 적고 리뷰어 판단을 받습니다.
- 인수 테스트가 실패하면 구현을 고칩니다. 인수 테스트 자체가 틀렸다고 판단되면 고치지 말고 보고합니다(설계 단계로 되돌림).
- 같은 실패가 세 번 반복되면 멈추고 원인 분석과 함께 보고합니다.

## 보고 형식

```
### 검증: <작업 디렉터리>
- 결과: 통과 | 차단 (종료 코드 N)
- 요약:
  pass  format  ruff format
  pass  lint    ruff check
  ...
- 건너뛴 검사와 이유: <없음 | 목록>
```
