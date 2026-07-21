---
sidebar_position: 6
---

# MCP 연동

검색·조회 기능을 MCP(Model Context Protocol) 툴로 노출해, Claude Desktop 같은 MCP
클라이언트나 LibreChat 같은 챗 서비스가 rag-api의 KB를 직접 조회하게 한다.

```yaml
mcp:
  enabled: true
  transport: streamable-http   # stdio | sse | streamable-http
```

---

## 전송 방식

`transport`에 따라 MCP 서버가 실행되는 위치 자체가 달라진다.

| transport | 실행 위치 |
|-----------|-----------|
| `streamable-http` / `sse` | `rag-api serve`(메인 FastAPI 앱)에 `/mcp` 경로로 자동 마운트된다. 별도 프로세스가 필요 없다 |
| `stdio` | `rag-api serve`에는 마운트되지 않는다. `rag-api serve-mcp --transport stdio`로 별도 프로세스를 띄워야 하며, MCP 클라이언트가 이 커맨드를 subprocess로 직접 실행하는 방식이 일반적이다 |

### HTTP 서버에 내장 (streamable-http / sse)

`mcp.enabled: true`이고 `transport`가 `streamable-http` 또는 `sse`면 `rag-api serve`가 기동될
때 MCP 서버가 같은 프로세스·같은 포트에 `/mcp` 경로로 자동 마운트된다.

```bash
rag-api serve --port 8000
```

Streamable HTTP는 세션 기반이다 — `initialize` 호출로 세션을 먼저 열고, 응답 헤더의
`mcp-session-id`를 이후 모든 요청에 그대로 실어 보내야 한다.

```bash
# 1단계 — 세션 초기화
SESSION=$(curl -sD - -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }' | grep -i mcp-session-id | awk '{print $2}' | tr -d '\r')

# 2단계 — 툴 목록 조회
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
```

응답 본문은 SSE로 프레이밍되어 온다(`event: message` 줄 다음에 `data: {...}` 줄). 결과를
그대로 `jq`에 넘기면 `event: message` 줄에서 파싱 에러가 나므로, `data:` 줄만 뽑아 접두어를
제거한 뒤 전달해야 한다.

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}' \
  | sed -n 's/^data: //p' | jq
```

Claude Desktop처럼 HTTP 전송을 직접 지원하는 클라이언트는 `command` 대신 서버 URL만
설정하면 된다 — 세션 초기화는 클라이언트가 알아서 처리한다.

```json
{
  "mcpServers": {
    "rag-api": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

이 경우 `mcp.host`/`mcp.port` 설정은 쓰이지 않는다 — 서버 자체의 host/port(`rag-api serve
--host`/`--port`, 기본 `0.0.0.0:8000`)를 그대로 쓴다. `mcp.host`/`mcp.port`는 아래처럼
`serve-mcp`를 독립 HTTP 프로세스로 띄울 때만 적용된다.

### 독립 프로세스로 실행 (stdio)

로컬 MCP 클라이언트(Claude Desktop 등)는 보통 서버를 subprocess로 직접 실행하고 표준
입출력으로 통신한다. `--transport`/`--port` 플래그는 `settings.yaml`의 `mcp` 섹션 값을
그때만 덮어쓴다.

```bash
rag-api serve-mcp --transport stdio
```

```json
{
  "mcpServers": {
    "rag-api": {
      "command": "rag-api",
      "args": ["serve-mcp", "--transport", "stdio"]
    }
  }
}
```

stdio 모드는 표준입출력을 프로토콜이 그대로 점유하므로 포트 개념이 없다 — `mcp.host`/
`mcp.port`는 이 모드에서 의미가 없다. `mcp.enabled: false`면 `serve-mcp`는 전송 방식과
무관하게 즉시 종료된다.

## 제공 Tool

`list_knowledge_bases` → `search` 순서로 호출하는 것이 기본 사용 흐름이다 — 서버가 MCP
`instructions`로 클라이언트에 이 순서를 안내한다. 세 tool 모두 OpenTelemetry 스팬으로
자동 추적된다.

### search

질의어로 KB를 검색해 관련 청크를 반환한다.

| 파라미터 | 필수 여부 | 설명 |
|----------|-----------|------|
| `query` | 필수 | 검색어 |
| `kb_ids` | 선택 | 검색 대상 KB 목록. 생략하면 접근 가능한 전체 KB를 대상으로 한다 |
| `top_k` | 선택 | 반환할 최대 결과 수. 기본값은 `retrieval.top_k` |
| `mode` | 선택 | `hybrid`(키워드+의미 검색, 특정 용어에 유리) 또는 `similarity`(의미 검색 전용, 개념적 질의에 유리). 기본값은 `retrieval.mode` |
| `min_score` | 선택 | 최소 유사도 점수(0.0~1.0). `similarity` 모드에서만 적용되며, 기본값은 `retrieval.similarity.min_score` |

응답은 청크별 `text`/`score`/`rerank_score`/`kb_id`/`source`/`page_num`/`page_label`/
`chunk_idx`와 전체 `latency_ms`를 담은 결과 목록이다.

### list_knowledge_bases

파라미터 없이 호출하며, 접근 가능한 모든 KB의 `id`/`name`/`description`/`tags`를 반환한다.
`search`에 넘길 `kb_ids`를 알아내기 위한 첫 호출로 쓰인다.

### get_document_status

문서 하나의 인덱싱 상태를 조회한다.

| 파라미터 | 필수 여부 | 설명 |
|----------|-----------|------|
| `kb_id` | 필수 | 문서가 속한 KB |
| `doc_id` | 필수 | 문서 ID |

`status`는 문서가 없거나 `kb_id`가 일치하지 않으면 `not_found`를 반환하고, 그 외에는
문서의 실제 상태값을 그대로 반환한다 — 상태값의 의미와 전이 규칙은
[문서 상태 흐름](../../concepts/document-lifecycle.md) 참고. 함께 `updated_at`/
`file_size`/`content_version`도 반환한다.

---

Enterprise 배포에서는 REST·검색과 동일한 OIDC 인증 + KB 단위 역할(RBAC)이 MCP 호출
경로에도 그대로 적용된다 — `search`는 호출자가 접근 가능한 KB로 자동 필터링되고,
`list_knowledge_bases`/`get_document_status`도 같은 권한 판단을 거친다. rag-api
단독 배포에는 이 인증 계층이 없다 — MCP 엔드포인트에 도달할 수 있는 클라이언트는 모든 KB의
모든 tool을 제한 없이 호출할 수 있다는 뜻이므로, 네트워크 경계에서 접근을 통제해야 한다.
자세한 흐름은 [접근 제어](../../concepts/access-control.md) 참고.
