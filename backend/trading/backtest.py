"""Backtest runner — 2-year simulation over Nifty50 with charges applied."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
import numpy as np
import pandas as pd
import ta
from .market_data import get_historical
from .charges import calc_charges
from .config import CAPITAL, WATCHLIST, TARGET_NET_DAILY
from .db import get_db

logger = logging.getLogger(__name__)


# ======== Helpers ========

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema_fast"] = df["close"].ewm(span=9).mean()
    df["ema_slow"] = df["close"].ewm(span=21).mean()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], 14).average_true_range()
    df["regime_proxy"] = df["close"].pct_change(20)
    return df


def _entry_signal(row) -> bool:
    return (
        not np.isnan(row.rsi)
        and 50 < row.rsi < 70
        and row.ema_fast > row.ema_slow
        and row.regime_proxy > 0
    )


@dataclass
class _Position:
    entry_idx: int
    entry_price: float
    stop: float
    target: float
    qty: int


def _open_position(row, i: int) -> _Position:
    atr = float(row.atr) if not np.isnan(row.atr) else float(row.close) * 0.01
    stop_dist = atr * 1.5
    entry = float(row.close)
    risk_amt = CAPITAL * 0.015
    qty = max(1, int(risk_amt // stop_dist))
    qty = min(qty, int(CAPITAL * 0.2 // entry))
    return _Position(i, entry, entry - stop_dist, entry + stop_dist * 2, qty)


def _exit_price(row, pos: _Position, i: int) -> tuple[float | None, str]:
    hi, lo = float(row.high), float(row.low)
    if lo <= pos.stop:
        return pos.stop, "sl"
    if hi >= pos.target:
        return pos.target, "target"
    if i - pos.entry_idx >= 3:
        return float(row.close), "time"
    return None, ""


def _record_trade(date, sym: str, pos: _Position, exit_px: float, reason: str) -> dict:
    gross = (exit_px - pos.entry_price) * pos.qty
    charges = calc_charges(pos.entry_price, exit_px, pos.qty).total
    return {
        "date": date.strftime("%Y-%m-%d"),
        "symbol": sym,
        "qty": pos.qty,
        "entry": round(pos.entry_price, 2),
        "exit": round(exit_px, 2),
        "gross": round(gross, 2),
        "charges": round(charges, 2),
        "net": round(gross - charges, 2),
        "reason": reason,
    }


def _simulate_symbol(sym: str, period: str) -> list[dict]:
    df = get_historical(sym, period=period, interval="1d")
    if df.empty or len(df) < 60:
        return []
    df = _prep(df)
    trades: list[dict] = []
    pos: _Position | None = None
    for i in range(40, len(df)):
        row = df.iloc[i]
        date = df.index[i]
        if pos is None:
            if _entry_signal(row):
                pos = _open_position(row, i)
            continue
        exit_px, reason = _exit_price(row, pos, i)
        if exit_px is not None:
            trades.append(_record_trade(date, sym, pos, exit_px, reason))
            pos = None
    return trades


def _compute_metrics(tdf: pd.DataFrame) -> dict:
    tdf = tdf.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])
    wins = int((tdf["net"] > 0).sum())
    losses = int((tdf["net"] < 0).sum())
    daily = tdf.groupby(tdf["date"].dt.normalize()).agg(
        net=("net", "sum"), gross=("gross", "sum"),
        charges=("charges", "sum"), trades=("net", "count"))
    daily["cum"] = daily["net"].cumsum()
    dd_series = daily["cum"] - daily["cum"].cummax()
    daily_ret = daily["net"] / CAPITAL
    sharpe = float((daily_ret.mean() / daily_ret.std()) * np.sqrt(252)) if daily_ret.std() > 0 else 0.0

    return {
        "wins": wins, "losses": losses,
        "win_rate": round(wins / len(tdf) * 100, 1) if len(tdf) else 0.0,
        "trading_days": int(daily.shape[0]),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(float(dd_series.min()) if not dd_series.empty else 0.0, 2),
        "target_hit_rate": round(float((daily["net"] >= TARGET_NET_DAILY).sum() / len(daily) * 100) if len(daily) else 0.0, 1),
        "daily": daily,
    }


def _monthly_breakdown(tdf: pd.DataFrame) -> list[dict]:
    tdf = tdf.copy()
    tdf["date"] = pd.to_datetime(tdf["date"])
    monthly = tdf.groupby(tdf["date"].dt.to_period("M")).agg(
        gross=("gross", "sum"), charges=("charges", "sum"),
        net=("net", "sum"), trades=("net", "count"))
    return [
        {"month": str(p), "gross": round(float(r.gross), 2),
         "charges": round(float(r.charges), 2),
         "net": round(float(r.net), 2), "trades": int(r.trades)}
        for p, r in monthly.iterrows()
    ]


# ======== Public ========

def run_backtest(period: str = "2y", symbols: list[str] | None = None) -> dict:
    symbols = symbols or WATCHLIST
    all_trades: list[dict] = []
    for sym in symbols:
        all_trades.extend(_simulate_symbol(sym, period))

    if not all_trades:
        return {"error": "No trades simulated — data fetch may have failed."}

    tdf = pd.DataFrame(all_trades)
    metrics = _compute_metrics(tdf)
    daily = metrics.pop("daily")
    trading_days = metrics["trading_days"]
    gross_total = float(tdf["gross"].sum())
    charges_total = float(tdf["charges"].sum())
    net_total = float(tdf["net"].sum())

    return {
        "id": str(uuid.uuid4()),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "symbols": symbols,
        "total_trades": len(tdf),
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "win_rate": metrics["win_rate"],
        "gross_pnl": round(gross_total, 2),
        "total_charges": round(charges_total, 2),
        "net_pnl": round(net_total, 2),
        "trading_days": trading_days,
        "avg_gross_per_day": round(gross_total / trading_days, 2) if trading_days else 0,
        "avg_charges_per_day": round(charges_total / trading_days, 2) if trading_days else 0,
        "avg_net_per_day": round(net_total / trading_days, 2) if trading_days else 0,
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "target_hit_rate": metrics["target_hit_rate"],
        "monthly": _monthly_breakdown(tdf),
        "equity_curve": [
            {"date": d.strftime("%Y-%m-%d"), "cum_net": round(float(v), 2)}
            for d, v in daily["cum"].items()
        ],
        "sample_trades": all_trades[:100],
    }


async def save_result(result: dict) -> None:
    await get_db().backtest_results.insert_one({**result})


async def latest_result() -> dict | None:
    return await get_db().backtest_results.find_one({}, {"_id": 0}, sort=[("run_at", -1)])
