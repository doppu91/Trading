"""Upstox API wrapper — live + sandbox. Keys pulled from settings collection."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import httpx
from .db import get_db
from .config import INSTRUMENT_MAP

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
    has_key_secret = bool(s.get("api_key") and s.get("api_secret"))
    # Token-only setup is valid (read-only operations work with just access_token).
    if token:
        state = "connected"
    elif has_key_secret:
        state = "configured_no_token"
    else:
        state = "disconnected"
    return {
        "configured": has_key_secret or bool(token),
        "has_token": bool(token),
        "state": state,
        "token_only": bool(token) and not has_key_secret,
        "token_refreshed_at": refreshed,
        "sandbox": bool(s.get("sandbox", False)),
        "api_key_preview": (s.get("api_key", "")[:6] + "…") if s.get("api_key") else None,
    }


# ============ Live data helpers ============

async def _authed_client() -> tuple[httpx.AsyncClient, str] | None:
    s = await get_upstox_settings()
    token = s.get("access_token")
    if not token:
        return None
    base = _base_url(bool(s.get("sandbox", False)))
    return httpx.AsyncClient(base_url=base, headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }, timeout=10), base


async def get_funds() -> dict:
    auth = await _authed_client()
    if not auth:
        return {"error": "No Upstox access token. Connect Upstox first."}
    client, _ = auth
    async with client:
        r = await client.get("/user/get-funds-and-margin")
        return r.json()


def _symbol_to_key(symbol: str) -> str | None:
    info = INSTRUMENT_MAP.get(symbol)
    return info["token"] if info else None


async def get_quote(symbol: str) -> dict | None:
    """Fetch live LTP + OHLC from Upstox. Returns None if unauth or not found."""
    auth = await _authed_client()
    if not auth:
        return None
    client, _ = auth
    key = _symbol_to_key(symbol)
    if not key:
        return None
    try:
        async with client:
            # Use public-quote endpoint; works with most Upstox plans
            r = await client.get("/market-quote/ltp", params={"instrument_key": key})
            if r.status_code != 200:
                # Try fuller quote endpoint
                r = await client.get("/market-quote/quotes", params={"instrument_key": key})
                if r.status_code != 200:
                    return None
            data = r.json()
            if data.get("status") != "success":
                return None
            entry = next(iter(data.get("data", {}).values()), None)
            if not entry:
                return None
            price = entry.get("last_price") or entry.get("ltp") or entry.get("ohlc", {}).get("close")
            ohlc = entry.get("ohlc", {})
            prev_close = ohlc.get("close", price)
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
            return {
                "symbol": symbol,
                "price": round(float(price), 2),
                "prev_close": round(float(prev_close), 2),
                "change_pct": round(change_pct, 2),
                "volume": entry.get("volume", 0),
                "source": "upstox",
            }
    except Exception as e:
        logger.debug(f"upstox quote fail {symbol}: {e}")
        return None


async def get_historical(symbol: str, interval: str = "day",
                         to_date: str | None = None, from_date: str | None = None,
                         days_back: int = 365) -> list | None:
    """Fetch historical candles. `interval`:
       - 'day' | 'week' | 'month'     → v2 endpoint (no limits)
       - '5minute' | '30minute' | '1minute' → v3 endpoint, minutes/{n}
    Returns list of [ts, open, high, low, close, volume, oi] or None.
    """
    auth = await _authed_client()
    if not auth:
        return None
    client, _ = auth
    key = _symbol_to_key(symbol)
    if not key:
        return None
    from datetime import timedelta as _td
    if not to_date:
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not from_date:
        from_date = (datetime.now(timezone.utc) - _td(days=days_back)).strftime("%Y-%m-%d")

    # Route to v2 or v3 based on interval type
    if interval in ("day", "week", "month"):
        path = f"/historical-candle/{key}/{interval}/{to_date}/{from_date}"
        base_override = None
    else:
        # intraday: map to v3 minutes/{n}
        mapping = {"1minute": ("minutes", "1"), "5minute": ("minutes", "5"),
                   "30minute": ("minutes", "30"), "15minute": ("minutes", "15")}
        unit, n = mapping.get(interval, ("minutes", "30"))
        path = f"/historical-candle/{key}/{unit}/{n}/{to_date}/{from_date}"
        base_override = "https://api.upstox.com/v3"
    try:
        async with client:
            if base_override:
                # use full URL, bypassing v2 base_url
                r = await client.get(base_override + path)
            else:
                r = await client.get(path)
            if r.status_code != 200:
                return None
            data = r.json()
            if data.get("status") != "success":
                return None
            return data.get("data", {}).get("candles", [])
    except Exception as e:
        logger.debug(f"upstox hist fail {symbol}: {e}")
        return None
