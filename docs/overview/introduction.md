---
sidebar_position: 1
title: Introduction
---

# RAG Platform

**RAG Platform은 사내 문서를 자동으로 수집·인덱싱하고, LLM 애플리케이션과 AI 에이전트에 고품질
하이브리드 검색을 공급하는 셀프호스팅 RAG 검색 플랫폼이다.**

챗봇이나 앱을 만들어주는 도구가 아니라, 조직의 문서 지식을 "검색 가능한 상태"로 유지하고 그
검색 능력을 REST API와 MCP(Model Context Protocol)로 어떤 LLM 애플리케이션에든 꽂아 쓸 수
있게 하는 **검색 백엔드(retrieval backend)**다.

---

## 1. RAG Platform으로 뭘 할 수 있나

- **문서를 검색 가능한 상태로 유지한다** — 파일 직접 업로드(PDF·Word·한글(HWP)·마크다운 등)와
  웹·Confluence·GitHub 커넥터를 통한 자동 수집을 모두 지원하고, 커넥터는 변경분만 자동
  재인덱싱한다.
- **하이브리드 검색을 어디서든 호출한다** — 의미(dense) + 키워드(sparse) 검색을 RRF로 병합한
  결과를 REST API와 MCP 양쪽으로 노출한다. 기존 챗 서비스, IDE 에이전트, 자체 앱 어디서든
  같은 검색을 재사용할 수 있다.
- **중복·유사 문서를 자동으로 걸러낸다** — 같은 내용이 여러 KB에 반복 색인되며 검색 품질을
  떨어뜨리는 것을 막는다.
- **완전 셀프호스팅이 가능하다** — 임베딩까지 로컬 모델(Ollama)로 구성하면 외부 API 호출이
  전혀 없는 폐쇄망 운영이 가능하다.  
- **지식베이스(KB) 단위로 경계를 나눈다** — 문서 저장, 청킹·중복감지 설정, 접근 권한[ENT]이
  모두 KB 단위로 걸린다. 부서·목적별로 KB를 나눠 운영해도 서로 간섭하지 않는다.
- **고급 문서를 이해한다** — 이미지 캡셔닝, 스캔 문서에 대한 OCR 폴백, PDF 표 구조를
  유지하는 파싱 기능 등을 지원한다[ENT].

핵심 기능을 한눈에 살펴보려면 [Features](features.md)를 참고한다 — `[Core]`는 기본
배포부터 제공되는 기능, `[ENT]`는 Enterprise 배포에서 추가로 제공되는 기능이다.

## 2. 제품 구성

RAG Platform은 제품 3종으로 구성된다 — 상시 실행되는 관리 콘솔(rag-admin)과, 배포 모드에
따라 둘 중 하나만 실행되는 API 서버(rag-api 또는 rag-ent-api)다.

```
          ┌──────────────────────────────┐
          │          rag-admin           │   Console — always running
          └──────────────────────────────┘
                          │  REST API
                          ▼
          ┌──────────────────────────────┐
          │           rag-api            │   [Core] — no auth
          │            — or —            │   only one is deployed at a time
          │         rag-ent-api          │   [ENT] — OIDC auth + KB-level RBAC + Extensions
          └──────────────────────────────┘
```

- **rag-api** — 오픈소스(MIT)로 공개 ([GitHub](https://github.com/cnapcloud/rag-api))
- **rag-admin** — 비공개
- **rag-ent-api** — 비공개

[Getting Started](../getting-started/quickstart.md)에서 rag-api와 rag-admin만으로 docker-compose
설치부터 KB 생성·문서 업로드·검색까지 직접 시연해볼 수 있다.

## 3. 핵심 빌딩 블록

RAG Platform을 이해하려면 아래 다섯 가지 개념부터 잡고 가는 게 빠르다.

| 개념 | 정의 | 더 보기 |
|------|------|---------|
| **Knowledge Base (KB)** | 문서를 격리하는 기본 단위. 문서뿐 아니라 청킹·중복감지 설정 오버라이드, (Enterprise) 접근 권한까지 전부 KB 단위로 걸린다 | [아키텍처 개요](../concepts/architecture.md) |
| **Connector** | 웹·Confluence·GitHub 같은 외부 소스에서 문서를 자동·증분 수집하는 파이프라인 | [커넥터 가이드](../guides/rag-api/connectors.md) |
| **Document** | 업로드·수집된 문서 한 건. `uploading → pending → running → indexed` 등 상태를 거치며, 처리 중에는 충돌 방지를 위해 일부 요청이 차단된다 | [문서 상태 흐름](../concepts/document-lifecycle.md) |
| **Search** | dense+sparse 하이브리드 결과를 RRF로 병합하고 선택적으로 리랭킹하는 질의 경로 | [검색·인제스트 흐름](../concepts/data-flow.md) |
| **RBAC** | (Enterprise) KB마다 viewer(조회)/editor(문서 작업)/admin(설정·멤버)/owner(삭제·이전) 4단계 역할로 접근을 제어한다 | [접근 제어](../concepts/access-control.md) |

## 4. 차별점

- **앱 빌더가 아니라 검색 인프라다** — Dify·RAGFlow류가 "LLM 앱을 만드는 플랫폼"에 가깝다면,
  RAG Platform은 기존/신규 LLM 앱과 에이전트에 검색만 공급하는 인프라다. 챗 UI나 워크플로
  빌더를 내장하지 않는 것은 의도된 비범위다.
- **R2R과 가장 가깝지만 완결형이다** — R2R(SciPhi)이 같은 "API-first 검색 인프라" 축의
  아키텍처상 가장 가까운 비교 대상이다. RAG Platform은 여기에 KB 단위 RBAC·SSO를 갖춘
  Enterprise 배포, 완전 로컬 추론 기반 표/OCR 처리, 관리 콘솔까지 기본 포함한다.
- **하나의 코드베이스, 두 가지 배포 형태** — **Core**(인증 없는 내부망 전용 구성)와
  **Enterprise**(Keycloak 연동 SSO + KB 단위 RBAC 추가)는 같은 아키텍처에서 API 이미지와
  설정만 다르다. 관리 콘솔도 같은 빌드가 두 모드를 모두 지원한다. Core로 시작해 인증·권한이
  필요해지면 Enterprise로 전환하면 된다.

## 5. 더 깊이 보기

- 구조·인프라·데이터 흐름·상태·권한을 하나씩 이해하고 싶다면 → [concepts/](../concepts/architecture.md)
- 지금 바로 설치해보고 싶다면 → [getting-started/quickstart.md](../getting-started/quickstart.md)
- 특정 기능(KB 관리, 커넥터, 파이프라인, 검색, MCP 등)을 바로 다루고 싶다면 → [guides/](../guides/rag-api/kb.md)
