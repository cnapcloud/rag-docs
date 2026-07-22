---
sidebar_position: 4
---

# Documents

KB 안의 문서를 업로드하고, 상태를 추적하고, 재인덱싱·삭제하는 화면이다. 업로드로 직접 올린
파일과 커넥터가 가져온 문서가 모두 이 화면에서 함께 관리된다. REST API 기준 동작은
[문서 관리](../rag-api/documents.md)에서, 9가지 `status`와 전이 규칙은
[문서 상태 흐름](../../concepts/document-lifecycle.md)에서 다룬다.

## 목록·필터

![Documents 목록](/img/kb-admin/docs-list.png)

KB를 고른 뒤 Status/Type 드롭다운과 제목·ID 검색으로 좁힌다. Title/Chunks/Age 헤더로
정렬한다. 처리 중인 문서(`pending`/`running`)가 있으면 짧은 주기로 자동 새로고침되고,
없으면 `DOC_REFRESH_INTERVAL` 주기로 새로고침된다 — `DOC_POLL_ENABLED=false`면 자동
새로고침 자체가 꺼진다([Environment Variables](../../reference/environment-variables.md) 참고).

우측 상단 Upload로 파일을 올리고, Reindex All로 KB 전체를 재인덱싱한다.

## 업로드

Upload 모달은 드래그앤드롭 또는 파일 선택으로 여러 파일을 한 번에 올린다. 허용 확장자는
배포 모드에 따라 다르다.

<p align="center">
  <img src="/img/kb-admin/docs-upload.png" alt="문서 업로드" width="350" />
</p>

- **Core** — 문서류만: PDF/HWP/DOCX/XLSX/PPTX/TXT/HTML/MD/RST/EML/CSV.
- **Enterprise** — 위 문서류에 이미지(PNG/JPG/JPEG/GIF/BMP)까지 추가로 허용한다.

파일별 성공/실패가 배치 결과에 독립적으로 표시되므로, 하나가 실패해도 나머지 업로드는
그대로 진행된다.

## 선택 항목 일괄 작업·재인덱싱

행 앞 체크박스로 여러 문서를 선택하면 Reindex Selected / Delete Selected가 나타난다. 선택
항목 중 활성 상태(`uploading`/`pending`/`fetching`/`running`/`deleting`) 문서가 섞여 있으면
두 작업 모두 거부된다 — 진행 중인 파이프라인과 충돌하지 않기 위한 가드다. 두 버튼 모두
Editor 이상 역할에서만 쓸 수 있다.

Admin UI에서 실행하는 재인덱스(Reindex Selected/Reindex All/상세 패널의 Reindex)는 항상
`force=true`로 호출된다 — REST API가 지원하는 ETag 비교 스킵 최적화는 UI에서는 적용되지
않는다.

## 상세 패널

행을 클릭하면 우측에 ID/Title/KB/Status/Type/Chunks/Size/Model/Created/Updated가, 있는
경우에만 Source type/Source/Processing time/Duplicate of/Run ID/Error가 표시된다.

<p align="center">
  <img src="/img/kb-admin/docs-detail.png" alt="문서 상세 패널" width="300" />
</p>

문서 상태에 따라 나타나는 버튼이 다르다.

- **Reindex** — 안정 상태(`indexed`/`failed`/`outdated`)일 때만.
- **Recover** — `running` 상태가 30분 넘게 이어질 때만 나타나는 프런트엔드 판단 기준이다
  (백엔드 상태 자체에 이 임계값이 있는 것은 아니다). 클릭하면 문서를 `failed`로 되돌린 뒤
  강제 재인덱스한다.
- **Force Fail** — 안정 상태가 아닐 때(활성 상태 전반)만 나타난다.
- **Delete** — 안정 상태일 때만 나타난다. `outdated` 문서는 자동으로 hard delete(S3 원본까지
  삭제)로 처리되고, 그 외 상태는 soft delete(S3 원본 유지)로 처리된다 — 목록의 Delete
  Selected는 선택한 문서 상태와 무관하게 항상 soft delete다.
