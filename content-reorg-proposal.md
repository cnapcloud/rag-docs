# RAG Docs 콘텐츠 재구성 기획안


docs/
├── overview/                          # 원안의 intro.md 단일 파일 대신, 카테고리로 구성해
│   │                                  # 소개(내러티브)와 기능 카탈로그(스캔용 표)의 역할을 분리
│   ├── introduction.md               # conductor-oss devguide/concepts 패턴 차용 — 4단 구성:
│   │                                  # 1) RAG Platform으로 뭘 할 수 있나(핵심 가치·사용 시나리오)
│   │                                  # 2) 핵심 빌딩 블록(KB/Connector/Document/Search 정의 +
│   │                                  #    각 상세 문서로 링크) 3) 차별점(경쟁 제품 포지셔닝,
│   │                                  #    Core/Enterprise 차이) 4) 더 깊이 보기(concepts/·guides/ 링크)
│   └── features.md                   # [Core]/[ENT] 표기가 붙은 영역별 전체 기능·파라미터
│                                      # 카탈로그 — concepts/에 흡수하는 대신(성격이 안 맞음:
│                                      # concepts는 "왜"를 설명, 이 문서는 스캔용 체크리스트)
│                                      # introduction.md와 같은 카테고리에 남겨 인트로 역할 유지
│
├── getting-started/                  # Tutorial (Diátaxis) — installation.md 없음: quickstart와
│   │                                  # 겹치지 않는 고유 튜토리얼 콘텐츠가 없어서 제외.
│   │                                  # 기존 install/01-requirements.md(사이징 표, Reference
│   │                                  # 성격)는 deployment/production-checklist.md로 이동
│   ├── quickstart.md                 # docker-compose로 5분 안에 띄우기
│   └── first-kb-and-query.md         # KB 생성 → 문서 업로드 → 검색까지 엔드투엔드
│
├── concepts/                         # Explanation (Diátaxis) — 정적 구조 → 정적 인프라 →
│   │                                  # 동적 흐름 → 엔터티 상태 → 횡단 권한 순으로 쌓이는 구성.
│   │                                  # 내부 엔지니어링 문서(docs/internal/architecture, 3분할:
│   │                                  # application/technical/runtime)와 같은 원칙을 쓰되,
│   │                                  # 대상은 "고치는 사람"이 아니라 "도입·연동하는 사람"
│   ├── architecture.md      # [구조] rag-api/rag-ent-api/rag-admin 컴포넌트 구성과
│   │                                  # 각자 책임, KB가 이 구조 전체를 조직하는 핵심 도메인
│   │                                  # 개념이라는 것(문서 격리+설정 오버라이드+권한 경계가
│   │                                  # 동시에 KB 단위로 걸림), Core/Enterprise가 이 구조 안에서
│   │                                  # 무엇이 바뀌는지(API 이미지·설정만 다르고 아키텍처는 동일)
│   ├── data-flow.md                   # [흐름] architecture.md의 Pipeline Layer가 다루지 않은
│   │                                  # 두 가지 — 검색 흐름(질의→하이브리드 검색→RRF→리랭크
│   │                                  # →응답, 리랭커 폴백)과 dedup이 왜 3단계(해시→MinHash→
│   │                                  # 청크 코사인 유사도) 깔때기 구조인지
│   ├── ingestion-extensions.md       # [흐름, Enterprise] rag-ent-api가 parser_plugins로
│   │                                  # parse 단계에 꽂는 이미지 캡셔닝/PDF OCR 폴백/표 구조
│   │                                  # 보존 파싱 처리 흐름 — vector/스캔 페이지의 표 위치
│   │                                  # 탐지 방식이 갈리는 이유, content_type별 chunk 처리
│   ├── document-lifecycle.md         # [상태] 문서 8개 상태(활성 4/안정 4), 활성 상태에서
│   │                                  # 요청이 409로 막히는 이유, dedup 판정→outdated 전이,
│   │                                  # 재시작 후 stuck 문서가 생기는 이유와 복구
│   ├── connector-lifecycle.md        # [상태] status/sync_status 이원 상태, error에서 자동
│   │                                  # 복구되는 조건, abort와 sync 실패가 다르게 취급되는 이유,
│   │                                  # 자동 스케줄에만 있는 stale lock(1시간), 재시작 후 복구
│   ├── access-control.md             # [권한] KB 단위 RBAC 4단계(viewer/editor/admin/owner)가
│   │                                  # REST·검색·MCP 전체에 동일하게 적용된다는 일관성 원칙
│   └── resource-authorization.md     # [권한] 그 role이 리소스마다 실제로 어떤 문턱값으로
│                                      # 걸리는지 — 인증/인가/super-admin 세 축, admin과 owner가
│                                      # 갈리는 지점, 리소스마다 강제 방식(엔드포인트별/라우터
│                                      # 분리/단일 게이트/필터링)이 다른 이유, frozen KB 예외
│
├── guides/                           # How-to (Diátaxis) — 제품별 하위 분류, 각 제품의
│   │                                  # 실제 도메인 모델을 그대로 뼈대로 사용 (KB/Connector/
│   │                                  # Pipeline/Document/Search 등) — 백로그 항목 나열이 아님
│   ├── rag-api/                      # KB / Connector / Pipeline / Document / Search / MCP
│   │   ├── kb.md   # KB 생성/관리 + 설정 오버라이드(ingestion/chunking/dedup)
│   │   ├── connectors.md                 # 웹/Confluence/GitHub 커넥터 생성·동기화·운영
│   │   ├── ingestion-pipeline.md         # validate→parse→chunk→dedup→embed→upsert→meta 각 스텝
│   │   │                                  # (파서 확장 레지스트리, dedup 임계값 튜닝 포함)
│   │   ├── documents.md                  # 업로드·상태 추적·재인덱싱·복구·삭제(문서 생명주기)
│   │   ├── search.md                     # 하이브리드/유사도 검색, alpha·rerank·min_score 튜닝
│   │   └── mcp-integration.md            # MCP 서버(search/list_knowledge_bases/get_document_status)
│   ├── rag-admin/                    # 콘솔 화면 단위 — rag-api 도메인과 1:1 대응
│   │   ├── dashboard-overview.md         # Home — 대시보드 지표, 인프라 상태 타일 읽는 법
│   │   ├── managing-knowledge-bases.md   # Knowledge Bases — KB 생성/목록/상태 확인
│   │   ├── connectors.md                 # Connectors — 커넥터 생성 마법사 UI로 운영
│   │   ├── documents.md                  # Documents — 업로드, 처리 상태(임베딩/dedup) 모니터링
│   │   ├── query-playground.md           # Query Playground — 검색 콘솔 사용법
│   │   ├── configuration-overrides.md    # Configuration — KB 설정 오버라이드 편집 화면
│   │   └── access-management.md          # Access Management [ENT] — 역할 부여, 초대, 소유권 이전
│   └── rag-ent/                      # rag-ent-api 확장 능력 단위
│       ├── sso-and-auth-setup.md         # OIDC/Keycloak 연동
│       ├── membership-and-invites.md     # 멤버십·초대·소유권 이전, 사용자 프로필 캐시
│       ├── kb-visibility.md              # public KB
│       ├── rate-limiting.md              # 사용자별 요청 제한
│       ├── image-captioning-ocr-fallback.md  # 이미지 캡셔닝, 스캔 문서 OCR 폴백
│       └── table-layout-parsing.md       # PDF 표 구조 보존 파싱
│
├── reference/                        # Reference (Diátaxis) — 정확성 우선, 가능하면 자동생성.
│   │                                  # 제품별 폴더링 대신 콘텐츠 유형별 flat 메뉴로 통합
│   │                                  # (guides/reference처럼 제품별로 나눌 만큼 API·설정
│   │                                  # 표면이 제품마다 갈리지 않음 — rag-ent-api가 rag-api
│   │                                  # 위에 얹는 추가 엔드포인트/설정 정도라 한 문서 안에서
│   │                                  # [Enterprise 전용] 표시로 구분하는 편이 낫다)
│   ├── api-guide.md                  # rag-api + rag-ent REST API 통합, OpenAPI 스펙 기반
│   │                                  # 자동 생성 권장. Enterprise 전용 절은 표시로 구분
│   ├── configuration.md              # settings.yaml, rag-api 공통 + rag-ent 확장 설정
│   │                                  # (oidc/authz/smtp/rate_limit 등) 통합
│   ├── environment-variables.md      # docker/.env 시크릿 변수 전체 — settings.yaml과
│   │                                  # 담는 값·배포 형식이 달라 configuration.md와 별도 문서로 분리
│   ├── docker-compose.md             # 컨테이너 구성·이벤트 처리 흐름·기동 의존 순서·오브젝트
│   │                                  # 스토리지 레이아웃. Core/Enterprise 컨테이너 차이(rag-admin
│   │                                  # container_name, mailpit 등)를 한 문서에서 [ENT]로 구분
│   └── cli.md                        # 있다면
│
├── deployment/                       # 별도 섹션으로 분리 추천
│   ├── kubernetes.md
│   ├── docker-compose.md
│   └── production-checklist.md
│
├── support/                          # 기존 support/ 대체 위치 (아래 "미결정 사항" 참고)
│   ├── support-policy.md
│   ├── releases-and-compatibility.md
│   └── known-limitations.md
│
└── faq.md

---

## 외부 사례 조사

Docusaurus 기반 또는 유사 규모의 멀티 오디언스 OSS 프로젝트 5곳의 문서 구조를 조사했다
(Keycloak, Conductor OSS, R2R, Kafka, RabbitMQ — 상세 근거는 조사 당시 세션 로그 참고).

| 프로젝트 | 최상위 nav | Diátaxis 채택 | 멀티 제품/SDK 처리 | 특이사항 |
|---|---|---|---|---|
| Keycloak (Antora) | Getting Started / Server / Operator / Securing Applications / Admin API / Migration | 부분적 (암묵적) | 오디언스별로 **가이드북 자체를 분리** (Server Admin Guide vs Securing Applications Guide) | Admin API 레퍼런스는 OpenAPI 자동생성 |
| Conductor OSS (Docusaurus) | Quickstart / Guides / Cookbook / SDKs / Reference / Deploy | 근접 | 언어별 **SDKs 최상위 섹션** 별도 운영 | Cookbook(태스크 레시피)을 Guides와 분리 |
| R2R (RAG 프레임워크, 가장 유사) | Introduction / Documentation / Cookbooks / API & SDKs / Self-Hosting | 근접, concepts 성격 유지 | Self-Hosting을 Cookbooks/API와 분리 | API & SDKs가 엔드포인트별 자동생성 페이지 |
| Kafka | Getting Started / Key Concepts / APIs / Configuration / Operations (단일 롱페이지) | 약함 | Producer/Consumer/Streams/Connect 각각 API 서브섹션, 커지면 별도 트리로 분리 | Javadoc은 별도 생성물로 외부 링크 |
| RabbitMQ | Getting Started / How to Use / How to Manage / How to Monitor | 미채택이지만 동사형으로 사실상 how-to | 언어별 클라이언트 허브 페이지 별도, 플러그인은 하위 페이지로 중첩 | "How to Use/Manage/Monitor" 동사형 분리가 integrator/operator/SRE 오디언스를 자연히 구분 |

**공통 패턴 (3개 이상에서 반복)**
1. getting-started/quickstart는 항상 최상위 독립 섹션.
2. 클라이언트 SDK가 있으면 언어별로 묶은 별도 허브를 둔다 (feature 가이드마다 중복 기술 방지).
3. 배포/운영(deployment, self-hosting, ops)은 통합 가이드와 분리된 별도 최상위 섹션.
4. "concepts"를 독립 최상위 카테고리로 두는 곳은 드물다 (R2R 정도) — 대부분 getting-started나
   기능 가이드 상단에 개념 설명을 녹인다.
5. REST API 중심 제품은 OpenAPI 기반 엔드포인트별 자동생성, 클라이언트 라이브러리/프로토콜
   중심 제품은 손으로 쓴 프로즈 — 제품 성격에 따라 갈린다.

## 검토 의견

**강점 — 그대로 유지**
- `getting-started/` + `concepts/` + `guides/<product>/` + `reference/` 4분할은 조사한
  5곳 중 가장 근접한 R2R보다도 Diátaxis를 더 정직하게 따른다. concepts를 독립 섹션으로
  둔 것(공통 패턴 4번과 반대)은 리스크가 아니라, RAG 개념(하이브리드 검색, dedup 파이프라인)이
  여러 제품에 걸친 설명이 필요하기 때문에 의도적으로 맞는 선택.
- `guides/`를 제품별 하위 폴더로 나눈 것은 Keycloak(가이드북 자체 분리), RabbitMQ(동사형
  오디언스 분리)와 같은 목적(오디언스 혼선 방지)을 Docusaurus의 auto-generated sidebar
  카테고리 구조로 자연스럽게 구현한다. `reference/`는 반대로 제품별 폴더 없이 flat하게
  두는데, rag-ent-api의 API·설정 표면이 rag-api 위에 얹는 확장 수준이라 guides처럼
  오디언스 자체를 분리할 만큼 크지 않기 때문이다.
- `deployment/`를 별도 섹션으로 뺀 것은 조사 대상 5곳 중 4곳이 공통으로 쓰는 패턴과 일치.

**보완 검토 필요**
1. ~~`reference/cli.md`(최상위, "있다면")는 제품별 폴더링 원칙과 어긋난다~~ — reference/를
   제품별 폴더 대신 `api-guide.md`/`configuration.md` flat 2메뉴로 통합하기로 하면서 이
   불일치 자체가 해소됨. `cli.md`도 같은 층위의 flat 파일로 그대로 둔다.
2. `rag-admin`에는 `reference/` 항목이 없다 — rag-admin이 자체 공개 API 없이 rag-api/rag-ent
   API를 소비하는 대시보드라면 의도된 설계이지만, 이 판단을 문서에 명시해두지 않으면 이후
   "왜 rag-admin만 reference가 없냐"는 질문이 반복될 수 있다.
3. **콘텐츠 유실 위험**: 현재 `rag-docs/docs/support/`(지원 정책, 릴리스·호환성, 알려진
   제약)에 이미 실제 콘텐츠가 있는데, 신규 구조안에는 이를 받을 자리가 없었다. Keycloak의
   Migration, RabbitMQ의 별도 area처럼 이런 정보는 getting-started나 faq에 욱여넣기보다
   독립 섹션으로 두는 사례가 많아 위 트리에 `support/`를 추가했다. faq.md와의 역할 구분:
   faq는 사용자 질문 기반 Q&A, support/는 정책·버전 호환성·제약사항처럼 표 형태의 사실 정보.
4. 클라이언트 SDK(Python/JS 등 rag-api/rag-ent를 감싸는 라이브러리)는 rag-api, rag-ent-api,
   rag-admin 저장소를 확인한 결과 현재 존재하지 않는다. 따라서 R2R/Conductor/RabbitMQ가
   공통으로 갖는 "SDK 허브" 섹션은 지금은 불필요 — 다만 향후 공식 클라이언트 SDK가 나오면
   `reference/sdks/` 최상위 섹션 신설을 고려할 것 (기능 가이드마다 통합 코드를 중복 기술하지
   않기 위함).

## 마이그레이션 매핑 (기존 docs/ → 신규 구조)

| 기존 | 신규 |
|---|---|
| `intro.md` | `intro.md` (유지) |
| `install/01-requirements.md` | `deployment/production-checklist.md` (사이징·요구사항 표) |
| `install/02-quickstart.md` | `getting-started/quickstart.md` |
| `install/03-install-k8s.md` | `deployment/kubernetes.md` |
| `install/04-enterprise-setup.md` | `guides/rag-ent/sso-and-auth-setup.md` (SSO 부분) + `deployment/production-checklist.md` (인프라 부분) 분리 |
| `install/05-verification.md` | `getting-started/first-kb-and-query.md`에 통합 |
| `install/06-integrations.md` | `guides/rag-api/` 하위로, 성격에 따라 신규 파일명 부여 |
| `operations/01-runbook-k8s.md`, `03-runbook-docker-compose.md` | `deployment/production-checklist.md` |
| `operations/02-observability.md` | `guides/rag-admin/monitoring-and-logs.md` |
| `overview/01-product.md` | `overview/introduction.md` |
| `overview/02-features.md` | `overview/features.md` (별도 페이지 유지, `intro.md` 통합안 폐기) |
| `overview/03-architecture.md` | `concepts/architecture.md` |
| `reference/01-api-guide.md` | `reference/api-guide.md` (rag-api + rag-ent 통합, Enterprise 전용 절은 표시로 구분) |
| `reference/02-settings-guide.md` | `reference/configuration.md` (rag-ent 확장 설정 포함 통합) |
| `reference/03-environment-guide.md` | `reference/environment-variables.md` (별도 문서 유지) |
| `reference/04-features-catalog.md` | `concepts/` 하위 관련 파일에 흡수 |
| `reference/05-docker-compose-reference.md` | `reference/docker-compose.md` (deployment/ 대신 flat reference/ 유지) |
| `support/01-support-policy.md` | `support/support-policy.md` |
| `support/02-releases.md` | `support/releases-and-compatibility.md` |
| `support/03-known-limitations.md` | `support/known-limitations.md` |

## 미결정 사항

- [ ] `support/`를 최상위 섹션으로 유지할지, 일부는 `faq.md`로 흡수할지 — 위 의견 참고,
      독립 섹션 유지를 권장하나 최종 판단 필요.
- [ ] `rag-admin`이 향후에도 자체 공개 API를 갖지 않을지 (안 갖는다면 `reference/`에
      rag-admin 항목이 없는 것은 확정 설계로 문서 상단에 한 줄 명시 권장).
- [ ] `install/04-enterprise-setup.md`를 SSO 가이드와 배포 체크리스트로 쪼갤지, 하나로
      유지할지 — 원문 내용 검토 후 결정.