---
sidebar_position: 1
title: RAG Platform 데모
sidebar_label: RAG Platform
---

# RAG Platform 데모

관리자(jane)와 초대받은 멤버(john) 두 시점으로 RAG Platform의 KB 접근 제어, 하이브리드 검색,
인제스트 파이프라인이 실제 rag-admin 화면에서 어떻게 동작하는지 보여준다.

<video controls width="100%" poster="/img/video/rag-demo-poster.jpg">
  <source src="/img/video/rag-demo.mp4" type="video/mp4" />
  브라우저가 비디오 태그를 지원하지 않는다 — [다운로드](/img/video/rag-demo.mp4)로 직접 확인한다.
</video>

## 시연 순서

### 1. 관리자(jane) 시점

- Home에서 인프라 상태를 한눈에 확인
- Knowledge Bases에서 KB 목록과 상세 정보 확인
- Connectors에서 나무위키 커넥터 설정 확인 및 수동 동기화 실행
- Documents에서 KB별 인제스트 문서를 필터링·검색하고 원본 소스까지 확인
- Query Playground에서 자연어 질의("최고령 고양이 찾아줘")로 하이브리드 검색 결과 확인
- Access Management에서 다른 KB(kb-02)에 john을 멤버로 초대 — 실제 초대 메일 발송까지 확인

### 2. 초대받은 멤버(john) 시점

- 로그인 직후 초대받은 KB(kb-02)만 보이는 것을 확인 — KB 단위 접근 제어 확인
- 새 KB(kb-04)를 만들고 Configuration에서 opt-in 인제스트 기능(이미지 캡셔닝/PDF OCR
  폴백/테이블 레이아웃 인식)을 KB 단위로 on/off
- 문서를 업로드해 `running` 상태로 인제스트되는 것과 Dagster에서 파이프라인 run이 잡히는
  것을 확인

기능 자체에 대한 자세한 설명은 [Features](../overview/features.md)를 참고한다.
