---
sidebar_position: 5
---

# Query Playground

`POST /api/search`를 직접 호출해 하이브리드/유사도 검색 결과를 확인하는 화면이다. 검색
파라미터의 의미와 KB 병렬 검색·리랭킹 동작 원리는 [검색](../rag-api/search.md)에서 다룬다.

![Query Playground 실행 화면](/img/kb-admin/query-playground.png)

## 검색 실행

Knowledge Bases에서 검색 대상 KB를 하나 이상 고른다(+ Add KB로 추가, 배지의 X로 제거).
검색어를 입력하고 KB가 하나 이상 선택된 상태에서 Enter(Shift 없이)를 누르거나 Search
버튼을 누르면 실행된다.

## 옵션

- **Mode** — `hybrid` / `similarity`.
- **top_k** — 반환할 최대 결과 수(1-100).
- **alpha (hybrid)** — `hybrid` 모드에서만 노출, dense/sparse 비중(0-1). `similarity`
  모드에서는 대신 **min_score**(0-1)가 노출된다.
- **Rerank** — enabled 체크박스. 켜져 있을 때만 **top_n (rerank)** 필드가 노출된다.

이 화면은 옵션 필드를 항상 명시적으로 채워서 요청을 보낸다 — REST API가 지원하는 "필드를
생략하면 `settings.yaml`의 `retrieval` 값을 기본값으로 쓰는" 동작은 이 화면에서는 일어나지
않는다. 화면을 열었을 때의 초기값(top_k 10, alpha 0.5, min_score 0.3, rerank enabled,
top_n 5)은 `settings.yaml` 기본값과 다를 수 있으므로, 배포의 기본 검색 품질을 확인하려면
REST API를 직접 호출해야 한다.

## 결과

결과 상단에 반환 개수·후보 수(`total_candidates`)·응답 시간(ms)·검색 모드가 표시되고,
리랭킹이 적용됐으면 `reranked` 배지가 붙는다(리랭커 API 실패로 순위가 그대로 반환된
경우 `reranked (fallback)`).

결과 카드마다 순위·소속 KB·점수(리랭킹 적용 시 `rerank_score`, 아니면 유사도/RRF 점수)·
청크 본문을 보여준다. 소스가 URL이면 제목이 그 URL로 링크되고, 아니면 제목 클릭으로 원본
파일을 내려받는다. PDF 등 페이지 정보가 있는 청크는 페이지 번호(`p.N`)도 함께 표시된다.
