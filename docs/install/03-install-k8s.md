# Kubernetes 배포

운영 환경 설치 담당자(k8s 운영 경험 전제)를 위한 표준 설치 절차. 배포 매니페스트의 고객
인도용 파라미터화(Helm 차트화)가 진행 중이며, 이 문서는 현재 `k8s/manifests/`의 kustomize
구조를 기준으로 한다 — 패키징 개선 시 갱신된다.

---

## 1. 배포 구성 개요

```
k8s/manifests/
  infra/                          # 네임스페이스: infra (기존 인프라 재사용 시 배포 생략 가능)
    cnpg/operator                 # CloudNativePG 오퍼레이터
    cnpg/cluster                  # PostgreSQL 클러스터 (rag-api/dagster DB 계정 자동 생성,
                                  # langfuse DB도 함께 생성되나 관측 연동은 범위 밖 — 기본 비활성)
    minio                         # S3 호환 스토리지
    redis-ha                      # ingest/delete 이벤트 큐 (Sentinel/HAProxy)
    mailpit                       # SMTP 평가/테스트용 — 운영은 고객 SMTP로 교체 (Enterprise 구성 시)
    reloader                      # ConfigMap/Secret 변경 시 Deployment 자동 재기동

  llm/                            # 네임스페이스: llm
    qdrant                       # 벡터 DB (Helm 기반)
    dagster                      # webserver / daemon / user-code (Helm 기반)
    rag-api                      # rag-api Deployment+Service, rag-admin Deployment+Service+Ingress 포함
                                  # Enterprise 구성 시 overlays/dev/kustomization.yaml의
                                  # images 트랜스포머(newName/newTag)로 rag-ent-api 이미지로 교체
    ollama                       # 클러스터 외부 Ollama GPU 노드를 위한 Service+EndpointSlice
                                  # (선택 — 임베딩 서버가 클러스터 밖에 있을 때만 배포)

외부 준비 (매니페스트에 포함되지 않음):
  임베딩 서버    Ollama GPU 노드 (클러스터 외부면 llm/ollama로 연결 — §2의 5번 항목 참조)
                또는 OpenAI API 사용 (자체 호스팅 불필요 — 외부 전송 보안 정책 확인)
  Keycloak      Enterprise 구성 시 (04-enterprise-setup.md)
  운영용 SMTP    Enterprise 구성 시 (mailpit은 평가/테스트 전용)
```

각 컴포넌트는 `kustomize/base`(공통 리소스) + `kustomize/overlays/<환경>`(환경별 설정)
구조와 자체 `Makefile`(`preview` / `diff` / `apply` / `delete` / `namespace` 타겟)을 가진다.
`infra/`는 PostgreSQL·Redis·S3·SMTP를 이미 운영 중이면 배포하지 않고, §3.1에서 해당 접속
정보만 채워 넣어도 된다 — 이후 절차는 두 경우 모두 동일하다.

각 overlay의 `kustomization.yaml`은 네임스페이스(`infra` 또는 `llm`)를 고정값으로 갖는다.
다른 이름을 쓰려면 overlay마다 `namespace:` 값과 §3.1의 서비스 주소를 함께 수정한다.

## 2. 사전 준비

1. **이미지 접근**: 컨테이너 레지스트리에서 제품 이미지(rag-ent-api, rag-admin, dagster)
   pull 가능 여부 확인. 배포 시 **버전 태그를 고정**한다 (`:latest` 사용 금지 — 롤백 불가).
2. **네임스페이스**: 컴포넌트별 `make namespace` 타겟이 있거나, 직접 생성한다.

   ```bash
   kubectl create namespace infra   # infra/ 배포 시
   kubectl create namespace llm     # rag/ 배포 시 (제품 네임스페이스)
   ```

3. **데이터 계층**: 두 가지 방법 중 하나를 선택한다.

   - **매니페스트로 직접 설치**: `infra/minio`를 가장 먼저 `make apply`한다 — cnpg
     cluster의 백업 대상이 이 MinIO이므로 먼저 떠 있어야 한다. 이후 `infra/cnpg/operator`
     → `infra/cnpg/cluster` → `infra/redis-ha` 순으로 배포한다. Cluster 매니페스트가
     `managed.roles`로 rag-api/dagster용 DB 계정을 자동 생성하므로 별도 SQL이 필요 없다
     (langfuse DB/계정도 함께 생성되지만 관측 연동은 이 문서 범위 밖이라 기본 비활성
     상태로 둔다 — `tracing.enabled: false`. 실제 연결은 해당 사이트에서 직접 구성한다,
     [02-observability.md](../operations/02-observability.md) 참조). 각 overlay의
     `secrets/*.env`(현재는 placeholder 값)만 실제 값으로 교체하면 된다.
   - **기존 인프라 재사용**: 아래처럼 직접 계정/DB와 버킷을 준비한다.

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

4. **ingress + TLS**: nginx ingress controller와 도메인 인증서. rag-admin(관리 콘솔)
   Ingress는 rag-api kustomize base에 이미 포함되어 있고, dagster(webserver UI)도 Helm
   values의 `ingress.enabled: true`로 이미 켜져 있다 — 둘 다 host 값만 실제 도메인으로
   바꾸면 된다(예시는 5절 참조). rag-api 자체는 기본적으로 Ingress가 없으므로, API를
   외부로 노출하려면 직접 추가한다(§5 하단 참조).
5. **임베딩 서버(Ollama) 연결** — OpenAI를 쓰지 않고 클러스터 외부 Ollama GPU 노드를
   쓰는 경우에만 해당. `llm/ollama`가 클러스터 안에서 `ollama.llm.svc.cluster.local:11434`로
   접근할 수 있도록 Service+EndpointSlice를 새로 구성해준다 — 배포 전에
   `llm/ollama/kustomize/base/resources/endpoints.yaml`의 `addresses`(현재는 placeholder
   IP)를 실제 Ollama 호스트 IP로 바꿔둔다(배포는 §4에서 진행). Ollama가 클러스터 안에
   직접 떠 있다면(자체 Deployment) 이 컴포넌트는 배포하지 않고 해당 Service를 그대로 쓴다.

## 3. 환경 overlay 작성

overlay 디렉터리를 환경에 맞게 복제한 뒤 `settings.yaml`을 수정한다. 관리 콘솔의
admin-ui ConfigMap(OIDC 값 포함)은 Enterprise 전용 설정이므로
[04-enterprise-setup.md §3](04-enterprise-setup.md#3-관리-콘솔-ent-모드-활성화)에서 다룬다 —
Core 모드는 overlay의 기본값을 그대로 둔다.

### 3.1 `settings.yaml` (rag-api ConfigMap)

내부 서비스 주소·자격증명을 환경 값으로 치환한다. 아래는 `infra/`·`rag/` 매니페스트를
그대로 배포했을 때의 기본 서비스 주소이며, 네임스페이스를 바꿨다면 그에 맞게 수정한다.

```yaml
postgres:  { host: cnpg-postgres-rw.infra.svc, dbname: rag-api, user: rag-api, ... }
redis:     { host: redis-ha-haproxy.infra.svc, ... }
qdrant:    { host: qdrant.llm.svc.cluster.local, port: 6333 }
s3:        { endpoint: http://minio.infra.svc:9000, rag_bucket: rag-api, ... }
dagster:   { endpoint: http://dagster-webserver.llm.svc.cluster.local:3000 }
embedding: { provider: ollama, model: bge-m3, ollama_url: http://ollama.llm.svc.cluster.local:11434 }
           # ollama_url은 §2의 5번 항목에서 구성한 llm/ollama Service 주소 (클러스터 내부 Ollama라면 해당 Service 주소로)
           # 또는 { provider: openai, openai_model: text-embedding-3-small, openai_api_key: <Secret 주입> }
           # 주의: vector_size가 모델과 일치해야 함 (bge-m3=1024, text-embedding-3-small=1536).
           #       provider·모델 변경 시 기존 KB는 전체 재인덱싱 필요
queue_worker: { enabled: false }   # 운영은 Dagster 모드 (알려진 제약 문서 참조)
oidc / authz / smtp / rate_limit:  # Enterprise 구성 시 — 04-enterprise-setup.md
```

전체 키는 `settings.example.yaml`을 참조하고, 항목별 상세 설명·운영 고려사항은
[reference/02-settings-guide.md](../reference/02-settings-guide.md)를 참조한다.

### 3.2 시크릿 처리 (중요)

DB·S3·Redis 비밀번호, 외부 API 키는 `settings.yaml` ConfigMap에 쓰지 않는다. 키 자체를
빼고 환경변수 오버라이드(`SECTION__FIELD` 형식)로 **k8s Secret에서만 주입**한다.
커넥터 접속 토큰은 제품이 자체 암호화(Fernet)하므로 `security.fernet_key`만 Secret으로
주입하면 된다.

각 overlay의 `secrets/*.env`는 kustomize 기본 `secretGenerator`로 Secret을 생성하며,
저장소에는 로컬 평가용 placeholder 값만 커밋되어 있다. 운영 배포 전 이 파일들의 값을
실제 값으로 교체한다. Git으로 overlay를 관리하는 경우 실값이 담긴 `secrets/*.env`는
커밋 대상에서 제외하거나(배포 파이프라인에서 별도 주입), 조직에서 이미 쓰는 시크릿
관리 도구([SOPS](https://github.com/getsops/sops), Sealed Secrets, External Secrets 등)로
교체해 사용한다 — 매니페스트 자체는 특정 도구에 종속되어 있지 않다.

Docker Compose 배포([02-quickstart.md](02-quickstart.md))는 `docker/.env`로 동일하게
해결한다 — `docker-compose.yml`의 모든 서비스가 `env_file: .env`로 주입받고
`settings.yaml`에는 자격증명 키가 없다. 저장소에는 로컬 평가용 placeholder 값만
커밋되어 있으므로, 운영 배포 시 `.env`를 실값으로 교체한다(git 추적 대상에서 제외하거나
배포 파이프라인의 시크릿 주입으로 대체).

## 4. 배포

```bash
# 각 컴포넌트 디렉터리에서 (기존 인프라 재사용 시 infra/ 단계는 생략)
# 1) infra:  minio(cnpg 백업 대상이라 먼저) → cnpg/operator → cnpg/cluster → redis-ha
#            (mailpit, reloader는 선택)
# 2) llm:    qdrant → ollama(클러스터 외부 임베딩 서버 쓸 때만, §2 5번 항목 참조) → dagster → rag-api
#            (rag-admin은 rag-api에 포함)
#            임베딩 서버가 먼저 준비돼 있어야 한다 — /ready가 임베딩 연결까지 확인한다
make preview     # 생성될 매니페스트 확인
make diff        # 기존 클러스터와 차이 확인
make apply       # server-side apply
```

## 5. Ingress 예시

`rag-admin` Ingress는 `llm/rag-api/kustomize/base/resources/admin/ingress.yaml`에 이미
정의되어 있다 — 실제 내용은 다음과 같다.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-admin
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"     # 문서 업로드 크기
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
spec:
  ingressClassName: nginx
  rules:
    - host: rag-admin.<도메인>
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: rag-admin, port: { number: 80 } } }
  tls:
    - secretName: <tls-secret>
      hosts: [rag-admin.<도메인>]
```

dagster webserver UI의 Ingress도 Helm values(`llm/dagster/kustomize/overlays/dev/helm/
values-dev.yaml`의 `ingress` 섹션)에 이미 켜져 있다 — `ingress.dagsterWebserver.host` 값만
실제 도메인으로 바꾸면 된다. rag-api 자체는 기본 Ingress가 없으므로, API를 외부로
노출하는 경우 위와 동일한 방식(annotations 포함)으로 직접 추가한다.

## 6. 배포 확인

- 각 컴포넌트에서 `make apply` 전에 `make preview`로 렌더링 결과를 먼저 확인한다(Helm
  기반 컴포넌트는 Makefile이 `--enable-alpha-plugins`를 이미 포함한다).
- `kubectl -n <ns> get pods` — 전체 Running, readiness 통과
- rag-api의 liveness(`/health`)·readiness(`/ready`) 프로브는 매니페스트에 포함되어 있다.
  readiness 실패 시 `/ready` 응답의 `checks`에서 실패 인프라를 식별한다.
- §5에서 설정한 도메인으로 rag-admin(`https://rag-admin.<도메인>`), dagster
  (`https://dagster.<도메인>`) 접속 확인 — 로그인 화면/UI가 정상 로드되어야 한다.
- Dagster UI에서 code location 로드와 `event_queue_sensor` 활성 상태 확인.
- 이후 [05-verification.md](05-verification.md)의 스모크 테스트를 수행한다. rag-api는
  기본적으로 Ingress가 없으므로(§2의 4번 항목), 별도로 노출하지 않았다면 아래처럼 포트포워딩한
  뒤 `<api>`를 `http://localhost:8000`으로 대체해 진행한다.

  ```bash
  kubectl -n llm port-forward svc/rag-api 8000:8000
  ```

## 7. 운영 팁

- 설정 ConfigMap/Secret 변경 시 자동 재기동: Deployment에 reloader 어노테이션이 포함되어
  있어 `infra/reloader`([stakater/reloader](https://github.com/stakater/Reloader)) 배포
  시 활성화된다 (선택).
- 커넥터의 `sync_schedule`(cron) 변경은 Dagster 재시작이 필요하다 —
  [알려진 제약](../support/03-known-limitations.md) 참조.
- 업그레이드·롤백, 백업·복구 절차는 [01-runbook-k8s.md](../operations/01-runbook-k8s.md) 참조.

## 8. 다음 단계

| 목적 | 문서 |
|------|------|
| SSO·KB 접근제어 활성화 | [04-enterprise-setup.md](04-enterprise-setup.md) |
| LibreChat 등 챗 서비스 연동 (핵심 시나리오) | [06-integrations.md](06-integrations.md) |
| 관측 구성 (Langfuse·Prometheus·Grafana) | [02-observability.md](../operations/02-observability.md) |
| 설치 검증 | [05-verification.md](05-verification.md) |
