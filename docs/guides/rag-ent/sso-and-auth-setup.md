---
sidebar_position: 1
---

# SSO·인증 설정

rag-ent-api 배포와 운영 중인 Keycloak realm이 전제 조건이다. Enterprise 배포는 rag-api
이미지를 rag-ent-api 이미지로 교체하고 OIDC 설정을 추가하는 방식으로 전환되며, Core 대비
달라지는 구조는 [아키텍처](../../concepts/architecture.md)에서 다룬다. 인증(JWT 검증)과
권한(KB 역할 검사)이 요청 하나 안에서 어떻게 이어지는지는
[접근 제어](../../concepts/access-control.md)가 다루고, Keycloak과 rag-ent-api 양쪽을 연결해
그 경로가 실제로 동작하도록 만드는 절차를 다룬다.

---

## Keycloak 클라이언트 구성

| 클라이언트 | 유형 | 용도 | 필수 설정 |
|------------|------|------|-----------|
| 관리 콘솔용(`rag`) | Public(SPA) | 콘솔 로그인, Authorization Code + PKCE | Valid redirect URIs에 `<콘솔 도메인>/auth/callback` 등록, client secret 미사용 |
| Admin API용(선택) | Confidential | 멤버 초대 시 이메일로 기존 가입 여부 조회 | Service account 활성화, realm `view-users` 권한 부여 |

Admin API용 클라이언트를 만들지 않으면 이메일 조회가 항상 "미가입"으로 처리되어 모든 초대가
pending invite 경로로만 동작한다 — 첫 로그인 시 자동으로 활성화되므로 기능 저하는 아니다.

### super-admin 그룹

전역 관리자 그룹을 만들고(기본 이름 `rag-super-admin`) 관리자 계정을 소속시킨다. 이 그룹명이
JWT의 `groups` claim에 실리도록 client scope에 Group Membership mapper를 추가한다 — Full
group path는 비활성화한다. 활성화하면 claim 값이 `/rag-super-admin`으로 실려 그룹명이 정확히
일치하지 않게 된다.

### audience mapper (선택)

`oidc.audience`는 기본값이 빈 문자열이며, 비어 있으면 rag-ent-api는 `aud` claim 자체를
검증하지 않는다(서명·발급자·만료는 그대로 검증). 값을 채우는 순간부터 그 값과 일치하지 않는
`aud`를 가진 토큰은 401로 거부된다.

검증을 켜려면 두 가지를 순서대로 맞춘다.

1. Keycloak `rag` 클라이언트에 Audience mapper를 추가해 발급되는 토큰의 `aud`가
   `oidc.audience`와 같은 값을 갖도록 한다 — mapper가 없으면 클라이언트는 기본값
   `aud="account"`를 발급한다.
2. rag-ent-api `settings.yaml`의 `oidc.audience`를 같은 값으로 채운다.

순서를 바꿔 mapper 없이 설정값만 채우면 정상 토큰까지 401로 막힌다.

## rag-ent-api 설정

```yaml
oidc:
  issuer_url: "https://<keycloak 도메인>/realms/<realm>"
  audience: ""                          # 비우면 aud 미검증 — 위 audience mapper 절 참고
  jwks_cache_ttl_seconds: 3600
  admin_url: ""                         # 선택 — Keycloak Admin API 베이스 URL
  admin_client_id: ""                   # 선택 — Secret으로 주입
  admin_client_secret: ""               # 선택 — Secret으로 주입

authz:
  super_admin_role: "rag-super-admin"   # super-admin 그룹 절의 그룹명과 일치해야 함
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `oidc.issuer_url` | `""` | Keycloak realm 발급자 URL. JWKS 조회(`/protocol/openid-connect/certs`)와 JWT `iss` 검증에 쓰인다 |
| `oidc.audience` | `""` | 비어 있으면 `aud` 미검증. 값을 채우면 Keycloak 클라이언트에 Audience mapper가 있어야 한다 |
| `oidc.jwks_cache_ttl_seconds` | `3600` | JWKS 캐시 유효 시간(초) — 키 로테이션 반영 주기 |
| `oidc.admin_url` | `""` | Keycloak Admin API 베이스 URL. 비어 있으면 이메일 조회가 항상 미가입으로 처리된다 |
| `oidc.admin_client_id` / `admin_client_secret` | `""` | Admin API용 confidential 클라이언트 자격증명 |
| `authz.super_admin_role` | `"rag-super-admin"` | JWT `groups` claim에서 슈퍼관리자 여부를 판정하는 그룹명 |

`admin_url`을 비워두면 이메일 조회가 예외 없이 항상 미가입으로 처리된다 — Keycloak Admin
API가 응답하지 않는 상황에서도 초대 생성 자체는 항상 가능해야 하기 때문이다.

Docker Compose는 `docker/settings.yaml`, Kubernetes는 ConfigMap에 같은 키를 채운다 — 클라이언트
시크릿류(`admin_client_secret` 등)는 파일에 평문으로 남기지 않고 Secret으로 주입한다.

## 관리 콘솔 ENT 모드 활성화

콘솔은 단일 빌드로 배포되며 환경값의 존재 여부만으로 모드가 갈린다 — `OIDC_CLIENT_ID`가
비어 있지 않으면 ENT 모드가 켜진다. Docker Compose는 `public/env.js`, Kubernetes는 콘솔
이미지의 ConfigMap에 아래 값을 채운다.

```js
window.__env = {
  API_URL: "https://<rag-ent-api 주소>",
  OIDC_ISSUER: "https://<keycloak 도메인>/realms/<realm>",
  OIDC_CLIENT_ID: "rag",   // Keycloak 클라이언트 구성의 SPA 클라이언트 ID
  // ...
};
```

ENT 모드에서는 미인증 접속 시 Keycloak 로그인 화면으로 리다이렉트되고(Authorization Code +
PKCE, 콜백 경로 `/auth/callback`), 로그인 후 액세스·ID 토큰은 브라우저 메모리에만 유지된다.
refresh 토큰만 `sessionStorage`에 저장되어 새로고침 시에는 재로그인 없이 조용히 갱신되지만,
탭을 닫으면 함께 사라져 다음 접속에서는 다시 Keycloak 로그인을 거친다.

## RBAC 활성화

설치 직후 `kb_authz_enabled`는 꺼져 있을 수 있다 — 이 상태에서는 인증만 요구되고 KB 역할
검사는 건너뛴다([kb_authz_enabled 토글](../../concepts/access-control.md#kb_authz_enabled-토글)
참고). 단계적으로 켤 수 있다.

1. super-admin 계정으로 콘솔에 로그인한다.
2. 사이드바 RBAC 배지(`RBAC: ON` / `RBAC: OFF`)로 현재 상태를 확인한다 — 값은 `GET /api/me`
   응답의 `kb_authz_enabled` 필드와 같다.
3. super-admin만 배지를 눌러 켜고 끌 수 있다. API로 직접 바꾸려면:

   ```bash
   curl -X PATCH https://<api>/api/admin/config \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"kb_authz_enabled": true}'
   ```

4. `false → true`로 켜는 순간, owner가 없는 모든 KB에 이 요청을 보낸 super-admin이 owner로
   자동 등록된다. 실제 담당자에게 소유권을 넘기는 절차는
   [Access Management](../rag-admin/access-management.md)에서 다룬다.

## 연동 애플리케이션의 토큰 전달

REST 경로는 그대로이므로, 연동 애플리케이션은 사용자 토큰을 `Authorization: Bearer`로
실어 보내기만 하면 권한 필터가 적용된다.

```
# 검색 — 호출자가 접근 가능한 KB만 대상이 됨
POST /api/search  (Authorization: Bearer <사용자 JWT>)

# MCP — 동일한 인증 경로를 그대로 통과한다 (예: LibreChat 등 MCP 클라이언트 설정)
"rag": {
  "type": "streamable-http",
  "url": "https://<api>/mcp",
  "headers": { "Authorization": "Bearer <사용자 JWT>" }
}
```

## 구성 검증

| # | 확인 | 기대 결과 |
|---|------|-----------|
| 1 | 토큰 없이 `GET /api/kb` 호출 | 401 |
| 2 | 일반 사용자 토큰으로 `GET /api/me` 호출 | 본인 정보와 `is_super_admin: false` |
| 3 | super-admin 토큰으로 `GET /api/admin/config` 호출 | 200 (일반 사용자는 403) |
| 4 | 콘솔에서 로그아웃 후 재접속 | Keycloak 로그인 화면으로 리다이렉트 |

KB 역할별 접근 통제 확인은 [접근 제어](../../concepts/access-control.md), 멤버 초대·소유권
이전 확인은 [Access Management](../rag-admin/access-management.md)에서 이어서 다룬다.
