---
name: stack-detection
description: 작업할 디렉터리의 매니페스트(package.json, pyproject.toml, Cargo.toml, go.mod)를 읽어 불러올 계층·언어·프레임워크 스킬 목록을 정하는 판별 규칙입니다. 설계자가 작업 분해표에 스킬 목록을 적을 때, 그리고 개발자·테스터·리뷰어가 스킬 목록 없이 호출됐을 때 사용합니다.
---

# 스택 판별

**의존성 이름이라는 확실한 근거로만 판별합니다.** 파일 확장자나 코드 모양으로 추측하지 않습니다.

## 절차

1. 작업 대상 파일에서 출발해 상위 디렉터리로 올라가며 **가장 가까운 매니페스트**를 찾습니다.
2. 그 매니페스트가 워크스페이스 루트일 뿐이면(아래 「워크스페이스」), 작업 파일이 속한 **멤버의 매니페스트**를 기준으로 삼습니다.
3. 아래 표에서 언어 → 프레임워크 → 계층 순서로 해당하는 행을 모두 고릅니다.
4. 결과를 「출력 형식」으로 적습니다. 근거(매니페스트 경로와 의존성 이름)를 반드시 함께 적습니다.

## 1. 언어

| 매니페스트 | 언어 스킬 |
|---|---|
| `package.json` (+ `tsconfig.json` 또는 `.ts` 파일) | `work-standards:typescript-standards` |
| `pyproject.toml`, `requirements*.txt`, `setup.cfg` | `work-standards:python-standards` |
| `go.mod` | `work-standards:go-standards` |
| `Cargo.toml` | `work-standards:rust-standards` |

## 2. 프레임워크

어느 필드를 볼지가 중요합니다. **기본은 런타임 의존성만 봅니다.** 테스트나 스토리북 때문에 `react`가 들어 있는 백엔드 패키지가 있기 때문입니다.

| 언어 | 볼 필드 | 의존성 | 프레임워크 스킬 |
|---|---|---|---|
| TS | `dependencies` | `react` | `work-standards:react-standards` |
| TS | `dependencies` **또는** `devDependencies` | `@tauri-apps/api`, `@tauri-apps/cli` | `work-standards:tauri-standards` |
| TS | `dependencies` | `@modelcontextprotocol/sdk` | `work-standards:mcp-server` |
| Python | `[project].dependencies`, `[tool.poetry.dependencies]`, `requirements.txt` (dev/test 파일 제외) | `fastapi` | `work-standards:fastapi-standards` |
| Python | 위와 같음 | `mcp`, `fastmcp` | `work-standards:mcp-server` |
| Rust | `[dependencies]` | `axum` | `work-standards:axum-standards` |
| Rust | `[dependencies]` | `tauri` | `work-standards:tauri-standards` |
| Rust | `[dependencies]` | `rmcp` | `work-standards:mcp-server` |
| Go | `require` | (아직 없음) | — |

Tauri CLI는 빌드 도구 자체가 프레임워크라서 `devDependencies`도 봅니다.

## 3. 계층

| 근거 | 계층 스킬 |
|---|---|
| `react` 또는 웹 UI 프레임워크가 있음, 또는 Tauri 프로젝트의 프론트엔드 디렉터리(`src/`) | `work-standards:frontend-principles` |
| `fastapi`, `axum`, MCP SDK가 있음, 또는 Python·Go·Rust 프로세스 | `work-standards:backend-principles` |
| Tauri 프로젝트의 `src-tauri/` | `work-standards:backend-principles` (예외 절의 「데스크톱 네이티브」를 따름) |
| 프레임워크 없는 TypeScript | **판별 불가** → 설계자가 정하고 설계서에 근거를 적습니다 |

한 작업 행에는 계층 스킬을 **하나만** 둡니다. 두 계층이 다 필요해 보이면 행을 디렉터리 단위로 나눕니다.

## 워크스페이스

| 도구 | 루트 표시 | 멤버 찾기 | 주의 |
|---|---|---|---|
| Cargo | `[workspace]`와 `members` | 작업 파일이 속한 크레이트의 `Cargo.toml` | 멤버에 `axum = { workspace = true }`처럼 적혀 있으면 루트의 `[workspace.dependencies]`에서 버전을 확인합니다 |
| npm/pnpm/yarn | `workspaces` 필드 또는 `pnpm-workspace.yaml` | `packages/*`, `apps/*` 아래 해당 패키지의 `package.json` | 루트 `package.json`에 없는 의존성이 멤버에만 있는 것이 정상입니다 |
| uv | `[tool.uv.workspace]` | 해당 멤버의 `pyproject.toml` | — |
| Go | `go.work` | 해당 모듈의 `go.mod` | — |

## 출력 형식

```
### 스킬 목록: <디렉터리>
- 근거: <매니페스트 경로> — <찾은 의존성들>
- 불러올 스킬:
  - work-standards:<계층 스킬>
  - work-standards:<언어 스킬>
  - work-standards:<프레임워크 스킬> (해당할 때만, 여러 개 가능)
- 판별 불가 항목: <없음 | 무엇이 왜 불확실한지>
```

## 불러오기

에이전트는 목록의 각 스킬을 `Skill` 도구로 불러옵니다. 이미 미리 로드된 스킬(`code-principles`, `stack-detection`)은 다시 불러오지 않습니다. 불러오기에 실패하면 이름을 바꿔 추측하지 말고, 실패한 이름을 보고합니다.
