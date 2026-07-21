---
sidebar_position: 1
---

# 아키텍처

RAG Platform의 아키텍처는 세 개의 레이어로 나뉜다 — 요청을 받는 **Application Layer**
(rag-admin / rag-api / rag-ent-api), 실제 데이터가 저장되는 **Data Layer**(Qdrant / Redis /
PostgreSQL / MinIO / Embedding Server), 그리고 이 둘을 연결해 인제스트를 실행하는
**Pipeline Layer**(Dagster)다. 

```
Application Layer
-────────────────────────────────────────────────────────────────────
                              ┌──────────────┐
                              │ rag-platform │
                              └──────┬───────┘
                  ┌──────────────────┼──────────────────┐
                  ▼                  ▼  REST API        ▼
          ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
          │  rag-admin  │──▶│   rag-api   │◀──│ rag-ent-api │
          │  (console)  │   │(core engine)│   │(auth + RBAC)│
          └─────────────┘   └──────┬──────┘   └─────────────┘
                                   │ 
                                   │  (KB mgmt · upload · search)
                                   ▼
Data Layer 
──────────────────────────────────────────────────────────────────────
 ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
 │  Qdrant   │ │   Redis   │ │PostgreSQL │ │   MinIO   │ │ Embedding │
 │ (vector)  │ │  (queue)  │ │(metadata) │ │(raw file) │ │  Server   │
 └─────▲─────┘ └─────▲─────┘ └─────▲─────┘ └─────▲─────┘ └─────▲─────┘
       │             │             │             │             │  
       │             │             │             │             │   
Pipeline Layer        
───────────────────────────────────────────────────────────────────────
       │             │             │             │             │   
       |        ┌──────────────────────────────────────────┐   │
       └─────── │                 Dagster                  │───┘
  vector upsert │ - pop event from Redis queue             │ embed request
                │ - parse → dedup → chunk → embed →  meta  │
                └──────────────────────────────────────────┘
```

## Application Layer

Application Layer는 사용자, 애플리케이션, MCP 클라이언트의 요청을 직접 수신하는 레이어다.
rag-admin은 상시 실행되며, 그 뒤에는 rag-api와 rag-ent-api 중 하나만 실행된다. 인증이
필요하지 않은 경우에는 rag-api(Core)가, 인증과 권한 제어가 필요한 경우에는
rag-ent-api(Enterprise)가 사용된다.


| 항목 | Core | Enterprise |
|------|------|------|
| API 구성 | rag-api — 인제스트 파이프라인, 하이브리드 검색, 커넥터, MCP 서버 | rag-api를 위에 인증·권한 레이어 추가|
| 관리 콘솔 | rag-admin (OIDC 설정값 없음 → 로그인 화면 비활성) | rag-admin — 동일 빌드, OIDC 설정값이 있으면 SSO 로그인 활성화 |
| 인증 | 없음 | OIDC Bearer JWT |
| KB 접근 제어 | 없음 | KB 단위 RBAC(viewer/editor/admin/owner) + 멤버십·초대 |
| 설정 섹션 | ingestion/chunking/dedup/embedding/retrieval 등 | 좌측 전체 + `oidc`/`authz`/`smtp`/`rate_limit`/`security` |
| 인제스트 확장 | — | 이미지 캡셔닝·OCR 폴백·표 구조 보존 파싱 (opt-in) |


## Data Layer

Application Layer가 실제로 읽고 쓰는 다섯 개의 저장소다. 하나로 합치지 않고 이렇게 쪼갠 이유는
각 저장소가 요구하는 조회 패턴이 서로 다르기 때문이다.

| 저장소 | 저장 데이터 | 선택 이유 |
|--------|-------------|------------------|
| **Qdrant** | 청크 단위 벡터(dense+sparse), KB별 컬렉션(`{kb_id}`) | ANN 검색 특화, 컬렉션 분리로 물리적 KB 격리 |
| **PostgreSQL** | KB/문서/커넥터 메타데이터, dedup LSH 밴드 인덱스(`simhash_bands`/`minhash_bands`) | 정확 일치 조회 특화 — SQL 인덱스로 dedup 후보 저비용 필터링 후 정밀 비교 |
| **Redis** | 업로드/삭제 큐 4개 키(`rag:upload:queue`, `rag:delete:queue`, 각 `:delay`) | 큐 전용, 유실 시 재인덱싱으로 복구 가능 |
| **MinIO (S3 호환)** | 원본 파일 | 재인덱싱의 근원(source of truth) |
| **Embedding Server** | 상태 없음 — Ollama(로컬) / OpenAI 선택 | 순수 계산 서버, 로컬 구성 시 외부 전송 없음 |

## Pipeline Layer

Application Layer와 Data Layer 사이에서 실제 인제스트 작업을 수행하는 Dagster다. 위 다섯
저장소를 아래 순서로 오가며 하나의 문서를 처리한다.

Redis 큐에 쌓인 이벤트를 Dagster가 pop하는 순간부터, 문서 하나는 아래 5단계 파이프라인을
순서대로 통과한다(`pipeline/steps/` — 순수 함수라 Dagster 없이 `runner.py`로도 동일하게
실행된다).

1. **validate** — 파일 형식·크기가 설정 범위 안인지 검증한다.
2. **parse → dedup** — MinIO에서 원본을 fetch해 텍스트를 추출하고, 곧바로 중복 검사를 한다.
   PostgreSQL의 `simhash_bands`/`minhash_bands` 인덱스로 후보를 먼저 좁히고, 중복으로
   판정되면 **여기서 처리가 중단**된다 — 문서는 색인되지 않고 `outdated`로 남는다.
3. **chunk** — 중복이 아닌 문서만 청킹 단계로 넘어간다.
4. **embed** — Embedding Server를 호출해 청크별로 dense+sparse 벡터를 만든다.
5. **upsert → meta** — 벡터를 해당 KB의 Qdrant 컬렉션에 저장하고, PostgreSQL의 문서 상태를
   `indexed`로 갱신한다.

이 다섯 단계가 순서대로 실패 없이 끝나야 문서 하나가 검색 가능한 상태가 된다 — 이 과정에서
문서 상태가 어떻게 전이되고 왜 중간에 요청이 막히는지는 [문서 상태 흐름](document-lifecycle.md)에서
다룬다.