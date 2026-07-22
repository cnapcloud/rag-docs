---
sidebar_position: 6
---

# 표 구조 보존 파싱

기본 PDF 리더는 `page.get_text()`만 써서 표를 구조 없이 한 줄 텍스트로 뭉갠다 — 이 확장은
표를 별도 Document(마크다운 표)로 분리해 행/열/셀 구조를 보존한다. Vector PDF와 스캔
PDF가 표 위치를 찾는 방법 자체가 다르고 그만큼 처리 경로도 갈리는데, 그 흐름은
[파서 확장 처리 흐름](../../concepts/ingestion-extensions.md)에서 다루고 여기서는 설정
방법만 다룬다.

---

## 설정

```yaml
ingestion:
  parser_plugins:
    # 순서 중요 — 표 구조 보존 파싱이 이미지 캡셔닝/OCR 폴백 뒤에 와야 .pdf 리더 슬롯을 가져간다
    - "rag_ent.pipeline.plugins.image_ocr:register"
    - "rag_ent.pipeline.plugins.table_layout:register"

  table_layout:
    enabled: true
    scan_region_min_score: 0.5
    scan_region_fragment_merge_gap_pt: 20
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `false` | opt-in. 꺼져 있으면 이미지 캡셔닝/OCR 폴백 플러그인이 등록한 `.pdf` 리더로 그대로 위임되고, 표는 기존처럼 본문에 한 줄로 뭉개진다 |
| `scan_region_min_score` | `0.5` | 스캔 페이지 표 영역 검출(RapidLayout) 신뢰도 임계값 — 미달이면 표 후보에서 제외 |
| `scan_region_fragment_merge_gap_pt` | `20` | 같은 x범위를 공유하는 두 표 후보의 세로 간격(pt)이 이 값 이하면 내부 격자선이 끊겨 조각난 같은 표로 보고 하나로 합침 |

모든 필드는 [KB별 설정 오버라이드](../rag-api/kb.md#kb별-설정-오버라이드)로 KB마다 다르게
지정할 수 있다.

`parser_plugins` 순서는 필수다 — `register_parser()`가 last-writer-wins라, 표 구조 보존
파싱 플러그인이 이미지 캡셔닝/OCR 폴백 플러그인보다 **나중에** 로드돼야 `.pdf` 리더 슬롯을
가져간다. 순서를 반대로 두면 표 구조 보존 파싱이 조용히 무시된다(에러 없이 이전 리더가
계속 쓰임).

## 표 구조 인식

RapidAI의 RapidOCR·RapidTable·RapidLayout — onnxruntime 기반 경량 모델 3종을 조합해 무거운
범용 레이아웃 모델 대신 정확도와 리소스 사용량의 균형을 맞췄다. 별도 GPU나 대형 런타임 없이
CPU 한 대로도 실측으로 검증된 정확도를 낼 수 있어, 지금 수준의 요구에서는 이 조합이 가장
효율적인 선택이다.

### 인식 모델

- **표 구조 — 행/열/셀, 병합 헤더 포함**  
  RapidTable(SLANet-plus, ONNX). 경량 onnxruntime 모델이며, vector PDF에서 셀 단위 완전
  일치를 실측으로 확인했다.
- **스캔 페이지의 표 위치(bbox)**  
  RapidLayout(DOCLAYOUT_DOCSTRUCTBENCH, DocLayout-YOLO). 1024×1024 입력 + LetterBox
  전처리로 종횡비를 유지해, 이전에 쓰던 800×608 고정·종횡비 무시 모델에서 발생하던 표
  컬럼 손실을 해결했다.
- **스캔 페이지 본문·표 셀 텍스트**  
  RapidOCR(PP-OCRv5, 서버 검출 모델 + 언어별 모바일 인식 모델). 이미지 캡셔닝·OCR
  폴백과 동일한 onnxruntime 스택을 재사용한다.

RapidLayout은 여러 클래스(제목/본문/그림/표/캡션 등)를 함께 예측하는 모델이라, 그중
`"table"` 클래스만 걸러서 표 위치로 쓴다. 세 모델 모두 onnxruntime 기반이라 별도의 무거운
런타임(torch, GPU 드라이버) 없이 CPU에서 바로 추론한다.

### 처리 한계

- vector PDF에서 표 후보 영역이 서로 겹치면 같은 데이터가 중복 추출될 수 있다.
- 병합 헤더나 다단 헤더가 있는 복잡한 표는 구조가 완벽히 재현되지 않을 수 있다.
- 스캔 페이지에서 표 마스킹 경계 부근의 본문 텍스트가 드물게 인식되지 않을 수 있다.
- 테두리 없는 안내 박스처럼 표가 아닌 레이아웃이 표로 오탐지될 수 있다.
- 현재 추론은 CPU 전용이다 — 처리량이 실제 병목이 되면 GPU 추론으로 전환할 수 있다.

### 개선 계획

Docling·MinerU 같은 별도 레이아웃 분석 서비스를 private hosted service로 연계하는 옵션을
추가해, 문서 특성과 리소스 여건에 따라 사용자가 인식 방식을 직접 선택할 수 있는 범위를
넓혀갈 계획이다.

## PDF OCR 폴백과의 관계

`table_layout.enabled=true`인 상태에서도 스캔 문서 판단은
[PDF OCR 폴백](image-captioning-ocr-fallback.md)의 `pdf_ocr_fallback.enabled` +
`min_chars_per_page` 조건을 그대로 따른다 — 표 구조 보존 파싱이 스캔 문서에서도 동작하려면
`pdf_ocr_fallback.enabled`도 함께 켜야 한다. `pdf_ocr_fallback`이 꺼져 있으면 스캔 페이지는
OCR 판단 자체가 일어나지 않아 vector 경로로 처리되고, 실제 스캔 페이지에서는
`find_tables()`가 항상 0개를 반환하므로 표가 추출되지 않는다.
