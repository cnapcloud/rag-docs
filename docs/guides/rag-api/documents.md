---
sidebar_position: 4
---

# 문서 관리

문서(document)는 KB 안에서 실제 콘텐츠를 담는 단위다. `POST /upload`로 직접 올린 파일
(`source_type: s3`)과 [커넥터](connectors.md)가 가져온 웹/Confluence/GitHub 콘텐츠
(`source_type: web`/`confluence`/`github`) 모두 같은 문서 레코드로 관리되며, 이후
파싱·청킹·임베딩도 동일한 [인제스트 흐름](../../concepts/data-flow.md#인제스트-흐름)을
거친다. `status`가 왜 9가지로 세분화되어 있고 활성 상태에서 특정 요청이 왜 409로 막히는지는
[문서 상태 흐름](../../concepts/document-lifecycle.md)에서 다룬다.

---

## 문서 업로드

업로드하기 전에 대상 KB(아래 예시의 `kb-01`)가 이미 존재하는지 먼저 확인하고, 없으면
생성한다 — 존재하지 않는 `kb_id`로 업로드를 요청하면 파일 전송 전에 404가 반환된다. KB
생성 방법은 [KB 생성·조회·수정·삭제](kb.md#kb-생성조회수정삭제) 참고.

```bash
# 단건 업로드
curl -X POST http://localhost:8000/api/kb/kb-01/docs/upload \
  -F "file=@./guide.pdf"

# 배치 업로드 — 항목별로 성공/실패가 독립적으로 결과에 담긴다
curl -X POST http://localhost:8000/api/kb/kb-01/docs/upload/batch \
  -F "files=@./guide.pdf" -F "files=@./notes.md"
```

문서 업로드는 PDF/Office/HWP 문서류와 코드/설정 파일을 포함해 확장자 40종 가까이
지원하며, 전체 목록은 [파서 레지스트리](../../concepts/data-flow.md#파서-레지스트리)
기준을 따른다. 지원하지 않는 확장자로 문서를 업로드 요청하면 422로 거부된다.

문서 업로드는 문서 row를 먼저 만들고(`status: uploading`) S3 전송이 끝나면 `pending`으로
바꿔 큐에 넣는 순서로 진행된다(row-first). 같은 KB에 같은 파일명을 다시 업로드하면 새
문서가 아니라 기존 문서의 재업로드로 취급된다 — 기존 문서가 활성 상태(`uploading`/
`pending`/`running`/`deleting`)면 409, 아니면 파일 내용과 `status`가 갱신되고 다시
인제스트된다.

## 문서 조회·목록

```bash
# KB 안의 문서 목록 — status/source_type/search 필터, sort_by/sort_order 정렬
curl "http://localhost:8000/api/kb/kb-01/docs?status=indexed&sort_by=updated_at&sort_order=desc"

# 전체 KB를 아우르는 문서 목록
curl "http://localhost:8000/api/docs?search=guide"

# 단건 상태 조회 — 문서 row 전체를 그대로 반환
curl http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/status

# KB 하나의 상태별 개수
curl http://localhost:8000/api/kb/kb-01/docs/status

# 전체 KB의 상태별 개수를 KB 단위로 묶어서 반환
curl http://localhost:8000/api/docs/status
```

목록 API는 `page`/`page_size`(최대 100)로 페이지네이션하며, `sort_by`는 `updated_at` /
`created_at` / `title` / `chunk_count` / `file_size` 중 하나를 받는다.

## 문서 다운로드

```bash
curl http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/download -OJ
```

S3에 저장된 원본 파일을 그대로 스트리밍한다 — 파싱·청킹을 거치기 전 원문을 그대로
받는 API다. `storage_key`가 없는 문서(예: 스테이징에 실패한 문서)는 404를 반환한다.

## 문서 삭제

```bash
# soft delete — Qdrant 청크만 제거, S3 원본은 유지
curl -X DELETE http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890

# hard delete — S3 원본까지 제거하고 문서 row 자체를 삭제
curl -X DELETE "http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890?force=true"
```

삭제도 업로드와 마찬가지로 대상 문서가 활성 상태면 409를 반환한다. 요청은 즉시 처리되지
않고 삭제 이벤트가 큐에 들어가 `deleting` 상태를 거친 뒤 완료된다 — 두 방식의 차이와 상태
전이는 [문서 상태 흐름](../../concepts/document-lifecycle.md#상태-전이)에 정리되어 있다.

## 재인덱싱

```bash
# KB 전체 재인덱스 — S3 ETag가 content_version과 다른 문서만 큐잉
curl -X POST http://localhost:8000/api/kb/kb-01/reindex

# 단일 문서 재인덱스
curl -X POST http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/reindex

# force=true — ETag 일치 여부와 무관하게 무조건 재큐잉
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/reindex?force=true"
```

`force` 없이 호출하면 S3에 저장된 파일의 ETag와 문서의 `content_version`을 비교해 변경이
없는 문서는 건너뛴다(`queued`/`skipped` 개수로 응답). KB 전체 재인덱스는 활성 상태이거나
`outdated`로 판정된 문서도 건너뛴다 — `outdated`는 이미 다른 문서로 대체된 구버전이므로
재인덱스 대상이 아니다.

## 강제 종료·복구

```bash
# uploading/pending/running/deleting 상태의 문서를 강제로 failed 처리
curl -X POST "http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/fail?reason=stuck"

# running 상태의 문서를 failed로 되돌리고 강제 재인덱스까지 한 번에 처리
curl -X POST http://localhost:8000/api/kb/kb-01/docs/12ab34cd56ef7890/recover
```

서버나 Dagster 코드 서버가 재시작되면 실행 중이던 작업은 사라져도 PostgreSQL의 `status`는
`running`/`uploading`/`deleting`으로 남아 이후 업로드·삭제·재인덱스 요청이 계속 409로
막힐 수 있다. `/fail`과 `/recover`는 이런 stuck 문서를 되돌리기 위한 API이며, 적용 대상
상태와 동작 방식이 서로 다르다 — 상세 표와 재시작 이후 복구 절차는
[문서 상태 흐름](../../concepts/document-lifecycle.md#강제-종료와-복구)에서 다룬다.
