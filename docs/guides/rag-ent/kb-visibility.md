---
sidebar_position: 3
---

# 공개 KB(Visibility)

멤버십 없이도 모든 인증된 사용자에게 조회를 열어주는 `visibility` 필드의 REST API를
다룬다. 공개 KB가 [역할 계층](../../concepts/access-control.md#역할-계층)에서 정확히
어디까지 우회하는지는 [접근 제어](../../concepts/access-control.md)와
[리소스별 권한 강제](../../concepts/resource-authorization.md)에서 이미 다뤘고, 콘솔에서
켜고 끄는 화면은 [Knowledge Bases](../rag-admin/knowledge-bases.md)와
[Access Management](../rag-admin/access-management.md)에서 다룬다 — 여기서는 그 값을
직접 지정·조회하는 API와 실제 적용 범위의 경계를 다룬다.

---

## Visibility 지정

`private`(기본값) 또는 `public` 중 하나이며, 생성 시점에 바로 지정하거나 이후 전환할 수
있다.

```bash
# 생성 시점에 공개로 지정 — 생성 자체는 role 체크 없이 항상 허용
curl -X POST https://<api>/api/kb \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"kb_id": "kb-public-01", "kb_name": "공개 매뉴얼", "visibility": "public"}'

# 기존 KB 전환 — admin 이상 필요, 다른 KB 설정 변경과 동일한 문턱
curl -X PATCH https://<api>/api/kb/kb-01 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"visibility": "public"}'
```

`GET /api/kb`, `GET /api/kb/{kb_id}` 응답은 public 여부와 무관하게 모든 KB에 `visibility`
필드를 항상 포함한다.

## Public이 부여하는 범위

`public` KB는 `kb_membership` 행이 전혀 없는 사용자에게도 암묵적으로 `viewer` role을
부여한다 — 딱 거기까지다.

- **viewer까지만** — 조회는 누구나 가능하지만, 문서 업로드·삭제나 멤버 관리 같은 `editor`
  이상 작업은 여전히 명시적인 `kb_membership` 행을 요구한다. `visibility`는 상한을 올려주는
  게 아니라 viewer 문턱 하나만 낮춰준다.
- **`my_role` 표시** — membership 행이 없는 사용자가 public KB를 조회하면 `my_role`이
  `"viewer"`로 표시된다. 실제 멤버 등록이 아니라 `visibility=public`이 매 요청 계산해서
  붙이는 값이라, [Access Management](../rag-admin/access-management.md)의 Members 표에는
  나타나지 않는다.
- **검색에도 자동 포함** — `POST /api/search`가 접근 가능한 KB 목록을 계산할 때 public
  KB 전체를 무조건 합집합으로 더한다. `kb_ids`에 public KB를 넣기 위해 별도 멤버십을 만들
  필요가 없다.
- **`kb_authz_enabled=false`일 때는 의미 없음** — 이 플래그가 꺼져 있으면 이미 모든 인증된
  사용자가 모든 KB에 전체 접근하므로, `visibility` 값 자체가 아무 것도 바꾸지 않는다.

## 캐시

public KB id 목록은 사용자별이 아니라 전역 Redis 키(`authz:public_kbs`) 하나에 60초 TTL로
캐시된다. `PATCH`로 `visibility`를 바꾸면 이 키를 즉시 지운다 — 그래서 TTL이 남아있어도
바로 다음 조회부터 새 값이 반영되고, 별도로 60초를 기다릴 필요가 없다.
