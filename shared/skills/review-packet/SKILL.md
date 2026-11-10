---
name: review-packet
description: 검토 역할과 실행 provider를 나누는 절차 — 검토 꾸러미 형식, provider 능력표(Antigravity·EXAONE), 판정 확인, provider 실행기. 메인 대화가 외부 provider에 검토를 맡길 때 사용합니다.
---

# 검토 꾸러미와 provider

## 1. 언제 쓰는가

메인 대화가 외부 provider(Antigravity, EXAONE)에 검토를 맡길 때 씁니다. 검토 꾸러미를 만들어 보내고, 돌아온 지적을 원본에 대조해 판정합니다.

하위 에이전트는 다른 에이전트·provider를 부를 수 없으므로, 이 스킬은 **메인 대화용**입니다. `work-standards:dev-workflow`의 ⑧-1 외부 검토와 `book-writer:book-workflow`의 ⑤ 초안 검토가 이 스킬을 가리킵니다.

## 2. 원칙

- **역할(기준·범위·관점·독립성·산출물)과 provider(실행 레이어)는 다릅니다.** 리뷰어를 특징짓는 것은 역할이 정합니다. 코드는 `work-standards:reviewer`(관점 code·security), 원고는 `book-writer:editor`가 이미 그 역할입니다. provider 이름으로 역할(에이전트)을 만들지 않습니다. provider마다 역할이 복제되고, 검토의 질을 정하는 기준은 어디에도 정의되지 않기 때문입니다.
- **기준과 범위 없이 검토를 맡기지 않습니다.** 그러면 일반론만 돌아오고, provider 사이에 판정을 비교할 수 없습니다.
- **구현한 provider로 같은 작업을 검토하지 않습니다.** 같은 모델은 같은 착각을 정답으로 봅니다. Z.ai가 구현했으면 Claude·Antigravity·EXAONE으로 검토합니다.

## 3. 검토 꾸러미 만들기

`templates/packet.md`의 각 칸을 채워 꾸러미를 만듭니다. 검토 한 건마다 꾸러미 하나이고, **같은 꾸러미를 어느 provider에든 보냅니다.** 각 칸을 채우는 법:

- **역할**: `work-standards:reviewer`(코드) 또는 `book-writer:editor`(원고).
- **관점**: `code | security | spec(명세 일치) | style(문체·표기)` 중 하나. **꾸러미 하나에 관점 하나**입니다. 한 번에 모든 관점을 보게 하면 얕아집니다.
- **범위**: 기준 커밋과 대상 커밋, 대상 파일 목록(또는 "diff 전체"), 제외할 파일·디렉터리와 이유.
- **기준**: ① 수용 기준(지시서·설계서의 해당 절 **원문**), ② 분야 기준(스킬 이름 목록 — 스킬을 못 읽는 provider에게는 본문을 첨부), ③ 심각도 정의.
- **심각도는 역할의 표 그대로** 싣습니다. 코드는 `work-standards:reviewer`의 CRITICAL/HIGH/MEDIUM/LOW, 원고는 `book-writer:editor`의 blocker/major/minor입니다. 다른 척도를 만들지 않습니다.
- **참고 원본**: 대조할 파일 경로. 저장소를 못 읽는 provider에게는 파일을 첨부합니다.
- **사실 자료**: 메인 대화가 돌린 검증 결과(테스트·validate 출력). 명령을 못 돌리는 provider용입니다.
- **출력 형식**: 역할의 출력 형식 그대로(`work-standards:reviewer`·`book-writer:editor`의 출력 형식 절).
- **규칙·보내지 않는 것**: 틀에 적힌 문구 그대로 둡니다.

## 4. provider 능력표

꾸러미에 무엇을 첨부할지는 provider의 능력으로 정합니다.

| provider | 실행 | 저장소 읽기 | 명령 실행 | 스킬 로드 | 속도·제한 | 비고 |
|---|---|---|---|---|---|---|
| Claude 하위 에이전트 | `Agent` 도구 | 가능 | 가능(역할의 Bash 허용 목록) | 가능 | 빠름 | 기본값 |
| Z.ai (GLM) | `claude-zai -p` | 가능 | 허용 목록 안에서 | `~/.claude`·플러그인 공유 | 보통 | 구현 provider와 같으면 검토에 쓰지 않음(② 원칙) |
| Antigravity | `agy --mode plan --print "<꾸러미>"` | 가능 | 가능 | 불가(파일로 읽음) | 몇 분 | `-p` 바로 뒤에 다른 플래그를 두면 그 플래그를 지시문으로 먹음 |
| EXAONE | 채팅 API 스크립트(`api.exaone.ai/v1`, `k-exaone_v2.5`) | 불가 — 원본 첨부 | 불가 — 사실 자료 첨부 | 불가 — 스킬 본문 첨부 | 느림(추론, 초당 1회 제한). 컨텍스트 524,288 토큰 | 비스트리밍은 긴 응답에서 HTTP 500 → 스트리밍으로 받음. 외부 반출이므로 「보내지 않는 것」을 지킴 |

- 능력에 따라 첨부할 것: **저장소 읽기가 불가하면 원본을, 스킬 로드가 불가하면 스킬 본문을, 명령 실행이 불가하면 사실 자료를** 꾸러미에 함께 넣습니다.
- 능력이 없어서 볼 수 없는 기준은 provider가 "확인 못 함"으로 적고, 메인 대화가 사실 자료(테스트 결과 등)로 메웁니다.

## 5. 기본 절차

1. **검토를 시작할 때 `추가 검토: exaone` 줄을 확인합니다.** 작업 지시서나 설계서의 검토 줄에 있거나 사용자가 요청하면 EXAONE을 켜고, 없으면 부르지 않습니다.
2. 꾸러미를 만들어(③절) **Antigravity로 검토합니다.** 실행기는 ⑧절의 `run_agy.sh`입니다.
3. EXAONE을 켰으면 **같은 꾸러미**를 EXAONE에도 보내 **동시에** 돌립니다. EXAONE은 저장소·명령·스킬을 못 읽으므로(④절), diff·스킬 본문·사실 자료를 첨부합니다. 실행기는 ⑧절의 `exaone_review.py`입니다.
4. **EXAONE이 늦거나 실패하면 Antigravity 판정으로 진행합니다.** 그 사실을 판정 기록(⑥절)에 적습니다.
5. EXAONE 호출은 한 번에 하나씩 합니다. 병렬로 돌리면 초당 1회 제한에 걸립니다.

## 6. 판정 확인

- provider가 돌려준 지적은 **메인 대화가 원본에 대조해** 하나씩 `채택` · `기각(근거)` · `확인 필요`로 판정합니다. 줄 번호가 어긋나거나, 없는 코드를 지적하거나, 지시서가 허용한 것을 위반으로 보는 경우가 있습니다.
- provider 여럿의 지적은 **지적 단위로 합칩니다.** 같은 지적이 겹치면 하나로 묶어 두 provider 모두가 지적했음을 적습니다.
- **종합 판정은 채택된 지적으로 메인 대화가 내립니다.** provider가 판정을 내리지 않습니다.
- 기록: 원문은 `docs/reviews/<작업>-<provider>-<날짜>.md`에 남기고, 그 파일 끝에 `templates/verdict.md` 형식의 판정 표를 덧붙입니다. 원문은 고치지 않습니다.

## 7. 보내지 않는 것 (외부 provider)

외부 API·서비스로 나가는 순간 공개된 것으로 봅니다.

- 비밀값: `.env`, 키·토큰·비밀번호가 든 파일, `llm.env` 자체
- 개인정보, 고객 데이터
- 계약상 외부 반출이 금지된 원고·자료

대상에 위 내용이 섞여 있으면 빼거나 가린 사본을 보냅니다. 판단이 어려우면 **보내기 전에 사람에게 묻습니다.**

## 8. 실행기 사용법

두 스크립트 모두 표준 도구만 씁니다. Antigravity는 `agy` CLI가, EXAONE은 `python3`가 필요하고, 키는 환경 변수 `EXAONE_API_KEY` 또는 `LLM_ENV_FILE`(기본 `~/.config/server-guardian/llm.env`)의 `EXAONE_API_KEY=` 줄에서 읽습니다.

Antigravity(`run_agy.sh` — 저장소로 이동해 꾸러미를 지시문으로 보냅니다):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/run_agy.sh" <저장소> <꾸러미 파일> <결과 파일>
```

- 종료 코드는 agy의 것을 그대로 돌려주고, 결과 파일이 비어 있으면 2로 끝납니다. agy의 stderr은 `<결과 파일>.err`에 남습니다.
- Antigravity가 명령을 실행할 수 있으므로, 호출을 경계 확인으로 감싸는 것은 각 워크플로(`work-standards:dev-workflow` ⑧-1)가 정합니다.

EXAONE(`exaone_review.py` — 꾸러미를 system·user 메시지로 묶어 스트리밍으로 받습니다):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/exaone_review.py" \
  --packet <꾸러미 파일> --out <결과 파일> \
  --diff <저장소> <기준 커밋>        # git diff <기준 커밋>..HEAD 를 함께 보냄
  [파일 ...]                          # 참고 원본·스킬 본문 등 첨부 파일
# --stdin-label <이름>: 표준 입력(diff 등)을 함께 보낼 때
# --effort low|medium|high|max: reasoning_effort (기본 high)
# --max-tokens N: 최대 생성 토큰 (기본 16000)
```

- 첨부 파일과 diff는 **줄 번호를 붙여** 보냅니다. 지적에 `파일:줄`을 달라고 꾸러미의 출력 형식에 적어 둡니다.
- 429는 `Retry-After`를 따르거나 지수 백오프로 최대 5회 재시도합니다. 그 밖의 HTTP 오류는 종료 코드 1로 끝납니다.
- 결과 파일에 검토 본문을 쓰고, stderr에 모델·추론 글자 수·`finish_reason`을 적습니다. `finish_reason`이 `length`면 답이 잘렸다는 경고가 나옵니다 — `--max-tokens`를 늘리거나 `--effort`를 낮춥니다.
