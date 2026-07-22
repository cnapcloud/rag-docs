---
sidebar_position: 6
---

# Configuration

KB별 `ingestion`/`chunking`/`dedup` 설정 오버라이드를 조회·수정하는 화면이다. `embedding`/
`retrieval`처럼 KB 단위로 오버라이드할 수 없는 설정은 이 화면에 나타나지 않는다 — 전역
설정 자체는 `settings.yaml`에서만 바꾼다([Configuration 레퍼런스](../../reference/configuration.md)
참고). 전역값과 KB 오버라이드가 병합되는 방식, PUT/PATCH 저장 시맨틱, `overridable: false`로
막힌 필드 목록은 [KB별 설정 오버라이드](../rag-api/kb.md#kb별-설정-오버라이드)에서 이미
다루므로 여기서는 화면 조작 방법만 정리한다.

![Configuration 화면 — Dedup 탭](/img/kb-admin/configuration.png)

## KB 선택·탭

우측 상단 드롭다운으로 KB를 고른다. Ingestion/Chunking/Dedup 세 탭은 `settings.yaml`의
같은 이름 섹션과 대응하며, 탭 옆 숫자는 그 탭에서 오버라이드된 필드 개수다. 필드는 스키마의
`group`으로 다시 묶인다 — 탭 자신의 최상위 필드는 "General"로, Dedup 탭의 SimHash/MinHash/
Chunk Compare처럼 하위 구조가 있는 필드는 각각의 섹션 카드로 나뉜다. `overridable: false`인
필드(예: `dedup.simhash.ngram`)는 오버라이드가 애초에 불가능하므로 이 화면에 아예 나타나지
않는다.

## 필드 수정·저장

값을 바꾸면 즉시 저장되지 않고 로컬에만 반영된다. 바뀐 필드가 하나 이상이면 화면 하단에
저장 바가 나타나고, Save를 눌러야 바뀐 필드만 `PATCH .../settings/overrides`로 전송된다
(Discard로 되돌릴 수 있다). 전역값과 다르게 오버라이드된 필드는 입력창 아래 "(default: …)"
로 전역 기본값을 함께 보여주고, 옆의 되돌리기 아이콘으로 그 필드 하나만 오버라이드 해제
(전역값 복귀)할 수 있다.

필드 입력 방식은 스키마의 `type`을 따른다 — `bool`은 체크박스, `enum`은 드롭다운, `int`/
`float`은 스키마의 `min`/`max`를 반영한 숫자 입력, 그 외는 텍스트 입력이다.

저장·되돌리기는 이 KB의 owner 역할에서만 가능하다 — admin 역할은 KB 메타데이터 수정과
멤버 관리까지만 가능하고 설정 오버라이드는 쓸 수 없다([접근 제어](../../concepts/access-control.md#역할-계층)
참고). Core 배포(역할 개념이 없는 rag-api)에서는 이 제약이 적용되지 않는다.

## 필터·일괄 작업

- **Show overridden only** — 오버라이드된 필드만 남기고 나머지는 숨긴다.
- **Expand all / Collapse all** — 그룹 카드를 한 번에 펼치거나 접는다.
- **Reset all** — 이 KB의 모든 오버라이드를 지우고 전역값으로 되돌린다(owner만, 확인 다이얼로그 필요).
- **Download JSON** — 지금 KB에 적용 중인 유효 설정(`GET .../settings` 응답, 전역값과
  오버라이드를 병합한 결과)을 그대로 JSON 파일로 내려받는다. 오버라이드 값만 담긴 파일이
  아니다.
