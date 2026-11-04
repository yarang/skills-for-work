---
name: react-standards
description: React(+Vite) 프레임워크 표준입니다. 컴포넌트 설계, 훅 규칙, 서버 상태(TanStack Query), 폼, 라우팅, 에러 경계, 렌더링 성능, React Testing Library 테스트를 다룹니다. package.json의 dependencies에 react가 있는 디렉터리에서 코드를 쓰거나 리뷰할 때 사용합니다.
---

# React 표준

`frontend-principles`의 규칙(네 가지 화면 상태, 서버 상태와 UI 상태 구분, 응답 검증)을 React로 구현하는 방법입니다.

## 구조

```
src/
  features/<도메인>/
    api.ts          # 이 도메인의 API 호출과 응답 스키마
    hooks.ts        # useXxxQuery, useXxxMutation
    components/     # 도메인 전용 컴포넌트
    index.ts        # 공개 진입점
  shared/ui/        # 두 도메인 이상이 쓰는 표현 컴포넌트
  app/              # 라우터, 프로바이더, 전역 레이아웃
```

## 컴포넌트

- 함수 컴포넌트만 씁니다. props 타입은 `type XxxProps = {...}`로 이름을 붙여 둡니다.
- 한 컴포넌트는 한 가지를 합니다. 데이터를 가져오는 컴포넌트와 그리는 컴포넌트를 나누면 테스트가 쉬워집니다.
- 목록의 `key`는 안정적인 ID를 씁니다. 배열 인덱스는 순서가 바뀌지 않는 정적 목록에서만 씁니다.
- props로 받은 값을 `useState`의 초깃값으로 복사해 동기화하지 않습니다. 계산하거나, 부모가 상태를 갖게 합니다.

## 훅

- 훅 규칙(최상위에서만 호출, 조건문 안에서 호출 금지)을 지키고 `eslint-plugin-react-hooks`를 켭니다.
- `useEffect`는 **외부 시스템과 동기화**(구독, 타이머, DOM API)할 때만 씁니다. 파생 값 계산이나 이벤트 처리에 쓰지 않습니다.
- effect에서 만든 구독·타이머는 정리 함수에서 해제합니다.
- 의존성 배열을 비워서 경고를 없애지 않습니다. 경고가 나면 설계를 다시 봅니다.

## 서버 상태

- 서버 데이터는 TanStack Query(`useQuery`, `useMutation`)로 다룹니다. `useEffect` + `fetch` + `useState` 조합으로 직접 만들지 않습니다.
- 쿼리 키는 도메인별 팩토리로 만듭니다: `userKeys.detail(id)`.
- `queryFn` 안에서 응답을 zod로 파싱합니다. 컴포넌트까지 검증 안 된 데이터가 오지 않게 합니다.
- 변경 뒤에는 관련 쿼리를 무효화(`invalidateQueries`)합니다.
- 네 가지 화면 상태를 모두 그립니다: `isPending`, `isError`, 빈 결과, 정상.

## 폼

- 필드가 몇 개를 넘으면 `react-hook-form` + zod 리졸버를 씁니다. 서버와 같은 스키마를 공유할 수 있으면 공유합니다.
- 제출 중에는 버튼을 막고, 서버 에러를 필드 옆에 보여 줍니다.

## 에러 경계

- 라우트 단위로 에러 경계를 둡니다. 한 화면의 오류가 앱 전체를 하얗게 만들지 않게 합니다.
- 에러 경계는 렌더링 오류만 잡습니다. 이벤트 핸들러와 비동기 오류는 직접 처리합니다.

## 성능

- `useMemo`, `useCallback`, `memo`는 측정해서 필요할 때만 씁니다. 프로젝트가 React Compiler를 쓰면 손으로 쓰지 않습니다.
- 라우트 단위로 `lazy()` + `Suspense` 코드 분할을 합니다.
- 긴 목록(수백 개 이상)은 가상화합니다.

## 보안

- `dangerouslySetInnerHTML`은 DOMPurify 같은 정화기를 거친 값에만 씁니다. 리뷰에서 반드시 짚습니다.
- 사용자 입력으로 `href`를 만들 때 `javascript:` 스킴을 막습니다.

## 테스트

- React Testing Library로 **사용자가 보는 것**을 테스트합니다. 조회는 `getByRole` → `getByLabelText` → `getByText` 순서로 고르고, `data-testid`는 마지막 수단입니다.
- 상호작용은 `@testing-library/user-event`로 합니다.
- 네트워크는 MSW로 가짜를 둡니다. 훅이나 모듈을 직접 mock하지 않습니다.
- 네 가지 화면 상태를 각각 테스트합니다.
