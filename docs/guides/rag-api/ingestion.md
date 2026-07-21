---
sidebar_position: 3
---

# 인제스트 파이프라인

업로드되거나 [커넥터](connectors.md)가 가져온 문서는 Validate → Parse → Dedup → Chunk →
Embed → Upsert → Meta 7단계를 거쳐 검색 가능한 상태가 된다. 단계 구성 자체([아키텍처](../../concepts/architecture.md#pipeline-layer))와
각 단계가 어느 저장소를 건드리는지([인제스트 흐름](../../concepts/data-flow.md#인제스트-흐름))는
개념 문서에서 다룬다. 여기서는 각 단계를 실제로 조정하는 `settings.yaml` 키와 그 효과를
정리한다.

`ingestion` / `chunking` / `dedup` 세 섹션은 [KB별로 오버라이드](kb.md#kb별-설정-오버라이드)할
수 있다. 반면 `provider` / `embedding`은 오버라이드 대상이 아닌 전역 전용 설정이다 — 임베딩
모델이 KB마다 다르면 Qdrant 컬렉션의 벡터 차원이 KB마다 달라져야 하기 때문이다.

---

## Validate 단계

업로드되거나 커넥터가 가져온 파일이 `max_file_size_mb`를 넘으면 파이프라인에 들어가기 전에
거부한다.

```yaml
ingestion:
  max_file_size_mb: 10   # 1-1024
```

파일 크기가 이 값을 초과하면 큐 소비 직후, parse로 넘어가기 전에 `IngestValidationError`
(422)로 거부된다. 커넥터가 가져온 문서도 동일하게 적용된다 — 크기 제한은 소스와 무관하게
파이프라인 레벨에서 한 번만 걸린다.

## Parse 단계

HTML 문서에서 본문을 얼마나 보수적으로 추출할지, 그리고 새 파일 형식을 코드 수정 없이 어떻게
등록할지를 정한다.

```yaml
ingestion:
  html_extraction_policy: "lenient"   # strict | lenient | balanced
  parser_plugins: []
```

### HTML 추출 정책

`html_extraction_policy`는 HTML 문서(웹/Confluence 커넥터 산출물 포함)에서 본문을 추출할 때
애매한 블록을 어떻게 다룰지 정한다.

| 값 | 동작 |
|----|------|
| `strict` | 애매한 블록은 제외 — 짧지만 확실한 본문만 남긴다 |
| `lenient` | 애매한 블록도 포함 — 본문 손실은 최소화되지만 짧은 boilerplate가 섞일 수 있다 |
| `balanced` | 두 정책의 중간 |

### 파서 플러그인 확장

`parser_plugins`는 확장자별 리더를 코드 수정 없이 추가·교체하는 확장점이다. 기본으로 문서류
17종 리더(PDF/Office/HWP/HTML/텍스트 등)와 코드·설정 파일 확장자를 합쳐 36개 확장자가
등록되어 있으며, 등록·교체 메커니즘 자체는 [파서 레지스트리](../../concepts/data-flow.md#파서-레지스트리)에서
다이어그램으로 설명한다. 실제로 확장하려면 `register(ext, reader)` 시그니처를 따르는 함수를
만들고 그 경로를 나열하면 된다.

```yaml
ingestion:
  parser_plugins:
    - "my_plugins.readers:register"
```

기동 시 목록 순서대로 호출되며, 같은 확장자를 여러 플러그인이 등록하면 나중에 실행된 쪽이
이긴다(last-writer-wins). `parser_plugins` 자체는 배포 타임에 고정되는 설정이라 KB별
오버라이드 대상에서 제외된다.

## Dedup 단계

새 문서 A를 기존 문서와 비교해 완전 동일/제목 변경/유사 여부를 저비용 검사부터 순서대로
판정한다.

```yaml
dedup:
  enabled: true
  simhash:       { hamming_identical_threshold: 2, hamming_similar_threshold: 5 }
  minhash:       { jaccard_threshold: 0.65, title_fuzzy_threshold: 0.85 }
  chunk_compare: { chunk_match_threshold: 0.50, body_identical_threshold: 0.95, body_similar_threshold: 0.75 }
```

`dedup.enabled: false`면 이 단계 전체를 건너뛰고 바로 chunk로 넘어간다. 코드/설정 파일
확장자(`.py`, `.yaml` 등)는 dedup 대상이 아니다 — 산문 본문 비교이므로 PDF/Office/HTML 같은
문서류 확장자에만 실행된다.

### 탐지 흐름

앞 차수가 후보를 못 찾으면 다음 차수로 넘어가고, `similar` 후보까지만 나오면 3차가 그
후보 하나를 정밀 비교해 최종 확정하는 깔때기 구조다.

```
new document A
   │
   ▼
stage 1: SimHash — title SHA-256 exact match + body Hamming distance
   │
   ├─ distance <= hamming_identical_threshold ──► identical_level (title: same/changed)
   ├─ distance <= hamming_similar_threshold   ──► similar candidate
   └─ no candidate
        │
        ▼
   stage 2: MinHash + title fuzzy match — only if stage 1 found nothing
        │
        ├─ Jaccard >= jaccard_threshold, or
        │  (title_sim >= title_fuzzy_threshold and Jaccard >= title_only_min_jaccard_floor)
        │       ──► similar candidate
        └─ otherwise ──► none → index normally
             │
             ▼  (only for a similar candidate, from stage 1 or 2)
   stage 3: chunk-level comparison — Top-1 match per chunk vs the
            candidate's chunks in Qdrant, coverage-weighted average x chunk_ratio
             │
             ├─ score >= body_identical_threshold ──► identical_level (title recomputed)
             ├─ score >= body_similar_threshold    ──► similar
             └─ score <  body_similar_threshold     ──► none → index normally
```

### 차수별 동작

- **1차 — SimHash**: body Hamming distance와 title SHA-256 완전 일치를 비교한다. 저비용
  근사 비교라 대부분의 신규 문서가 여기서 후보 없음으로 끝나며, `identical_level`을 그
  자리에서 직접 확정할 수 있는 유일한 차수다(이때 `title_match`도 함께 결정된다).
- **2차 — MinHash**: 1차가 후보를 못 찾았을 때만 실행되는 보조 필터로, Jaccard
  유사도(128개 MinHash 시그니처)와 제목 fuzzy match로 `similar` 후보만 걸러낸다. 근사치라
  완전 동일 여부까지는 판정하지 않는다.
- **3차 — chunk 비교**: 1·2차가 넘긴 `similar` 후보 하나(기본값,
  `compare_all_candidates: true`면 전체 후보)에 대해서만 Qdrant 검색과 임베딩 계산을
  동반하는 정밀 비교를 수행한다. `title_match`도 이 차수에서 최종 후보를 대상으로 다시
  계산한다 — 1차에서 확정된 경우가 아니면 "미확인" 상태로 남아 있어서, 그대로 두면
  제목이 실제로 바뀐 문서까지 "완전 동일"로 오판되기 때문이다.

### 3차 집계 점수

A의 전체 청크 수 N을 분모로 고정한 커버리지 가중 평균이다.

```
raw_score(A, C) = (매칭된 청크들의 Qdrant Top-1 점수 합) / N
chunk_ratio     = min(A 청크 수, C 청크 수) / max(A 청크 수, C 청크 수)
score(A, C)     = raw_score(A, C) * chunk_ratio
```

매칭 안 된 청크도 0점으로 분모에 남기 때문에 "몇 개 중 몇 개가 겹쳤는지"가 그대로 점수에
반영된다. `chunk_ratio`는 짧은 문서가 훨씬 긴 문서의 일부와만 겹쳐도 `raw_score`가 1.0에
가깝게 나오는 문제(포함 관계를 동일 문서로 오판)를 보정한다 — 두 문서의 청크 수 차이가
클수록 최종 점수를 깎는다.

### 판정 결과 처리

최종 판정은 `doc_created_at`이 더 최신인 문서가 이기는 방식으로 문서 `status`를 바꾼다.

| 판정 | 결과 |
|------|------|
| `none` | 정상 색인 진행 |
| `identical_level` + title 동일 | A → `outdated`(`duplicate_of`=기존 문서), 기존 문서는 변경 없음 |
| `identical_level` + title 변경, A가 최신 | 기존 문서 청크의 Qdrant payload(`doc_id`/`title`/`source`)만 A로 이전(재임베딩 없음), 기존 문서 → `outdated`, A → `indexed` |
| `identical_level` + title 변경, 기존 문서가 최신 | A → `outdated`만, 기존 문서는 변경 없음 |
| `similar`, A가 최신 | 기존 문서의 Qdrant 청크를 삭제하고 → `outdated`, A는 표준 경로로 재색인 |
| `similar`, 기존 문서가 최신 | A → `outdated`(색인하지 않음), 기존 문서는 변경 없음 |

상태 전이 관점은
[dedup 판정과 outdated 전이](../../concepts/document-lifecycle.md#dedup-판정과-outdated-전이)
참고.

### 임계값 튜닝

| 차수 | 필드 | 범위 | 의미 |
|------|------|------|------|
| SimHash | `hamming_identical_threshold` | `0‑19` | 이 값 이하 Hamming 거리 → `identical_level` |
| SimHash | `hamming_similar_threshold` | `0‑19` | 이 값 이하 거리(위 임계값 초과분) → `similar` 후보. 이 값도 넘으면 후보에서 제외 |
| MinHash | `jaccard_threshold` | `0.0‑1.0` | 128개 MinHash 시그니처 중 일치 비율이 이 값 이상이면 `similar` |
| MinHash | `title_fuzzy_threshold` | `0.0‑1.0` | 제목 유사도가 이 값 이상이고 Jaccard가 `title_only_min_jaccard_floor` 이상이면 `similar`(본문 유사도가 낮아도 제목만으로 후보 인정) |
| <span style={{whiteSpace: "nowrap"}}>chunk 비교</span> | `chunk_match_threshold` | `0.0‑1.0` | 청크 단위 임베딩 코사인 유사도가 이 값 이상인 청크만 매칭으로 인정 |
| <span style={{whiteSpace: "nowrap"}}>chunk 비교</span> | `body_identical_threshold` | `0.0‑1.0` | 집계 점수가 이 값 이상 → `identical_level` |
| <span style={{whiteSpace: "nowrap"}}>chunk 비교</span> | `body_similar_threshold` | `0.0‑1.0` | 집계 점수가 이 값 이상 → `similar` |

임계값은 올릴수록 "유사" 판정 폭이 넓어져 과다 탐지 위험이, 낮출수록 후보가 좁아져 누락
위험이 커진다. `simhash.ngram`/`num_bands`/`simhash_bits`와 `minhash.user_words_path`는
기존 문서 지문과 계산 방식이 어긋나면 안 되므로 KB별 오버라이드 대상에서 제외된다.

## Chunk 단계

파싱된 문서를 얼마나 잘게 나눠 임베딩할지 정한다 — 일반 문서는 `recursive`/`semantic` 중
선택하고, 코드 파일은 항상 전용 분할기를 쓴다.

```yaml
chunking:
  strategy: "recursive"   # recursive | semantic
  chunk_size: 1024        # 64-8192
  chunk_overlap: 128      # 0-8191
  min_chunk_chars: 30     # 1-2000
  semantic_threshold: 0.8 # 0.0-1.0, semantic 전략에서만 사용
  code_chunk_lines: 40           # 5-500
  code_chunk_lines_overlap: 5    # 0-499
```

### 청킹 전략

| 전략 | 동작 |
|------|------|
| `recursive` | `SentenceSplitter` — `chunk_size`/`chunk_overlap` 글자 수 기준 분할. 추가 API 호출 없음 |
| `semantic` | `SemanticSplitterNodeParser` — 문장 임베딩 유사도가 `semantic_threshold`(백분위) 밑으로 떨어지는 지점에서 분할. 청킹 단계에서 임베딩 모델을 호출하므로 `recursive`보다 느리고 비용이 든다 |

분할 후 `min_chunk_chars`보다 짧은 청크는 (코드/atomic 청크를 포함해) 모두 버려진다 — 문장
경계가 애매해 생기는 한두 글자짜리 파편이 검색 인덱스에 섞이는 것을 막기 위한 하한선이다.

### 코드 파일 처리

`strategy`는 코드/설정 파일이 아닌 일반 문서에만 적용된다 — `.py`/`.ts`/`.yaml` 같은
확장자는 `strategy` 설정과 무관하게 항상 `CodeSplitter`로 자동 라우팅되고,
`code_chunk_lines`/`code_chunk_lines_overlap`(줄 수 기준)으로 크기를 조절한다.

## Embed 단계

청크마다 dense 벡터(의미 검색용)와 sparse 벡터(키워드 검색용)를 계산해 주입한다.

```yaml
provider:
  name: "ollama"          # ollama | openai
  ollama_url: "http://localhost:11434"
  openai_api_key: ""

embedding:
  model: "bge-m3"          # ollama: bge-m3 / openai: text-embedding-3-small
  vector_size: 1024         # bge-m3=1024, text-embedding-3-small/ada-002=1536
```

### 프로바이더와 모델

Dense 임베딩은 `provider.name`이 가리키는 프로바이더(Ollama 또는 OpenAI)로 계산되고,
Sparse(BM25) 임베딩은 FastEmbed로 별도 계산되어 두 벡터가 `asyncio.gather`로 병렬 처리된다.

### vector_size 주의사항

`vector_size`는 실제 모델의 출력 차원과 반드시 일치해야 한다 — Qdrant 컬렉션은 KB가 처음
쓰일 때 이 값으로 생성되고, 이후 `vector_size`를 바꾸면 기존 컬렉션의 차원과 어긋나
`ConfigError`(500)로 즉시 실패한다. 이미 문서가 색인된 KB에서 임베딩 모델을 바꾸려면
컬렉션을 새로 만들고 전체 문서를 재인덱스해야 한다.

## Upsert·Meta 단계

Qdrant에 청크를 반영하고 문서 상태를 갱신하는 마지막 단계로, 별도로 조정할 설정은 없다.

`upsert_op`은 Qdrant에서 해당 `doc_id`의 기존 청크를 지운 뒤 새 청크를 넣는 방식으로 동작해
재인덱스가 그대로 멱등하게 적용되고, `meta_op`이 문서 `status`를 `indexed`로 바꾸며
`etag`/`chunk_count`/`updated_at`을 기록한다. 색인된 청크를 어떻게 검색하고 리랭킹하는지는
[검색](search.md) 가이드에서 다룬다.
