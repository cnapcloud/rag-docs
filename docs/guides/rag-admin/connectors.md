---
sidebar_position: 3
---

# Connectors

웹 페이지, Confluence 스페이스, GitHub 저장소를 KB로 동기화하는 커넥터를 생성·조회·수정·
삭제하고 동기화 상태를 모니터링하는 화면이다. REST API 기준 동작과 소스 타입별 설정 필드는
[커넥터](../rag-api/connectors.md)에서, `status`/`sync_status` 전이 규칙은
[커넥터 상태 흐름](../../concepts/connector-lifecycle.md)에서 다룬다.

## 목록·필터·상세

![Connectors 목록](/img/kb-admin/connector-list.png)

KB/Type/Status 드롭다운과 이름·ID 검색으로 목록을 좁힌다. Name/Type/KB/Status/Last sync
헤더를 클릭하면 정렬 기준이 바뀐다. 목록에 `deleting` 상태인 커넥터가 있으면 삭제 완료
여부를 반영하도록 화면이 짧은 주기로 자동 새로고침된다.

행을 클릭하면 우측에 상세 패널이 열린다.
<p align="center">
<img src="/img/kb-admin/connector-detail.png" alt="웹 커넥터 상세 패널" width="300" />
</p>

- **Status** — 배지 옆 Pause/Resume 토글로 즉시 전환한다.
- **Sync status** — `idle`/`running`. 실행 중이면 Abort 버튼이 나타난다.
- **Last synced** (실행 중이면 대신 **Running since**), `status`가 `error`면 마지막 에러
  메시지.
- 문서 개수 요약(indexed/pending/running/failed/outdated/deleted)과 **View docs** 링크 — 이
  커넥터가 만든 문서 목록으로 이동한다.

![커넥터별 문서 목록](/img/kb-admin/connector-docs.png)

## 커넥터 생성

New Connector는 2단계 다이얼로그다.

1. **Name**, **Knowledge Base**, **Source Type**(Web/Confluence/GitHub)을 고른다.
2. 선택한 소스 타입에 맞는 설정 필드를 입력하고, 선택적으로 **Sync Schedule**(cron)을
   지정한다.

소스 타입별 설정 필드(웹의 Seed URLs/Depth/Authentication, Confluence의 Base URL/Space Key,
GitHub의 Owner/Repo/Paths 등)는 REST API의 `config`와 동일한 의미다 — 필드별 정의는
[커넥터](../rag-api/connectors.md)의 소스 타입별 절에서 다룬다. `auth_token_secret`, 웹
커넥터의 Header Value/Password 같은 시크릿 필드는 입력창에서 가려져 있다가 눈 아이콘으로
토글해 확인할 수 있고, 저장 시 서버에서 암호화된다.

Sync Schedule에 값을 입력하면 "Restart `dagster-rag-api` after saving to apply the new
schedule."라는 안내가 뜬다 — cron 표현식 자체를 바꾸거나 새로 등록할 때는 Dagster
워크스페이스 reload가 필요하기 때문이다. `schedule_enabled`(스케줄 on/off)만 바꿀 때는
해당하지 않는다.

## 수정·삭제

Edit 다이얼로그는 생성과 같은 설정 필드를 보여주지만 Connector ID·KB·Type은 읽기 전용이다
— 커넥터를 만든 뒤에는 소스 타입을 바꿀 수 없다.

<p align="center">
  <img src="/img/kb-admin/connector-web.png" alt="웹 커넥터 설정 화면" width="400" />
</p>

Delete는 진행 중인 sync가 있으면 서버가 거부한다(409). 삭제가 시작되면 status가 `deleting`
으로 바뀌고, 백그라운드에서 이 커넥터가 만든 문서의 Qdrant 청크·dedup 밴드를 지우고 문서
레코드를 소프트 삭제한다 — S3에 저장된 원본 파일은 지우지 않는다. 커넥터가 사라지면
재동기화할 소스가 없으므로 S3 사본이 유일하게 남는 기록이기 때문이다.
