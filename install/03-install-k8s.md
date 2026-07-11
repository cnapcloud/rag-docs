# 표준 설치 — Kubernetes (kustomize)

운영 환경 설치 담당자(k8s 운영 경험 전제)를 위한 표준 설치 절차. 배포 매니페스트의 고객
인도용 파라미터화(Helm 차트화)가 진행 중이며, 이 문서는 현재 kustomize 방식을 기준으로
한다 — 패키징 개선 시 갱신된다.

---

## 1. 배포 구성 개요

```
namespace: <제품 네임스페이스, 예: rag>
  rag-api        Deployment + Service            # rag-api 이미지 (API + MCP), 
                                                 # Enterprise 구성 시, 
                                                 # rag-ent-api 이미지로 교체 재배포 (overlays/dev/kustomization.yam 수정)
  rag-admin      Deployment + Service + Ingress  # 관리 콘솔
  dagster        Helm 차트 기반                    # webserver / daemon / user-code
  qdrant         StatefulSet + PVC               # 벡터 DB

외부 준비 (기존 인프라 재사용 또는 별도 설치):
  PostgreSQL    HA 권장 (CloudNativePG 검증됨)
  Redis         HA 권장 (Sentinel/HAProxy 검증됨)
  S3 호환 스토리지  MinIO 또는 기존 S3
  임베딩 서버    Ollama GPU 노드 (클러스터 외부면 Service+EndpointSlice로 연결)
                또는 OpenAI API 사용 (자체 호스팅 불필요 — 외부 전송 보안 정책 확인)
  Keycloak      Enterprise 구성 시 (05-ent-setup.md)
  SMTP          Enterprise 구성 시
```

각 컴포넌트는 `kustomize/base`(공통 리소스) + `kustomize/overlays/<환경>`(환경별
설정) 구조를 따르며, Makefile의 `preview / diff / apply` 타겟으로 배포한다.

## 2. 사전 준비

1. **이미지 접근**: 컨테이너 레지스트리에서 제품 이미지(rag-ent-api, rag-admin, dagster)
   pull 가능 여부 확인. 배포 시 **버전 태그를 고정**한다 (`:latest` 사용 금지 — 롤백 불가).
2. **네임스페이스**: `kubectl create namespace <ns>`
3. **데이터 계층**: PostgreSQL(rag-api용 DB/계정 + dagster용 DB/계정), Redis, S3 버킷
   (`rag-api`, `dagster`) 준비.

   ```sql
   CREATE USER "rag-api" WITH PASSWORD '<password>';
   CREATE DATABASE "rag-api" OWNER "rag-api";
   CREATE USER dagster WITH PASSWORD '<password>';
   CREATE DATABASE dagster OWNER dagster;
   ```

4. **ingress + TLS**: nginx ingress controller와 도메인 인증서.

## 3. 환경 overlay 작성

overlay 디렉터리를 환경에 맞게 복제한 뒤 두 파일을 수정한다.

### 3.1 `settings.yaml` (rag-api ConfigMap)

내부 서비스 주소·자격증명을 환경 값으로 치환한다. 주요 키:

```yaml
postgres:  { host: <postgres 주소>, dbname: rag-api, user: rag-api, ... }
redis:     { host: <redis 주소>, ... }
qdrant:    { host: qdrant.<ns>.svc.cluster.local, port: 6333 }
s3:        { endpoint: http://<minio 주소>:9000, rag_bucket: rag-api, ... }
dagster:   { endpoint: http://dagster-webserver.<ns>.svc.cluster.local:3000 }
embedding: { provider: ollama, model: bge-m3, ollama_url: http://<ollama 주소>:11434 }
           # 또는 { provider: openai, openai_model: text-embedding-3-small, openai_api_key: <Secret 주입> }
           # 주의: vector_size가 모델과 일치해야 함 (bge-m3=1024, text-embedding-3-small=1536).
           #       provider·모델 변경 시 기존 KB는 전체 재인덱싱 필요
queue_worker: { enabled: false }   # 운영은 Dagster 모드 (알려진 제약 문서 참조)
oidc / authz / smtp:               # Enterprise 구성 시 — 05-ent-setup.md
```

전체 키는 `settings.example.yaml`을 참조한다.

### 3.2 관리 콘솔 환경 파일 (admin-ui ConfigMap)

```
API_URL=http://rag-api:8000            # 콘솔이 호출할 API 주소
OIDC_ISSUER=                            # Core 모드는 빈 값
OIDC_CLIENT_ID=                         # 값이 있으면 ENT 모드로 동작
```

### 3.3 시크릿 처리 (중요)

DB·S3·Redis 비밀번호, 외부 API 키는 `settings.yaml` ConfigMap에 쓰지 않는다. 키 자체를
빼고 환경변수 오버라이드(`SECTION__FIELD` 형식)로 **k8s Secret에서만 주입**한다.
커넥터 접속 토큰은 제품이 자체 암호화(Fernet)하므로 `security.fernet_key`만 Secret으로
주입하면 된다.

overlay를 git으로 관리하는 경우, Secret 원본을 평문으로 커밋하지 않도록
[SOPS](https://github.com/getsops/sops) + kustomize
[`SopsSecretGenerator`](https://github.com/goabout/kustomize-sopssecretgenerator)로
암호화한다. 저장소 루트의 `.sops.yaml`에 암복호화용 PGP/age 키를 등록해둔다.

```yaml
# .sops.yaml
creation_rules:
  - pgp: "<PGP 키 지문>"
```

```yaml
# secrets/sops-secrets.yaml
apiVersion: goabout.com/v1beta1
kind: SopsSecretGenerator
metadata:
  name: rag-api-credentials
envs:
  - ./secrets/sops/rag-api-credentials.env   # sops -e로 암호화된 dotenv
```

Docker Compose 배포([02-quickstart.md](02-quickstart.md))는 `docker/.env`로 동일하게
해결한다 — `docker-compose.yml`의 모든 서비스가 `env_file: .env`로 주입받고
`settings.yaml`에는 자격증명 키가 없다. 저장소에는 로컬 평가용 placeholder 값만
커밋되어 있으므로, 운영 배포 시 `.env`를 실값으로 교체한다(git 추적 대상에서 제외하거나
배포 파이프라인의 시크릿 주입으로 대체).

## 4. 배포

```bash
# 컴포넌트별 디렉터리에서 (qdrant → dagster → rag-api → rag-admin 순 권장)
make preview     # 생성될 매니페스트 확인
make diff        # 기존 클러스터와 차이 확인
make apply       # server-side apply
```

## 5. Ingress 예시 (관리 콘솔)

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

API를 외부 노출하는 경우 동일한 방식으로 rag-api ingress를 추가한다 (proxy-body-size는
업로드 상한에 맞춰 동일하게 설정).

## 6. 배포 확인

- `kubectl -n <ns> get pods` — 전체 Running, readiness 통과
- rag-api의 liveness(`/health`)·readiness(`/ready`) 프로브는 매니페스트에 포함되어 있다.
  readiness 실패 시 `/ready` 응답의 `checks`에서 실패 인프라를 식별한다.
- Dagster UI에서 code location 로드와 `event_queue_sensor` 활성 상태 확인.
- 이후 [05-verification.md](05-verification.md)의 스모크 테스트를 수행한다.

## 7. 운영 팁

- 설정 ConfigMap 변경 시 자동 재기동: Deployment에 reloader 어노테이션이 포함되어 있어
  [stakater/reloader](https://github.com/stakater/Reloader) 설치 시 활성화된다 (선택).
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
