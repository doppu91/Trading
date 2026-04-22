"""Paper trade simulator — records simulated orders in MongoDB."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from .db import get_db
from .charges import calc_charges
from .market_data import get_live_quote

logger = logging.getLogger(__name__)

POSITIONS = "paper_positions"
TRADES = "paper_trades"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def open_paper_position(symbol: str, qty: int, entry: float, stop_loss: float, target: float, signal_score: float) -> dict:
    db = get_db()
    pos = {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "qty": qty,
        "entry_price": entry,
        "stop_loss": stop_loss,
        "target": target,
        "signal_score": signal_score,
        "opened_at": _now_iso(),
        "status": "OPEN",
        "action": "BUY",
    }
    await db[POSITIONS].insert_one({**pos})
    return pos


async def close_paper_position(position_id: str, exit_price: float | None = None, reason: str = "manual") -> dict | None:
    db = get_db()
    pos = await db[POSITIONS].find_one({"id": position_id, "status": "OPEN"}, {"_id": 0})
    if not pos:
        return None
    if exit_price is None:
        q = get_live_quote(pos["symbol"])
        exit_price = q["price"] if q else pos["entry_price"]
    qty = pos["qty"]
    buy = pos["entry_price"]
    sell = exit_price
    gross = (sell - buy) * qty
    charges = calc_charges(buy, sell, qty)
    net = gross - charges.total

    trade = {
        "id": str(uuid.uuid4()),
        "position_id": position_id,
        "symbol": pos["symbol"],
        "qty": qty,
        "entry_price": buy,
        "exit_price": sell,
        "gross_pnl": round(gross, 2),
        "charges": charges.to_dict(),
        "net_pnl": round(net, 2),
        "opened_at": pos["opened_at"],
        "closed_at": _now_iso(),
        "signal_score": pos.get("signal_score"),
        "reason": reason,
    }
    await db[TRADES].insert_one({**trade})
    await db[POSITIONS].update_one({"id": position_id}, {"$set": {"status": "CLOSED", "closed_at": trade["closed_at"], "exit_price": sell}})
    return trade


async def list_open_positions() -> list[dict]:
    db = get_db()
    cursor = db[POSITIONS].find({"status": "OPEN"}, {"_id": 0}).sort("opened_at", -1)
    out = []
    async for p in cursor:
        q = get_live_quote(p["symbol"])
        ltp = q["price"] if q else p["entry_price"]
        unrealized = (ltp - p["entry_price"]) * p["qty"]
        p["ltp"] = ltp
        p["unrealized_pnl"] = round(unrealized, 2)
        out.append(p)
    return out


async def list_trades(limit: int = 50, since_iso: str | None = None) -> list[dict]:
    db = get_db()
    q: dict = {}
    if since_iso:
        q["closed_at"] = {"$gte": since_iso}
    cursor = db[TRADES].find(q, {"_id": 0}).sort("closed_at", -1).limit(limit)
    return [t async for t in cursor]


async def today_summary() -> dict:
    """Aggregate today's trades (UTC date boundary — OK for demo)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trades = await list_trades(limit=500, since_iso=today)
    gross = sum(t["gross_pnl"] for t in trades)
    charges_total = sum(t["charges"]["total"] for t in trades)
    net = gross - charges_total
    wins = sum(1 for t in trades if t["net_pnl"] > 0)
    losses = sum(1 for t in trades if t["net_pnl"] < 0)
    return {
        "num_trades": len(trades),
        "gross_pnl": round(gross, 2),
        "total_charges": round(charges_total, 2),
        "net_pnl": round(net, 2),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0.0,
        "trades": trades,
    }


async def charges_breakdown_today() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trades = await list_trades(limit=500, since_iso=today)
    agg = {"brokerage": 0, "stt": 0, "exchange_txn": 0, "sebi": 0, "stamp": 0, "gst": 0, "total": 0}
    for t in trades:
        for k in agg:
            agg[k] += t["charges"].get(k, 0)
    return {k: round(v, 2) for k, v in agg.items()}
