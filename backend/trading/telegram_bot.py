"""Telegram bot wrapper — configure via API; sends/receives messages."""
from __future__ import annotations
import logging
import httpx
from datetime import datetime, timezone
from .db import get_db

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/{method}"


async def get_tg_settings() -> dict:
    db = get_db()
    s = await db.settings.find_one({"_id": "telegram"}, {"_id": 0}) or {}
    return s


async def save_tg_settings(data: dict) -> None:
    db = get_db()
    await db.settings.update_one({"_id": "telegram"}, {"$set": data}, upsert=True)


async def send_message(text: str) -> dict:
    s = await get_tg_settings()
    token = s.get("bot_token")
    chat_id = s.get("chat_id")
    if not token or not chat_id:
        return {"ok": False, "error": "Telegram not configured"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            TG_API.format(token=token, method="sendMessage"),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
        data = r.json()
    # log
    db = get_db()
    await db.telegram_log.insert_one({
        "ts": datetime.now(timezone.utc).isoformat(),
        "direction": "out",
        "text": text,
        "ok": data.get("ok", False),
    })
    return data


async def get_bot_info() -> dict:
    s = await get_tg_settings()
    token = s.get("bot_token")
    if not token:
        return {"configured": False, "error": "Telegram not configured"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(TG_API.format(token=token, method="getMe"))
        return r.json()


async def status() -> dict:
    s = await get_tg_settings()
    return {
        "configured": bool(s.get("bot_token") and s.get("chat_id")),
        "bot_token_preview": (s.get("bot_token", "")[:10] + "…") if s.get("bot_token") else None,
        "chat_id": s.get("chat_id"),
    }


async def recent_log(limit: int = 20) -> list[dict]:
    db = get_db()
    cursor = db.telegram_log.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
    return [x async for x in cursor]


# === Message formatters ===

def morning_brief(regime: dict, cues: dict, signals: list[dict], target_gross: float) -> str:
    reg = regime.get("regime", "Unknown")
    emoji = {"Bull": "🟢", "Sideways": "🟡", "Bear": "🔴"}.get(reg, "⚪")
    lines = [
        f"<b>📰 MORNING BRIEF — {datetime.now().strftime('%d %b %Y')}</b>",
        f"Regime: {emoji} <b>{reg}</b> (conf {regime.get('confidence', 0):.2f})",
        "",
        "<b>Global cues:</b>",
    ]
    for k, label in [("sp500", "S&P 500"), ("india_vix", "India VIX"), ("nifty", "Nifty"), ("crude", "Crude"), ("usdinr", "USDINR")]:
        q = cues.get(k)
        if q:
            lines.append(f"  • {label}: {q.get('price')} ({q.get('change_pct'):+.2f}%)")
    top = sorted(signals, key=lambda s: s.get("composite", 0), reverse=True)[:3]
    lines.append("")
    lines.append("<b>Top signals:</b>")
    for s in top:
        lines.append(f"  • {s['symbol']}: {s['composite']:.2f} → {s['action']}")
    lines.append("")
    lines.append(f"🎯 Target: ₹{target_gross:,.0f} gross → ₹4,000 net")
    return "\n".join(lines)


def eod_summary(summary: dict) -> str:
    n = summary.get("num_trades", 0)
    return (
        f"<b>📊 EOD SUMMARY</b>\n"
        f"Trades: {n}  |  Wins: {summary.get('wins',0)}  |  Losses: {summary.get('losses',0)}\n"
        f"Win rate: {summary.get('win_rate',0)}%\n\n"
        f"Gross P&L:  ₹{summary.get('gross_pnl',0):,.2f}\n"
        f"Charges:    -₹{summary.get('total_charges',0):,.2f}\n"
        f"<b>NET P&L:   ₹{summary.get('net_pnl',0):,.2f}</b>"
    )
