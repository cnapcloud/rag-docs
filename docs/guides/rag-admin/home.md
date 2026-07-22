---
sidebar_position: 1
---

# Home

RAG Admin에 접속하면 가장 먼저 표시되는 화면이다. 주요 화면으로 이동하는 바로가기와 연동된
인프라 컴포넌트의 상태를 한 화면에서 보여준다.

![RAG Admin Home 화면](/img/kb-admin/home.png)

## Quick links

사이드바 메뉴와 1:1로 대응하는 카드 4개다.

- **Knowledge Bases** — KB 생성·조회, 태그·상태 관리. [Knowledge Bases](./knowledge-bases.md)로 이동한다.
- **Connectors** — 웹/Confluence/GitHub 문서를 KB로 자동 동기화. [Connectors](./connectors.md)로 이동한다.
- **Documents** — 업로드, 재인덱싱, KB 전반의 임베딩 진행 상황 모니터링. [Documents](./documents.md)로 이동한다.
- **Query Playground** — 하나 이상의 KB에 대해 하이브리드/유사도 검색 실행. [Query Playground](./query-playground.md)로 이동한다.

## Infrastructure 상태

RAG API, Qdrant, Redis, Postgres, S3, Ollama 컴포넌트의 연결 상태를 카드로 보여준다. 프로바이더
설정(예: OpenAI 미사용 배포)에 따라 표시되는 카드 구성은 달라질 수 있다.

- **정상** — 초록색 `OK` 배지.
- **연결 실패** — 빨간색 `Error` 배지. Ollama는 기동 직후 모델을 로드하는 동안 일시적으로 이
  상태로 보일 수 있다 — [Configuration](../../reference/configuration.md) 참고.
- **RAG API 자체에 연결 불가** — 카드 대신 "Failed to reach API. Is the server running?" 메시지가
  표시된다.

이 상태는 RAG API의 [`/ready` 엔드포인트](../../reference/api-guide.md)를 조회한 결과다.
우측 상단 Refresh 버튼으로 즉시 다시 확인할 수 있고, 그 외에는 `DOC_REFRESH_INTERVAL`(최소
3초) 주기로 자동 갱신된다 — [Environment Variables](../../reference/environment-variables.md) 참고.

## 사이드바 탐색

`⌘B`로 좌측 사이드바를 아이콘만 남긴 접힌 상태로 토글할 수 있다. 사이드바가 모든 화면으로
이동하는 유일한 경로이므로, 화면 폭이 좁을 때 유용하다.
