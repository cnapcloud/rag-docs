"""Playwright recording script for the two-account RBAC verification demo.

Follows the cuts in 01-scenario.md (jane the admin, then john the invited
member) against a live rag-admin deployment (default target:
https://rag-admin.cnapcloud.com). This drives a REAL environment as TWO REAL
users in a single continuous recording — review every step before running,
especially jane's invite step, which sends an actual email via SMTP.

This scenario requires an Enterprise-mode deployment: Access Management and
the sidebar's Sign out button are both gated behind entMode (see rag-admin
src/components/layout/Sidebar.tsx) — a Core deployment has no way to sign out
from the UI, so the john-login half of this script cannot run against it.

Setup:
    pip install playwright
    playwright install chromium

Credentials come from environment variables ONLY. Never hardcode them here —
this file lives in a repo that may be shared with customers.

    export RAG_ADMIN_URL="https://rag-admin.cnapcloud.com"
    export RAG_ADMIN_JANE_USER="jane@cnapcloud.com"
    export RAG_ADMIN_JANE_PASSWORD="..."
    export RAG_ADMIN_JOHN_USER="john@cnapcloud.com"
    export RAG_ADMIN_JOHN_PASSWORD="..."

Run:
    python 02-record.py

Before running, walk through 01-scenario.md's "사전 준비사항" checklist (john's
IdP account must already exist, kb-01/02/03 must exist with no leftover kb-04
or john membership from a prior take, no other ingest running, etc.) and its
"재실행 시 정리" section afterwards.

John's upload step uses assets/ai_chat_소개.pdf (already in this repo).

Login is OIDC Authorization Code + PKCE (see CLAUDE.md access-control docs).
rag-admin has no local login form; it redirects to the IdP (Keycloak by
default). The selectors below (#username / #password / #kc-login) are
Keycloak's default theme — adjust if your IdP uses a custom theme.

Pacing: every action moves the (visible, injected) cursor to the target over
several animated steps before clicking. The default beat between actions is
1 second; steps the viewer actually needs to read (dashboard tiles, the
RBAC-filtered KB list, search results, run detail, sync confirmation) hold
longer — see the DEFAULT_WAIT_MS / LONG_WAIT_MS constants below.
"""

import os
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

def _load_env_local() -> None:
    """Load demo/.env.local (gitignored, never committed) for anything not
    already set in the shell environment - shell env still wins, so `export`
    before running always overrides the file."""
    env_file = Path(__file__).parent / ".env.local"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_local()

BASE_URL = os.environ["RAG_ADMIN_URL"]
JANE_USER = os.environ["RAG_ADMIN_JANE_USER"]
JANE_PASSWORD = os.environ["RAG_ADMIN_JANE_PASSWORD"]
JOHN_USER = os.environ["RAG_ADMIN_JOHN_USER"]
JOHN_PASSWORD = os.environ["RAG_ADMIN_JOHN_PASSWORD"]
DAGSTER_URL = os.environ.get("DAGSTER_URL", "https://dagster.cnapcloud.com")
MAILPIT_URL = os.environ.get("MAILPIT_URL", "https://mailpit.cnapcloud.com")

SAMPLE_DOC = Path(__file__).parent / "assets" / "ai_chat_소개.pdf"
RECORDING_DIR = Path(__file__).parent / "recordings"

NAMUWIKI_CONNECTOR_NAME = "나무위키"
CAT_SEARCH_TERM = "고양이"
CAT_QUERY = "최고령 고양이 찾아줘"
INVITE_TARGET_KB = "kb-02"
NEW_KB_ID = os.environ.get("RAG_ADMIN_NEW_KB_ID", "kb-04")
NEW_KB_LABEL = "test-kb"
NEW_KB_DESCRIPTION = f"Demo KB created during RBAC walkthrough ({NEW_KB_LABEL})"

# 기본 대기 - 액션 사이 호흡. 화면을 실제로 읽어야 하는 구간(대시보드 타일, RBAC로
# 걸러진 KB 리스트, 검색 결과, run 상세, sync 확인 등)은 LONG_WAIT_MS를 쓴다.
DEFAULT_WAIT_MS = 1000
LONG_WAIT_MS = 2500

# Chromium (headless or headed) never draws the OS mouse cursor, so a plain
# recording looks like elements are changing by themselves. This injects a
# small dot that tracks real mousemove events, on every document (including
# the IdP login page) so cursor movement is visible in the video.
CURSOR_JS = """
(() => {
  function init() {
    const el = document.createElement('div');
    el.id = '__demo_cursor';
    Object.assign(el.style, {
      position: 'fixed', top: '0px', left: '0px', width: '20px', height: '20px',
      borderRadius: '50%', background: 'rgba(255, 45, 45, 0.85)',
      border: '2px solid white', boxShadow: '0 0 8px rgba(0,0,0,0.6)',
      pointerEvents: 'none', zIndex: 2147483647, transform: 'translate(-50%, -50%)',
      transition: 'left 60ms linear, top 60ms linear',
    });
    document.documentElement.appendChild(el);
    window.addEventListener('mousemove', (e) => {
      el.style.left = e.clientX + 'px';
      el.style.top = e.clientY + 'px';
    }, true);
  }
  // init scripts run before the parser has created <html> yet, so
  // document.documentElement is still null here - defer to DOMContentLoaded
  // (this was previously failing silently: appendChild on null).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""


def move_and_click(page: Page, locator: Locator, steps: int = 20, settle_ms: int = 300) -> None:
    """Glide the visible cursor to the element, pause, then click - instead of
    Playwright's default instant jump-and-click, which is invisible on camera."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box is None:
        locator.click()
        return
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=steps)
    page.wait_for_timeout(settle_ms)
    page.mouse.down()
    page.wait_for_timeout(100)
    page.mouse.up()


def move_and_type(page: Page, locator: Locator, text: str, char_delay_ms: int = 90) -> None:
    move_and_click(page, locator)
    locator.press_sequentially(text, delay=char_delay_ms)


def move_to(page: Page, locator: Locator, steps: int = 20) -> None:
    """Glide the cursor onto an element without clicking - for pure hover beats
    ('마우스 포인터', no click) called out in the scenario."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box is None:
        return
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=steps)


def slow_scroll(page: Page, total_px: int = 1200, steps: int = 12, step_delay_ms: int = 250) -> None:
    """Scroll down gradually in small ticks instead of one big jump, so the
    motion reads as a deliberate scroll on camera rather than a page snap."""
    per_step = total_px / steps
    for _ in range(steps):
        page.mouse.wheel(0, per_step)
        page.wait_for_timeout(step_delay_ms)


def nav_to(page: Page, label: str) -> None:
    # Scoped to the sidebar <nav> - the dashboard also has quick-link cards
    # with overlapping accessible names (e.g. "Connectors Sync documents"),
    # which collide with a plain get_by_role("link", name=label) lookup.
    link = page.locator("nav").get_by_role("link", name=label, exact=True)
    move_and_click(page, link)


def select_kb(page: Page, kb_id: str) -> None:
    """Pick kb_id from a KB dropdown (Documents filter / Access Management KB
    select / Upload modal) - all render the same Radix combobox+option pair,
    and each page only has one KB combobox visible at a time."""
    trigger = page.get_by_role("combobox").first
    move_and_click(page, trigger)
    page.get_by_role("option", name=kb_id, exact=True).click()


def login(page: Page, username: str, password: str) -> None:
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    # Checking page.url right after networkidle races the client-side OIDC
    # redirect (AuthContext kicks it off async) - it can still read as
    # BASE_URL a moment before navigating away, which previously caused a
    # false "already authenticated" skip and left the page on the sidebar-less
    # "Redirecting to sign in..." screen. Wait for the login form itself
    # instead; if it never shows up, we really are already authenticated.
    try:
        page.wait_for_selector("#username", timeout=8000)
    except Exception:
        return

    move_and_type(page, page.locator("#username"), username)
    page.wait_for_timeout(250)
    move_and_type(page, page.locator("#password"), password)
    page.wait_for_timeout(250)
    move_and_click(page, page.locator("#kc-login"))
    page.wait_for_url(lambda url: "/auth/callback" not in url, timeout=15000)
    page.wait_for_timeout(800)


def logout(page: Page) -> None:
    # Sign out button only renders in entMode (Sidebar.tsx) - if this hangs
    # waiting for "Sign out", the target deployment is Core, not Enterprise.
    move_and_click(page, page.get_by_role("button", name="Sign out"))
    page.wait_for_selector("#username", timeout=15000)
    page.wait_for_timeout(DEFAULT_WAIT_MS)


# --- 시나리오 1: jane (관리자) --------------------------------------------


def jane_step2_dashboard(page: Page) -> None:
    # home에서 인프라 상태 타일에 마우스 포인터 (2초 대기)
    nav_to(page, "Home")
    page.wait_for_load_state("networkidle")
    move_to(page, page.get_by_text("Infrastructure", exact=True))
    page.wait_for_timeout(2000)


def jane_step3_kb_panel(page: Page) -> None:
    # KB로 이동, kb-01 로우 클릭 (1초 대기), right panel에 마우스 포인터
    nav_to(page, "Knowledge Bases")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    row = page.locator("tbody tr", has_text="kb-01")
    row.first.wait_for(state="visible", timeout=10000)
    move_and_click(page, row.first)
    page.wait_for_timeout(1000)

    panel = page.locator("aside, div").filter(has_text="Detail").last
    move_to(page, panel)
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def jane_step4_connector(page: Page) -> None:
    # Connectors로 이동 - 나무위키 선택, right panel edit -> cancel, sync 버튼
    nav_to(page, "Connectors")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    row = page.locator("tbody tr", has_text=NAMUWIKI_CONNECTOR_NAME)
    row.first.wait_for(state="visible", timeout=10000)
    name_cell = row.first.locator("td").first
    move_and_click(page, name_cell)
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    # 각 커넥터 행에도 아이콘 전용 "Edit" 버튼이 있어 이름이 겹친다 - detail
    # panel은 테이블 뒤에 렌더링되므로 DOM 순서상 마지막 매치를 잡는다.
    move_and_click(page, page.get_by_role("button", name="Edit", exact=True).last)
    page.wait_for_timeout(1000)
    move_to(page, page.get_by_role("dialog").get_by_role("heading"))
    page.wait_for_timeout(2000)
    move_and_click(page, page.get_by_role("button", name="Cancel"))
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    move_and_click(page, page.get_by_role("button", name="Sync", exact=True))
    # sync 시작 토스트 + sync status 변화를 화면에서 볼 수 있게 대기.
    page.wait_for_timeout(LONG_WAIT_MS)


def jane_step5_documents_source(page: Page) -> None:
    # Documents로 이동 - kb-01/02/03 한 번씩 선택 후 kb-01로, "고양이" 검색,
    # source 클릭 -> 새 탭에서 스크롤 -> rag-admin 탭으로 복귀
    nav_to(page, "Documents")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    for kb_id in ("kb-02", "kb-03", "kb-01"):
        select_kb(page, kb_id)
        page.wait_for_timeout(DEFAULT_WAIT_MS)

    move_and_type(page, page.get_by_placeholder("Search by title or ID…"), CAT_SEARCH_TERM)
    page.wait_for_timeout(1500)

    # get_by_role("cell", name=..., exact=True) doesn't work here - the title
    # cell also renders the doc ID as a second line underneath, so the cell's
    # accessible name is "고양이<id>", never an exact match. Target the title
    # text node itself instead (also avoids matching the "분류:고양이" row).
    title_cell = page.locator("tbody").get_by_text(CAT_SEARCH_TERM, exact=True)
    title_cell.first.wait_for(state="visible", timeout=10000)
    move_and_click(page, title_cell.first)
    page.wait_for_timeout(1500)

    # 클릭은 하지 않고 커서만 source 링크로 이동 - 실제 팝업 열림/스크롤 클립은
    # 02b-record-namuwiki.py에서 따로 녹화해서 편집 시 이어 붙인다.
    source_link = page.locator("aside").get_by_role("link", name=CAT_SEARCH_TERM)
    move_to(page, source_link)
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def jane_step6_query(page: Page) -> None:
    # Query Playground로 이동, "최고령 고양이 찾아줘" 질의
    nav_to(page, "Query Playground")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)
    move_and_type(page, page.get_by_placeholder("Query text…"), CAT_QUERY)
    page.wait_for_timeout(400)
    move_and_click(page, page.get_by_role("button", name="Search"))

    # 결과 카드가 렌더링될 때까지 대기한 뒤 첫 번째 카드까지 스크롤.
    # rag-admin src/routes/query.tsx에 카드 전용 data-testid가 없어, 카드 헤더의
    # "#1" 인덱스 배지(정확히 일치하는 텍스트)로 첫 카드를 특정한다 - 카드 공통
    # Tailwind 클래스(rounded-xl border bg-card)만으로는 다른 카드형 UI와 겹친다.
    first_card = page.locator("div.rounded-xl.border.bg-card.shadow-sm").filter(
        has=page.get_by_text("#1", exact=True)
    )
    first_card.first.wait_for(state="visible", timeout=15000)
    move_to(page, first_card.first)

    # 카드 안 "최고령" 문구 줄 바로 아래로 커서를 옮겨 그 줄을 가리키는 것처럼 연출.
    # 카드 본문이 <p> 하나에 다 들어있는 긴 텍스트 블록이라 get_by_text의 bounding_box는
    # 문단 전체를 반환한다(원하는 단어 줄이 아님) - Range API로 "최고령" 텍스트 자체의
    # 정확한 위치를 찾는다. 못 찾으면 방금 옮긴 카드 중앙 위치를 그대로 유지한다.
    try:
        rect = first_card.first.evaluate("""
            (card) => {
                const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const idx = node.textContent.indexOf('최고령');
                    if (idx !== -1) {
                        const range = document.createRange();
                        range.setStart(node, idx);
                        range.setEnd(node, idx + '최고령'.length);
                        const r = range.getBoundingClientRect();
                        return { x: r.x + r.width / 2, bottom: r.bottom };
                    }
                }
                return null;
            }
        """)
        if rect:
            page.mouse.move(rect["x"], rect["bottom"] + 8, steps=20)
            page.wait_for_timeout(1200)
    except Exception:
        print("[info] jane_step6_query: '최고령' text not found in first card, keeping card-center hover")


def jane_step7_invite(page: Page) -> None:
    # Access Management로 이동, kb-02 선택 -> invite에서 john@... 추가
    nav_to(page, "Access Management")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    select_kb(page, INVITE_TARGET_KB)
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    move_and_click(page, page.get_by_role("button", name="Invite", exact=True).first)
    page.wait_for_timeout(600)
    move_and_type(page, page.get_by_placeholder("user@example.com"), JOHN_USER)
    page.wait_for_timeout(DEFAULT_WAIT_MS)
    move_and_click(page, page.get_by_role("button", name="Look up"))
    # lookup 결과(신규/기존 멤버 여부, role 선택지)가 뜨는 걸 볼 시간.
    page.wait_for_timeout(LONG_WAIT_MS)

    dialog = page.get_by_role("dialog")
    move_and_click(page, dialog.get_by_role("button", name="Invite", exact=True))
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def jane_step7b_mailpit_check(page: Page) -> None:
    # 초대 메일이 실제로 수신됐는지 Mailpit에서 확인 - inbox 첫 번째 메일 클릭 후
    # rag-admin으로 복귀. rag-admin과 별개 앱이라 그냥 goto로 이동한다.
    # 메시지 행 셀렉터는 Mailpit v1.29.6 웹UI 기준(list-group 안 a.message) - 버전이
    # 바뀌면 촬영 전에 실제 화면에서 확인/조정할 것 (Keycloak 셀렉터와 동일한 주의사항).
    page.goto(MAILPIT_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    first_message = page.locator(".list-group a.message").first
    first_message.wait_for(state="visible", timeout=10000)
    move_and_click(page, first_message)
    page.wait_for_timeout(1500)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def jane_step8_signout(page: Page) -> None:
    logout(page)


# --- 시나리오 2: john (초대받은 사용자) ------------------------------------


def john_step2_kb_list(page: Page) -> None:
    # KB로 이동, 리스트 확인 (kb-02만 보이는지 - RBAC 격리 증명)
    nav_to(page, "Knowledge Bases")
    page.wait_for_load_state("networkidle")
    # 리스트가 kb-02만 보인다는 걸 화면에서 충분히 보여준다.
    page.wait_for_timeout(LONG_WAIT_MS)


def john_step3_create_kb(page: Page) -> None:
    # 다시 KB로 이동, kb-04 생성 - 직전 step2에서 이미 이 리스트를 충분히 보여줬으니
    # 여기서는 추가 대기 없이 바로 New KB 버튼을 누른다.
    nav_to(page, "Knowledge Bases")
    page.wait_for_load_state("networkidle")

    move_and_click(page, page.get_by_role("button", name="New KB"))
    page.wait_for_timeout(800)
    move_and_type(page, page.locator("#kb_id"), NEW_KB_ID)
    page.wait_for_timeout(600)
    move_and_type(page, page.locator("#kb_name"), NEW_KB_LABEL)
    page.wait_for_timeout(400)
    move_and_type(page, page.locator("#description"), NEW_KB_DESCRIPTION)
    page.wait_for_timeout(400)
    move_and_type(page, page.locator("#tags"), "ai, chat, llm")
    page.wait_for_timeout(600)
    move_and_click(page, page.get_by_role("button", name="Create"))
    page.wait_for_timeout(LONG_WAIT_MS)


def john_step4_upload(page: Page) -> None:
    # Documents에서 kb-04에 ai_chat_소개.pdf 업로드
    nav_to(page, "Documents")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(DEFAULT_WAIT_MS)
    select_kb(page, NEW_KB_ID)
    page.wait_for_timeout(DEFAULT_WAIT_MS)

    if not SAMPLE_DOC.exists():
        print(f"[skip] john_step4: sample doc not found at {SAMPLE_DOC}")
        page.wait_for_timeout(1500)
        return

    move_and_click(page, page.get_by_role("button", name="Upload"))
    page.wait_for_timeout(1000)
    page.locator('input[type="file"]').set_input_files(str(SAMPLE_DOC))
    page.wait_for_timeout(2000)
    move_and_click(page, page.get_by_role("button", name="Upload", exact=True))
    # phase goes idle -> uploading -> done/error; only "Close" appears once
    # settled. Leaving the dialog open blocks the sidebar nav (Radix marks the
    # rest of the page aria-hidden while a dialog is open), so wait for it.
    close_button = page.get_by_role("button", name="Close").first
    close_button.wait_for(state="visible", timeout=60000)
    page.wait_for_timeout(2000)
    move_and_click(page, close_button)
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def john_step5_wait_running(page: Page) -> None:
    # ai_chat_소개.pdf 상태가 "running"인 것을 확인
    row = page.locator("tbody tr", has_text="ai_chat")
    row.first.wait_for(state="visible", timeout=15000)
    try:
        row.first.get_by_text("running", exact=True).wait_for(state="visible", timeout=15000)
    except Exception:
        print("[info] john_step5: ai_chat_소개.pdf was already past 'running' by the time we checked")
    # 상태 배지를 화면에서 읽을 시간.
    page.wait_for_timeout(LONG_WAIT_MS)


def john_step6_dagster_run(page: Page) -> None:
    # Dagster로 이동, Runs에서 해당 run_id 클릭
    # rag-admin과 별개 앱(Dagster webserver)이라 그냥 goto로 이동한다 - 세션
    # 쿠키는 브라우저 컨텍스트에 남아있으므로 재로그인은 필요 없다.
    page.goto(f"{DAGSTER_URL}/runs", timeout=20000)
    # 실행 ID는 매번 달라 텍스트로 못 잡는다 - 표 첫 행의 /runs/<uuid> 링크를 잡는다.
    # "가장 최근 run = 방금 올린 ai_chat_소개.pdf"라는 전제이므로, 촬영 시점에 다른
    # 인제스트가 동시에 돌고 있지 않아야 한다 (01-scenario.md 사전 준비사항 4번).
    first_run_link = page.locator('a[href^="/runs/"]').first
    first_run_link.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1500)
    move_and_click(page, first_run_link)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)
    slow_scroll(page)
    page.wait_for_timeout(DEFAULT_WAIT_MS)


def main() -> None:
    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RECORDING_DIR),
            record_video_size={"width": 1920, "height": 1080},
            # rag-admin ingress currently serves the nginx-ingress default fallback
            # cert instead of the cnapcloud-com-tls secret (SAN=ingress.local) -
            # fix the ingress TLS binding before recording the real customer video,
            # a browser will show a security warning otherwise. Tracked as a known
            # gap, not a workaround to keep long-term.
            ignore_https_errors=True,
        )
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        try:
            login(page, JANE_USER, JANE_PASSWORD)
            jane_step2_dashboard(page)
            jane_step3_kb_panel(page)
            jane_step4_connector(page)
            jane_step5_documents_source(page)
            jane_step6_query(page)
            jane_step7_invite(page)
            jane_step7b_mailpit_check(page)
            jane_step8_signout(page)

            login(page, JOHN_USER, JOHN_PASSWORD)
            john_step2_kb_list(page)
            john_step3_create_kb(page)
            john_step4_upload(page)
            john_step5_wait_running(page)
            john_step6_dagster_run(page)
        finally:
            context.close()
            browser.close()
    print(f"Recording saved under {RECORDING_DIR}")


if __name__ == "__main__":
    main()
