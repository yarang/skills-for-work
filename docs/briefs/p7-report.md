# P7 보고서 — P2 발견 9건 반영

- 작업: `docs/briefs/p7-p2-findings.md` (근거: `docs/reviews/p2-trial-2026-11-10.md` 발견 1~9)
- 버전: book-writer 0.1.2 → 0.1.3, work-standards(developer) 0.3.0 → 0.3.1, docu-writer 0.3.0 → 0.3.1

## 1. 만든·바꾼 파일 목록 (발견 번호별)

| 발견 | 파일 | 바꾼 것 |
|---|---|---|
| 1 (세션·루트 안내) | `book-writer/hooks/write_guard.py` | `find_root_with_flag` 신설(루트, manifest.md 발견 여부), `find_root`는 기존 동작 유지(래퍼). 루트 밖 거부 사유를 두 종류로 나눔(찾았을 때 / 못 찾았을 때 — 지시서 문구) |
| 1 | `book-writer/docs/design.md` 「쓰기 보호」 | 원고 루트 R 정의를 "세션의 작업 디렉터리(hook 입력의 `cwd`)"로 고침. 다른 저장소 세션에서 부르면 모든 원고 쓰기가 막힌다는 점과 거부 메시지 두 종류를 적음 |
| 1 | `book-writer/README.md` | 「설치」 아래 「실행 조건」 절 신설(원고 저장소 세션, `--add-dir`, 검증 명령 허용 + settings.json 예시 블록) |
| 1, 3 | `book-writer/skills/book-workflow/SKILL.md` | 0절 목록 첫 줄에 "원고 저장소에서 연 세션에서 부릅니다"(발견 1). ⑤ 첫 항목 앞에 "메인 세션이 표기 검사를 돌려 사실 자료로 넘김"(발견 3) |
| 2 | 에이전트 14개: `book-writer/agents/{planner,writer,editor,researcher,capturer}.md`, `developer/agents/{developer,tester,reviewer,documenter}.md`, `docu-writer/agents/{analyst,planner,researcher,reviewer,writer}.md` | "불러온 스킬 이름을 보고서 첫 줄에 적습니다" → "**컨텍스트에서 확인한 스킬**(frontmatter `skills:`로 미리 로드된 것과 `Skill`로 부른 것 모두) 이름을 보고서 첫 줄에 적습니다". 보고 형식 `불러온 스킬:` 줄 9개와 book-writer 자리표시 5개를 `확인한 스킬:`·`<확인한 스킬 목록…>`으로 맞춤 |
| 4 (실습 폴더는 메인 세션 준비) | `book-writer/agents/capturer.md` | 불변 조건: 임시 변경을 "앱 설정 바꾸기, Skill 설치"로 좁히고 "실습 폴더·파일은 메인 세션이 준비해 작업 지시로 넘기며, capturer는 만들지 않습니다" 추가. 사전 조건에 실습 폴더 경로·`--add-dir` 접근 여부 추가. 사후 조건·불변 조건에서 "파일" 되돌림 표현 정리 |
| 4 | `book-writer/skills/screen-capture/SKILL.md` 정찰 「준비 상태」 | "실습 폴더·파일은 **메인 세션이 준비해** 작업 지시로 넘깁니다(capturer는 실습 파일을 만들지 않습니다)" |
| 5 (실측 기록 위치 통일) | `book-writer/skills/screen-capture/SKILL.md` 「5. 실측 기록」 | "저장소 관례" 문구 삭제, 위치를 `research/measure-<대상>-<YYYY-MM-DD>.md` 하나로 통일, "다른 위치가 필요하면 `.book-writer/paths.json`의 capturer 목록으로 바꿉니다" |
| 6 (`--add-dir`) | `book-writer/README.md`, `book-writer/skills/screen-capture/SKILL.md` 정찰 「실행 조건」 줄 | 세션이 `--add-dir <폴더>`로 열려 있어야 함, 막히면 우회하지 않고 `물어볼 것`에 적음 |
| 7 (`research/raw/**`) | `book-writer/hooks/write_guard.py` | `DEFAULT_ALLOWLIST["capturer"]`에 `"research/raw/**"` 추가 |
| 7 | `book-writer/docs/design.md`, `book-writer/README.md` | capturer 허용 표에 `research/raw/**`(실측 응답 원문) 추가 |
| 7 | `book-writer/skills/screen-capture/SKILL.md` 「4. 캡처 정리」·기록 틀 | 원본 위치를 이미지 `raw/`와 텍스트 `research/raw/measure-<대상>-<YYYY-MM-DD>-<번호>.txt`로 명시. 기록 틀에 `## 원문` 칸 추가 |
| 7 | `book-writer/agents/capturer.md` 보고 형식 | `## 실측 기록` 아래 `원문: <research/raw/… 경로 또는 없음>` 한 줄 |
| 8 (writer 검증 위임) | `book-writer/skills/book-workflow/SKILL.md` 「검증의 두 단계」 | 변경 범위 검증 끝에 "돌리지 못한 검증은 보고서 '확인 못 함'에 명령과 이유를 적고, 메인 세션이 대신 돌려 결과를 반영 기록에 남깁니다" |
| 8 | `book-writer/agents/writer.md` | 검증 단계 완료 기준에 "세션 권한·도구가 없어 돌리지 못한 검증은 우회하지 말고 보고서 '확인 못 함'에 명령과 이유를 적습니다". 보고 형식에 `## 확인 못 함` 칸 추가 |
| 9 (editor 직접 읽기) | `book-writer/agents/editor.md` 「1. 정찰」 | "**회차와 관계없이** 계획 문서 세 개(story·content·outline)와 `DECISIONS.md`·manifest의 해당 장 줄을 직접 읽고" + 표기 검사 결과는 메인 세션이 넣어 준 것을 씀, 없으면 '표기 검사 결과 없음' |
| — | plugin.json 3개 | book-writer 0.1.3, developer(work-standards) 0.3.1, docu-writer 0.3.1 |

새로 만든 파일: 이 보고서뿐입니다.

## 2. 쓰기 가드에 더한 테스트와 처음 실패 확인

`book-writer/hooks/tests/test_write_guard.py`에 더한 테스트 4개(케이스 6건):

| 테스트 | 확인 것 |
|---|---|
| `test_outside_root_reason_without_manifest_mentions_cwd` | manifest.md 없는 cwd 밖 쓰기 거부 사유에 `manifest.md를 찾지 못해`와 cwd(realpath) 경로 |
| `test_outside_root_reason_with_manifest_mentions_root` | manifest.md 있는 루트 밖 쓰기 거부 사유에 루트 경로와 `세션 작업 디렉터리 기준` |
| `test_capturer_raw_research_allowed` (2케이스) | capturer `research/raw/x.txt`, `research/raw/sub/y.json` 허용 |
| `test_capturer_research_notes_denied` | capturer `research/notes.md` 거부(기존 동작 유지) |
| `test_writer_research_raw_denied` | writer `research/raw/x.txt` 거부 |

처음 실패 확인(구현 전 실행): **4 failed, 56 passed** — 새 동작을 요구하는 4케이스(사유 문구 2, raw 허용 2)가 올바른 이유로 실패(거부 사유에 문구 없음, `research/raw/**` 미허용). 기존 동작을 확인하는 2케이스(`research/notes.md` 거부, writer raw 거부)는 이미 통과했습니다. 구현 뒤 **60 passed**.

## 3. 실행한 검증 명령과 결과

| 명령 | 결과 |
|---|---|
| `cd book-writer && uv run --python 3.13 --with pytest pytest hooks/tests -q` | **60 passed**, 0 failed (기존 26개 함수 54케이스 + 새 6케이스) |
| `cd developer && uv run --with pytest pytest -q hooks/tests skills/verify/tests` | **90 passed**, 0 failed |
| `claude plugin validate book-writer` | 통과 (icon ICON_MISSING 경고 1건 — 기존부터 있던 것, 판정 영향 없음) |
| `claude plugin validate developer` | 통과 (같은 경고, README 설치 줄 조언 — 기존 것) |
| `claude plugin validate docu-writer` | 통과 (같은 경로의 조언 — 기존 것) |
| `claude plugin validate .` (마켓플레이스) | 통과 |
| `grep -rn "불러온 스킬 이름을 보고서" book-writer/agents developer/agents docu-writer/agents` | **0줄** |
| `grep -rn "^불러온 스킬:" book-writer/agents developer/agents docu-writer/agents` | **0줄** |
| `grep -n "관례" book-writer/skills/screen-capture/SKILL.md` | **0줄** |
| 쓰기 가드 diff 확인 | 판정 로직(relpath·pardir·glob)은 그대로, 바뀐 것은 루트 밖 거부 메시지 두 종류와 capturer `research/raw/**` 추가뿐 |
| 스킬·에이전트 본문 검토 | 새 문장 모두 합니다체, 새로 넣은 참조는 문서 경로(`docs/design.md`)뿐(스킬 접두사 해당 없음), 기존 스킬 참조 접두사 유지 |

## 4. 지시서와 다르게 한 것과 이유

1. **에이전트 문구 변경은 14개 파일**입니다. 지시서는 "세 플러그인 16개 에이전트"라고 했지만, `developer/agents/architect.md`(설계서 형식의 `불러올 스킬:` 목록만 있음)와 `developer/agents/researcher.md`(출력 형식에 스킬 첫 줄 없음)은 "불러온 스킬 이름을 보고서…" 문구도, 보고 형식 `불러온 스킬:` 줄도 없어 바꿀 것이 없었습니다. 지시서 자체가 "이 문구가 없는 에이전트는 보고 형식 줄만 맞춥니다"라고 한 것에 따랐습니다. architect의 `불러올 스킬:`(설계서 칸 이름)과 developer.md·reviewer.md의 보고 형식이 아닌 "불러온 스킬" 문장(지시서가 예시로 남기라고 한 것)은 그대로 두었습니다.
2. **screen-capture 기록 틀 「되돌린 것」 자리표시**를 `<지운 Skill·설정·파일>` → `<지운 Skill·설정>`으로 맞췄습니다(지시서에 명시 없음). 임시 변경에서 파일이 빠졌으므로 틀에 남길 필요가 없어졌기 때문입니다.
3. **writer 보고 형식의 `## 확인 못 함` 칸 위치**를 「변경 범위 검증 결과」와 「반영 기록」 사이에 넣었습니다(지시서는 위치를 정하지 않음). 돌리지 못한 검증은 검증 결과의 일부이므로 바로 뒤가 자연스럽습니다.

## 5. 물어볼 것

없음.
