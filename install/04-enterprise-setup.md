# Enterprise 구성 — SSO 및 KB 접근제어

Enterprise 배포 설치 담당자, IdP 관리자를 위한 구성 가이드. Core 설치 완료
([02-quickstart.md](02-quickstart.md) 또는 [03-install-k8s.md](03-install-k8s.md))와 운영
중인 OIDC IdP(Keycloak 기준 설명)가 전제 조건이다.

Enterprise 배포는 rag-ent-api 이미지로 API를 교체하고 IdP·SMTP 설정을 추가하면 된다.
활성화되는 기능: OIDC 인증, KB 단위 RBAC(viewer/editor/admin/owner), 멤버십·이메일 초대,
소유권 관리, 권한 필터가 적용된 검색·MCP. 상세 동작은 [api-guide.md](../reference/01-api-guide.md) 참조.

이 문서는 `oidc`/`authz`/`smtp`/`security` 등 Enterprise 전용 설정만 다룬다. rag-ent-api는
rag-api의 `Settings`(ingestion/dedup/chunking/embedding/retrieval 등)를 그대로 상속해 쓰므로,
나머지 공통 설정값은 rag-api의 [02-settings-guide.md](../reference/02-settings-guide.md)를 참고한다.

---

## 1. Keycloak 설정

### 1.1 클라이언트 생성

| 클라이언트 | 유형 | 용도 | 필수 설정 |
|-----------|------|------|-----------|
| 관리 콘솔용 (예: `rag`) | Public (SPA) | 콘솔 로그인 (Authorization Code + PKCE) | Valid redirect URIs: `https://<콘솔 도메인>/auth/callback`, Web origins: 콘솔 origin. **client secret 사용 안 함** |
| Admin API용 (선택) | Confidential | 사용자 이메일 조회(멤버 초대 시 가입 여부 판별) | service account 활성화 + realm `view-users` 권한 |

Admin API용 클라이언트를 생성하지 않으면 사용자 조회가 항상 "미가입"으로 처리되어 모든
초대가 pending invite 경로로 동작한다 (기능 저하는 아님 — 첫 로그인 시 자동 활성화).

### 1.2 super-admin 그룹

전역 관리자 그룹을 만들고(기본 이름 `rag-super-admin`) 관리자 계정을 소속시킨다. JWT의
`groups` claim에 그룹명이 포함되도록 client scope에 **Group Membership mapper**를 추가한다
(Full group path 비활성 권장 — claim 값이 `/rag-super-admin`이 아닌 `rag-super-admin`이어야 함).

### 1.3 audience mapper (권장)

`oidc.audience`는 기본값이 빈 문자열이며, 빈 값이면 `aud` 검증 자체를 건너뛴다(서명·발급자·
만료는 그대로 검증됨). 값을 채우면 그 순간부터 `aud`가 일치하지 않는 토큰은 401로 거부된다.

검증을 켜려면 두 가지를 함께 한다: (1) Keycloak "rag" 클라이언트에 토큰의 `aud`가
`oidc.audience` 값과 일치하도록 **Audience mapper**를 추가하고 (mapper 없이는 클라이언트가
기본값 `aud="account"`를 발급함), (2) `settings.yaml`의 `oidc.audience`를 그 값으로 채운다.
순서를 반대로 하면(설정만 채우고 mapper 미구성) 정상 토큰까지 401로 막힌다.

## 2. rag-ent-api 설정 (settings.yaml)

Core와 동일한 `settings.yaml`에 아래 Enterprise 설정을 추가하면 된다 — Docker Compose는
[02-quickstart.md](02-quickstart.md)의 `docker/settings.yaml` 파일, Kubernetes는
[03-install-k8s.md](03-install-k8s.md) 3.1의 `settings.yaml` ConfigMap(reloader 어노테이션이
있으면 저장만으로 자동 재기동).

```yaml
oidc:
  issuer_url: "https://<keycloak 도메인>/realms/<realm>"
  audience: "rag-api"                  # audience mapper와 일치
  jwks_cache_ttl_seconds: 3600
  # Admin API용 (선택 — 1.1 참조)
  # admin_client_id / admin_client_secret — Secret으로 주입

authz:
  super_admin_role: "rag-super-admin"  # 1.2의 그룹명

smtp:                                   # 초대 메일 발송
  host: "<smtp 호스트>"
  port: 587
  username: "<계정>"                    # Secret으로 주입
  password: "<비밀번호>"                # Secret으로 주입
  from_address: "noreply@<도메인>"

security:
  fernet_key: "<Fernet 키>"             # 커넥터 토큰 암호화용 — Secret으로 주입
```

**SMTP는 반드시 실 발송 가능한 서버를 사용한다.** 평가 환경의 mailpit은 메일을 가두는
개발 도구로, 운영에서 사용하면 초대 메일이 사용자에게 도달하지 않는다.

## 3. 관리 콘솔 ENT 모드 활성화

콘솔은 단일 빌드로 배포 시 환경값만으로 모드가 결정된다. admin-ui ConfigMap(또는
`public/env.js`)에 OIDC 값을 채우면 ENT 모드가 켜진다.

```
API_URL=<rag-ent-api 주소>
OIDC_ISSUER=https://<keycloak 도메인>/realms/<realm>
OIDC_CLIENT_ID=rag        # 1.1의 SPA 클라이언트 ID — 값이 있으면 ENT 모드
```

동작: 미인증 접속 시 Keycloak 로그인으로 리다이렉트, 토큰은 브라우저 메모리에만 보관
(새로고침 시 재로그인 — 의도된 보안 설계).

## 4. RBAC 활성화 절차

설치 직후 RBAC는 꺼져 있을 수 있다 (`kb_authz_enabled=false` — 인증만 요구, 역할 체크
없음). 단계적 도입이 가능하다.

1. **super-admin 계정으로 로그인** — 콘솔 접속 또는 토큰 발급.
2. **현재 상태 확인**: `GET /api/me` 응답의 `kb_authz_enabled` (또는 콘솔 헤더의 RBAC 배지).
3. **활성화**: 콘솔 Settings 화면의 토글(확인 모달), 또는:

   ```bash
   curl -X PATCH https://<api>/api/admin/config \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"kb_authz_enabled": true}'
   ```

4. **자동 백필**: 활성화 시점에 owner가 없는 모든 KB에 요청한 super-admin이 owner로
   자동 등록된다. 이후 콘솔 Access Management에서 실제 담당자에게 멤버 등록 → 소유권
   이전으로 넘긴다.

역할별 권한 요약은 [reference/01-api-guide.md 1장](../reference/01-api-guide.md#1-인증-및-권한-enterprise-전용)
참조.

## 5. 연동 애플리케이션의 토큰 전달

기존 rag-api API 경로가 그대로 유지되므로, 연동 앱은 사용자 토큰을 `Authorization:
Bearer`로 전달하기만 하면 권한 필터가 적용된다.

```
# 검색 — 호출자가 접근 가능한 KB만 대상이 됨
POST /api/search  (Authorization: Bearer <사용자 JWT>)

# MCP — 동일 (예: LibreChat 등 MCP 클라이언트 설정)
"rag": {
  "type": "streamable-http",
  "url": "https://<api>/mcp",
  "headers": { "Authorization": "Bearer <사용자 JWT>" }
}
```

## 6. 구성 검증 체크리스트

| # | 확인 | 기대 결과 |
|---|------|-----------|
| 1 | 토큰 없이 `GET /api/kb` | 401 |
| 2 | 일반 사용자 토큰으로 `GET /api/me` | 본인 정보 + `is_super_admin: false` |
| 3 | super-admin 토큰으로 `GET /api/admin/config` | 200 (일반 사용자는 403) |
| 4 | KB 생성 후 `GET /api/kb` | 생성 KB의 `my_role: "owner"` |
| 5 | 멤버 미등록 사용자 토큰으로 해당 KB 문서 업로드 | 403 |
| 6 | 미가입 이메일로 멤버 초대 | 초대 메일 실제 수신 (SMTP 검증) |
| 7 | 콘솔 로그아웃 → 재접속 | Keycloak 로그인 화면 |

전체 스모크 테스트는 [05-verification.md](05-verification.md) 참조.
