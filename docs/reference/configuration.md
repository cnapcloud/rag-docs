---
sidebar_position: 2
title: 설정
---

# 설정

`settings.yaml`에 있는 모든 설정 항목의 의미·기본값·바꿀 때 고려할 점을 섹션별로 정리한다.

설정 파일은 로컬 실행 시 `settings.yaml`(프로젝트 루트)을 그대로 쓰고, 컨테이너 안에서는
배포 방식과 무관하게 `/app/settings.yaml` 경로에 있어야 한다. 시크릿(비밀번호·API 키)은
이 문서가 다루는 `settings.yaml`에 직접 쓰지 않고 배포 방식에 맞는 시크릿 저장소에 담는다
— 평문 형상관리 대상과 시크릿을 분리하기 위함이다.

- **Docker Compose** — `settings.yaml`은 볼륨 마운트로 주입, 시크릿은 `docker/.env`(실제
  변수 목록은 [Environment Variables](environment-variables.md) 참고)
- **Kubernetes** — `settings.yaml`은 ConfigMap으로 주입, 시크릿은 Secret 리소스

---

## 1. dagster

Dagster 웹서버 연결 설정. 큐 워커 모드(`queue_worker.enabled: true`)에서는 사용되지 않는다.

```yaml
dagster:
  endpoint: "http://localhost:3000"
```

| 키 | 설명 |
|----|------|
| `endpoint` | Dagster 웹서버 URL. workspace reload(`reloadWorkspace`)와 run 강제 종료(`terminateRun`) GraphQL 호출에 사용됨. `queue_worker.enabled: true`이면 no-op |

**운영 고려사항**

- 컨테이너 환경에서는 `http://dagster-webserver:3000` 형식의 내부 네트워크 주소를 사용한다.
- 실제 job 실행은 gRPC(`dagster-rag-api:4000`)를 통해 이루어지며 이 설정과 무관하다.
- `queue_worker.enabled: false` 모드에서 이 주소에 접근할 수 없으면 커넥터 스케줄 reload는 warning 로그만 남기고 무시되지만, run terminate 실패는 `RuntimeError`로 상위에 전파된다.

---

## 2. s3

MinIO(S3 호환) 오브젝트 스토리지 연결 설정. 업로드 파일과 커넥터가 수집한 원본 문서를 저장한다.

```yaml
s3:
  endpoint: "http://192.168.0.185:9000"
  access_key: "admin"
  secret_key: "password"
  rag_bucket: "rag-api"
  dagster_bucket: "dagster"
  region: "us-east-1"
  insecure: true
```

| 키 | 설명 |
|----|------|
| `endpoint` | MinIO 서버 주소 (포트 포함) |
| `access_key` | 접근 키 (MinIO root user) |
| `secret_key` | 시크릿 키 (MinIO root password) |
| `rag_bucket` | 문서 저장 버킷 이름 |
| `dagster_bucket` | Dagster 아티팩트 저장 버킷 이름 |
| `region` | 리전 (S3 호환성용, 실질 영향 없음) |
| `insecure` | `true`: HTTP 사용. `false`: HTTPS + 인증서 검증 |

**운영 고려사항**

- `secret_key`는 평문으로 파일에 저장하지 않도록 한다. 프로덕션에서는 환경변수(`S3_SECRET_KEY`)로 주입한다.
- `insecure: false` 전환 시 MinIO가 유효한 TLS 인증서를 사용해야 한다. Let's Encrypt 또는 내부 CA 인증서를 MinIO에 적용한 후 변경한다.
- `rag_bucket`과 `dagster_bucket`은 사전에 생성되어 있어야 한다. `minio-init` 컨테이너가 이를 담당한다.

---

## 3. postgres

KB, 문서, 커넥터 메타데이터와 dedup 밴드(SimHash/MinHash)를 저장하는 Postgres 연결 설정.

```yaml
postgres:
  host: "postgresql"
  port: 5432
  dbname: "rag-api"
  user: "rag-api"
  password: "password"
  pool_size: 5
  connect_timeout: 30
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `host` | — | Postgres 호스트 |
| `port` | `5432` | Postgres 포트 |
| `dbname` | — | 데이터베이스 이름 |
| `user` | — | 접속 유저 |
| `password` | — | 비밀번호 |
| `pool_size` | `5` | asyncpg 연결 풀 크기 |
| `connect_timeout` | `30` | 연결 타임아웃(초) |

**운영 고려사항**

- `pool_size`는 `queue_worker.max_workers`와 연계해 설정한다. 동시 처리 워커 수보다 약간 크게 설정하는 것이 일반적이다. 예: `max_workers: 5` → `pool_size: 7`.
- Postgres `max_connections`가 낮으면 커넥션 풀 생성에 실패한다. 기본값(`100`) 기준으로 rag-api, Dagster 컨테이너가 각자 `pool_size`만큼 연결을 가져간다는 점을 고려한다.
- `connect_timeout`은 네트워크 장애 감지 속도에 영향을 준다. 너무 낮으면 일시적 지연에도 연결 실패로 처리된다.
- 비밀번호는 `POSTGRES_PASSWORD` 환경변수로 주입하는 것을 권장한다.

---

## 4. qdrant

벡터 DB 연결 설정. 문서 청크의 dense/sparse 임베딩을 저장하고 검색한다.

```yaml
qdrant:
  host: "192.168.0.184"
  port: 6333
  insecure: true
```

| 키 | 설명 |
|----|------|
| `host` | Qdrant 서버 호스트 |
| `port` | gRPC 포트 (`6333`: REST, `6334`: gRPC — 코드는 REST 사용) |
| `insecure` | `true`: HTTP 사용. `false`: HTTPS |

**운영 고려사항**

- Qdrant는 재시작 시 메모리 맵 파일로부터 컬렉션을 복구한다. 볼륨(`qdrant_storage`)이 유지되는 한 데이터가 보존된다.
- 컬렉션은 `embedding.vector_size`와 맞아야 한다. 모델을 변경하면서 `vector_size`도 바꾸면 기존 컬렉션과 충돌한다 — 컬렉션을 삭제하고 전체 재인덱싱이 필요하다.
- 대용량 컬렉션(수백만 벡터)에서는 Qdrant 메모리 사용량이 급격히 늘어날 수 있다. Qdrant 공식 권장: 벡터 차원 × 4바이트 × 벡터 수를 RAM으로 확보한다. bge-m3(1024차원), 50만 벡터 기준 약 2GB.

---

## 5. redis

인제스트·삭제 이벤트 큐 전용 Redis 연결 설정. API가 enqueue한 이벤트를 `event_queue_sensor`(Dagster 모드) 또는 `QueueWorker`(내장 워커 모드)가 소비해 파이프라인을 실행한다. Enterprise 배포는 같은 Redis를 역할 캐시, rate limit 카운터, 초대 로그인 체크에도 함께 쓴다.

```yaml
redis:
  host: "192.168.0.183"
  port: 6379
  password: "redis"
  db: 0
```

| 키 | 설명 |
|----|------|
| `host` | Redis 호스트 |
| `port` | Redis 포트 |
| `password` | Redis AUTH 비밀번호. 없으면 빈 문자열 |
| `db` | Redis DB 인덱스 (0~15) |

**운영 고려사항**

- 기본 설정은 RDB 스냅샷 모드다. Redis 비정상 종료 시 마지막 스냅샷 이후에 enqueue된 이벤트가 유실될 수 있다. 무중단 운영이 필요하면 AOF 활성화를 검토한다.
- Redis DB 인덱스를 변경하면 기존 큐 데이터가 보이지 않아 미처리 이벤트가 유실된다. 운영 중 변경은 금지한다.
- `password`는 `REDIS_PASSWORD` 환경변수로 주입하는 것을 권장한다.

---

## 6. queue_worker

인제스트 이벤트를 처리하는 워커 방식 선택.

```yaml
queue_worker:
  enabled: true
  max_workers: 5
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `true` | `true`: rag-api 내장 AsyncIO 워커 사용. `false`: Dagster 센서 사용 |
| `max_workers` | `5` | 내장 워커 모드에서 동시 처리 가능한 최대 문서 수 |

**운영 고려사항**

| 모드 | 장점 | 단점 |
|------|------|------|
| `enabled: true` (내장 워커) | 별도 인프라 불필요, 배포 단순 | 태스크 강제 종료 불가, Dagster UI에서 실행 이력 미확인, **커넥터 sync 자동 스케줄 미지원** |
| `enabled: false` (Dagster) | 실행 이력·실패 추적 가능, run 강제 종료 가능, 커넥터 sync 자동 스케줄 지원 | Dagster 컨테이너 필요 |

- `max_workers`는 `postgres.pool_size`, 임베딩 서버(Ollama) 처리 용량을 고려해 설정한다. 내장 워커 기준 워커 1개가 embed 단계에서 Ollama에 집중적으로 요청을 보낸다. Ollama가 단일 모델 단일 GPU 구성이라면 `max_workers: 3` 정도가 실질 한계인 경우가 많다.
- 내장 워커 모드에서 `status=running` 문서는 force-fail API로만 상태를 변경할 수 있으며 실제 AsyncIO 태스크는 종료되지 않는다. 태스크가 완료되면 상태를 덮어쓸 수 있으므로 주의한다.

---

## 7. queue_poll

Redis 큐 폴링 설정. Dagster 센서 모드에서는 Dagster가 독자적인 tick 간격을 사용하며 이 설정은 내장 워커 모드에만 적용된다.

```yaml
queue_poll:
  poll_interval_sec: 5
  max_per_poll: 5
  retry_interval_sec: 10
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `poll_interval_sec` | `5` | Redis 큐를 확인하는 주기(초) |
| `max_per_poll` | `5` | 한 번의 poll에서 꺼낼 최대 이벤트 수 |
| `retry_interval_sec` | `10` | 동일 문서가 이미 처리 중일 때 delay queue에서 재시도 대기 시간(초) |

**운영 고려사항**

- `max_per_poll`은 `queue_worker.max_workers`와 동일하거나 작게 설정한다. 크게 설정하면 워커보다 더 많은 이벤트를 꺼내서 일부가 즉시 delay queue로 밀린다.
- `poll_interval_sec`를 낮추면 응답성이 올라가지만 Redis 연결 빈도가 늘어난다. 5초는 대부분의 워크로드에서 적절하다.
- `retry_interval_sec`는 동시에 같은 문서가 업로드되었을 때 두 번째 요청이 얼마나 기다렸다가 재시도할지를 결정한다. 너무 낮으면 Redis delay sorted set의 조회 빈도가 높아진다.

---

## 8. provider

임베딩과 (Enterprise 전용) 이미지 캡셔닝이 공유하는 LLM/임베딩 백엔드 연결 설정.

```yaml
provider:
  name: "ollama"
  ollama_url: "http://localhost:11434"
  openai_api_key: ""
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `name` | `"ollama"` | `ollama`: 로컬 Ollama 서버. `openai`: OpenAI API — embedding, (Enterprise) `ingestion.image_captioning` 공통 |
| `ollama_url` | `"http://localhost:11434"` | Ollama 서버 주소 |
| `openai_api_key` | `""` | OpenAI provider 사용 시 필수 |

**운영 고려사항**

- `name`을 바꾸면 embedding과 image_captioning(Enterprise) 양쪽 모두 백엔드가 바뀐다 — 둘 중 하나만 다른 provider를 쓰고 싶다면 이 설정으로는 불가능하다(두 기능이 이 블록 하나를 공유).
- `openai_api_key`는 `OPENAI_API_KEY` 환경변수로 주입한다. 파일에 직접 기록하지 않는다.
- Ollama 모델은 첫 요청 시 모델 파일을 로드한다. 이 과정이 수십 초 걸릴 수 있다. 서비스 기동 직후 `/ready` 엔드포인트 확인 시 `ollama: false`가 나오면 모델 로딩 중인 경우다.

---

## 9. ingestion

파일 업로드 및 커넥터 수집 단계의 제한 설정.

```yaml
ingestion:
  max_file_size_mb: 10
  min_content_chars: 200
  html_extraction_policy: "lenient"
  parser_plugins: []
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `max_file_size_mb` | `10` | 파일 업로드 최대 크기(MB). 초과 시 422 반환 |
| `min_content_chars` | `200` | 웹 커넥터 전용. trafilatura 본문 추출 결과가 이 값 미만인 페이지는 저장 제외 |
| `html_extraction_policy` | `"lenient"` | `HTMLCleanReader`(`.html`/`.htm` 파싱)가 trafilatura로 본문을 추출할 때 애매한 블록(사이드바 경계 등)을 얼마나 적극적으로 포함시킬지 결정. `"strict"`/`"lenient"`/`"balanced"` 중 하나 |
| `parser_plugins` | `[]` | 파서 확장 레지스트리에 로드할 `"module.path:register_func"` 문자열 목록. 목록에 나열된 순서대로 import되어 각 `register()`가 실행되며, 기본 파서(PDF/DOCX/MD/TXT/HWP/HTML 등)를 교체하거나 새 확장자를 추가할 수 있다 |

**`html_extraction_policy` 값별 동작**

| 값 | 판단 기준 | 트레이드오프 |
|----|-----------|--------------|
| `"strict"` | 애매하면 제외 | 본문 일부가 boilerplate로 오판되어 손실될 수 있음 — 위키형 페이지(namu.wiki 등)에서 본문 90%+ 손실 실측됨 |
| `"balanced"` | 표준 임계치, 정책 전용 로직 미적용 | strict/lenient 중간값. 검증된 운영 데이터는 아직 없음 |
| `"lenient"` (기본값) | 애매하면 포함 | 라이선스 푸터 등 짧은 boilerplate가 본문에 섞여 들어올 수 있음(실측 확인) — 그러나 본문 손실보다는 검색 가능성을 우선한 선택 |

**운영 고려사항**

- `max_file_size_mb`를 크게 올리면 파싱·임베딩 시간이 선형 이상으로 늘어날 수 있다. 대용량 PDF(100MB+)는 LlamaIndex 파서가 메모리를 수백 MB 사용한다. 실제 필요 크기를 기준으로 보수적으로 설정한다.
- `min_content_chars`는 크롤 대상 사이트의 특성에 따라 조정한다. 짧은 페이지(FAQ, 카드형 UI)가 많은 사이트에서는 너무 높게 설정하면 유효한 문서가 걸러질 수 있다. 수집 결과를 확인한 후 조정한다.
- `html_extraction_policy`는 기본값(`"lenient"`)을 유지하는 것을 권장한다. 이전 기본값은 `"strict"`였으나, 위키형 페이지에서 본문 대부분이 boilerplate로 오판되어 검색이 아예 안 되는 사례가 실측되어 전환했다. 반대로 특정 사이트의 문서가 dedup에서 계속 오탐되거나 라이선스 푸터/네비게이션 문구가 검색 결과에 자주 섞여 나온다는 신호가 관찰되면 `"strict"` 또는 `"balanced"`로 전환해 재검증한다.
- 이미 `"strict"` 정책으로 인제스트된 기존 HTML 문서는 설정을 바꿔도 자동으로 재추출되지 않는다 — 재인제스트(reindex)가 필요하다.

**`parser_plugins`**

확장자 → 리더 매핑은 정적 상수가 아니라 등록 기반 레지스트리다. `parser_plugins`에는
"무엇을 로드할지"만 나열하며, 각 항목이 실제로 무엇을 등록/해제하는지는 그 모듈의
`register()` 코드에 있다 — 설정은 스위치 역할만 한다. 저장소 밖(비공개 패키지)의 모듈도
dotted path로 그대로 참조할 수 있다.

```yaml
ingestion:
  parser_plugins:
    - "ent_pkg.parsers.captioning:register"   # 1) 기본 등록 이후 실행 — .pdf 리더 교체 등
    - "ent_pkg.parsers.pptx:register"         # 2) 1)과 무관하게 별도 확장자 등록
```

- 목록 순서가 곧 로드 순서다 — 기본 파서가 먼저 등록된 뒤 목록이 순서대로 실행되므로, 뒤 항목이 앞 항목·기본 파서를 덮어쓸 수 있다.
- 각 항목은 프로세스 최초 `parse()` 호출 시 지연 로드된다(애플리케이션 startup 훅에 묶지 않음) — FastAPI/Dagster op/큐 워커/CLI 등 `parse()` 진입점이 여러 개이기 때문.
- Enterprise 배포는 이 메커니즘으로 이미지 캡셔닝/PDF OCR 폴백/표 구조 보존 파싱을 등록한다 —
  아래 [확장 필드](#확장-필드-ent) 참고.

### 확장 필드 [ENT]

`ingestion` 섹션에 Enterprise가 추가하는 세 하위 키. Core `Settings`에는 존재하지 않으며,
Core 단독 배포에서는 설정 파일에 넣어도 무시된다. 처리 흐름은
[파서 확장 처리 흐름](../concepts/ingestion-extensions.md), 설정 방법은
[이미지 캡셔닝·OCR 폴백](../guides/rag-ent/image-captioning-ocr-fallback.md)/
[표 구조 보존 파싱](../guides/rag-ent/table-layout-parsing.md) 참고.

```yaml
ingestion:
  image_captioning:
    enabled: false
    model: "qwen2.5vl:3b"
    temperature: 0.1
    max_images_per_doc: 20
    max_concurrent_tasks: 5
    default_language: ko

  pdf_ocr_fallback:
    enabled: false
    engine: rapidocr
    language: korean
    min_chars_per_page: 50

  table_layout:
    enabled: false
    scan_region_min_score: 0.5
    scan_region_fragment_merge_gap_pt: 20
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `image_captioning.enabled` | `false` | 이미지 캡셔닝 opt-in |
| `image_captioning.model` | `"qwen2.5vl:3b"` | 비전 모델 이름(`provider.name`에 맞는 모델). KB별 오버라이드 불가 |
| `image_captioning.temperature` | `0.1` | 캡션 재현성 확보를 위해 낮게 고정 |
| `image_captioning.max_images_per_doc` | `20` | 문서당 캡셔닝할 최대 이미지 수 |
| `image_captioning.max_concurrent_tasks` | `5` | 이미지별 VLM 호출 동시성 |
| `image_captioning.default_language` | `"ko"` | 언어 감지 불가 시(독립 이미지 파일) 쓰는 캡션 언어 |
| `pdf_ocr_fallback.enabled` | `false` | PDF OCR 폴백 opt-in |
| `pdf_ocr_fallback.engine` | `"rapidocr"` | 현재 유일한 값 |
| `pdf_ocr_fallback.language` | `"korean"` | RapidOCR `Rec.lang_type` 값 |
| `pdf_ocr_fallback.min_chars_per_page` | `50` | 페이지 평균 글자 수가 이 값 미만이면 스캔 문서로 판단 |
| `table_layout.enabled` | `false` | 표 구조 보존 파싱 opt-in |
| `table_layout.scan_region_min_score` | `0.5` | 스캔 페이지 표 영역 검출(RapidLayout) 신뢰도 임계값 |
| `table_layout.scan_region_fragment_merge_gap_pt` | `20` | 조각난 표 후보를 하나로 합칠 세로 간격(pt) 임계값 |

---

## 10. dedup

중복 문서 탐지 설정. 파이프라인에서 validate 단계 직후, parse 전에 실행된다. Stage별(SimHash/MinHash/chunk_compare) 하위 섹션으로 중첩되어 있다 — 어떤 값이 어느 단계 것인지 이름만으로 구분하기 위함이다.

중복 비교 대상은 **정상 색인된(`indexed`) 문서로 한정된다.** 이미 중복으로 처리되어 검색에서 제외된 문서(`outdated`)나 처리 중/실패/삭제된 문서는 비교 대상에 포함되지 않는다.

```yaml
dedup:
  enabled: true

  simhash:                                 # Stage1 - SimHash 근접 중복 탐지
    ngram: 3
    num_bands: 4
    simhash_bits: 64
    hamming_identical_threshold: 2
    hamming_similar_threshold: 5

  minhash:                                 # Stage2 - MinHash/제목 유사도 (Stage1 후보 없을 때만 실행)
    jaccard_threshold: 0.65
    title_fuzzy_threshold: 0.85
    title_only_min_jaccard_floor: 0.25
    user_words_path: "data/kiwi_user_words.tsv"

  chunk_compare:                           # Stage3 - 임베딩 기반 청크 단위 정밀 비교
    chunk_match_threshold: 0.50
    body_identical_threshold: 0.95
    body_similar_threshold: 0.75
    compare_all_candidates: false
```

### 작동 흐름

```
Stage 1 (SimHash)
  → hamming distance <= simhash.hamming_identical_threshold  → identical 판정 → 인덱싱 건너뜀
  → hamming distance <= simhash.hamming_similar_threshold    → Stage 3(chunk_compare)로 라우팅
  → 그 외                                                    → Stage 2 진입

Stage 2 (MinHash + pg_trgm, Stage1 후보 없을 때만)
  → MinHash Jaccard >= minhash.jaccard_threshold             → Stage 3(chunk_compare)로 라우팅
  → Title pg_trgm similarity >= minhash.title_fuzzy_threshold
    AND MinHash Jaccard >= minhash.title_only_min_jaccard_floor → Stage 3(chunk_compare)로 라우팅
  → 그 외                                                    → unique 판정 → 정상 인덱싱

Stage 3 (chunk_compare, Stage1/2가 "similar" 후보를 넘겼을 때만)
  → 임베딩 코사인 유사도 집계 점수(청크 수 비율로 스케일링됨) >= chunk_compare.body_identical_threshold → identical 판정
  → 집계 점수 >= chunk_compare.body_similar_threshold                                                → similar 판정 (기존 문서 outdated, 신규 색인)
  → 그 외                                                                                            → unique 판정 → 정상 인덱싱
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `true` | `false`로 설정하면 dedup 단계 전체 건너뜀 |
| **simhash** (Stage1) | | |
| `simhash.ngram` | `3` | SimHash 생성에 사용할 문자 n-gram 크기 |
| `simhash.num_bands` | `4` | SimHash 밴드 수. 클수록 후보 정밀도 증가, 처리량 감소 |
| `simhash.simhash_bits` | `64` | SimHash 해시 비트 수 (64 고정 권장) |
| `simhash.hamming_identical_threshold` | `2` | 이 값 이하이면 identical로 즉시 판정 |
| `simhash.hamming_similar_threshold` | `5` | 이 값 이하이면 Stage 3(chunk_compare)로 넘김 |
| **minhash** (Stage2) | | |
| `minhash.jaccard_threshold` | `0.65` | MinHash Jaccard 유사도 임계값 |
| `minhash.title_fuzzy_threshold` | `0.85` | 제목 유사도 임계값 (pg_trgm similarity) |
| `minhash.title_only_min_jaccard_floor` | `0.25` | 제목만으로 후보 판정할 때 본문 유사도 최솟값 |
| `minhash.user_words_path` | `""` | Kiwi 형태소 분석기 사용자 사전 경로 (빈 값 = 사용 안 함) |
| **chunk_compare** (Stage3) | | |
| `chunk_compare.chunk_match_threshold` | `0.50` | 청크쌍 필터 임계값 (Top-1 매칭 최소 점수) |
| `chunk_compare.body_identical_threshold` | `0.95` | 집계 점수가 이 값 이상이면 body=identical |
| `chunk_compare.body_similar_threshold` | `0.75` | 집계 점수가 이 값 이상(identical 미만)이면 body=similar |
| `chunk_compare.compare_all_candidates` | `false` | `false`=best match 1건만 정밀 비교, `true`=후보 전체 순회 |

**운영 고려사항**

- `hamming_identical_threshold`와 `hamming_similar_threshold`는 역전되어서는 안 된다 (`identical <= similar`).
- `jaccard_threshold`를 낮추면 더 느슨하게 중복을 판정한다. 도메인 특화 문서(법령, 기술 문서 등)에서는 유사 표현이 많아 0.5 이하로 낮추면 오탐이 늘어날 수 있다.
- `user_words_path`는 Kiwi 형태소 분석기가 인식하지 못하는 고유명사·약어를 등록하는 용도다. 정확도를 높이려면 도메인 사전을 작성해 경로를 설정한다.
- `enabled: false`는 dedup 전체를 끄므로 성능 이슈 디버깅 외에는 운영 중 사용하지 않는다.

---

## 11. chunking

문서를 검색 가능한 청크로 분할하는 방식 설정.

```yaml
chunking:
  strategy: "recursive"
  chunk_size: 1024
  chunk_overlap: 128
  min_chunk_chars: 30
  semantic_threshold: 0.8
  code_max_chars: 1500
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `strategy` | `"recursive"` | `recursive`: 구분자 기반 재귀 분할. `semantic`: 임베딩 유사도 기반 분할. `hierarchical`: parent-child 계층 분할 — 검색 시 [§13 retrieval](#13-retrieval)의 `auto_merge`와 짝을 이룬다 |
| `chunk_size` | `1024` | `strategy`가 `recursive`/`semantic`이면 청크당 최대 문자 수(단일 int, 64~8192). `hierarchical`이면 큰 것→작은 것 내림차순 리스트(예: `[2048, 512, 128]`, 최소 2레벨, 각 항목 64~8192) — 마지막 값이 실제 검색 대상인 leaf 청크 크기다 |
| `chunk_overlap` | `128` | 인접 leaf 청크 간 겹치는 문자 수. `hierarchical`에서도 leaf 레벨에만 적용되고 root/mid 레벨은 겹치지 않는다(`HierarchicalNodeParser`가 레벨별로 다른 overlap을 지원하지 않기 때문). 가장 작은 `chunk_size`(leaf) 대비 15%를 넘는 값은 저장/로드 시점에 거부된다 |
| `min_chunk_chars` | `30` | 분할 후 이 값보다 짧은 청크는 버림. `hierarchical`에서는 이 필터로 제외된 leaf가 parent의 자식 수 계산에서도 제외된다 |
| `semantic_threshold` | `0.8` | `semantic` 전략에서 청크를 합칠 유사도 임계값 |
| `code_max_chars` | `1500` | GitHub 소스코드 파일(`.py`/`.ts`/`.go` 등)에 적용하는 `CodeSplitter` 청크 최대 문자 수 |

**hierarchical 예시**

```yaml
chunking:
  strategy: "hierarchical"
  chunk_size: [2048, 512, 128]   # root -> mid -> leaf, 내림차순
  chunk_overlap: 16              # leaf(128)의 15% 이내
```

**운영 고려사항**

- `chunk_size`는 임베딩 모델의 입력 길이 제한에 맞게 설정한다. bge-m3의 토큰 제한은 8192이며, 1024는 여유롭게 맞는 크기다. `text-embedding-3-small`은 8191 제한이므로 유사하다. `hierarchical`도 레벨마다 동일한 제한을 받는다.
- `chunk_overlap`을 늘리면 청크 경계에서 의미가 끊어지는 문제를 줄일 수 있지만 청크 수가 늘어나 Qdrant 스토리지와 검색 비용이 증가한다. `chunk_size`(hierarchical은 leaf 기준)의 10~15% 수준이 일반적이며, 15%를 넘으면 설정 자체가 거부된다.
- `semantic` 전략은 recursive 대비 임베딩 호출이 추가로 발생해 청킹 속도가 느려진다. 대량 문서 환경에서는 비용·속도 트레이드오프를 확인한 후 사용한다.
- `min_chunk_chars`는 목차, 헤더만 있는 청크가 인덱싱되는 것을 방지한다. 너무 높게 설정하면 유효한 짧은 내용이 버려질 수 있다.
- `hierarchical`은 기존에 이미 인덱싱된 문서를 소급 재청킹하지 않는다 — 전략을 바꾸면 그 이후 새로 업로드/재인덱싱하는 문서부터 적용된다.
- 이 섹션 전체는 KB별로 오버라이드 가능하다 — [API Guide §3 KB 설정 오버라이드](api-guide.md#kb-설정-오버라이드) 참고.

---

## 12. embedding

임베딩 모델 설정. dense 벡터 생성에 사용하며, sparse는 클라이언트가 TF만 계산하고 IDF는 Qdrant 서버가 코퍼스 기반으로 자동 관리한다. 백엔드 연결 정보(`ollama_url`/`openai_api_key`)는 [§8 provider](#8-provider)로 분리되어 있다 — 여기는 모델명/차원수만 다룬다.

```yaml
embedding:
  model: "bge-m3"
  vector_size: 1024
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `model` | `"bge-m3"` | `provider.name`(§8)에 맞는 모델명. ollama: `bge-m3` 등, openai: `text-embedding-3-small` 등 |
| `vector_size` | `1024` | Dense 벡터 차원수. 모델과 일치해야 함 |

**모델별 vector_size**

| 모델 | provider.name | vector_size |
|------|----------|-------------|
| `bge-m3` | ollama | `1024` |
| `nomic-embed-text` | ollama | `768` |
| `text-embedding-3-small` | openai | `1536` |
| `text-embedding-ada-002` | openai | `1536` |

**운영 고려사항**

- `vector_size`를 잘못 설정하면 Qdrant 컬렉션 생성 시 `ConfigError`로 기동이 실패한다. 모델 변경 시 반드시 함께 수정한다.
- **모델 변경은 전체 재인덱싱을 수반한다.** 기존 Qdrant 컬렉션은 이전 차원으로 생성되어 있으므로 삭제 후 재생성해야 한다. KB별 `DELETE /api/kb/{id}` 후 재생성 → `POST /api/kb/{id}/reindex?force=true` 순서로 진행한다.
- `model`을 바꿀 때 `provider.name`(§8)이 실제 그 모델을 제공하는 백엔드로 맞춰져 있는지 함께 확인한다.

---

## 13. retrieval

검색 방식과 파라미터 설정. `auto_merge`를 제외한 나머지는 검색 요청의 `options` 필드로 요청 단위 오버라이드가 가능하다(우선순위: 요청값 > 이 전역 설정값). `auto_merge`만 KB 단위로도 오버라이드할 수 있다 — [API Guide §3 KB 설정 오버라이드](api-guide.md#kb-설정-오버라이드) 참고. 여러 KB를 한 요청으로 합쳐 검색할 때 병합(RRF)과 리랭크는 병합된 결과 전체에 대해 정확히 한 번만 일어나므로, `auto_merge` 외 나머지 필드는 KB별로 다른 값을 가질 수 없다.

```yaml
retrieval:
  mode: "hybrid"
  top_k: 5
  hybrid:
    alpha: 0.5
    rrf_k: 60
  similarity:
    min_score: 0.0
  rerank:
    enabled: false
    provider: "jina"
    api_key: ""
    model: "jina-reranker-v2-base-multilingual"
    top_n: 3
    timeout_sec: 5
    fallback_on_error: true
  auto_merge:
    enabled: false
    merge_threshold: 0.5
```

### 기본 설정

| 키 | 기본값 | 설명 |
|----|--------|------|
| `mode` | `"hybrid"` | `hybrid`: dense + sparse RRF. `similarity`: dense 코사인 유사도만 사용 |
| `top_k` | `5` | 반환할 최대 청크 수 |

### hybrid 설정

| 키 | 기본값 | 설명 |
|----|--------|------|
| `alpha` | `0.5` | Dense와 Sparse의 가중치 비율. `1.0` = Dense 100%, `0.0` = Sparse(키워드) 100% |
| `rrf_k` | `60` | RRF 점수 공식 `1/(k+rank)`의 k값. 클수록 상위 순위와 하위 순위의 점수 차이가 줄어듦 |

**운영 고려사항 (hybrid)**

- `alpha: 0.5`는 중립 출발점이다. 키워드 일치가 중요한 도메인(법령, 기술 명세)에서는 `0.3` 이하로, 의미 검색이 중요한 도메인(QA, 요약)에서는 `0.7` 이상으로 조정을 검토한다.
- `rrf_k: 60`은 업계 표준값이다. 변경 효과가 미미하므로 특별한 이유 없이 바꾸지 않는다.
- hybrid 모드에서 `min_score`는 적용되지 않는다. 결과 수 제어는 `top_k`만으로 한다.

### similarity 설정

| 키 | 기본값 | 설명 |
|----|--------|------|
| `min_score` | `0.0` | 이 값 미만의 코사인 유사도 결과를 제외. `0.0`은 필터 없음 |

**운영 고려사항 (similarity)**

- `min_score: 0.0`은 관련성이 낮은 결과도 모두 반환한다. 품질 확인 후 `0.4`~`0.6` 수준으로 올리는 것을 권장한다.
- bge-m3 기준 코사인 유사도 0.5 이하는 대체로 주제가 다른 문서다. 도메인에 따라 기준이 달라지므로 실제 검색 결과를 모니터링하며 조정한다.

### rerank 설정

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `false` | 리랭킹 활성화 여부 |
| `provider` | `"jina"` | 현재 `jina`만 지원 |
| `api_key` | `""` | Jina API 키 |
| `model` | `"jina-reranker-v2-base-multilingual"` | Jina 리랭킹 모델 |
| `top_n` | `3` | 리랭킹 후 반환할 최종 결과 수 |
| `timeout_sec` | `5` | Jina API 응답 타임아웃(초) |
| `fallback_on_error` | `true` | Jina 호출 실패 시 RRF 점수 순으로 대체 반환 |

**운영 고려사항 (rerank)**

- `enabled: true`로 변경하면 검색 응답 시간이 Jina API 왕복 시간(통상 200~500ms)만큼 늘어난다. 지연 허용치를 확인한 후 활성화한다.
- `fallback_on_error: true`를 유지하면 Jina API가 일시 다운돼도 검색 자체는 중단되지 않는다. 다만 리랭킹 품질 없이 RRF 점수로 반환된다.
- `api_key`는 `RERANKER_API_KEY` 환경변수로 주입한다.
- `top_n`은 `top_k`보다 작아야 의미가 있다. 리랭킹은 `top_k` 결과를 재순위 매긴 뒤 상위 `top_n`개만 반환한다.

### auto_merge 설정

parent-child 계층 청킹([§11 chunking](#11-chunking)의 `strategy: "hierarchical"`)으로 인덱싱된 문서에서, 검색된 leaf 청크들을 상위(parent) 텍스트로 자동 병합해 반환할지 결정한다. `chunking.strategy`(저장 구조)와는 독립된 별도 스위치다 — 구조는 hierarchical로 저장해두고 병합만 따로 껐다 켤 수 있다.

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `false` | 자동 병합 활성화 여부 |
| `merge_threshold` | `0.5` | 같은 parent 아래 검색된 child 비율이 이 값 이상이면 parent 텍스트로 병합. 미만이면 개별 child 결과를 그대로 반환 |

**운영 고려사항 (auto_merge)**

- `chunking.strategy`가 `hierarchical`이 아닌 문서에는 `parent_chunk_id`가 없으므로 `enabled: true`여도 영향이 없다.
- `merge_threshold`를 낮추면 더 쉽게 병합돼 문맥은 풍부해지지만 반환 텍스트 길이가 늘어난다. 높이면 더 정밀한 개별 청크가 유지된다.
- 3-level 이상 계층에서는 레벨을 타고 올라가며 반복 병합되고, 한 레벨에서 threshold 미달로 병합에 실패한 결과는 상위 레벨에서 재시도되지 않는다.
- 검색 응답의 `merged`/`parent_chunk_id` 필드는 [API Guide §13 검색 — 응답 필드](api-guide.md#응답-필드)에서 다룬다.
- `retrieval` 중 이 필드만 KB별로 오버라이드 가능하다(`retrieval.auto_merge.enabled`, `retrieval.auto_merge.merge_threshold`) — [API Guide §3](api-guide.md#kb-설정-오버라이드) 참고.

---

## 14. knowledge_bases

시스템에 사전 등록할 KB 목록. 서버 기동 시 DB에 없는 KB를 자동 생성한다.

```yaml
knowledge_bases:
  - id: "kb-01"
    name: "지식베이스 01"
    description: "첫 번째 지식베이스입니다."
    tags: ["general"]
  - id: "kb-02"
    name: "지식베이스 02"
    description: "두 번째 지식베이스입니다."
```

| 키 | 필수 | 설명 |
|----|------|------|
| `id` | 필수 | KB 고유 식별자. 생성 후 변경 불가 |
| `name` | 선택 | 표시 이름 |
| `description` | 선택 | 설명 |
| `tags` | 선택 | 태그 목록 |

**운영 고려사항**

- 이 목록은 초기 생성용이다. 이미 존재하는 KB는 기동 시 변경되지 않는다. KB 수정은 `PATCH /api/kb/{id}` API를 사용한다.
- KB를 목록에서 제거해도 실제 DB에서 삭제되지 않는다. KB 삭제는 `DELETE /api/kb/{id}` API로 명시적으로 수행한다.
- 환경별로 KB 구성이 달라야 하면 `docker/settings.yaml`을 환경별로 분리하거나 환경변수 오버라이드를 활용한다.

---

## 15. mcp

Model Context Protocol 서버 설정. AI 에이전트가 rag-api를 툴로 사용할 수 있게 한다.

```yaml
mcp:
  enabled: true
  transport: streamable-http
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `true` | MCP 엔드포인트 활성화 여부 |
| `transport` | `streamable-http` | `stdio` / `sse` / `streamable-http` |

**운영 고려사항**

- `streamable-http`는 HTTP 기반으로 서버 재시작 없이 클라이언트가 재연결할 수 있다. VS Code, Claude Desktop 등 대부분의 MCP 클라이언트가 지원한다.
- `stdio`는 단일 프로세스 환경(CLI 실행)에서만 유용하다. 서버 모드로 배포할 때는 사용하지 않는다.
- `enabled: false`로 설정하면 `/mcp` 경로가 비활성화된다. MCP를 사용하지 않는 배포에서는 불필요한 엔드포인트를 닫는 용도로 사용한다.

---

## 16. tracing

Langfuse 기반 LLM 추적 설정. 임베딩 호출 및 검색 파이프라인의 trace를 기록한다.

```yaml
tracing:
  enabled: true
  langfuse_baseurl: "http://langfuse-web.llm.svc.cluster.local:3000"
  langfuse_public_key: "pk-lf-..."
  langfuse_secret_key: "sk-lf-..."
  service_name: "rag-api"
```

| 키 | 설명 |
|----|------|
| `enabled` | `false`로 설정하면 Langfuse 클라이언트를 초기화하지 않음 |
| `langfuse_baseurl` | Langfuse 서버 주소 |
| `langfuse_public_key` | Langfuse 프로젝트 퍼블릭 키 |
| `langfuse_secret_key` | Langfuse 프로젝트 시크릿 키 |
| `service_name` | Langfuse trace에 표시되는 서비스 이름 |

**운영 고려사항**

- `enabled: false`이면 Langfuse 서버가 없어도 정상 동작한다. Langfuse 없이 배포할 때는 반드시 `false`로 설정한다. `true`인 상태에서 서버가 없으면 추적 전송 시 연결 오류가 로그에 반복 출력될 수 있다.
- `langfuse_secret_key`는 `TRACING_LANGFUSE_SECRET_KEY` 환경변수로 주입한다.
- `service_name`은 동일 Langfuse 프로젝트에 여러 서비스가 연결될 때 trace를 구분하는 레이블이다.

---

## 17. logging

애플리케이션 로그 레벨 설정.

```yaml
logging:
  level: INFO
```

| 값 | 설명 |
|----|------|
| `DEBUG` | 모든 내부 처리 로그. 파이프라인 각 단계 입출력 포함 |
| `INFO` | 일반 운영 로그. 문서 처리 시작·완료, API 요청 기록 |
| `WARNING` | 비정상 상황이지만 처리는 계속되는 경우 |
| `ERROR` | 처리 실패, 예외 발생 |

**운영 고려사항**

- `DEBUG`는 로그 볼륨이 크게 늘어난다. 트러블슈팅 이후에는 반드시 `INFO`로 되돌린다.
- `WARNING` 이상의 로그는 반드시 원인을 확인한다. `WARNING`은 MinIO delete 실패처럼 의도된 silent-fail 케이스에도 출력된다.
- 로그 레벨은 환경변수 오버라이드가 없다. `settings.yaml`의 `logging.level`을 직접 수정하고 컨테이너를 재시작해야 반영된다.

---

## 18. oidc [ENT]

Keycloak OIDC 연동 설정. 클라이언트·그룹 구성 절차는 [SSO·인증 설정](../guides/rag-ent/sso-and-auth-setup.md) 참고.

```yaml
oidc:
  issuer_url: "https://<keycloak 도메인>/realms/<realm>"
  audience: ""
  jwks_cache_ttl_seconds: 3600
  admin_url: ""
  admin_client_id: ""
  admin_client_secret: ""
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `issuer_url` | `""` | Keycloak realm 발급자 URL. JWKS 조회와 JWT `iss` 검증에 쓰인다 |
| `audience` | `""` | 비어 있으면 `aud` claim 미검증. 값을 채우면 Keycloak 클라이언트에 Audience mapper가 있어야 한다 |
| `jwks_cache_ttl_seconds` | `3600` | JWKS 캐시 유효 시간(초) |
| `admin_url` | `""` | Keycloak Admin API 베이스 URL. 비어 있으면 이메일 조회가 항상 미가입으로 처리된다 |
| `admin_client_id` / `admin_client_secret` | `""` | Admin API용 confidential 클라이언트 자격증명. `OIDC_ADMIN_CLIENT_ID`/`OIDC_ADMIN_CLIENT_SECRET` 환경변수로 주입 |

---

## 19. authz [ENT]

KB 단위 RBAC 관련 설정. 역할 판정 경로와 role 계층은 [접근 제어](../concepts/access-control.md) 참고.

```yaml
authz:
  super_admin_role: "rag-super-admin"
  role_cache_ttl_seconds: 60
  invite_expiry_days: 7
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `super_admin_role` | `"rag-super-admin"` | JWT `groups` claim에서 슈퍼관리자 여부를 판정하는 그룹명 |
| `role_cache_ttl_seconds` | `60` | Redis에 캐시하는 KB 역할·접근 가능 KB 목록의 TTL. 역할 변경 시에는 캐시가 즉시 무효화되므로, 이 TTL은 무효화가 누락된 경우의 보수적 상한이다 |
| `invite_expiry_days` | `7` | 이메일 초대의 유효 기간(일) |

`kb_authz_enabled`(RBAC 전체 on/off)는 이 섹션의 설정값이 아니라 `GET`/`PATCH /api/admin/config`로
런타임에 토글하는 시스템 설정이다 — [API Guide §6.4](api-guide.md)와
[SSO·인증 설정의 RBAC 활성화](../guides/rag-ent/sso-and-auth-setup.md#rbac-활성화) 참고.

---

## 20. smtp [ENT]

멤버 초대·역할 부여 이메일 발송 설정. 다른 Enterprise 기능은 SMTP에 의존하지 않는다. 상세는
[멤버십·초대·소유권 관리의 알림 메일 설정](../guides/rag-ent/membership-and-invites.md#알림-메일-설정-smtp) 참고.

```yaml
smtp:
  host: "localhost"
  port: 1025
  username: ""
  password: ""
  from_address: "noreply@rag-ent-api.local"
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `host` / `port` | `"localhost"` / `1025` | SMTP 서버 주소. 기본값은 로컬 개발용 mailpit |
| `username` / `password` | `""` | 비어 있으면 인증 없이 발송(mailpit 등). `SMTP_USERNAME`/`SMTP_PASSWORD` 환경변수로 주입 |
| `from_address` | `"noreply@rag-ent-api.local"` | 발신자 주소 |

**운영 고려사항**: mailpit은 메일을 외부로 보내지 않고 가두는 개발용 도구다. 운영 환경은
반드시 실제로 발송 가능한 SMTP 서버로 교체한다.

---

## 21. rate_limit [ENT]

사용자별 API 요청 제한 설정. 규칙 매칭·카운팅 방식은
[사용자별 요청 제한](../guides/rag-ent/rate-limiting.md) 참고.

```yaml
rate_limit:
  enabled: true
  rules:
    - name: search
      paths: ["/api/search"]
      limit: "10/second"
    - name: upload
      paths: ["/api/kb/*/docs/upload", "/api/kb/*/docs/upload/batch"]
      limit: "30/minute"
      weights:
        "/api/kb/*/docs/upload/batch": 10
  default: "120/minute"
  exempt_paths: ["/health", "/ready", "/docs", "/redoc", "/openapi.json"]
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `enabled` | `false` | opt-in. 꺼져 있으면 미들웨어가 요청을 세지 않고 통과시킨다 |
| `rules[].paths` | — | `*`는 경로 세그먼트 하나와 매칭 |
| `rules[].weights` | `{}` | 특정 경로 호출 1건을 몇 건으로 셀지 |
| `default` | `"120/minute"` | 어떤 `rules`에도 매칭되지 않는 나머지 경로의 기본 한도 |
| `exempt_paths` | 헬스체크·문서 경로 | 카운터 자체를 건드리지 않는 경로 |
