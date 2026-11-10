# P4 보고서: work-standards bun 지원과 작업 종류(bugfix·refactor)

> 작업 지시서: `docs/briefs/p4-work-standards-bun-tasktypes.md` (근거: 통합 계획 §4)
> 일자: 2026-11-10. 커밋: 이 보고서가 포함된 `feat: work-standards bun 지원과 작업 종류 bugfix·refactor (P4)`

## 1. 바꾼 파일 목록

| 파일 | 무엇을 |
|---|---|
| `developer/skills/verify/tests/test_verify_bun.py` | 신규. bun 잠금 파일 6건 테스트(가짜 `bun`·`node`·`npm`·`pnpm` 실행 파일로 호출 로그 확인) |
| `developer/skills/verify/scripts/verify.sh` | `check_node`: `lock_dir`에 `bun.lock`·`bun.lockb` 추가, bun이면 `pm=bun`·node 불필요(존재 확인은 `bun`만), 스크립트 존재 확인을 `bun -e`로, 매니저 우선순위 bun → pnpm → yarn → npm |
| `developer/skills/verify/SKILL.md` | 판별 문장을 잠금 파일→매니저 표로 바꾸고 bun 행 추가, bun이면 node 없이 검사한다는 노트 추가 |
| `developer/skills/dev-workflow/scripts/boundary-check.sh` | `classify_out_of_scope` 주석의 보호 잠금 파일 목록에 bun 2종·`npm-shrinkwrap.json` 추가 |
| `developer/skills/dev-workflow/SKILL.md` | ⑥ 보호 잠금 파일 목록 갱신(bun 2종 포함, 전체 생태계 목록으로 통일). 「작업 종류」 절 신규(feature·bugfix·refactor 표 + refactor 실패 시 중단 규칙) |
| `developer/skills/typescript-standards/SKILL.md` | 툴체인 판별 줄에 bun 추가. node-standards에서 빠진 항목 3건 이전(§2 표). 「bun을 쓸 때」 절 신규(bun-runtime 함정 목록) |
| `developer/skills/stack-detection/SKILL.md` | 「bun 판별」 절 신규: 근거 3가지(잠금 파일, `bunfig.toml`, `packageManager: "bun@…"`) |
| `developer/docs/design.md` | §4 파이프라인 요점에 작업 종류 반영, 경계 확인 절에 보호 잠금 파일 목록 명시 |
| `developer/agents/tester.md` | 「작업 종류」 절 추가(종류별 RED/GREEN 확인 방법, refactor 실패 시 중단) |
| `developer/agents/developer.md` | 「작업 종류」 절 추가(종류별 GREEN 만들기, 동작 변경 금지) |

잠금 파일 목록은 다섯 군데(verify.sh, verify/SKILL.md, boundary-check.sh, dev-workflow/SKILL.md, typescript-standards/SKILL.md) 모두 같습니다: JS 6종(`bun.lock`, `bun.lockb`, `package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `yarn.lock`) + dev-workflow 계열 3곳은 `uv.lock`·`poetry.lock`·`Cargo.lock`·`go.sum`까지 같은 순서. `design.md`도 같은 목록을 따릅니다.

## 2. `node-standards` 비교 표 (claude-agents → typescript-standards)

| node-standards 항목 | typescript-standards에 있음? | 옮김 | 이유 |
|---|---|---|---|
| 정찰: 런타임·패키지 매니저 판별(bun 기준 포함) | 있음(툴체인 절) | 안 옮김 | 툴체인 절이 잠금 파일 판별을 이미 담당. bun 판별은 이번 작업으로 반영함 |
| 정찰: 지원 런타임 버전(`engines`, `packageManager`, 버전 고정 파일) | 없음 | **옮김** | 언어 스킬이 정할 항목인데 빠져 있었음 → 툴체인 절에 추가 |
| 정찰: 모듈 방식(ESM/CJS)과 TypeScript 여부 | 부분(ESM 기본만 규정) | 안 옮김 | work-standards는 ESM 기본을 이미 규정. 프로젝트 관례 확인은 설계 단계가 담당 |
| 정찰: 코드 구조(도메인별/계층별) | code-principles 구조 절이 담당 | 안 옮김 | ① 공통 스킬이 담당 |
| 정찰: 테스트 러너와 테스트 파일 위치 | 있음(테스트 절, `*.test.ts`) | 안 옮김 | — |
| 정찰: 검증에 쓸 scripts(typecheck·lint·test) | 있음(툴체인) + `verify` 스킬 | 안 옮김 | — |
| 정찰: 프로그램 종류(서버·CLI·라이브러리·stdio) | 언어 스킬 밖 | 안 옮김 | backend-principles(예외 절 포함)와 stack-detection 계층 판별이 담당 |
| 검증: typecheck script가 없어도 `tsc --noEmit` | 없음(정반대: "없으면 만들지 말고 보고") | 안 옮김 | typescript-standards 툴체인 규칙·verify 스크립트 정책과 충돌. 정책을 바꾸는 결정은 별도로 물어야 함 |
| 구조: 도메인 `index.ts` 공개 API, import 경계 | code-principles가 담당 | 안 옮김 | ①이 개념으로 담당 |
| 구조: 기능 1개 = 파일 1개(kebab-case) | 부분(파일 단위 분해는 code-principles) | 안 옮김 | kebab-case 강제는 React 등 프레임워크 관례(PascalCase)와 충돌. 프로젝트 관례에 맡김 |
| 구조: 테스트는 기능 파일 옆 | 있음 | 안 옮김 | — |
| 구조: 의존성 주입은 함수 인자 | code-principles 의존성 주입 절이 담당 | 안 옮김 | ①이 담당 |
| 관례: 비동기 I/O, 모든 Promise 처리, CPU 작업 worker | 부분(floating promises 금지) | 안 옮김 | backend-principles 동시성 절·Node 런타임 절이 담당 |
| 관례: `cause`로 에러 원인 보존 | 있음 | — | — |
| 관례: 내장 모듈 `node:` 접두사 | 없음 | **옮김** | 언어 수준 관례인데 빠져 있었음 → 모듈 절에 추가 |
| 관례: npm 배포 라이브러리는 `node:*` 표준 API만 | 없음 | **옮김** | 같은 이유 → 모듈 절에 추가 |
| 프레임워크 스킬 표(react·tauri·mcp) | 없음(의도적으로 비움) | 안 옮김 | v2 설계에서 판별표는 stack-detection이 담당 |

옮긴 항목은 3건(런타임 버전 확인, `node:` 접두사, 배포 라이브러리 `node:*` 제한). 나머지는 이미 있거나(①·②·stack-detection·verify가 담당) 정책 충돌로 옮기지 않았습니다.

## 3. 실행한 검증 명령과 결과

| 명령 (`developer/`에서) | 결과 |
|---|---|
| `uv run --with pytest pytest -q skills/verify/tests` (구현 전, RED 확인) | **3 failed, 3 passed** — 실패 3건: `bun.lock`→`bun run test` 아님, `bun.lockb`→같음, bun 잠금+node 없음→"건너뜀"으로 차단. 통과 3건은 기존 동작 고정 핀(하위 `package-lock.json` 우선, 잠금 없음→npm, boundary `bun.lock` 보호) |
| `uv run --with pytest pytest -q skills/verify/tests` (구현 후) | **6 passed**, 0 실패 |
| `uv run --with pytest pytest -q hooks/tests skills/verify/tests` (전체) | **74 passed**, 0 실패 (기존 hooks/tests 68 + 신규 6) |
| `bash -n skills/verify/scripts/verify.sh skills/dev-workflow/scripts/boundary-check.sh` | 통과 |
| `git diff`로 dev-workflow/SKILL.md 삭제 줄 확인 | 잠금 파일 목록이 든 불릿 1줄만 고쳤고, ②~⑧·④-1 번호와 feature 흐름 문구는 무변경 |

## 4. 계획서와 다르게 한 것과 이유

1. **스크립트 존재 확인 코드를 node/bun 하나로 통합했습니다.** 지시서는 "bun일 때는 `bun -e`로"였지만, `node -e`는 인자를 `process.argv`로 넘기는 방식이라 bun의 `-e` 인자 전달이 버전에 따라 다를 수 있어, 스크립트 이름을 eval 코드 안에 넣는 형태(`-e "…s['test']…"`; node에서도 동등)로 둘 다 바꿨습니다. 동작은 같고 bun 버전 영향을 받지 않습니다.
2. **`npm-shrinkwrap.json`을 보호 목록 3곳(dev-workflow, boundary-check, design.md)에도 추가했습니다.** 지시서는 bun 2종 추가만 말했지만 "모두 같은 목록이 되게" 조항에 따라 verify.sh에만 있던 항목을 맞췄습니다.
3. **verify/SKILL.md의 판별 문장을 표로 바꿨습니다.** "판별 표에 bun 행 추가"를 표가 없던 문장에 그대로 적용한 해석입니다(문장 → 잠금 파일·매니저 표 + bun 행).
4. **신규 테스트 6건 중 3건은 구현 전에도 통과했습니다.** "가장 가까운 잠금 파일" 우선·잠금 없음→npm·boundary 보호는 구현 전 동작과 같으므로 회귀 고정 핀으로 두었고, RED는 bun 3건 실패로 확인했습니다.
5. **dev-workflow의 워크스페이스 문구에 bun을 포함했습니다**("bun·npm·pnpm·Yarn·uv·Cargo 워크스페이스는…루트의 잠금 파일 하나를 바꾸므로"). bun 워크스페이스도 같은 구조라 보호 근거 문장의 빠진 이름을 채운 것입니다.
6. **구현을 Z.ai 에이전트가 아니라 이 세션(Claude)에서 직접했습니다.** 사용자가 이 worktree에서 지시서를 "그대로 수행"하라고 지시했고, 메모리 기록상 zai/opencode 경로는 인증 실패 상태입니다(§5).

## 5. 물어볼 것

1. **Z.ai 위임 원칙**: 이번엔 직접 구현했습니다. 앞으로도 세션 지시가 있으면 직접 할까요, 아니면 zai 래퍼(opencode 키) 인증을 먼저 고칠까요?
2. **Codex·Antigravity 검증 시점**: 커밋은 이 worktree에만 있고 push하지 않았습니다. 두 리뷰를 이 worktree 커밋 대상으로 언제 돌릴지 정해 주세요.
3. **typecheck script 없는 프로젝트에서 `tsc --noEmit` 강제**(node-standards 항목, 충돌로 안 옮김): verify 정책을 바꾸는 결정이 필요하면 별도 작업 지시로 넣을지 결정해 주세요.

## 검토 반영(1차)

Antigravity 검토 지적 4건을 반영했습니다(2026-11-10). 고친 범위는 `developer/skills/verify/tests/test_verify_bun.py`, `developer/agents/tester.md`, `developer/agents/developer.md`, 이 보고서입니다.

| # | 지적 | 무엇을 바꿨는지 |
|---|---|---|
| 1 | 가짜 실행 파일이 `-e` 호출에 항상 0을 돌려줘서, package.json에 스크립트가 없을 때 건너뛰는 분기를 검증하지 못함 | `FakePM`의 가짜 실행 파일을 python3 스크립트로 다시 씀. `-e <코드>`로 불리면 코드에서 스크립트 이름(`s['<이름>']`)을 뽑아 현재 디렉터리 `package.json`의 `scripts`에 있으면 0, 없으면 1을 돌려줌(그 밖의 호출은 종전대로 0). 신규 테스트 `test_bun_lock_without_test_script_skips_bun_run_test`: bun.lock + `scripts`에 test 없음 → `bun run typecheck`·`bun run lint`는 실행하고 `bun run test`는 부르지 않으며 "건너뜀 — test 스크립트가 없음" 출력(skip 차단 정책으로 종료 코드 1) |
| 2 | 같은 디렉터리에 잠금 파일이 여럿일 때 bun이 선택되는 테스트 없음 | 신규 테스트 `test_bun_lock_wins_over_npm_pnpm_locks_in_same_dir`: `bun.lock` + `package-lock.json` + `pnpm-lock.yaml`이 같은 디렉터리에 있으면 `bun run test`가 불리고 `npm`·`pnpm` 호출은 없음 |
| 3 | boundary-check 테스트에 `bun.lockb` 변경이 block되는 경우 없음 | 기존 `test_boundary_check_blocks_bun_lock_change`를 parametrize로 확장해 `bun.lock`·`bun.lockb` 두 케이스 모두 확인: 잠금 파일 내용 변경 → `--protect` 지정 시 보호 경로 위반(block, 종료 코드 1) |
| 4 | `tester.md`·`developer.md` 출력 형식의 `### RED 확인` 칸이 refactor 작업에서 모호함 | 두 파일의 출력 형식 첫머리에 `작업 종류: <feature \| bugfix \| refactor>` 줄을 추가하고, tester는 `### RED 확인`, developer는 대응 칸인 `### 인수 테스트`에 refactor일 때 적을 줄(`특성 테스트 GREEN N건(지금 코드)`)을 명시. feature 흐름 문구(명령·실패 N건·N/N 통과)는 무변경 |

검증 (`developer/`에서, 테스트 먼저 추가 → 실패 확인 → 고침 순서):

| 명령 | 결과 |
|---|---|
| `uv run --with pytest pytest -q skills/verify/tests` (테스트만 추가, 가짜 실행 파일 교체 전) | **1 failed, 8 passed** — 실패: `test_bun_lock_without_test_script_skips_bun_run_test`. 지적 그대로 `scripts`에 test가 없는데 `pass test bun run test`로 통과하던 결함이 재현됨(RED). 신규 2건(bun 우선, `bun.lockb` block)은 기존 구현으로 통과 |
| `uv run --with pytest pytest -q skills/verify/tests` (가짜 실행 파일 교체 후) | **9 passed**, 0 실패 |
| `uv run --with pytest pytest -q hooks/tests skills/verify/tests` (전체) | **77 passed**, 0 실패 (기존 hooks/tests 68 + verify 9: 종전 6건 + 신규 2건 + parametrize 확장 1건) |
| `bash -n skills/verify/scripts/verify.sh skills/dev-workflow/scripts/boundary-check.sh` | 통과 |

## 검토 반영(2차, EXAONE)

EXAONE 검토 지적 minor 2건을 반영했습니다(2026-11-10). 고친 범위는 `developer/skills/verify/scripts/verify.sh`, `developer/skills/verify/tests/test_verify_bun.py`, 이 보고서입니다.

| # | 지적 | 무엇을 바꿨는지 |
|---|---|---|
| 1 | `check_node`의 bun 분기에서 bun이 없을 때 검사 이름이 `node`로 기록됨(`skip_check "node" test "bun이 없음"` — 건너뜀 메시지와 요약 테이블 모두) | 테스트 `test_bun_lock_without_bun_skips_as_bun`(bun.lock 있음 + 가짜 bin에 bun 없음)을 먼저 추가해 실패를 확인한 뒤(RED), `skip_check "bun" test "bun이 없음"`으로 고침. 테스트는 종료 코드 1(skip 차단 임시 정책), "건너뜀: bun — bun이 없음" 출력, "건너뜀: node" 부재, 패키지 매니저 호출 로그가 비어 있음을 단언 |
| 2 | "bun 잠금 + node 없음" 테스트(`test_bun_lock_without_node_still_runs`)가 PATH에 `/usr/bin` 등을 넣어, 시스템 node가 설치된 환경에서는 전제(node 없음)가 깨짐 | `test_bun_lock_with_node_on_path_still_runs_bun`로 다시 씀. `FakePM`에 `failing` 옵션을 더해, 가짜 실행 디렉터리에 호출되면 로그를 남기고 exit 1 하는 `node`(신규 `FAIL_BIN`)를 둠. node가 PATH에 있어도 전제가 깨지지 않고, bun 분기가 node를 부르지 않는다는 것을 node 호출 로그가 비어 있음으로 단언 |

함께 손본 것: `FakePM.calls()`는 로그 파일이 아직 없으면(도구가 한 번도 불리지 않음) 빈 목록을 돌려주게 했습니다. 지적 1의 테스트처럼 아무 도구도 불리지 않는 경우를 잡기 위함입니다.

검증 (`developer/`에서, 테스트 먼저 추가 → 실패 확인 → 고침 순서):

| 명령 | 결과 |
|---|---|
| `uv run --with pytest pytest -q skills/verify/tests/test_verify_bun.py -k "without_bun or with_node_on_path"` (테스트만 추가, verify.sh 고치기 전) | **1 failed, 1 passed** — 실패: `test_bun_lock_without_bun_skips_as_bun`. 출력이 "건너뜀: node — bun이 없음"이고 요약에도 `skip test node`로 남아 검사 이름 단언에 걸림(RED). 재작성한 `test_bun_lock_with_node_on_path_still_runs_bun`은 기존 구현으로 통과(이미 node를 부르지 않음) |
| `uv run --with pytest pytest -q hooks/tests skills/verify/tests` (verify.sh 수정 후, 전체) | **78 passed**, 0 실패 (hooks/tests 68 + verify 10: 종전 9건 − 재작성 1건 + 신규 2건) |
| `bash -n skills/verify/scripts/verify.sh` | 통과 |
