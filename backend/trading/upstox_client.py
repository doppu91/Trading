"""Upstox API wrapper — live + sandbox. Keys pulled from settings collection."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import httpx
from .db import get_db

logger = logging.getLogger(__name__)

LIVE_BASE = "https://api.upstox.com/v2"
SANDBOX_BASE = "https://api-sandbox.upstox.com/v2"


async def get_upstox_settings() -> dict:
    db = get_db()
    s = await db.settings.find_one({"_id": "upstox"}, {"_id": 0}) or {}
    return s


async def save_upstox_settings(data: dict) -> None:
    db = get_db()
    await db.settings.update_one({"_id": "upstox"}, {"$set": data}, upsert=True)


def _base_url(sandbox: bool) -> str:
    return SANDBOX_BASE if sandbox else LIVE_BASE


async def get_auth_url() -> str | None:
    s = await get_upstox_settings()
    api_key = s.get("api_key")
    redirect_uri = s.get("redirect_uri", "https://127.0.0.1")
    if not api_key:
        return None
    return (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    )


async def exchange_code_for_token(code: str) -> dict:
    s = await get_upstox_settings()
    api_key = s.get("api_key")
    api_secret = s.get("api_secret")
    redirect_uri = s.get("redirect_uri", "https://127.0.0.1")
    if not api_key or not api_secret:
        return {"error": "Upstox API key/secret not configured"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code": code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        data = r.json()
        if "access_token" in data:
            await save_upstox_settings({
                "access_token": data["access_token"],
                "token_refreshed_at": datetime.now(timezone.utc).isoformat(),
            })
        return data


async def get_status() -> dict:
    s = await get_upstox_settings()
    token = s.get("access_token")
    refreshed = s.get("token_refreshed_at")
    configured = bool(s.get("api_key") and s.get("api_secret"))
    state = "disconnected"
    if configured and token:
        state = "connected"
    elif configured:
        state = "configured_no_token"
    return {
        "configured": configured,
        "has_token": bool(token),
        "state": state,
        "token_refreshed_at": refreshed,
        "sandbox": bool(s.get("sandbox", True)),
        "api_key_preview": (s.get("api_key", "")[:6] + "…") if s.get("api_key") else None,
    }


async def get_funds() -> dict:
    s = await get_upstox_settings()
    token = s.get("access_token")
    if not token:
        return {"error": "No Upstox access token. Connect Upstox first."}
    base = _base_url(bool(s.get("sandbox", True)))
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{base}/user/get-funds-and-margin",
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        )
        return r.json()
