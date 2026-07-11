# 운영 Runbook

| 항목 | 내용 |
|------|------|
| 대상 | 운영 담당자 |
| 범위 | 백업·복구(§1~§3), 업그레이드·롤백(§4)이 확정 절차. §4.2는 aiops 고정 태그 전환 완료 후 실제 적용 가능(2026-07-10 기준 미완). §5는 개요 수준 — 차기 갱신에서 보강 예정 |

---

## 1. 백업 대상

이 제품의 데이터는 세 저장소에 분산되어 있으며, **세 곳을 함께 백업해야 복원 가능한
일관된 상태**가 된다.

| 저장소 | 내용 | 유실 시 영향 |
|--------|------|-------------|
| PostgreSQL (`rag-api` DB) | KB·문서·커넥터·권한 메타데이터 | 전체 관리 정보 유실 — 최우선 백업 대상 |
| S3 (`rag-api` 버킷) | 원본 문서 파일 | 원본 유실 — 재업로드 없이는 재인덱싱 불가 |
| Qdrant | 벡터 인덱스 | **재생성 가능** — Postgres+S3만 있으면 전체 재인덱싱으로 복원 가능 (시간 소요) |
| PostgreSQL (`dagster` DB) | 파이프라인 실행 이력 | 이력만 유실 — 서비스 데이터 아님, 백업 선택 |
| 설정 파일 (settings.yaml, k8s Secret) | 배포 구성 | 재설치 불가 — 형상 관리 필수 |

## 2. 백업 절차

### 2.1 일관성 원칙

문서 인제스트가 진행 중일 때 백업하면 세 저장소 간 불일치(예: Postgres에는 있는데
Qdrant에 없는 문서)가 생길 수 있다. 권장 순서:

1. 백업 시작 전 처리 중 문서가 없는지 확인:

   ```bash
   curl http://<api>/api/docs/status
   # 모든 KB의 pending + running = 0 확인
   ```

2. 커넥터 스케줄이 백업 시간대와 겹치지 않게 조정 (또는 일시 pause).
3. Postgres → Qdrant → S3 순으로 백업.

불일치가 생겨도 문서 단위 재인덱싱으로 교정 가능하므로(§3.3), 무중단 백업도 허용된다.

### 2.2 PostgreSQL

```bash
pg_dump -h <host> -U rag-api -d rag-api -Fc -f rag-api_$(date +%Y%m%d).dump
# 선택: dagster DB
pg_dump -h <host> -U dagster -d dagster -Fc -f dagster_$(date +%Y%m%d).dump
```

HA 구성(CloudNativePG 등)을 사용하는 경우 해당 오퍼레이터의 스케줄 백업 기능(WAL 아카이빙
포함)을 우선 사용한다. aiops 배포에서는 이 명령이 CronJob `cnpg-postgres-backup`
(`aiops/infra/cnpg/cluster`)으로 매일 자동 실행되며, 산출물은 MinIO `pg-backup` 버킷에
쌓인다.

원본을 건드리지 않고 백업이 실제로 복원 가능한지 주기적으로 점검하려면 CronJob
`cnpg-postgres-restore`(같은 위치, `suspend: true` — 수동 트리거 전용)를 쓴다. 최신 덤프를
별도 스키마(`RESTORE_SCHEMA` env, 기본 `restore_test`)에 복원해 원본과 row count를 비교하고
끝나면 자동 삭제한다. 복원한 데이터를 실제로 꺼내 써야 하면 `CLEANUP_SCHEMA_AFTER=false`로
트리거해 스키마를 남긴다: `kubectl create job --from=cronjob/cnpg-postgres-restore`.

### 2.3 Qdrant

```bash
# 전체 스냅숏 생성 (컬렉션별로도 가능)
curl -X POST http://<qdrant>:6333/snapshots
# 생성된 스냅숏 파일을 외부 스토리지로 복사 (기본 경로: /qdrant/storage/snapshots)
```

또는 Qdrant를 재생성 대상으로 정하고 백업을 생략할 수 있다 (복구 시간 대신 백업 비용 절감
— 문서량이 크면 재인덱싱에 수 시간 이상 소요될 수 있으므로 규모에 따라 판단).

### 2.4 S3 (MinIO)

```bash
mc mirror <alias>/rag-api <백업 대상 경로 또는 원격 alias>/rag-api-backup
```

기존 S3 인프라를 쓰는 경우 해당 스토리지의 버전닝/복제 정책을 활용한다. aiops
배포에서는 CronJob `minio-rag-api-mirror`(`aiops/infra/minio`)가 매일 자동 실행한다
(`--remove` 미사용 — 원본에서 삭제된 파일도 백업엔 남겨 복구 가치를 유지).

### 2.5 권장 주기

| 대상 | 주기 |
|------|------|
| PostgreSQL(rag-api) | 일 1회 + (HA 구성 시) WAL 연속 아카이빙 |
| S3 | 일 1회 증분 (mirror) |
| Qdrant | 주 1회 (또는 재생성 정책 선택 시 생략) |
| 설정·Secret | 변경 시마다 (형상 관리) |

## 3. 복구 절차

### 3.1 전체 복구

1. 인프라(Postgres/Redis/Qdrant/S3) 기동, 애플리케이션은 아직 중지 상태.
2. Postgres 복원:

   ```bash
   pg_restore -h <host> -U rag-api -d rag-api --clean rag-api_<날짜>.dump
   ```

3. S3 복원: `mc mirror <백업>/rag-api-backup <alias>/rag-api`
4. Qdrant 복원: 스냅숏 업로드 후 recover API 호출 (스냅숏이 없으면 §3.2로 재생성).
5. 애플리케이션 기동 → `/ready` 통과 확인.
6. 정합성 점검: `GET /api/docs/status`의 KB별 `indexed` 수와 Qdrant 컬렉션 포인트 수가
   상식적으로 부합하는지 확인. 어긋난 KB는 §3.3으로 교정.

### 3.2 Qdrant 없이 복구 (벡터 재생성)

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

### 3.3 부분 불일치 교정

- 특정 문서가 검색에 안 나옴 → 해당 문서 강제 재인덱싱:
  `POST /api/kb/<kb>/docs/<doc_id>/reindex?force=true`
- `running`에 고착된 문서 → 복구 API: `POST /api/kb/<kb>/docs/<doc_id>/recover`
- 실패 문서 일괄 확인: `GET /api/docs?status=failed` → `last_error` 확인 후 재인덱싱.

## 4. 업그레이드·롤백

### 4.1 버전 체계

이미지는 `ghcr.io/cnapcloud/<repo>:vMAJOR.MINOR.PATCH` 형식으로 태깅된다. 태그는 자동 증가가
아니라 릴리스 시점에 사람이 직접 생성한다:

```bash
git tag v1.2.0 && git push origin v1.2.0
```

이 push가 CI를 트리거해 `pytest`/`ruff`/`mypy`(또는 프론트엔드 typecheck/lint/build)를 통과한
뒤 그 태그명으로 이미지를 빌드·푸시한다 (`:latest`도 함께 갱신됨). 태그가 CI를 통과하지
못하면 이미지가 존재하지 않으므로, "태그가 있다 = 테스트를 통과했다"는 보장이 성립한다.

### 4.2 배포 (aiops)

각 컴포넌트의 `kustomize` 오버레이 `kustomization.yaml`의 `images:` 필드가 실제 배포 태그를
결정한다 (예: `aiops/llm/rag-api/kustomize/overlays/<env>/kustomization.yaml`):

```yaml
images:
  - name: cnapcloud/rag-api
    newName: ghcr.io/cnapcloud/rag-ent-api   # 레지스트리 접두사 aiops 쪽 반영 필요 (미완)
    newTag: v1.2.0                            # 배포할 버전
```

`newTag`를 원하는 버전으로 바꾸고 `kubectl apply -k <오버레이 경로>`(또는 GitOps 파이프라인)로
반영한다. `imagePullPolicy`는 고정 태그를 쓰는 한 `IfNotPresent`로 충분하다 — `Always`는
`:latest`처럼 태그가 재사용될 때만 의미가 있다.

### 4.3 업그레이드 절차

1. **업그레이드 직전 Postgres 백업(§2.2) 필수 수행** — DB 스키마 마이그레이션은 API 서버
   기동 시 자동 적용되며 자동 롤백되지 않는다.
2. 한 번에 하나의 버전 단계만 올린다 (여러 버전을 건너뛰지 않음).
3. `kustomization.yaml`의 `newTag`를 목표 버전으로 변경 후 적용.
4. [07-verification.md](07-verification.md) 스모크 테스트 수행.

### 4.4 롤백 절차

스키마 마이그레이션이 없는 패치 업그레이드라면:

1. `kustomization.yaml`의 `newTag`를 직전 버전으로 되돌리고 재적용.
2. `/ready` 및 [07-verification.md](07-verification.md) 스모크 테스트로 정상 동작 확인.

스키마 마이그레이션이 포함된 업그레이드였다면 이미지만 되돌려서는 안 된다 — 새 스키마와 이전
코드가 맞지 않을 수 있으므로, §3.1 절차대로 **업그레이드 직전 백업(4.3-1)에서 Postgres를
복원**한 뒤 이전 이미지 태그로 되돌린다.


## 5. 일상 운영 참조 (개요 — 차기 보강)

| 작업 | 방법 |
|------|------|
| 인제스트 현황 모니터링 | `GET /api/docs/status`, Dagster UI |
| 실패 문서 처리 | `status=failed` 필터 → `last_error` 확인 → 재인덱싱 또는 원본 교체 |
| 고착 문서(장시간 running) | recover API — 콘솔 Documents 화면에서도 가능 |
| 커넥터 장애 | 커넥터 목록의 `last_error` 확인, pause/resume, sync abort |
| 처리 중 작업 강제 중단 | Dagster 모드에서만 완전 지원 — [알려진 제약](../support/03-known-limitations.md) |
