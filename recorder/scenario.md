---
sidebar_position: 1
title: 데모 시나리오
---

# 데모 시나리오

jane(관리자)·john(초대받은 멤버) 두 실제 계정으로 로그인해 KB 격리·멤버십 초대
([Features](../overview/features.md) 참고)를 나레이션이 아니라 화면으로 직접 증명하는
제품 데모 영상의 촬영 스크립트다. 아래 시나리오를 `record.py`(`make record`)가 그대로
따라가며 자동 녹화한다.


---

## 사전 준비사항

| # | 확인 항목 | 이유 |
|---|-----------|------|
| 1 | john@cnapcloud.com 계정이 Keycloak(IdP)에 이미 존재 | 초대 후 자동 활성화되는 것은 KB 멤버십이며 IdP 계정 자체 생성이 아님 — 계정이 없으면 시나리오 2의 로그인 단계에서 막힌다 |
| 2 | john@cnapcloud.com이 실제 수신 확인 가능한 메일함인지 확인 | 시나리오 1의 7번(멤버 초대)은 실제 이메일 발송을 유발함 (scenario.md 촬영 메모의 opt-in 항목과 동일 이슈) |
| 3 | john 역할(초대받은 일반 멤버)에 KB 생성 권한이 있는지 확인 | 시나리오 2의 3번(kb-04 생성)이 그 권한으로 가능한 동작인지 사전 확인 필요 — 안 되면 해당 단계에서 실패 |
| 4 | 촬영 시점에 다른 인제스트가 동시에 돌고 있지 않은지 확인 | 시나리오 2의 6번(Dagster run 클릭)이 "가장 최근 run = 방금 올린 ai_chat_소개.pdf"라는 전제에 의존 (scenario.md 컷 3과 동일 주의사항) |
| 5 | kb-01/02/03에 이전 촬영에서 남은 데이터(kb-04, john 멤버십 등)가 없는지 확인 | 반복 촬영 시 리스트가 지저분해지거나 흐름이 어긋날 수 있음 — 아래 "재실행 시 정리" 참고 |

---

## 시나리오 1: jane (관리자)

1. jane@cnapcloud.com / password 로그인
2. Home으로 이동, "Infrastructure" 타일에 마우스 포인터 (2초 대기)
3. Knowledge Bases로 이동, kb-01 로우 클릭 (1초 대기), Detail 패널에 마우스 포인터
4. Connectors로 이동
   - 나무위키 커넥터 행 클릭 → Detail 패널의 Edit 클릭
   - 팝업 제목으로 마우스 포인터 이동 (2초 대기) → Cancel
   - Sync 버튼 클릭 (토스트/상태 변화 확인 대기)
5. Documents로 이동
   - kb-02 → kb-03 → kb-01 순서로 KB 필터 전환
   - "고양이" 검색 → 제목 "고양이" 행 클릭
   - Detail 패널의 source 링크로 마우스 포인터만 이동 (클릭하지 않음 — 이 링크를 눌러서
     열리는 나무위키 페이지 스크롤 클립은 이 스크립트에 없다. "나무위키 소스 클립" 절 참고)
6. Query Playground로 이동, "최고령 고양이 찾아줘" 질의 → Search
   - 첫 번째 결과 카드로 마우스 포인터 이동
   - 카드 본문 중 "최고령" 문구 바로 아래로 마우스 포인터 이동
7. Access Management로 이동, kb-02 선택 → Invite → john@cnapcloud.com 입력 → Look up
   → 결과 확인 후 Invite 확정 (실제 이메일 발송)
8. Mailpit(`https://mailpit.cnapcloud.com`)으로 이동, inbox 첫 번째 메일 클릭 (1.5초 대기)
   → rag-admin으로 복귀
9. Sign out

## 시나리오 2: john (초대받은 사용자)

1. john@cnapcloud.com / password 로그인
2. Knowledge Bases로 이동, 리스트 확인 (kb-02만 보이는지 — jane이 초대하지 않은 kb-01/03은
   제외되는지 확인)
3. 다시 Knowledge Bases로 이동, kb-04 생성 (New KB → kb_id/이름/설명/태그 입력 → Create)
4. Documents에서 kb-04 선택 후 ai_chat_소개.pdf 업로드
5. ai_chat_소개.pdf 상태가 "running"인 것 확인
6. Dagster(Runs)로 이동, 가장 최근 run 클릭 → 상세 화면 스크롤

---

## 나무위키 소스 클립 (별도 스크립트)

시나리오 1의 5번에서 source 링크는 커서만 이동하고 클릭하지 않는다 — 링크를 눌렀을 때 실제로
열리는 `https://namu.wiki/w/고양이` 페이지에서 "최고령" 문구까지 스크롤하는 클립은
`record-namuwiki.py`가 독립적으로 녹화한다 (`make record-namuwiki`). rag-admin
로그인/실제 환경 없이 namu.wiki URL로 바로 이동해서 찍기 때문에, 이 컷만 다시 찍고 싶을 때
전체 시나리오를 재실행할 필요가 없다. 편집 시 시나리오 1-5번의 "source 링크로 마우스 포인터
이동" 컷 뒤에 이 클립을 이어 붙인다.

---

## 재실행 시 정리 (cleanup)

다음 촬영을 위해 이번 실행에서 생성된 데이터를 원상 복구한다. 순서대로 진행.

| # | 정리 대상 | 방법 |
|---|-----------|------|
| 1 | kb-04 (john이 생성한 KB) | KB 삭제 — 하위 문서(ai_chat_소개.pdf)가 cascade로 함께 삭제되는지 확인, 안 되면 문서 먼저 삭제 후 KB 삭제 |
| 2 | john의 kb-02 멤버십 | Access Management에서 john 제거 — 다음 실행에서 "초대 → 첫 로그인 시 활성화" 흐름을 처음부터 다시 보여주려면 필수 |
| 3 | 초대 재발송 여부 | 이미 멤버십이 남은 상태에서 시나리오 1의 7번을 재실행하면 초대 버튼이 재발송/에러 등 다른 동작을 할 수 있음 — 위 2번을 먼저 끝낸 뒤에만 재실행 |
| 4 | Dagster run 이력 | 정리 불필요 — 과거 run은 남아 있어도 무방하나, 촬영 시 "가장 최근 run"이 이번에 올린 ai_chat_소개.pdf인지는 매번 재확인 |

