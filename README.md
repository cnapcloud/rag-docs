# RAG API Documentation

RAG 제품(rag-api / rag-ent-api / rag-admin)을 설치·운영·연동하는 고객·파트너를 위한 문서 모음.
[Docusaurus](https://docusaurus.io/) 사이트로 빌드되며, 문서 원본은 전부 `docs/`에 있다.

| 적용 대상 | 의미 |
|---|---|
| [공통] | Core, Enterprise 배포 모두 해당 |
| [Enterprise 전용] | Enterprise(rag-ent-api, OIDC 인증 + RBAC) 배포에만 해당 |

## 구성

| 폴더 | 내용 |
|------|------|
| [docs/overview/](docs/overview/) | 제품 개요, 기능 카탈로그, 아키텍처 |
| [docs/install/](docs/install/) | 요구사항, Quick Start, k8s 설치, Enterprise 설정, 설치 검증, 연동 가이드 |
| [docs/operations/](docs/operations/) | 백업·복구·업그레이드 runbook(k8s / docker-compose), 관측 구성 |
| [docs/reference/](docs/reference/) | API 가이드, 설정(settings.yaml) 레퍼런스, 환경변수(.env) 레퍼런스 |
| [docs/support/](docs/support/) | 지원 정책, 릴리스·호환성, 알려진 제약 |
| [docs/demo/](docs/demo/) | 데모 시나리오 및 녹화 스크립트 |

## 읽는 순서 (처음 접하는 경우)

1. [overview/01-product.md](docs/overview/01-product.md) — 제품이 뭔지
2. [install/02-quickstart.md](docs/install/02-quickstart.md) — 30분 안에 첫 검색까지
3. [install/03-install-k8s.md](docs/install/03-install-k8s.md) — 실제 배포
4. [operations/01-runbook-k8s.md](docs/operations/01-runbook-k8s.md) — 배포 후 운영

## 문서 사이트 실행

`Makefile` 타겟 또는 npm 스크립트 중 편한 쪽을 쓴다.

```bash
make install   # npm install
make start     # 개발 서버 (http://localhost:3000, 변경사항 즉시 반영)
make build     # 정적 빌드 (build/)
make serve     # 빌드 결과물 로컬 서빙
make clean     # build/, .docusaurus/ 삭제
```

Docker(nginx)로 서빙:

```bash
make docker-build   # 로컬 이미지 빌드
make docker-push     # 레지스트리 빌드/푸시 (CI)
```

GitHub Pages 배포:

```bash
USE_SSH=true make deploy
# 또는
GIT_USER=<GitHub username> make deploy
```

## 문서 추가/수정

- 문서 파일은 `docs/<섹션>/NN-slug.md` 형식 (번호는 사이드바 정렬용, 파일명에 그대로 유지됨 —
  `numberPrefixParser: false`).
- 섹션(폴더) 라벨·순서는 각 폴더의 `_category_.json`에서 관리.
- 새 섹션을 추가하면 `docusaurus.config.js`의 navbar/footer 링크도 함께 갱신한다.

## 유지보수 원칙

- 새로 쓰지 않는다 — 코드 저장소(rag-api, rag-ent-api)의 실제 동작을 반영해 이 저장소로
  옮겨온 문서다. 코드가 바뀌면 이 저장소도 같은 PR 사이클에서 갱신한다(문서가 코드를
  따라가지 못하는 걸 방지).
- 내부 전략·게이트 트래킹 문서는 여기 두지 않는다 — [rag-product](../rag-product) 참고.
- Core/Enterprise 구분이 필요한 절은 제목이나 본문에 `[공통]`/`[Enterprise 전용]`을 명시한다.
