---
sidebar_position: 4
---

# Docker Compose

컨테이너 구성, 이벤트 처리 흐름, 기동 의존 순서, 오브젝트 스토리지 레이아웃을 다룬다.

---

## 컨테이너 구성

| 컨테이너 | 역할 | 포트 |
|---|---|---|
| API 서버 | REST API 서버. Core/Enterprise 모두 docker-compose 서비스 키는 `rag-api`로 같고, 실제 컨테이너 이름(`container_name`)만 Enterprise에서 `rag-ent-api`로 다르다 | 8000 |
| `rag-admin` | 관리 콘솔(nginx) | 8080 |
| `postgresql` | Postgres 15 — 메타데이터 + Dagster 상태 저장소 | 5432 |
| `redis` | Redis 7 — 이벤트 큐. Enterprise는 역할 캐시·rate limit 카운터도 같은 Redis를 겸용 | 6379 |
| `qdrant` | Qdrant v1.18 — 벡터 DB | 6333 / 6334 |
| `minio` | MinIO — 오브젝트 스토리지 | 9000 / 9001(콘솔) |
| `minio-init` | 버킷 초기화(일회성) | — |
| `dagster-rag-api` | gRPC 코드 서버(definitions 로드) | 4000 |
| `dagster-webserver` | Dagster UI | 3000 |
| `dagster-daemon` | 센서·스케줄 실행 프로세스 | — |
| `mailpit` [ENT] | 초대·역할 부여 메일을 가두는 로컬 SMTP 서버. 운영 배포에는 사용하지 않는다 | 8025(Web UI) / 1025(SMTP) |

## 이벤트 처리 흐름

`queue_worker.enabled: false`(기본값)일 때 Dagster가 이벤트를 처리하는 경로다.

```
API call (file upload / document delete / connector sync)
  -> API server: enqueue_upload_event / enqueue_delete_event
    -> Redis queue (rag:upload:queue / rag:delete:queue)
      -> event_queue_sensor (dagster-daemon, 30s tick)
        -> ingest_job / delete_job
```

`queue_worker.enabled: true`로 바꾸면 Dagster 없이 API 서버 내장 워커가 큐를 직접 처리한다
— 이 경우 Dagster 센서는 동작하지 않는다.

## 기동 의존 순서

```
postgresql ─┐
redis ───────┼─(all healthy)─→ API server ─→ rag-admin
qdrant ──────┤                            └─→ minio-init (+ minio healthy)
minio ───────┘

postgresql ─(healthy)─→ dagster-rag-api ─→ dagster-webserver
                                        └─→ dagster-daemon
```

Enterprise는 API 서버가 `mailpit`(healthy)도 함께 기다린 뒤에 기동한다.

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

버킷 이름 `rag-api`는 `s3.rag_bucket`([Configuration §2 s3](configuration.md#2-s3) 참고)
설정값으로, Enterprise 배포에서도 기본값을 그대로 쓰면 동일하다.
