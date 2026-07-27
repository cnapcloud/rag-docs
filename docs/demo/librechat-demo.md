---
sidebar_position: 2
title: LibreChat 연동 데모
sidebar_label: LibreChat 연동
---

# LibreChat 연동 데모

LibreChat(CNAP AI Chat)이 MCP로 rag-api의 `search` 툴을 호출해 자연어 질문에 KB 문서 근거
답변을 생성하고, 그 호출이 Langfuse·Grafana로 실시간 관측되는 흐름을 보여준다.

<video controls width="100%" poster="/img/video/librechat-rag-poster.jpg">
  <source src="/img/video/librechat-rag.mp4" type="video/mp4" />
  브라우저가 비디오 태그를 지원하지 않는다 — [다운로드](/img/video/librechat-rag.mp4)로 직접 확인한다.
</video>

## 시연 순서
- RAG Admin Documents에서 인제스트된 고양이 문서를 확인하고, Query Playground에서
  "최고령 고양이를 찾아봐"로 하이브리드 검색 결과를 확인
- LibreChat에서 GPT-4.1 모델에 MCP `rag` 서버를 연결하고 동일하게 "최고령 고양이를 찾아봐" 질문
- "출처도 알려줘" 후속 질문 — 검색된 문서의 원본 링크까지 제시
- Langfuse 트레이스에서 `mcp/tools/search`의 입력(query/kb_ids/mode)과 출력(청크, score) 확인
- Grafana LLM Observability 대시보드에서 TTFT/E2E latency, TPS, 에러율 확인

