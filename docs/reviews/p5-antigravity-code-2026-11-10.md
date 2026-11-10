불러온 스킬: work-standards:code-principles, work-standards:python-standards

## 리뷰 결과 (관점: code)
- 범위: 18개 파일 (`shared/` 전체 10개, `developer/skills/dev-workflow/SKILL.md`, `book-writer/` 4개, `.claude-plugin/marketplace.json`, `developer/README.md`, `docs/briefs/p5-report.md`)
- 판정: 경고

### 발견

1. [HIGH] [`shared/skills/review-packet/scripts/run_agy.sh:20-23`](shared/skills/review-packet/scripts/run_agy.sh#L20-L23) — `cd "$repo"` 이후 상대 경로 `$packet`과 `$out`이 대상 저장소 기준으로 풀려 실행 실패 및 결과 누락 발생
   - 근거:
     ```bash
     [ -d "$repo" ] || { echo "저장소가 없습니다: $repo" >&2; exit 2; }
     [ -f "$packet" ] || { echo "꾸러미 파일이 없습니다: $packet" >&2; exit 2; }

     cd "$repo" || exit 1
     agy --mode plan --print "$(cat "$packet")" > "$out" 2> "$out.err"
     ```
     호출 위치에서 `[ -f "$packet" ]` 검사를 통과하더라도 `cd "$repo"`를 수행한 뒤에는 작업 디렉터리가 바뀌므로, `$packet`이나 `$out`이 상대 경로(`packet.md`, `reviews/out.md` 등)일 경우 호출 위치 기준이 아닌 대상 저장소(`$repo`) 내부 경로로 풀립니다. 그 결과 `cat "$packet"`이 실패(`No such file or directory`)하여 빈 프롬프트가 전달되거나, 결과 파일(`$out`, `$out.err`)이 대상 저장소 내부에 생기거나 부모 디렉터리 부재로 리다이렉션 에러가 발생합니다. 기존 [`test_run_agy.py`](shared/skills/review-packet/tests/test_run_agy.py#L21-L26)는 인자를 모두 `pathlib.Path` 절대 경로로 넘겨 이 버그를 잡지 못했습니다.
   - 고칠 방법: `cd "$repo"`를 실행하기 전에 `packet`과 `out`을 절대 경로로 정규화하거나, `cat "$packet"` 내용을 변수에 먼저 읽어두고 `out`의 절대 경로를 계산합니다. bash 3.2 호환 절대 경로 변환 예시:
     ```bash
     to_abs() {
       local dir base
       dir=$(dirname "$1")
       base=$(basename "$1")
       echo "$(cd "$dir" && pwd)/$base"
     }
     packet=$(to_abs "$packet")
     out_dir=$(cd "$(dirname "$out")" && pwd)
     out="$out_dir/$(basename "$out")"
     ```

2. [MEDIUM] [`book-writer/skills/book-workflow/SKILL.md:68`](book-writer/skills/book-workflow/SKILL.md#L68) — 수용 기준 7(스킬 본문 합니다체) 위반 (한다체 문장 삽입)
   - 근거:
     ```markdown
     - 사용자 지침에 외부 검토가 있으면 `shared:review-packet`대로 꾸러미를 만들어 Antigravity로 검토하고, `추가 검토: exaone`이면 EXAONE도 함께 돌린다. 기준 파일(이 스킬, `book-writer:book-principles`, `book-writer:korean-style`, 책의 집필 규칙)과 계획 문서를 꾸러미의 기준·참고 원본에 넣는다.
     ```
     주변 문장(`검토합니다`, `남깁니다`, `적습니다`, `옮겨 붙입니다`)과 달리, 지시서 인용 문구를 그대로 복사하면서 종결어미가 `돌린다`, `넣는다`로 작성되어 수용 기준 7("스킬 본문은 합니다체")에 어긋납니다.
   - 고칠 방법: `돌린다.` → `돌립니다.`, `넣는다.` → `넣습니다.` 로 수정합니다.

3. [LOW] [`shared/skills/review-packet/scripts/exaone_review.py:92-95`](shared/skills/review-packet/scripts/exaone_review.py#L92-L95) — SSE 파싱 시 빈 `data:` 줄 처리 방어 누락
   - 근거:
     ```python
     data = line[len("data:"):].strip()
     if data == "[DONE]":
         break
     chunk = json.loads(data)
     ```
     SSE 스트림에서 빈 데이터 라인(`data:\n` 또는 `data: \n`)이 들어올 경우 `data`가 `""`가 되어 `json.loads("")` 호출 시 `JSONDecodeError`가 발생할 수 있습니다.
   - 고칠 방법: `if not data: continue` 구문을 추가합니다.

4. [LOW] [`shared/skills/review-packet/scripts/exaone_review.py:74,82`](shared/skills/review-packet/scripts/exaone_review.py#L74-L82) — `retry_wait`와 `read_stream` 함수 인자 타입 힌트 누락
   - 근거: `developer/skills/python-standards/SKILL.md`는 "공개 함수에는 인자와 반환 타입을 모두 적습니다"를 규정합니다. `retry_wait`의 `headers`와 `read_stream`의 `resp` 매개변수에 타입 힌트가 누락되어 있습니다.
   - 고칠 방법: `headers: email.message.Message | dict[str, str]`, `resp: typing.Iterable[bytes]` 등으로 명시합니다.

5. [LOW] [`shared/skills/review-packet/tests/test_run_agy.py`](shared/skills/review-packet/tests/test_run_agy.py#L21-L26) — 상대 경로 전달 시의 동작을 검증하는 테스트 케이스 부재
   - 근거: `run_agy` 헬퍼 함수가 모든 인자를 절대 경로로 넘기고 있어 상대 경로 전달 시의 동작이 검증되지 않습니다.
   - 고칠 방법: `packet`과 `out`을 상대 경로로 넘겨도 정상 동작하는지 검증하는 테스트 케이스를 추가합니다.

### 확인 못 함

- 실제 EXAONE API 및 Antigravity CLI 네트워크 통신: 수용 기준 및 리뷰 규칙("실제 EXAONE·Antigravity 호출 금지")에 따라 실제 외부 API를 부르지 않고 로컬 모의 환경(가짜 SSE 서버 및 가짜 `agy` 바이너리)으로만 검증했으므로, 실제 외부 엔드포인트의 네트워크 지연 및 실서버 특성은 확인하지 못했습니다.

---

### 수용 기준 1~7 판정 표

| # | 수용 기준 | 판정 | 근거 |
|---|---|:---:|---|
| 1 | `claude plugin validate shared`와 `claude plugin validate .`(마켓플레이스) 통과 | **충족** | 두 명령 모두 `Validation passed`로 성공(아이콘/README 권고 경고는 통과 판정에 무영향) |
| 2 | `shared` 테스트 모두 통과. 기존 테스트도 통과 | **충족** | `shared` 14 passed, `developer` 78 passed, `book-writer` 54 passed 확인 |
| 3 | `grep -rn -i 'codex' book-writer/ developer/skills/dev-workflow/ shared/` 결과 없음 | **충족** | 이력 문서인 `book-writer/docs/design.md:73` 외 대상 코드 및 워크플로 스킬에서 `Codex` 완전 제거됨 |
| 4 | `SKILL.md`에 8개 절이 있고, 계획서 §9.2 꾸러미 칸과 §9.3 능력표가 빠짐없이 들어 있음 | **충족** | `review-packet/SKILL.md`에 8개 절 구성 및 §9.2 틀, §9.3 4개 provider 능력표 완비 |
| 5 | dev-workflow에 ⑧-1이 표·흐름도·본문 세 곳에 있고, 기존 ⑧ 문구는 바뀌지 않음 | **충족** | `dev-workflow/SKILL.md` diff 확인 결과 세 곳에 ⑧-1 반영 완료, 기존 ⑧ 문구 및 번호 불변 |
| 6 | 실행기가 키 파일에서 `EXAONE_API_KEY` 외의 줄을 읽거나 출력하지 않음 | **충족** | `load_key()`가 `EXAONE_API_KEY=` 줄만 식별해 읽으며 `test_key_file_reads_only_exaone_line` 통과 |
| 7 | 스킬 본문은 합니다체, 스킬 참조에는 접두사가 붙어 있음 | **미충족** | `shared/skills/review-packet/SKILL.md`는 준수하나, `book-writer/skills/book-workflow/SKILL.md:68`에 한다체(`돌린다`, `넣는다`) 문장이 포함됨 (발견 2) |

---

## 판정 표

- 작업: P5 shared·review-packet (`b9f845e..87eee3f`)
- provider: Antigravity (관점: code)
- 날짜: 2026-11-10
- EXAONE 지연·실패: 해당 없음(`추가 검토: exaone` 없음)

| # | 지적 (심각도) | 판정 | 근거 |
|---|---|---|---|
| 1 | `run_agy.sh:20-23` — 상대 경로가 `cd` 뒤에 저장소 기준으로 풀림 (HIGH) | 채택 | 원본 확인. 검사는 호출 위치 기준, `cat`·리다이렉션은 `cd` 뒤. security 1과 같은 지적 |
| 2 | `book-workflow/SKILL.md:68` — 한다체 문장 (MEDIUM) | 채택 | 원본 확인: "돌린다", "넣는다". security 검토는 이 줄을 놓침 |
| 3 | `exaone_review.py:92-95` — 빈 `data:` 줄에서 `json.loads("")` (LOW) | 채택 | 원본 확인 |
| 4 | `exaone_review.py:74,82` — 인자 타입 힌트 누락 (LOW) | 채택 | `headers`, `resp`에 타입 없음. python-standards 규칙 |
| 5 | `test_run_agy.py` — 상대 경로 테스트 없음 (LOW) | 채택 | 1과 함께 고침 |

- 종합 판정: 경고 — HIGH 1건(security 1과 합침), MEDIUM 1건 수정 후 진행
