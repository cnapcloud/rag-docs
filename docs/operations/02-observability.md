# Observability

Langfuse·Prometheus·Grafana 기반 관측 구성을 다룬다. 대시보드 일부는 설계는 완료되었으나
구현이 진행 중이며, 해당 항목은 본문에 표시했다.

---

## 1. 구성 개요 — 3계층 관측

```
[무엇이 잘못됐나]        Prometheus  ── k8s 프로브(/health, /ready) 기반 가용성·리소스
[무슨 일이 있었나]        Langfuse    ── 검색·MCP·LLM 호출 trace (저장소: ClickHouse)
[전체 흐름은 어떤가]      Grafana     ── 두 소스를 묶은 통합 대시보드
                                        (Prometheus + ClickHouse datasource)
```

| 계층 | 역할 | 데이터 소스 |
|------|------|-------------|
| Prometheus | 서비스 가용성, 컨테이너 리소스, 재시작 감지 | kube-state, 프로브 |
| Langfuse | 요청 단위 추적 — 검색 지연, MCP 툴 호출, (LibreChat 연계 시) LLM 토큰·비용, 품질 점수 | 제품 OTel 계측, LLM 앱 콜백 |
| Grafana | 성능·비용·사용 패턴·품질 대시보드 | ClickHouse(Langfuse 데이터) + Prometheus |

## 2. Langfuse — 검색·LLM 추적 (제품 내장 기능)

### 2.1 제품 측 활성화

본 제품은 OpenTelemetry 기반 Langfuse 전송을 내장한다. `settings.yaml`:

```yaml
tracing:
  enabled: true
  langfuse_baseurl: "http://<langfuse 주소>:3000"
  langfuse_public_key: "<pk-lf-...>"     # Secret으로 주입
  langfuse_secret_key: "<sk-lf-...>"     # Secret으로 주입
  service_name: "rag-api"
```

추적 범위:

| 경로 | 내용 |
|------|------|
| REST 검색 (`/api/search`) | 검색 요청 span — W3C `traceparent` 헤더를 보내면 호출 앱의 trace에 연결됨 |
| MCP 툴 호출 | 요청 `_meta.traceparent`를 수신해 상위 trace의 child로 기록 — LibreChat 등 MCP 클라이언트의 대화 trace 아래에 검색이 나타남 |

### 2.2 E2E 체인 (LibreChat 연계 시)

LibreChat 연계([06-integrations.md](../install/06-integrations.md)) 환경에서는 하나의 사용자 질문이
다음과 같이 단일 trace로 이어진다:

```
사용자 질문 (LibreChat AgentRun)
  ├── LLM 호출 (litellm → 모델)     : 토큰 수, TTFT, 비용
  └── RAG 검색 (MCP tools/call)     : 검색 지연, 반환 청크
```

이 체인이 되면 **"느린 응답의 원인이 LLM인지 검색인지"를 trace 하나로 판별**할 수 있다.
LibreChat 측 trace 전파에는 계측 패치 이미지가 필요하다 (사내 검증 완료 — 적용은 지원
채널로 문의).

### 2.3 품질 평가 (LLM-as-judge, 선택)

검색 결과가 MCP tool 결과로 trace에 저장되므로, **추가 계측 없이** Langfuse Evaluator
설정만으로 품질 지표를 샘플링 평가할 수 있다.

| 지표 | 의미 |
|------|------|
| Context Precision / Recall | 검색된 문서가 답변에 유효했는지 / 필요한 문서를 찾았는지 |
| Faithfulness | 답변이 검색 문서에 충실한지 (환각 감지) |
| Answer Relevance | 질문 대비 답변 관련성 |

구성: Langfuse UI에서 LLM 연결(judge 모델) 등록 → Evaluator 생성 → 샘플링 비율 설정
(**10~20% 권장** — 전량 평가는 judge LLM 비용 과다). 평가 결과는 대시보드(§4)에서 추이로
확인한다.

## 3. Prometheus — 가용성·리소스

| 항목 | 방법 |
|------|------|
| 서비스 가용성 | rag-api의 `/health`(liveness)·`/ready`(readiness) 프로브 결과를 kube-state-metrics로 수집. `/ready`는 인프라(Qdrant/Redis/Postgres/S3/임베딩) 연결까지 반영하므로 이 지표 하나로 의존 인프라 이상까지 감지된다 |
| 리소스·재시작 | 표준 kube 메트릭 (CPU/메모리, restart count) |
| 인제스트 백로그 | 제품 API 폴링으로 대체: `GET /api/docs/status`의 `pending`/`running`/`failed` 집계를 주기 수집해 경보 기준으로 사용 (예: pending이 N분 이상 감소하지 않으면 경보) |

> **현재 제약**: 제품 자체 `/metrics`(Prometheus exposition) 엔드포인트는 아직 제공하지
> 않는다 (로드맵 반영 — 큐 깊이·인제스트 실패율·검색 지연 히스토그램 노출 예정). 그
> 전까지 요청 단위 성능 지표는 Langfuse(§2), 백로그 지표는 위 API 폴링 방식을 사용한다.

### 권장 경보 기준선

| 경보 | 조건(예시) |
|------|-----------|
| Readiness 실패 | `/ready` 503이 3분 지속 |
| 인제스트 정체 | `pending + running`이 30분간 감소 없음 |
| 실패 누적 | `failed` 증가율이 임계 초과 |
| 리랭커 폴백 지속 | 검색 응답 `rerank_fallback: true` 비율 급증 (Langfuse trace 속성으로 집계) |

## 4. Grafana — 통합 대시보드

### 4.1 데이터소스

| datasource | 대상 | 비고 |
|------------|------|------|
| Prometheus | §3 지표 | 표준 구성 |
| ClickHouse | Langfuse의 traces/observations/scores 테이블 | Grafana ClickHouse 플러그인 설치 필요 |

### 4.2 대시보드 구성 (Langfuse-ClickHouse 기반)

| 대시보드 | 패널 | 상태 |
|----------|------|------|
| 성능 | TTFT, E2E 지연 p50/p95/p99, TPS, 에러율 | 쿼리 검증 완료 — 대시보드 패키징 진행 중 |
| 비용·사용량 | 모델별 토큰/비용 추이, 사용자별 누적, 시간대 트래픽, 기능별(RAG/일반 대화) 분포 | 동일 |
| 안정성 | 가용성(Prometheus), 타임아웃·재시도율 | 동일 |
| 품질 | LLM-as-judge 점수 추이(§2.3), 사용자 피드백(좋아요/싫어요) | 환경 구성·동작 확인 완료 |

대시보드는 JSON ConfigMap(`grafana_dashboard: "1"` 레이블)로 배포하면 Grafana sidecar가
자동 적재한다. 표준 대시보드 팩은 관측 패키지로 제공 예정이며, 그 전에는 쿼리 예시를 지원
채널로 제공한다.

## 5. 구성 수준 선택 가이드

| 수준 | 구성 | 얻는 것 |
|------|------|---------|
| 기본 (필수) | Prometheus 프로브 + 백로그 API 폴링 경보 | 장애·정체 감지 |
| 표준 (권장) | + Langfuse 트레이싱 활성화 (§2.1) | 검색 성능 분석, 요청 단위 진단 |
| 전체 | + LibreChat E2E 체인 + Grafana 대시보드 + LLM-as-judge | 서비스 품질·비용까지 상시 가시화 |

기본 수준은 설치 당일 구성 가능하다. 표준은 Langfuse 배포(또는 기존 인스턴스)가 전제이고,
전체는 관측 패키지 일정([지원 정책](../support/01-support-policy.md) 채널 문의)에 따른다.
