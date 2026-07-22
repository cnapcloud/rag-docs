---
sidebar_position: 5
---

# 이미지 캡셔닝·OCR 폴백

문서 업로드 API는 그대로이고, 두 기능 모두 parse 단계에 자동으로 개입하는 opt-in
확장이다 — 별도로 호출하는 엔드포인트가 없다. 두 기능이 실제로 어떤 순서로 처리되고 왜
그렇게 나뉘는지는 [파서 확장 처리 흐름](../../concepts/ingestion-extensions.md)에서
다루고, 여기서는 설정 방법만 다룬다.

---

## 이미지 캡셔닝

문서 안에 박힌 이미지(PDF/DOCX/PPTX)와 이미지 파일 자체(`.png`/`.jpg`/`.jpeg`/`.gif`/
`.bmp`/`.webp`) 둘 다 대상이다.

```yaml
ingestion:
  image_captioning:
    enabled: true
    model: "qwen2.5vl:3b"      # provider.name에 맞는 모델 — ollama: qwen2.5vl:3b, openai: gpt-4o-mini
    temperature: 0.1
    max_images_per_doc: 20
    max_concurrent_tasks: 5
    default_language: ko
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `false` | opt-in. 꺼진 상태에서 독립 이미지 파일을 업로드하면 업로드 자체가 422로 거부된다 |
| `model` | `"qwen2.5vl:3b"` | 비전 모델 이름. KB별 오버라이드 불가(`overridable: false`) — 배포 타임 모델 pull/GPU 메모리 결정이라 KB마다 바꾸면 조용히 실패할 수 있다 |
| `temperature` | `0.1` | 낮게 고정 — 캡션 재현성 확보 목적 |
| `max_images_per_doc` | `20` | 문서당 캡셔닝할 최대 이미지 수(대용량 스캔 PDF의 지연 상한) |
| `max_concurrent_tasks` | `5` | 이미지별 VLM 호출 동시성 |
| `default_language` | `"ko"` | 문서 텍스트가 없어 언어 감지가 불가능할 때(독립 이미지 파일) 쓰는 캡션 언어(ISO 639-1) |

`model`을 제외한 나머지 필드는 [KB별 설정 오버라이드](../rag-api/kb.md#kb별-설정-오버라이드)로
KB마다 다르게 지정할 수 있다.

**Provider는 embedding과 공유한다** — `provider.name`(ollama/openai)에 따라
`provider.ollama_url` 또는 `provider.openai_api_key`를 그대로 재사용하고, `image_captioning.model`은
그 provider에 맞는 비전 모델 이름만 별도로 지정한다.

**언어 판정**은 두 경우가 다르다. PDF/DOCX/PPTX에 박힌 이미지는 같은 문서의 본문 텍스트
일부를 샘플링해 언어를 자동 감지하고, 감지에 실패하면 영어로 폴백한다. 독립 이미지
파일은 감지할 본문 텍스트가 없으므로 `default_language`를 그대로 쓴다.

## PDF OCR 폴백

```yaml
ingestion:
  pdf_ocr_fallback:
    enabled: true
    engine: rapidocr
    language: korean
    min_chars_per_page: 50
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `false` | opt-in |
| `engine` | `"rapidocr"` | 현재 유일한 값(onnxruntime 기반, PaddleOCR 모델을 ONNX로 변환해 재사용) |
| `language` | `"korean"` | RapidOCR `Rec.lang_type` 값 |
| `min_chars_per_page` | `50` | 문서 전체 페이지 평균 글자 수가 이 값 미만이면 스캔 문서로 판단해 OCR 경로로 전환 |

`enabled`와 페이지당 평균 글자 수 미달, **두 조건이 모두 참이어야** OCR이 호출된다 — 판단은
페이지 단위가 아니라 문서 전체 단위다(본문 텍스트와 스캔 페이지가 섞인 문서는 지원 범위
밖). 정상 텍스트 PDF에 실수로 켜져 있어도, 평균 글자 수가 충분하면 OCR은 발동하지 않는다.

첫 호출 시 RapidOCR 모델(PP-OCRv5 server-tier 검출 모델 + 언어별 mobile-tier 인식 모델,
약 84MB)을 내려받아 캐시한다 — 이후 호출은 캐시된 모델을 재사용한다.
