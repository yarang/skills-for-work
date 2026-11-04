---
name: rust-standards
description: Rust 언어 표준입니다. cargo fmt·clippy 툴체인, 워크스페이스와 모듈 구조, 에러 설계(thiserror·anyhow), unwrap 금지, 경계의 newtype, tokio 비동기 규칙, tracing, 테스트를 다룹니다. Rust 코드(axum, Tauri, CLI, TUI 포함)를 쓰거나 리뷰할 때 사용합니다.
---

# Rust 표준

## 툴체인

- `cargo fmt --check`와 `cargo clippy --all-targets --all-features -- -D warnings`를 통과해야 합니다.
- 툴체인 버전은 `rust-toolchain.toml`을 따르고, 크레이트의 `rust-version`(MSRV)보다 새 기능을 쓰지 않습니다.
- 워크스페이스에서는 공통 의존성 버전을 루트의 `[workspace.dependencies]`에 두고, 멤버에서는 `{ workspace = true }`로 씁니다.
- `#[allow(clippy::...)]`로 경고를 끌 때는 이유를 주석으로 남깁니다.

## 구조

- 바이너리 크레이트도 로직은 `lib.rs`에 두고, `main.rs`는 조립과 실행만 합니다. 그래야 통합 테스트가 로직에 접근할 수 있습니다.
- 모듈은 도메인별로 나눕니다. 공개 범위는 최소로 두고(`pub(crate)`), 진입점에서만 `pub use`로 다시 내보냅니다.
- 하나의 큰 크레이트가 컴파일 시간을 늘리면 워크스페이스 멤버로 쪼갭니다.

## 에러

- **라이브러리 코드**는 `thiserror`로 열거형 에러 타입을 만듭니다. 호출자가 경우별로 처리할 수 있어야 합니다.
- **바이너리·애플리케이션 최상위**에서는 `anyhow::Result`와 `.context("...")`로 맥락을 붙여도 됩니다.
- 테스트와 예제가 아닌 코드에서 `unwrap()`을 쓰지 않습니다. 불가능한 경우에만 `expect("왜 불가능한지")`를 씁니다.
- `?`로 전파하고, 변환은 `From` 구현이나 `map_err`로 합니다.
- `panic!`은 불변식이 깨진 경우에만 씁니다.

## 타입

- 경계에서 받은 값은 newtype으로 감싸 검증된 상태를 타입으로 표현합니다(`struct Email(String)` + `TryFrom<String>`).
- 상태가 여러 갈래면 `enum`으로 표현하고, `bool` 플래그 여러 개로 표현하지 않습니다.
- 직렬화 모델(`serde`)과 도메인 모델을 분리합니다. 외부 형식이 바뀌어도 도메인이 흔들리지 않게 합니다.
- 소유권: 읽기만 하면 `&str`/`&[T]`를 받고, 저장하면 `String`/`Vec<T>`를 받습니다. `clone()`으로 빌림 검사기를 피하지 않습니다.

## 비동기 (tokio)

- async 함수 안에서 블로킹 호출(`std::fs`, `std::thread::sleep`, CPU 집약 계산, 동기 DB 드라이버)을 하지 않습니다. `tokio::task::spawn_blocking`으로 보내거나 async 대응 API(`tokio::fs`)를 씁니다.
- `std::sync::Mutex`의 가드를 쥔 채 `.await`하지 않습니다. await를 넘어 락이 필요하면 `tokio::sync::Mutex`를 씁니다.
- 띄운 태스크는 `JoinHandle` 또는 `JoinSet`으로 추적하고, 종료 시 정리합니다.
- 타임아웃은 `tokio::time::timeout`으로, 종료 신호는 `tokio_util::sync::CancellationToken` 또는 `tokio::signal`로 다룹니다.

## 로그

- `println!`/`eprintln!`이 아니라 `tracing`을 씁니다. 함수 단위 맥락은 `#[tracing::instrument(skip(비밀값, 큰 인자))]`로 붙입니다.
- 구독자(`tracing_subscriber`) 설정은 `main`에서 한 번만 합니다.

## unsafe

- `unsafe` 블록에는 지켜야 할 불변식을 `// SAFETY:` 주석으로 적습니다. 새 `unsafe`는 리뷰에서 반드시 짚습니다.

## 테스트

- 단위 테스트는 같은 파일의 `#[cfg(test)] mod tests`에, 통합 테스트는 `tests/`에 둡니다.
- 비동기 테스트는 `#[tokio::test]`를 씁니다.
- 프로젝트가 `cargo nextest`를 쓰면 따릅니다.
- 외부 자원은 트레이트로 추상화해 테스트에서 가짜 구현을 넘깁니다.
