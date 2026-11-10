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
- 잠금 파일은 대상 디렉터리부터 저장소 루트까지 올라가며 **가장 가까운 것**을 씁니다. 워크스페이스 멤버는 루트 잠금 파일로 잡히고, 자기 잠금 파일이 있는 하위 프로젝트는 상위 것에 끌려가지 않습니다.
- Python은 그 잠금 파일이 `uv.lock`이면 `uv run --frozen`으로 가상환경 안에서 실행합니다. `--frozen`이라 잠금 파일을 고치지 않습니다. `pyproject.toml`이 없는 디렉터리(`requirements.txt`만 있음)는 uv 프로젝트가 아니므로 위의 uv 환경을 쓰지 않고 가상환경 밖에서 검사합니다. 위에 `uv.lock`이 있지만 워크스페이스 멤버가 아니어서 자기 잠금 파일을 찾지 못하는 프로젝트도 가상환경 밖에서 검사합니다. 이 확인은 `.venv`를 만들지 않는 `uv tree --frozen --depth 0`으로 먼저 합니다. 가장 가까운 잠금 파일이 `poetry.lock`이면 `poetry run`을 쓰지 않으므로, 도구가 들어 있는 Poetry 가상환경을 활성화한 뒤 실행합니다. 그 밖의 `uv run` 실패(빌드 실패, Python 버전, 손상된 잠금 파일)는 환경 준비 실패(test 종류 fail)로 기록하고 Python 검사를 멈춥니다.
- Node는 그 잠금 파일로 패키지 매니저를 고릅니다. 같은 디렉터리에 잠금 파일이 여럿이면 표의 위 행부터 고릅니다(bun → pnpm → yarn → npm).

  | 잠금 파일 | 패키지 매니저 |
  |---|---|
  | `bun.lock`, `bun.lockb` | bun |
  | `pnpm-lock.yaml` | pnpm |
  | `yarn.lock` | yarn |
  | `package-lock.json`, `npm-shrinkwrap.json`, 또는 잠금 파일 없음 | npm |

- 잠금 파일이 bun이면 런타임도 bun이므로 node가 없어도 됩니다. 있는 것은 bun만 확인하고, `package.json` 스크립트 존재 확인도 `bun -e`로 합니다. 검사는 `bun run <script>`로 실행합니다.
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
