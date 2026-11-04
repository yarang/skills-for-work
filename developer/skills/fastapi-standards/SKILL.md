---
name: fastapi-standards
description: FastAPI 프레임워크 표준입니다. 라우터 구성, pydantic 요청·응답 모델, Depends 의존성 주입, lifespan 자원 관리, 예외 처리기, async 규칙, 설정, httpx 기반 테스트를 다룹니다. Python 의존성에 fastapi가 있는 디렉터리에서 코드를 쓰거나 리뷰할 때 사용합니다.
---

# FastAPI 표준

`backend-principles`의 규칙(수명주기, 설정, 외부 호출, 동시성)을 FastAPI로 구현하는 방법입니다.

## 구조

```
src/<패키지>/
  main.py               # create_app(): 앱 조립, 라우터 등록, lifespan
  config.py             # Settings(BaseSettings)
  features/<도메인>/
    router.py           # APIRouter, 엔드포인트 (얇게)
    schemas.py          # 요청·응답 pydantic 모델
    service.py          # 업무 로직 (FastAPI를 모름)
    repository.py       # 저장소 접근
    deps.py             # 이 도메인의 Depends 함수
```

- 앱은 `create_app()` 팩토리로 만듭니다. 테스트가 설정을 바꿔 새 앱을 만들 수 있습니다.
- 라우터 함수는 입력을 받아 서비스를 부르고 결과를 돌려주기만 합니다. 업무 로직을 넣지 않습니다.
- `service.py`는 `fastapi`를 import하지 않습니다. `HTTPException`도 던지지 않고 도메인 예외를 던집니다.

## 모델

- 요청 모델과 응답 모델을 따로 둡니다(`UserCreate`, `UserRead`). ORM 모델을 그대로 응답하지 않습니다.
- 모든 엔드포인트에 `response_model`(또는 반환 타입 표기)을 둡니다. 응답에 비밀 필드가 새는 것을 막는 경계입니다.
- 입력 제약은 모델에 둡니다(`Field(min_length=1, max_length=100)`, `EmailStr`).
- 알 수 없는 필드를 거부하려면 `model_config = ConfigDict(extra="forbid")`를 씁니다.

## 의존성 주입

- DB 세션, 현재 사용자, 서비스 객체는 `Depends`로 받습니다. 타입 별칭으로 줄입니다: `SessionDep = Annotated[AsyncSession, Depends(get_session)]`.
- 정리가 필요한 의존성은 `yield` 의존성으로 만듭니다.
- 인증·인가는 의존성으로 두고, 라우터 수준(`dependencies=[...]`)에서 일괄 적용합니다.

## 수명주기

- 연결 풀, HTTP 클라이언트 같은 프로세스 자원은 `lifespan` 컨텍스트에서 만들고 닫습니다. `@app.on_event`는 쓰지 않습니다.
- 자원은 `app.state`에 두고 의존성 함수로 꺼냅니다. 모듈 전역 변수에 두지 않습니다.

## 에러

- 도메인 예외를 HTTP 응답으로 바꾸는 일은 `app.add_exception_handler`에서 **한 곳에서** 합니다.
- 에러 응답 본문 형식을 하나로 통일합니다(예: RFC 9457 Problem Details).
- 500 응답에 스택 트레이스나 내부 메시지를 담지 않습니다. 로그에만 남깁니다.

## async

- `async def` 엔드포인트 안에서 블로킹 호출을 하지 않습니다. 동기 라이브러리만 있으면 엔드포인트를 `def`로 선언해 스레드 풀에서 돌게 하거나 `run_in_threadpool`을 씁니다.
- 외부 HTTP 호출은 lifespan에서 만든 `httpx.AsyncClient` 하나를 공유하고, 타임아웃을 겁니다.
- 요청 처리 뒤 가벼운 작업만 `BackgroundTasks`로 보냅니다. 실패하면 안 되는 작업은 작업 큐로 보냅니다.

## 보안

- CORS 허용 출처를 명시합니다. 인증 쿠키를 쓰면서 `allow_origins=["*"]`를 쓰지 않습니다.
- 목록 엔드포인트에는 페이지 크기 상한을 둡니다(`limit: int = Query(20, le=100)`).
- 운영 환경에서 `/docs`를 열지 여부를 설정으로 정합니다.

## 테스트

- `httpx.AsyncClient(transport=ASGITransport(app=app))` 또는 `TestClient`로 테스트합니다.
- 의존성은 `app.dependency_overrides`로 가짜로 바꿉니다. 테스트가 끝나면 비웁니다.
- lifespan이 필요한 테스트는 lifespan을 실행하는 방식(`with TestClient(app)` 또는 `LifespanManager`)으로 앱을 엽니다.
- 상태 코드와 응답 본문 스키마를 함께 검증합니다.
