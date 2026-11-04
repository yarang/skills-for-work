---
name: python-standards
description: Python 언어 표준입니다. uv·ruff·타입 검사기 툴체인, 타입 힌트, pydantic 경계 검증, 예외 설계, logging, async, 패키지 구조, pytest를 다룹니다. Python 코드(FastAPI, MCP 서버, 스크립트 포함)를 쓰거나 리뷰할 때 사용합니다.
---

# Python 표준

## 툴체인

- 프로젝트 관리는 `uv`를 기본으로 합니다(`uv sync`, `uv run`, `uv add`). 프로젝트가 poetry나 pip을 쓰면 따릅니다.
- 의존성은 `pyproject.toml`에 선언합니다. 개발 의존성은 `[dependency-groups]`(uv) 또는 해당 도구의 dev 그룹에 둡니다.
- 린트와 포맷은 `ruff check`, `ruff format`을 씁니다.
- 타입 검사는 프로젝트에 설정된 것(`mypy` 또는 `pyright`)을 씁니다. 새 코드는 엄격 모드를 통과해야 합니다.
- 지원 버전은 `requires-python`을 따릅니다. 그보다 새 문법을 쓰지 않습니다.

## 구조

- `src/<패키지>/` 레이아웃을 씁니다. 그 아래를 도메인별 하위 패키지로 나눕니다.
- import는 절대 경로로 합니다. 모듈 import 시점에 부작용(네트워크 연결, 파일 쓰기)을 만들지 않습니다.
- 진입점은 `if __name__ == "__main__":` 또는 `[project.scripts]`로 둡니다.

## 타입

- 공개 함수에는 인자와 반환 타입을 모두 적습니다. 새 코드에 `Any`를 쓰지 않습니다.
- 내장 제네릭(`list[str]`, `dict[str, int]`)과 `X | None`을 씁니다. `typing.List`, `Optional`은 쓰지 않습니다.
- 값 객체는 `@dataclass(frozen=True, slots=True)`로 만듭니다. 외부 데이터 모델은 pydantic `BaseModel`로 만듭니다.
- 고정된 선택지는 `Literal` 또는 `enum.StrEnum`으로 표현합니다.
- 구조적 인터페이스가 필요하면 `typing.Protocol`을 씁니다. 주입받는 의존성의 타입으로 쓰기 좋습니다.

## 경계 검증

- 외부 입력은 pydantic 모델로 파싱합니다(`Model.model_validate(data)`). 검증된 모델 안쪽에서는 `dict`를 돌려 쓰지 않습니다.
- 설정은 `pydantic-settings`의 `BaseSettings`로 한 번 읽습니다.

## 예외

- 도메인마다 기반 예외 클래스를 두고(`class BillingError(Exception)`), 구체 예외를 그 아래에 둡니다.
- `except:`와 `except Exception: pass`는 금지합니다. 잡을 예외를 좁혀서 적습니다.
- 다시 올릴 때는 원인을 이어 붙입니다: `raise AppError("...") from e`.
- 자원은 `with`/`async with`로 다룹니다.

## 로그

- `print`가 아니라 `logging`을 씁니다. 모듈마다 `logger = logging.getLogger(__name__)`를 둡니다.
- 메시지는 지연 포맷으로 남깁니다: `logger.info("user %s", user_id)`. f-string은 로그를 남기지 않는 레벨에서도 계산됩니다.
- 로그 핸들러 설정은 진입점에서 한 번만 합니다. 라이브러리 모듈은 설정하지 않습니다.

## async

- async 함수 안에서 블로킹 호출(`requests`, `time.sleep`, 동기 DB 드라이버, 큰 파일 I/O)을 하지 않습니다. async 라이브러리(`httpx.AsyncClient`)를 쓰거나 `asyncio.to_thread`로 보냅니다.
- 태스크는 `asyncio.TaskGroup`으로 묶어 고아 태스크를 만들지 않습니다.
- 타임아웃은 `asyncio.timeout()`으로 겁니다.

## 스타일

- 기본값으로 바뀌는 객체(`def f(x=[])`)를 쓰지 않습니다.
- 경로는 `pathlib.Path`로 다룹니다.
- 셸 명령은 `subprocess.run([...], check=True)`처럼 리스트로 넘깁니다. `shell=True`는 쓰지 않습니다.

## 테스트

- pytest를 씁니다. 테스트는 `tests/` 아래에 패키지 구조를 따라 둡니다.
- 준비 코드는 fixture로 만들고, 범위(`scope`)를 필요한 만큼만 넓힙니다.
- 여러 입력은 `@pytest.mark.parametrize`로 다룹니다.
- async 테스트는 프로젝트에 설정된 플러그인(`pytest-asyncio` 또는 `anyio`)을 따릅니다.
- `monkeypatch`로 전역을 바꾸기보다 의존성 주입으로 가짜를 넘깁니다.
