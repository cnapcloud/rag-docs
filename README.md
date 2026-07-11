# RAG API — 고객 인도 문서

RAG 제품(rag-api / rag-ent-api / rag-admin)을 설치·운영·연동하는 고객·파트너를 위한 문서 모음.

| 적용 대상 | 의미 |
|---|---|
| [공통] | Core, Enterprise 배포 모두 해당 |
| [Enterprise 전용] | Enterprise(rag-ent-api, OIDC 인증 + RBAC) 배포에만 해당 |

## 구성

| 폴더 | 내용 |
|------|------|
| [overview/](overview/) | 제품 개요, 기능 카탈로그, 아키텍처 |
| [install/](install/) | 요구사항, Quick Start, k8s 설치, Enterprise 설정, 설치 검증, 연동 가이드 |
| [operations/](operations/) | 백업·복구·업그레이드 runbook(k8s / docker-compose), 관측 구성 |
| [reference/](reference/) | API 가이드, 설정(settings.yaml) 레퍼런스, 환경변수(.env) 레퍼런스 |
| [support/](support/) | 지원 정책, 릴리스·호환성, 알려진 제약 |

## 읽는 순서 (처음 접하는 경우)

1. [overview/01-product.md](overview/01-product.md) — 제품이 뭔지
2. [install/02-quickstart.md](install/02-quickstart.md) — 30분 안에 첫 검색까지
3. [install/03-install-k8s.md](install/03-install-k8s.md) — 실제 배포
4. [operations/01-runbook-k8s.md](operations/01-runbook-k8s.md) — 배포 후 운영

## 유지보수 원칙

- 새로 쓰지 않는다 — 코드 저장소(rag-api, rag-ent-api)의 실제 동작을 반영해 이 저장소로
  옮겨온 문서다. 코드가 바뀌면 이 저장소도 같은 PR 사이클에서 갱신한다(문서가 코드를
  따라가지 못하는 걸 방지).
- 내부 전략·게이트 트래킹 문서는 여기 두지 않는다 — [rag-product](../rag-product) 참고.
- Core/Enterprise 구분이 필요한 절은 제목이나 본문에 `[공통]`/`[Enterprise 전용]`을 명시한다.
