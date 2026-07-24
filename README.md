# RAG Platform Docs

RAG Platform(Core: `rag-api` / Enterprise: `rag-ent-api` / 콘솔: `rag-admin`) 공식 문서 사이트의
소스 저장소. [Docusaurus](https://docusaurus.io/)로 빌드되는 공개(public) 사이트이며, 문서
원본은 전부 `docs/`에 있다.

| 표기 | 의미 |
|---|---|
| `[ENT]` | Enterprise(`rag-ent-api`, OIDC 인증 + RBAC) 배포에만 해당. 표기가 없으면 Core/Enterprise 공통 |

## 구성

| 폴더 | 내용 |
|------|------|
| [docs/overview/](docs/overview/) | 제품 정의, 기능 카탈로그 |
| [docs/getting-started/](docs/getting-started/) | Quick Start, 첫 KB 생성부터 검색까지 |
| [docs/concepts/](docs/concepts/) | 아키텍처, 검색·인제스트 흐름, 접근 제어 등 동작 원리 |
| [docs/guides/](docs/guides/) | 제품별(`rag-api` / `rag-admin` / `rag-ent`) How-to |
| [docs/deploy/](docs/deploy/) | 요구사항, k8s 설치, 백업/복구/업그레이드 runbook, 관측 구성 |
| [docs/reference/](docs/reference/) | API, 설정(`settings.yaml`), 환경변수(`.env`), Docker Compose 레퍼런스 |
| [docs/support/](docs/support/) | 지원 정책, 릴리스·호환성, 알려진 제약 |
| [docs/demo/](docs/demo/) | 데모 시나리오·영상 (녹화 스크립트/원본 소스는 저장소 루트 `demo/`, 사이트에는 포함 안 됨) |

## 읽는 순서 (처음 접하는 경우)

1. [overview/introduction.md](docs/overview/introduction.md) — 제품이 뭔지
2. [getting-started/quickstart.md](docs/getting-started/quickstart.md) — 30분 안에 첫 검색까지
3. [deploy/kubernetes.md](docs/deploy/kubernetes.md) — 실제 배포
4. [deploy/runbook.md](docs/deploy/runbook.md) — 배포 후 운영

## 문서 사이트 실행

`Makefile` 타겟 또는 npm 스크립트 중 편한 쪽을 쓴다.

```bash
make install   # npm install
make start     # 개발 서버 (http://localhost:3000, 변경사항 즉시 반영)
make build     # 정적 빌드 (build/)
make serve     # 빌드 결과물 로컬 서빙
make clean     # build/, .docusaurus/ 삭제
```

컨테이너 이미지 빌드/푸시:

```bash
make docker-build   # 로컬 이미지 빌드
make docker-push    # 레지스트리 빌드/푸시
```

## 문서 추가/수정

- 문서 파일은 `docs/<섹션>/slug.md` 형식 — 파일명에 번호 접두사를 쓰지 않는다
  (`numberPrefixParser: false`). 사이드바 순서는 파일 프런트매터의 `sidebar_position`,
  섹션(폴더) 순서는 각 폴더 `_category_.json`의 `position`으로 정한다.
- 섹션(폴더) 라벨·설명은 `_category_.json`에서 관리.
- 새 섹션을 추가하면 `docusaurus.config.js`의 navbar/footer 링크도 함께 갱신한다.
- 문서 작성 컨벤션(문장·표·헤딩 구성, `[ENT]` 표기 규칙 등)은 [CLAUDE.md](CLAUDE.md) 참고.

## 유지보수 원칙

- 코드 저장소(`rag-api`, `rag-ent-api`, `rag-admin`)의 실제 동작을 반영해서 쓴다 — 코드가
  바뀌면 이 저장소도 같은 PR 사이클에서 갱신한다(문서가 코드를 따라가지 못하는 걸 방지).
- 내부 전략·게이트 트래킹 문서는 여기 두지 않는다 — `rag-product` 저장소 참고.
