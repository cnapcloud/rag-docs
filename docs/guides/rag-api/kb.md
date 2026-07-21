---
sidebar_position: 1
---

# KB 관리

KB 생성부터 삭제, 그리고 KB별 인제스트 설정 오버라이드까지 다룬다. KB가 왜 문서 격리·설정·
권한의 단위인지는 [아키텍처](../../concepts/architecture.md)에서 다룬다.

---

## Startup 시 KB 자동 생성

API 호출 없이 `settings.yaml`에 KB를 선언해두면 애플리케이션이 기동할 때 자동으로
생성된다 — 이미 존재하는 `kb_id`는 건너뛴다. 배포 자동화(GitOps 등)로 KB 목록을 코드로
관리할 때 쓴다.

```yaml
knowledge_bases:
  - id: "kb-hr"
    name: "인사팀 KB"
    tags: ["hr"]
  - id: "kb-legal"
    name: "법무팀 KB"
```

필드는 생성 API와 동일하다(`id`가 `kb_id`에 대응). 자동 생성이 실패해도(예: PostgreSQL
연결 불가) 애플리케이션 기동 자체는 막지 않고 경고 로그만 남긴다.

## KB 생성·조회·수정·삭제

```bash
# 목록
curl http://localhost:8000/api/kb

# 단건 조회 (없으면 404)
curl http://localhost:8000/api/kb/kb-99

# 생성 (kb_id 중복 시 409)
curl -X POST http://localhost:8000/api/kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id": "kb-99", "kb_name": "지식베이스 99", "tags": ["tag1"]}'

# 수정 — 전달한 필드만 갱신 (PATCH 의미론)
curl -X PATCH http://localhost:8000/api/kb/kb-99 \
  -H "Content-Type: application/json" \
  -d '{"kb_name": "새 이름"}'

# 삭제
curl -X DELETE http://localhost:8000/api/kb/kb-99
```

| 필드 | 필수 여부 | 설명 |
|------|-----------|------|
| `kb_id` | 필수 | KB 식별자, 중복 불가 |
| `kb_name` | 선택 | 표시 이름 |
| `description` | 선택 | 설명 |
| `tags` | 선택 | 태그 목록(수정 시 전체 교체) |

삭제는 Qdrant 컬렉션 → S3 오브젝트 → PostgreSQL 메타데이터 순으로 진행되며, 문서 레코드는
cascade 삭제된다.

## KB별 설정 오버라이드

인제스트 설정(`ingestion`/`chunking`/`dedup`)은 `settings.yaml`에 정의된 전역값 위에,
KB마다 다른 값을 오버라이드로 얹을 수 있다. 파이프라인은 문서를 처리할 때마다 전역값 위에
그 KB의 오버라이드를 병합한 유효 설정을 사용한다. 아래는 오버라이드가 없을 때 적용되는
전역 기본값이다.

```yaml
ingestion:
  max_file_size_mb: 10
  min_content_chars: 200
  html_extraction_policy: "lenient"
  parser_plugins: []

chunking:
  strategy: "recursive"
  chunk_size: 1024
  chunk_overlap: 128

dedup:
  enabled: true
  simhash:       { ngram: 3, num_bands: 4, simhash_bits: 64,
                   hamming_identical_threshold: 2, hamming_similar_threshold: 5 }
  minhash:       { jaccard_threshold: 0.65, title_fuzzy_threshold: 0.85 }
  chunk_compare: { chunk_match_threshold: 0.50, body_identical_threshold: 0.95,
                    body_similar_threshold: 0.75 }
```

| 섹션 | 대표 키 | 설명 |
|------|---------|------|
| `ingestion` | `max_file_size_mb`, `html_extraction_policy`, `parser_plugins` | 업로드·수집 제한, HTML 본문 추출 정책, 파서 확장 등록 목록 |
| `chunking` | `strategy`, `chunk_size`, `chunk_overlap` | 청킹 전략과 크기 |
| `dedup` | `simhash` / `minhash` / `chunk_compare` | 3단계 중복 감지 임계값 — 단계별 동작은 [검색·인제스트 흐름](../../concepts/data-flow.md#dedup-3단계-처리) 참고 |

전역값을 바꾸면 이후 인제스트되는 문서부터 적용된다 — 이미 색인된 문서는 재인덱싱해야 새
설정이 반영된다. 반영 방식은 배포 형태에 따라 다르다: k8s는 ConfigMap에 reloader
어노테이션이 있으면 저장만으로 자동 재기동되고, docker-compose는 컨테이너를 수동으로
재기동해야 한다.

`ingestion` / `chunking` / `dedup` 안에서도 아래 필드는 오버라이드에서 제외된다
(`overridable: false`) — 배포 타임에 고정되거나, 이미 저장된 기존 문서의 지문(fingerprint)과
계산 방식이 달라지면 안 되기 때문이다.

- `ingestion.parser_plugins`
- `dedup.simhash.ngram` / `num_bands` / `simhash_bits`
- `dedup.minhash.user_words_path`

### 오버라이드 가능한 필드 확인

프론트엔드가 필드 목록을 하드코딩하지 않고 동적으로 폼을 그릴 수 있도록, 전체 dot-key와
타입·허용값·기본값·`overridable` 여부를 반환한다.

```bash
curl http://localhost:8000/api/kb/kb-01/settings/schema
```

`ingestion.parser_plugins`, `dedup.simhash.ngram` 같은 필드는 `overridable: false`로
표시된다 — 배포 타임에 고정되거나 기존 저장된 지문(fingerprint)과의 호환성 때문에 KB별로
바꿀 수 없는 필드다. 이런 필드를 저장 API에 보내면 명시적으로 거부된다.

### 현재 유효 설정 확인

전역값과 KB 오버라이드를 병합한 결과다. `ingestion`/`chunking`/`dedup` 세 섹션만 반환하며
인프라 자격증명 등 다른 설정은 노출되지 않는다.

```bash
curl http://localhost:8000/api/kb/kb-01/settings
```

### 오버라이드 저장

전체 교체(PUT)와 부분 upsert(PATCH)는 동작이 다르다.

```bash
# 전체 교체 — body에 없는 기존 키는 전역값으로 리셋
curl -X PUT http://localhost:8000/api/kb/kb-01/settings/overrides \
  -H "Content-Type: application/json" \
  -d '{"overrides": {"chunking.chunk_size": 1024, "ingestion.max_file_size_mb": 100}}'

# 부분 upsert — 지정한 키만 갱신, 값이 null이면 그 키만 해제, 나머지 기존 키는 유지
curl -X PATCH http://localhost:8000/api/kb/kb-01/settings/overrides \
  -H "Content-Type: application/json" \
  -d '{"overrides": {"chunking.chunk_overlap": 128, "ingestion.max_file_size_mb": null}}'
```

두 API 모두 저장 전 순서대로 검증하며 위반 시 422를 반환한다.

1. dot-key가 `ingestion.` / `chunking.` / `dedup.` 접두사로 시작하는지.
2. 실제 존재하는 필드 경로이고 `overridable: false`가 아닌지.
3. 값이 필드의 타입·범위(`min`/`max`)·enum을 만족하는지.

### 오버라이드 삭제

```bash
curl -X DELETE http://localhost:8000/api/kb/kb-01/settings/overrides
```

이 KB의 모든 오버라이드를 지우고 전역 설정값으로 되돌린다.

---

Enterprise 배포에서는 위 API 전체에 KB 단위 역할이 추가로 걸리고 `visibility`(공개/비공개)
필드가 추가된다 — [access-management.md](../rag-admin/access-management.md)와
[access-control.md](../../concepts/access-control.md) 참고.
