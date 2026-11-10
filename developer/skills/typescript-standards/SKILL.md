---
name: typescript-standards
description: TypeScript 언어 표준입니다. 프론트엔드(React, Tauri 웹뷰)와 백엔드(Node MCP 서버) 공통으로 tsconfig 엄격 모드, 타입 설계, 런타임 검증(zod), 에러 처리, 모듈, 패키지 매니저, 린트, 테스트(vitest)를 다룹니다. TypeScript·JavaScript 코드를 쓰거나 리뷰할 때 사용합니다.
---

# TypeScript 표준

브라우저와 Node 양쪽에서 쓰는 **언어 규칙만** 담습니다. 런타임별 규칙은 계층 스킬(`frontend-principles`, `backend-principles`의 Node 절)에 있습니다.

## 툴체인

- 패키지 매니저는 잠금 파일로 판단합니다: `bun.lock`·`bun.lockb` → bun, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json`·`npm-shrinkwrap.json` → npm. 섞어 쓰지 않습니다.
- 스크립트는 `package.json`의 `scripts`에 있는 것을 씁니다(`typecheck`, `lint`, `test`). 없으면 만들지 말고 보고합니다.
- 지원 런타임 버전은 `package.json`의 `engines`, `packageManager`, 버전 고정 파일로 확인합니다.
- ESM을 기본으로 둡니다(`"type": "module"`).

## tsconfig

- `"strict": true`는 필수입니다. 추가로 `noUncheckedIndexedAccess`, `noImplicitOverride`, `exactOptionalPropertyTypes`를 권장합니다.
- 엄격 옵션을 끄는 것으로 타입 에러를 해결하지 않습니다.

## 타입

- `any` 금지. 모르는 값은 `unknown`으로 받고 좁혀서(narrowing) 씁니다.
- 타입 단언(`as`)과 non-null 단언(`!`)은 근거를 주석으로 남길 수 있을 때만 씁니다. `as unknown as T`는 금지합니다.
- 상태가 여러 갈래면 판별 유니온(`{ kind: 'loading' } | { kind: 'ok'; data: T }`)으로 표현하고, `switch`에서 `never`로 빠짐없음을 검사합니다.
- 같은 문자열이라도 의미가 다르면 브랜드 타입으로 구분합니다(`type UserId = string & { readonly __brand: 'UserId' }`).
- 객체 모양은 `type`과 `interface` 중 프로젝트 관례를 따릅니다. 없으면 `type`을 씁니다.
- `enum` 대신 `as const` 객체와 유니온 타입을 씁니다.

## 경계 검증

- 외부 입력(fetch 응답, `JSON.parse`, 환경변수, IPC, 폼)은 **zod 같은 런타임 스키마**로 파싱합니다. TypeScript 타입은 런타임에 아무것도 검사하지 않습니다.
- 스키마에서 타입을 끌어냅니다(`z.infer<typeof Schema>`). 타입과 스키마를 따로 쓰지 않습니다.

## 에러

- `throw`하는 것은 `Error`의 하위 클래스만입니다. 문자열이나 객체를 던지지 않습니다.
- `catch (e)`의 `e`는 `unknown`입니다. `instanceof`로 좁힌 뒤 씁니다.
- 원인을 이어 붙입니다: `new AppError('...', { cause: e })`.
- 예상된 실패(검증 실패, 없음)가 흔한 함수는 결과 타입(`{ ok: true; value } | { ok: false; error }`)으로 돌려줘도 됩니다. 한 모듈 안에서 방식을 섞지 않습니다.
- `await` 없이 떠도는 Promise를 만들지 않습니다(`@typescript-eslint/no-floating-promises`).

## 모듈

- 기본 내보내기(default export)보다 이름 있는 내보내기를 씁니다.
- 도메인 진입점(`index.ts`)은 공개할 것만 다시 내보냅니다. 모든 파일을 다시 내보내는 배럴 파일을 만들지 않습니다.
- 순환 import를 만들지 않습니다.
- Node 내장 모듈은 `node:` 접두사로 가져옵니다.
- npm에 배포하는 라이브러리 코드는 `node:*` 표준 API만 씁니다.

## 스타일

- `const` 기본, `let`은 재할당이 필요할 때만, `var` 금지.
- 배열·객체는 바꾸지 않고 새로 만듭니다(spread, `map`, `filter`). 함수 인자에 `readonly`를 붙입니다.
- `==` 금지, `===`만 씁니다.

## 테스트

- 테스트 러너는 vitest를 기본으로 합니다. 프로젝트가 jest를 쓰면 따릅니다.
- 테스트 파일은 대상 옆에 `*.test.ts`로 둡니다.
- 모듈 전체를 mock하기보다 의존성을 주입해 가짜를 넘깁니다.
- 타입 수준 보장이 중요하면 `expectTypeOf`로 타입 테스트를 씁니다.

## bun을 쓸 때

잠금 파일이 `bun.lock`·`bun.lockb`면 런타임과 패키지 매니저 모두 bun을 씁니다. bun 1.4 기준으로 확인한 함정입니다. bun 버전이 바뀌면 이 절을 고칩니다.

- **scripts는 `bun run <script>`로 실행합니다.** `bun test`는 `test` script가 아니라 bun 내장 테스트 러너를 실행합니다.
- bun 프로젝트의 새 테스트는 `bun:test`로 씁니다. 다른 러너가 설정된 프로젝트는 그 러너를 유지합니다.
- **타입 검사는 별도로 실행합니다.** bun은 TypeScript를 실행만 하고 타입을 검사하지 않습니다. `bunx tsc --noEmit`을 실행합니다(`typescript`가 devDependencies에 없으면 `bunx -p typescript tsc --noEmit`).
- TypeScript 실행, watch, `.env` 로딩은 bun에 내장되어 있으므로 이를 위한 별도 패키지를 추가하지 않습니다.
- `.env` 자동 로딩은 설정 누락을 가립니다. 로컬에서는 `.env` 덕분에 돌아가도 배포 환경에서 빠질 수 있으므로, 시작 시 설정 검증을 그대로 둡니다.
- 런타임 전용 API(`Bun.*`, `bun:*`)는 이점이 분명할 때만 씁니다.
- 의존성을 추가한 뒤에는 `bun audit`을 실행합니다.
- bun은 의존성의 설치 후 스크립트를 기본으로 실행하지 않습니다. 그 때문에 설치 결과가 깨지면 신뢰 목록(`trustedDependencies`)에 넣을지 사람이 결정하도록 제안으로 남깁니다.
