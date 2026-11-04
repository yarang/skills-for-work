---
name: axum-standards
description: axum 프레임워크 표준입니다. Router 구성, State 공유, 추출기(extractor) 순서, IntoResponse 에러 변환, tower 미들웨어(타임아웃·추적·본문 크기 제한), graceful shutdown, oneshot 기반 테스트를 다룹니다. Rust 의존성에 axum이 있는 디렉터리에서 코드를 쓰거나 리뷰할 때 사용합니다.
---

# axum 표준

`backend-principles`와 `rust-standards`를 axum으로 구현하는 방법입니다.

## 구조

```
src/
  main.rs              # 설정 읽기, 추적 초기화, serve + shutdown
  lib.rs               # pub fn app(state: AppState) -> Router
  state.rs             # AppState
  error.rs             # AppError + IntoResponse
  features/<도메인>/
    mod.rs             # pub fn router() -> Router<AppState>
    handlers.rs        # 얇은 핸들러
    service.rs         # 업무 로직 (axum을 모름)
    dto.rs             # 요청·응답 serde 타입
```

- 라우터는 `lib.rs`의 `app()` 함수로 만듭니다. 테스트가 같은 라우터를 씁니다.
- 도메인마다 `router()`를 두고 `Router::new().nest("/users", users::router())`로 합칩니다.

## State

- 공유 자원(DB 풀, HTTP 클라이언트, 설정)은 `#[derive(Clone)] struct AppState`에 담고 `.with_state(state)`로 넘깁니다.
- 큰 자원이나 복제할 수 없는 자원은 `Arc`로 감쌉니다. 풀 타입(`PgPool`)은 이미 내부가 `Arc`라 그대로 둡니다.
- 핸들러가 State 전체가 필요 없으면 `FromRef`로 하위 State만 추출합니다.
- 전역 `static`이나 `lazy_static`에 자원을 두지 않습니다.

## 핸들러와 추출기

- 본문을 소비하는 추출기(`Json`, `Form`, `Bytes`)는 **마지막 인자**에 둡니다.
- 핸들러는 입력을 추출해 서비스를 부르고 결과를 돌려주기만 합니다.
- 추출 실패 응답 형식을 통일하려면 커스텀 추출기나 `WithRejection`으로 거부(rejection)를 `AppError`로 바꿉니다.
- 컴파일 에러가 알아보기 어려우면 개발 중에 `#[debug_handler]`를 붙입니다.

## 에러

- `AppError` 열거형 하나에 `IntoResponse`를 구현하고, 핸들러는 `Result<T, AppError>`를 돌려줍니다.
- 서비스의 도메인 에러를 `From`으로 `AppError`에 연결해 `?`로 전파합니다.
- 상태 코드 결정과 응답 본문 생성은 `into_response` **한 곳에서만** 합니다. 내부 에러는 로그로 남기고 응답에는 일반 메시지만 담습니다.

## 미들웨어 (tower)

- `tower_http`로 기본 계층을 둡니다: `TraceLayer`(요청 추적), `TimeoutLayer`(요청 상한), `RequestBodyLimitLayer`(본문 크기), `CorsLayer`(필요할 때).
- 계층은 `ServiceBuilder`로 묶습니다. 적용 순서가 바뀌면 동작이 바뀌므로 순서를 주석으로 남깁니다.
- 인증은 `middleware::from_fn_with_state` 또는 커스텀 추출기로 구현합니다.

## 수명주기

- `axum::serve(listener, app).with_graceful_shutdown(shutdown_signal())`로 종료 신호(SIGINT, SIGTERM)를 처리합니다.
- 종료 대기에 상한을 둡니다. 상한이 지나면 강제 종료합니다.
- 상태 확인 엔드포인트를 둘로 나눕니다: `/healthz`(살아 있음), `/readyz`(의존성 준비됨).

## 테스트

- `tower::ServiceExt::oneshot`으로 서버를 띄우지 않고 라우터에 요청을 보냅니다.
- 테스트용 `AppState`는 가짜 구현(트레이트 객체) 또는 테스트 DB로 만듭니다.
- 상태 코드, 응답 본문, 에러 응답 형식을 함께 검증합니다.
- 실제 포트가 필요한 테스트는 `127.0.0.1:0`에 바인딩해 포트 충돌을 피합니다.
