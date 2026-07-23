---
sidebar_position: 3
---

# Runbook

백업·복구·업그레이드·장애 대응 절차를 배포 방식별로 다룬다. Kubernetes 배포는 [A절](#a-kubernetes-배포),
Docker Compose 배포는 [B절](#b-docker-compose-배포)을 참고한다.

---

## A. Kubernetes 배포

백업·복구·업그레이드 절차를 다룬다. A.1~A.3(백업·복구)은 확정 절차이며, A.4(업그레이드·롤백)의
일부와 A.5(일상 운영 참조)는 후속 버전에서 보강될 예정이다.

### A.1 백업 대상

이 제품의 데이터는 세 저장소에 분산되어 있으며, **세 곳을 함께 백업해야 복원 가능한
일관된 상태**가 된다.

| 저장소 | 내용 | 유실 시 영향 |
|--------|------|-------------|
| PostgreSQL (`rag-api` DB) | KB·문서·커넥터·권한 메타데이터 | 전체 관리 정보 유실 — 최우선 백업 대상 |
| S3 (`rag-api` 버킷) | 원본 문서 파일 | 원본 유실 — 재업로드 없이는 재인덱싱 불가 |
| Qdrant | 벡터 인덱스 | **재생성 가능** — Postgres+S3만 있으면 전체 재인덱싱으로 복원 가능 (시간 소요) |
| PostgreSQL (`dagster` DB) | 파이프라인 실행 이력 | 이력만 유실 — 서비스 데이터 아님, 백업 선택 |
| 설정 파일 (settings.yaml, k8s Secret) | 배포 구성 | 재설치 불가 — 형상 관리 필수 |

### A.2 백업 절차

#### A.2.1 일관성 원칙

문서 인제스트가 진행 중일 때 백업하면 세 저장소 간 불일치(예: Postgres에는 있는데
Qdrant에 없는 문서)가 생길 수 있다. 권장 순서:

1. 백업 시작 전 처리 중 문서가 없는지 확인:

   ```bash
   curl http://<api>/api/docs/status
   # 모든 KB의 pending + running = 0 확인
   ```

2. 커넥터 스케줄이 백업 시간대와 겹치지 않게 조정 (또는 일시 pause).
3. Postgres → Qdrant → S3 순으로 백업.

불일치가 생겨도 문서 단위 재인덱싱으로 교정 가능하므로(A.3.3), 무중단 백업도 허용된다.

#### A.2.2 PostgreSQL

```bash
pg_dump -h <host> -U rag-api -d rag-api -Fc -f rag-api_$(date +%Y%m%d).dump
# 선택: dagster DB
pg_dump -h <host> -U dagster -d dagster -Fc -f dagster_$(date +%Y%m%d).dump
```

HA 구성(CloudNativePG 등)을 사용하는 경우 해당 오퍼레이터의 스케줄 백업 기능(WAL 아카이빙
포함)을 우선 사용한다. 위 명령은 CronJob으로 매일 자동 실행하도록 구성하고, 산출물은
별도 버킷(예: MinIO `pg-backup`)에 보관하는 것을 권장한다.

원본을 건드리지 않고 백업이 실제로 복원 가능한지 주기적으로 점검하려면 CronJob
`cnpg-postgres-restore`(같은 위치, `suspend: true` — 수동 트리거 전용)를 쓴다. 최신 덤프를
별도 스키마(`RESTORE_SCHEMA` env, 기본 `restore_test`)에 복원해 원본과 row count를 비교하고
끝나면 자동 삭제한다. 복원한 데이터를 실제로 꺼내 써야 하면 `CLEANUP_SCHEMA_AFTER=false`로
트리거해 스키마를 남긴다: `kubectl create job --from=cronjob/cnpg-postgres-restore`.

#### A.2.3 Qdrant

```bash
# 전체 스냅숏 생성 (컬렉션별로도 가능)
curl -X POST http://<qdrant>:6333/snapshots
# 생성된 스냅숏 파일을 외부 스토리지로 복사 (기본 경로: /qdrant/storage/snapshots)
```

또는 Qdrant를 재생성 대상으로 정하고 백업을 생략할 수 있다 (복구 시간 대신 백업 비용 절감
— 문서량이 크면 재인덱싱에 수 시간 이상 소요될 수 있으므로 규모에 따라 판단).

#### A.2.4 S3 (MinIO)

```bash
mc mirror <alias>/rag-api <백업 대상 경로 또는 원격 alias>/rag-api-backup
```

기존 S3 인프라를 쓰는 경우 해당 스토리지의 버전닝/복제 정책을 활용한다. 위 명령은
CronJob으로 매일 자동 실행하도록 구성할 수 있다(`--remove` 미사용 권장 — 원본에서
삭제된 파일도 백업엔 남겨 복구 가치를 유지).

#### A.2.5 권장 주기

| 대상 | 주기 |
|------|------|
| PostgreSQL(rag-api) | 일 1회 + (HA 구성 시) WAL 연속 아카이빙 |
| S3 | 일 1회 증분 (mirror) |
| Qdrant | 주 1회 (또는 재생성 정책 선택 시 생략) |
| 설정·Secret | 변경 시마다 (형상 관리) |

### A.3 복구 절차

#### A.3.1 전체 복구

1. 인프라(Postgres/Redis/Qdrant/S3) 기동, 애플리케이션은 아직 중지 상태.
2. Postgres 복원:

   ```bash
   pg_restore -h <host> -U rag-api -d rag-api --clean rag-api_<날짜>.dump
   ```

3. S3 복원: `mc mirror <백업>/rag-api-backup <alias>/rag-api`
4. Qdrant 복원: 스냅숏 업로드 후 recover API 호출 (스냅숏이 없으면 A.3.2로 재생성).
5. 애플리케이션 기동 → `/ready` 통과 확인.
6. 정합성 점검: `GET /api/docs/status`의 KB별 `indexed` 수와 Qdrant 컬렉션 포인트 수가
   상식적으로 부합하는지 확인. 어긋난 KB는 A.3.3으로 교정.

#### A.3.2 Qdrant 없이 복구 (벡터 재생성)

Postgres + S3만 있으면 강제 재인덱싱으로 복구된다. 컬렉션이 없으면 자동 생성되고, 있으면
문서별로 기존 벡터를 덮어쓰므로 별도로 지울 필요는 없다:

```bash
# 토큰 발급(Keycloak ROPC, issuer_url은 settings.yaml의 oidc.issuer_url) 후 강제 재인덱싱
TOKEN=$(curl -s -X POST "<issuer_url>/protocol/openid-connect/token" \
  -d "grant_type=password" -d "client_id=<client_id>" -d "client_secret=<client_secret>" \
  -d "username=<user>" -d "password=<password>" -d "scope=openid" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST "http://<api>/api/kb/<kb_id>/reindex?force=true" -H "Authorization: Bearer ${TOKEN}"
```

컬렉션 스키마(벡터 크기 등)가 깨져서 `vector_size mismatch` 에러가 나는 경우에만
`curl -X DELETE "http://<qdrant>:6333/collections/<kb_id>"`로 컬렉션 자체를 지운 뒤
위 명령을 실행한다.

`status=outdated` 문서는 스킵되지만(dedup에서 진 쪽 — `pipeline/ops/dedup/verdict.py`)
콘텐츠는 `duplicate_of`가 가리키는 `indexed` 짝이 커버하므로 손실은 아니다.

문서량에 비례해 시간이 걸린다 (임베딩 서버 성능이 병목). 진행 상황은
`GET /api/kb/<kb_id>/docs/status`로 추적한다.

#### A.3.3 부분 불일치 교정

- 특정 문서가 검색에 안 나옴 → 해당 문서 강제 재인덱싱:
  `POST /api/kb/<kb>/docs/<doc_id>/reindex?force=true`
- `running`에 고착된 문서 → 복구 API: `POST /api/kb/<kb>/docs/<doc_id>/recover`
- 실패 문서 일괄 확인: `GET /api/docs?status=failed` → `last_error` 확인 후 재인덱싱.

### A.4 업그레이드·롤백

#### A.4.1 버전 체계

이미지는 `ghcr.io/cnapcloud/<repo>:vMAJOR.MINOR.PATCH` 형식으로 태깅된다. 태그는 자동 증가가
아니라 릴리스 시점에 사람이 직접 생성한다:

```bash
git tag v1.2.0 && git push origin v1.2.0
```

이 push가 CI를 트리거해 `pytest`/`ruff`/`mypy`(또는 프론트엔드 typecheck/lint/build)를 통과한
뒤 그 태그명으로 이미지를 빌드·푸시한다 (`:latest`도 함께 갱신됨). 태그가 CI를 통과하지
못하면 이미지가 존재하지 않으므로, "태그가 있다 = 테스트를 통과했다"는 보장이 성립한다.

#### A.4.2 배포

`k8s/helm/values.yaml`(또는 환경별 `values.yaml`)의 `image.tag`가 실제 배포할 rag-api
이미지 태그를 결정한다 ([kubernetes.md](kubernetes.md) §4 참조):

```yaml
image:
  repository: ghcr.io/cnapcloud/rag-api
  tag: v1.2.0                            # 배포할 버전
```

값을 원하는 버전으로 바꾸고 아래처럼 반영한다(또는 GitOps 파이프라인으로):

```bash
cd k8s
helm upgrade --install rag oci://ghcr.io/cnapcloud/charts/rag-platform \
  --version <차트 버전> \
  -n rag -f values.yaml
```

패키지가 public이라 별도 로그인은 필요 없다. `--atomic`을 붙이지 않으면 실패 시 자동
롤백되지 않는다 — 실패하면 원인을 바로잡고 `helm uninstall rag -n rag` 후 다시 설치하거나,
스키마 변경이 없었다면 A.4.4의 `helm rollback`으로 되돌린다. 동일한 흐름을 감싼
`make upgrade`(및 `check-cnpg`로 cnpg-operator 존재를 먼저 확인하는 것)를
`k8s/Makefile`에서도 쓸 수 있다([kubernetes.md](kubernetes.md) §4 참조).

`imagePullPolicy`는 고정 태그를 쓰는 한 `IfNotPresent`로 충분하다 — `Always`는 `:latest`처럼
태그가 재사용될 때만 의미가 있으므로, 고정 태그로 운영한다면 `values.yaml`에서
`IfNotPresent`로 바꿔두면 불필요한 재다운로드를 줄일 수 있다.

#### A.4.3 업그레이드 절차

1. **업그레이드 직전 Postgres 백업(A.2.2) 필수 수행** — DB 스키마 마이그레이션은 API 서버
   기동 시 자동 적용되며 자동 롤백되지 않는다.
2. 한 번에 하나의 버전 단계만 올린다 (여러 버전을 건너뛰지 않음).
3. `values.yaml`의 `image.tag`를 목표 버전으로 변경 후 A.4.2의 명령으로 적용.
4. [첫 KB와 검색](../getting-started/first-kb-and-query.md) 스모크 테스트 수행.

#### A.4.4 롤백 절차

스키마 마이그레이션이 없는 패치 업그레이드라면:

1. `values.yaml`의 `image.tag`를 직전 버전으로 되돌리고 A.4.2의 명령으로 재적용한다.
   또는 `helm rollback rag <REVISION> -n rag`로 직전 release revision으로 바로 되돌릴 수
   있다 — `helm history rag -n rag`로 revision 번호를 확인한다(마찬가지로 스키마
   마이그레이션이 없는 경우에만 안전하다).
2. `/ready` 및 [첫 KB와 검색](../getting-started/first-kb-and-query.md) 스모크 테스트로 정상 동작 확인.

스키마 마이그레이션이 포함된 업그레이드였다면 이미지만 되돌려서는 안 된다 — 새 스키마와 이전
코드가 맞지 않을 수 있으므로, A.3.1 절차대로 **업그레이드 직전 백업(A.4.3-1)에서 Postgres를
복원**한 뒤 이전 이미지 태그로 되돌린다.

### A.5 일상 운영 참조 (개요 — 차기 보강)

| 작업 | 방법 |
|------|------|
| 인제스트 현황 모니터링 | `GET /api/docs/status`, Dagster UI |
| 실패 문서 처리 | `status=failed` 필터 → `last_error` 확인 → 재인덱싱 또는 원본 교체 |
| 고착 문서(장시간 running) | recover API — 콘솔 Documents 화면에서도 가능 |
| 커넥터 장애 | 커넥터 목록의 `last_error` 확인, pause/resume, sync abort |
| 처리 중 작업 강제 중단 | Dagster 모드에서만 완전 지원 — [알려진 제약](../support/known-limitations.md) |

---

## B. Docker Compose 배포

Core 배포(docker-compose) 기준 운영 절차를 다룬다. k8s/Enterprise 배포는 [A절](#a-kubernetes-배포) 참고.

### B.0 빠른 참조

자주 쓰는 명령어 모음. 상세 설명은 각 섹션 참고.

```bash
# 전체 상태 확인
docker compose ps
curl -s http://localhost:8000/ready | jq

# API 생존 확인
curl -s http://localhost:8000/health

# Redis 큐 대기 수 확인
docker exec redis redis-cli -a <REDIS_PASSWORD> LLEN rag:upload:queue
docker exec redis redis-cli -a <REDIS_PASSWORD> LLEN rag:delete:queue

# Dagster 센서 상태
docker exec dagster-daemon dagster sensor list -w /opt/dagster/workspace.yaml

# 로그 확인
docker compose logs --tail=100 rag-api
docker compose logs --tail=100 dagster-daemon

# 수동 재인덱스 (변경분만)
curl -X POST http://localhost:8000/api/kb/kb-01/reindex

# 전체 재시작
docker compose down && docker compose up -d
```

### B.1 서비스 헬스체크

#### B.1.1 컨테이너 상태 확인

```bash
docker compose ps
```

모든 컨테이너가 `healthy` 또는 `running`이어야 한다.
`minio-init`는 초기화 후 `Exited (0)`이 정상이다.

| 컨테이너 | 정상 상태 |
|---|---|
| `postgresql` | healthy |
| `redis` | healthy |
| `qdrant` | healthy |
| `minio` | healthy |
| `minio-init` | Exited (0) |
| `rag-api` | running |
| `rag-admin` | running |
| `dagster-rag-api` | running |
| `dagster-webserver` | running |
| `dagster-daemon` | running |

#### B.1.2 API 헬스체크

**생존 확인** (rag-api 프로세스만 확인)

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

**준비 확인** (Qdrant, Redis, Postgres, MinIO, 임베딩 모델 연결 모두 확인)

```bash
curl -s http://localhost:8000/ready | jq
```

모든 항목이 `true`여야 한다.

```json
{
  "status": "ready",
  "checks": {
    "qdrant": true,
    "redis": true,
    "postgres": true,
    "s3": true,
    "ollama": true
  }
}
```

`"status": "not_ready"`이면 `false`인 항목이 연결 실패다.

#### B.1.3 문서 처리 상태 확인

인덱싱이 정상적으로 진행 중인지 확인한다.

```bash
# KB 내 문서 상태 목록
curl -s "http://localhost:8000/api/kb/kb-01/docs?page_size=20" | jq '.items[] | {doc_id, status, source}'

# 실패한 문서 확인
curl -s "http://localhost:8000/api/kb/kb-01/docs?status=failed" | jq '.items[] | {doc_id, source, last_error}'

# 처리 중인 문서 확인
curl -s "http://localhost:8000/api/kb/kb-01/docs?status=running" | jq '.total'
```

#### B.1.4 Dagster 센서 상태

```bash
docker exec dagster-daemon dagster sensor list -w /opt/dagster/workspace.yaml
```

`event_queue_sensor` 상태가 `RUNNING`이어야 한다.

Dagster UI(포트 3000)에서도 확인할 수 있다:
`Deployment > grpc:dagster-rag-api:4000 > Sensors`

### B.2 장애 대응 Runbook

#### B.2.1 파일 업로드 후 문서 상태가 변하지 않을 때

순서대로 확인한다.

**Step 1 — rag-api가 enqueue했는지 확인**

```bash
docker compose logs --tail=50 rag-api | grep "enqueued\|enqueue"
```

`Upload event enqueued: doc_id=...` 로그가 없으면 API 호출 자체에 문제.
rag-api 로그에서 에러를 찾는다.

**Step 2 — Redis 큐에 이벤트가 있는지 확인**

```bash
docker exec redis redis-cli -a <REDIS_PASSWORD> LLEN rag:upload:queue
docker exec redis redis-cli -a <REDIS_PASSWORD> ZCARD rag:upload:delay
```

| 상태 | 의미 |
|------|------|
| 둘 다 0 | 센서가 이미 소비했거나 enqueue가 안 된 것 |
| `upload:queue` > 0 | 센서가 소비를 못 하고 있음 → Step 3 |
| `upload:delay` > 0 | 동일 doc이 실행 중(`running`/`deleting`)이어서 대기 중 → Step 3 후 zombie run 확인 |

**Step 3 — Dagster 센서 상태 확인**

```bash
docker exec dagster-daemon dagster sensor list -w /opt/dagster/workspace.yaml
docker compose logs --tail=100 dagster-daemon | grep -i "error\|warn\|sensor"
```

센서가 `STOPPED`면 → [B.2.2 Dagster 센서가 멈췄을 때] 진행.

**Step 4 — Dagster job 실행 기록 확인**

Dagster UI(포트 3000) > Runs 에서 최근 `ingest_job` 실행 결과를 확인한다.
실패한 run을 클릭하면 어느 op에서 에러가 났는지 볼 수 있다.

#### B.2.2 Dagster 센서가 멈췄을 때 (STOPPED)

`dagster-rag-api` gRPC 서버가 내려가면 센서가 자동 중지된다.

**Step 1 — dagster-rag-api 상태 확인**

```bash
docker compose ps dagster-rag-api
docker compose logs --tail=50 dagster-rag-api
```

**Step 2 — dagster-rag-api 재시작**

```bash
docker compose restart dagster-rag-api
```

재시작 후 daemon 로그에 아래 메시지가 나오면 연결 복구된 것이다.

```
Received LocationStateChangeEventType.LOCATION_UPDATED event for location grpc:dagster-rag-api:4000
```

**Step 3 — 재시작 전 실행 중이던 run 강제 종료**

`dagster-rag-api` 재시작 전에 실행 중이던 run은 프로세스가 사라졌지만 Dagster DB에 `STARTED` 상태로 남는다.
이 상태가 남아 있으면 센서가 해당 doc_id를 "실행 중"으로 보고 이벤트를 delay queue에 계속 밀어넣어 처리가 멈춘다.

Dagster UI(포트 3000) > Runs 에서 `STARTED` 상태인 run을 찾아 우측 상단 `Terminate` 버튼으로 강제 종료한다.

CLI로 일괄 처리:

```bash
# STARTED 상태 run ID 목록 조회
docker exec dagster-daemon dagster run list -w /opt/dagster/workspace.yaml --status STARTED

# 개별 강제 종료
docker exec dagster-daemon dagster run terminate <run_id> -w /opt/dagster/workspace.yaml
```

종료 후 해당 문서의 상태가 `failed`로 바뀐다. 이후 reindex로 재처리한다.

**Step 4 — 센서 수동 시작**

자동으로 `RUNNING`이 되지 않으면 수동으로 시작한다.

```bash
docker exec dagster-daemon dagster sensor start event_queue_sensor -w /opt/dagster/workspace.yaml
```

또는 Dagster UI > Sensors > `event_queue_sensor` > Running 토글.

#### B.2.3 Redis 큐가 계속 쌓일 때

**원인 1 — Dagster job이 계속 실패하는 경우**

```bash
docker compose logs --tail=200 dagster-daemon | grep -i "error\|failed"
```

Dagster UI > Runs 에서 실패한 run 상세 확인.

**원인 2 — 동일 문서가 `running` 상태에서 멈춘 경우 (zombie run)**

```bash
# 오래된 running 문서 확인 (Postgres)
docker exec postgresql psql -U rag-api -d rag-api -c \
  "SELECT doc_id, source, status, process_started_at FROM documents \
   WHERE status = 'running' AND process_started_at < NOW() - INTERVAL '30 minutes';"
```

zombie run이 있으면 해당 문서를 `failed`로 수동 초기화한다.

```bash
docker exec postgresql psql -U rag-api -d rag-api -c \
  "UPDATE documents SET status = 'failed', last_error = 'manually reset' \
   WHERE status = 'running' AND process_started_at < NOW() - INTERVAL '30 minutes';"
```

이후 수동 reindex로 재처리한다.

```bash
curl -X POST http://localhost:8000/api/kb/kb-01/docs/<doc_id>/reindex
```

#### B.2.4 rag-api가 기동하지 않을 때

인프라 4개가 모두 healthy인지 먼저 확인한다.

```bash
docker compose ps postgresql redis qdrant minio
```

healthy가 아닌 컨테이너가 있으면 해당 컨테이너 로그를 확인한다.

```bash
docker compose logs --tail=50 postgresql
```

모두 healthy인데도 기동 안 되면:

```bash
docker compose logs --tail=100 rag-api
```

`/ready` 엔드포인트 응답의 `false` 항목이 연결 실패 원인이다.

#### B.2.5 커넥터 동기화가 진행되지 않을 때

**스케줄 기반 동기화**

Dagster UI(포트 3000) > Schedules 에서 해당 커넥터 스케줄(`connector_sync_<id>`)이 `RUNNING` 상태인지 확인한다.

`STOPPED`면 `dagster-rag-api`를 재시작한다 (스케줄은 재시작 시 자동 복구됨).

**수동 동기화**

```bash
curl -X POST http://localhost:8000/api/connectors/<connector_id>/sync
```

**동기화 중 abort**

```bash
curl -X POST http://localhost:8000/api/connectors/<connector_id>/sync/abort
```

### B.3 일상 운영

#### B.3.1 로그 확인

```bash
# rag-api (업로드, 검색, API 에러)
docker compose logs --tail=100 -f rag-api

# Dagster daemon (센서, job 실행)
docker compose logs --tail=100 -f dagster-daemon

# Dagster gRPC 서버 (definitions 로드 에러)
docker compose logs --tail=50 dagster-rag-api

# 모든 컨테이너
docker compose logs --tail=50
```

#### B.3.2 Redis 큐 상태 확인

```bash
docker exec redis redis-cli -a <REDIS_PASSWORD>
LLEN rag:upload:queue    # 업로드 대기 수
LLEN rag:delete:queue    # 삭제 대기 수
ZCARD rag:upload:delay   # 재시도 대기 중인 업로드 수
ZCARD rag:delete:delay   # 재시도 대기 중인 삭제 수
```

#### B.3.3 수동 재인덱스

**변경된 문서만 재처리** (ETag 비교, 정상 복구 시 우선 사용)

```bash
curl -X POST http://localhost:8000/api/kb/kb-01/reindex
```

**전체 강제 재인덱스** (인덱스 전체를 새로 쌓아야 할 때)

```bash
curl -X POST "http://localhost:8000/api/kb/kb-01/reindex?force=true"
```

부하가 크므로 트래픽이 적은 시간대에 실행한다.

**단일 문서 재인덱스**

```bash
curl -X POST http://localhost:8000/api/kb/kb-01/docs/<doc_id>/reindex
```

#### B.3.4 Dagster 센서 관리

**센서 중지** (점검·배포 전, 진행 중 job이 끊기는 것을 방지)

```bash
docker exec dagster-daemon dagster sensor stop event_queue_sensor -w /opt/dagster/workspace.yaml
```

**센서 시작**

```bash
docker exec dagster-daemon dagster sensor start event_queue_sensor -w /opt/dagster/workspace.yaml
```

### B.4 배포 및 업데이트

#### B.4.1 코드 업데이트 배포

인프라가 먼저 실행 중이어야 한다.

```bash
docker compose up -d postgresql redis qdrant minio
```

애플리케이션 이미지는 로컬 빌드이므로 `pull`이 아닌 `build`를 사용한다.

```bash
docker compose build rag-api dagster-rag-api
docker compose up -d rag-api dagster-rag-api
```

배포 후 확인:

```bash
curl -s http://localhost:8000/health
docker exec dagster-daemon dagster sensor list -w /opt/dagster/workspace.yaml
```

#### B.4.2 롤백

이전 이미지 태그가 있는 경우:

```bash
# docker-compose.yml의 image 태그를 이전 버전으로 변경 후
docker compose up -d rag-api dagster-rag-api
```

이미지 태그가 없는 경우 git으로 소스를 되돌리고 재빌드한다.

```bash
git checkout <이전 커밋>
docker compose build rag-api dagster-rag-api
docker compose up -d rag-api dagster-rag-api
```

#### B.4.3 커넥터 스케줄 변경 후 재시작

커넥터의 cron 표현식(`sync_schedule`)을 변경하면 Dagster가 반영하려면 재시작이 필요하다.

```bash
docker compose restart dagster-rag-api
```

재시작 후 Dagster UI > Schedules 에서 변경된 cron이 반영됐는지 확인한다.

> `schedule_enabled` 필드(API `PATCH /api/connectors/{id}`)는 재시작 없이 즉시 반영된다.

#### B.4.4 인프라 이미지 업데이트

```bash
docker compose pull postgresql redis qdrant minio
docker compose up -d postgresql redis qdrant minio
```

#### B.4.5 전체 재시작

```bash
docker compose down
docker compose up -d
```

전체 재시작 후 체크리스트:

1. `docker compose ps` — 모든 컨테이너 `healthy` 또는 `running`
2. `minio-init` — `Exited (0)` 확인
3. `curl -s http://localhost:8000/ready | jq` — 모든 체크 `true`
4. Dagster 센서 `RUNNING` 확인

### B.5 초기 설정 (일회성)

#### B.5.1 자격증명 변경

`docker/.env`와 `docker/settings.yaml`의 초기값은 개발·테스트용이다. 프로덕션 배포 전에 반드시 변경한다.

**PostgreSQL**

`docker/init-db.sql`에서 유저·패스워드를 수정한다.
이 파일은 `pg_data` 볼륨이 없을 때 최초 기동 시에만 실행된다.

```sql
CREATE USER dagster WITH PASSWORD '새패스워드';
CREATE DATABASE dagster OWNER dagster;
CREATE USER "rag-api" WITH PASSWORD '새패스워드';
CREATE DATABASE "rag-api" OWNER "rag-api";
```

`docker/settings.yaml`과 `docker/docker-compose.yml`의 `DAGSTER_POSTGRES_URL`도 함께 수정한다.

```yaml
# docker/settings.yaml
postgres:
  password: "새패스워드"

# docker/docker-compose.yml (Dagster 컨테이너 3개 모두)
DAGSTER_POSTGRES_URL: postgresql://dagster:새패스워드@postgresql:5432/dagster
```

> 볼륨이 이미 생성된 상태에서 패스워드를 변경하려면 `docker compose down -v`로 볼륨을 삭제 후 재기동해야 한다. 저장된 데이터가 모두 삭제되므로 주의한다.

**Redis**

```bash
# docker/.env
REDIS_PASSWORD=새패스워드
```

```yaml
# docker/settings.yaml
redis:
  password: "새패스워드"
```

**MinIO**

```bash
# docker/.env
MINIO_ROOT_USER=새유저
MINIO_ROOT_PASSWORD=새패스워드
```

```yaml
# docker/settings.yaml
s3:
  access_key: "새유저"
  secret_key: "새패스워드"
```

MinIO 재기동 후 `minio-init`를 재실행해 버킷을 다시 초기화한다.

#### B.5.2 MinIO 초기화

`minio-init` 컨테이너가 최초 기동 시 버킷 생성(`rag-api`, `dagster-storage`)을 처리한다.

MinIO 재시작 후 버킷이 없어진 경우 재실행한다.

```bash
docker compose run --rm minio-init
```

이미 존재하는 버킷은 건너뛰므로 반복 실행해도 안전하다.

#### B.5.3 Redis AOF 영속성

기본 설정은 RDB 스냅샷 모드다. Redis 재시작 시 마지막 스냅샷 이후의 미처리 큐 이벤트가 유실될 수 있다.

AOF를 활성화하려면 `docker/docker-compose.yml`의 redis `command`를 수정한다.

```yaml
redis:
  command: redis-server --requirepass ${REDIS_PASSWORD:-redis} --appendonly yes --appendfsync everysec
```

```bash
docker compose up -d --no-deps redis
```

큐가 유실된 경우 AOF 여부와 무관하게 reindex로 복구할 수 있다.

### B.6 참고

컨테이너 구성, 이벤트 처리 흐름, 기동 의존 순서, 오브젝트 스토리지 레이아웃 등 배경
정보는 [Docker Compose 컴포넌트 참조](../reference/docker-compose.md)를 참고한다.
