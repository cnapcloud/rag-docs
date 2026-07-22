---
sidebar_position: 6
---

# 접근 제어

조직 내 여러 부서가 KB를 공유하는 환경에서는 로그인 여부만으로 접근을 통제할 수 없다 —
인증된 사용자라 해서 모든 KB의 문서를 볼 수 있어야 하는 것은 아니며, 이 통제는 REST API
뿐 아니라 검색 결과와 MCP 툴 호출 경로에서도 동일하게 적용되어야 한다. Enterprise 배포는
이를 위해 OIDC(Keycloak) 인증에 KB 단위 역할(RBAC)을 결합한다. 인증과 권한이 요청 하나
안에서 어떻게 이어지는지, 그리고 그 역할이 REST·검색·MCP 전체에 일관되게 적용되는 방식을
다룬다.

이 구조는 챗 서비스 연동에도 그대로 얹힌다. 예를 들어 LibreChat이 rag-ent-api와 같은
Keycloak realm을 공유하면, 로그인한 사용자의 액세스 토큰을 그대로 MCP 요청에 실어 보낼 수
있다 — 검색은 항상 "지금 질문한 사용자"가 접근 가능한 KB로 제한되므로, 같은 챗봇을 여러
사용자가 함께 쓰더라도 별도 구현 없이 KB 단위로 지식 검색 범위를 통제할 수 있다.

---

## 인증 → 권한 경로

```
Keycloak (OIDC IdP)
   │  user logs in, issues signed JWT (RS256)
   ▼
client ──Authorization: Bearer <JWT>──▶ rag-ent-api
                                            │
                                            ▼
                                       OIDCMiddleware
                                            │  fetch Keycloak JWKS, verify signature + issuer
                                            │  (+ audience, if oidc.audience is configured)
                                            ▼
                                      invalid / expired ──▶ 401
                                            │  valid
                                            ▼
                                      CurrentUser
                                        user_id, email,
                                        is_super_admin  (JWT "groups" claim contains
                                                          authz.super_admin_role)
                                            │
                                            ▼
                                KB-scoped endpoint (kb router / require_kb_role)
                                            │  is_super_admin? ──▶ owner rank, skip lookup
                                            │  아니면 membership 조회 (Redis 캐시)
                                            ▼
                                has_role(actual_role, required_role)
                                            │  rank(actual) >= rank(required)?
                               ┌────────────┴────────────┐
                             true                       false
                               │                         │
                               ▼                         ▼
                            proceed                403 Forbidden
```

인증(JWT 검증)과 권한(KB 역할 검사)은 같은 요청 안에서 순서대로 일어나는 별개의 단계다 —
JWT가 유효해도 KB 역할이 부족하면 403이고, KB 역할이 있어도 JWT가 없으면 애초에
`OIDCMiddleware`에서 401로 끝난다.

## 역할 계층

| 역할 | 순위(rank) | 가능한 작업 |
|------|-----------|-------------|
| `viewer` | 1 | 조회 |
| `editor` | 2 | 문서 업로드·삭제·재인덱스 |
| `admin` | 3 | KB 메타데이터 수정(이름/설명/태그/visibility)·멤버 관리 |
| `owner` | 4 | KB 삭제·소유권 이전·인제스트/청킹/dedup 설정 오버라이드 |

역할 검사는 정확히 일치가 아니라 순위 비교다(`ROLE_RANK`, `has_role()`). `admin`은
`editor`가 할 수 있는 모든 작업도 할 수 있다 — 상위 역할이 하위 역할의 권한을 포함한다.

이 role이 REST의 각 리소스·엔드포인트에 실제로 어떤 문턱값으로 걸리는지, 그리고 admin과
owner가 왜 갈리는지는 [리소스별 권한 강제](resource-authorization.md)에서 다룬다.

## REST · 검색 · MCP에 동일하게 적용된다

세 경로 모두 같은 판단 로직을 공유한다.

- **REST** — [아키텍처](architecture.md)에서 다룬 것처럼 rag-ent-api는 rag-api의 `kb` 라우터를
  `my_role`을 주입하는 버전으로 교체하고, 나머지 라우터는 `require_kb_role`/
  `require_connector_role` 의존성으로 감싼다.
- **검색** — 질의에 포함된 `kb_ids`가 호출자의 접근 가능한 KB 목록과 교집합으로
  필터링된다(`get_accessible_kb_ids`). 권한 없는 KB가 섞여 있어도 오류 없이 조용히
  제외된다.
- **MCP** — 같은 `CurrentUser`·역할 판단 경로를 그대로 사용한다. MCP 클라이언트가
  전달하는 토큰도 REST와 동일하게 `OIDCMiddleware`를 통과한다.

## 공개 KB와 슈퍼관리자

- **공개(public) KB** — `is_kb_public()`이 true면 접근 가능 KB 목록에 무조건 포함된다.
  멤버십 등록 없이 모든 인증된 사용자가 조회할 수 있다(전사 공지·규정 KB 용도).
- **슈퍼관리자** — DB 조회가 아니라 **JWT의 `groups` claim**으로 판정된다. `groups`에
  `authz.super_admin_role`(기본 그룹명)이 포함되어 있으면 모든 KB에 대해 `owner` 순위로
  취급되고, 멤버십 조회 자체를 건너뛴다.

## kb_authz_enabled 토글

설치 직후 `kb_authz_enabled`는 꺼져 있을 수 있다 — 이 경우 인증만 요구하고 역할 검사는
하지 않는다. 켜는 순간(`false → true`) owner가 없는 모든 KB에 요청한 슈퍼관리자가 자동으로
owner로 등록된다(`set_authz_enabled`의 backfill 로직) — 단계적 도입을 위한 설계다.

## 캐싱

접근 가능 KB 목록과 공개 KB 목록은 매 요청마다 PostgreSQL을 조회하지 않고 Redis에
캐시된다(`get_accessible_cache`, `get_public_kb_cache`). 멤버십이 바뀌면 해당 캐시가
무효화된다(`invalidate_role_cache`) — 캐시 미스 시에만 DB를 다시 조회한다.
