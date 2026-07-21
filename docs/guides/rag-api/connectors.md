---
sidebar_position: 2
---

# 커넥터

웹 페이지, Confluence 스페이스, GitHub 저장소 같은 외부 소스를 주기적으로 또는 수동으로
가져와 KB에 인제스트하는 단위다. 커넥터가 담당하는 범위는 소스에서 콘텐츠를 가져와 S3에
스테이징하고 Redis 업로드 큐에 이벤트를 넣는 지점까지이며, 이후 파싱·청킹·임베딩은 일반
[인제스트 흐름](../../concepts/data-flow.md#인제스트-흐름)과 동일하게 처리된다. 커넥터
운영 상태(`status`)와 동기화 실행 여부(`sync_status`)가 왜 분리되어 있고 수동 sync·자동
스케줄·abort가 두 필드를 각각 어떻게 바꾸는지는
[커넥터 상태 흐름](../../concepts/connector-lifecycle.md)에서 다룬다.

---

## 커넥터 생성·조회·수정·삭제

커넥터를 만들기 전에 대상 KB(아래 예시의 `kb-01`)가 이미 존재하는지 먼저 확인하고, 없으면
생성한다 — 존재하지 않는 `kb_id`로 커넥터 생성을 요청하면 404가 반환된다. KB 생성 방법은
[KB 생성·조회·수정·삭제](kb.md#kb-생성조회수정삭제) 참고.

```bash
# 목록 — kb_id/source_type/status/search 필터, sort_by/sort_order 정렬 지원
curl "http://localhost:8000/api/connectors?kb_id=kb-01&status=active"

# 단건 조회 (없으면 404)
curl http://localhost:8000/api/connectors/c-abcdef0123456789

# 생성 — config는 source_type별로 스키마가 다르다 (아래 절 참고)
curl -X POST http://localhost:8000/api/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "kb-01",
    "name": "제품 문서 사이트",
    "source_type": "web",
    "config": {"seed_urls": ["https://docs.example.com/guide"]},
    "sync_schedule": "0 3 * * *",
    "schedule_enabled": true
  }'

# 수정 — 전달한 필드만 갱신 (PATCH 의미론). status는 active/paused만 허용
curl -X PATCH http://localhost:8000/api/connectors/c-abcdef0123456789 \
  -H "Content-Type: application/json" \
  -d '{"status": "paused"}'

# 삭제 — 즉시 삭제되지 않고 status: deleting으로 전환된 뒤 백그라운드에서 cascade 삭제
curl -X DELETE http://localhost:8000/api/connectors/c-abcdef0123456789
```

| 필드 | 필수 여부 | 설명 |
|------|-----------|------|
| `kb_id` | 필수 | 대상 KB. 존재하지 않으면 404 |
| `name` | 필수 | 표시 이름 |
| `source_type` | 필수 | `web` / `confluence` / `github` |
| `config` | 필수 | 소스 타입별 설정 (다음 절 참고) |
| `sync_schedule` | 선택 | cron 표현식. 지정하면 자동 sync 스케줄 등록 대상이 된다 |
| `schedule_enabled` | 선택 | 스케줄 활성화 여부, 기본 `false` |

삭제는 진행 중인 sync가 있으면 409를 반환한다. cascade 삭제는 이 커넥터 소속 문서를 대상으로
Qdrant 청크·dedup 밴드·PostgreSQL 메타데이터를 순서대로 정리하지만, S3에 저장된 원본 파일은
지우지 않는다 — 커넥터가 사라지면 재동기화할 소스가 없으므로 S3 사본이 유일하게 남는 기록이기
때문이다.

### 웹 커넥터 (`web`)

`seed_urls`에서 시작해 링크를 따라가며 페이지를 수집한다. 각 seed URL의 경로가 크롤 범위를
정하는 기준이 된다 — 예를 들어 `https://example.com/docs`를 seed로 주면 기본적으로
`https://example.com/docs/*` 아래만 크롤링한다. `unrestricted: true`로 설정하면 이 경로
제한이 풀려 seed와 같은 도메인이기만 하면 `depth`가 허용하는 만큼 어느 경로로든 이동하며
크롤링한다 — 경로 제한만 없어질 뿐 `depth`/`max_pages` 등 다른 범위 제약은 그대로 적용된다.

| 필드 | 필수 여부 | 기본값 | 설명 |
|------|-----------|--------|------|
| `seed_urls` | 필수 | - | 크롤 시작 URL 목록 |
| `depth` | 선택 | `2` | BFS 탐색 깊이 (1-10) |
| `max_pages` | 선택 | `50` | sync당 처리할 최대 페이지 수 (1-500) |
| `include_patterns` | 선택 | `[]` | seed 범위 안에서 추가로 적용할 fnmatch 패턴 |
| `exclude_patterns` | 선택 | `[]` | 항상 제외할 fnmatch 패턴 (`include_patterns`보다 우선) |
| `unrestricted` | 선택 | `false` | `true`면 seed 경로 범위 체크를 끄고 같은 도메인 전체를 허용 |
| `skip_seed_pages` | 선택 | `true` | seed URL 자체(깊이 0)는 링크 탐색에만 쓰고 문서로 스테이징하지 않음 |
| `min_content_chars` | 선택 | KB의 `ingestion.min_content_chars` 전역값 | trafilatura 추출 글자 수가 이 값 미만이면 스테이징 제외 (0-10000, `0`은 비활성화) |
| `request_timeout_sec` | 선택 | `30` | HTTP 타임아웃(초) (1-300) |
| `request_delay_ms` | 선택 | `100` | 페이지 요청 사이 대기 시간(ms) (0-5000) |
| `auth_headers` | 선택 | - | 요청에 추가할 헤더. 시크릿 필드(암호화 저장) |
| `auth_basic` | 선택 | - | `{"username": ..., "password": ...}`. 시크릿 필드(암호화 저장) |

`text/html` 이외의 응답은 링크 탐색 없이 건너뛴다. 페이지네이션 URL(`/page/2/`, `?page=3`
형태)은 링크 탐색용으로만 방문하고 문서로 스테이징하지 않는다.

### Confluence 커넥터 (`confluence`)

지정한 스페이스의 페이지와 첨부파일을 REST API로 가져온다. Cloud(`*.atlassian.net`)와
Server를 모두 지원하며, 어느 쪽인지는 `base_url`로 판단한다.

| 필드 | 필수 여부 | 기본값 | 설명 |
|------|-----------|--------|------|
| `base_url` | 필수 | - | 예: `https://company.atlassian.net` |
| `space_key` | 필수 | - | 동기화할 스페이스 키 |
| `auth_token_secret` | 선택 | - | Cloud는 `email:api_token`(콜론 포함) → Basic 인증으로 변환, Server는 PAT 문자열 그대로 → Bearer 인증. 시크릿 필드(암호화 저장) |
| `exclude_labels` | 선택 | `[]` | 이 라벨이 붙은 페이지와 그 첨부파일을 건너뜀 |
| `max_pages` | 선택 | `50` | sync당 처리할 최대 페이지 수 (1-500) |
| `depth` | 선택 | 제한 없음 | 상위 페이지 개수(ancestor count) 기준 깊이 제한 (1-10) |
| `max_attachment_mb` | 선택 | `10` | 첨부파일 최대 크기(MB) |
| `request_delay_ms` | 선택 | `100` | API 호출 사이 대기 시간(ms) |
| `request_timeout_sec` | 선택 | `30` | HTTP 타임아웃(초) |

첨부파일은 [지원하는 파서 확장자](../../concepts/data-flow.md#파서-레지스트리)에 해당하는
것만 다운로드한다.

### GitHub 커넥터 (`github`)

지정한 브랜치의 저장소 트리를 조회해 지원 확장자 파일만 가져온다.

| 필드 | 필수 여부 | 기본값 | 설명 |
|------|-----------|--------|------|
| `owner` | 필수 | - | 저장소 소유자(사용자 또는 조직) |
| `repo` | 필수 | - | 저장소 이름 |
| `branch` | 선택 | `main` | 동기화할 브랜치 |
| `path_prefix` | 선택 | - | 이 경로 아래 파일만 포함 |
| `auth_token_secret` | 선택 | - | GitHub PAT, Bearer 인증으로 사용. 시크릿 필드(암호화 저장) |
| `max_file_size_mb` | 선택 | `5` | 다운로드할 파일의 최대 크기(MB) |
| `max_files` | 선택 | `200` | sync당 처리할 최대 파일 수 |
| `request_delay_ms` | 선택 | `100` | API 호출 사이 대기 시간(ms) |
| `request_timeout_sec` | 선택 | `30` | HTTP 타임아웃(초) |

API rate limit(403/429) 응답을 받으면 `Retry-After` 또는 `X-RateLimit-Reset` 헤더를 보고
자동으로 대기한 뒤 재요청한다.

## 시크릿 필드 암호화

`auth_token_secret` / `auth_headers` / `auth_basic`은 저장 전 Fernet(AES-128-CBC)으로
암호화되고, 조회 응답에서는 항상 `"********************"`(20자 마스크)로 치환되어
평문이 API로 노출되지 않는다.

```bash
curl http://localhost:8000/api/connectors/c-abcdef0123456789
# config.auth_token_secret 은 마스크 값으로 반환된다
```

PATCH로 `config`를 보낼 때 시크릿 필드에 마스크 값을 그대로 다시 담아 보내면 "값 변경 없음"
으로 처리되어 기존 암호화된 값이 유지된다. 실제 값을 바꾸려면 새 평문 값을 담아 보낸다.

암호화 키는 환경변수 `CONNECTOR_SECRET_KEY`(URL-safe base64, 32바이트)로 지정한다. 설정하지
않으면 코드에 내장된 고정 키로 폴백하므로, 프로덕션 배포에서는 반드시 별도로 지정해야 한다.

## 수동 sync 실행·중단

```bash
# 수동 sync 시작 — status가 paused거나 이미 sync_status가 running이면 409
curl -X POST http://localhost:8000/api/connectors/c-abcdef0123456789/sync

# 진행 중인 sync 중단 — sync_status가 running이 아니면 409
curl -X POST http://localhost:8000/api/connectors/c-abcdef0123456789/sync/abort
```

abort는 커넥터의 크롤/페치 루프에 중단 신호를 보내 다음 페이지 요청 전에 멈추고, 이 커넥터
소속으로 처리 중이던 문서를 실패 처리한 뒤 관련 Dagster run을 강제 종료한다. sync 실패와
abort로 인한 중단은 커넥터 `status`에 미치는 영향이 다르다 — 자세한 전이 규칙은
[커넥터 상태 흐름](../../concepts/connector-lifecycle.md#sync-실패와-abort의-차이) 참고.

## 자동 sync 스케줄

`sync_schedule`(cron 표현식)을 지정하면 Dagster Schedule이 등록되어 그 주기로
`connector_sync_op`이 자동 실행된다. `sync_schedule`과 `schedule_enabled`은 반영 방식이
다르다.

- `sync_schedule`(cron 표현식 자체)을 만들거나 바꾸면 Dagster 워크스페이스 reload가
  필요하다 — 생성·수정 API가 이를 백그라운드 작업으로 자동 트리거한다.
- `schedule_enabled`는 스케줄 실행 시점에 매번 조회해서 확인하므로, 켜고 끄는 데 reload가
  필요 없다. `false`면 스케줄은 등록된 채로 매 실행을 건너뛴다(`SkipReason`).

커넥터가 `paused` 상태면 `schedule_enabled=true`여도 스케줄 실행이 건너뛰어진다. 자동
스케줄이 오래 `running`으로 멈춰 있는 stale lock을 어떻게 복구하는지는
[커넥터 상태 흐름](../../concepts/connector-lifecycle.md#자동-스케줄과-stale-lock)에서
다룬다.

이 스케줄은 Dagster 배포 모드에서만 동작한다 — `queue_worker.enabled: true`로 Dagster 없이
운영하는 배포에서는 워크스페이스 reload가 no-op이므로 `sync_schedule`을 등록해도 자동
실행되지 않고, 수동 `POST /sync` 또는 외부 스케줄러로 트리거해야 한다.

## sync 상태·문서 목록 조회

```bash
# 현재 상태와 문서 개수 요약
curl http://localhost:8000/api/connectors/c-abcdef0123456789/sync/status

# 이 커넥터가 만든 문서 목록 — 페이지네이션, status/search 필터
curl "http://localhost:8000/api/connectors/c-abcdef0123456789/docs?page=1&page_size=20&status=indexed"
```

`sync/status`는 `status`, `sync_status`, `sync_started_at`, `last_synced_at`, `last_error`와
함께 문서 상태별 개수(`doc_counts`)를 반환한다. 문서 개별 상태값(`pending`/`indexed`/
`failed` 등)의 전이 규칙은 [문서 상태 흐름](../../concepts/document-lifecycle.md) 참고.
