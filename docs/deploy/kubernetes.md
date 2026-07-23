---
sidebar_position: 2
---

# Kubernetes 설치

운영 환경(k8s 운영 경험 전제)에 Helm 차트로 설치하는 표준 절차를 다룬다. 배포 매니페스트는
단일 umbrella Helm 차트(`k8s/helm/`)로 제공되며, `ghcr.io/cnapcloud/charts/rag-platform`
OCI 레지스트리에 공개(public) 패키지로 게시되어 있다 — 설치·업그레이드에는 별도 로그인이나
자격증명이 필요 없다. 이 문서는 `helm upgrade --install`로 OCI 참조를 직접 설치하는 방법을
기준으로 설명한다(§4). 저장소의 `k8s/Makefile`에도 동일한 동작을 하는
`install`/`upgrade`/`uninstall` 타깃이 있어 편의상 쓸 수 있다.

---

## 1. 배포 구성 개요

```
k8s/
  Makefile                  # install/upgrade/uninstall을 감싼 선택적 편의 타깃 (아래 표 참조)
  values.yaml.example      # 실값으로 채워 values.yaml로 복사 (gitignored) — secrets override
  helm/
    Chart.yaml               # 차트 메타데이터(이름: rag-platform) + 의존성 목록
    values.yaml              # 기본값 (체크인) — 단일 환경 기준
    templates/                # rag-api + rag-admin 리소스 (이 차트 자체 템플릿)
    charts/
      cnpg-cluster/            # 로컬 서브차트 — Postgres Cluster CR + 백업/복구 CronJob
      minio-jobs/              # 로컬 서브차트 — 버킷 부트스트랩 Job + 백업 미러 CronJob
      ollama/                  # 로컬 서브차트 — 외부 Ollama 호스트로 향하는 Service+EndpointSlice
```

### Makefile 타깃

| 타깃 | 용도 |
|------|------|
| `install` | 최초 설치 — `helm upgrade --install rag oci://.../rag-platform ... -f values.yaml`을 감싼 편의 타깃(§4는 이 명령을 직접 보여준다) |
| `upgrade` | 업그레이드 — 동일 방식, 이미 존재하는 release에 적용 |
| `uninstall` | 제거 — `helm uninstall rag -n rag` |
| `check-cnpg` | `install`/`upgrade`의 선행 타깃 — `cnpg-system` 네임스페이스 존재 여부를 먼저 확인하고, 없으면 안내 메시지와 함께 즉시 실패 |

이미 운영 중인 Postgres/Redis/MinIO/SMTP가 있으면 해당 서브차트를 `<alias>.enabled: false`로
꺼서 배포를 생략하고, `values.yaml`의 `settings:` 블록(§3.2)에 접속 정보만 채워 넣으면 된다
— 이후 절차는 두 경우 모두 동일하다.

### 의존성 (서브차트)

| alias | 출처 | 역할 |
|-------|------|------|
| `cnpg-cluster` | 로컬 (`charts/cnpg-cluster`) | Postgres `Cluster` CR, 백업/복구 CronJob |
| `minio-jobs` | 로컬 (`charts/minio-jobs`) | 버킷 부트스트랩 Job, 백업 미러 CronJob |
| `ollama` | 로컬 (`charts/ollama`) | 외부 Ollama 호스트로 향하는 Service/EndpointSlice |
| `cnpg-operator` (차트명 `cloudnative-pg`) | upstream | CNPG 오퍼레이터 — **이 차트의 의존성이 아님**, 별도 설치 (§2 참조) |
| `redis-ha` | upstream | ingest/delete 이벤트 큐 |
| `minio` | upstream | S3 호환 문서 스토리지 |
| `mailpit` | upstream | SMTP 평가/테스트용 — 운영은 고객 SMTP로 교체 (Enterprise 구성 시) |
| `qdrant` | upstream | 벡터 DB |
| `dagster` | upstream | webserver / daemon / user-code |
| `reloader` | upstream | ConfigMap/Secret 변경 시 Deployment 자동 재기동 |

설치에 쓰는 OCI 참조는 이미 서브차트가 전부 번들된 상태로 게시되어 있으므로,
`helm dependency update` 같은 별도 빌드 단계가 필요 없다.

외부 준비(차트에 포함되지 않음):

| 항목 | 비고 |
|------|------|
| 임베딩 서버 | 클러스터 외부 Ollama GPU 노드(`ollama` 서브차트로 연결, §2의 6번 참조) 또는 OpenAI API(자체 호스팅 불필요 — 외부 전송 보안 정책 확인) |
| Keycloak | Enterprise 구성 시 (SSO 설정 가이드 참조) |
| 운영용 SMTP | Enterprise 구성 시 (mailpit은 평가/테스트 전용) |

### 네임스페이스 전략

기본 구성은 **전체를 하나의 네임스페이스**(예: `rag`)에 설치한다 — Helm release 하나,
`--namespace rag` 하나. 소~중간 규모 운영이면 이 기본 구성이 관리 부담이 가장 적다.

**대규모 환경 권고**: 클러스터를 여러 제품·팀이 공유하거나, 인프라 성격 컴포넌트(Postgres,
Redis, MinIO, SMTP처럼 이 차트가 직접 띄울 수도, 기존 걸 재사용할 수도 있는 영역)를
애플리케이션 컴포넌트(Qdrant, Dagster, rag-api/rag-admin — 제품 자체)와 다른 정책·팀으로
운영해야 한다면, **인프라 성격 컴포넌트를 별도 네임스페이스로 분리하는 것을 권장한다.**

- NetworkPolicy/ResourceQuota/RBAC을 인프라와 애플리케이션에 서로 다른 기준으로 적용하기
  쉬워진다.
- 인프라 컴포넌트는 여러 제품이 공유하는 경우가 흔한데, 제품 릴리스 주기와 분리해두면
  배포가 서로 영향을 덜 준다.
- 장애 격리와 리소스 쿼터 관리 단위가 명확해진다.

이 차트는 단일 네임스페이스 설치를 기준으로 만들어져 있어(서브차트 리소스가 대부분
`.Release.Namespace`를 참조), 네임스페이스를 분리하려면 **Helm release를 두 개로
나눈다**(각 release마다 release 이름/네임스페이스를 직접 다르게 지정한다):

1. **인프라 release** — `cnpg-cluster`/`redis-ha`/`minio`/`mailpit`/`reloader`만
   `enabled: true`로 두고 나머지는 `false`로 꺼서 `infra` 같은 별도 네임스페이스에 설치.
2. **애플리케이션 release** — `qdrant`/`dagster`/`ollama`(및 이 차트 자체 rag-api/rag-admin
   템플릿)만 켜서 `llm`(또는 `rag`) 네임스페이스에 설치. 이때 `values.yaml`의 `settings:`
   블록에서 Postgres/Redis/S3 호스트를 `{{ .Release.Namespace }}` 기반 기본값 대신
   `<svc>.infra.svc.cluster.local` 형태로 직접 지정해야 한다(§3.2 참고).

두 release 방식은 이 문서가 기본으로 다루는 단일 네임스페이스 구성보다 운영 복잡도가
높으므로, 실제로 규모나 조직 정책상 필요할 때만 적용한다. 이하 §2~§7은 단일 네임스페이스
구성을 기준으로 설명한다.

## 2. 사전 준비

1. **이미지 접근**: 컨테이너 레지스트리에서 제품 이미지(rag-api, rag-admin) pull 가능
   여부 확인. 배포 시 `image.tag`를 **버전 태그로 고정**한다(`latest` 사용 금지 — 롤백
   불가). Core `rag-api` 이미지는 공개 레지스트리라 별도 인증이 필요 없다 — private
   레지스트리(Enterprise `rag-ent-api`)를 쓰는 경우는 문서 끝의
   [참고: private 레지스트리 이미지 사용 시](#참고-private-레지스트리-이미지-사용-시)를
   본다.

2. **네임스페이스**: §4의 `helm upgrade --install ... --create-namespace`가 자동 생성
   하므로 별도 생성이 필요 없다(대규모 구성으로 분리한다면 §1의 네임스페이스 전략을 먼저
   확인한다).

3. **cnpg-operator 설치 (필수, 별도 release)**: 이 차트의 의존성이 아니다. 클러스터당
   한 번, 이 차트를 설치하기 전에 먼저 설치한다.

   ```bash
   helm repo add cnpg https://cloudnative-pg.github.io/charts
   helm install cnpg-operator cnpg/cloudnative-pg -n cnpg-system --create-namespace
   ```

   이 단계를 건너뛰고 바로 설치하면 `Cluster` CR 생성이 webhook 없이 실패해 한참 뒤에야
   문제가 드러난다 — §4에서 설치 전에 `kubectl get namespace cnpg-system`으로 먼저
   확인한다. (`k8s/Makefile`의 `install`/`upgrade` 타깃을 쓰면 `check-cnpg`가 이 확인을
   자동으로 해준다.)

4. **데이터 계층**: 두 가지 방법 중 하나를 선택한다.

   - **차트로 직접 설치**: `cnpg-cluster`/`minio`/`redis-ha`를 `enabled: true`로 두면
     §4의 `helm upgrade --install` 한 번으로 함께 뜬다. `cnpg-cluster`가 `managed.roles`로
     rag-api/dagster용 DB 계정을 자동 생성하므로 별도 SQL이 필요 없다(langfuse DB/계정도
     함께 생성되지만 관측 연동은 이 문서 범위 밖이라 기본 비활성 상태로 둔다 —
     `tracing.enabled: false`. 실제 연결은 해당 사이트에서 직접 구성한다,
     [observability.md](observability.md) 참조). `values.yaml`의 `secrets:` 맵(현재는
     placeholder 값)만 실제 값으로 교체하면 된다.
   - **기존 인프라 재사용**: 해당 서브차트를 `enabled: false`로 끄고, 아래처럼 직접
     계정/DB와 버킷을 준비한다.

   ```sql
   CREATE USER "rag-api" WITH PASSWORD '<password>';
   CREATE DATABASE "rag-api" OWNER "rag-api";
   CREATE USER dagster WITH PASSWORD '<password>';
   CREATE DATABASE dagster OWNER dagster;
   ```

   ```bash
   mc alias set local http://<minio 주소>:9000 <access-key> <secret-key>
   mc mb --ignore-existing local/rag-api
   mc mb --ignore-existing local/dagster
   ```

   이후 `values.yaml`의 `settings:` 블록(§3.2)에 실제 호스트/포트를 채워 넣는다.

5. **ingress + TLS**: nginx ingress controller와 도메인 인증서. rag-admin(관리 콘솔)
   Ingress는 이 차트 자체 values(`admin.ingress`)에, dagster(webserver UI) Ingress도
   dagster 서브차트 values(`dagster.ingress`)에 이미 켜져 있다 — host/tlsSecretName 값만
   실제 도메인으로 바꾸면 된다(예시는 §5). rag-api 자체는 기본적으로 Ingress 템플릿이
   없으므로, API를 외부로 노출하려면 직접 추가한다(§5 하단 참조).

6. **임베딩 서버(Ollama) 연결** — OpenAI를 쓰지 않고 클러스터 외부 Ollama GPU 노드를
   쓰는 경우에만 해당. `ollama.externalIP`(`values.yaml`, 현재 placeholder IP)를 실제
   Ollama 호스트 IP로 바꿔둔다(배포는 §4에서 진행). Ollama가 클러스터 안에 직접 떠
   있다면(자체 Deployment) `ollama` 서브차트는 꺼두고 해당 Service를 그대로 쓴다.

## 3. values 작성

### 3.1 시작

```bash
cd k8s
cp values.yaml.example values.yaml   # gitignored — 실값으로 채운다
```

설치만 하는 경우 이게 전부다 — §4에서 설치할 OCI 차트는 이미 서브차트까지 번들된 상태로
게시되어 있으므로, `helm dependency update` 같은 별도 빌드 단계가 필요 없다.

### 3.2 `settings.yaml` (rag-api 설정 — `helm/values.yaml`의 `settings:` 블록)

`helm/values.yaml`의 `settings:` 블록이 rag-api의 `settings.yaml`로 그대로 렌더링된다
(Helm `tpl`로 렌더링되므로 `{{ .Release.Namespace }}` 같은 템플릿 표현식을 그 안에 그대로
쓸 수 있다). 아래는 서브차트를 기본값대로(같은 네임스페이스에) 배포했을 때의 기본 서비스
주소이며, 네임스페이스를 분리했다면(§1) 해당 값을 실제 인프라 네임스페이스 호스트로 직접
바꾼다.

```yaml
postgres:  { host: "cnpg-postgres-rw.{{ .Release.Namespace }}.svc.cluster.local", dbname: rag-api, user: rag-api, ... }
redis:     { host: "redis-ha-haproxy.{{ .Release.Namespace }}.svc.cluster.local", ... }
qdrant:    { host: "qdrant.{{ .Release.Namespace }}.svc.cluster.local", port: 6333 }
s3:        { endpoint: "http://minio.{{ .Release.Namespace }}.svc.cluster.local:9000", rag_bucket: rag-api, ... }
dagster:   { endpoint: "http://{{ .Release.Name }}-webserver.{{ .Release.Namespace }}.svc.cluster.local:3000" }
           # dagster webserver Service는 fullnameOverride를 따르지 않고 release 이름을 그대로 쓴다
           # — 그래서 이 값만 .Release.Name을 남겨 릴리스 이름에 따라 동적으로 풀리게 한다
provider:  { name: ollama, ollama_url: "http://ollama.{{ .Release.Namespace }}.svc.cluster.local:11434" }
           # ollama_url은 §2의 6번 항목에서 구성한 ollama 서브차트 Service 주소
           # 또는 { name: openai, openai_api_key: <Secret 주입> }
embedding: { model: bge-m3, vector_size: 1024 }
           # 주의: vector_size가 모델과 일치해야 함 (bge-m3=1024, text-embedding-3-small=1536).
           #       provider·모델 변경 시 기존 KB는 전체 재인덱싱 필요
queue_worker: { enabled: false }   # 운영은 Dagster 모드 (알려진 제약 문서 참조)
oidc / authz / smtp / rate_limit:  # Enterprise 구성 시 — SSO 설정 가이드 참조
```

전체 키는 `helm/values.yaml`의 `settings:` 블록과 `settings.example.yaml`(Docker
Compose용, 키 구조는 동일)을 참조하고, 항목별 상세 설명·운영 고려사항은
[Configuration](../reference/configuration.md)을 참조한다.

### 3.3 시크릿 처리 (중요)

DB·S3·Redis 비밀번호, 외부 API 키는 `settings:` 블록(ConfigMap으로 렌더링됨)에 쓰지 않는다.
`values.yaml`의 `secrets:` 맵(그리고 `cnpg-cluster.secrets:`)으로만 채운다 — 이 값들이
`templates/secrets.yaml`(및 `charts/cnpg-cluster/templates/secrets.yaml`)을 통해 k8s
Secret으로 생성되고, rag-api 컨테이너에는 환경변수 오버라이드(`SECTION__FIELD` 형식)로
주입된다. 커넥터 접속 토큰은 제품이 자체 암호화(Fernet)하므로 `CONNECTOR_SECRET_KEY`
환경변수만 Secret으로 주입하면 된다(값 자체는 API로 설정).

필요한 Secret은 총 8개 — `rag-api-credentials`, `redis-auth`, `minio-root-secret`,
`mailpit-smtp-auth`, `dagster-postgresql-secret`, `cnpg-rag-api-role`/`cnpg-dagster-role`/
`cnpg-langfuse-role` — 채우는 방법은 이름별로 자유롭게 선택하되, 같은 이름에 두 방법을
섞지 않는다.

- **차트가 관리 (기본)**: `values.yaml.example`을 `values.yaml`(gitignored)로 복사해
  실값을 채운다(§3.1) — §4의 `helm upgrade --install` 명령에서 `-f values.yaml`로 이
  파일을 레이어링한다. `secrets:` 맵에 있는 키마다 Secret이 생성/갱신된다.
- **기존/사전 생성 Secret 사용**: 해당 키를 맵에서 빼거나(또는 `values.yaml`을 채우지
  않고) 아래처럼 직접 한 번 생성한다 — Helm은 이 방식으로 만든 Secret을 건드리거나
  소유권을 가져가지 않는다.

  ```bash
  kubectl create secret generic rag-api-credentials -n rag \
    --from-literal=S3_ACCESS_KEY=... --from-literal=S3_SECRET_KEY=... \
    --from-literal=REDIS_PASSWORD=... \
    --from-literal=POSTGRES_USER=... --from-literal=POSTGRES_PASSWORD=... \
    --from-literal=OPENAI_API_KEY=... --from-literal=RERANKER_API_KEY=...
  # redis-auth / minio-root-secret / dagster-postgresql-secret / cnpg-*-role 등도 동일하게 직접 생성
  ```

`rag-api-credentials`의 `S3_ACCESS_KEY`/`S3_SECRET_KEY`는 `minio-root-secret`의
`rootUser`/`rootPassword`와 반드시 같은 값이어야 한다 — 다르면 MinIO 자체는 떠도 업로드가
`InvalidAccessKeyId`로 실패한다.

저장소에는 로컬 평가용 placeholder 값만 담긴 `values.yaml.example`이 커밋되어 있다. Git으로
실값 `values.yaml`을 관리해야 하는 경우 커밋 대상에서 제외하거나(배포 파이프라인에서 별도
주입), 조직에서 이미 쓰는 시크릿 관리 도구([SOPS](https://github.com/getsops/sops), Sealed
Secrets, External Secrets 등)로 교체해 사용한다 — 차트 자체는 특정 도구에 종속되어 있지
않다.

Docker Compose 배포([Quick Start](../getting-started/quickstart.md))는 `docker/.env`로
동일하게 해결한다 — `docker-compose.yml`의 모든 서비스가 `env_file: .env`로 주입받고
`settings.yaml`에는 자격증명 키가 없다. 저장소에는 로컬 평가용 placeholder 값만 커밋되어
있으므로, 운영 배포 시 `.env`를 실값으로 교체한다.

## 4. 배포

§2에서 cnpg-operator를 먼저 설치했는지 확인한다:

```bash
kubectl get namespace cnpg-system   # 없으면 §2의 3번 항목부터 진행
```

그 외 컴포넌트 간 순서는 Helm이 알아서 처리하므로(Chart.yaml 선언 순서 + 각 리소스의 Helm
훅) OCI 참조를 바로 설치하는 명령 한 번이면 된다 — 별도로 `.tgz`를 내려받아 둘 필요 없이
`helm upgrade --install`이 레지스트리에서 직접 pull한다. 게시된 버전 목록은
[GHCR 패키지 페이지](https://github.com/orgs/cnapcloud/packages/container/package/charts%2Frag-platform)에서
확인하거나 배포 시 안내받은 버전을 사용한다.

```bash
cd k8s
helm upgrade --install rag oci://ghcr.io/cnapcloud/charts/rag-platform \
  --version 0.1.0 \
  -n rag --create-namespace \
  -f values.yaml
```

패키지가 public이므로(§1) 별도 인증이 필요 없다. 이 차트는 이미 `helm/values.yaml`에
해당하는 기본값을 포함하고 있으므로, 직접 채운 `values.yaml`(§3.3의 실제 시크릿)만 `-f`로
얹으면 된다 — `helm/values.yaml`을 따로 갖고 있거나 `-f`로 다시 넘길 필요는 없다.

업그레이드도 동일한 형태다 — `--version`만 새 값으로 바꿔 같은 명령을 다시 실행한다:

```bash
helm upgrade --install rag oci://ghcr.io/cnapcloud/charts/rag-platform \
  --version 0.2.0 \
  -n rag -f values.yaml
```

`--atomic`을 붙이지 않으면 설치 도중 실패해도 자동으로 롤백되지 않고 release가
`pending-install`/`failed` 상태로 남을 수 있다. 흔한 원인은 `values.yaml`(§3.3의 실제
시크릿)을 채우지 않은 채로 실행한 경우다 — Secret이 비어 있으면 여러 파드가
`CreateContainerConfigError`로 멈추고, MinIO 버킷 부트스트랩 post-install 훅이 그 상태로
무한 대기하면서 `helm upgrade --install` 자체도 멈춘다. 이 경우 값을 바로잡은 뒤
`helm uninstall rag -n rag`로 정리하고 다시 설치한다. 이 실패 모드를 자동 롤백으로 바꾸려면
`--atomic`을 직접 추가한다.

제거:

```bash
helm uninstall rag -n rag
```

`k8s/Makefile`에는 위 흐름을 그대로 감싼 `install`/`upgrade`/`uninstall` 타깃(및 실행 전
`cnpg-system` 존재를 자동 확인하는 `check-cnpg`)이 있다 — 버전 번호를 직접 다루지 않고
싶다면 `make install`/`make upgrade`/`make uninstall`을 대신 쓴다(§1 Makefile 타깃 표
참고).

### 트러블슈팅 — `<resource> already exists`

release가 "존재하지 않는데" 설치/업그레이드 시 이 에러가 나면, 이전 시도가 중간에 실패하며
release 기록 없이 리소스만 남긴 경우다. 충돌하는 오브젝트를 지우고 재시도한다:

```bash
kubectl delete role dagster-role -n rag
kubectl delete rolebinding dagster-rolebinding -n rag
```

## 5. Ingress 예시

`rag-admin` Ingress는 이 차트 자체 values(`admin.ingress`, `helm/values.yaml`)에 이미
켜져 있다 — 실제 값은 다음과 같은 형태이며 host/tlsSecretName만 실제 도메인으로 바꾸면
된다.

```yaml
admin:
  ingress:
    enabled: true
    ingressClassName: nginx
    host: rag-admin.<도메인>
    tlsSecretName: <tls-secret>
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"     # 문서 업로드 크기
      nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
```

dagster webserver UI의 Ingress도 dagster 서브차트 values(`dagster.ingress`)에 이미 켜져
있다 — `dagster.ingress.dagsterWebserver.host`와 `tls.secretName` 값만 실제 도메인으로
바꾸면 된다. rag-api 자체는 이 차트에 Ingress 템플릿이 없으므로, API를 외부로 노출하는
경우 별도 `Ingress` 리소스를 직접 추가한다(위와 동일한 방식, annotations 포함).

데이터 계층(Postgres/Redis/Qdrant/S3)과 Dagster webserver는 원칙적으로 외부에 노출하지
않는다 — 사용자 접점은 관리 콘솔과 RAG API 두 개뿐이다. Qdrant/MinIO 서브차트에도 자체
`ingress`/`consoleIngress` 값이 있어 필요하면 켤 수 있지만(예: 운영자가 Qdrant dashboard나
`mc` CLI로 직접 접근해야 하는 경우), 기본적으로는 꺼두고 필요할 때만 운영자 인증이 걸린
별도 경로로 제한적으로 연다.

## 6. 배포 확인

- `helm status rag -n rag`, `kubectl -n rag get pods` — 전체 Running, readiness 통과.
- rag-api의 liveness(`/health`)·readiness(`/ready`) 프로브는 차트에 포함되어 있다.
  readiness 실패 시 `/ready` 응답의 `checks`에서 실패 인프라를 식별한다.
- §5에서 설정한 도메인으로 rag-admin(`https://rag-admin.<도메인>`), dagster
  (`https://dagster.<도메인>`) 접속 확인 — 로그인 화면/UI가 정상 로드되어야 한다.
- Dagster UI에서 code location 로드와 `event_queue_sensor` 활성 상태 확인.
- 이후 [첫 KB와 검색](../getting-started/first-kb-and-query.md)의 스모크 테스트를 수행한다.
  rag-api는 기본적으로 Ingress가 없으므로(§2의 5번 항목), 별도로 노출하지 않았다면
  아래처럼 포트포워딩한 뒤 `<api>`를 `http://localhost:8000`으로 대체해 진행한다.

  ```bash
  kubectl -n rag port-forward svc/rag-api 8000:8000
  ```

## 7. 운영 팁

- 설정 ConfigMap/Secret 변경 시 자동 재기동: rag-api/dagster 리소스에 reloader
  어노테이션이 포함되어 있어 `reloader` 서브차트(기본 `enabled: true`,
  [stakater/reloader](https://github.com/stakater/Reloader)) 배포 시 활성화된다.
- 커넥터의 `sync_schedule`(cron) 변경은 Dagster 재시작이 필요하다 —
  [알려진 제약](../support/known-limitations.md) 참조.
- 대규모 환경에서 인프라 성격 컴포넌트를 별도 네임스페이스로 분리해 운영하는 경우(§1),
  release가 두 개로 늘어나므로 업그레이드 순서(인프라 release를 먼저 적용)와 `settings:`
  블록의 교차 네임스페이스 호스트 값을 함께 관리한다.
- 업그레이드·롤백, 백업·복구 절차는 [runbook.md](runbook.md) 참조.

## 8. 다음 단계

| 목적 | 문서 |
|------|------|
| SSO·KB 접근제어 활성화 | [SSO 설정](../guides/rag-ent/sso-and-auth-setup.md) |
| LibreChat 등 챗 서비스 연동 (핵심 시나리오) | LibreChat 연동 가이드 (마이그레이션 예정) |
| 관측 구성 (Langfuse·Prometheus·Grafana) | [observability.md](observability.md) |
| 설치 검증 | [첫 KB와 검색](../getting-started/first-kb-and-query.md) |

## 참고: private 레지스트리 이미지 사용 시

Core `rag-api` 이미지는 공개 레지스트리에 있어 별도 인증 없이 pull된다. Enterprise
구성에서 private 레지스트리의 `rag-ent-api` 이미지를 쓰는 경우에만 아래 절차가 필요하다
(§2의 1번 항목 참고).

`imagePullSecrets`용 Secret을 먼저 만든다:

```bash
kubectl create secret docker-registry ghcr-pull-token --docker-server=ghcr.io \
  --docker-username=<user> --docker-password=<token> -n rag
```

그다음 `values.yaml`에 `imagePullSecrets: [{name: ghcr-pull-token}]`을 채운다.
