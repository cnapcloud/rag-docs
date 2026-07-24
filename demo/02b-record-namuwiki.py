"""Standalone recording for the namu.wiki "고양이" source clip.

02-record.py's jane_step5_documents_source clicks through to this same page
from rag-admin and immediately closes the popup - the actual scroll-to-content
clip is recorded here instead, independently of the real rag-admin/Keycloak/
SMTP environment, so it can be re-taken quickly without re-running the full
two-account scenario. Splice this clip in after that popup-open cut during
editing (see 02-record.py:295-298).

Run:
    python 02b-record-namuwiki.py
"""

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

NAMUWIKI_CAT_URL = "https://namu.wiki/w/고양이"
RECORDING_DIR = Path(__file__).parent / "recordings"

# Chromium (headless or headed) never draws the OS mouse cursor, so a plain
# recording looks like elements are changing by themselves. This injects a
# small dot that tracks real mousemove events so cursor movement is visible
# in the video - mirrors 02-record.py's CURSOR_JS.
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
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""


def slow_scroll(page: Page, total_px: int = 1200, steps: int = 12, step_delay_ms: int = 250) -> None:
    # Scroll down gradually in small ticks instead of one big jump, so the
    # motion reads as a deliberate scroll on camera rather than a page snap.
    per_step = total_px / steps
    for _ in range(steps):
        page.mouse.wheel(0, per_step)
        page.wait_for_timeout(step_delay_ms)


def main() -> None:
    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=80)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RECORDING_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        try:
            page.goto(NAMUWIKI_CAT_URL)
            page.wait_for_load_state()

            # "최고령" 문구가 두 번째로 나오는 위치(실제 최고령 고양이 항목)까지 스크롤 -
            # 첫 번째 매치는 다른 문단이라 두 번째를 타겟팅한다. 외부 사이트라 마크업을
            # 통제할 수 없으므로, 두 번째 매치를 못 찾으면 고정 거리만 스크롤한다.
            try:
                target_text = page.get_by_text("최고령").nth(1)
                target_text.wait_for(state="visible", timeout=2000)
                box = target_text.bounding_box()
                viewport = page.viewport_size
                if box and viewport:
                    offset = box["y"] - viewport["height"] / 3
                    if offset > 0:
                        slow_scroll(page, total_px=int(offset))
            except Exception:
                print("[info] second '최고령' text not found, using fixed scroll")
                page.mouse.wheel(0, 1000)

            page.wait_for_timeout(2000)
        finally:
            context.close()
            browser.close()
    print(f"Recording saved under {RECORDING_DIR}")


if __name__ == "__main__":
    main()
