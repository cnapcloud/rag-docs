---
sidebar_position: 3
---

# 파서 확장 처리 흐름

rag-ent-api(Enterprise 배포)가 제공하는 기능이다. rag-api의 `parse` 단계는 확장자별 리더와
후처리 함수를 등록하는 레지스트리를 갖고 있고, rag-ent-api는 이 레지스트리에 리더·후처리
함수를 꽂아 이미지 캡셔닝·PDF OCR 폴백·표 구조 보존 파싱 세 기능을 구현한다 — rag-api
소스 자체는 건드리지 않는다. [아키텍처](architecture.md)가 다룬 Pipeline Layer의 parse
단계가 내부적으로 어떻게 갈라지는지, 그리고 그 결과가 chunk 단계에서 어떻게 다뤄지는지를
다룬다. 설정 필드(`ingestion.image_captioning`/`pdf_ocr_fallback`/`table_layout`)를 KB별로
켜고 끄는 방법은 각 기능의 guide에서 다룬다.

---

## 확장 지점 — 파서 레지스트리

`register_parser(ext, reader)`는 확장자 하나에 리더 하나만 연결한다 — 같은 확장자를 다시
등록하면 나중 등록이 이전 등록을 덮어쓴다(last-writer-wins). `register_post_processor(fn)`은
여러 개를 등록할 수 있고, 리더의 결과를 대체하지 않고 추가로 덧붙인다.

이 때문에 `settings.yaml`의 `ingestion.parser_plugins` 순서가 의미를 갖는다 — 표 구조 보존
파싱 플러그인은 이미지 캡셔닝/OCR 폴백 플러그인 **뒤에** 와야 한다. 둘 다 `.pdf` 리더를
등록하는데, 나중에 로드되는 쪽이 `.pdf` 슬롯을 가져가기 때문이다. 후처리 함수는 등록 순서와
무관하게 전부 실행되고 결과가 합쳐진다.

## 처리 흐름

```
parse(doc_id, storage_key)
  |
  v
pick reader for this extension (parser registry, last-registered wins)
  |
  +-- .png / .jpg / ... --> VLMCaptionReader
  |     +-- image_captioning.enabled == false
  |     |     -> raises IngestValidationError (upload rejected, no fallback document)
  |     +-- image_captioning.enabled == true
  |           -> VLM caption -> 1 "image_caption" Document
  |
  +-- .pdf --> TableAwarePyMuPDFReader
        |
        |     scanned-page judgment (both must be true, checked once per document):
        |       pdf_ocr_fallback.enabled == true
        |       AND avg chars/page < pdf_ocr_fallback.min_chars_per_page
        |
        +-- table_layout.enabled == false
        |     -> delegate to PyMuPDFOCRFallbackReader
        |          |
        |          +-- judgment false (feature off, or plenty of text per page)
        |          |     -> plain vector text -> "text" Document per page
        |          |
        |          +-- judgment true (scanned)
        |                -> render page, RapidOCR transcribes whole page
        |                -> "ocr_text" Document per page
        |
        +-- table_layout.enabled == true (same judgment, then per page)
              |
              +-- judgment false -> vector page
              |     find_tables() locates table bboxes
              |       -> body text minus those bboxes -> "text" Document
              |       (table structure recognized later, see post-processor below)
              |
              +-- judgment true -> scanned page
                    render page -> RapidLayout detects table regions
                      -> crop each region -> RapidTable structure + built-in OCR
                           -> "table" Document per region
                      -> mask those same regions -> RapidOCR reads the rest
                           -> "ocr_text" Document (body only, tables excluded)
  |
  v
reader.load_data() returns the Documents built above
  |
  v
post-processors run (each appends more Documents, never replaces)
  |
  +-- extract_tables (.pdf, vector pages only)
  |     table_layout.enabled == false -> skip, returns no Documents
  |     table_layout.enabled == true
  |       -> find_tables() again (cheap, local) -> RapidTable structure,
  |          original digital text (not OCR) -> "table" Document per table
  |
  +-- caption_embedded_images (.pdf / .docx / .pptx)
        image_captioning.enabled == false -> skip, returns no Documents
        image_captioning.enabled == true
          -> skip entirely if any "ocr_text" Document is present
             (that page's scan was already transcribed as text)
          -> else: extract embedded images -> detect_language() -> VLM caption
             -> "image_caption" Document per embedded image
  |
  v
final Document list: text / ocr_text / table / image_caption
  |
  v
chunk()  -- unchanged rag-api step, see "content_type과 chunk 단계" below
```

세 옵트인 플래그(`image_captioning`/`pdf_ocr_fallback`/`table_layout`)는 모두 기본값이
`false`지만, 꺼져 있을 때의 동작은 파일 종류마다 다르다. PDF/DOCX/PPTX에 박혀 있는
이미지(`caption_embedded_images`)나 표(`extract_tables`, `table_layout`)는 옵트인이 꺼져
있으면 그냥 아무 것도 만들지 않고 넘어간다 — 문서의 나머지 텍스트는 정상적으로 색인된다.
반면 확장자 자체가 이미지인 파일(`.png`/`.jpg`/...)은 `image_captioning`이 꺼져 있으면
`VLMCaptionReader`가 `IngestValidationError`를 던진다 — 이미지 자체가 유일한 콘텐츠라 캡션을
못 만들면 대체할 텍스트가 없으므로, 업로드 자체가 거부된다.

## 왜 표 위치 탐지 방법이 페이지 종류마다 다른가

`find_tables()`는 PDF의 벡터 그리기 명령(선·사각형)을 보고 표 격자를 판단한다. 스캔
페이지는 래스터 이미지 한 장이라 벡터 요소가 없으므로, 표가 실제로 있어도 항상 0개를
반환한다 — "표 위치를 찾는" 단계 자체가 vector PDF와 다른 방법을 요구한다.

### Vector 페이지 — 독립적으로 두 번 탐지

리더와 post-processor가 서로의 존재를 모른 채 각자 파일을 다시 열어 `find_tables()`를
두 번 호출한다. 로컬 연산이라 표 하나당 수 ms 수준이라 두 번 불러도 비용이 무시할 만하다.

```
Vector page (has a text layer)
+------------------------------+
| Heading                      |
| Intro paragraph text...      |
| [ 1.2 | 3.4 | 5.6 ]          |   <- table bbox (find_tables())
| Closing paragraph text...    |
+------------------------------+

reader path (TableAwarePyMuPDFReader)      post-processor path (extract_tables)
find_tables() -> bbox                      find_tables() again -> same bbox
drop text blocks overlapping bbox          crop bbox, read PyMuPDF words
        |                                  (original digital text, not OCR)
        v                                          |
+------------------------------+                   v
| Heading                      |          +-------------------+
| Intro paragraph text...      |          | 1.2 | 3.4 | 5.6   |
| Closing paragraph text...    |          +-------------------+
+------------------------------+            content_type: "table"
  content_type: "text"
```

두 갈래 다 같은 bbox를 얻으므로 리더가 본문에서 뺀 영역과 post-processor가 표로 만든
영역이 항상 일치한다 — 본문·표 중복도, 누락도 생기지 않는다.

### 스캔 페이지 — 한 번 탐지해 크롭·마스킹 양쪽에 공유

위치 탐지(RapidLayout)와 본문 전사(RapidOCR)가 둘 다 무거운 모델 추론이라, vector
페이지처럼 두 번 돌릴 수 없다. 그래서 리더 하나가 위치 탐지·표 구조 인식·본문 마스킹을
전부 한 곳에서 처리하고, 탐지된 영역을 표 추출과 본문 마스킹 양쪽에 그대로 재사용한다.

```
Scanned page (raster image, zero vector content)
+------------------------------+
| [ rendered page image ]      |
| Heading                      |
| Intro paragraph text...      |
| [ 1.2 | 3.4 | 5.6 ]          |   <- table region (RapidLayout, detected once)
| Closing paragraph text...    |
+------------------------------+
        |
        v
detect_table_regions() -> one set of bboxes, reused by both paths below

table path: crop region                  body path: mask same region (fill white),
(unmasked render)                        re-render the page
-> RapidTable + built-in OCR             -> RapidOCR transcribes the rest
        |                                        |
        v                                        v
+-------------------+                   +------------------------------+
| 1.2 | 3.4 | 5.6   |                   | Heading                      |
+-------------------+                   | Intro paragraph text...      |
  content_type: "table"                 | [ masked ]                   |
                                        | Closing paragraph text...    |
                                        +------------------------------+
                                           content_type: "ocr_text"
```

탐지를 한 번만 하고 그 결과를 표 추출(크롭)과 본문 전사(마스킹) 양쪽이 공유하기 때문에,
표 내용이 `ocr_text`와 `table` 양쪽에 중복 등장하지 않는다 — 마스킹 없이 페이지 전체를
그대로 OCR했다면 표 안의 숫자·문자가 본문 텍스트에도 그대로 전사돼 검색 결과에 같은
내용이 두 번 잡혔을 것이다.

페이지마다 본문 Document(`text` 또는 `ocr_text`)는 표 유무·내용 유무와 무관하게 항상 정확히
1개 생성된다 — 내용이 비어도 스킵되지 않는다. 이 보장 덕분에 `caption_embedded_images`가
"이 문서에서 OCR이 발동했는가"를 `documents` 리스트에 `ocr_text`가 있는지만 보고 판별할 수
있다.

## content_type과 chunk 단계

| `content_type` | 생성 주체 | chunk 단계 처리 |
|-----------------|-----------|-------------------|
| `text` | 기본 리더 / `TableAwarePyMuPDFReader`(vector 페이지) | `SentenceSplitter`/`SemanticSplitter`로 분할 |
| `ocr_text` | `PyMuPDFOCRFallbackReader` 또는 스캔 페이지 경로 | 위와 동일하게 분할 |
| `table` | `extract_tables`(vector) 또는 스캔 페이지 경로 | 분할하지 않음 — 표 하나가 청크 하나 |
| `image_caption` | `VLMCaptionReader` 또는 `caption_embedded_images` | 분할하지 않음 — 캡션 하나가 청크 하나 |

`table`/`image_caption`은 rag-api의 chunk 단계가 이미 `ATOMIC_CONTENT_TYPES`로 구분해 두는
값이다 — 표 행 중간이나 캡션 문장 중간이 잘리면 검색 결과로서 의미가 없기 때문에, 일반
텍스트 분할기를 거치지 않고 Document 하나를 그대로 노드 하나로 만든다. rag-ent-api는 이
값을 새로 얹기만 하고, 분할 제외 로직 자체는 rag-api가 이미 갖고 있던 것을 그대로 따른다.
