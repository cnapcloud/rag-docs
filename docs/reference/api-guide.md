---
sidebar_position: 1
title: API 가이드
---

# API Guide

KB 생성부터 문서 업로드, 검색, 커넥터 연동까지 RAG Platform이 제공하는 전체 REST
엔드포인트를 다룬다. 엔드포인트별로 실제 호출 가능한 curl 예제와 응답 형식을 함께 실어,
직접 붙여넣어 바로 호출해볼 수 있게 구성했다. 개념적인 설명보다 "지금 무엇을 호출해야
하는가"에 답하는 것을 목표로 한다.

Base URL: `http://localhost:8000`

대화형 API 문서 (Swagger UI): `http://localhost:8000/docs`

---

## 1. 인증 및 권한 [ENT]

인증 및 권한 관리는 Enterprise에서 제공하는 기능으로 Swagger UI(`/docs`)도 `/health`, `/ready`를
제외한 모든 경로에 `BearerAuth` 스킴이 자동 부여되어 Authorize 버튼으로 토큰을 넣고 테스트할 수 있다.

사용자별 요청 제한도 함께 적용된다 — 아래 어떤 엔드포인트든 한도를 초과하면 `Retry-After`
헤더와 함께 HTTP 429를 반환할 수 있다. 규칙·응답 형식은
[사용자별 요청 제한](../guides/rag-ent/rate-limiting.md) 참고.

### 1.1 인증 (Authentication)

모든 요청은 `Authorization: Bearer <JWT>` 헤더가 필요하다 (`/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json` 제외). 토큰은 Keycloak이 발급하는 OIDC ID 토큰/액세스 토큰이며, Enterprise API 자체에는 로그인 엔드포인트가 없다 — Keycloak의 표준 토큰 엔드포인트를 직접 사용한다.

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/kb
```

토큰 검증은 Keycloak JWKS(RS256)로 서명·`exp`·`iss`·`aud`를 확인한다.

### 1.2 권한 (Authorization)

JWT의 `groups` claim에 super-admin 그룹명(설정 키 `authz.super_admin_role`, 기본값 `rag-super-admin`)이 포함되어 있으면 모든 KB에 대해 owner 권한으로 동작한다.

#### KB 역할 (낮은 순 → 높은 순)

| 역할 | 설명 |
|------|------|
| `viewer` | 조회만 가능 |
| `editor` | 문서 업로드/삭제/재인덱싱 가능 |
| `admin` | KB 설정 변경, 멤버 관리 가능 |
| `owner` | KB 삭제, 소유권 이전 가능 (KB당 1명) |

super-admin은 모든 KB에서 owner로 취급된다. `kb_authz_enabled`가 `false`(6.4절 시스템 설정 참고 — `settings.yaml` 키가 아니라 런타임에 토글하는 시스템 설정값)이면 역할 체크 자체가 스킵되고 인증만 요구한다.

Keycloak 클라이언트·그룹 설정, `oidc`/`authz` 섹션의 상세 필드는 [설정](configuration.md#18-oidc-ent)과
[SSO·인증 설정](../guides/rag-ent/sso-and-auth-setup.md)에서 다룬다.

---

## 2. 상태 확인

```bash
# 서버 생존 여부
curl http://localhost:8000/health

# 인프라 헬스체크 (Qdrant / Redis / S3 / Ollama)
curl http://localhost:8000/ready
```

---

## 3. 지식베이스 (KB)

### KB 목록 조회

```bash
curl http://localhost:8000/api/kb
```

응답:

```json
{
  "knowledge_bases": [
    {
      "kb_id": "kb-99",
      "kb_name": "지식베이스 99",
      "description": "첫 번째 지식베이스입니다.",
      "tags": [],
      "status": "active",
      "created_at": "2026-06-19T14:30:00+09:00",
      "updated_at": "2026-06-19T14:30:00+09:00"
    }
  ]
}
```

### KB 단건 조회

```bash
curl http://localhost:8000/api/kb/kb-99
```

존재하지 않는 KB 조회 시 HTTP 404 반환.

### KB 생성

```bash
curl -X POST http://localhost:8000/api/kb \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "kb-99",
    "kb_name": "지식베이스 99",
    "description": "첫 번째 지식베이스입니다.",
    "tags": ["tag1", "tag2"]
  }'
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `kb_id` | 필수 | KB 식별자 (중복 불가) |
| `kb_name` | 선택 | 표시 이름 (기본값: `""`) |
| `description` | 선택 | 설명 |
| `tags` | 선택 | 태그 목록 (기본값: `[]`) |

응답 (HTTP 201):

```json
{ "kb_id": "kb-99", "status": "created" }
```

이미 존재하는 `kb_id`로 생성 시 HTTP 409 반환.

### KB 수정

`name`, `description`, `tags` 중 전달한 필드만 업데이트합니다 (PATCH 의미론).

```bash
curl -X PATCH http://localhost:8000/api/kb/kb-99 \
  -H "Content-Type: application/json" \
  -d '{
    "kb_name": "새 이름",
    "description": "수정된 설명",
    "tags": ["tag1", "tag3"]
  }'
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `kb_name` | 선택 | 표시 이름 |
| `description` | 선택 | 설명 |
| `tags` | 선택 | 태그 목록 (전체 교체) |

응답 (HTTP 200):

```json
{ "kb_id": "kb-99", "status": "updated" }
```

존재하지 않는 KB 수정 시 HTTP 404 반환.

### KB 삭제

```bash
curl -X DELETE http://localhost:8000/api/kb/kb-99
```

Qdrant 컬렉션 → S3 오브젝트 → Postgres 메타데이터 순으로 삭제. 문서 레코드는 cascade 삭제.

응답 (HTTP 200):

```json
{ "kb_id": "kb-99", "status": "deleted", "s3_objects_deleted": 7 }
```

존재하지 않는 KB 삭제 시 HTTP 404 반환.

### KB API 확장 [ENT]

위 KB API 전체에 인증 토큰과 아래 최소 역할이 추가로 걸리고, 경로는 동일하지만 응답에 `my_role` 필드가 추가되며 KB 생성자가 자동으로 owner가 된다.

| 메서드 | 경로 | 최소 역할 |
|--------|------|-----------|
| GET | `/api/kb` | 인증만 (본인이 role을 가진 KB만 반환, super-admin은 전체) |
| GET | `/api/kb/{kb_id}` | viewer |
| POST | `/api/kb` | 인증만 (생성자가 자동으로 owner) |
| PATCH | `/api/kb/{kb_id}` | admin |
| DELETE | `/api/kb/{kb_id}` | owner |

응답 예시 (`kb_authz_enabled=true`인 경우 `my_role` 포함):

```json
{ "knowledge_bases": [{ "kb_id": "kb-99", "kb_name": "지식베이스 99", "my_role": "admin", "status": "active" }] }
```

또한 `visibility`(`"private"`/`"public"`, 기본 `"private"`)는 Enterprise가 추가한 필드로 Core 스키마엔 없다 — `POST`(생성 시점) / `PATCH`(기존 KB 전환) 둘 다에서 받는다. 실제 적용 범위는 [공개 KB(Visibility)](../guides/rag-ent/kb-visibility.md) 참고.

### KB 설정 오버라이드

KB 단위로 인제스트 파이프라인 설정(`ingestion`/`chunking`/`dedup`)과 검색 설정 일부(`retrieval.auto_merge`)를 전역 `settings.yaml` 값과 다르게 오버라이드할 수 있다. 오버라이드는 KB별로 저장되며, 파이프라인/검색은 요청마다 전역값 위에 그 KB의 오버라이드를 병합한 유효 설정을 사용한다.

`retrieval` 섹션 중에서는 `auto_merge`(parent-child 자동 병합, [설정 §13 retrieval](configuration.md#13-retrieval))만 오버라이드 가능하다. `mode`/`top_k`/`hybrid.*`/`similarity.min_score`/`rerank.*`는 여러 KB를 한 번에 검색할 때 병합(RRF)·리랭크가 병합된 결과 전체에 대해 정확히 한 번만 적용되는 값이라 특정 KB 하나의 설정을 쓴다는 개념이 성립하지 않는다 — 전역 설정값 또는 검색 요청의 `options`([13장 검색](#13-검색))로만 바꿀 수 있다.

#### 유효 설정 조회

전역값과 KB 오버라이드를 병합한 현재 유효 설정을 반환한다. `ingestion`/`chunking`/`dedup`/`retrieval` 네 섹션만 반환하며, 인프라 자격증명 등 다른 설정 섹션은 노출되지 않는다. `retrieval`은 `auto_merge`만 이 KB의 오버라이드가 실제로 반영된 값이고, 나머지 필드는 항상 전역값 그대로 보여주는 참고용이다.

```bash
curl http://localhost:8000/api/kb/kb-01/settings
```

```json
{
  "ingestion": { "max_file_size_mb": 50, "min_content_chars": 200, "html_extraction_policy": "trafilatura", "...": "..." },
  "chunking": { "strategy": "recursive", "chunk_size": 512, "chunk_overlap": 64, "...": "..." },
  "dedup": { "enabled": true, "...": "..." },
  "retrieval": { "mode": "hybrid", "top_k": 5, "auto_merge": { "enabled": true, "merge_threshold": 0.6 }, "...": "..." }
}
```

존재하지 않는 KB 조회 시 HTTP 404 반환.

#### 오버라이드 가능 필드 스키마 조회

오버라이드 가능한 전체 dot-key 목록과 각 필드의 `type`(`bool`/`int`/`float`/`str`/`enum`), `enum` 허용값, `default`, `overridable`, `min`/`max`, `description`, 소속 그룹을 반환한다. 프론트엔드가 필드 목록을 하드코딩하지 않고 동적으로 폼을 그릴 때 사용한다.

```bash
curl http://localhost:8000/api/kb/kb-01/settings/schema
```

```json
{
  "schema": {
    "chunking.chunk_size": {
      "type": "int", "default": 512, "min": 64, "max": 4096,
      "overridable": true, "description": "청크 최대 문자 수", "group": "chunking"
    },
    "chunking.strategy": {
      "type": "enum", "enum": ["recursive", "semantic"], "default": "recursive",
      "overridable": true, "description": "청킹 전략", "group": "chunking"
    },
    "dedup.simhash.ngram": {
      "type": "int", "default": 3, "overridable": false,
      "description": "기존 문서 지문과 계산 방식이 달라져 재인덱싱 없이는 비교 불가능해짐", "group": "dedup"
    },
    "retrieval.auto_merge.enabled": {
      "type": "bool", "default": false, "overridable": true,
      "description": "Auto Merge Enabled", "group": "auto_merge"
    },
    "retrieval.hybrid.alpha": {
      "type": "float", "default": 0.5, "overridable": false,
      "description": "Alpha (Hybrid)", "group": "hybrid"
    }
  }
}
```

`ingestion.parser_plugins`, `dedup.simhash.ngram`/`num_bands`/`simhash_bits`, `dedup.minhash.user_words_path` 등 배포 타임에 고정되거나 기존 저장된 데이터와의 호환성 때문에 KB별로 바꿀 수 없는 필드는 `overridable: false`로 표시된다 — 이 필드를 오버라이드 저장 API에 보내면 명시적으로 거부된다(조용히 무시하지 않음). `retrieval.mode`/`top_k`/`hybrid.*`/`similarity.min_score`/`rerank.*`도 같은 `overridable: false`지만 이유는 다르다 — 배포 시점에 고정되는 값이라서가 아니라, 여러 KB를 한 요청으로 합쳐 검색할 때 병합·리랭크가 요청 전체에 대해 정확히 한 번만 일어나 "이 KB의 값"이라는 게 애초에 정의되지 않기 때문이다(`retrieval.auto_merge`만 예외).

이 스키마에 자체 확장 필드(`ingestion.image_captioning.*`, `ingestion.pdf_ocr_fallback.*`, `ingestion.table_layout.*`)도 함께 포함해 반환한다. [ENT]

#### 저장된 오버라이드 조회

이 KB에 실제로 저장된 오버라이드만(전역값과 병합하지 않은 원본) flat dict로 반환한다. 오버라이드가 없으면 `{}`.

```bash
curl http://localhost:8000/api/kb/kb-01/settings/overrides
```

```json
{ "overrides": { "chunking.chunk_size": 1024, "ingestion.max_file_size_mb": 100 } }
```

#### 오버라이드 저장 — 전체 교체 / 부분 upsert

```bash
# 전체 교체 — body에 없는 기존 키는 전역값으로 리셋
curl -X PUT http://localhost:8000/api/kb/kb-01/settings/overrides \
  -H "Content-Type: application/json" \
  -d '{"overrides": {"chunking.chunk_size": 1024, "ingestion.max_file_size_mb": 100}}'

# 부분 upsert — 지정한 키만 갱신/추가, 값이 null이면 그 키를 해제(전역값으로 리셋), 나머지 기존 키는 그대로 유지
curl -X PATCH http://localhost:8000/api/kb/kb-01/settings/overrides \
  -H "Content-Type: application/json" \
  -d '{"overrides": {"chunking.chunk_overlap": 128, "ingestion.max_file_size_mb": null}}'
```

응답 (HTTP 200): 저장 후 최종 오버라이드 dict.

```json
{ "kb_id": "kb-01", "overrides": { "chunking.chunk_size": 1024, "chunking.chunk_overlap": 128 } }
```

두 API 모두 저장 전 아래 순서로 검증하며, 위반 시 HTTP 422를 반환한다.

1. dot-key가 `ingestion.` / `chunking.` / `dedup.` / `retrieval.` 접두사로 시작하는지 (아니면 거부 — 인프라 자격증명 등 다른 설정 섹션 보호)
2. 실제 존재하는 필드 경로인지, 그리고 `overridable: false`로 표시된 필드가 아닌지
3. 값 자체가 필드의 타입/범위(`min`/`max`)/enum을 만족하는지

#### 오버라이드 전체 삭제

이 KB의 모든 오버라이드를 삭제해 전역 설정값으로 완전히 되돌린다.

```bash
curl -X DELETE http://localhost:8000/api/kb/kb-01/settings/overrides
```

응답 (HTTP 200): `{ "kb_id": "kb-01", "status": "overrides_cleared" }`

#### KB 설정 오버라이드 확장 [ENT]

| 메서드 | 경로 | 최소 역할 |
|--------|------|-----------|
| GET | `/api/kb/{kb_id}/settings` | viewer |
| GET | `/api/kb/{kb_id}/settings/schema` | viewer |
| GET | `/api/kb/{kb_id}/settings/overrides` | viewer |
| PUT | `/api/kb/{kb_id}/settings/overrides` | owner |
| PATCH | `/api/kb/{kb_id}/settings/overrides` | owner |
| DELETE | `/api/kb/{kb_id}/settings/overrides` | owner |

조회(GET)는 다른 KB 리소스와 동일하게 viewer부터 허용하지만, 오버라이드를 바꾸는 쓰기(PUT/PATCH/DELETE)는 파이프라인 동작 자체를 바꾸는 만큼 admin이 아니라 owner 이상만 가능하다.

---

## 4. KB 멤버십 관리 [ENT]

멤버 등록·초대의 판정 순서, 로그인 시 자동 활성화, SMTP 설정 등 배경은
[멤버십·초대·소유권 관리](../guides/rag-ent/membership-and-invites.md) 참고.

`GET /api/kb/{kb_id}/members`, `POST /api/kb/{kb_id}/members`, `PATCH /api/kb/{kb_id}/members/{user_id}`, `DELETE /api/kb/{kb_id}/members/{user_id}` — 모두 admin 이상.

### 멤버 목록 조회 (+ pending invite)

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/kb/kb-01/members
```

```json
{
  "members": [
    { "user_id": "u-123", "role": "owner", "granted_by": null, "granted_at": "2026-06-19T14:30:00",
      "email": "alice@example.com", "display_name": "Alice Kim" }
  ],
  "pending_invites": [
    { "invite_id": "inv-1", "kb_id": "kb-01", "email": "new@example.com", "role": "viewer",
      "granted_by": "u-123", "expires_at": "2026-06-26T14:30:00", "status": "pending" }
  ]
}
```

`email`/`display_name`은 사용자 프로필 캐시에서 채워진다 — 이 사용자가 초대/승인/로그인 중 한 번이라도 관측된 적이 없으면 둘 다 `null`이다 (진실의 원천이 아니라 표시용 캐시).

### 멤버 등록 (역할 부여 또는 이메일 초대)

가입된 사용자면 즉시 역할이 부여되고, 미가입 이메일이면 초대(invite)가 생성되어 로그인 시점에 자동 활성화된다. 어느 쪽인지는 서버가 Keycloak 조회 결과로 판단한다.

```bash
curl -X POST http://localhost:8000/api/kb/kb-01/members \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "role": "editor"}'
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `email` | 필수 | 대상 이메일 |
| `role` | 필수 | `admin` / `editor` / `viewer` (owner는 이 API로 부여 불가) |

응답 (가입된 사용자, HTTP 201): `{ "status": "granted", "user_id": "u-456", "role": "editor" }`

응답 (미가입 이메일, HTTP 201): `{ "status": "invited", "invite_id": "inv-2" }`

### 멤버 역할 변경

```bash
curl -X PATCH http://localhost:8000/api/kb/kb-01/members/u-456 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role": "admin"}'
```

owner의 역할은 이 API로 변경할 수 없다 (HTTP 403). 대상 멤버가 없으면 HTTP 404.

### 멤버 제거

```bash
curl -X DELETE http://localhost:8000/api/kb/kb-01/members/u-456 \
  -H "Authorization: Bearer $TOKEN"
```

- 본인 탈퇴는 role과 무관하게 항상 허용된다 (인증만 필요, admin 아니어도 됨).
- 타인을 제거하려면 admin 이상 필요.
- owner 제거는 super-admin만 가능하며, 제거 시 [5장 소유권 이전] 로직이 자동 실행된다 (admin이 있으면 가장 오래된 admin이 승격, 없으면 KB가 frozen 상태가 된다).

응답 (HTTP 200): `{ "kb_id": "kb-01", "user_id": "u-456", "status": "removed" }`

### 초대 취소

```bash
curl -X DELETE http://localhost:8000/api/kb/kb-01/invites/inv-2 \
  -H "Authorization: Bearer $TOKEN"
```

응답 (HTTP 200): `{ "invite_id": "inv-2", "status": "revoked" }`

---

## 5. KB 소유권 이전 [ENT]

`POST /api/kb/{kb_id}/transfer-owner` — owner 이상 (frozen KB는 super-admin만 통과, 이 경로가 곧 unfreeze 경로이다).

기존 owner는 admin으로 강등되고 지정한 사용자가 새 owner가 된다.

```bash
curl -X POST http://localhost:8000/api/kb/kb-01/transfer-owner \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"new_owner_user_id": "u-789"}'
```

응답 (HTTP 200): `{ "kb_id": "kb-01", "owner": "u-789" }`

**Frozen KB**: owner가 admin 없이 제거되면 KB가 frozen(쓰기 불가) 상태가 된다. 이 경우 super-admin이 `transfer-owner`를 호출하면 새 owner가 지정되고 KB가 `active`로 복구된다.

---

## 6. 사용자·시스템 관리 [ENT]

### 6.1 사용자 조회

`GET /api/users/lookup?email=` — 인증만 필요 (역할 제한 없음). 이메일로 Keycloak 사용자를 조회해 `user_id`를 얻는다.

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/users/lookup?email=user@example.com"
```

응답: `{ "found": true, "user_id": "u-456", "display_name": "Jane Doe" }`

Keycloak 연결 실패, 미설정, 대상 없음 등 모든 경우 예외 없이 `found: false`로 수렴한다.

### 6.2 내 정보

`GET /api/me` — 인증만 필요 (역할 제한 없음). 호출자 자신의 식별 정보와 전역 `kb_authz_enabled` 상태를 함께 반환한다.

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/me
```

```json
{
  "user_id": "u-123",
  "email": "alice@example.com",
  "preferred_username": "alice",
  "is_super_admin": false,
  "kb_authz_enabled": true
}
```

### 6.3 사용자 삭제 (Deprovisioning)

`DELETE /api/users/{user_id}`, `DELETE /api/users?email=` — super-admin 전용.

특정 사용자를 시스템에서 전역으로 제거한다. 대상의 모든 KB 멤버십을 삭제하고, 대상이 owner였던 KB는 소유권 이전과 동일한 승계 로직이 자동 실행되며, 사용자 프로필 캐시 행도 삭제한다.

```bash
# user_id로 삭제
curl -X DELETE http://localhost:8000/api/users/u-456 \
  -H "Authorization: Bearer $TOKEN"

# 이메일로 삭제
curl -X DELETE "http://localhost:8000/api/users?email=user@example.com" \
  -H "Authorization: Bearer $TOKEN"
```

응답 (HTTP 200): `{ "user_id": "u-456", "status": "removed", "kb_ids": ["kb-01", "kb-02"] }`

`kb_ids`는 이번 호출로 멤버십이 제거된 KB 목록이다 — 이 중 대상이 owner였고 다른 admin이 없던 KB는 함께 frozen 처리됐을 수 있다.

제약 사항:

- **자기 자신은 삭제 불가**: 대상이 호출자 본인과 같으면 HTTP 403.
- 이메일이 조회되지 않으면 HTTP 404.
- 호출자가 super-admin이 아니면 HTTP 403.

`is_super_admin`은 저장된 값이 아니라 Keycloak JWT의 `groups`/realm role 클레임에서 매 요청 계산된다 — 이 API로 그 권한 자체를 박탈할 수는 없다. 실제 super-admin 권한 박탈은 Keycloak의 realm role/group에서 직접 처리해야 한다.

### 6.4 시스템 설정

`GET /api/admin/config`, `PATCH /api/admin/config` — super-admin 전용. 현재 `kb_authz_enabled` 플래그 하나만 노출한다 (RBAC 기능 전체 on/off 스위치).

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/config

curl -X PATCH http://localhost:8000/api/admin/config \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"kb_authz_enabled": true}'
```

응답: `{ "kb_authz_enabled": true }`

`false` → `true`로 전환하면 owner가 없는 모든 KB에 대해 요청한 super-admin이 owner로 자동 등록된다 (backfill).

---

## 7. 문서 인덱싱

PDF, Word(docx), 텍스트(txt), 마크다운(md), 한글(hwp), HTML(html/htm), reStructuredText(rst) 형식을 지원합니다.

```bash
# 단일 파일 업로드
curl -X POST http://localhost:8000/api/kb/kb-01/docs/upload \
  -F "file=@./data/doc.pdf"

# 복수 파일 업로드
curl -X POST http://localhost:8000/api/kb/kb-01/docs/upload/batch \
  -F "files=@./data/a.pdf" \
  -F "files=@./data/b.pdf"

# KB 전체 문서 목록 (기본: 1페이지, 20개, updated_at 내림차순)
curl http://localhost:8000/api/kb/kb-01/docs

# 페이지네이션
curl "http://localhost:8000/api/kb/kb-01/docs?page=2&page_size=50"

# 상태 필터
curl "http://localhost:8000/api/kb/kb-01/docs?status=failed"

# source 부분 문자열 검색 (대소문자 무시)
curl "http://localhost:8000/api/kb/kb-01/docs?search=report"

# 정렬 (sort_by: updated_at | created_at | source | chunk_count | file_size)
curl "http://localhost:8000/api/kb/kb-01/docs?sort_by=source&sort_order=asc"

# 단일 문서 인덱싱 상태 확인 ({doc_id}는 업로드 응답의 doc_id)
curl http://localhost:8000/api/kb/kb-01/docs/{doc_id}/status

# 원본 파일 다운로드 (S3에서 스트리밍)
curl -OJ http://localhost:8000/api/kb/kb-01/docs/{doc_id}/download

# 문서 삭제 (벡터 + 메타데이터 + S3 파일, 비동기)
curl -X DELETE http://localhost:8000/api/kb/kb-01/docs/{doc_id}
```

### 단일 업로드 응답 (HTTP 202)

```json
{
  "doc_id": "b59168c41e5e4a0d",
  "source": "report.pdf",
  "etag": "d41d8cd98f00b204e9800998ecf8427e",
  "status_url": "/api/kb/kb-01/docs/b59168c41e5e4a0d/status"
}
```

`doc_id`는 이후 상태 확인, 삭제, 재인덱싱, 복구, 다운로드 요청에 사용합니다.

**동일 파일명 재업로드**: 같은 KB에 같은 파일명을 다시 업로드하면 기존 `doc_id`를 재사용하고 새 내용으로 재인덱싱됩니다. 커넥터 문서의 경우 `source_uri`가 같으면 동일하게 기존 `doc_id`를 재사용합니다. 어느 경우든 문서가 현재 처리 중인 경우(`pending`, `uploading`, `running`, `deleting`) HTTP 409를 반환합니다.

### 배치 업로드 응답 (HTTP 202)

파일별 결과를 `results` 배열로 반환합니다. 일부 파일이 실패해도 나머지는 처리됩니다.

```json
{
  "results": [
    { "doc_id": "b59168c41e5e4a0d", "source": "a.pdf", "etag": "d41d8cd98f00b204e9800998ecf8427e",
      "status_url": "/api/kb/kb-01/docs/b59168c41e5e4a0d/status" },
    { "title": "b.xyz", "error": "Unsupported file format: .xyz", "status": "error" }
  ]
}
```

### 문서 삭제 응답 (HTTP 202)

삭제는 비동기로 처리됩니다. 응답 반환 후 백그라운드에서 Qdrant 청크 → S3 파일 → Postgres 행 순으로 삭제합니다.

```json
{ "kb_id": "kb-01", "doc_id": "b59168c41e5e4a0d", "status": "pending" }
```

| 응답 코드 | 조건 |
|-----------|------|
| 202 | 삭제 큐에 등록됨 |
| 404 | 문서 없음 |
| 409 | `status=running` (파이프라인 처리 중) 또는 `status=deleting` (이미 삭제 진행 중) |

### 문서 상태값

| 상태 | 설명 |
|------|------|
| `uploading` | API 업로드 진행 중 |
| `fetching` | 커넥터가 원본 소스에서 콘텐츠 수집 중 |
| `pending` | 파이프라인 큐 대기 중 |
| `running` | 파이프라인 처리 중 |
| `indexed` | 인덱싱 완료 |
| `failed` | 처리 실패 (`last_error` 필드에 사유) |
| `deleting` | 삭제 진행 중 |
| `deleted` | 삭제 완료 (행은 보존, 검색에서 제외) |

### 문서 API 확장 [ENT]

`/health`, `/ready`를 제외한 위 문서/커넥터 API는 모두 인증 토큰이 필요하며, 엔드포인트별로 아래 최소 역할이 추가로 요구된다.

| 경로 | 메서드 | 최소 역할 |
|------|--------|-----------|
| `/api/kb/{kb_id}/docs/upload`, `/upload/batch` | POST | editor |
| `/api/kb/{kb_id}/docs` | GET | viewer |
| `/api/kb/{kb_id}/docs/status` | GET | viewer |
| `/api/kb/{kb_id}/docs/{doc_id}/status` | GET | viewer |
| `/api/kb/{kb_id}/docs/{doc_id}/download` | GET | viewer |
| `/api/kb/{kb_id}/docs/{doc_id}` | DELETE | editor |
| `/api/kb/{kb_id}/reindex`, `/docs/{doc_id}/reindex` | POST | editor |
| `/api/kb/{kb_id}/docs/{doc_id}/fail`, `/recover` | POST | editor |
| `/api/docs` (전체 KB 통합 조회) | GET | super-admin |
| `/api/docs/status` (전체 KB 집계) | GET | super-admin |
| `/api/connectors` 이하 전체 | — | admin 이상 |

공통 규칙:

- KB가 frozen 상태(owner 없음)이면 viewer를 초과하는 모든 쓰기 요청은 HTTP 403.
- 요청한 KB에 대한 역할이 없으면 HTTP 403, KB 자체가 없으면 HTTP 404.
- `kb_authz_enabled=false`이면 위 역할 요구사항이 모두 스킵되고 인증(토큰 유효성)만 검사한다.

---

## 8. 재인덱싱 / 복구

ETag가 동일하면 재인덱싱을 건너뜁니다. `force=true`로 강제 재처리합니다.

```bash
# KB 전체 재인덱싱 (변경된 파일만)
curl -X POST http://localhost:8000/api/kb/kb-01/reindex

# KB 전체 강제 재인덱싱
curl -X POST "http://localhost:8000/api/kb/kb-01/reindex?force=true"

# 단일 문서 재인덱싱
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/{doc_id}/reindex"

# 단일 문서 강제 재인덱싱 (failed 상태 등)
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/{doc_id}/reindex?force=true"

# stuck 문서 복구 — status=running 인 경우에만 사용
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/{doc_id}/recover"

# 문서 강제 실패 처리 — uploading / pending / running / deleting 상태에서 사용
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/{doc_id}/fail"

# 실패 사유 지정
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/{doc_id}/fail?reason=Manually+canceled"
```

### 응답 형식

**KB 전체 재인덱싱 (HTTP 202)**

```json
{ "kb_id": "kb-01", "queued": 5, "skipped": 12 }
```

ETag가 변경된 문서만 큐에 등록합니다. `force=true`이면 모두 큐에 등록합니다.

**단일 문서 재인덱싱 (HTTP 202)**

```json
{ "kb_id": "kb-01", "doc_id": "b59168c41e5e4a0d", "queued": 1, "skipped": 0 }
```

ETag가 동일하면 `queued: 0, skipped: 1`을 반환합니다. `force=true`이면 항상 `queued: 1`입니다.

**문서 복구 (HTTP 202)**

```json
{ "kb_id": "kb-01", "doc_id": "b59168c41e5e4a0d", "queued": true }
```

`status=running`이 아닌 문서에 복구를 요청하면 HTTP 409 반환.

**강제 실패 처리 (HTTP 200)**

```json
{ "kb_id": "kb-01", "doc_id": "b59168c41e5e4a0d", "status": "failed" }
```

`uploading`, `pending`, `running`, `deleting` 외 상태에서 요청하면 HTTP 409 반환.

queue_worker 모드에서 `running` / `deleting` 문서에 적용하면 asyncio 태스크를 실제로 종료할 수 없으므로 응답에 `warning` 필드가 추가됩니다.

```json
{
  "kb_id": "kb-01",
  "doc_id": "b59168c41e5e4a0d",
  "status": "failed",
  "warning": "Status set to failed, but the background task is still running and may overwrite this status (queue_worker mode has no terminate support)."
}
```

---

## 9. 문서 삭제

`DELETE /api/kb/{kb_id}/docs/{doc_id}`

```bash
# Soft delete (indexed 문서 — S3 파일 보존, 검색에서 제외)
curl -X DELETE "http://localhost:8000/api/kb/kb-01/docs/{doc_id}"

# Hard delete (S3 파일 포함 완전 삭제)
curl -X DELETE "http://localhost:8000/api/kb/kb-01/docs/{doc_id}?force=true"
```

| 상태 | `force=false` | `force=true` |
|------|---------------|--------------|
| `indexed` | soft delete — DB row `status=deleted`, S3 유지 | hard delete |
| 그 외 (`failed`, `pending` 등) | hard delete | hard delete |

- `running` 상태 문서는 삭제 요청 불가 — HTTP 409. 먼저 force-fail 후 삭제.
- Soft delete된 문서는 `status=deleted` 필터로 목록 조회 가능. 검색에는 포함되지 않음.
- Hard delete는 Qdrant 청크, S3 파일, DB row를 모두 제거.

**응답 (HTTP 202)**

```json
{ "kb_id": "kb-01", "doc_id": "b59168c41e5e4a0d", "status": "pending" }
```

삭제는 비동기로 처리됩니다. 완료 여부는 문서 상태 조회(`GET .../docs/{doc_id}/status`)로 확인하거나, soft delete의 경우 `status=deleted`, hard delete의 경우 404로 확인합니다.

---

## 10. 문서 목록 조회

`GET /api/kb/{kb_id}/docs`

### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `page` | int | 1 | 페이지 번호 (1-based) |
| `page_size` | int | 20 | 페이지당 항목 수 (최대 100, 초과 시 자동 클램핑) |
| `status` | str | — | 상태 필터: `uploading`, `fetching`, `pending`, `running`, `indexed`, `failed`, `deleting`, `deleted` |
| `source_type` | str | — | 출처 유형 필터: `s3` (직접 업로드), `web`, `confluence`, `github` |
| `search` | str | — | `source` 부분 문자열 검색 (대소문자 무시) |
| `sort_by` | str | `updated_at` | 정렬 기준: `updated_at`, `created_at`, `source`, `chunk_count`, `file_size` |
| `sort_order` | str | `desc` | 정렬 방향: `asc`, `desc` |

- `total`은 필터 적용 후 전체 건수 (전체 문서 수가 아님).
- 범위를 벗어난 `page`는 `items: []`를 반환 (404 아님).
- `chunk_count`, `file_size` 정렬 시 NULL 값은 방향에 관계없이 항상 마지막.
- `status=deleted` 필터 없이는 삭제된 문서가 응답에 포함되지 않음.

### 요청 예시

```bash
# 2페이지, 상태=indexed, "report" 검색, source 오름차순
curl "http://localhost:8000/api/kb/kb-01/docs?page=2&page_size=10&status=indexed&search=report&sort_by=title&sort_order=asc"
```

### 응답 예시

```json
{
  "items": [
    {
      "doc_id": "b59168c41e5e4a0d",
      "kb_id": "kb-01",
      "title": "report.pdf",
      "source_type": "s3",
      "source": "report.pdf",
      "storage_key": "kb-01/report.pdf",
      "connector_id": null,
      "status": "indexed",
      "doc_type": "pdf",
      "chunk_count": 42,
      "file_size": 1258291,
      "embedding_model": "ollama/nomic-embed-text",
      "last_error": null,
      "created_at": "2026-06-19T14:30:00+09:00",
      "updated_at": "2026-06-19T14:32:00+09:00"
    }
  ],
  "total": 87,
  "page": 1,
  "page_size": 20
}
```

### 전체 문서 목록 (KB 무관)

`GET /api/docs` — KB를 지정하지 않고 모든 KB의 문서를 통합 조회합니다.

쿼리 파라미터는 위 표와 동일하되, `source_type` 필터는 지원하지 않습니다. 응답 형식은 KB별 목록과 동일합니다 (`items`, `total`, `page`, `page_size`).

```bash
# 전체 문서 목록 (기본: 1페이지, 20개)
curl http://localhost:8000/api/docs

# 필터 예시
curl "http://localhost:8000/api/docs?status=failed&search=report&sort_by=updated_at"
```

---

## 11. 커넥터 (Connector)

커넥터는 외부 소스(웹 크롤러, Confluence, GitHub)에서 문서를 자동으로 수집해 KB에 인덱싱합니다.
파일 직접 업로드(7장)와 달리, 커넥터는 sync 트리거 시 소스를 순회하며 변경된 문서만 재인덱싱합니다.

`/api/connectors` 이하 전체 엔드포인트에 admin 이상 역할이 필요합니다 (7장 "문서 API 확장" 참고). [ENT]

### 커넥터 생성

```bash
curl -X POST http://localhost:8000/api/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "kb-01",
    "name": "Product Docs",
    "source_type": "web",
    "config": {
      "seed_urls": ["https://example.com/docs"],
      "depth": 2,
      "max_pages": 50
    },
    "sync_schedule": "0 2 * * *",
    "schedule_enabled": true
  }'
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `kb_id` | 필수 | 대상 KB (생성 후 변경 불가) |
| `name` | 필수 | 사용자 표시 이름 |
| `source_type` | 필수 | `web` / `confluence` / `github` (생성 후 변경 불가) |
| `config` | 필수 | 소스별 설정 (필수 항목은 아래 스키마 참조) |
| `sync_schedule` | 선택 | cron 표현식 (예: `"0 2 * * *"` = 매일 새벽 2시). 설정 후 **Dagster 컨테이너 재시작** 시 스케줄 자동 등록 |
| `schedule_enabled` | 선택 | 스케줄 자동 실행 여부 (기본값: `false`). PATCH로 변경 시 재시작 없이 즉시 반영 |

응답 (HTTP 201): 생성된 커넥터 전체 필드.

`connector_id`는 서버가 UUID로 자동 생성합니다. `kb_id`가 없으면 HTTP 404 반환.

#### source_type별 config 스키마

```json
// web
{
  "seed_urls": ["https://example.com/docs"],   // 필수
  "depth": 2,                                  // BFS 깊이 (기본값: 2)
  "include_patterns": ["*/docs/*", "*/guide/*"],  // 수집할 URL 패턴 (seed 스코프 내 추가 필터)
  "exclude_patterns": ["*/blog/*", "*.pdf"],      // 제외할 URL 패턴 (최우선 적용)
  "max_pages": 50,                             // 페이지 처리 상한 (기본값: 50)
  "request_timeout_sec": 30,                   // HTTP 타임아웃 (기본값: 30)
  "request_delay_ms": 100,                     // 요청 간 딜레이 ms (기본값: 100)

  // 인증 — 둘 다 설정된 경우 auth_headers 우선, 둘 다 없으면 인증 없이 요청
  "auth_headers": { "Authorization": "Bearer eyJ..." },  // Bearer 토큰 / API 키 등 커스텀 헤더
  "auth_basic": { "username": "user", "password": "pass" }  // HTTP Basic Auth
}

// confluence
{
  "base_url": "https://company.atlassian.net",  // Atlassian Cloud 또는 Server/Data Center URL
  "space_key": "DEV",                            // 수집할 스페이스 키 (필수)
  "auth_token_secret": "CONFLUENCE_TOKEN",       // 환경변수 키 이름 (선택, 공개 사이트는 생략)
  "exclude_labels": ["draft", "archived"],       // 이 레이블을 가진 페이지(+첨부파일) 제외
  "max_pages": 50,                               // sync 1회당 처리 페이지 상한 (기본값: 50)
  "max_attachment_mb": 10,                       // 첨부파일 최대 크기 MB (기본값: 10)
  "request_delay_ms": 100,                       // API 호출 간격 ms (기본값: 100)
  "request_timeout_sec": 30                      // HTTP 타임아웃 초 (기본값: 30)
}

// github
{
  "owner": "myorg",
  "repo": "docs",
  "branch": "main",
  "path_prefix": "docs/",
  "auth_token_secret": "GITHUB_TOKEN"
}
```

**web config 동작 규칙**

| 설정 | 기본값 | 동작 |
|------|--------|------|
| `seed_urls` | (필수) | 크롤 시작 URL 목록. 지정한 경로 하위만 수집 |
| `depth` | `2` | BFS 탐색 깊이. `0` = seed URL만 처리 |
| `max_pages` | `50` | sync 1회당 처리 페이지 상한. BFS queue도 `max_pages × 20`으로 상한 제한 |
| `include_patterns` | `[]` | 수집할 URL 패턴 (fnmatch). 예: `["*/guide/*"]` |
| `exclude_patterns` | `[]` | 제외할 URL 패턴 (fnmatch, 최우선). 예: `["*/blog/*", "*.pdf"]` |
| `request_delay_ms` | `100` | 페이지 요청 간 대기 시간(밀리초). 서버 부하 방지용 |
| `auth_headers` | `{}` | 모든 요청에 추가할 HTTP 헤더. Bearer 토큰(`Authorization: Bearer ...`) 또는 API 키(`X-API-Key: ...`) 등 |
| `auth_basic` | 없음 | HTTP Basic Auth. `auth_headers`가 설정되어 있으면 무시됨 |
| `skip_seed_pages` | `true` | seed URL 자체(depth 0)를 문서로 저장하지 않음. 목록/인덱스 페이지를 건너뛸 때 사용 |
| `min_content_chars` | `200` | trafilatura 본문 추출 결과가 이 값 미만인 페이지는 저장 제외. 네비게이션 전용 페이지 필터링에 활용 |

> **주의**: 포털 루트 URL처럼 수만 개 페이지를 보유한 사이트에 `include_patterns` 없이 `depth >= 2`를 설정하면 queue가 대량 누적될 수 있습니다. `include_patterns`로 경로를 명시하거나 `depth=1` + `max_pages` 조합으로 범위를 제한하세요.

**confluence config 동작 규칙**

| 설정 | 기본값 | 동작 |
|------|--------|------|
| `base_url` | (필수) | Cloud: `https://company.atlassian.net` / Server: `https://confluence.company.com` |
| `space_key` | (필수) | 수집할 Confluence 스페이스 키 (대소문자 구분) |
| `auth_token_secret` | `null` | 환경변수 키 이름. Cloud: `email:api_token` 형식 → Basic auth. Server: PAT → Bearer auth. 공개 사이트는 생략 가능 |
| `exclude_labels` | `[]` | 지정한 레이블을 가진 페이지와 해당 페이지의 첨부파일을 모두 건너뜀 |
| `max_pages` | `50` | sync 1회당 처리 페이지 상한. 초과 시 중단 |
| `max_attachment_mb` | `10` | 첨부파일 수집 크기 상한(MB). 초과 파일은 건너뜀 |
| `request_delay_ms` | `100` | API 호출 간 대기 시간(밀리초). Confluence 서버 부하 방지용 |
| `request_timeout_sec` | `30` | HTTP 타임아웃(초) |

**수집 대상**

- **페이지**: 스페이스 내 모든 페이지를 Confluence REST API로 열거. 각 페이지 본문(`body.view` HTML)을 `.html`로 스테이징.
- **첨부파일**: 각 페이지에 첨부된 파일 중 지원 포맷이고 크기가 `max_attachment_mb` 미만인 파일만 수집.

지원 첨부파일 포맷: `.pdf` `.docx` `.txt` `.md` `.html` `.htm` `.rst` `.hwp`

**github config 동작 규칙**

| 설정 | 기본값 | 동작 |
|------|--------|------|
| `owner` | (필수) | 레포지토리 소유자 (user 또는 org) |
| `repo` | (필수) | 레포지토리 이름 |
| `branch` | `"main"` | 수집할 브랜치 |
| `path_prefix` | `""` | 지정 시 해당 경로 하위 파일만 수집. 예: `"src/"` |
| `auth_token_secret` | `null` | 환경변수 키 이름. GitHub PAT → Bearer auth. 공개 레포는 생략 가능 |
| `max_files` | `200` | sync 1회당 수집 파일 수 상한. 초과 시 중단 |
| `max_file_size_mb` | `5` | 수집 파일 크기 상한(MB). 초과 파일은 건너뜀 |
| `request_delay_ms` | `100` | API 호출 간 대기 시간(밀리초). GitHub rate limit 방지용 |
| `request_timeout_sec` | `30` | HTTP 타임아웃(초) |

**수집 대상**

- 레포지토리의 recursive git tree에서 지원 확장자 파일만 수집. `path_prefix` 설정 시 해당 경로 하위로 범위 제한.
- 소스코드 파일(`.py` `.ts` `.js` `.go` 등)은 chunking 시 CodeSplitter(언어별 AST 분할) 자동 적용.

지원 포맷: `.py` `.ts` `.tsx` `.js` `.jsx` `.go` `.java` `.rs` `.cpp` `.cc` `.c` `.cs` `.rb` `.php` `.swift` `.kt` `.scala` `.sh` `.md` `.txt` `.rst`

**content_version과 증분 수집**

- **github**: 파일의 git blob SHA를 `content_version`으로 저장. 재sync 시 SHA가 동일하면 재인제스트를 건너뜁니다. `source` 형식: `github://{owner}/{repo}/{branch}/{file_path}`
- **confluence**: 페이지와 첨부파일 모두 Confluence 버전 번호를 `content_version`으로 저장. 재sync 시 버전이 동일하면 재인제스트를 건너뜁니다. 단, 페이지 버전이 변경 없더라도 첨부파일은 항상 순회합니다(첨부파일만 추가됐을 수 있으므로).

**Cloud vs Server 자동 감지**: `base_url`에 `.atlassian.net`이 포함되면 Cloud API 경로(`/wiki/rest/api`)를 사용하고, 그 외에는 Server/Data Center 경로(`/rest/api`)를 사용합니다.

`auth_token_secret`은 토큰 값이 아닌 **환경변수 키 이름**입니다. 실제 토큰은 DB에 저장되지 않으며 런타임에 환경변수에서 읽습니다. 퍼블릭 사이트/저장소는 생략 가능합니다.

### 커넥터 목록 조회

```bash
# 전체 목록
curl http://localhost:8000/api/connectors

# kb_id / source_type / status 필터
curl "http://localhost:8000/api/connectors?kb_id=kb-01&source_type=web&status=active"

# 이름 부분 검색 (대소문자 무시)
curl "http://localhost:8000/api/connectors?search=docs"

# 정렬 (sort_by: name | kb_id | source_type | status | last_synced_at | created_at | updated_at)
curl "http://localhost:8000/api/connectors?sort_by=name&sort_order=asc"
```

응답:

```json
{
  "items": [
    {
      "connector_id": "b59168c41e5e4a0d",
      "kb_id": "kb-01",
      "name": "Product Docs",
      "source_type": "web",
      "config": { "seed_urls": ["https://example.com/docs"], "depth": 2 },
      "sync_schedule": "0 2 * * *",
      "schedule_enabled": true,
      "sync_status": "idle",
      "sync_started_at": null,
      "last_synced_at": "2026-06-20T02:00:05+09:00",
      "status": "active",
      "last_error": null,
      "created_at": "2026-06-19T10:00:00+09:00",
      "updated_at": "2026-06-20T02:00:05+09:00"
    }
  ]
}
```

`last_error`는 마지막 sync 실패 메시지입니다(최대 500자) — 로그를 보지 않고도 실패 원인을 확인할 수 있습니다. `status=active`/`paused`로 수동 전환하거나 sync 재시도가 성공(abort 아님)하면 자동으로 클리어됩니다.

### 커넥터 단건 조회

```bash
curl http://localhost:8000/api/connectors/02ec3eccc6814577
```

### 커넥터 수정

`source_type`과 `kb_id`는 변경할 수 없습니다. `status`는 `active` / `paused`만 직접 설정 가능하며, `error`는 시스템이 자동으로 설정합니다.

```bash
curl -X PATCH http://localhost:8000/api/connectors/b59168c41e5e4a0d \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product Docs v2",
    "schedule_enabled": false
  }'
```

| 필드 | 설명 |
|------|------|
| `name` | 표시 이름 |
| `config` | 소스 설정 (전체 교체) |
| `sync_schedule` | cron 표현식 (`null`로 설정하면 스케줄 제거) |
| `schedule_enabled` | 스케줄 자동 실행 여부 |
| `status` | `active` 또는 `paused` |

응답 (HTTP 200): 수정된 커넥터 전체 필드.

### 커넥터 삭제

커넥터와 커넥터가 수집한 **모든 문서를 함께 삭제**합니다 (Qdrant 청크 + S3 파일 + Postgres 행). 즉시 202를 반환하고 백그라운드에서 실행됩니다.

```bash
curl -X DELETE http://localhost:8000/api/connectors/b59168c41e5e4a0d
```

응답 (HTTP 202): `{ "connector_id": "b59168c41e5e4a0d", "status": "deleting" }`

단, 커넥터를 통해 수집된 후 직접 업로드로 재업로드된 문서(`connector_id = NULL`)는 삭제되지 않습니다.

### 동기화 트리거

수동으로 동기화를 시작합니다. `sync_schedule`과 무관하게 항상 사용 가능합니다.

```bash
curl -X POST http://localhost:8000/api/connectors/b59168c41e5e4a0d/sync
```

응답 (HTTP 202): `{ "connector_id": "b59168c41e5e4a0d", "sync_status": "running" }`

| 응답 코드 | 조건 |
|-----------|------|
| 202 | 트리거 성공, 백그라운드 실행 중 |
| 404 | 커넥터 없음 |
| 409 | `status=paused` 또는 30분 이내 동기화 이미 진행 중 |

30분이 지났는데도 `sync_status=running`이면 이전 실행이 비정상 종료된 것으로 판단해 재트리거를 허용합니다.

### Pause / Resume

커넥터를 일시 중단하거나 재개합니다. `status=paused`이면 수동 트리거(`POST /sync`)와 자동 스케줄 모두 차단됩니다.

```bash
# Pause
curl -X PATCH http://localhost:8000/api/connectors/b59168c41e5e4a0d \
  -H "Content-Type: application/json" \
  -d '{"status": "paused"}'

# Resume
curl -X PATCH http://localhost:8000/api/connectors/b59168c41e5e4a0d \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

| `status` | 동작 |
|----------|------|
| `active` | 정상 운영. 수동/자동 sync 모두 허용 |
| `paused` | 전면 중단. 수동/자동 sync 모두 차단 (409 반환) |
| `error` | 시스템 자동 설정. sync 실패 시 기록되며 직접 설정 불가. 실패 메시지는 `last_error`에 기록. sync 재시도가 성공하면 `active`로 자동 복구되고 `last_error`도 클리어됨 (abort로 중단된 경우는 복구되지 않음) |

### 동기화 중단 (Abort)

진행 중인 sync를 즉시 중단합니다. 호출 즉시 `sync_status`가 `idle`로 전환되며, 다음 작업을 수행합니다.

- Redis 큐에서 이 커넥터 소속 `pending` 문서를 제거하고 `failed`로 표시
- `running` 상태 문서를 `failed`로 표시하고 Dagster run을 force-terminate
- 커넥터 sync 루프에 중단 신호를 전달해 새 페이지 요청을 막음

```bash
curl -X POST http://localhost:8000/api/connectors/b59168c41e5e4a0d/sync/abort
```

응답 (HTTP 202): `{ "connector_id": "b59168c41e5e4a0d", "status": "abort_requested" }`

| 응답 코드 | 조건 |
|-----------|------|
| 202 | 중단 요청 수락. `sync_status`는 즉시 `idle`로 전환됨 |
| 404 | 커넥터 없음 |
| 409 | `sync_status`가 `running`이 아님 |

### 동기화 상태 확인

```bash
curl http://localhost:8000/api/connectors/70779147cfc149de/sync/status
```

응답:

```json
{
  "connector_id": "b59168c41e5e4a0d",
  "status": "active",
  "sync_status": "idle",
  "sync_started_at": null,
  "last_synced_at": "2026-06-20T02:00:05+09:00",
  "last_error": null,
  "doc_counts": { "indexed": 142, "pending": 3, "failed": 1, "deleted": 5, "total": 151 }
}
```

`doc_counts.total`은 삭제된 문서 포함 전체 건수입니다.

| `sync_status` | 의미 |
|---------------|------|
| `idle` | 대기 중 (마지막 실행 완료 또는 한 번도 실행 안 됨) |
| `running` | 동기화 진행 중 |

### 스케줄 자동 동기화

`sync_schedule`에 cron 표현식을 설정하고 `schedule_enabled: true`로 두면, 지정한 시각에 Dagster Schedule이 `connector_sync_job`을 자동으로 실행합니다. 실행 흐름은 수동 트리거와 동일합니다.

```
Dagster Schedule (cron 도달)
  → connector_sync_job
    → connector_sync_op
      → WebConnector / ConfluenceConnector / GitHubConnector
        → 문서 fetch → S3 staging → ingest 큐 적재
          → ingest_job (validate → parse → chunk → embed → upsert → meta)
```

**동작 방식**

| 항목 | 동작 |
|------|------|
| 등록 시점 | **Dagster 컨테이너 재시작 시** `sync_schedule IS NOT NULL`인 커넥터를 DB에서 읽어 `connector_sync_job` 연결 스케줄로 자동 등록. `dagster api grpc` 방식은 런타임 reload를 지원하지 않으므로 신규 커넥터에 `sync_schedule`을 설정하면 재시작 필요 |
| `schedule_enabled` 토글 | PATCH로 변경하면 **재시작 없이 즉시 반영** — 다음 firing 시점에 DB를 재조회해 `false`면 실행 생략 |
| cron 표현식 변경 | `sync_schedule` 자체를 바꾸면 Dagster 컨테이너 재시작 필요 |
| 수동 트리거 | `POST /sync`는 `schedule_enabled` 값과 무관하게 항상 사용 가능하며 동일한 `connector_sync_job` 경로로 실행 |
| 중복 방지 | 같은 실행 구간에 중복 firing이 발생해도 Dagster가 `run_key`로 무시 |

**cron 표현식 형식** (5-field, UTC 기준)

```
분 시 일 월 요일
0 2 * * *    → 매일 02:00
0 */6 * * *  → 6시간마다
0 9 * * 1    → 매주 월요일 09:00
```

> **주의:** `sync_schedule` 값을 변경하면 Dagster 컨테이너를 재시작해야 새 스케줄이 반영된다. `schedule_enabled` 토글은 재시작 없이 즉시 반영된다.

**`status`와 `schedule_enabled`의 차이**

| 필드 | 역할 |
|------|------|
| `status: paused` | 수동 트리거(`POST /sync`)까지 차단 |
| `schedule_enabled: false` | 자동 스케줄만 비활성화, 수동 트리거는 허용 |

### 커넥터 문서 목록

이 커넥터가 수집한 문서 목록을 조회합니다. 쿼리 파라미터는 [10장 — 문서 목록 조회](#10-문서-목록-조회)와 동일합니다. 커넥터별 집계는 [12장 — 문서 상태 집계 조회](#12-문서-상태-집계-조회)의 커넥터별 집계 참고.

```bash
curl "http://localhost:8000/api/connectors/b59168c41e5e4a0d/docs"

# 필터 + 정렬 예시
curl "http://localhost:8000/api/connectors/b59168c41e5e4a0d/docs?status=failed&sort_by=updated_at"
```

응답 형식은 `GET /api/kb/{kb_id}/docs`와 동일합니다 (`items`, `total`, `page`, `page_size`).

### 웹 커넥터 수집 제외 대상

다음 페이지는 링크 탐색(BFS)에는 사용되지만 문서로 저장되지 않습니다.

| 제외 유형 | 조건 | 예시 |
|-----------|------|------|
| Seed 페이지 (depth 0) | `config.skip_seed_pages: true` (기본값) — seed URL 자체는 목록/인덱스 페이지로 간주 | `https://example.com/blog` |
| 페이지네이션 URL | 경로에 `/page/N` 포함, 또는 쿼리에 `page=N` / `p=N` 포함 | `/blog/page/2/`, `?page=3` |
| 콘텐츠 부족 페이지 | trafilatura 추출 결과가 `config.min_content_chars`(기본 200자) 미만 | 빈 페이지, 네비게이션 전용 페이지 |

> 제외된 페이지는 링크 발견 후 다음 depth 크롤링에 활용되므로, 해당 페이지에 연결된 실제 콘텐츠 페이지는 정상적으로 수집됩니다.

---

## 12. 문서 상태 집계 조회

처리 중인 문서가 있는지 확인하거나 전체 현황을 파악할 때 사용합니다.
개별 문서를 전부 조회하지 않고 상태별 카운트만 반환하므로 대량 문서 환경에서도 가볍습니다.

### 전체 KB 집계

```bash
curl http://localhost:8000/api/docs/status
```

응답:

```json
{
  "knowledge_bases": {
    "kb-01": { "doc_counts": { "indexed": 142, "pending": 0, "running": 0, "failed": 1, "deleted": 5, "total": 148 } },
    "kb-02": { "doc_counts": { "indexed": 0, "pending": 0, "running": 0, "failed": 0, "deleted": 0, "total": 0 } }
  }
}
```

### 특정 KB 집계

```bash
curl http://localhost:8000/api/kb/kb-01/docs/status
```

응답:

```json
{ "kb_id": "kb-01", "doc_counts": { "indexed": 142, "pending": 0, "running": 0, "failed": 1, "deleted": 5, "total": 148 } }
```

KB가 없으면 HTTP 404 반환.

### 커넥터별 집계

```bash
curl http://localhost:8000/api/connectors/{connector_id}/sync/status
```

응답:

```json
{
  "connector_id": "b59168c41e5e4a0d",
  "status": "active",
  "sync_status": "idle",
  "sync_started_at": null,
  "last_synced_at": "2026-06-20T02:00:05+09:00",
  "last_error": null,
  "doc_counts": { "indexed": 142, "pending": 0, "running": 0, "failed": 1, "deleted": 5, "total": 148 }
}
```

`doc_counts.total`은 삭제된 문서를 포함한 전체 건수입니다.

### 처리 완료 여부 확인 패턴

```bash
# pending + running 이 0 이면 모든 처리 완료
curl -s http://localhost:8000/api/kb/kb-01/docs/status | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)['doc_counts']
active = d['pending'] + d['running']
print('active' if active > 0 else 'done', f'(pending={d[\"pending\"]} running={d[\"running\"]})')
"
```

---

## 13. 검색

### hybrid 모드 (기본)

dense(의미) + sparse(키워드) 검색을 결합해 RRF로 재순위를 매깁니다.

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "검색어",
    "kb_ids": ["kb-01", "kb-02"],
    "options": {
      "mode": "hybrid",
      "top_k": 10,
      "hybrid": { "alpha": 0.5 },
      "rerank": { "enabled": true, "top_n": 5 }
    }
  }'
```

### similarity 모드

dense 벡터 코사인 유사도만 사용합니다. `min_score`로 낮은 유사도 결과를 걸러낼 수 있습니다.

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "검색어",
    "kb_ids": ["kb-01", "kb-02"],
    "options": {
      "mode": "similarity",
      "top_k": 10,
      "similarity": { "min_score": 0.7 },
      "rerank": { "enabled": true, "top_n": 5 }
    }
  }'
```

### 옵션 파라미터

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `mode` | settings | `"hybrid"` 또는 `"similarity"`. 생략 시 settings.retrieval.mode 사용 |
| `top_k` | settings | 최종 반환할 최대 청크 수 |
| `hybrid.alpha` | settings | 1.0 = Dense 100%, 0.0 = Sparse(키워드) 100%. hybrid 모드에서만 적용 |
| `similarity.min_score` | settings | 반환할 최소 코사인 유사도 (0.0~1.0). similarity 모드에서만 적용 |
| `rerank.enabled` | true | 리랭킹 활성화 여부 |
| `rerank.top_n` | settings | 리랭킹 후 반환할 결과 수 |

`auto_merge`(parent-child 자동 병합)는 이 `options`로 요청 단위 오버라이드를 할 수 없다 — 설정(전역 `settings.yaml` 또는 [KB 오버라이드](#kb-설정-오버라이드))로만 켜고 끈다.

### 응답 필드

```json
{
  "query": "검색어",
  "results": [
    {
      "chunk_id": "b59168c41e5e4a0d:1",
      "kb_id": "kb-01",
      "doc_id": "b59168c41e5e4a0d",
      "title": "report.pdf",
      "source_type": "s3",
      "source": "report.pdf",
      "doc_type": "pdf",
      "chunk_index": null,
      "page_num": 4,
      "page_label": "4",
      "text": "...",
      "score": 0.0164,
      "rerank_score": 0.91,
      "updated_at": "2026-06-19T14:32:00+09:00",
      "merged": true,
      "parent_chunk_id": "b59168c41e5e4a0d:0"
    }
  ],
  "meta": {
    "total_candidates": 42,
    "returned": 10,
    "search_mode": "hybrid",
    "score_threshold": 0.0,
    "reranked": true,
    "rerank_provider": "jina",
    "rerank_fallback": false,
    "latency_ms": 320
  }
}
```

| 필드 | 설명 |
|------|------|
| `merged` | `true`면 개별 청크가 아니라 parent-child 자동 병합(auto-merge)으로 만들어진 상위 텍스트다. `chunking.strategy="hierarchical"`로 인덱싱된 문서에서 `retrieval.auto_merge.enabled`가 켜져 있고, 같은 parent 아래 매칭된 child 비율이 `merge_threshold` 이상일 때 발생한다 — [설정 §11 chunking](configuration.md#11-chunking), [§13 retrieval](configuration.md#13-retrieval) 참고 |
| `chunk_index` | `merged=true`인 결과는 여러 leaf 청크를 합친 것이라 단일 시퀀스 위치가 없으므로 `null` |
| `parent_chunk_id` | 이 청크가 속한 상위(parent) 청크 ID. root 청크이거나 `hierarchical` 전략이 아니면 `null` |
| `meta.score_threshold` | 실제 적용된 `similarity.min_score`. hybrid 모드에서는 항상 `0.0`(미적용) |

### 모드별 점수(score) 및 복수 KB 집계 방식

**hybrid 모드**

- 각 KB에서 `top_k`개를 독립적으로 검색 (dense 순위 + sparse 순위 합산 → KB 내 RRF 점수)
- 복수 KB 결과를 하나로 모아 RRF를 다시 적용해 순위를 재산출
- `score = 1 / (60 + rank)` — 1위 ≈ 0.0164, 10위 ≈ 0.0143
- 점수 절댓값은 의미 없음. 품질 제어는 `top_k`로 한다 (`min_score` 적용 불가)
- 최종 결과: 전체 candidate 중 RRF 점수 상위 `top_k`개 반환

**similarity 모드**

- 각 KB에서 `top_k`개를 독립적으로 검색 (코사인 유사도 기준)
- `min_score` 미만 결과를 KB별로 먼저 제거
- 복수 KB 결과를 합산한 뒤 코사인 유사도 내림차순으로 정렬
- 최종 결과: 정렬된 전체 candidate 중 상위 `top_k`개 반환

### 검색 API 확장 [ENT]

`POST /api/search`는 viewer 이상 필요. 요청한 `kb_ids` 중 호출자가 접근 권한이 없는 KB는 검색 전에 자동으로 제외됩니다. super-admin이거나 `kb_authz_enabled=false`이면 필터링이 적용되지 않습니다. 필터링 후 남는 KB가 하나도 없으면 (Core처럼 422가 아니라) 빈 결과로 HTTP 200을 반환합니다.

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "검색어", "kb_ids": ["kb-01", "kb-02"], "options": {"mode": "hybrid", "top_k": 10}}'
```

---

## 14. MCP 연결

VS Code `.vscode/mcp.json` (워크스페이스 기준):

```json
{
  "servers": {
    "rag-api": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

또는 사용자 전역 설정 (`settings.json`):

```json
{
  "mcp.servers": {
    "rag-api": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### MCP 확장 [ENT]

Core의 MCP 서버와 별개로, Enterprise 자체 MCP 서버(`search` / `list_knowledge_bases` / `get_document` 툴)가 동일한 인증·역할 검사를 거쳐 동작합니다.

```json
{
  "servers": {
    "rag-ent-api": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": { "Authorization": "Bearer <JWT>" }
    }
  }
}
```

각 툴은 REST API와 동일하게 접근 가능한 KB만 조회/검색 대상에 포함하며, super-admin 및 `kb_authz_enabled=false` 우회 규칙도 동일하게 적용됩니다.
