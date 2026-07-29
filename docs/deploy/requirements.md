---
sidebar_position: 1
---

# 설치 사양

Kubernetes 기반 운영 환경에 RAG Platform을 설치하기 위해 필요한 최소 시스템 사양과 스토리지 산정 기준을 설명한다.
최소 사양은 **문서 약 1만 건, 동시 사용자 약 10명** 규모를 기준으로 한다. 실제 운영 환경에서는 문서 수, 사용자 수, 검색 요청량, 임베딩 구성(OpenAI API 또는 자체 모델), 고가용성(HA) 요구사항에 따라 필요한 리소스를 산정한다.

Docker Compose 기반 평가(PoC) 환경은 [Quick Start](../getting-started/quickstart.md)를 참고한다.

---

## 1. 최소 사양

k8s worker node 3대 — 노드당 2 vCPU / 8 GB RAM / 40 GB Disk

문서 ~1만 건, 동시 사용자 ~10명 규모 기준이다. 임베딩 서버(Ollama)는 위 worker node와
별도로 GPU 8 GB VRAM 이상을 갖춘 노드가 필요하다(OpenAI API 사용 시 불필요). 디스크
용량은 컴포넌트 배치에 따라 달라지므로 §2 스토리지 산정 기준을 함께 확인한다.

## 2. 스토리지 산정 기준

문서 ~1만 건 규모의 대략적인 컴포넌트별 디스크 추정치다(단일 인스턴스 기준). 정밀
벤치마크가 아닌 대략적인 목표치다.

| 컴포넌트 | 단일 인스턴스 (문서 1만 건 기준) | 비고 |
|----------|----------------------------------|------|
| Qdrant (벡터) | ~3 GB | |
| PostgreSQL (메타데이터 + Dagster 실행 이력) | ~3 GB (메타 ~1 GB + Dagster 이력 ~2 GB) | |
| Redis (큐) | 1 GB 미만 | 문서 수와 무관하게 일정 |
| 오브젝트 스토리지 (MinIO, 원본 문서) | ~10~12 GB | |
| **합계** | **약 17~19 GB** | |

PostgreSQL(`cnpg-cluster`)·Redis(`redis-ha`)·MinIO(분산 모드) 3개 컴포넌트는 HA 구성이
가능하다 — HA로 배포하면 해당 컴포넌트만 위 수치의 ×3(복제 노드 수)만큼 늘어난다.

Dagster 실행 이력은 보존 정책이 없어 방치 시 계속 증가한다 — 주기적 정리를 권장한다
([runbook.md](runbook.md) 참고).

## 3. 소프트웨어 요구

| 항목 | 요구 |
|------|------|
| 컨테이너 런타임 | Docker 24+ (평가), Kubernetes 1.27+ (운영) |
| Ingress | nginx ingress controller + TLS 인증서 (운영) |
| IdP (Enterprise) | OIDC 호환 (Keycloak 검증됨) |
| SMTP (Enterprise) | 초대 메일 발송용 실 SMTP 서버 |

## 4. 네트워크 포트

| 포트 | 컴포넌트 | 노출 범위 |
|------|----------|-----------|
| 8000 | RAG API (+MCP `/mcp`) | 사용자/연동 앱 — ingress 경유 |
| 80 (8080) | 관리 콘솔 | 사용자 — ingress 경유 |
| 3000 | Dagster UI | **운영자 전용** — 외부 비노출 권장 |
| 5432 / 6379 / 6333 / 9000 | Postgres / Redis / Qdrant / S3 | 내부 전용 |
| 11434 | Ollama | 내부 전용 (API 서버·Dagster에서 접근) |

**주의**: 데이터 계층(Postgres/Redis/Qdrant/S3)과 Dagster UI는 외부에 노출하지 않는다 —
사용자 접점은 관리 콘솔과 RAG API 두 개뿐이다.

## 5. 외부 연결 요구 (선택 기능)

| 기능 | 외부 연결 | 미연결 시 |
|------|-----------|-----------|
| 리랭킹 | Jina API (HTTPS)| `enabled: false` 또는 자동 폴백 — 검색은 정상 동작 |
| OpenAI 임베딩 | OpenAI API | Ollama 로컬 임베딩 사용 (기본) |
| 커넥터 | 대상 시스템(Confluence/GitHub/웹) | 직접 업로드만 사용 |

임베딩을 Ollama로 구성하고 리랭킹을 끄거나 `provider: internal`(자체 호스팅)로 구성하면
**완전 폐쇄망 운영이 가능**하다.
