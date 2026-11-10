# P7 Antigravity 검토 (관점 spec, 2026-11-11)

- 꾸러미: 범위 665bf31..dbe0245 (rebase 뒤 main `4232f50`), 기준 docs/briefs/p7-p2-findings.md·docs/reviews/p2-trial-2026-11-10.md
- 실행: shared:review-packet run_agy.sh

## 원문

확인한 스킬: work-standards:code-principles, work-standards:python-standards

## 리뷰 결과 (관점: spec)
- 범위: 24개 파일 (`book-writer/` 9개, `developer/agents/` 4개, `docu-writer/agents/` 5개, `*/plugin.json` 3개, `docs/briefs/p7-report.md` 1개, `docs/briefs/p7-p2-findings.md` 및 `docs/reviews/p2-trial-2026-11-10.md` 대조)
- 판정: 통과

### 발견
발견 없음

---

### 확인 못 함
- **`pytest` 및 `claude plugin validate` 샌드박스 내 동적 직접 실행**: 현재 실행 환경(macOS Sandbox)의 보안 격리 정책으로 인해 `uv` 실행 시 시스템 프레임워크 접근 제한(`SystemConfiguration` NULL object panic)이 발생하고 `claude` CLI가 샌드박스 내에 직접 제공되지 않아, 동적 테스트(`hooks/tests` 60건, `developer` 90건 통과) 및 플러그인 유효성 검증은 메인 대화가 격리 밖에서 직접 실행하여 제공한 사실 자료(Fact Data)를 신뢰 근거로 확인했습니다. 정적 검증(`git diff`, `git grep` 0건 검증, 파일 단위 정밀 검토)은 독립적으로 직접 수행해 완료했습니다.

---

### 수용 기준 1~7 판정 표

| # | 수용 기준 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | `cd book-writer && pytest hooks/tests` 통과 | **통과** | 사실 자료 60 passed 확인. 신규 테스트 4함수(6케이스) 추가 및 RED→GREEN 확인 |
| 2 | `cd developer && pytest hooks/tests ...` 통과 | **통과** | 사실 자료 90 passed 회귀 없음 확인 |
| 3 | `claude plugin validate` 세 플러그인 및 루트 통과 | **통과** | 사실 자료 4개 검증 모두 통과 확인 |
| 4 | 에이전트 내 구 문구 및 보고 줄 `grep` 0줄 | **통과** | `grep -rn "불러온 스킬 이름을 보고서"` 0줄, `grep -rn "^불러온 스킬:"` 0줄 직접 확인 |
| 5 | `screen-capture/SKILL.md` 내 "관례" 문구 제거 | **통과** | `grep -n "관례"` 0줄 직접 확인 (`research/measure-*.md` 단일 경로 통일 완료) |
| 6 | 쓰기 가드 판정 변경 제한(메시지 2종 + `raw/**` 허용만) | **통과** | `write_guard.py` diff 확인 결과 판정 알고리즘 불변, 거부 사유 분기 2종 및 capturer 허용 목록 외 변경 없음 |
| 7 | 본문 합니다체 및 스킬 참조 접두사 유지 | **통과** | 추가된 설명·안내 문장 전수 합니다체(하십시오/합니다/씁니다) 준수, 스킬 호출 접두사 규격 유지 확인 |

---

### 발견 1~9 반영 표

| 발견 | 대상 내용 및 결정 사항 | 반영 여부 | 근거 |
|---|---|---|---|
| 1 | 세션 cwd 원고 루트 안내 및 거부 사유 구체화 | **반영** | `write_guard.py`에 `find_root_with_flag` 신설 및 사유 2종 분기 반영, `design.md`·`README.md`·`book-workflow`에 원고 저장소 세션 실행 조건 명시 |
| 2 | 스킬 확인 문구 모호성 해소 (미리 로드 + `Skill` 호출) | **반영** | 세 플러그인 14개 에이전트에 "컨텍스트에서 확인한 스킬" 반영. 보고 형식이 아닌 문장(developer.md 등) 및 architect/researcher의 미해당 문맥은 원형 보존 |
| 3 | editor Bash 부재에 따른 표기 검사 위임 | **반영** | `book-workflow/SKILL.md` ⑤ 및 `editor.md` 정찰에 메인 세션이 표기 검사 결과를 사실 자료로 넘김 명시 |
| 4 | capturer 실습 폴더 준비 주체 및 계약 범위 조정 | **반영** | `screen-capture/SKILL.md` 및 `capturer.md`에 실습 준비 주체를 메인 세션으로 명시, capturer 임시 변경을 앱 설정·Skill 설치로 한정 |
| 5 | 실측 기록 위치 통일 (`research/measure-*.md`) | **반영** | "저장소 관례" 문구 삭제, 단일 기본 경로로 통일하고 다른 경로는 `.book-writer/paths.json`으로만 제어하도록 명시 |
| 6 | 원고 저장소 밖 실측 시 `--add-dir` 조건 안내 | **반영** | `README.md`, `screen-capture/SKILL.md` 정찰, `capturer.md` 사전 조건에 `--add-dir` 필요성 및 막힐 시 보고 명시 |
| 7 | capturer 실측 원문(텍스트/이미지) 저장 경로 마련 | **반영** | `write_guard.py` 기본 허용에 `research/raw/**` 추가, 캡처 정리에 텍스트 원문(`research/raw/`)과 이미지 원본(`images/raw/`) 분리 명시, capturer 보고 형식 반영 |
| 8 | writer 검증 권한 부재 시 메인 세션 위임 절차 | **반영** | `README.md`에 `permissions.allow` 예시 안내, `book-workflow` 및 `writer.md`에 '확인 못 함' 보고 후 메인 세션 위임 절차 추가 |
| 9 | editor 회차 무관 계획 문서·결정 직접 대조 의무화 | **반영** | `editor.md` 정찰에 "회차와 관계없이 계획 문서 세 개와 DECISIONS.md·manifest 직접 읽기" 명시 |

## 판정 (메인 대화)

| # | 지적 | 판정 | 근거 |
|---|---|---|---|
| — | 발견 없음 | — | 수용 기준 1~7·발견 1~9 반영 표를 원본과 대조해 동의 |
| M1 | (메인 대화) README 「실행 조건」 예시의 `scripts/build.py`는 없는 경로라 독자를 오도할 수 있음(LOW) | 채택 | 자리표시 `<예제 테스트 명령>`·`<빌드 명령>`과 "책의 집필 규칙이 정한 명령으로 바꿈" 문장으로 고침(메인 대화, 문서 한 곳) |

종합: **통과** — CRITICAL·HIGH 0. book-writer 0.1.3, work-standards 0.3.1, docu-writer 0.4.1(원격의 deck-design 0.4.0 위에 rebase)로 main 반영.

참고: 원고 저장소 실측 기록 이동(결정 5)은 원고 저장소 커밋.
