# Quick Start

제품 평가·PoC 담당자를 위한 가장 빠른 설치 경로 — 약 30분(이미지 빌드 시간 제외), Core 모드
(인증 없음) 단일 호스트 docker-compose 배포.

이 문서는 가장 빠르게 "문서 업로드 → 인덱싱 → 검색"을 체험하는 평가용 설치를 다룬다.
인증(SSO)·접근제어를 포함한 Enterprise 구성 평가는 [04-enterprise-setup.md](04-enterprise-setup.md),
운영 환경 설치는 [03-install-k8s.md](03-install-k8s.md)를 참고한다.

---

## 1. 사전 요구사항

| 항목 | 요구 |
|------|------|
| OS | Linux 또는 macOS (Docker Desktop) |
| 소프트웨어 | Docker 24+, Docker Compose v2, git |
| 리소스 | 4 vCPU / 16 GB RAM / 50 GB 디스크 권장 |
| 임베딩 서버 | Ollama (아래 §2에서 준비 — GPU 권장, CPU도 평가 가능) |
| Python | 소스 빌드 기준 3.12 (3.13 이상 미지원 — [알려진 제약](../support/03-known-limitations.md) 참조) |

## 2. 임베딩 서버(Ollama) 준비

임베딩 모델 서버는 compose에 포함되지 않는다. 평가 호스트 또는 접근 가능한 GPU 서버에
Ollama를 설치하고 기본 임베딩 모델을 내려받는다.

```bash
# https://ollama.com 설치 후
ollama pull bge-m3
ollama serve   # 데몬으로 이미 실행 중이면 생략
```

확인:

```bash
curl http://localhost:11434/api/tags   # bge-m3 목록에 있어야 함
```

> **대안 — OpenAI 임베딩**: GPU가 없으면 Ollama 대신 OpenAI API를 쓸 수 있다.
> §4에서 `embedding.provider: "openai"`, `openai_api_key`, `vector_size: 1536`으로
> 설정하면 이 단계는 생략된다 (문서 내용이 외부 API로 전송되는 점 유의).

## 3. 소스 준비

Core 모드 평가는 `rag-api` 저장소 하나로 충분하다.

```bash
git clone <rag-api 저장소 URL>
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

- 같은 호스트에서 Ollama를 실행 중이면 `http://host.docker.internal:11434`
  (Linux는 호스트 IP 사용).
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
실패하면 `checks`에서 false인 항목의 컨테이너 로그를 확인한다
([05-verification.md](05-verification.md) §1 참조).

### 접속 주소

| 서비스 | 주소 | 용도 |
|--------|------|------|
| RAG API | http://localhost:8000 | REST API (Swagger UI: `/docs`) |
| 관리 콘솔 | http://localhost:8080 | KB·문서·커넥터 관리, 검색 콘솔 |
| Dagster UI | http://localhost:3000 | 인덱싱 파이프라인 실행 현황 |
| MinIO 콘솔 | http://localhost:9001 | 원본 문서 스토리지 확인 (admin/password) |
| Mailpit | http://localhost:8025 | 평가용 메일 수신함 (ENT 초대 메일 확인용) |

## 6. 첫 검색까지 (smoke test)

관리 콘솔(`http://localhost:8080`)에서 UI로 진행하거나, 아래처럼 API로 진행한다.

```bash
# 1. KB 생성
curl -X POST http://localhost:8000/api/kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "kb-eval", "kb_name": "평가용 KB"}'

# 2. 문서 업로드 (pdf/docx/hwp/txt/md/html/rst 지원)
curl -X POST http://localhost:8000/api/kb/kb-eval/docs/upload \
  -F "file=@./sample.pdf"
# 응답의 doc_id를 기록

# 3. 인덱싱 상태 확인 — status가 indexed가 될 때까지 (일반 문서 수십 초 내)
curl http://localhost:8000/api/kb/kb-eval/docs/{doc_id}/status

# 4. 검색
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "문서 내용에 대한 질문", "kb_ids": ["kb-eval"]}'
```

검색 응답에 업로드한 문서의 관련 청크가 점수·출처와 함께 반환되면 설치 성공이다.
전체 검증 체크리스트는 [05-verification.md](05-verification.md) 참조.

## 7. AI 에이전트 연결 (선택)

MCP 지원 클라이언트(Claude Code, VS Code 등)에 검색 툴을 노출할 수 있다.

```json
{
  "servers": {
    "rag": { "type": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

## 8. 정리 및 다음 단계

```bash
docker compose down            # 중지 (데이터 볼륨 유지)
docker compose down -v         # 중지 + 데이터 삭제
```

| 다음 단계 | 문서 |
|-----------|------|
| SSO·KB 접근제어 포함 Enterprise 평가 | [04-enterprise-setup.md](04-enterprise-setup.md) |
| 운영 환경(k8s) 설치 | [03-install-k8s.md](03-install-k8s.md) |
| 커넥터(Confluence·GitHub·웹) 설정 | rag-api [api-guide.md](../reference/01-api-guide.md) |
| 규모 산정 | [01-requirements.md](01-requirements.md) |
