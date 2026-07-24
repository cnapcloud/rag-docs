---
sidebar_position: 1
---

# Quick Start

가장 빠른 설치 경로 — 약 30분(이미지 빌드 시간 제외) 안에 Core 모드(인증 없음) 단일 호스트
docker-compose로 배포해 제품을 평가할 수 있다.

이 문서는 **설치와 기동**까지만 다룬다. 설치가 끝난 뒤 KB를 만들고 문서를 올려 실제로
검색해보는 흐름은 [첫 KB와 검색](first-kb-and-query.md)에서 이어서 진행한다. 인증(SSO)·접근
제어는 [sso-and-auth-setup.md](../guides/rag-ent/sso-and-auth-setup.md),
Kubernetes 설치는 [kubernetes.md](../deploy/kubernetes.md)를 참고한다[ENT].

---

## 1. 사전 요구사항

| 항목 | 요구 |
|------|------|
| OS | Linux 또는 macOS (Docker Desktop) |
| 소프트웨어 | Docker 24+, Docker Compose v2, git |
| 리소스 | 4 vCPU / 16 GB RAM / 50 GB 디스크 권장 |
| 임베딩 서버 | Ollama (아래 §2에서 준비 — GPU 권장, CPU도 평가 가능) |
| Python | 소스 빌드 기준 3.12 (3.13 이상 미지원 — [알려진 제약](../support/known-limitations.md) 참조) |


## 2. 임베딩 서버(Ollama) 준비

임베딩 모델 서버는 compose에 포함되지 않는다. 평가 호스트 또는 접근 가능한 GPU 서버에
Ollama를 설치하고 기본 임베딩 모델을 내려받는다.

```bash
ollama pull bge-m3
OLLAMA_HOST=0.0.0.0 ollama serve  # 데몬으로 이미 실행 중이면 생략

# 확인 (bge-m3가 목록에 있어야 함)
curl http://localhost:11434/api/tags
```

> **대안 — OpenAI 임베딩**: GPU가 없으면 Ollama 대신 OpenAI API를 쓸 수 있다.
> §4에서 `embedding.provider: "openai"`, `openai_api_key`, `vector_size: 1536`으로
> 설정하면 이 단계는 생략된다 (문서 내용이 외부 API로 전송되는 점 유의).

## 3. 소스 준비

Core 모드 평가는 `rag-api` 저장소 하나로 충분하다.

```bash
git clone https://github.com/cnapcloud/rag-api.git
cd rag-api/docker
```

## 4. 설정

`docker/settings.yaml`에서 임베딩 서버 주소만 환경에 맞게 수정한다.

```yaml
embedding:
  provider: "ollama"
  model: "bge-m3"
  ollama_url: "http://<Ollama 호스트 IP>:11434"   # 컨테이너에서 접근 가능한 주소
```

- 리랭킹(`retrieval.rerank`)은 외부 API(Jina) 연동 기능이다. API 키가 없으면
  `enabled: false`로 두어도 검색은 정상 동작한다 (RRF 점수 사용).

## 5. 기동

```bash
docker compose up -d --build
```

빌드 포함 최초 기동은 수 분 소요된다. 상태 확인:

```bash
docker compose ps                        # 전 서비스 Up/healthy 확인
curl http://localhost:8000/ready         # {"status":"ready", ...} 이면 준비 완료
```

`/ready`가 503이면 아직 의존 서비스 초기화 중일 수 있다. 1~2분 후 재시도하고, 계속
실패하면 `checks`에서 false인 항목의 컨테이너 로그를 확인한다.

### 접속 주소

| 서비스 | 주소 | 용도 |
|--------|------|------|
| RAG API | http://localhost:8000 | REST API (Swagger UI: `/docs`) |
| 관리 콘솔 | http://localhost:8080 | KB·문서·커넥터 관리, 검색 콘솔 |
| Dagster UI | http://localhost:3000 | 인덱싱 파이프라인 실행 현황 |
| MinIO 콘솔 | http://localhost:9001 | 원본 문서 스토리지 확인 (admin/password) |
| Mailpit | http://localhost:8025 | 평가용 메일 수신함 (ENT 초대 메일 확인용) |

## 6. 정리 및 다음 단계

```bash
docker compose down            # 중지 (데이터 볼륨 유지)
docker compose down -v         # 중지 + 데이터 삭제
```

`/ready`가 정상이면 설치는 끝났다. 이제 [첫 KB와 검색](first-kb-and-query.md)에서 KB를
만들고 문서를 올려 실제로 검색해본다.

| 다음 단계 | 문서 |
|-----------|------|
| KB 생성 → 문서 업로드 → 검색 (튜토리얼) | [first-kb-and-query.md](first-kb-and-query.md) |
| SSO·KB 접근제어 포함 Enterprise 평가 | [guides/rag-ent/sso-and-auth-setup.md](../guides/rag-ent/sso-and-auth-setup.md) |
| 운영 환경(k8s) 설치 | [kubernetes.md](../deploy/kubernetes.md) |
| 커넥터(Confluence·GitHub·웹) 설정 | [guides/rag-api/connectors.md](../guides/rag-api/connectors.md) |
