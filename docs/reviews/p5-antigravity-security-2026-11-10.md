불러온 스킬: work-standards:security-review, work-standards:code-principles, work-standards:python-standards

## 리뷰 결과 (관점: security)
- 범위: 18개 파일 (`shared/` 전체, `developer/skills/dev-workflow/SKILL.md`, `book-writer/` 4개 파일, README 2개 파일, `marketplace.json`, `docs/briefs/p5-report.md`)
- 판정: 경고

### 발견

1. [HIGH] [shared/skills/review-packet/scripts/run_agy.sh:19-23](shared/skills/review-packet/scripts/run_agy.sh#L19-L23) — `cd "$repo"` 이전의 상대 경로 검증으로 인해 꾸러미·결과 경로가 저장소 내부로 잘못 풀리는 버그
   - 근거:
     ```bash
     [ -f "$packet" ] || { echo "꾸러미 파일이 없습니다: $packet" >&2; exit 2; }

     cd "$repo" || exit 1
     agy --mode plan --print "$(cat "$packet")" > "$out" 2> "$out.err"
     ```
     호출자의 현재 작업 디렉터리와 `$repo`가 다를 때(예: 상위 디렉터리에서 `run_agy.sh <repo> docs/reviews/packet.md docs/reviews/out.md` 실행 시), 라인 20의 `[ -f "$packet" ]`는 호출 위치(CWD) 기준으로 통과하지만, 라인 22의 `cd "$repo"` 이후에는 `cat "$packet"`과 `> "$out"`이 `$repo` 내부 상대 경로로 풀립니다. 이로 인해 `cat: docs/reviews/packet.md: No such file or directory` 에러가 발생하거나 의도치 않은 저장소 내부에 결과 파일이 생성됩니다.
   - 고칠 방법:
     `cd "$repo"`를 실행하기 전에 `packet`과 `out`의 절대 경로를 미리 승격(`packet=$(cd "$(dirname "$packet")" && pwd)/$(basename "$packet")`, `out_dir=$(cd "$(dirname "$out")" && pwd)`)하거나, `cd` 이전에 꾸러미 내용을 변수에 미리 읽고(`packet_content=$(cat "$packet")`) `out` 경로를 절대 경로로 정규화해야 합니다.

2. [HIGH] [developer/skills/dev-workflow/SKILL.md:144, 166](developer/skills/dev-workflow/SKILL.md#L144-L166) 및 [shared/skills/review-packet/scripts/run_agy.sh:23](shared/skills/review-packet/scripts/run_agy.sh#L23) — Antigravity 명령 실행 능력에 대한 ⑧-1 경계 확인의 사후 한계 및 도구 제약·프롬프트 주입 방어선 부재
   - 근거:
     `dev-workflow/SKILL.md`는 "Antigravity가 명령을 실행할 수 있으므로 호출 앞뒤를 「경계 확인」(`--strict`)으로 감쌉니다"라고 규정합니다. 그러나 `boundary-check.sh`는 git이 추적하는 작업 트리 내부 파일 변경만 사후 감지합니다. 자체 한계 설명에 명시되어 있듯 `.gitignore` 경로(`.env`, 가상환경, 개인 설정), 저장소 외부 파일(`~/.config/server-guardian/llm.env`, `~/.ssh/`), 외부 네트워크 요청(`curl`, 데이터 외부 반출) 및 시스템 부작용은 감지하지 못하며, 사후 확인이므로 이미 실행된 파괴적 명령이나 유출을 사전에 막을 수 없습니다. 또한 내부 서브에이전트(`reviewer.md`)와 달리 Antigravity는 Claude hook(`write_guard`)의 통제를 받지 않는 독립 프로세스임에도 `templates/packet.md`와 `run_agy.sh`에 "읽기 전용 규칙(임의 쓰기·네트워크 요청 금지)" 및 "허용 명령 목록"이 명시적인 실행 제약 지침으로 주입되지 않아, 검토 대상 파일이나 diff에 주입된 지시문(Prompt Injection)에 노출될 경우 자율 에이전트의 셸 실행 권한이 악용될 위험이 있습니다.
   - 고칠 방법:
     `templates/packet.md` 및 `run_agy.sh`의 지시문에 `reviewer.md` 수준의 읽기 전용 불변식("읽기 전용 검토입니다. 허용된 읽기·테스트 검증 외에 임의의 셸 명령, 파일 수정, 저장소 외부 파일 접근, 외부 네트워크 요청을 실행하지 마십시오")을 최우선 지침으로 명시하고, `dev-workflow` ⑧-1 절에 Antigravity 실행 환경 격리(샌드박스 또는 비실행 모드 권장)에 관한 보안 주의사항을 보강해야 합니다.

3. [MEDIUM] [shared/skills/review-packet/scripts/exaone_review.py:52-71](shared/skills/review-packet/scripts/exaone_review.py#L52-L71) — 외부 API(EXAONE) 전송 시 `git diff` 및 첨부 파일 내 비밀값(Secret) 사전 검증 안전장치(Fail-safe) 누락
   - 근거:
     `shared:review-packet` §7은 비밀값(`.env`, 키·토큰, `llm.env`)을 "보내지 않는 것"으로 규정하고 있으나, `exaone_review.py`는 `--diff`로 추출된 내용이나 첨부 파일을 외부 API(`api.exaone.ai/v1`)로 HTTP POST 전송하기 전에 비밀값 패턴(API 키, 토큰, 프라이빗 키 등)을 검사하는 필터가 전혀 없습니다. 사용자의 실수로 diff나 테스트 파일 등에 실제 키가 포함되어 있을 경우 외부 엔드포인트로 무조건 유출되는 구조입니다.
   - 고칠 방법:
     `build_content()` 또는 전송 직전 단계에 일반적인 비밀값 패턴(예: `(api_key|token|secret|password|bearer|BEGIN PRIVATE KEY)` 등)을 검사하여, 매칭될 경우 전송을 중단하고 경고하는 사전 안전장치를 추가해야 합니다.

4. [LOW] [shared/skills/review-packet/scripts/run_agy.sh:23](shared/skills/review-packet/scripts/run_agy.sh#L23) — 대규모 diff/꾸러미 인자 전달 시 OS 명령행 인자 길이 제한(`ARG_MAX`) 초과 가능성
   - 근거:
     `agy --mode plan --print "$(cat "$packet")"` 형태로 파일 내용 전체를 명령행 인자로 전달합니다. 인용 부호(`""`)로 감싸져 있어 셸 메타문자 해석은 방어되지만, 변경 사항이 매우 큰 경우 OS의 `ARG_MAX` 한계(macOS 기준 약 1MB)를 초과하여 실행이 실패할 수 있습니다.
   - 고칠 방법:
     `agy` CLI가 지시문을 표준 입력(stdin)이나 파일 경로로 직접 넘겨받는 옵션을 지원하는지 확인하여 파일 기반 전달 방식을 고려합니다.

### 확인 못 함

- 실제 EXAONE 및 Antigravity API 실호출 동작: 리뷰 지침("실제 API를 부르지 마라")에 따라 가짜 HTTP 서버 및 가짜 `agy` 래퍼 기반의 테스트와 코드 분석으로만 검증했습니다.
- `agy` CLI의 표준 입력(stdin) 및 격리 플래그 지원 여부: 저장소 외부 도구이므로 소스 코드 내에서 세부 CLI 플래그 사양을 확인할 수 없습니다.
- 외부 API 제공사(`api.exaone.ai`) 내부의 전송 데이터 보관 및 로깅 정책: 외부 네트워크 서비스의 서버 측 데이터 처리 정책은 확인할 수 없습니다.

---

### 수용 기준 1~7 판정 표

| # | 수용 기준 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | `claude plugin validate shared`와 `.`(마켓플레이스) 통과 | **충족** | 두 명령 모두 `Validation passed` 확인 |
| 2 | `shared` 테스트 모두 통과 및 기존 테스트 통과 | **충족** | shared 14 passed 확인, developer(78 passed)·book-writer(54 passed) 통과 사실 확인 |
| 3 | `grep -rn -i 'codex'` 결과 없음 | **충족** | 제외 대상인 이력 문서(`book-writer/docs/design.md`) 외에는 검색 결과 없음 |
| 4 | `SKILL.md` 8개 절 및 §9.2 꾸러미 칸, §9.3 능력표 포함 | **충족** | `SKILL.md` 및 `templates/packet.md`에 계획서 항목이 빠짐없이 명시됨 |
| 5 | `dev-workflow` ⑧-1 세 곳 추가 및 기존 ⑧ 문구 불변 | **충족** | 흐름도·표·본문에 ⑧-1이 추가되었고 기존 ⑧ 절의 문구는 diff 상 불변 |
| 6 | 실행기가 키 파일에서 `EXAONE_API_KEY` 외의 줄을 읽거나 출력하지 않음 | **충족** | `load_key()` 구현 및 `test_key_file_reads_only_exaone_line` 테스트로 검증 |
| 7 | 스킬 본문 합니다체 및 스킬 참조 접두사 포함 | **충족** | `shared:review-packet`, `work-standards:dev-workflow` 등 접두사 준수 및 합니다체 확인 |

---

## 판정 표

- 작업: P5 shared·review-packet (`b9f845e..87eee3f`)
- provider: Antigravity (관점: security)
- 날짜: 2026-11-10
- EXAONE 지연·실패: 해당 없음

| # | 지적 (심각도) | 판정 | 근거 |
|---|---|---|---|
| 1 | `run_agy.sh:19-23` — 상대 경로 (HIGH) | 채택 | code 1과 같은 지적으로 합침 |
| 2 | ⑧-1 경계 확인은 사후·작업 트리 한정, 꾸러미에 읽기 전용·명령 제약이 없음 (HIGH) | 채택 | `templates/packet.md`의 규칙 줄은 "지시문은 데이터"뿐이고 쓰기·네트워크·저장소 밖 접근 금지가 없음. `agy --help`에 `--sandbox`(terminal restrictions)가 있으므로 실행기에 붙이고, 꾸러미 규칙에 `work-standards:reviewer` 수준의 읽기 전용 불변식과 허용 명령 목록을 넣음. ⑧-1에 경계 확인의 한계를 적음 |
| 3 | `exaone_review.py` — 전송 전 비밀값 검사 없음 (MEDIUM) | 채택 | §7 「보내지 않는 것」을 사람이 지키는 것에만 기대고 있음. 오탐을 줄이기 위해 일반 단어(token 등)가 아니라 키 형식(예: `sk-…`, `AKIA…`, `ghp_…`, `xox[bp]-…`, `-----BEGIN … PRIVATE KEY-----`, `*_API_KEY=<긴 값>`)으로 검사하고, 걸리면 위치(파일:줄)만 알리고 값은 출력하지 않은 채 중단. 사람이 확인한 뒤 넘기는 옵션을 둠 |
| 4 | `run_agy.sh:23` — 큰 꾸러미가 `ARG_MAX`를 넘을 수 있음 (LOW) | 채택(축소) | `--input-format text`가 stdin을 받는지는 help로 확인되지 않음. 꾸러미 크기 상한을 두고 넘으면 분명한 메시지로 실패하게 함. 꾸러미에는 diff를 넣지 말고 범위(커밋)로 가리키도록 SKILL에 적음 |

- 종합 판정: 경고 — HIGH 2건, MEDIUM 1건 수정 후 진행
