# 작업 지시서 P7: P2 시험 운용 발견 9건 반영

> 근거: `docs/reviews/p2-trial-2026-11-10.md` 「발견 (고칠 것)」 1~9. 방향 결정 2026-11-11(아래 「결정」).
> 맡는 쪽: Z.ai 구현 에이전트. 검토: Antigravity(`shared:review-packet`). 심각도는 코드(쓰기 가드)는 `work-standards:reviewer` 표(CRITICAL/HIGH/MEDIUM/LOW), 스킬·에이전트 문서도 같은 표를 씁니다.
> 추가 검토: 없음

## 결정 (2026-11-11, 사용자)
- 발견 4: **계약을 좁힙니다.** 실습 폴더는 메인 세션이 준비해 작업 지시로 넘깁니다. capturer의 임시 변경은 앱 설정 바꾸기와 Skill 설치로 한정합니다. 쓰기 가드 권한은 넓히지 않습니다.
- 발견 5: **실측 기록은 `research/measure-*.md` 하나로 통일**합니다. "저장소 관례가 있으면 따른다"는 문구를 없애고, 다른 위치는 `.book-writer/paths.json`으로만 바꿉니다. (원고 저장소의 기존 파일 이동은 메인 세션이 따로 합니다. 이 작업 범위 밖.)
- 발견 7: capturer 기본 허용 목록에 **`research/raw/**`**를 더합니다(실측 응답 원문 텍스트).
- 발견 2: 문구 변경은 **세 플러그인 모두**(book-writer 5, work-standards 6, docu-writer 5 에이전트)에 적용합니다.

## 읽을 것 (읽기만 함)
| 무엇 | 위치 |
|---|---|
| 발견 원문 | `docs/reviews/p2-trial-2026-11-10.md` |
| 쓰기 가드 | `book-writer/hooks/write_guard.py`, `book-writer/hooks/tests/test_write_guard.py` |
| 쓰기 보호 계약 | `book-writer/docs/design.md` 「쓰기 보호」 |
| 절차 | `book-writer/skills/book-workflow/SKILL.md` (⑤·「검증의 두 단계」) |
| 실측 기준 | `book-writer/skills/screen-capture/SKILL.md` (정찰 항목, 4, 5) |
| 에이전트 | `book-writer/agents/*.md`, `developer/agents/*.md`, `docu-writer/agents/*.md` |

## 고칠 것

### A. 쓰기 가드 (`book-writer/hooks/write_guard.py`) — 발견 1, 7
1. **테스트를 먼저** `book-writer/hooks/tests/test_write_guard.py`에 더하고 실패를 확인한 뒤 구현합니다.
2. `find_root`가 `manifest.md`를 찾았는지도 알 수 있게 합니다(예: `(root, found)`를 돌려주는 함수를 새로 두고 `find_root`는 기존 동작 유지, 또는 호출부만 바꿈). 판정 결과(허용·거부 경로)는 바꾸지 않습니다.
3. **거부 메시지**(원고 루트 밖 경로일 때만):
   - `manifest.md`를 못 찾았을 때: `세션 작업 디렉터리(<cwd>)와 그 위에서 manifest.md를 찾지 못해 <cwd>를 원고 루트로 봤습니다 — book-writer 에이전트는 원고 저장소에서 연 세션에서 부르십시오`
   - 찾았을 때: `원고 루트(<root>, 세션 작업 디렉터리 기준) 밖 경로입니다 — 다른 원고 저장소에 쓰려면 그 저장소에서 세션을 여십시오`
   - 문구는 위 뜻을 지키면 다듬어도 됩니다. 메시지 앞머리 `[book-writer:<역할>] <경로> 쓰기를 막습니다:`는 그대로 둡니다.
4. `DEFAULT_ALLOWLIST["capturer"]`에 `"research/raw/**"`를 더합니다.
5. 더할 테스트:
   - manifest.md가 없는 cwd에서 writer가 그 cwd 밖에 쓰면 거부, 사유에 `manifest.md를 찾지 못해`와 cwd 경로가 들어감
   - manifest.md가 있는 루트에서 루트 밖 경로를 쓰면 거부, 사유에 루트 경로와 `세션 작업 디렉터리 기준`이 들어감
   - capturer `research/raw/x.txt`·`research/raw/sub/y.json` 허용, capturer `research/notes.md` 거부(기존 동작 유지), writer `research/raw/x.txt` 거부
   - 기존 테스트 26개는 그대로 통과

### B. 문서 — 발견 1, 6, 7
| 파일 | 할 일 |
|---|---|
| `book-writer/docs/design.md` 「쓰기 보호」 | ① "원고 루트 R: 서브에이전트의 cwd" → "**세션**의 작업 디렉터리(hook 입력의 `cwd`)". 다른 저장소에서 연 세션이 부르면 모든 원고 쓰기가 막힌다는 점과 거부 메시지 두 종류를 적음 ② capturer 허용 표에 `research/raw/**` |
| `book-writer/README.md` | ① 「설치」 아래에 「실행 조건」 절: (가) book-writer 에이전트는 원고 저장소(manifest.md가 있는 곳)에서 연 세션에서 부름 (나) 원고 저장소 밖 실습 폴더를 capturer가 실측하려면 세션을 `--add-dir <실습 폴더>`로 띄움 (다) writer의 검증 명령(빌드·예제 테스트·쪽수 확인)이 세션 허용 목록에 없으면 writer는 '확인 못 함'으로 넘기고 메인 세션이 돌림 — 원고 저장소 `.claude/settings.json`의 `permissions.allow`에 검증 명령을 두면 writer가 직접 돌릴 수 있음(예시 한 블록) ② 에이전트 표 capturer 「쓰는 곳」에 `research/raw/` |

### C. 절차 스킬 `book-writer/skills/book-workflow/SKILL.md` — 발견 1, 3, 8
1. 0절 표 아래 목록 첫 줄에: "book-writer 에이전트는 **원고 저장소에서 연 세션**에서 부릅니다. 쓰기 가드가 세션 작업 디렉터리에서 원고 루트를 찾기 때문입니다(`docs/design.md` 「쓰기 보호」)."
2. ⑤ 첫 항목 앞에: "메인 세션이 표기 검사(책의 집필 규칙이 정한 명령)를 돌려 결과를 editor 작업 지시에 사실 자료로 넣습니다. editor에는 Bash가 없습니다."
3. 「검증의 두 단계」 변경 범위 검증 끝에: "writer가 세션 권한이나 도구가 없어 돌리지 못한 검증은 보고서 '확인 못 함'에 명령과 이유를 적고, 메인 세션이 대신 돌려 결과를 반영 기록에 남깁니다."

### D. 실측 스킬 `book-writer/skills/screen-capture/SKILL.md` — 발견 4, 5, 6, 7
1. 정찰 항목에 **실행 조건** 한 줄: 실습 폴더가 원고 저장소 밖이면 세션이 `--add-dir <폴더>`로 열려 있어야 합니다. 열려 있지 않아 접근이 막히면 우회하지 않고 멈춰 `물어볼 것`에 적습니다.
2. 「준비 상태」: 실습 폴더·파일은 **메인 세션이 준비해** 작업 지시로 넘깁니다. capturer는 실습 파일을 만들지 않습니다.
3. 「2. 안전 규칙」의 임시 변경 문장을 "촬영 준비를 위해 임시로 바꾼 앱 설정과 설치한 Skill"로 좁힘(파일 제외).
4. 「4. 캡처 정리」 원본 위치: 원본 이미지는 그림 폴더 아래 `raw/`(예: `manuscript/…/images/raw/`), 실측 응답 원문(텍스트)은 `research/raw/measure-<대상>-<YYYY-MM-DD>-<번호>.txt`.
5. 「5. 실측 기록」: 위치는 `research/measure-<대상>-<YYYY-MM-DD>.md` **하나**입니다. "저장소 관례가 있으면 따릅니다"·"다른 위치를 쓰면 그 관례를 따릅니다"를 지우고 "다른 위치가 필요하면 `.book-writer/paths.json`의 capturer 목록으로 바꿉니다"로 바꿈. 기록 틀에 `## 원문` 칸(원문 파일 경로 목록) 추가.

### E. 에이전트 — 발견 2, 4, 9
1. **세 플러그인 16개 에이전트**(`book-writer/agents/*.md` 5, `developer/agents/*.md` 6, `docu-writer/agents/*.md` 5)의 "불러온 스킬 이름을 보고서 첫 줄에 적습니다"를 "**컨텍스트에서 확인한 스킬**(frontmatter `skills:`로 미리 로드된 것과 `Skill`로 부른 것 모두) 이름을 보고서 첫 줄에 적습니다"로 바꿉니다. 보고 형식의 `불러온 스킬:` 줄과 `<불러온 스킬 목록…>` 자리표시도 `확인한 스킬:`, `<확인한 스킬 목록…>`으로 맞춥니다. `developer.md`의 "어떤 언어를 쓰는 개발자인지는 **불러온 스킬**이 정합니다"처럼 보고 형식이 아닌 문장은 그대로 둡니다. 이 문구가 없는 에이전트(예: docu-writer researcher의 본문)는 보고 형식 줄만 맞춥니다.
2. `book-writer/agents/capturer.md` 행동 계약 불변 조건: "임시 변경(설정 바꾸기, Skill 설치, 실습 파일 만들기)" → "임시 변경(앱 설정 바꾸기, Skill 설치). 실습 폴더·파일은 메인 세션이 준비해 작업 지시로 넘기며, capturer는 만들지 않습니다". 사전 조건에 "실습이 원고 저장소 밖 폴더를 쓰면 그 경로와, 세션이 그 폴더에 접근할 수 있는지(`--add-dir`)"를 더함. 보고 형식 `## 실측 기록` 아래에 `원문: <research/raw/... 경로 또는 없음>` 한 줄.
3. `book-writer/agents/editor.md` 「1. 정찰」: "계획 문서 세 개의 결정 사항" → "**회차와 관계없이** 계획 문서 세 개(story·content·outline)와 `DECISIONS.md`·manifest의 해당 장 줄을 직접 읽고 결정 사항을". 이어서 "표기 검사 결과는 메인 세션이 작업 지시에 넣어 준 것을 씁니다. 없으면 '표기 검사 결과 없음'을 판정에 적습니다(editor는 검사를 돌리지 않습니다)."
4. `book-writer/agents/writer.md`: 검증을 다루는 곳(진행 순서의 검증 단계)에 "세션 권한·도구가 없어 돌리지 못한 검증은 우회하지 말고 보고서 '확인 못 함'에 명령과 이유를 적습니다" 한 줄. writer 보고 형식에 '확인 못 함' 칸이 없으면 더합니다.

### F. 버전
| 파일 | 버전 |
|---|---|
| `book-writer/.claude-plugin/plugin.json` | `0.1.3` |
| `developer/.claude-plugin/plugin.json` | `0.3.1` |
| `docu-writer/.claude-plugin/plugin.json` | `0.3.1` |

## 수용 기준
1. `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q` 모두 통과(기존 26 + 새 테스트).
2. `cd developer && uv run --with pytest pytest -q hooks/tests skills/verify/tests` 모두 통과(바뀐 코드는 없지만 회귀 확인).
3. `claude plugin validate book-writer`, `claude plugin validate developer`, `claude plugin validate docu-writer`, `claude plugin validate .` 통과.
4. `grep -rn "불러온 스킬 이름을 보고서" book-writer/agents developer/agents docu-writer/agents` 결과 0줄, `grep -rn "^불러온 스킬:" ...` 결과 0줄.
5. `grep -n "관례" book-writer/skills/screen-capture/SKILL.md`에 실측 기록 위치를 저장소 관례에 맡기는 문장이 없음.
6. 쓰기 가드의 기존 허용·거부 판정은 그대로이고, 바뀐 것은 거부 메시지(루트 밖일 때)와 capturer `research/raw/**` 허용뿐입니다(diff로 확인).
7. 스킬·에이전트 본문은 합니다체, 스킬 참조는 접두사가 붙어 있음.

## 바꾸지 않을 것
- `shared/`, `docs/plans/`, `docs/reviews/`, `docs/briefs/`(보고서 파일만 새로 씀)
- 다른 역할의 허용 경로, `.book-writer/` 보호, 승인 문서 보호
- 에이전트의 `tools`·`model`·`skills` frontmatter
- `~/.claude/`, 다른 저장소(원고 저장소 포함)

## 보고서 형식 (`docs/briefs/p7-report.md`)
1. 만든·바꾼 파일 목록 (발견 번호별)
2. 쓰기 가드에 더한 테스트 목록과 처음 실패 확인 결과
3. 실행한 검증 명령과 결과(통과·실패 개수)
4. 지시서와 다르게 한 것과 이유
5. 물어볼 것
