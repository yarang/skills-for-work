---
name: go-standards
description: Go 언어 표준입니다. gofmt·go vet·golangci-lint 툴체인, 패키지 구조, 에러 래핑(%w, errors.Is/As), context 전파, 인터페이스 위치, 고루틴 수명, 테이블 테스트를 다룹니다. Go 코드를 쓰거나 리뷰할 때 사용합니다.
---

# Go 표준

## 툴체인

- `gofmt`(또는 `goimports`)로 포맷하고, `go vet ./...`을 통과해야 합니다. 프로젝트에 `.golangci.yml`이 있으면 `golangci-lint run`도 통과해야 합니다.
- Go 버전은 `go.mod`의 `go` 지시어를 따릅니다.
- 의존성을 바꾼 뒤에는 `go mod tidy`를 실행합니다. 단, `dev-workflow` 파이프라인 안에서는 developer·tester가 실행하지 않습니다(`go.sum`은 보호 경로입니다). 메인 대화가 ④-1에서 `go get '<모듈>/...@<버전>'`으로 받고, 모든 행이 모인 뒤 ⑦ⓒ에서 `go mod tidy`를 실행합니다.

## 구조

- 실행 파일은 `cmd/<이름>/main.go`에 두고, `main`은 조립(설정 읽기, 의존성 생성, 서버 시작)만 합니다.
- 외부에 공개하지 않을 코드는 `internal/` 아래에 둡니다. 그 아래를 도메인별 패키지로 나눕니다(`internal/billing`).
- 패키지 이름은 짧은 소문자 단수형입니다. `util`, `common`, `helpers` 같은 이름은 쓰지 않습니다.
- 패키지 수준 가변 전역 변수와 `init()`의 부작용을 만들지 않습니다.

## 에러

- 에러는 반환값으로 돌려줍니다. 맥락을 붙여 감쌉니다: `fmt.Errorf("load user %s: %w", id, err)`.
- 비교는 `errors.Is`, 타입 확인은 `errors.As`로 합니다. 에러 문자열을 비교하지 않습니다.
- 호출자가 구분해야 하는 에러는 센티널(`var ErrNotFound = errors.New("not found")`) 또는 에러 타입으로 공개합니다.
- 에러는 **처리하거나 반환하거나** 둘 중 하나만 합니다. 로그를 남기고 또 반환하면 같은 에러가 여러 번 기록됩니다.
- `panic`은 프로그래밍 오류(불가능한 상태)에만 씁니다. 라이브러리 코드에서 쓰지 않습니다.
- `_`로 에러를 버리지 않습니다. 정말 무시해도 되면 이유를 주석으로 남깁니다.

## context

- I/O를 하거나 오래 걸리는 함수는 첫 인자로 `ctx context.Context`를 받습니다.
- context를 구조체 필드에 저장하지 않습니다.
- 요청 범위 값(요청 ID 등)만 `context.WithValue`에 넣습니다. 선택적 인자를 context로 넘기지 않습니다.
- 외부 호출에는 `context.WithTimeout`으로 상한을 둡니다.

## 인터페이스

- 인터페이스는 **쓰는 쪽 패키지**에 정의합니다. 구현하는 쪽은 구체 타입을 반환합니다("인터페이스를 받고, 구조체를 반환").
- 인터페이스는 작게(메서드 1~3개) 둡니다.
- 의존성은 생성자 인자로 받습니다: `func NewService(repo UserRepo, clock Clock) *Service`.

## 동시성

- 고루틴을 시작하는 쪽이 그 고루틴의 종료를 책임집니다. 종료 신호(ctx)와 대기(`sync.WaitGroup`, `errgroup.Group`) 없이 고루틴을 띄우지 않습니다.
- 여러 고루틴의 에러를 모으려면 `golang.org/x/sync/errgroup`을 씁니다.
- 공유 상태는 채널 또는 `sync.Mutex`로 보호합니다. `go test -race`를 통과해야 합니다.

## 스타일

- 이른 반환으로 중첩을 줄입니다. 정상 경로는 왼쪽 들여쓰기에 둡니다.
- 수신자 이름은 타입의 짧은 약어로 일관되게 씁니다.
- 공개 식별자에는 이름으로 시작하는 문서 주석을 답니다.

## 테스트

- 테이블 기반 테스트와 `t.Run`으로 하위 테스트를 만듭니다.
- 도우미 함수에는 `t.Helper()`를 붙이고, 정리는 `t.Cleanup`으로 합니다.
- HTTP 핸들러는 `httptest.NewRecorder`·`httptest.NewServer`로 테스트합니다.
- 테스트 대상 패키지 밖에서 공개 API만 검증하려면 `package xxx_test`를 씁니다.
