"""Upstox TOTP auto-login via Playwright headless chromium.

Performs the full OAuth dialog → mobile → TOTP → PIN → code capture flow,
then exchanges the code for an access token using the API key/secret saved
in the upstox settings doc.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import httpx
import pyotp
from playwright.async_api import async_playwright
from .upstox_client import get_upstox_settings, save_upstox_settings

logger = logging.getLogger(__name__)


async def auto_login() -> dict:
    """Headless TOTP login → returns dict with new access_token or error."""
    s = await get_upstox_settings()
    api_key = s.get("api_key")
    api_secret = s.get("api_secret")
    redirect_uri = s.get("redirect_uri", "https://127.0.0.1")
    mobile = s.get("mobile")
    pin = s.get("pin")
    totp_secret = s.get("totp_secret")

    missing = [k for k, v in {
        "api_key": api_key, "api_secret": api_secret,
        "mobile": mobile, "pin": pin, "totp_secret": totp_secret,
    }.items() if not v]
    if missing:
        return {"ok": False, "error": f"Missing credentials: {', '.join(missing)}"}

    auth_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    )

    code: dict[str, str | None] = {"value": None}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        def _on_request(req):
            if req.url.startswith(redirect_uri) and "code=" in req.url:
                qs = parse_qs(urlparse(req.url).query)
                code["value"] = qs.get("code", [None])[0]
        page.on("request", _on_request)

        try:
            await page.goto(auth_url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_selector("#mobileNum", timeout=15000)
            await page.fill("#mobileNum", mobile)
            await page.click("#getOtp")

            await page.wait_for_selector("#otpNum", timeout=15000)
            otp = pyotp.TOTP(totp_secret).now()
            await page.fill("#otpNum", otp)
            await page.click("#continueBtn")

            await page.wait_for_selector("#pinCode", timeout=15000)
            await page.fill("#pinCode", pin)
            await page.click("#pinContinueBtn")

            # Wait up to 15s for redirect callback to fire
            for _ in range(30):
                await page.wait_for_timeout(500)
                if code["value"]:
                    break
                if "code=" in (page.url or ""):
                    qs = parse_qs(urlparse(page.url).query)
                    code["value"] = qs.get("code", [None])[0]
                    break
        except Exception as e:
            logger.error(f"playwright login err: {e}")
            try:
                await page.screenshot(path="/tmp/upstox_login_err.png", full_page=True)
            except Exception:
                pass
            await browser.close()
            return {"ok": False, "error": f"Login flow failed: {type(e).__name__}: {e}"}
        finally:
            await browser.close()

    if not code["value"]:
        return {"ok": False, "error": "Auth code not captured. Check credentials."}

    # Exchange code for token
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code": code["value"],
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        data = r.json()

    if "access_token" not in data:
        return {"ok": False, "error": "Token exchange failed", "details": data}

    await save_upstox_settings({
        "access_token": data["access_token"],
        "token_refreshed_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "ok": True,
        "token_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "expires_in": data.get("expires_in"),
        "token_preview": data["access_token"][:20] + "…",
    }
