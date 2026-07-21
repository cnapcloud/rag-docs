# 아키텍처

RAG Platform의 전체 구성도, 핵심 데이터 흐름(인제스트·검색·커넥터 동기화), 네트워크 정책 설계용
통신 매트릭스, Core/Enterprise 차이, 실행 모드, 고가용성·장애 복구 관점 등 배포 설계에 필요한 배경 정보를 다룬다.

---

## 1. 전체 구성

```
                     [User / Integrated App / MCP Client]
                                    |
                                  HTTPS
                                    v
                     +------------+-------------+
                     v                          v
            rag-admin (console)         rag-api (API + MCP)
                     |                          |
                     |  API call                |
                     +--------------------------+
                                    |
                                    v
               +------------------------------------------+
               | dagster (webserver / daemon / user-code) |
               |   |                                      |
               |   v  run & schedule ingest pipeline      |
               | qdrant (vector DB, Helm-based)           |
               +------------------------------------------+
                                    |
                                    v
   +----------------------------------------------------------------+
   | PostgreSQL(CNPG)   Redis(HA)     MinIO(S3)    embedding server |
   | metadata/authz     event queue   raw docs     Ollama(GPU) or   |
   |                                                OpenAI API(ext) |
   +----------------------------------------------------------------+

Enterprise add-on:  Keycloak (OIDC IdP)   SMTP (invite email)
```

임베딩은 두 프로바이더 중 선택한다 (`embedding.provider`):

| 프로바이더 | 구성 | 선택 기준 |
|-----------|------|-----------|
| Ollama | 클러스터 내부 또는 별도 GPU 노드에 자체 호스팅 (기본 모델 bge-m3) | 폐쇄망·데이터 반출 불가 환경, 호출 비용 없음 |
| OpenAI | 외부 API 호출 (`text-embedding-3-small` 등) | GPU 인프라 없이 빠른 도입 — 문서 내용이 외부로 전송되는 점을 보안 정책과 확인 |

컴포넌트별 요구 리소스는 [01-requirements.md](../install/01-requirements.md), 설치 절차는
[03-install-k8s.md](../install/03-install-k8s.md) 참조.

## 2. 핵심 데이터 흐름

### 인제스트 (업로드 ~ 검색 가능)

```
업로드 API, Connector ──> S3 저장 + Redis 큐 적재
   ──> Dagster 센서 ──> 인제스트 파이프라인
        (검증 → 파싱 → 중복 검사 → 청킹 → 임베딩 → 벡터 저장 → 메타 갱신)
   ──> Qdrant(청크 벡터) + Postgres(문서 상태 indexed)
```

중복 검사(dedup) 단계에서 기존 문서와 동일·유사로 판정되면 이후 단계를 건너뛰어 중복
청크가 검색 인덱스에 들어가지 않는다 (2단계 감지 — 해시 기반 + 유사도 기반,
[기능 카탈로그](../reference/04-features-catalog.md) 참조).

문서 유입 경로는 두 가지(직접 업로드, 커넥터 수집)지만 S3 저장 이후의 처리는 동일하다.

- **문서 1건 = 독립 실행 1건**: 특정 문서 실패가 다른 문서에 영향을 주지 않고, 문서별
  재시도가 가능하다.
- 병렬성은 Dagster `max_concurrent_runs`(기본 8)로 제어한다.

### 검색

```
검색 API ──> Qdrant 하이브리드 질의 (dense + sparse, KB별 병렬)
   ──> RRF 순위 병합 ──> (선택) 리랭커 ──> 응답
```

Enterprise 배포는 질의 전에 호출자의 KB 권한으로 대상을 필터링한다.

### 커넥터 동기화

```
스케줄(cron) 또는 수동 트리거 ──> 커넥터가 소스(웹/Confluence/GitHub) 순회
   ──> 변경 문서만 S3 스테이징 ──> 이후 인제스트 흐름과 동일
```

## 3. 통신 매트릭스

네트워크 정책 설계용 — 이 표에 없는 경로는 차단해도 된다.

| 출발 | 도착 | 포트 | 용도 |
|------|------|------|------|
| ingress | rag-admin | 80 | 콘솔 UI |
| ingress | rag-api | 8000 | API·MCP |
| rag-admin | rag-api | 8000 | API 호출 |
| rag-api | Postgres / Redis / Qdrant / S3 | 5432 / 6379 / 6333 / 9000 | 데이터 계층 |
| rag-api | Dagster webserver | 3000 | run 조회·종료 (GraphQL) |
| rag-api | 임베딩 서버 (Ollama 11434 또는 OpenAI API 443) | 11434 / 443 | 검색 질의 임베딩 |
| Dagster (daemon·job) | Postgres / Redis / Qdrant / S3 / 임베딩 서버 | 상동 | 파이프라인 실행 |
| rag-api / rag-admin(브라우저) | Keycloak | 443 | 토큰 검증(JWKS) / 로그인 (ENT) |
| rag-api | SMTP | 587 등 | 초대 메일 (ENT) |
| rag-api / Dagster | Langfuse | 3000 | 트레이스 전송 (관측 구성 시, [02-observability.md](../operations/02-observability.md)) |

## 4. Core vs Enterprise

동일 아키텍처에서 **API 이미지와 설정만 다르다.** 콘솔은 단일 빌드로 런타임 설정에 따라
모드가 결정된다.

| 항목 | Core | Enterprise |
|------|------|------------|
| API 이미지 | rag-api | rag-ent-api (rag-api를 포함·확장) |
| 인증 | 없음 (내부망 전제) | OIDC Bearer JWT |
| KB 접근제어 | 없음 | KB 단위 RBAC + 멤버십·초대 |
| 추가 인프라 | — | Keycloak, SMTP |
| 콘솔 | 동일 빌드 (`OIDC_CLIENT_ID` 빈 값) | 동일 빌드 (`OIDC_CLIENT_ID` 설정 → SSO 로그인) |

## 5. 실행 모드

| 모드 | 파이프라인 실행 주체 | 용도 |
|------|---------------------|------|
| Dagster 모드 (기본, 운영 표준) | Dagster 센서가 큐 소비, 문서별 run 실행 | 실행 이력 UI, 강제 종료·자동 복구 완전 지원 |
| 경량 모드 (`queue_worker.enabled: true`) | API 서버 내장 워커 | Dagster 없이 단순 구성 — **평가·개발 전용** ([알려진 제약](../support/03-known-limitations.md) §1) |

두 모드는 같은 Redis 큐를 소비하므로 파이프라인 동작은 동일하다. 평가는
docker-compose([02-quickstart.md](../install/02-quickstart.md)), 운영은 k8s + Dagster 모드가 표준이다.

## 6. 고가용성·단일 지점

| 계층 | 상태 |
|------|------|
| PostgreSQL / Redis | HA 구성 운영 검증됨 (CloudNativePG, Redis HA) — 기존 HA 인프라 재사용 권장 |
| rag-api | 기본 1 replica — 다중 replica 구성은 검증 진행 중 |
| Qdrant / MinIO / Ollama(사용 시) | 단일 인스턴스 기준 — HA 구성 가이드는 로드맵 항목. OpenAI 임베딩 사용 시 임베딩 서버 운영 부담 없음 |
| 파이프라인 | 문서 단위 격리로 부분 실패가 전체로 번지지 않음. 비정상 종료로 고착된 문서는 자동 복구(Dagster 모드) 또는 복구 API |

장애 시 데이터 복원 관점은 [01-runbook-k8s.md](../operations/01-runbook-k8s.md) §1 참조 — 핵심은 **벡터
(Qdrant)는 Postgres+S3만 있으면 재인덱싱으로 재생성 가능**하다는 점이다.
