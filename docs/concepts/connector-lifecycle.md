---
sidebar_position: 5
---

# 커넥터 상태 흐름

커넥터는 문서 하나와 달리 `status`(운영 상태)와 `sync_status`(동기화 실행 여부) 두 필드를
독립적으로 가진다. 두 필드가 분리되어 있는 이유와, 그로 인해 자동 스케줄·수동 트리거·강제
중단이 서로 다르게 취급되는 이유를 다룬다.

---

## 상태 필드

| 필드 | 값 | 의미 |
|------|-----|------|
| `status` | `active` / `paused` / `error` / `deleting` | 커넥터 자체의 운영 상태 |
| `sync_status` | `idle` / `running` | 현재 sync 실행 여부 |
| `last_error` | 문자열 (500자 제한) | 마지막 sync 실패 메시지 — `status`가 `error`가 아닌 값으로 바뀌는 순간 항상 함께 클리어된다 |

두 필드는 독립적으로 관리된다. `status=error`여도 `sync_status=idle`이면 수동 sync는
가능하다 — 직전 실패가 다음 시도를 막지 않는다.

## 상태 전이

```
status:
             PATCH(pause)
    active ──────────────► paused
      ▲                       │
      │      PATCH(resume)    │
      └───────────────────────┘

    active / paused / error ──(sync fails: exception raised)──► error
    error ──(sync retries and succeeds, not via abort)──► active
    error / active / paused ──(PATCH status: active|paused)──► specified status

    any ──(DELETE called)──► deleting ──(cascade delete completes)──► (record deleted)

sync_status:
              POST /sync (or Dagster Schedule)
    idle ────────────────────────────────────► running
                                                   │
                    ┌──────────────────────────────┼───────────────────────┐
                    │                              │                       │
              sync completes                  sync fails              abort called
                    │                              │                       │
                    │                     status → error                (immediate,
                    └──────────────────────────────┴─── idle ──────────  no wait)
```

`error`에서 `active`로의 자동 복구는 sync가 예외 없이 완료됐을 때만 일어난다. abort로 중단된
sync는 "정상 완료"가 아니므로 status를 건드리지 않고 이전 상태(예: `error`)를 그대로 둔다 —
abort 자체가 실패 원인을 고친 것은 아니기 때문이다.

## 수동 sync와 abort

| API | 조건 | 결과 |
|-----|------|------|
| `POST /sync` | `status == paused` | 409 — Connector is paused |
| `POST /sync` | `sync_status == running` | 409 — Sync already in progress |
| `POST /sync` | 그 외 | 202 — sync 시작, `sync_status → running` |
| `POST /sync/abort` | `sync_status != running` | 409 — No sync in progress |
| `POST /sync/abort` | `sync_status == running` | 202 — 중단 처리 시작 |
| `DELETE /connectors/{id}` | sync 실행 중 | 409 — Cannot delete connector while sync is running |

abort 호출 시 수행되는 작업은 순서대로 다음과 같다.

1. `sync_status → idle`(즉시).
2. 이 커넥터 소속 `pending` 문서를 Redis 큐에서 제거하고 `status → failed`로 전환.
3. 이 커넥터 소속 `running` 문서를 `status → failed`로 전환하고 Dagster run을 강제 종료.
4. sync 루프에 abort 신호를 전달 — 다음 페이지 요청 전에 루프가 종료된다.

## 자동 스케줄과 stale lock

`sync_schedule`이 설정된 커넥터는 Dagster Schedule로 `connector_sync_op`이 자동 실행된다.
수동 트리거와 다른 점은 `sync_status == running`이 오래 지속된 경우의 처리다.

- 실행 중 경과 시간이 **3600초(1시간) 미만**이면 건너뛴다(중복 실행 방지).
- **1시간을 초과**하면 stale lock으로 간주하고 다시 sync를 시작한다 — 이전 실행이 죽은
  채로 `sync_status`만 `running`으로 남는 상황을 스스로 복구하기 위함이다.

성공하면 `status`를 `active`로(직전이 `error`였어도), `sync_status`를 `idle`로 되돌리고
`last_synced_at`을 기록한다. 실패하면 `status`를 `error`로, `sync_status`를 `idle`로
되돌린다.

## sync 실패와 abort의 차이

sync 실패란 커넥터의 크롤/페치 루프(`_dispatch_sync()`)가 처리되지 않은 예외를 던지는
경우다. 개별 문서 인덱싱 실패(문서 `status → failed`)는 sync 실패가 아니며 커넥터 상태에
영향을 주지 않는다.

| 상황 | `status` | `sync_status` |
|------|----------|----------------|
| 수동/자동 sync 실패 (abort 없이 예외 발생) | `error` | `idle` |
| abort 진행 중 예외 발생 | 변경 없음 | `idle`(abort 호출 시점에 이미 전환됨) |

abort 중 백그라운드에서 예외가 발생해도 로그만 남긴다 — abort는 사용자의 의도적인 중단이므로
sync 실패와 구분한다.

## 재시작 후 sync_status 복구

서버(FastAPI)가 재시작되면 백그라운드 스레드가 종료되지만, PostgreSQL의 `sync_status`는
`running`으로 남을 수 있다.

```
process restarted
   │
   ▼
PostgreSQL sync_status: still "running"
   │
   ├─ 수동 sync 트리거 → 409 (Sync already in progress)
   └─ 자동 Dagster Schedule → 1시간 경과 후 stale lock으로 재트리거
```

`POST /sync/abort`를 호출하면 즉시 `sync_status → idle`로 전환된다 — 이 시점엔 실제 실행
중인 프로세스가 없으므로 큐·Dagster 작업 없이 상태 전환만 일어난다.
