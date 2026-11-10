# 작업 지시서 P4: work-standards에 bun 지원과 작업 종류(bugfix·refactor) 추가

> 근거: `docs/plans/2026-11-10-integrate-claude-agents.md` §4 (승인 2026-11-10)
> 맡는 쪽: Z.ai 구현 에이전트. 검토: Antigravity가 이 문서의 「수용 기준」으로 판정합니다.
> P1과 병렬로 진행합니다. P1은 `book-writer/`만, P4는 `developer/`만 고칩니다.

## 목표
1. work-standards가 bun 프로젝트(`bun.lock`, `bun.lockb`)를 알아보고, 검증·보호·관례를 bun 기준으로 처리합니다.
2. claude-agents `node-standards`에만 있고 `typescript-standards`에 없는 항목을 옮깁니다.
3. `dev-workflow`에 작업 종류 `feature`(지금과 같음)·`bugfix`·`refactor`를 더합니다.

## 읽을 것 (읽기만 함)
| 무엇 | 위치 |
|---|---|
| 승인된 계획 §4 | `docs/plans/2026-11-10-integrate-claude-agents.md` |
| bun 원본 | `/Users/yarang/working/tools/claude-agents/skills/bun-runtime/SKILL.md` |
| node 원본 | `/Users/yarang/working/tools/claude-agents/skills/node-standards/SKILL.md` |
| bugfix·refactor 원본 | `/Users/yarang/working/tools/claude-agents/roles/implementer.md`의 모드 설명 |
| 설계 문서 | `developer/docs/design.md` |

## 바꿀 파일과 할 일
잠금 파일 목록이 나오는 곳은 지금 다섯 군데입니다. 모두 같은 목록이 되게 고칩니다.

| 파일 | 할 일 |
|---|---|
| `developer/skills/verify/scripts/verify.sh` | `check_node`: `lock_dir`에 `bun.lock`, `bun.lockb`를 더하고, 가장 가까운 잠금 파일이 bun이면 `pm=bun`. bun이면 `node`가 없어도 됩니다(있는 것은 `bun`만 확인). `package.json` 스크립트 존재 확인도 bun일 때는 `bun -e`로 합니다. 같은 디렉터리에 잠금 파일이 여럿이면 지금 순서(pnpm → yarn → npm) 앞에 bun을 둡니다. macOS bash 3.2 호환을 유지합니다 |
| `developer/skills/verify/SKILL.md` | 판별 표에 bun 행 추가 |
| `developer/skills/dev-workflow/scripts/boundary-check.sh` | 보호 잠금 파일 목록에 `bun.lock`, `bun.lockb` 추가 |
| `developer/skills/dev-workflow/SKILL.md` | 잠금 파일 목록에 bun 추가. 그리고 아래 「작업 종류」 |
| `developer/skills/typescript-standards/SKILL.md` | 잠금 파일 판단 줄에 `bun.lock`/`bun.lockb` → bun 추가. `bun-runtime`의 함정 목록을 「bun을 쓸 때」 절로 추가. `node-standards`와 비교해 빠진 항목만 옮김 |
| `developer/skills/stack-detection/SKILL.md` | bun 판별 근거(잠금 파일, `bunfig.toml`, `package.json`의 `packageManager: bun@…`) 추가 |
| `developer/docs/design.md` | 잠금 파일 목록과 작업 종류를 반영 |

`node-standards`와 비교한 결과는 보고서에 표로 남깁니다(항목, `typescript-standards`에 있음/없음, 옮김/안 옮김과 이유). 옮길 것이 없으면 그렇게 적습니다.

## 작업 종류 (`dev-workflow`)
절차 첫머리에서 메인 대화가 작업 종류를 정하고, 설계서·tester·developer 작업 지시에 적습니다.

| 종류 | tester | developer |
|---|---|---|
| `feature` | 지금과 같음: 인수 테스트를 쓰고 RED 확인 | GREEN |
| `bugfix` | 버그를 **재현하는** 테스트를 쓰고, 그 테스트가 버그 때문에 실패(RED)하는지 확인. 실패 메시지가 보고된 증상과 맞아야 함 | 재현 테스트를 GREEN으로. 재현 테스트 밖의 동작은 바꾸지 않음 |
| `refactor` | 바꿀 범위의 현재 동작을 고정하는 **특성 테스트**를 쓰고, 지금 코드에서 GREEN인지 확인(RED 단계 없음) | 한 번에 하나씩 바꾸고, 바꿀 때마다 특성 테스트가 GREEN인지 확인. 동작 변경 금지 |

- `refactor`에서 특성 테스트가 지금 코드에서 실패하면 멈추고 보고합니다(이미 깨진 동작을 고정하지 않음).
- `developer/agents/tester.md`와 `developer/agents/developer.md`에 작업 종류별로 달라지는 점을 짧게 더합니다.
- 기존 `feature` 흐름의 문구·번호(②~⑧, ④-1)는 바꾸지 않습니다.

## 테스트
`developer/skills/verify/tests/test_verify_bun.py`를 새로 만듭니다(pytest, 표준 라이브러리 + pytest만).
- 임시 디렉터리에 `package.json`(`scripts.test` 있음)과 잠금 파일을 만들고, `PATH` 앞에 가짜 `bun`·`node`·`npm`·`pnpm` 실행 파일(받은 인자를 로그 파일에 적고 exit 0)을 둔 뒤 `verify.sh`를 실행합니다.
- 확인할 것: `bun.lock` → `bun run test` 호출, `bun.lockb` → 같음, bun 잠금 + node 없음 → 건너뛰지 않고 실행, 상위 디렉터리의 `bun.lock` + 하위의 `package-lock.json` → 하위는 npm(가장 가까운 것), 잠금 파일 없음 → 지금처럼 npm.
- `boundary-check.sh`에서 `bun.lock` 변경이 block으로 판정되는 테스트 1건(스크립트를 직접 호출하는 방법은 스크립트 사용법을 따름).

**테스트를 먼저 쓰고 실패를 확인한 뒤** 구현합니다.

실행:
```
cd developer
uv run --with pytest pytest -q hooks/tests skills/verify/tests
bash -n skills/verify/scripts/verify.sh skills/dev-workflow/scripts/boundary-check.sh
```

## 수용 기준
1. 위 표의 모든 파일에서 잠금 파일 목록이 같습니다(bun 2종 포함).
2. 새 테스트와 기존 `hooks/tests`(68개)가 모두 통과합니다. `bash -n` 통과.
3. `node-standards` 비교 표가 보고서에 있습니다.
4. `dev-workflow`에 작업 종류 표가 있고, tester·developer 에이전트가 그 표를 따릅니다. `feature` 흐름은 바뀌지 않았습니다(diff로 확인).
5. 스킬 본문 문체는 합니다체입니다.

## 바꾸지 않을 것
- `book-writer/`, `docu-writer/`, `docs/` 아래 파일
- claude-agents 저장소, `~/.claude/` 아래 파일
- `developer/hooks/` 구현(테스트 실행만)

## 보고서 형식
1. 바꾼 파일 목록
2. `node-standards` 비교 표
3. 실행한 검증 명령과 결과(통과·실패 개수)
4. 계획서와 다르게 한 것과 이유
5. 물어볼 것
