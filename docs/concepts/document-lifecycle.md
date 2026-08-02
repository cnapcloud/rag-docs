---
sidebar_position: 4
---

# 문서 상태 흐름

문서(document)의 전체 생명주기는 단일 `status` 필드로 표현된다. 상태가 여러 종류로 세분화
되어 있고 전이 규칙이 엄격한 이유는 동시성 충돌을 막기 위해서다. 상태가 어떻게 나뉘고
전이되는지, 그리고 그로 인해 특정 요청이 왜 409로 거부되는지를 차례로 설명한다.

---

## 상태 종류

상태는 활성(active) 5종과 안정(stable) 4종으로 나뉜다. 활성 상태는 안정 상태의 여집합으로
정의된다(`pipeline/utils/doc_state.py`의 `is_active()`).

| 구분 | 상태 | 의미 |
|------|------|------|
| 활성 | `uploading` | S3(MinIO) 파일 전송 중 |
| 활성 | `pending` | Redis 큐 대기 중 |
| 활성 | `fetching` | 커넥터가 원격 소스에서 콘텐츠 다운로드 중 |
| 활성 | `running` | 인제스트 파이프라인 실행 중 |
| 활성 | `deleting` | 삭제 파이프라인 실행 중 |
| 안정 | `indexed` | 인덱싱 완료 — 검색 가능 |
| 안정 | `failed` | 파이프라인 실패 — `last_error` 필드에 원인 기록 |
| 안정 | `deleted` | soft delete 완료 — Qdrant 청크 제거, S3 파일 유지 |
| 안정 | `outdated` | dedup에 의해 구버전으로 판정됨 |

## 상태 전이

```
direct upload:
  POST /upload ──(new / re-upload)──► uploading ──(S3 transfer done)──► pending

connector fetch:
  connector job ──► fetching ──(fetch succeeds)──► pending
                            └───(fetch fails)────► failed
                                                       │
                                          (queue consumer dequeues)
                                                       ▼
                                                    running
                                                       │
                            ┌──────────────────────────┼──────────────────┐
                            │                          │                  │
                       ingest succeeds            dedup verdict      pipeline fails
                            │                          │                  │
                            ▼                   (older version)           ▼
                        indexed                        │                failed
                            │                          ▼
                            │                       outdated
                            │
                      ┌─────┴───────────────────────────────┐
                  reindex                                 delete   
                      |                                     │
                  POST /reindex ──► pending ──► running     │
                                               │            │
                                          ingest succeeds   │
                                               ▼            │
                                           indexed          │
                                                            │
                    DELETE /docs/{id} ──► pending ──► deleting
                                                       │
                                ┌──────────────────────┤
                                │                      │
                           soft delete            hard delete
                          (force=false)           (force=true)
                          delete Qdrant chunks    delete Qdrant chunks
                          delete hash bands       delete hash bands
                          keep S3 file            delete S3 file
                                │                      │
                                ▼                      ▼
                             deleted            (DB row deleted)
```

## 활성 상태에서 요청이 막히는 이유

업로드·삭제·재인덱스 API는 대상 문서가 활성 상태면 409를 반환한다(`is_active()` 가드,
`api/routers/docs.py`). 같은 문서에 대한 두 파이프라인이 동시에 도는 것을 막기 위한
동시성 제어다.

```
POST /docs/upload, DELETE /docs/{id}, POST /docs/{id}/reindex
   │
   ▼
is_active(status)?
   │
   ├─ true (uploading/pending/fetching/running/deleting)
   │     ▼
   │  409 Conflict — "Document is active, try again later"
   │
   └─ false (indexed/failed/deleted/outdated)
         ▼
      요청 처리
```

큐 레벨에서도 같은 원칙이 적용된다. `event_queue_sensor`가 이벤트를 꺼낼 때 대상 문서가
`running` 또는 `deleting`이면 즉시 처리하지 않고 delay 큐로 미룬다 — 실행 중인 파이프라인과
충돌하지 않기 위해서다.

## 강제 종료와 복구

멈춘 문서를 되돌리는 API는 두 개이며 적용 대상이 다르다.

| API | 적용 대상 상태 | 동작 |
|-----|----------------|------|
| `POST /docs/{id}/fail` | `uploading` / `pending` / `running` / `deleting` | `run_id`가 있으면 Dagster run 강제 종료 → Redis 큐에서 이벤트 제거 → `failed`로 전환 |
| `POST /docs/{id}/recover` | `running` | `failed`로 전환 후 강제 재인덱스 큐잉(`force=true`) |

`fetching`은 두 API 어디에도 포함되지 않는다 — 커넥터 다운로드가 멈추면 문서 단위 복구가
아니라 커넥터 단위 abort로 처리해야 한다.

QueueWorker 모드에서는 `running`/`deleting` 상태의 실제 AsyncIO 태스크를 강제 종료할 수
없다. `/fail` 호출 시 상태만 `failed`로 바뀌고, 응답에 `warning` 필드가 포함된다 — 태스크가
나중에 완료되면 이 상태를 덮어쓸 수 있다(자세한 배경은 [인제스트 흐름의 QueueWorker
모드](data-flow.md#queueworker-모드) 참고).

## dedup 판정과 `outdated` 전이

`running` 중 dedup이 판정한 결과가 문서 상태를 직접 바꾼다([dedup 3단계 처리](data-flow.md#dedup-3단계-처리)
참고).

- **중복 없음** — 정상 인덱싱, `indexed`로 전환.
- **동일 판정(identical_level)** — 기존 문서와 제목까지 같으면, 더 오래된 쪽이 `outdated`가
  된다.
- **유사 판정(similar)** — 더 최신 문서가 기존 청크를 대체하고 `indexed`, 더 오래된 쪽이
  `outdated`로 남는다.

`outdated`는 데이터 유실이 아니다. 검색에는 나타나지 않지만 레코드 자체는 남아 있고, 어떤
문서가 이를 대체했는지는 `duplicate_of` 필드로 추적된다.

## 재시작 후 stuck 문서

서버(FastAPI) 또는 dagster-rag-api(코드 서버)가 재시작되면 실행 중이던 백그라운드
작업이나 Run은 사라지지만, PostgreSQL의 `status`는 `running` / `uploading` / `deleting`으로
남을 수 있다. 이 상태에서는 업로드·삭제·재인덱스 API가 모두 409로 막힌다.

```
process restarted
   │
   ▼
PostgreSQL status: still "running" / "uploading" / "deleting"
   │
   ▼
POST /fail  →  status: "failed"
   │
   ▼
POST /reindex (또는 POST /recover)  →  재처리
```

복구는 수동이다 — `POST /fail`로 `failed`로 되돌린 뒤 재인덱스하거나, `running` 상태라면
`POST /recover`로 한 번에 처리한다.
