# LibreChat 연동

연동 애플리케이션 구성 담당자를 위한 연동 가이드. 핵심 시나리오: LibreChat 사용자가 자기
권한 범위의 KB만 대상으로 RAG 검색을 쓰는 구성(§1~§4). SSO·RBAC 기반 연동이므로 전체가
Enterprise 배포를 전제로 한다.

이 문서는 **LibreChat과의 연동 방법**(OIDC 로그인 연결, MCP 서버 등록, 권한 전달 구조)만
다룬다. LibreChat 자체의 배포·구성(설치, MongoDB, 리소스 사이징 등)은 범위 밖이며, 해당
사이트에서 LibreChat 운영 주체가 별도로 진행한다.

---

## 1. LibreChat 연계 아키텍처

LibreChat과 본 제품이 **같은 IdP(Keycloak)를 공유**하고, LibreChat이 로그인 사용자의
액세스 토큰을 그대로 MCP 요청에 실어 보내는 구조다. 별도의 서비스 계정이나 API 키가
없으며, **검색 권한은 항상 "지금 질문한 사용자" 기준**으로 적용된다.

```
사용자 ── SSO 로그인 ──> LibreChat ── MCP (Bearer: 사용자 토큰) ──> rag-ent-api /mcp
              │                                                        │
              └────────────── Keycloak (공유 realm) ────────────────────┘
                                                     KB 권한 필터: 사용자가 viewer 이상인
                                                     KB만 검색 대상에 포함
```

- 사용자 A가 "우리 팀 규정 알려줘"라고 물으면, A가 멤버인 KB에서만 검색된다.
- 권한 없는 KB가 대상에 섞여도 오류 없이 자동 제외된다 (전부 제외되면 빈 결과).
- super-admin, public KB, RBAC 비활성 시의 동작은 [api-guide.md](../reference/01-api-guide.md) 참조.

## 2. 사전 준비

| 항목 | 내용 |
|------|------|
| 본 제품 | Enterprise 배포 완료 ([04-enterprise-setup.md](04-enterprise-setup.md)) — MCP 활성 (`mcp.enabled: true`) |
| LibreChat | v1.3+ 배포 (자체 MongoDB 포함) |
| Keycloak 클라이언트 | LibreChat용 **confidential** 클라이언트 추가 (client id + secret). 관리 콘솔용 public 클라이언트와 별개 |

**주의 — 계정 충돌**: LibreChat은 이메일로 사용자를 식별한다. 로컬 가입 계정과 Keycloak
SSO 계정의 이메일이 같으면 로그인이 충돌하므로, SSO 도입 시 로컬 가입을 비활성화하거나
기존 로컬 계정을 정리한다.

## 3. LibreChat 설정

### 3.1 OIDC 로그인 (.env)

```env
ALLOW_SOCIAL_LOGIN=true
OPENID_CLIENT_ID=<librechat 클라이언트 ID>
OPENID_CLIENT_SECRET=<시크릿>
OPENID_ISSUER=https://<keycloak>/realms/<realm>
OPENID_SCOPE=openid profile email
```

### 3.2 RAG MCP 서버 등록 (librechat.yaml)

```yaml
mcpServers:
  rag:
    type: streamable-http
    url: http://rag-api.<ns>.svc.cluster.local:8000/mcp
    scopes: ["openid", "profile", "email"]
    headers:
      Authorization: "Bearer {{LIBRECHAT_OPENID_ACCESS_TOKEN}}"
    timeout: 30000
    initTimeout: 60000
    reconnect:
      enabled: true
      delay: 3000
      maxRetries: 5

mcpSettings:
  allowedAddresses:
    - "rag-api.<ns>.svc.cluster.local:8000"
```

구성 요점:

| 항목 | 설명 |
|------|------|
| `{{LIBRECHAT_OPENID_ACCESS_TOKEN}}` | LibreChat이 로그인 사용자의 토큰을 치환해 전달. 토큰이 만료됐으면 요청 시점에 자동 갱신 후 전송(lazy-refresh) — 세션 쿠키 수명 설정과는 무관 |
| `type: streamable-http` | **SSE 대신 필수 권장.** SSE는 상시 연결 방식이라 서버 pod 재시작 시 연결이 끊기고 수동 재연결이 필요하다. streamable-http는 요청 단위 연결이라 재시작에 강하고 확장이 쉽다 |
| `allowedAddresses` | LibreChat의 MCP 허용 목록에 반드시 포함 |

설정 변경 후 LibreChat의 ConfigMap 반영과 rollout restart가 필요하다.

### 3.3 에이전트 권한 (선택)

LibreChat에서 RAG 툴은 에이전트를 통해 사용된다. 사용자에게 노출하려면 세 단계가 모두
필요하다: (1) `librechat.yaml`에서 agents 활성화 → (2) Admin Settings에서 역할별
사용(USE)/생성(CREATE)/공유(SHARE) 정책 부여 → (3) RAG 툴을 포함한 에이전트를 만들어
대상 사용자·그룹에 공유. 어느 한 단계가 빠지면 일반 사용자 화면에 나타나지 않는다.

## 4. 동작 검증

| # | 확인 | 기대 결과 |
|---|------|-----------|
| 1 | Keycloak 계정으로 LibreChat 로그인 | SSO 로그인 성공 |
| 2 | 에이전트에서 rag 툴 목록 확인 | search / list_knowledge_bases / get_document |
| 3 | 본인이 멤버인 KB 내용 질문 | 해당 KB 문서 기반 답변 |
| 4 | 권한 없는 KB 내용 질문 | 해당 KB 결과가 포함되지 않음 (오류 아님) |
| 5 | KB 멤버 추가 직후 재질문 | 새 KB가 검색 대상에 포함됨 |

## 5. 기타 MCP 클라이언트 (IDE·에이전트)

Claude Code, VS Code 등 MCP 지원 도구는 동일한 엔드포인트를 사용한다. Enterprise 배포는
사용자별 토큰을 헤더에 지정한다.

```json
{
  "servers": {
    "rag": {
      "type": "http",
      "url": "https://<api 도메인>/mcp",
      "headers": { "Authorization": "Bearer <사용자 JWT>" }
    }
  }
}
```

IDE 환경은 토큰 만료 시 자동 갱신이 없으므로, 장기 사용은 IdP의 오프라인 토큰 또는 토큰
발급 절차를 조직 정책에 맞게 안내한다.

## 6. 외부 RAG 플랫폼 연계 (참고)

- **Dify**: Dify의 외부 지식베이스(External Knowledge Base) API로 본 제품을 검색
  백엔드로 연결할 수 있다 — Dify 앱/워크플로는 유지하면서 검색만 본 제품으로 교체하는
  경로. 전용 어댑터는 로드맵 항목이며 상세 가이드는 추후 제공.
- **자체 애플리케이션**: REST `/api/search`에 사용자 토큰을 전달하는 방식이 가장 단순하다
  ([04-enterprise-setup.md §5](04-enterprise-setup.md)).

## 7. 관측 연계

챗 요청 → LLM 호출 → RAG 검색을 하나의 trace로 잇는 Langfuse 연동과 Prometheus·Grafana
대시보드 구성은 [02-observability.md](../operations/02-observability.md) 참조.
