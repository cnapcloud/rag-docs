---
sidebar_position: 4
---

# 사용자별 요청 제한

인증된 사용자 식별이 전제이므로 Enterprise 배포에만 있는 기능이다. REST 전체와 `/mcp`를
아우르는 단일 미들웨어가 사용자별로 호출 횟수를 세고, 규칙을 초과하면 429를 반환한다.

---

## 설정 방법

```yaml
rate_limit:
  enabled: true                 # false면 미들웨어 자체가 아무것도 세지 않고 통과시킨다
  rules:                        # 배열 순서대로 첫 매칭 규칙이 적용된다
    - name: search
      paths: ["/api/search"]
      limit: "10/second"        # "N/second" | "N/minute" | "N/hour"
    - name: upload
      paths: ["/api/kb/*/docs/upload", "/api/kb/*/docs/upload/batch"]
      limit: "30/minute"
      weights:
        "/api/kb/*/docs/upload/batch": 10   # 배치 호출 1건을 업로드 10건으로 취급
    - name: reindex
      paths: ["/api/kb/*/reindex", "/api/kb/*/docs/*/reindex"]
      limit: "2/minute"
    - name: mcp
      paths: ["/mcp"]
      limit: "300/minute"       # MCP 툴 전체가 하나의 버킷을 공유
  default: "120/minute"         # 위 규칙 어디에도 매칭되지 않는 경로의 기본 한도
  exempt_paths: ["/health", "/ready", "/docs", "/redoc", "/openapi.json"]
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `false` | 꺼져 있으면 미들웨어가 요청을 세지 않고 그대로 통과시킨다 |
| `rules[].paths` | — | `*`는 경로 세그먼트 하나와 매칭된다(`/api/kb/*/reindex`가 `/api/kb/kb-01/reindex`와 매칭) |
| `rules[].weights` | `{}` | 특정 경로 호출 1건을 몇 건으로 셀지. 지정 없으면 1건 |
| `default` | `"120/minute"` | 어떤 `rules`에도 매칭되지 않는 나머지 전체 경로에 적용 |
| `exempt_paths` | 헬스체크·문서 경로 | 카운터 자체를 건드리지 않는다 — 한도를 이미 넘긴 사용자가 호출해도 항상 통과 |

## 규칙 매칭과 카운팅

경로는 `rules` 배열을 순서대로 검사해 처음 매칭되는 규칙 하나만 적용한다 — 여러 규칙에
걸쳐도 중첩 적용되지 않는다. 매칭되는 규칙이 없으면 `default`가 적용된다.

카운팅은 사용자별·규칙별·시간창별로 독립된 Redis fixed-window 카운터를 쓴다
(`rl:{user_id}:{category}:{window_index}`). 창이 넘어가면 카운터가 자연 만료돼 리셋되며,
별도의 정리 작업이 필요 없다. fixed window라 창 경계 부근에서는 순간적으로 한도의 최대
두 배까지 요청이 몰릴 수 있다 — 예를 들어 60초 창의 마지막 1초와 다음 창의 첫 1초에 각각
한도를 꽉 채우면 2초 사이에 한도의 2배가 통과한다.

## 예외 경로와 super-admin

`exempt_paths`에 있는 경로는 카운터를 아예 건드리지 않는다. super-admin 토큰으로 호출하면
어떤 규칙의 한도를 이미 넘긴 상태여도 카운터 갱신 없이 곧바로 통과한다 — 운영 중 긴급 대응
시 rate limit 때문에 막히지 않게 하려는 설계다.

## 초과 시 응답

```
HTTP/1.1 429 Too Many Requests
retry-after: 46

{"detail": "Rate limit exceeded for 'reindex' requests"}
```

`retry-after`는 해당 시간창이 끝나기까지 남은 초(반올림)다.

## Redis 장애 시 동작

Redis 호출이 실패하면 그 요청의 한도 체크를 건너뛰고 통과시킨다(fail-open) — rate
limiting 경로 자체의 장애가 서비스 전체를 막는 일은 없어야 한다는 설계다. 실패 사실은
경고 로그로만 남고 사용자에게는 노출되지 않는다.
