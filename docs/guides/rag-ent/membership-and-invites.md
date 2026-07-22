---
sidebar_position: 2
---

# 멤버십·초대·소유권 관리

KB 멤버를 등록·조회·변경·제거하고, 아직 가입하지 않은 사용자를 이메일로 초대하고,
소유권을 이전하는 REST API를 다룬다. 역할 순위와 각 역할이 실제로 할 수 있는 작업 범위는
[접근 제어](../../concepts/access-control.md)에서 정의하며, 같은 기능의 콘솔 화면은
[Access Management](../rag-admin/access-management.md)에서 다룬다. 아래 API는 모두
`admin` 이상 역할(또는 super-admin)을 요구한다 — `kb_authz_enabled`가 꺼져 있어도 멤버십
데이터 자체는 그대로 관리할 수 있다. 역할 검사가 적용되지 않을 뿐이다([RBAC 활성화](sso-and-auth-setup.md#rbac-활성화)
참고).

---

## 멤버 등록과 이메일 초대

`POST /api/kb/{kb_id}/members` 하나가 두 가지 상황을 모두 처리한다 — 이메일 주인이 이미
가입돼 있으면 그 자리에서 역할을 부여하고, 아직 가입 전이면 초대를 만든다. 호출자가 둘 중
어느 쪽인지 미리 알 필요는 없다. 판정 순서는 캐시된 `user_profile` 조회 → Keycloak 사용자
조회([SSO·인증 설정의 Admin API용 클라이언트](sso-and-auth-setup.md#keycloak-클라이언트-구성))이며,
그 결과로 아래 둘 중 하나가 결정된다.

```bash
curl -X POST https://<api>/api/kb/kb-01/members \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "role": "editor"}'
```

| 상황 | 응답 | 부수 효과 |
|------|------|-----------|
| 이미 가입된 사용자 | `{"status": "granted", "user_id": ..., "role": ...}` | 즉시 `kb_membership` 등록, "역할 부여" 이메일 발송 |
| 미가입 이메일 | `{"status": "invited", "invite_id": ...}` | `kb_invite` 레코드 생성(대기), "초대" 이메일 발송 |

`role`은 `admin`/`editor`/`viewer` 중 하나만 지정할 수 있다 — `owner`는 이 API로 부여할 수
없고 [소유권 이전](#소유권-이전과-자동-승계) 절차를 거친다. 이미 멤버인 사용자를 다시
등록하거나, 같은 이메일에 대기 중인 초대가 이미 있으면 409를 반환한다.

이메일 발송은 fire-and-forget이다 — SMTP 발송이 실패해도 방금 만든 멤버십·초대 레코드는
그대로 유지된다([알림 메일 설정](#알림-메일-설정-smtp) 참고).

## 초대 조회·취소

```bash
# 멤버 목록 + 대기 중인 초대 목록을 함께 반환
curl https://<api>/api/kb/kb-01/members -H "Authorization: Bearer $TOKEN"

# 대기 중인 초대 취소
curl -X DELETE https://<api>/api/kb/kb-01/invites/inv-01 -H "Authorization: Bearer $TOKEN"
```

초대는 `authz.invite_expiry_days`(기본 7일)가 지나면 만료된다. 만료·취소된 초대는 같은
이메일로 다시 초대할 수 있도록 대기 목록에서 빠진다.

## 로그인 시 자동 활성화

대기 중인 초대는 사용자가 직접 수락하는 절차 없이, 그 이메일로 처음 로그인하는 순간
자동으로 멤버십이 된다. `OIDCMiddleware`가 매 요청마다 호출하는 로그인 훅이 해당 이메일의
대기 초대를 모두 찾아 `kb_membership` 행으로 승격시키고 초대 상태를 `accepted`로 바꾼다.
초대 스캔은 요청마다 실행하지 않고 사용자별로 Redis에 5분 TTL로 결과를 캐싱해, 매 요청마다
`kb_invite` 테이블을 조회하지 않는다.

## 사용자 프로필 캐시

`user_profile` 테이블은 `user_id`별 이메일·표시 이름을 담은 로컬 캐시다 — 소스는 항상
Keycloak이고, 이 테이블은 그 값을 매번 Keycloak Admin API로 조회하지 않기 위한 부산물일
뿐 별도의 API나 화면을 갖는 도메인 모델이 아니다. 두 시점에 독립적으로 채워진다.

- **로그인 시** — 위 로그인 훅이 초대 활성화보다 먼저 호출자 자신의 프로필을 매번
  갱신한다(요청마다 실행되므로 요청 제한이 없다).
- **관리자 작업 시** — [멤버 등록과 이메일 초대](#멤버-등록과-이메일-초대)에서 캐시에
  없는 이메일을 Keycloak Admin API로 조회해 역할을 부여할 때, 그 결과를 함께 캐시에
  기록한다.

두 값이 다르면 캐시는 다음 로그인이나 다음 관리자 조회 전까지 갱신되지 않는다 — Keycloak에서
이메일·표시 이름을 바꿔도 즉시 반영되지 않는다.

멤버 목록(`GET /api/kb/{kb_id}/members`)의 `email`/`display_name` 필드가 이 캐시에서 채워지고,
초대 대상 이메일의 기가입 여부 판정도 Keycloak Admin API를 부르기 전에 먼저 이 캐시를 확인한다.
[사용자 디프로비저닝](#사용자-디프로비저닝) 시 해당 사용자의 캐시 행도 함께 삭제된다. 이
캐시를 직접 조회하는 공개 API는 없다 — `GET /api/users/lookup`은 캐시가 아니라 Keycloak Admin
API를 직접 조회하는 별개의 경로다.

## 역할 변경과 멤버 제거

```bash
# 역할 변경 — owner에는 적용 불가(403), owner는 소유권 이전으로만 바뀐다
curl -X PATCH https://<api>/api/kb/kb-01/members/user-42 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role": "admin"}'

# 멤버 제거
curl -X DELETE https://<api>/api/kb/kb-01/members/user-42 -H "Authorization: Bearer $TOKEN"
```

제거 권한은 대상과 호출자의 관계에 따라 갈린다.

- **본인 탈퇴** — 자신의 멤버십을 스스로 지우는 것은 역할과 무관하게 항상 허용된다.
- **다른 멤버 제거** — 호출자가 `admin` 이상이어야 한다.
- **owner 제거** — super-admin만 가능하다. 일반 admin은 owner를 제거할 수 없다.

owner가 제거되면 그 KB에서 가장 오래 admin으로 있던 멤버가 자동으로 owner로 승격된다.
승격 가능한 admin이 하나도 없으면 KB는 `frozen` 상태로 전환되고, [소유권 이전](#소유권-이전과-자동-승계)으로만
다시 활성화할 수 있다.

역할 변경·제거는 즉시 역할 캐시를 무효화한다 — [캐싱](../../concepts/access-control.md#캐싱)에서
설명하는 TTL과 무관하게 다음 요청부터 바로 반영된다.

## 소유권 이전과 자동 승계

```bash
curl -X POST https://<api>/api/kb/kb-01/transfer-owner \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"new_owner_user_id": "user-42"}'
```

호출자는 현재 owner(또는 super-admin)여야 한다. 기존 owner는 admin으로 강등되고 지정한
사용자가 새 owner가 된다.

`frozen` 상태 KB(owner 제거 후 승계 대상이 없어 자동 동결된 경우)에도 같은 API를 쓴다 —
owner가 없는 상태에서 super-admin이 호출하면 강등 없이 바로 새 owner를 등록하고 KB 상태를
`active`로 되돌린다. 별도의 "동결 해제" API는 없다.

## 사용자 디프로비저닝

콘솔 화면은 없고 API로만 제공되는 super-admin 전용 작업이다. 특정 사용자를 전체 KB에서
한 번에 제거한다 — 계정을 만든 개인정보 삭제 요청이나 퇴사 처리에 쓴다.

```bash
curl -X DELETE https://<api>/api/users/user-42 -H "Authorization: Bearer $TOKEN"
# 또는 user_id를 모를 때
curl -X DELETE "https://<api>/api/users?email=user@example.com" -H "Authorization: Bearer $TOKEN"
```

대상 사용자가 속한 모든 KB의 `kb_membership` 행과 캐시된 프로필을 지운다. owner였던 KB는
[역할 변경과 멤버 제거](#역할-변경과-멤버-제거)와 동일하게 자동 승계 또는 동결이 일어난다.
super-admin은 자기 자신을 디프로비저닝할 수 없다 — `is_super_admin`은 JWT의 `groups` claim에서
매 요청 계산되는 값이라 이 API로 지울 수 없는데, `kb_membership` 행만 잃고 되돌릴 방법이
없어지는 상황을 막기 위해서다.

## 알림 메일 설정 (SMTP)

역할 부여·초대 이메일 발송에만 쓰인다. 다른 Enterprise 기능은 SMTP에 의존하지 않는다.

```yaml
smtp:
  host: "<smtp 호스트>"
  port: 587
  username: "<계정>"          # 비우면 인증 없이 발송 (로컬 개발용 mailpit 등)
  password: "<비밀번호>"       # Secret으로 주입
  from_address: "noreply@<도메인>"
```

**운영 환경은 실제로 발송 가능한 SMTP 서버를 사용한다.** 평가 환경에서 흔히 쓰는 mailpit은
메일을 외부로 내보내지 않고 가두는 개발용 도구라, 그대로 운영에 쓰면 초대·역할 부여
메일이 사용자에게 도달하지 않는다.
