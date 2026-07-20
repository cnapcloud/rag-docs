# 설치 검증

설치 직후 및 업그레이드 후 수행하는 설치 검증 체크리스트(약 15분).

---

## 1. 인프라 연결 확인

```bash
curl http://<api>/health    # 프로세스 생존 — 항상 200
curl http://<api>/ready     # 인프라 연결 — 전체 정상 시 200
```

`/ready` 응답의 `checks`로 실패 지점을 식별한다:

```json
{ "status": "ready",
  "checks": { "qdrant": true, "redis": true, "postgres": true, "s3": true, "ollama": true } }
```

| 실패 항목 | 점검 |
|-----------|------|
| `postgres` / `redis` / `qdrant` | 주소·자격증명(settings.yaml), 네트워크 정책, 대상 서비스 기동 여부 |
| `s3` | 엔드포인트·자격증명, 버킷(`rag-api`, `dagster`) 존재 여부 |
| `ollama` | `embedding.ollama_url` 접근 가능 여부, `bge-m3` 모델 pull 여부 (`curl <ollama>/api/tags`) |

Dagster 모드 배포는 추가로 Dagster UI에서 확인한다: code location 로드 성공,
`event_queue_sensor` 상태 RUNNING.

## 2. 스모크 테스트 — 인제스트·검색 경로

Core 모드는 그대로, Enterprise 모드는 OpenID Connect로 토큰을 발급받아 `$TOKEN`에 설정한 뒤
모든 요청에 `-H "Authorization: Bearer $TOKEN"`을 추가해 진행한다.

```bash
# [1] KB 생성 → 201
curl -X POST http://<api>/api/kb -H "Content-Type: application/json" \
  -d '{"kb_id": "kb-verify", "kb_name": "설치 검증"}'

# [2] 문서 업로드 → 202, doc_id 확보
curl -X POST http://<api>/api/kb/kb-verify/docs/upload -F "file=@./sample.pdf"

# [3] 인덱싱 완료 대기 — status: pending → running → indexed
curl http://<api>/api/kb/kb-verify/docs/{doc_id}/status
#     indexed가 아니고 failed면 응답의 last_error로 원인 확인

# [4] 집계 확인 — pending+running=0, indexed>=1
curl http://<api>/api/kb/kb-verify/docs/status

# [5] 검색 — 업로드 문서의 청크가 출처와 함께 반환
curl -X POST http://<api>/api/search -H "Content-Type: application/json" \
  -d '{"query": "<문서 내용 관련 질문>", "kb_ids": ["kb-verify"]}'

# [6] 원본 다운로드 — 업로드 파일과 동일
curl -OJ http://<api>/api/kb/kb-verify/docs/{doc_id}/download

# [7] 문서 삭제 → 202, 이후 목록에서 제외 확인
curl -X DELETE http://<api>/api/kb/kb-verify/docs/{doc_id}

# [8] KB 삭제 (정리) → 200
curl -X DELETE http://<api>/api/kb/kb-verify
```

각 단계의 정상/오류 응답 상세는 [api-guide.md](../reference/01-api-guide.md) 참조.

### 판정 기준

| 단계 | 통과 기준 | 실패 시 |
|------|-----------|---------|
| [3] 인덱싱 | 일반 문서(수 MB) 기준 수십 초 내 `indexed` | `failed`: `last_error` 확인 (임베딩 서버 연결이 최다 원인). 5분 이상 `pending`: 큐 소비자(Dagster sensor 또는 QueueWorker) 동작 확인 |
| [5] 검색 | 관련 청크 반환, `latency_ms` 확인 | 빈 결과: [3]에서 실제 `indexed`였는지, `kb_ids` 오타 확인 |
| [5] 리랭킹 사용 시 | 응답 `rerank_fallback: false` | `true`면 리랭커 API 연결 실패 — 검색은 정상이나 리랭킹 미적용 (API 키·네트워크 확인) |

## 3. 스모크 테스트 — 관리 콘솔

1. 콘솔 접속 → Home의 인프라 타일 전체 OK.
2. Documents 화면에서 파일 업로드 → 진행률 표시 → `indexed` 뱃지.
3. Query 화면에서 검색 → 결과 카드에 점수·출처 표시.

## 4. 스모크 테스트 — Enterprise 권한 (ENT 배포만)

[04-enterprise-setup.md §6](04-enterprise-setup.md)의 체크리스트 7항목을 수행한다. 최소 확인 3가지:

- 토큰 없는 API 호출이 401로 거부되는가.
- KB 생성자가 `my_role: "owner"`를 받는가.
- 권한 없는 사용자의 문서 업로드가 403으로 거부되는가.

## 5. 스모크 테스트 — MCP (선택)

MCP 클라이언트(Claude Code, VS Code 등)에 서버를 등록하고 검색 툴 호출이 REST 검색과
동일한 결과를 반환하는지 확인한다. ENT 배포는 Bearer 토큰 헤더 포함 여부도 함께 확인.

## 6. 검증 완료 기준

- §1 인프라 체크 전체 통과
- §2 [1]~[8] 전 단계 통과
- (ENT) §4 3항목 통과

실패가 재현되면 [01-runbook-k8s.md](../operations/01-runbook-k8s.md)의 장애 대응 절 및
[알려진 제약](../support/03-known-limitations.md)을 확인하고, 해결되지 않으면 지원 채널
([지원 정책](../support/01-support-policy.md))로 문의한다.
