---
sidebar_position: 2
---

# Knowledge Bases

KB 목록 조회, 생성, 수정, 삭제를 다루는 화면이다. REST API 기준 동작은
[KB 관리](../rag-api/kb.md)에서 다룬다 — 이 화면은 그 API를 호출하는 클라이언트다.

## 목록·검색

![Knowledge Bases 목록](/img/kb-admin/kb-list.png)

ID/Name/Created 헤더를 클릭하면 정렬 기준이 바뀐다. 검색창은 KB ID·이름·설명에 대해 부분
일치로 필터링한다. 행을 클릭하면 우측에 상세 패널이 열린다.

## KB 생성

![새 KB 생성](/img/kb-admin/kb-add.png)

우측 상단 New KB 버튼으로 연다.

- **KB ID** — 필수, 중복 불가.
- **Name** — 선택, 표시 이름.
- **Description** — 선택.
- **Tags** — 선택, 쉼표로 구분해 입력한다.

## 상세·수정·삭제

목록에서 행을 선택하면 우측 패널에 KB ID·Name·Description·Tags·Created가 표시되고 Edit·
Delete 버튼이 있다. Edit은 Name/Description/Tags만 바꿀 수 있다 — KB ID는 생성 후 변경할 수
없다.

![새 KB 생성](/img/kb-admin/kb-edit.png)

Delete는 아래 조건에서 막힌다.

- 남은 KB가 이 하나뿐일 때 — 최소 1개는 항상 유지된다.
- Enterprise 배포에서 역할이 부여된 KB라면, 그 KB의 owner가 아닐 때.

삭제는 Qdrant 컬렉션 → S3 오브젝트 → PostgreSQL 메타데이터 순으로 진행되며 되돌릴 수 없다.

## Enterprise 배포에서 달라지는 점

Enterprise 배포(rag-ent-api, OIDC 로그인)에서는 두 가지가 추가된다.

- **Role 열** — 목록과 상세 패널에 KB별 내 역할(Owner/Admin/Editor/Viewer)이 표시된다.
  슈퍼관리자는 실제 멤버십 없이도 모든 KB에 대해 별도로 "Super Admin"으로 표시된다.
- **Visibility** — KB 생성 시 Private/Public을 선택할 수 있다. Public KB는 이름 옆에
  "(Public)" 표시가 붙는다.

역할 체계와 Public/Private의 실제 접근 통제 방식은
[접근 제어](../../concepts/access-control.md)에서 다룬다. KB별 멤버 초대·역할 변경·소유권
이전은 이 화면이 아니라 사이드바의 별도 [Access Management](access-management.md)
화면(관리자에게만 노출)에서 이뤄진다.
