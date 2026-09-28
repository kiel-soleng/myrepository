"""
sigma_session.py — reusable Playwright login helper for Sigma's browser UI.

Sigma has no REST write path for input-table rows (see data-seeding.md),
so seeding demo data requires a real interactive browser session. This
module is the login half of that: email/password + MFA-by-email, saving
a `storage_state` so later scripts (input_table_upload.py) can reuse the
session without logging in again.

Credentials are read from environment variables only -- never written to
a file or hardcoded. Set SIGMA_LOGIN_EMAIL / SIGMA_LOGIN_PASSWORD before
running.

MFA handling: this module supports two modes.
  - Manual relay (default): the script blocks, writes a screenshot, and
    polls a small marker file for the code -- an operator (in this repo's
    case, an agent relaying a chat message) writes the code to that file
    once they have it from the inbox.
  - Programmatic: pass `mfa_code_provider` (a zero-arg callable returning
    the code string) if a mail-search tool is wired up to fetch it
    automatically. Not implemented here since this session uses manual
    relay -- see reference/data-seeding.md's recipe note on why the
    "trigger email" and "read email" steps can't span two separate tool
    calls unless the browser process itself stays alive across both.
"""
import os
import time

from playwright.sync_api import sync_playwright

CHROMIUM_PATH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
PROXY_SERVER = os.environ.get("SIGMA_BROWSER_PROXY", "http://127.0.0.1:33303")
DEFAULT_LOGIN_URL_TEMPLATE = "https://app.sigmacomputing.com/{org}/login"


def _launch(headless=True):
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        executable_path=CHROMIUM_PATH,
        headless=headless,
        proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
    )
    return pw, browser


def login(org, storage_state_path, mfa_marker_dir, email=None, password=None,
          mfa_code_provider=None, headless=True, mfa_timeout_s=300):
    """
    Logs into https://app.sigmacomputing.com/{org}/login and saves the
    resulting storage_state (cookies + local storage) to
    storage_state_path for reuse by other Playwright scripts.

    mfa_marker_dir: directory to write mfa_screenshot.png +
      mfa_awaiting.flag into, and to poll mfa_code.txt from, when no
      mfa_code_provider is given (manual-relay mode).

    Returns True on success, raises RuntimeError otherwise.
    """
    email = email or os.environ.get("SIGMA_LOGIN_EMAIL")
    password = password or os.environ.get("SIGMA_LOGIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("SIGMA_LOGIN_EMAIL / SIGMA_LOGIN_PASSWORD not set")

    pw, browser = _launch(headless=headless)
    try:
        page = browser.new_page()
        page.goto(DEFAULT_LOGIN_URL_TEMPLATE.format(org=org), timeout=30000)
        page.wait_for_timeout(1500)

        page.fill('input[type="email"], input[name="email"]', email)
        page.fill('input[type="password"], input[name="password"]', password)
        page.click('button:has-text("Sign in")')
        page.wait_for_timeout(3000)

        if _looks_like_mfa_prompt(page):
            code = mfa_code_provider() if mfa_code_provider else _wait_for_manual_code(
                page, mfa_marker_dir, timeout_s=mfa_timeout_s
            )
            _submit_mfa_code(page, code)
            page.wait_for_timeout(3000)

        if _looks_like_login_form(page):
            page.screenshot(path=os.path.join(mfa_marker_dir, "login_failed.png"))
            raise RuntimeError(
                "Still on a login/verification form after submitting credentials "
                "(and MFA code, if prompted) -- see login_failed.png"
            )

        browser.contexts[0].storage_state(path=storage_state_path)
        return True
    finally:
        browser.close()
        pw.stop()


def _looks_like_mfa_prompt(page):
    text = page.content().lower()
    return any(k in text for k in ("verification code", "enter the code", "one-time code", "check your email"))


def _looks_like_login_form(page):
    text = page.content().lower()
    return "sign in to" in text and "email" in text and "password" in text


def _wait_for_manual_code(page, mfa_marker_dir, timeout_s=300):
    os.makedirs(mfa_marker_dir, exist_ok=True)
    screenshot_path = os.path.join(mfa_marker_dir, "mfa_screenshot.png")
    flag_path = os.path.join(mfa_marker_dir, "mfa_awaiting.flag")
    code_path = os.path.join(mfa_marker_dir, "mfa_code.txt")

    for stale in (flag_path, code_path):
        if os.path.exists(stale):
            os.remove(stale)

    page.screenshot(path=screenshot_path)
    with open(flag_path, "w") as f:
        f.write("awaiting MFA code\n")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(code_path):
            with open(code_path) as f:
                code = f.read().strip()
            os.remove(code_path)
            os.remove(flag_path)
            return code
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting {timeout_s}s for {code_path} to appear")


def _submit_mfa_code(page, code):
    selector_candidates = [
        'input[autocomplete="one-time-code"]',
        'input[name="code"]',
        'input[type="text"]',
    ]
    for sel in selector_candidates:
        if page.locator(sel).count() > 0:
            page.fill(sel, code)
            break
    else:
        raise RuntimeError("Could not find an MFA code input field")
    for label in ("Validate", "Verify", "Submit", "Continue", "Confirm"):
        loc = page.locator(f'button:has-text("{label}")')
        if loc.count() > 0:
            loc.first.click()
            return
    page.keyboard.press("Enter")
