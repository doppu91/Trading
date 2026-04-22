"""Backtest runner — 2-year simulation over Nifty50 with charges applied."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ta
from .market_data import get_historical
from .charges import calc_charges
from .config import CAPITAL, WATCHLIST, CHARGES_PER_TRADE, TARGET_NET_DAILY
from .db import get_db

logger = logging.getLogger(__name__)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema_fast"] = df["close"].ewm(span=9).mean()
    df["ema_slow"] = df["close"].ewm(span=21).mean()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], 14).average_true_range()
    df["ret"] = df["close"].pct_change()
    df["regime_proxy"] = df["close"].pct_change(20)
    return df


def _entry_signal(row) -> bool:
    return (
        not np.isnan(row.rsi)
        and 50 < row.rsi < 70
        and row.ema_fast > row.ema_slow
        and row.regime_proxy > 0
    )


def run_backtest(period: str = "2y", symbols: list[str] | None = None) -> dict:
    symbols = symbols or WATCHLIST
    all_trades = []
    for sym in symbols:
        df = get_historical(sym, period=period, interval="1d")
        if df.empty or len(df) < 60:
            continue
        df = _prep(df)
        in_pos = False
        entry_idx = None
        entry_price = 0.0
        stop_px = 0.0
        target_px = 0.0
        qty = 0
        for i in range(40, len(df)):
            row = df.iloc[i]
            date = df.index[i]
            if not in_pos and _entry_signal(row):
                atr = float(row.atr) if not np.isnan(row.atr) else float(row.close) * 0.01
                stop_dist = atr * 1.5
                entry_price = float(row.close)
                stop_px = entry_price - stop_dist
                target_px = entry_price + stop_dist * 2
                risk_amt = CAPITAL * 0.015
                qty = max(1, int(risk_amt // stop_dist))
                qty = min(qty, int(CAPITAL * 0.2 // entry_price))
                entry_idx = i
                in_pos = True
            elif in_pos:
                hi = float(row.high)
                lo = float(row.low)
                exit_px = None
                reason = ""
                if lo <= stop_px:
                    exit_px = stop_px; reason = "sl"
                elif hi >= target_px:
                    exit_px = target_px; reason = "target"
                elif i - entry_idx >= 3:  # intraday horizon proxy: close after 3 bars
                    exit_px = float(row.close); reason = "time"
                if exit_px is not None:
                    gross = (exit_px - entry_price) * qty
                    c = calc_charges(entry_price, exit_px, qty).total
                    all_trades.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "qty": qty,
                        "entry": round(entry_price, 2),
                        "exit": round(exit_px, 2),
                        "gross": round(gross, 2),
                        "charges": round(c, 2),
                        "net": round(gross - c, 2),
                        "reason": reason,
                    })
                    in_pos = False
                    qty = 0
    if not all_trades:
        return {"error": "No trades simulated — data fetch may have failed."}

    tdf = pd.DataFrame(all_trades)
    tdf["date"] = pd.to_datetime(tdf["date"])
    total = len(tdf)
    wins = int((tdf["net"] > 0).sum())
    losses = int((tdf["net"] < 0).sum())
    gross_total = float(tdf["gross"].sum())
    charges_total = float(tdf["charges"].sum())
    net_total = float(tdf["net"].sum())
    trading_days = int(tdf["date"].dt.normalize().nunique())

    daily = tdf.groupby(tdf["date"].dt.normalize()).agg(net=("net", "sum"), gross=("gross", "sum"), charges=("charges", "sum"), trades=("net", "count"))
    daily["cum"] = daily["net"].cumsum()
    peak = daily["cum"].cummax()
    dd = (daily["cum"] - peak)
    max_dd = float(dd.min()) if not dd.empty else 0.0
    daily_returns = daily["net"] / CAPITAL
    sharpe = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252)) if daily_returns.std() > 0 else 0.0
    target_hit_rate = float((daily["net"] >= TARGET_NET_DAILY).sum() / len(daily) * 100) if len(daily) else 0.0

    monthly = tdf.groupby(tdf["date"].dt.to_period("M")).agg(gross=("gross", "sum"), charges=("charges", "sum"), net=("net", "sum"), trades=("net", "count"))
    monthly_list = []
    for p, row in monthly.iterrows():
        monthly_list.append({
            "month": str(p),
            "gross": round(float(row.gross), 2),
            "charges": round(float(row.charges), 2),
            "net": round(float(row.net), 2),
            "trades": int(row.trades),
        })

    result = {
        "id": str(uuid.uuid4()),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "symbols": symbols,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total else 0.0,
        "gross_pnl": round(gross_total, 2),
        "total_charges": round(charges_total, 2),
        "net_pnl": round(net_total, 2),
        "trading_days": trading_days,
        "avg_gross_per_day": round(gross_total / trading_days, 2) if trading_days else 0,
        "avg_charges_per_day": round(charges_total / trading_days, 2) if trading_days else 0,
        "avg_net_per_day": round(net_total / trading_days, 2) if trading_days else 0,
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_dd, 2),
        "target_hit_rate": round(target_hit_rate, 1),
        "monthly": monthly_list,
        "equity_curve": [
            {"date": d.strftime("%Y-%m-%d"), "cum_net": round(float(v), 2)}
            for d, v in daily["cum"].items()
        ],
        "sample_trades": all_trades[:100],
    }
    return result


async def save_result(result: dict) -> None:
    db = get_db()
    await db.backtest_results.insert_one({**result})


async def latest_result() -> dict | None:
    db = get_db()
    r = await db.backtest_results.find_one({}, {"_id": 0}, sort=[("run_at", -1)])
    return r
