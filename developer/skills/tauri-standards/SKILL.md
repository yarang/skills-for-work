---
name: tauri-standards
description: Tauri 2 프레임워크 표준입니다. 웹뷰 프론트엔드(src/)와 Rust 코어(src-tauri/)의 경계, 명령(command) 설계, IPC 입력 검증, 권한(capabilities) 최소화, 상태 관리, 이벤트, CSP, 테스트를 프론트엔드 쪽과 Rust 쪽 절로 나눠 다룹니다. 의존성에 tauri 또는 @tauri-apps/*가 있는 프로젝트에서 사용합니다.
---

# Tauri 2 표준

Tauri 프로젝트는 두 계층이 한 저장소에 있습니다. 작업 행은 디렉터리로 나눕니다.

| 디렉터리 | 계층 스킬 | 이 문서에서 볼 절 |
|---|---|---|
| `src/` (웹뷰) | `frontend-principles` | 「공통」 + 「프론트엔드 쪽」 |
| `src-tauri/` (Rust 코어) | `backend-principles`의 데스크톱 네이티브 예외 | 「공통」 + 「Rust 쪽」 |

## 공통: 신뢰 경계

- **웹뷰는 신뢰하지 않는 쪽입니다.** 웹뷰에서 오는 모든 명령 인자는 브라우저에서 온 HTTP 요청처럼 취급합니다.
- 파일 시스템, 셸, 네트워크 같은 강한 권한은 Rust 쪽에만 둡니다. 웹뷰에 플러그인 권한을 넓게 열어 주기보다, 필요한 일만 하는 좁은 명령을 만듭니다.
- 명령의 인자와 반환 타입을 계약으로 봅니다. 양쪽 타입을 손으로 맞추지 말고, 가능하면 생성 도구(`tauri-specta` 등)로 TypeScript 타입을 만듭니다.

## 프론트엔드 쪽 (`src/`)

- `invoke` 호출은 도메인별 모듈(`src/features/<도메인>/api.ts`)에 모읍니다. 컴포넌트에서 `invoke('...')`를 직접 부르지 않습니다.
- 명령 결과는 zod로 파싱합니다. Rust 쪽 타입이 바뀌면 여기서 바로 드러납니다.
- `invoke`가 던지는 에러는 Rust의 에러 직렬화 형식입니다. 한 곳에서 앱 에러 타입으로 바꿉니다.
- 이벤트 구독(`listen`)은 반환된 해제 함수를 정리 단계(React effect cleanup)에서 반드시 부릅니다.
- 브라우저 전용 API(`window.open`, 직접 `fetch`로 로컬 파일 접근)보다 Tauri 플러그인 API를 씁니다.

## Rust 쪽 (`src-tauri/`)

### 명령

- `#[tauri::command]` 함수는 얇게 둡니다. 입력 검증 → 서비스 호출 → 결과 반환만 합니다. 업무 로직은 Tauri를 모르는 모듈에 둡니다.
- 무거운 작업이나 I/O가 있는 명령은 `async fn`으로 만듭니다. 동기 명령은 메인 스레드를 막을 수 있습니다.
- 반환 타입은 `Result<T, AppError>`이고, `AppError`는 `serde::Serialize`를 구현합니다. 직렬화 내용에 내부 경로나 비밀을 담지 않습니다.
- 경로 인자는 허용된 기준 디렉터리 안으로 정규화되는지 확인합니다(경로 탐색 차단).
- 셸 명령을 만들 때 인자를 문자열로 이어 붙이지 않습니다.

### 상태

- 공유 상태는 `app.manage(state)`로 등록하고 명령에서 `State<'_, T>`로 받습니다.
- 내부 가변성은 `Mutex`/`RwLock`으로 둡니다. async 명령에서 await를 넘어 락이 필요하면 `tokio::sync::Mutex`를 씁니다.

### 이벤트

- 백엔드에서 프론트로 보내는 진행 상황은 이벤트(`emit`) 또는 채널(`tauri::ipc::Channel`)로 보냅니다. 큰 스트림은 채널이 낫습니다.

### 권한과 보안

- `src-tauri/capabilities/*.json`에는 필요한 권한만 넣습니다. `fs:default`처럼 넓은 권한 대신 범위(scope)를 지정합니다.
- 창마다 필요한 권한이 다르면 capability 파일을 나눕니다.
- `tauri.conf.json`의 CSP를 끄지 않습니다(`"csp": null` 금지). 원격 콘텐츠를 웹뷰에 로드하지 않습니다.
- 앱 업데이트를 쓰면 서명 검증을 켭니다.

### 로그와 종료

- 로그는 `tauri-plugin-log` 또는 `tracing`으로 남깁니다. 데스크톱 네이티브 예외에 따라 사용자 데이터 디렉터리의 로그 파일에 둘 수 있습니다.
- 창이 닫힐 때 정리해야 할 자원은 `RunEvent::ExitRequested`/`Exit`에서 정리합니다.

## 테스트

- 업무 로직은 Tauri와 떨어진 Rust 모듈로 두고 `cargo test`로 테스트합니다.
- 명령 자체는 `tauri::test`(`mock_builder`, `mock_context`)로 테스트할 수 있습니다.
- 프론트엔드에서는 `@tauri-apps/api/mocks`의 `mockIPC`로 `invoke`를 가짜로 바꿔 테스트합니다.
