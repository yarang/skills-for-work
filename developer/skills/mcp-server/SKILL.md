---
name: mcp-server
description: MCP(Model Context Protocol) 서버 표준입니다. 전송 방식(stdio, Streamable HTTP)별 규칙, 도구 설계와 입력 스키마, 도구 에러 보고, 비밀 처리, 그리고 Python(mcp·FastMCP)·TypeScript(@modelcontextprotocol/sdk)·Rust(rmcp) SDK별 관용구를 다룹니다. 의존성에 MCP SDK가 있는 디렉터리에서 코드를 쓰거나 리뷰할 때 사용합니다.
---

# MCP 서버 표준

## 전송 방식

| 전송 | stdout | 로그 | 수명 |
|---|---|---|---|
| **stdio** | **프로토콜 전용.** JSON-RPC 메시지 외에는 한 바이트도 쓰지 않습니다 | stderr로만 | 클라이언트가 stdin을 닫으면 종료 |
| **Streamable HTTP** | 제약 없음 | `backend-principles`를 따름 | 일반 HTTP 서비스와 같음 |

- **stdio 서버에서 `print`, `console.log`, `println!`은 프로토콜을 깨뜨립니다.** 의존 라이브러리가 stdout에 쓰는지도 확인합니다.
- 로그 설정은 진입점에서 stderr로 명시합니다(Python `logging.basicConfig(stream=sys.stderr)`, Node `console.error`, Rust `tracing_subscriber`의 `.with_writer(std::io::stderr)`).
- HTTP 전송은 `Origin` 헤더를 검증하고, 로컬 전용이면 `127.0.0.1`에만 바인딩합니다. 인증이 필요하면 MCP 인가 명세(OAuth)를 따릅니다.

## 도구 설계

- 도구 하나는 한 가지 일을 합니다. 이름은 `동사_명사`(`search_issues`, `create_draft`)로 짓습니다.
- `description`은 **모델이 읽는 문서**입니다. 언제 쓰는지, 무엇을 돌려주는지, 부작용이 있는지 적습니다.
- 입력 스키마는 엄격하게 둡니다: 필수 필드 명시, 열거형, 길이·범위 제한, 각 필드의 설명.
- 결과는 모델이 읽기 좋은 크기로 돌려줍니다. 큰 목록은 페이지를 나누고 다음 커서를 함께 줍니다.
- 읽기 전용 도구와 쓰기 도구를 나누고, 지원되는 SDK에서는 도구 어노테이션(`readOnlyHint`, `destructiveHint`)을 붙입니다.

## 에러

두 종류를 구분합니다.

| 종류 | 예 | 보고 방법 |
|---|---|---|
| **도구 실행 실패** | 대상 없음, 외부 API 오류, 입력 값이 업무 규칙에 어긋남 | 도구 결과에 `isError: true`와 사람이 읽을 메시지. 모델이 보고 다시 시도할 수 있어야 합니다 |
| **프로토콜 오류** | 없는 도구 이름, 스키마에 안 맞는 인자 | JSON-RPC 에러. 보통 SDK가 처리합니다 |

- 예외를 삼키고 빈 결과를 돌려주지 않습니다. 모델은 "없음"과 "실패"를 구분하지 못하게 됩니다.
- 에러 메시지에 비밀값, 내부 경로, 스택 트레이스를 담지 않습니다.

## 비밀

- API 키는 환경변수로 받습니다. 도구 인자로 받지 않습니다(모델 대화 기록에 남습니다).
- 도구 결과에 토큰이나 키를 담지 않습니다.

## SDK별 관용구

### Python — `mcp` / FastMCP

- `@mcp.tool()` 데코레이터로 등록합니다. 타입 힌트와 docstring이 입력 스키마와 설명이 됩니다. 모든 인자에 타입을 적고, 제약은 `Annotated[str, Field(max_length=200)]`로 둡니다.
- 도구 실행 실패는 `ToolError`(FastMCP는 `fastmcp.exceptions.ToolError`)를 던져 `isError` 결과로 보냅니다. 그 외 예외는 메시지가 가려질 수 있으니, 모델에게 알려야 할 실패는 `ToolError`로 바꿉니다.
- 진행 보고와 로그는 `Context`(`ctx.info`, `ctx.report_progress`)로 클라이언트에 보냅니다.
- 공유 자원은 `lifespan`으로 만들고 닫습니다.

### TypeScript — `@modelcontextprotocol/sdk`

- `McpServer`의 `registerTool`(또는 `tool`)로 등록하고, 입력 스키마는 zod로 정의합니다.
- 실패는 `{ content: [{ type: 'text', text: '...' }], isError: true }`를 돌려줍니다. 핸들러 밖으로 예외를 흘리지 않습니다.
- stdio는 `StdioServerTransport`, HTTP는 `StreamableHTTPServerTransport`를 씁니다.

### Rust — `rmcp`

- `#[tool_router]` / `#[tool]` 매크로로 도구를 등록하고, 인자 구조체에 `schemars::JsonSchema`를 파생시켜 스키마를 만듭니다.
- 실패는 `CallToolResult::error(...)`로 돌려줍니다. `unwrap()`으로 서버 태스크를 죽이지 않습니다.
- stdio는 `rmcp::transport::stdio()`를 쓰고, `tracing` 출력은 stderr로 보냅니다.

## 테스트

- 도구 로직은 MCP와 떨어진 순수 함수·서비스로 두고 단위 테스트합니다.
- SDK가 제공하는 인메모리 클라이언트(Python `Client(mcp)`, TS `InMemoryTransport`)로 도구 목록, 입력 검증, `isError` 결과를 통합 테스트합니다.
- stdio 서버는 실행해서 stdout에 프로토콜 외 출력이 없는지 확인하는 테스트를 하나 둡니다.
