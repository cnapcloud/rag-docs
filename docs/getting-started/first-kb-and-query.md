---
sidebar_position: 2
---

# 첫 KB와 검색

[Quick Start](quickstart.md)로 설치를 끝냈다면, 이제 지식베이스(KB)를 하나 만들고 문서를
올려서 실제로 검색까지 해본다. 5~10분이면 끝난다.

콘솔 UI(`http://localhost:8080`)로 따라 해도 되고, 아래처럼 API를 직접 호출해도 된다 —
둘 다 같은 결과를 낸다. 이 문서는 API 기준으로 진행한다.

---

## 1. KB 생성

KB(Knowledge Base)는 문서를 격리하는 기본 단위다. 지금은 평가용으로 하나만 만든다.

```bash
curl -X POST http://localhost:8000/api/kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "kb-eval", "kb_name": "평가용 KB"}'
```

콘솔로 하려면: 좌측 메뉴 **Knowledge Bases** → **New KB** → `kb-eval` 입력.

## 2. 문서 업로드

가지고 있는 PDF·Word·한글(HWP)·마크다운 파일 아무거나 하나 올려본다.

```bash
curl -X POST http://localhost:8000/api/kb/kb-eval/docs/upload \
  -F "file=@./sample.pdf"
```

응답에 `doc_id`가 들어있다 — 다음 단계에서 이 값으로 상태를 확인한다.

콘솔로 하려면: **Documents** 화면에서 드래그 앤 드롭.

## 3. 인덱싱 대기

업로드 직후 문서는 바로 검색되지 않는다. 파싱 → 중복 검사 → 청킹 → 임베딩 → 색인 단계를
거치는데, 일반적인 문서는 수십 초 안에 끝난다. 이 상태 전이가 왜 이렇게 나뉘어 있는지는
[문서 상태 흐름](../concepts/document-lifecycle.md)에서 다룬다 — 지금은 `status`가
`indexed`가 될 때까지 기다리면 된다.

```bash
curl http://localhost:8000/api/kb/kb-eval/docs/{doc_id}/status
```

콘솔의 **Documents** 화면에서는 상태 뱃지가 자동으로 갱신된다.

`failed`로 바뀌면 같은 응답의 `last_error` 필드에 원인이 남는다 — 임베딩 서버(Ollama) 연결이
가장 흔한 원인이다.

## 4. 검색

문서 상태가 `indexed`가 되면 바로 검색 대상이다.

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "문서 내용에 대한 질문", "kb_ids": ["kb-eval"]}'
```

응답에 관련 청크가 점수·출처와 함께 반환되면 성공이다. 이 결과가 어떻게 만들어지는지
(dense+sparse 하이브리드, RRF 병합, 리랭킹)는 [검색·인제스트 흐름](../concepts/data-flow.md)에서
설명한다.

콘솔로 하려면: **Query Playground**에서 같은 질의를 입력하고 점수·출처·발췌를 눈으로 확인한다.

## 5. (선택) AI 에이전트에 연결

Claude Code, VS Code 등 MCP를 지원하는 클라이언트가 있다면 검색 툴을 바로 노출할 수 있다.

```json
{
  "servers": {
    "rag": { "type": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

전체 툴 목록과 옵션은 [guides/rag-api/mcp-integration.md](../guides/rag-api/mcp-integration.md) 참고.

## 다음 단계

| 하고 싶은 것 | 문서 |
|--------------|------|
| 커넥터로 문서를 자동 수집하고 싶다 | [guides/rag-api/connectors.md](../guides/rag-api/connectors.md) |
| KB마다 청킹·중복감지 설정을 다르게 주고 싶다 | [guides/rag-api/kb.md](../guides/rag-api/kb.md) |
| SSO·권한 제어가 필요하다 (Enterprise) | [guides/rag-ent/sso-and-auth-setup.md](../guides/rag-ent/sso-and-auth-setup.md) |
| 운영 환경(k8s)에 제대로 배포하고 싶다 | [deployment/kubernetes.md](../deployment/kubernetes.md) |
