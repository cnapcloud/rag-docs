---
sidebar_position: 7
---

# Access Management

KB별 멤버 초대·역할 변경·소유권 이전·Visibility 전환을 다루는 화면이다. Enterprise
배포(rag-ent-api, OIDC 로그인)에서만 노출되며, 사이드바에 관리자에게만 보인다. 역할 체계와
실제 접근 통제가 REST·검색·MCP 경로에 어떻게 적용되는지는
[접근 제어](../../concepts/access-control.md)에서 다룬다 — 이 화면은 그 역할 데이터를
편집하는 클라이언트다.

## KB 선택

![Access Management](/img/kb-admin/access-management.png)

상단 Knowledge Base 드롭다운으로 대상 KB를 고른다. 옆의 검색창은 현재 KB의 멤버 목록을
이메일로 필터링한다.

## Visibility

Private/Public 라디오로 KB 공개 범위를 바꾼다. Public으로 바꾸면 멤버십 등록 여부와
무관하게 모든 인증된 사용자가 조회할 수 있다(전사 공지·규정 KB 용도) — 판정 로직은
접근 제어 문서의 "공개 KB와 슈퍼관리자" 절 참고. Public으로 지정된 KB는
[Knowledge Bases 목록](knowledge-bases.md)에서 이름 옆에 "(Public)" 표시로 구분된다.

## Members

Members 탭 표는 Email·Role·Added(등록일) 열로 구성되고, 행마다 역할에 따라 다른 버튼이
붙는다.

- **Owner 행** — Transfer 버튼만 노출된다. 소유권을 다른 멤버에게 넘기면 기존 owner는
  admin으로 강등된다.
- **그 외 역할 행** — Change(역할 변경: viewer/editor/admin 중 선택)와 Remove(멤버십 삭제)
  버튼이 노출된다.

역할 순위(viewer < editor < admin < owner)와 각 역할이 실제로 할 수 있는 작업 범위는
접근 제어 문서의 "역할 계층" 표를 따른다 — 이 화면에서 부여하는 값이 곧 그 표의 판정
기준이다.

우측 상단 **Invite** 버튼으로 이메일 기반 초대를 보낸다. 수락 전 초대는 Pending Invites
탭에서 별도로 확인·취소할 수 있다.

## Knowledge Bases 목록과의 연결

![Knowledge Bases 목록의 Role 열](/img/kb-admin/kb-list-role.png)

이 화면에서 부여한 역할은 [Knowledge Bases](knowledge-bases.md) 목록의 Role 열에 색상
배지(Viewer/Editor/Owner)로 그대로 반영된다. 위 화면은 슈퍼관리자가 아닌 일반 사용자
(john@cnapcloud.com) 기준이다 — 자신이 멤버로 등록된 KB만 목록에 나타나므로, 역할을 받지
않은 KB(예: gitops-kb)는 아예 표시되지 않는다. 앞서 Members 표에서 이 사용자를 kb-02의
editor로 등록한 것이 여기서 Editor 배지로 이어진다.

슈퍼관리자로 조회하면 결과가 다르다 — 실제 멤버십 등록 없이도 모든 KB가 목록에 나타나고
Role 열에는 "Super Admin"이 표시된다. JWT의 `groups` claim으로 판정되는 값이라 Access
Management의 Members 표에는 나타나지 않는다.
