"""Upstox Regime-Adaptive Trading System — FastAPI backend."""
from __future__ import annotations
import os
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, APIRouter, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from trading import config as tconfig
from trading import regime as tregime
from trading import signals as tsignals
from trading import market_data as tmarket
from trading import paper_trader as tpaper
from trading import risk as trisk
from trading import backtest as tbacktest
from trading import upstox_client as tupstox
from trading import telegram_bot as ttelegram
from trading import scheduler as tscheduler
from trading.db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Upstox Regime-Adaptive Trading System")
api = APIRouter(prefix="/api")


# ================= Models =================
class PaperTradeRequest(BaseModel):
    symbol: str
    quantity: Optional[int] = None  # if None, auto-size


class UpstoxSettingsBody(BaseModel):
    api_key: str
    api_secret: str
    redirect_uri: Optional[str] = "https://127.0.0.1"
    totp_secret: Optional[str] = ""
    sandbox: Optional[bool] = True


class UpstoxTokenBody(BaseModel):
    code: Optional[str] = None
    access_token: Optional[str] = None


class TelegramSettingsBody(BaseModel):
    bot_token: str
    chat_id: str


class SettingsBody(BaseModel):
    paper_mode: Optional[bool] = None
    capital: Optional[float] = None
    max_daily_loss: Optional[float] = None
    target_gross: Optional[float] = None
    signal_threshold: Optional[float] = None


class BacktestRequest(BaseModel):
    period: Optional[str] = "2y"


# ================= Root =================
@api.get("/")
async def root():
    return {"service": "Upstox Regime-Adaptive Trading", "version": "1.0.0", "time": datetime.now(timezone.utc).isoformat()}


# ================= System status =================
@api.get("/status")
async def system_status():
    db = get_db()
    s = await db.settings.find_one({"_id": "system"}, {"_id": 0}) or {}
    paper = s.get("paper_mode", tconfig.PAPER_MODE)
    up = await tupstox.get_status()
    tg = await ttelegram.status()
    summary = await tpaper.today_summary()
    now = datetime.now(timezone.utc)
    return {
        "paper_mode": bool(paper),
        "capital": s.get("capital", tconfig.CAPITAL),
        "max_daily_loss": s.get("max_daily_loss", tconfig.MAX_DAILY_LOSS),
        "target_gross": s.get("target_gross", tconfig.TARGET_GROSS_DAILY),
        "target_net": tconfig.TARGET_NET_DAILY,
        "signal_threshold": s.get("signal_threshold", tconfig.SIGNAL_THRESHOLD),
        "upstox": up,
        "telegram": tg,
        "today": {
            "gross_pnl": summary["gross_pnl"],
            "total_charges": summary["total_charges"],
            "net_pnl": summary["net_pnl"],
            "num_trades": summary["num_trades"],
            "wins": summary["wins"],
            "losses": summary["losses"],
        },
        "server_time": now.isoformat(),
    }


# ================= Settings =================
@api.get("/settings")
async def get_settings():
    db = get_db()
    s = await db.settings.find_one({"_id": "system"}, {"_id": 0}) or {}
    return {
        "paper_mode": s.get("paper_mode", tconfig.PAPER_MODE),
        "capital": s.get("capital", tconfig.CAPITAL),
        "max_daily_loss": s.get("max_daily_loss", tconfig.MAX_DAILY_LOSS),
        "target_gross": s.get("target_gross", tconfig.TARGET_GROSS_DAILY),
        "signal_threshold": s.get("signal_threshold", tconfig.SIGNAL_THRESHOLD),
        "max_positions": tconfig.MAX_POSITIONS,
        "risk_per_trade_pct": tconfig.RISK_PER_TRADE_PCT,
        "watchlist": tconfig.WATCHLIST,
        "weights": tconfig.WEIGHTS,
    }


@api.put("/settings")
async def update_settings(body: SettingsBody):
    db = get_db()
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if update:
        await db.settings.update_one({"_id": "system"}, {"$set": update}, upsert=True)
    return {"ok": True, "updated": update}


# ================= Regime =================
@api.get("/regime")
async def regime_now():
    return tregime.get_current_regime()


@api.get("/regime/timeline")
async def regime_timeline(days: int = 90):
    return {"timeline": tregime.get_regime_timeline(days=days)}


# ================= Morning brief =================
@api.get("/morning-brief")
async def morning_brief():
    reg = tregime.get_current_regime()
    await tmarket.prime_upstox_quotes(tconfig.WATCHLIST)
    cues = tmarket.get_global_cues()
    sigs = [tsignals.get_signal_for_symbol(s, cues) for s in tconfig.WATCHLIST]
    sigs_sorted = sorted(sigs, key=lambda x: x.get("composite", 0), reverse=True)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regime": reg,
        "global_cues": cues,
        "top_signals": sigs_sorted[:5],
        "watchlist_count": len(tconfig.WATCHLIST),
        "target_gross": tconfig.TARGET_GROSS_DAILY,
        "target_net": tconfig.TARGET_NET_DAILY,
    }


# ================= EOD summary =================
@api.get("/eod-summary")
async def eod():
    return await tpaper.today_summary()


# ================= Signals =================
@api.get("/signals")
async def all_signals():
    await tmarket.prime_upstox_quotes(tconfig.WATCHLIST)
    cues = tmarket.get_global_cues()
    results = [tsignals.get_signal_for_symbol(s, cues) for s in tconfig.WATCHLIST]
    return {"signals": results, "threshold": tconfig.SIGNAL_THRESHOLD}


# ================= Positions =================
@api.get("/positions")
async def positions():
    # Warm cache so LTPs are real.
    await tmarket.prime_upstox_quotes(tconfig.WATCHLIST)
    return {"positions": await tpaper.list_open_positions()}


# ================= Trades =================
@api.get("/trades")
async def trades(limit: int = 100):
    return {"trades": await tpaper.list_trades(limit=limit)}


# ================= Charges =================
@api.get("/charges/today")
async def charges_today():
    return await tpaper.charges_breakdown_today()


# ================= Risk =================
@api.get("/risk")
async def risk_monitor():
    db = get_db()
    s = await db.settings.find_one({"_id": "system"}, {"_id": 0}) or {}
    summary = await tpaper.today_summary()
    positions = await tpaper.list_open_positions()
    vix = (tmarket.get_global_cues().get("india_vix", {}) or {}).get("price", 0)
    reg = tregime.get_current_regime()
    max_loss = s.get("max_daily_loss", tconfig.MAX_DAILY_LOSS)
    capital = s.get("capital", tconfig.CAPITAL)
    loss_used = abs(min(0, summary["net_pnl"]))
    allowed, reason = tsignals.check_hard_gates(
        regime=reg.get("regime", "Unknown"),
        vix=vix or 0,
        daily_pnl=summary["net_pnl"],
        open_positions=len(positions),
        max_daily_loss=max_loss,
        max_positions=tconfig.MAX_POSITIONS,
    )
    return {
        "capital": capital,
        "daily_loss_cap": max_loss,
        "loss_used": round(loss_used, 2),
        "loss_used_pct": round((loss_used / max_loss * 100) if max_loss else 0, 1),
        "open_positions": len(positions),
        "max_positions": tconfig.MAX_POSITIONS,
        "vix": vix,
        "vix_cap": tconfig.INDIA_VIX_MAX,
        "regime": reg.get("regime"),
        "trades_allowed": allowed,
        "block_reason": None if allowed else reason,
    }


# ================= Paper trading =================
@api.post("/paper/open")
async def paper_open(body: PaperTradeRequest):
    await tmarket.prime_upstox_quotes([body.symbol])
    sig = tsignals.get_signal_for_symbol(body.symbol)
    if not sig.get("price"):
        raise HTTPException(status_code=400, detail="No live price for symbol")
    # rough ATR approximation via 14-day range
    df = tmarket.get_historical(body.symbol, period="1mo", interval="1d")
    if df.empty:
        atr = sig["price"] * 0.01
    else:
        tr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
        atr = float(tr) if tr and not (isinstance(tr, float) and (tr != tr)) else sig["price"] * 0.01
    sizing = trisk.calc_position_size(sig["price"], atr)
    qty = body.quantity or sizing["quantity"]
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity resolved to 0")
    pos = await tpaper.open_paper_position(
        symbol=body.symbol,
        qty=qty,
        entry=sig["price"],
        stop_loss=sizing["stop_loss"],
        target=sizing["target"],
        signal_score=sig["composite"],
    )
    return {"position": pos, "sizing": sizing, "signal": sig}


@api.post("/paper/close/{position_id}")
async def paper_close(position_id: str):
    t = await tpaper.close_paper_position(position_id, reason="manual")
    if not t:
        raise HTTPException(status_code=404, detail="Position not found or already closed")
    return {"trade": t}


@api.post("/paper/close-all")
async def paper_close_all():
    positions = await tpaper.list_open_positions()
    closed = []
    for p in positions:
        t = await tpaper.close_paper_position(p["id"], reason="close_all")
        if t:
            closed.append(t)
    return {"closed": closed, "count": len(closed)}


# ================= Backtest =================
@api.post("/backtest/run")
async def backtest_run(body: BacktestRequest):
    # Offload to thread since yfinance is sync & heavy
    result = await asyncio.to_thread(tbacktest.run_backtest, body.period or "2y")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await tbacktest.save_result(result)
    return result


@api.get("/backtest/latest")
async def backtest_latest():
    r = await tbacktest.latest_result()
    if not r:
        return {"none": True}
    return r


# ================= Upstox =================
@api.get("/upstox/status")
async def upstox_status():
    return await tupstox.get_status()


@api.post("/upstox/configure")
async def upstox_configure(body: UpstoxSettingsBody):
    await tupstox.save_upstox_settings(body.model_dump())
    return {"ok": True, "status": await tupstox.get_status()}


@api.get("/upstox/auth-url")
async def upstox_auth_url():
    url = await tupstox.get_auth_url()
    if not url:
        raise HTTPException(status_code=400, detail="Configure Upstox API key first")
    return {"auth_url": url}


@api.post("/upstox/token")
async def upstox_token(body: UpstoxTokenBody):
    if body.access_token:
        await tupstox.save_upstox_settings({
            "access_token": body.access_token,
            "token_refreshed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "status": await tupstox.get_status()}
    if body.code:
        result = await tupstox.exchange_code_for_token(body.code)
        return {"result": result, "status": await tupstox.get_status()}
    raise HTTPException(status_code=400, detail="Provide 'code' or 'access_token'")


@api.get("/upstox/funds")
async def upstox_funds():
    return await tupstox.get_funds()


@api.post("/upstox/save-credentials")
async def upstox_save_creds(body: dict = Body(...)):
    """Save mobile, pin, totp_secret for auto-login. All optional individually."""
    allowed = {"mobile", "pin", "totp_secret"}
    update = {k: v for k, v in body.items() if k in allowed and v}
    if not update:
        raise HTTPException(status_code=400, detail="Provide mobile/pin/totp_secret")
    await tupstox.save_upstox_settings(update)
    return {"ok": True, "saved_keys": list(update.keys())}


@api.post("/upstox/auto-login")
async def upstox_auto_login():
    """Trigger Playwright TOTP auto-login flow."""
    from trading import upstox_auth as ua
    result = await ua.auto_login()
    if result.get("ok"):
        # Push Telegram confirmation
        try:
            await ttelegram.send_message(
                f"🔓 <b>Upstox token refreshed</b>\nAt {result.get('token_refreshed_at')}\n"
                f"Expires in {result.get('expires_in', 'unknown')}s"
            )
        except Exception:
            pass
    return result


# ================= Telegram =================
@api.get("/telegram/status")
async def tg_status():
    st = await ttelegram.status()
    log = await ttelegram.recent_log(limit=20)
    return {**st, "recent": log}


@api.post("/telegram/configure")
async def tg_configure(body: TelegramSettingsBody):
    await ttelegram.save_tg_settings(body.model_dump())
    info = await ttelegram.get_bot_info()
    return {"ok": True, "bot_info": info, "status": await ttelegram.status()}


@api.post("/telegram/send-test")
async def tg_send_test():
    r = await ttelegram.send_message("✅ <b>Upstox Bot Online</b>\nTest message from dashboard")
    return r


@api.post("/telegram/send-morning-brief")
async def tg_morning():
    await tscheduler.job_morning_brief()
    return {"ok": True}


@api.post("/telegram/send-eod")
async def tg_eod():
    await tscheduler.job_eod_summary()
    return {"ok": True}


@api.post("/telegram/discover-chat")
async def tg_discover():
    return await ttelegram.discover_chat_id()


@api.post("/telegram/save-bot-token")
async def tg_save_bot(body: dict = Body(...)):
    token = body.get("bot_token")
    if not token:
        raise HTTPException(status_code=400, detail="bot_token required")
    await ttelegram.save_tg_settings({"bot_token": token})
    info = await ttelegram.get_bot_info()
    return {"ok": True, "bot_info": info}


# ================= Seed demo data =================
@api.post("/seed-demo")
async def seed_demo():
    """Creates some sample paper trades for demo display."""
    import random
    db = get_db()
    await db.paper_trades.delete_many({})
    await db.paper_positions.delete_many({})
    syms = tconfig.WATCHLIST
    now = datetime.now(timezone.utc)
    for i in range(5):
        sym = random.choice(syms)
        q = tmarket.get_live_quote(sym)
        if not q:
            continue
        price = q["price"]
        qty = random.randint(20, 80)
        if i < 3:
            exit_px = price * (1 + random.uniform(0.003, 0.012))
        else:
            exit_px = price * (1 - random.uniform(0.002, 0.008))
        from trading.charges import calc_charges
        c = calc_charges(price, exit_px, qty)
        gross = (exit_px - price) * qty
        net = gross - c.total
        await db.paper_trades.insert_one({
            "id": f"seed-{i}",
            "symbol": sym,
            "qty": qty,
            "entry_price": round(price, 2),
            "exit_price": round(exit_px, 2),
            "gross_pnl": round(gross, 2),
            "charges": c.to_dict(),
            "net_pnl": round(net, 2),
            "opened_at": now.replace(hour=9, minute=30).isoformat(),
            "closed_at": now.isoformat(),
            "signal_score": round(random.uniform(0.68, 0.85), 3),
            "reason": "seed",
        })
    return {"ok": True}


# Register router
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    try:
        tscheduler.start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")


@app.on_event("shutdown")
async def _shutdown():
    tscheduler.stop_scheduler()
