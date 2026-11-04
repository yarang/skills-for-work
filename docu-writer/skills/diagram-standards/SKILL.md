---
name: diagram-standards
description: 문서에 넣는 도표·다이어그램의 표준입니다. mermaid를 우선으로 쓰고, 이미지는 SVG를 우선하며, 도표마다 원본(.mmd)과 SVG를 개별 파일로 둡니다. 도표 종류 고르기, 한글 줄바꿈, 프로파일 design.diagram 토큰에 맞춘 색·글꼴, mermaid-cli 렌더 명령을 정합니다. 문서에 흐름·구조·관계 그림을 넣을 때 사용합니다.
---

# 도표 표준

이 스킬은 **도표를 만들고 문서에 넣는 법만** 담습니다. 도표를 쓸지 말지는 `info-design`이, 도표 색·글꼴 값은 프로파일 `design.diagram`이 정합니다.

## 원칙

- **mermaid를 먼저 씁니다.** mermaid로 표현할 수 없을 때만 SVG를 직접 그립니다.
- **이미지는 SVG를 우선합니다.** PNG는 SVG를 넣을 수 없는 형식(HWPX 등)이나 미리보기에만 씁니다.
- **도표 하나에 파일 하나.** 원본 `<이름>.mmd`와 결과 `<이름>.svg`를 같은 디렉터리에 나란히 둡니다. 문서 안에 mermaid 코드만 박아 두지 않습니다.
- 파일 이름은 내용을 말하는 kebab-case입니다(`approval-flow.mmd`, `diagram1.mmd` 아님).
- `.mmd` 첫 줄에 `%%` 주석으로 도표가 말하는 것을 한 문장으로 적습니다.

## 도표 종류

| 보여 줄 것 | mermaid |
|---|---|
| 절차·결재 흐름, 분기 | `flowchart TD` (단계가 많으면 `LR`) |
| 주체 사이 주고받기 | `sequenceDiagram` |
| 일정·단계 기간 | `gantt` |
| 상태 바뀜 | `stateDiagram-v2` |
| 조직·구성 위계 | `flowchart TD` + `subgraph` |
| 데이터 구조 | `erDiagram`, `classDiagram` |
| 비율 | `pie` — 항목 5개 이하일 때만, 그 밖은 표 |

## 읽히게 만들기

- 노드는 12개 이하로 둡니다. 넘으면 `subgraph`로 묶거나 도표를 나눕니다.
- **한글 줄바꿈은 `<br/>`로 직접 넣습니다.** 자동 줄바꿈은 낱말 중간에서 끊습니다. 한 줄은 10자 안팎으로 둡니다.
- 노드 이름에 괄호·따옴표가 있으면 `["…"]`로 감쌉니다.
- 같은 꼬리표를 여러 화살표에 반복하지 않습니다. `subgraph`로 묶고 화살표 하나에 적습니다.
- 화살표 꼬리표는 동사구로 짧게 씁니다(`승인`, `반려 시 되돌림`).

## 색·글꼴 (프로파일 `design.diagram`)

견본 모드에서는 프로파일 팔레트만 씁니다. 첫 줄에 init 지시문을 둡니다.

```
%%{init: {"theme": "base", "themeVariables": {
  "primaryColor": "<palette[0]의 옅은 색>", "primaryBorderColor": "<palette[0]>",
  "lineColor": "<palette[1]>", "fontFamily": "<design.diagram.font>"}}}%%
```

- 색은 팔레트 두세 가지 안에서 씁니다. 강조할 노드 하나에만 `color.accent`를 씁니다.
- 프로파일에 `design.diagram`이 없으면 mermaid `neutral` 테마를 씁니다.
- 대비 기준은 `visual-design`을 따릅니다.

## 렌더

```bash
npx -y @mermaid-js/mermaid-cli -i <이름>.mmd -o <이름>.svg
npx -y @mermaid-js/mermaid-cli -i <이름>.mmd -o <이름>.png -s 2   # 미리보기·HWPX용
```

- 폭 옵션 `-w`는 없습니다. 해상도는 `-s`(배율)로 정합니다.
- 렌더한 뒤 PNG를 직접 열어 낱말이 끊기거나 꼬리표가 겹치지 않는지 봅니다.

## 형식별 넣기

| 형식 | 넣는 것 |
|---|---|
| Markdown | `![설명](diagrams/<이름>.svg)` |
| DOCX·PPTX | SVG를 그림으로 삽입. 지원하지 않는 뷰어를 위해 PNG(-s 2)를 대체 이미지로 |
| HWPX | PNG(-s 2). 견본의 그림 자리가 있으면 그 자리 크기에 맞춤 |

도표 안 글도 문서 본문처럼 근거가 있어야 합니다(`writing-principles` 불변 규칙 1).
