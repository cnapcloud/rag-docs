---
sidebar_position: 7
---

# 리소스별 권한 강제

[접근 제어](access-control.md)가 Enterprise 배포에서 "요청자가 어떤 role인가"를 판정하는
경로를 다룬다면, 여기서는 그 role이 REST의 각 리소스·액션에 실제로 어떤 문턱값으로 걸리는지,
그리고 왜 리소스마다 강제 방식과 세분화 정도가 다른지 다룬다.

---

## 인증·인가·super-admin — 독립된 세 축

세 축은 서로 다른 코드가 검사하고, `kb_authz_enabled`의 영향도 서로 다르다.

| 축 | 무엇을 체크하나 | 담당 코드 | `kb_authz_enabled`에 영향받나 |
|----|-----------------|-----------|-------------------------------|
| 인증 | JWT 유효성(서명·만료·발급자) | `OIDCMiddleware` | 아니오 — `/health`, `/ready` 제외 항상 강제 |
| 인가 | KB별 role rank(`viewer`~`owner`) | `require_kb_role()` | 예 — `false`면 이 체크만 건너뜀 |
| super-admin | JWT `groups` claim | `require_super_admin()` | 아니오 — 항상 강제, `require_kb_role` 내부 우회 로직과도 별개 |

`kb_authz_enabled=false`가 끄는 건 "이 KB에 대해 무슨 role을 가졌는지" 하나뿐이다. 로그인
여부와 super-admin 여부는 이 값과 무관하게 계속 검사된다 — 꺼진 상태에서도
`/api/admin/config`처럼 super-admin 전용 엔드포인트는 여전히 403이고, 토큰 없는 요청은
여전히 401이다.

기본값이 `false`인 것은 두 가지 의도된 시나리오 때문이다.

- **부트스트랩** — rag-ent-api를 처음 붙이는 시점에는 `kb_membership`이 비어 있다. 곧바로
  `true`로 켜면 super-admin을 제외한 전원이 모든 KB 접근을 잃는다. KB별 role 할당(초대 등)을
  끝낸 뒤 켜는 순서를 전제로 기본값이 `false`다.
- **되돌릴 수 있는 완화 스위치** — 꺼도 `kb_membership` 행은 삭제되지 않고 그대로 남는다.
  권한 설정이 꼬여 접근이 막혔을 때 super-admin이 일시적으로 전체 개방했다가, 문제 해결 후
  다시 켜면 이전 role 설정이 그대로 복원된다.

## Admin과 Owner의 차이

역할 순위상 `owner`가 `admin`보다 높지만, 일상적인 KB 운영 권한(문서 업로드·삭제, 멤버
초대·역할 변경·제거, `visibility` 등 KB 설정 변경)은 거의 동일하다. 실제로 갈리는 지점은
KB의 존폐와 소유권을 결정하는 행위뿐이다.

| 행위 | Admin | Owner |
|------|-------|-------|
| 문서 업로드·삭제, 멤버 관리, KB 설정 변경 | 가능 | 가능 |
| KB 삭제 | 불가 | 가능 |
| 소유권 이전 | 불가 | 가능 |
| Owner의 role 변경 | 불가 — 대상이 owner면 항상 403 | 해당 없음(자기 자신) |
| Owner 제거(본인 포함) | 불가 — super-admin만 가능 | 본인이 스스로 나갈 수 없고 super-admin이 처리 |

일상 운영 권한은 여러 명(admin)에게 분산시키되, 되돌리기 어려운 결정(KB 삭제·소유권
이전)만 KB당 정확히 1명인 owner 또는 그 상위인 super-admin으로 좁힌다는 설계다. owner가
없어지면 KB는 자동으로 `frozen` 상태가 된다 — [Frozen KB](#frozen-kb의-예외-경로)와
[멤버십·초대·소유권 관리](../guides/rag-ent/membership-and-invites.md)에서 실제 API 흐름을
다룬다.

## 리소스마다 강제 방식이 다른 이유

같은 role rank 비교(`has_role`)를 쓰지만, 그 체크를 어디에 붙이는지는 리소스의 위험
프로파일에 따라 세 가지 패턴으로 갈린다.

- **KB 메타데이터·설정(`kb.py`)** — rag-ent-api가 소유한 라우터라 액션별로 개별
  `Depends(require_kb_role(...))`를 붙일 수 있다. 조회는 viewer, 이름·설명 같은 메타데이터
  수정은 admin, 삭제·설정 오버라이드처럼 되돌리기 어렵거나 기존 문서 지문에 영향을 주는
  액션은 owner로 세분화된다.
- **Documents** — rag-api가 이미 구현한 라우터를 rag-ent-api가 그대로 가져다 쓴다. 엔드포인트
  하나하나에 손대는 대신, 기동 시점에 라우트를 경로·메서드 패턴으로 세 그룹(super-admin만/
  editor 이상/viewer 이상)으로 나눠 그룹 단위로 role을 건다 — 원본 라우터 코드를 고치지 않고
  권한만 얹는 방식이다. `DELETE`이거나 경로에 `upload`/`reindex`/`fail`/`recover`가 포함되면
  editor, KB 하나로 좁혀지지 않는 전체 조회(`/docs`, `/docs/status`)는 super-admin, 나머지
  단건 조회는 viewer다.
- **Connectors** — 마찬가지로 rag-api 라우터를 재사용하지만, 액션별 구분 없이 생성·수정·
  삭제·동기화 전체를 admin 하나로 묶는다. 커넥터 조작은 외부 시스템 자격증명을 다루는
  본질적으로 민감한 작업이라 세분화 이득보다 단순함을 택했다. `kb_id`가 없는 전체 목록
  조회(필터 없는 cross-KB 조회)만 super-admin으로 더 좁아진다.
- **Search** — role 게이트 자체가 없다. 요청한 `kb_ids`를 호출자의 접근 가능한 KB 목록과
  교집합으로 필터링할 뿐이다. 권한 없는 KB가 섞여 있어도 403이 아니라 결과에서 조용히
  제외되고, 전부 제외돼도 빈 결과로 200이다 — 여러 KB를 넘나드는 질의가 일부 KB 권한
  때문에 통째로 실패하면 안 되기 때문이다.

## 엔드포인트별 최소 역할

### KB

| 메서드 | 경로 | 최소 역할 | 비고 |
|--------|------|-----------|------|
| GET | `/api/kb` | 인증만 | role 있는 KB + public KB 반환(super-admin은 전체) |
| GET | `/api/kb/{kb_id}` | viewer | public KB는 membership 없어도 통과 |
| POST | `/api/kb` | 인증만 | 생성자가 자동 owner. `visibility`로 생성 시점에 public 지정 가능 |
| PATCH | `/api/kb/{kb_id}` | admin | `visibility` 포함 |
| DELETE | `/api/kb/{kb_id}` | owner | |
| GET/PUT/PATCH/DELETE | `/api/kb/{kb_id}/settings*` | viewer(조회) / owner(변경) | 조회는 viewer, 오버라이드 변경·삭제는 owner |

### 멤버십·초대·소유권 이전

실제 curl 예제와 응답 형식은 [멤버십·초대·소유권 관리](../guides/rag-ent/membership-and-invites.md)를 참고한다.

| 메서드 | 경로 | 최소 역할 | 비고 |
|--------|------|-----------|------|
| GET/POST | `/api/kb/{kb_id}/members` | admin | pending invite 포함 조회, 초대 겸용 등록 |
| PATCH | `/api/kb/{kb_id}/members/{user_id}` | admin | 대상이 owner면 항상 403 |
| DELETE | `/api/kb/{kb_id}/members/{user_id}` | 조건부 | 본인 탈퇴는 역할 무관 항상 허용. 타인 제거는 admin 이상. 대상이 owner면 super-admin만 |
| DELETE | `/api/kb/{kb_id}/invites/{invite_id}` | admin | |
| POST | `/api/kb/{kb_id}/transfer-owner` | owner | frozen KB는 super-admin만(동결 해제 겸용) |

### 검색·문서·커넥터

| 메서드 | 경로 | 최소 역할 | 비고 |
|--------|------|-----------|------|
| POST | `/api/search` | viewer(KB별 필터) | 접근 불가 KB는 결과에서 제외, 전부 제외돼도 200 |
| POST | `/api/kb/{kb_id}/docs/upload*` | editor | |
| GET | `/api/kb/{kb_id}/docs*` | viewer | |
| DELETE | `/api/kb/{kb_id}/docs/{doc_id}` | editor | |
| POST | `/api/kb/{kb_id}/reindex`, `/docs/{doc_id}/reindex` | editor | KB 전체 또는 문서 하나만, `outdated` 상태만 재실행 |
| POST | `/api/kb/{kb_id}/docs/{doc_id}/fail`, `/recover` | editor | 상태 머신 강제 전환(내용 수정이 아닌 escape hatch) |
| GET | `/api/docs`, `/api/docs/status` | super-admin | KB 하나로 좁혀지지 않는 전체 집계 |
| `/api/connectors/*` (전체) | admin | 생성·수정·삭제·동기화 구분 없음. `kb_id` 필터 없는 목록 조회만 super-admin |

### 시스템 설정

| 메서드 | 경로 | 최소 역할 | 비고 |
|--------|------|-----------|------|
| GET | `/api/me` | 인증만 | 자기 자신의 `user_id`/`is_super_admin`/`kb_authz_enabled` |
| GET/PATCH | `/api/admin/config` | super-admin | [아래](#get-apiadminconfig의-이중-역할) 참고 |

## Frozen KB의 예외 경로

owner가 제거되고 승계 대상(admin)도 없으면 KB는 `frozen` 상태가 된다. frozen 상태에서는
viewer를 초과하는 모든 요청이 실제 role과 무관하게 403이다. 유일한 예외는
`transfer-owner`이며, 이 경로조차 frozen 상태에서는 super-admin만 통과한다 — frozen KB에는
owner 역할을 가진 사람이 아무도 없으므로 `require_kb_role("owner")`를 만족할 수 있는
일반 사용자가 원천적으로 없기 때문이다. 복구 절차는
[멤버십·초대·소유권 관리](../guides/rag-ent/membership-and-invites.md#소유권-이전과-자동-승계)에서
다룬다.

## `GET /api/admin/config`의 이중 역할

이 엔드포인트는 시스템 설정 조회 외에 콘솔의 super-admin 판별 프로브 역할을 겸한다 —
Access Management 메뉴를 보여줄지는 클라이언트가 JWT의 `groups` claim을 직접 디코딩하는
대신, 이 엔드포인트가 403을 내는지로 판정한다. `GET /api/me`가 이미 `is_super_admin`
필드를 갖고 있는데도 이 용도로 재사용하지 않는 이유는, `/api/me`는 의도적으로 인증만 된
모든 사용자에게 열려 있어야 하기 때문이다(헤더의 `kb_authz_enabled` 배지가 모든 사용자에게
보여야 함). 두 엔드포인트가 분리돼 있어야 `/api/admin/config`가 super-admin에게만 403 없이
응답한다는 신호가 그대로 유지된다.
