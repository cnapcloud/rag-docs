# 시스템 요구사항

설치 전 확인해야 할 시스템 요구사항과 사이징 기준을 정리한다. 실측 기반 초기 가이드이며,
규모별 공식 벤치마크는 추후 갱신될 예정이다.

---

## 1. 배포 프로파일

| 프로파일 | 용도 | 형태 | 규모 가정 |
|----------|------|------|-----------|
| 평가(PoC) | 기능 검증, 데모 | 단일 호스트 docker-compose | 문서 수백 건, 동시 사용자 소수 |
| 소규모 | 팀·부서 단위 운영 | k8s (단일 노드 가능) | 문서 ~1만 건, 동시 사용자 ~50 |
| 표준 | 전사 서비스 | k8s + HA 데이터 계층 | 문서 ~10만 건, 동시 사용자 수백 (벤치마크 검증 예정) |

## 2. 하드웨어 요구

### 평가(PoC) — 단일 호스트

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 16 GB |
| 디스크 | 30 GB | 50 GB (SSD) |
| 임베딩 서버 | CPU 추론 가능 (느림) | GPU 8 GB VRAM 이상 (bge-m3 기준) |

### 소규모 / 표준 — 컴포넌트별 기준

| 컴포넌트 | 소규모 | 표준 | 비고 |
|----------|--------|------|------|
| RAG API 서버 | 1 vCPU / 1 GB | 2 vCPU / 2 GB x 2 replica | 운영 실측: requests 100m/256Mi, limits 1c/1Gi |
| 관리 콘솔 | 0.2 vCPU / 256 MB | 동일 | 정적 SPA |
| Dagster (webserver+daemon+code) | 2 vCPU / 4 GB | 4 vCPU / 8 GB | 동시 인제스트 수(`max_concurrent_runs`, 기본 8)에 비례 |
| PostgreSQL | 2 vCPU / 4 GB / 20 GB | HA 구성(예: CloudNativePG) 4 vCPU / 8 GB / 50 GB | 메타데이터 + Dagster 이력 |
| Redis | 1 vCPU / 1 GB | HA 구성 2 vCPU / 2 GB | 큐 전용 — 데이터량 작음 |
| Qdrant | 2 vCPU / 4 GB / 20 GB | 4 vCPU / 16 GB / 100 GB | RAM이 검색 성능 좌우. 아래 §3 산정식 참조 |
| 오브젝트 스토리지(MinIO/S3) | 원본 문서 총량 x 1.2 | 동일 | 기존 S3 호환 스토리지 재사용 가능 |
| 임베딩 서버(Ollama) | GPU 8 GB VRAM | GPU 16 GB VRAM 또는 전용 노드 | OpenAI API 사용 시 불필요 |

## 3. 스토리지 산정 기준

- **Qdrant (벡터)**: 청크 1개 = dense 1024차원(float32 약 4 KB) + sparse + 페이로드 ≈ 6~8 KB.
  문서당 평균 40청크 가정 시 **문서 1만 건 ≈ 3 GB, 10만 건 ≈ 30 GB** (여유 2배 권장).
- **PostgreSQL**: 문서당 메타데이터 수 KB — 문서 10만 건에 수 GB 수준. Dagster run 이력이
  더 큰 비중을 차지하므로 보존 주기 정리를 권장.
- **오브젝트 스토리지**: 원본 문서 총량 그대로 + 스테이징 여유 20%.

## 4. 소프트웨어 요구

| 항목 | 요구 |
|------|------|
| 컨테이너 런타임 | Docker 24+ (평가), Kubernetes 1.27+ (운영) |
| 배포 도구 | docker compose v2 (평가) / kubectl + kustomize (운영) |
| Python (소스 실행 시) | 3.12 — 3.13 이상 미지원 ([알려진 제약](../support/03-known-limitations.md)) |
| Ingress | nginx ingress controller + TLS 인증서 (운영) |
| IdP (Enterprise) | OIDC 호환 (Keycloak 검증됨) |
| SMTP (Enterprise) | 초대 메일 발송용 실 SMTP 서버 |

## 5. 네트워크 포트

| 포트 | 컴포넌트 | 노출 범위 |
|------|----------|-----------|
| 8000 | RAG API (+MCP `/mcp`) | 사용자/연동 앱 — ingress 경유 |
| 80 (8080) | 관리 콘솔 | 사용자 — ingress 경유 |
| 3000 | Dagster UI | **운영자 전용** — 외부 비노출 권장 |
| 5432 / 6379 / 6333 / 9000 | Postgres / Redis / Qdrant / S3 | 내부 전용 |
| 11434 | Ollama | 내부 전용 (API 서버·Dagster에서 접근) |

**주의**: 데이터 계층(Postgres/Redis/Qdrant/S3)과 Dagster UI는 외부에 노출하지 않는다 —
사용자 접점은 관리 콘솔과 RAG API 두 개뿐이다.

## 6. 외부 연결 요구 (선택 기능)

| 기능 | 외부 연결 | 미연결 시 |
|------|-----------|-----------|
| 리랭킹 | Jina API (HTTPS) | `enabled: false` 또는 자동 폴백 — 검색은 정상 동작 |
| OpenAI 임베딩 | OpenAI API | Ollama 로컬 임베딩 사용 (기본) |
| 커넥터 | 대상 시스템(Confluence/GitHub/웹) | 직접 업로드만 사용 |

임베딩을 Ollama로 구성하고 리랭킹을 끄면 **완전 폐쇄망 운영이 가능**하다.
