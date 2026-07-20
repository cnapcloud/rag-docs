# Docker Compose 컴포넌트 참조

docker-compose(Core) 배포의 컨테이너 구성, 이벤트 처리 흐름, 기동 의존 순서, 오브젝트
스토리지 레이아웃 참조. 장애 대응·일상 운영 절차는
[Operations Guide](../operations/03-runbook-docker-compose.md)를 참고한다.

---

## 컨테이너 구성

| 컨테이너 | 역할 | 포트 |
|---|---|---|
| `postgresql` | Postgres 15 — rag-api DB + Dagster 상태 저장소 | 5432 |
| `redis` | Redis 7 — 이벤트 큐 | 6379 |
| `qdrant` | Qdrant v1.18 — 벡터 DB | 6333 / 6334 |
| `minio` | MinIO — 오브젝트 스토리지 | 9000 / 9001(콘솔) |
| `minio-init` | 버킷 초기화 (일회성) | - |
| `rag-api` | RAG API 서버 | 8000 |
| `rag-admin` | 관리 UI (nginx) | 8080 |
| `dagster-rag-api` | gRPC 코드 서버 (definitions 로드) | 4000 |
| `dagster-webserver` | Dagster UI | 3000 |
| `dagster-daemon` | 센서·스케줄 실행 프로세스 | - |

## 이벤트 처리 흐름

`queue_worker.enabled: false` (기본값)일 때 Dagster가 이벤트를 처리한다.

```
API 호출 (파일 업로드 / 문서 삭제 / 커넥터 동기화)
  → rag-api: enqueue_upload_event / enqueue_delete_event
    → Redis 큐 (rag:upload:queue / rag:delete:queue)
      → event_queue_sensor (dagster-daemon, 30초 간격 tick)
        → ingest_job / delete_job
```

> `queue_worker.enabled: true`로 변경하면 Dagster 없이 rag-api 내장 워커가 큐를 직접 처리한다. 이 경우 Dagster 센서는 동작하지 않으며, 운영 Runbook의 센서 관련 절차는 해당 없다.

## 기동 의존 순서

```
postgresql  ─┐
redis ───────┼─(모두 healthy)→ rag-api ─→ rag-admin
qdrant ──────┤                        └─→ minio-init (minio healthy 추가)
minio ───────┘

postgresql ─(healthy)→ dagster-rag-api ─→ dagster-webserver
                                       └─→ dagster-daemon
```

## 오브젝트 스토리지 레이아웃

| source_type | storage_key 형식 | 예시 |
|---|---|---|
| `s3` (파일 업로드) | `{kb_id}/{filename}` | `kb-01/report.pdf` |
| `web` (크롤러) | `{kb_id}/web/{doc_id}.html` | `kb-01/web/a1b2c3-….html` |
| `confluence` | `{kb_id}/confluence/{doc_id}.md` | `kb-01/confluence/a1b2c3-….md` |
| `github` | `{kb_id}/github/{doc_id}.{ext}` | `kb-01/github/a1b2c3-….md` |

MinIO CLI로 오브젝트 확인:

```bash
docker exec minio mc alias set local http://localhost:9000 <user> <password>
docker exec minio mc ls local/rag-api/kb-01/
docker exec minio mc stat local/rag-api/kb-01/report.pdf
```
