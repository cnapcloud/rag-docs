---
sidebar_position: 5
---

# 검색

인제스트된 청크를 대상으로 하이브리드/유사도 검색을 실행하는 REST API다. dense와 sparse를
같이 쓰는 이유, 리랭커 폴백, 복수 KB 병렬 검색의 동작 원리는
[검색 흐름](../../concepts/data-flow.md#검색-흐름)에서 다루므로, 여기서는 실제로 호출하고
튜닝하는 방법을 정리한다. [MCP의 `search` tool](mcp-integration.md#search)도 이 REST API와
동일한 검색 로직을 공유한다.

---

## 검색 실행

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "TDF 상품 안내",
    "kb_ids": ["kb-01", "kb-02"],
    "options": {
      "mode": "hybrid",
      "top_k": 5,
      "hybrid": {"alpha": 0.5},
      "rerank": {"enabled": true, "top_n": 3}
    }
  }'
```

| 필드 | 필수 여부 | 설명 |
|------|-----------|------|
| `query` | 필수 | 검색어 |
| `kb_ids` | 필수 | 검색 대상 KB 목록. 비어 있으면 422 |
| `options.mode` | 선택 | `hybrid` / `similarity`. 기본값은 `retrieval.mode` |
| `options.top_k` | 선택 | 반환할 최대 결과 수. 기본값은 `retrieval.top_k` |
| `options.hybrid.alpha` | 선택 | `hybrid` 모드에서만 적용. 기본값은 `retrieval.hybrid.alpha` |
| `options.similarity.min_score` | 선택 | `similarity` 모드에서만 적용. 기본값은 `retrieval.similarity.min_score` |
| `options.rerank.enabled` | 선택 | 기본값은 `retrieval.rerank.enabled` |
| `options.rerank.top_n` | 선택 | 기본값은 `retrieval.rerank.top_n` |

요청 필드를 생략하면 그 자리에 `settings.yaml`의 `retrieval` 값이 기본값으로 들어간다 —
요청에 값이 있으면 요청이, 없으면 설정값이 이긴다.

응답의 `meta`는 `total_candidates`(리랭킹 전 후보 수)/`returned`/`search_mode`/
`score_threshold`/`reranked`/`rerank_provider`/`rerank_fallback`/`latency_ms`를 담는다.
`rerank_fallback: true`는 리랭커 API 호출이 실패해 순위를 그대로 반환했다는 뜻이다 — 검색
품질을 모니터링할 때 이 필드를 함께 봐야 조용히 리랭킹이 빠진 상태를 놓치지 않는다.

## 검색 모드

```yaml
retrieval:
  mode: "hybrid"          # hybrid | similarity
  top_k: 5
  hybrid:
    alpha: 0.5
    rrf_k: 60
  similarity:
    min_score: 0.0
```

### hybrid

Qdrant에서 dense(의미)와 sparse(BM25 키워드) 벡터를 KB마다 함께 질의하고, `alpha`로 두
결과의 비중을 조절해 KB 안에서 하나의 순위로 합친다 — `alpha: 0`은 sparse(키워드)만,
`alpha: 1`은 dense(의미)만 반영하고, 기본값 `0.5`는 절반씩 반영한다. 여러 KB를 동시에
검색하면 이렇게 KB별로 만들어진 순위를, `rrf_k`를 상수로 쓰는
RRF(Reciprocal Rank Fusion)로 다시 하나의 전체 순위로 합친다 — `alpha`는 KB 안에서
dense/sparse 비중을, `rrf_k`는 KB 사이 순위를 합치는 방식을 조절하는 서로 다른
파라미터다.

### similarity

dense 벡터만으로 코사인 유사도 검색을 한다. `alpha`는 무시되고(지정해도 경고 로그만 남기고
무시된다), 대신 `min_score` 미만인 결과를 걸러낸다. 복수 KB 결과는 RRF 없이 유사도 점수
자체로 정렬해 합친다.

## 리랭킹

```yaml
retrieval:
  rerank:
    enabled: false
    provider: "jina"        # jina | internal
    api_key: ""
    model: "jina-reranker-v2-base-multilingual"
    base_url: ""             # provider=internal일 때만 사용
    top_n: 3
    timeout_sec: 5
    fallback_on_error: true
```

`enabled: true`면 hybrid/similarity로 모인 상위 후보를 리랭커가 한 번 더 정렬해 상위
`top_n`개만 남긴다.

| provider | 설명 |
|----------|------|
| `jina` | Jina의 rerank API(`api_key` 필요) |
| `internal` | Cohere-compatible 스키마를 그대로 쓰는 자체 호스팅 리랭크 서버. `base_url`을 지정해야 하며, 없으면 `ConfigError` |

리랭커 API 호출이 실패하면(타임아웃, 5xx 등) `fallback_on_error: true`일 때 예외를 삼키고
기존 순위 그대로 상위 `top_n`개를 반환한다 — `false`면 예외가 그대로 전파된다.

## Auto-merge

```yaml
retrieval:
  auto_merge:
    enabled: false
    merge_threshold: 0.5
```

[`chunking.strategy: "hierarchical"`](ingestion.md#hierarchical-전략)로 인덱싱된 문서에서,
검색된 leaf 청크들을 상위(parent) 텍스트로 자동 병합해 반환할지 결정한다. 같은 parent
아래 매칭된 child 비율이 `merge_threshold` 이상이면 parent 텍스트로 병합하고, 미만이면
개별 child 결과를 그대로 반환한다. 3-level 이상 계층에서는 레벨을 타고 올라가며 반복
병합되며, 한 레벨에서 threshold 미달로 실패한 결과는 상위 레벨에서 재시도되지 않는다.
`chunking.strategy`(저장 구조)와는 독립된 별도 스위치라 구조는 hierarchical로 저장해두고
병합만 따로 껐다 켤 수 있다.

병합된 결과는 응답에서 `merged: true`, `chunk_index: null`로 표시되고, 병합 여부와
무관하게 `parent_chunk_id`에 상위 청크 ID가 채워진다(root거나 hierarchical이 아니면
`null`).

`auto_merge`는 검색 요청의 `options`로 오버라이드할 수 없다 — 오직 설정(전역 또는
[KB 오버라이드](kb.md#kb별-설정-오버라이드))으로만 제어한다. 위 hybrid/similarity/rerank
설정과 달리, `retrieval` 중 KB별로 오버라이드 가능한 건 `auto_merge`뿐이다 — 나머지는
여러 KB를 한 요청으로 합쳐 검색할 때 병합·리랭크가 요청 전체에 대해 정확히 한 번만
적용되므로 KB별로 다른 값을 가질 수 없다.

## 복수 KB 검색

`kb_ids`에 여러 KB를 넣으면 KB별로 병렬 질의한 뒤 하나의 순위로 합친다. 특정 KB 질의가
예외를 던져도 그 KB만 빈 결과로 처리되고 나머지 KB 결과로 응답이 만들어진다 — 한 KB의
장애가 전체 검색 요청을 막지 않는다.

검색 결과 중 PostgreSQL에 더 이상 존재하지 않는 `doc_id`를 가리키는 청크는 응답에서
제외되고, 그 자리에서 Qdrant에서도 함께 삭제된다(best-effort, 실패해도 검색 응답에는
영향 없음) — 삭제 파이프라인이 Qdrant 정리에 실패해 남긴 고아 청크를, 검색이 발견하는
대로 스스로 정리하는 self-healing 동작이다.
