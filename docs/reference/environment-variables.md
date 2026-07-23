---
sidebar_position: 3
---

# Environment Variables

배포에 필요한 자격증명·시크릿 값 전체를 정리한다. [Configuration](configuration.md)이 다루는
`settings.yaml`과 역할이 분리되어 있으며, 이 문서는 **어떤 값에 실제 자격증명을 넣어야
하는지**를 다루는 레퍼런스다.
---

## `settings.yaml`과의 역할 분리

| | `settings.yaml` | 시크릿 |
|---|---|---|
| 담는 값 | 호스트, 포트, 임계값 등 비-시크릿 설정 | 비밀번호, API 키 등 시크릿 |
| Docker Compose 전달 | 볼륨 마운트 | `docker/.env`(`env_file`) |
| Kubernetes 전달 | ConfigMap | Secret 리소스 |
| git 추적 | 항상 커밋 | Docker Compose는 로컬 평가용 placeholder만 커밋, 운영 배포 시 실값으로 교체 후 별도 관리 |

시크릿을 `settings.yaml`에 직접 쓰지 않는 이유는 배포 형식(ConfigMap)과 보관 형식(Secret)을
분리해 시크릿이 평문 형상관리 대상에 섞이지 않도록 하기 위함이다. `Settings.from_yaml()`이
모든 키를 자동으로 환경변수와 매칭하는 것은 아니다 — 코드에 하드코딩된 아래 변수 목록만
읽는다(자격증명·시크릿 성격의 항목으로 한정). 이 목록 밖의 설정은 환경변수로
오버라이드되지 않으며 [Configuration](configuration.md)의 `settings.yaml`을 직접 수정해야
한다. 환경변수는 `settings.yaml` 값보다 우선 적용된다.

---

## 인프라 자격증명

```
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password
S3_ACCESS_KEY=admin
S3_SECRET_KEY=password

REDIS_PASSWORD=redis

POSTGRES_USER=rag-api
POSTGRES_PASSWORD=password
```

| 변수 | 설명 |
|------|------|
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | 공식 MinIO 이미지가 읽는 루트 계정 |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | rag-api 앱이 같은 자격증명을 읽는 이름. **MinIO 변수와 값이 항상 같아야 한다** — 하나만 바꾸면 앱이 MinIO에 인증하지 못한다 |
| `REDIS_PASSWORD` | `redis-server --requirepass` 실행 인자와 rag-api 앱이 공유하는 값 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | 앱 DB 유저. `docker/init-db.sql`이 이 유저를 생성하며 비밀번호를 SQL 리터럴로 하드코딩한다 — **`.env`만 바꿔서는 비밀번호가 바뀌지 않는다.** `init-db.sql`도 함께 수정하고 `postgresql` 볼륨을 재생성해야 한다 |

**운영 고려사항**: `S3_ACCESS_KEY`/`SECRET_KEY`와 `MINIO_ROOT_USER`/`PASSWORD`의 값 동기화를
놓치는 것이 가장 흔한 초기 설정 실수다. Postgres 비밀번호 교체 절차는 `init-db.sql` 수정 →
`.env` 수정 → `docker compose down` → `postgresql` 볼륨 삭제 → `docker compose up` 순서다.
기존 데이터가 있는 볼륨을 그대로 두면 `init-db.sql`이 재실행되지 않아 비밀번호가 바뀌지 않는다.

---

## 커넥터 시크릿 암호화 키

```
CONNECTOR_SECRET_KEY=
```

| 변수 | 설명 |
|------|------|
| `CONNECTOR_SECRET_KEY` | 커넥터 설정의 시크릿 필드(`auth_token_secret`/`auth_headers`/`auth_basic`)를 저장 시 암호화하는 Fernet 키(URL-safe base64, 32바이트). 비워두면 코드에 고정된 약한 기본 키로 폴백한다 — **운영 배포에서는 반드시 실값을 채운다** |

커넥터 접속 토큰 자체는 이 변수로 넣는 게 아니라 커넥터 생성/수정 API 호출로 전달되며,
이 키는 그 값을 저장할 때 암호화하는 용도로만 쓰인다.

---

## 외부 서비스 키

```
RERANKER_API_KEY=
TRACING_LANGFUSE_PUBLIC_KEY=
TRACING_LANGFUSE_SECRET_KEY=
OPENAI_API_KEY=
```

| 변수 | 설명 |
|------|------|
| `RERANKER_API_KEY` | Jina 리랭킹 API 키. `retrieval.rerank.enabled: false`이면 값이 비어 있어도 무방하다 |
| `TRACING_LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` | Langfuse 트레이싱 키. `tracing.enabled: false`이면 비어 있어도 무방하다 |
| `OPENAI_API_KEY` | `provider.name: openai`일 때만 읽는다. `provider.openai_api_key`로 주입된다 |

세 값 모두 해당 기능이 꺼져 있으면(`enabled: false`) 비어 있어도 기동에 지장이 없다. 기능을
켜기 전에 값을 채워 넣는 순서로 진행한다.

---

## 백엔드 추가 변수 [ENT]

```
OIDC_ADMIN_CLIENT_ID=
OIDC_ADMIN_CLIENT_SECRET=
SMTP_USERNAME=
SMTP_PASSWORD=
```

| 변수 | 설명 |
|------|------|
| `OIDC_ADMIN_CLIENT_ID` / `OIDC_ADMIN_CLIENT_SECRET` | Keycloak Admin API 조회용 서비스 계정(`oidc.admin_url`과 함께 사용). 이메일 기반 사용자 조회에 쓰이며, 비어 있으면 해당 기능만 조용히 동작하지 않고 나머지는 정상이다 |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | 초대 메일 발송용 SMTP 인증. 평가 환경 mailpit은 인증 없이도 동작하지만, 운영 SMTP 서버는 대부분 인증을 요구한다 |

`OIDC_ADMIN_CLIENT_ID/SECRET`을 설정하지 않으면 관리자 조회 기능만 실패하고 나머지 Enterprise
기능(인증, RBAC)은 정상 동작한다 — 장애처럼 보이지 않아 누락을 알아채기 어렵다.
`SMTP_USERNAME`/`PASSWORD`를 운영 SMTP로 교체할 때
[Configuration §20 smtp](configuration.md#20-smtp-enterprise-전용)의
`host`/`port`/`from_address`도 함께 바꿔야 한다.

---

## rag-admin 프론트엔드 변수 [ENT]

```
API_URL=http://rag-ent-api:8000
OIDC_ISSUER=https://keycloak.example.com/realms/example
OIDC_CLIENT_ID=rag
DOC_REFRESH_INTERVAL=20
DOC_FAST_INTERVAL=5
DOC_POLL_ENABLED=true
PAGE_SIZE=10
```

| 변수 | 설명 |
|------|------|
| `API_URL` | 콘솔이 호출할 API 주소. docker-compose 배포에서는 `environment:` 블록이 내부 네트워크 주소로 재정의하므로 `.env` 값은 실질적으로 무시된다 |
| `OIDC_ISSUER` / `OIDC_CLIENT_ID` | 값이 있으면 콘솔이 ENT 모드(OIDC 로그인)로 동작한다. Core 배포에서는 빈 값으로 둔다 |
| `DOC_REFRESH_INTERVAL` / `DOC_FAST_INTERVAL` | 문서 목록 폴링 주기(초). `DOC_FAST_INTERVAL`은 처리 중 문서가 있을 때 적용되는 짧은 주기다 |
| `DOC_POLL_ENABLED` | 폴링 자체를 끌지 여부 |
| `PAGE_SIZE` | 목록 페이지네이션 크기 |

---

## 운영 배포 체크리스트

1. `docker/.env`의 모든 자격증명 값을 예제 값에서 실값으로 교체한다.
2. Postgres 비밀번호를 바꾼 경우 `init-db.sql`도 함께 수정했는지 확인한다.
3. `S3_ACCESS_KEY`/`SECRET_KEY`가 `MINIO_ROOT_USER`/`PASSWORD`와 일치하는지 확인한다.
4. k8s 배포라면 `.env` 대신 SOPS 등으로 암호화한 Secret을 사용한다.
5. `SMTP_USERNAME`/`PASSWORD`가 실 SMTP 서버 인증 정보와 일치하는지 확인한다. mailpit
   값이 그대로 남아 있으면 초대 메일이 실제로는 발송되지 않는다. [ENT]
6. `CONNECTOR_SECRET_KEY`를 코드 기본값이 아닌 실값으로 설정했는지 확인한다. 비워두면
   약한 기본 키로 폴백해 커넥터 시크릿 암호화가 사실상 무의미해진다.
