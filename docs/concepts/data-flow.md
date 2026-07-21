---
sidebar_position: 2
---

# 검색 · 인제스트 흐름

검색과 인제스트가 실제로 어떻게 동작하는지 다룬다. 검색에서는 하이브리드 질의가 응답으로
만들어지는 과정을 설명하고, 인제스트에서는 이벤트를 소비하는 두 배포 모드(Dagster /
QueueWorker)와 dedup 3단계, 파서 레지스트리까지 순서대로 설명한다.

---

## 검색 흐름

```
query ──▶ Qdrant hybrid query ──▶ RRF rank fusion ──▶ (optional) reranker ──▶ response
            (dense + sparse,
             parallel per KB)
```

### 왜 dense와 sparse를 같이 쓰는가

두 방식은 서로 다른 지점에서 약하다.

| 방식 | 강점 | 약점 |
|------|------|------|
| dense(의미) | 동의어·표현 변형 인식 | 고유명사·코드·숫자 등 정확 일치 매칭 |
| sparse(키워드, BM25) | 정확한 용어·식별자 매칭 | 의미가 같은 다른 표현 인식 불가 |

약점이 서로 다르기 때문에 하나만 쓰면 특정 질의 유형에서 결과가 빈다. 두 결과를 각각 구한
뒤 **RRF(Reciprocal Rank Fusion)**로 병합한다. RRF는 각 결과의 순위(rank)만으로 병합하는
방식이라 dense 점수와 sparse 점수를 직접 비교하거나 정규화할 필요가 없다. `alpha` 파라미터로
두 순위 중 어느 쪽에 가중치를 더 줄지 조정한다.

### 리랭커와 폴백

RRF 병합 결과 상위 일부를 리랭커(Jina API)가 한 번 더 정렬한다. 이 단계는 실패해도 검색
자체를 끊지 않는다. 리랭커 API가 응답하지 않으면 RRF 순위를 그대로 반환하고, 응답의
`rerank_fallback: true` 필드로 폴백 발생 여부를 알린다. 검색 품질에 민감한 환경은 이 필드를
모니터링해야 조용히 리랭킹이 빠진 상태를 놓치지 않는다.

### 복수 KB 검색

여러 KB를 동시에 검색할 때는 KB별로 병렬 질의한 뒤 결과를 하나의 순위로 합친다. 특정 KB의
질의가 실패해도(장애·권한 없음) 나머지 KB 결과만으로 응답한다. 한 KB의 장애가 전체 검색을
막지 않는다. Enterprise 배포에서는 이 병렬 질의 자체가 호출자의 KB 권한으로 필터링된
목록에만 나간다.

## 인제스트 흐름

[아키텍처](architecture.md)의 5단계(validate → parse+dedup → chunk → embed → upsert+meta)를
실제 op 단위와 저장소 접근까지 풀어보면 아래와 같다. Redis 큐를 소비하는 주체는 배포 모드에
따라 둘 중 하나이며, 이후 op 시퀀스는 두 모드 모두 동일하다(각 모드의 상세는 아래 절 참고).
두 모드 모두 같은 설정값 `queue_poll.poll_interval_sec`(기본 5초)로 큐를 poll한다 — Dagster
전용 간격이 따로 있는 게 아니다.

```
Redis (rag:upload:queue)
   │
   ▼  poll every queue_poll.poll_interval_sec (default 5s) — shared by both modes
event_queue_sensor (Dagster mode) / QueueWorker (queue_worker.enabled: true)
   │  N events → parallel execution (RunRequests / AsyncIO tasks, per mode's concurrency limit)
   ▼
validate_op
   │  PostgreSQL lookup — skip if ETag matches the existing document
   ▼
parse_op
   │  fetch raw file from MinIO → extract text
   ▼
dedup (SimHash → MinHash → chunk cosine, 3 stages — see below)
   │  query PostgreSQL simhash_bands / minhash_bands
   │  if duplicate, processing stops here → outdated
   ▼
chunk_op
   │  pure computation — no storage access
   ▼
embed_op
   │  call Embedding Server (Ollama/OpenAI) → generate dense+sparse vectors
   ▼
upsert_op
   │  Qdrant — delete existing chunks (doc_id filter), then upsert new chunks
   ▼
meta_op
   │  PostgreSQL — set status to indexed, record etag/chunk_count/updated_at
```

각 op은 순수 함수라 Dagster 없이도 `runner.py`로 동일하게 실행된다. op 하나가 저장소 하나씩만
건드리는 구조라, 특정 단계가 실패해도 어느 저장소까지 반영됐는지를 op 이름만으로 바로 특정할
수 있다.

### Dagster 모드

위 다이어그램의 `event_queue_sensor`는 컨테이너 하나가 아니라 역할이 분리된 세 컨테이너가
함께 동작한 결과다.

```
   ┌──────────────────┐   fetch definitions(gRPC)   ┌───────────────────┐
   │  dagster-daemon  │◀─────────────────────────── │  dagster-rag-api  │
   │  event_queue_    │                             │  code server,     │
   │  sensor          │─────────────────────────── ▶│  port 4000.       │
   │                  │     request Run execution   │  job/op defs      │
   └────────┬─────────┘                             └─────────▲─────────┘
            │                                                 │ fetch definitions(gRPC)
            │ poll Redis queue                                │
            ▼                                       ┌─────────┴────────┐
   Redis(rag:upload:queue)                          │dagster-webserver │
                                                    │ UI + GraphQL API │
                                                    │ (port 3000)      │
                                                    └─────────▲────────┘
                                                              │ query/force-terminate run (GraphQL)
                                                    ┌─────────┴────────┐
                                                    │      rag-api     │
                                                    │  force-fail API  │
                                                    └──────────────────┘
```

- **dagster-rag-api** — 실제 job/op 정의(`ingest_job`, `delete_job` 등)를 담은 gRPC 코드
  서버다. daemon과 webserver 모두 이 서버에 정의를 조회하러 간다 — job 로직을 바꾸려면 이
  컨테이너만 재배포하면 된다.
- **dagster-daemon** — `event_queue_sensor`를 실행하는 프로세스다.
  `queue_poll.poll_interval_sec`(기본 5초)마다 Redis 큐를 polling해 이벤트를 RunRequest로
  바꾸고, dagster-rag-api의 정의를 가져와 Run을 실행한다.
- **dagster-webserver** — UI인 동시에 GraphQL API 서버다(port 3000). rag-api의 force-fail
  API가 실행 중인 문서를 강제 종료할 때 이 GraphQL 엔드포인트로 요청을 보낸다
  (`infra/dagster_utils.py`).

강제 종료는 [문서 상태 흐름](document-lifecycle.md)의 `POST .../fail` 경로에서 이렇게
연결된다.

1. `run_id`가 있으면 dagster-webserver의 GraphQL로 해당 Run을 강제 종료한다.
2. Redis 큐에서 이 문서의 남은 upload 이벤트를 제거한다.
3. PostgreSQL의 문서 상태를 `failed`로 기록한다.

dagster-rag-api(코드 서버)가 재시작되는 도중에는 daemon이 정의를 조회하지 못해 실행 중이던
Run의 프로세스가 사라져도 PostgreSQL에는 `STARTED` 상태로 남을 수 있다 — 이 경우가 운영
중 stuck Run이 생기는 대표적인 경로다.

### QueueWorker 모드

`queue_worker.enabled: true`로 설정하면 Dagster 없이 rag-api 프로세스에 내장된 AsyncIO
워커가 같은 Redis 큐를 직접 소비한다. op 시퀀스 자체는 동일하지만, 큐를 꺼내는 주체와 실행
격리 방식이 다르다.

```
Redis (rag:upload:queue)
   │
   ▼  QueueWorker (embedded in rag-api process) polls every poll_interval_sec (default 5s)
QueueWorker
   │  pop up to max_per_poll (default 5) events per poll
   │  process as AsyncIO tasks within max_workers (default 5) concurrency limit
   ▼
validate_op → parse_op → dedup → chunk_op → embed_op → upsert_op → meta_op
   │  same ops called in sequence within the same process — no Dagster Run isolation
```

Dagster 모드와의 실질적인 차이는 세 가지다.

- **강제 종료** — Dagster는 문서 1건이 Run 1개라 실행 중에도 강제 종료할 수 있다. QueueWorker는
  같은 프로세스의 AsyncIO 태스크라 force-fail API를 호출해도 상태만 `failed`로 바뀔 뿐 실제
  태스크는 계속 실행되며, 완료 시 그 상태를 덮어쓸 수 있다.
- **커넥터 자동 스케줄** — Dagster Schedule로 동작하는 커넥터 정기 동기화는 QueueWorker
  모드에서 지원되지 않는다.
- **실행 이력** — Dagster UI가 제공하는 run별 실행 이력·실패 로그가 QueueWorker 모드에는
  없다.

이런 제약 때문에 QueueWorker 모드는 별도 인프라 없이 빠르게 띄워보는 평가·개발 용도로 쓰고,
운영 배포는 Dagster 모드를 표준으로 한다.

### dedup 3단계 처리

[아키텍처](architecture.md#pipeline-layer)에서 본 것처럼 dedup은 parse 직후, chunk 이전에
실행되어 중복이면 그 자리에서 처리를 중단시킨다. 내부적으로는 한 번에 정밀 비교를 하지 않고,
싼 검사로 후보를 좁힌 다음에만 비싼 검사를 수행하는 깔때기(funnel) 구조로 3단계다.

```
document ingested
   │
   ▼
stage 1: hash comparison (SimHash, 64-bit → four 16-bit bands)
   │  PostgreSQL LSH index cheaply extracts "exact/near-duplicate" candidates
   ▼
stage 2: lightweight similarity filtering (MinHash 128 signatures + title fuzzy match)
   │  Jaccard similarity narrows down to "possibly similar content" candidates
   ▼
stage 3: chunk-level precise comparison (embedding cosine similarity)
   │  the expensive computation — runs only on the few remaining candidates
   ▼
verdict: none / identical_level / similar
   → feeds into document status transition (e.g. outdated)
```

각 단계는 이전 단계의 결과 위에서만 동작한다. 대부분의 신규 문서는 1단계에서 곧바로
"후보 없음"으로 끝나고 비싼 3단계까지 가지 않는다. 판정 결과가 실제로 문서 상태에 어떻게
반영되는지(예: `identical_level` + 더 오래된 문서 → `outdated`)는
[문서 상태 흐름](document-lifecycle.md)에서 다룬다.

### 파서 레지스트리

parse는 확장자를 보고 정해진 리더를 호출하는 고정 로직이 아니라 레지스트리 조회 구조다.
신규 문서 형식이든 기존 형식에 대한 파싱 방식 변경이든, rag-api 코드를 수정하지 않고
추가·교체할 수 있게 하기 위함이다.

기본적으로 PDF·Word(`.doc`/`.docx`)·PowerPoint(`.ppt`/`.pptx`)·Excel(`.xls`/`.xlsx`)·
한글(HWP)·텍스트·마크다운·HTML·RST·이메일(EML)·CSV/TSV/JSON·EPUB에 리더 17종, 그리고
소스코드·설정 파일 확장자까지 총 36개 확장자가 등록되어 있다
이 레지스트리를 확장하는 방법은 두 가지다.

- **신규 추가** — 지원하지 않는 확장자에 새 리더를 등록한다.
- **교체(override)** — 이미 등록된 확장자에 리더를 다시 등록하면 기존 리더를 대체한다
  (last-writer-wins).

두 경우 모두 `settings.yaml`의 `ingestion.parser_plugins`에 등록 함수 경로를 나열하는 것으로
충분하다. 기동 시 `_load_plugins()`가 목록을 순서대로 호출해 레지스트리에 반영한다.

```
settings.yaml:
  ingestion.parser_plugins
    - "rag_ent.pipeline.plugins.image_ocr:register"
    - "rag_ent.pipeline.plugins.table_layout:register"
              │
              │  called in listed order — same extension → last-writer-wins
              ▼
startup ──▶ _register_defaults() ──▶  ┌─────────────────────────────┐ ◀── _load_plugins()
            (36 extensions:           │      parser_registry        │
             pdf/doc(x)/ppt(x)/       │  extension → reader         │
             xls(x)/hwp/txt/md/html/  │  extension → post-processor │
             rst/eml/csv/json/epub/   │                             │
             code+config files)       │                             │
                                      └─────────────┬───────────────┘
                                                    │  lookup by file extension
                                                    ▼
                                                parse_op(file)
```

rag-ent-api는 이 구조를 그대로 활용해 Enterprise 인제스트 확장을 연동하며, 두 방법을 동시에
쓴다.

- **`.pdf` override** — `image_ocr:register()`가 기존 `.pdf` 리더를 OCR 폴백 리더로
  덮어쓰고, `table_layout:register()`가 다시 표 구조 인식 리더로 덮어쓴다. 등록 순서가
  결과를 결정하므로, `parser_plugins` 목록에서 table_layout이 image_ocr 뒤에 있어야
  `.pdf`를 최종적으로 표 구조 인식 리더가 점유한다.
- **신규 이미지 포맷 추가** — 같은 `image_ocr:register()`가 기존에 등록되어 있지 않던
  이미지 확장자(`.png`/`.jpg`/`.jpeg`/`.gif`/`.bmp`/`.webp`)를 VLM 캡셔닝 리더로 새로
  등록한다. 이 여섯 확장자는 Core 배포의 36개 확장자 목록에는 없던, Enterprise 전용
  신규 지원 포맷이다.
