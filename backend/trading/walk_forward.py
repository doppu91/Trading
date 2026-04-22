"""Walk-forward backtest using REAL Upstox historical data.

Runs the live signal engine on the last N days of real NSE data day-by-day
(no future-leak), reports gross/net P&L with charges applied identically to
live execution.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import ta
from .charges import calc_charges
from .config import CAPITAL, WATCHLIST, TARGET_NET_DAILY
from .upstox_client import get_historical as upstox_history
from .db import get_db

logger = logging.getLogger(__name__)


async def _fetch_history_df(symbol: str, days_back: int, interval: str = "day") -> pd.DataFrame:
    candles = await upstox_history(symbol, interval=interval, days_back=days_back)
    if not candles:
        return pd.DataFrame()
    # Format: [ts, open, high, low, close, volume, oi]
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").set_index("ts")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema_fast"] = df["close"].ewm(span=9).mean()
    df["ema_slow"] = df["close"].ewm(span=21).mean()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], 14).average_true_range()
    df["regime20"] = df["close"].pct_change(20)
    df["macd_diff"] = ta.trend.MACD(df["close"]).macd_diff()
    return df


def _entry(row) -> bool:
    """Daily-bar entry signal."""
    return (
        not np.isnan(row.rsi)
        and 50 < row.rsi < 70
        and row.ema_fast > row.ema_slow
        and (row.regime20 or 0) > 0
        and (row.macd_diff or 0) > 0
    )


def _entry_intraday(row, composite_score: float | None = None,
                    composite_threshold: float = 0.75) -> bool:
    """Tighter intraday entry: narrower RSI band + composite gate + stronger trend."""
    if np.isnan(row.rsi):
        return False
    # Tighter RSI band: 55-65 (was 50-70)
    if not (55 < row.rsi < 65):
        return False
    if not (row.ema_fast > row.ema_slow):
        return False
    if (row.regime20 or 0) <= 0:
        return False
    if (row.macd_diff or 0) <= 0:
        return False
    # Composite (LightGBM) gate if available
    if composite_score is not None and composite_score < composite_threshold:
        return False
    return True


def _composite_for_row(df: pd.DataFrame, idx: int, model_key: str | None) -> float | None:
    """Score using a LightGBM model (keyed by symbol or None for default).
    Returns None if no model loaded.
    """
    from .lgbm_trainer import predict_score, get_model
    if get_model(model_key) is None:
        return None
    try:
        from .feature_engine import compute_features, FEATURE_COLS
        feats = compute_features(df.iloc[: idx + 1]).iloc[-1]
        feats_dict = {c: float(feats[c]) if not (isinstance(feats[c], float) and np.isnan(feats[c])) else 0.0 for c in FEATURE_COLS}
        return predict_score(feats_dict, model_key=model_key)
    except Exception:
        return None


async def run_walk_forward(days: int = 90, symbols: list[str] | None = None,
                           interval: str = "day", exit_bars: int = 3) -> dict:
    """Walk-forward over last N calendar days using REAL Upstox candles.

    interval: 'day' (default) or '30minute' / '5minute' / '1minute' for intraday.
    exit_bars: time-based exit after this many bars if SL/target not hit.
               For daily: 3 bars (3 days). For 30min: 6 bars (3 hours).
    """
    symbols = symbols or WATCHLIST
    all_trades: list[dict] = []
    fetched: dict[str, pd.DataFrame] = {}

    coros = [_fetch_history_df(s, days_back=days + 60, interval=interval) for s in symbols]
    results = await asyncio.gather(*coros, return_exceptions=True)
    for sym, res in zip(symbols, results):
        if isinstance(res, pd.DataFrame) and not res.empty:
            fetched[sym] = res

    if not fetched:
        return {"error": "Failed to fetch real historical data from Upstox."}

    # Now simulate per symbol
    is_intraday = interval != "day"
    composite_threshold = 0.75 if is_intraday else 0.68

    for sym, df in fetched.items():
        if len(df) < 40:
            continue
        df = _prep(df)
        # For intraday, simulate across the entire fetched window (except warm-up);
        # for daily, limit to last `days` bars.
        sim_start = 40 if is_intraday else max(40, len(df) - days)
        # Per-symbol intraday model key, or shared daily model
        model_key = f"intraday_{sym}" if is_intraday else None
        in_pos = False
        entry_idx = entry_px = stop = target = 0.0
        qty = 0
        for i in range(sim_start, len(df)):
            row = df.iloc[i]
            date = df.index[i]
            if not in_pos:
                comp = _composite_for_row(df, i, model_key) if is_intraday else None
                triggered = _entry_intraday(row, composite_score=comp,
                                            composite_threshold=composite_threshold) if is_intraday else _entry(row)
                if triggered:
                    atr = float(row.atr) if not np.isnan(row.atr) else float(row.close) * 0.01
                    # Tighter SL for intraday: 1.0× ATR (was 1.5×)
                    stop_dist = atr * (1.0 if is_intraday else 1.5)
                    entry_px = float(row.close)
                    stop = entry_px - stop_dist
                    target = entry_px + stop_dist * 2
                    risk_amt = CAPITAL * 0.015
                    qty = max(1, int(risk_amt // stop_dist))
                    qty = min(qty, int(CAPITAL * 0.2 // entry_px))
                    entry_idx = i
                    in_pos = True
            else:
                hi, lo = float(row.high), float(row.low)
                exit_px = None
                reason = ""
                if lo <= stop:
                    exit_px = stop; reason = "sl"
                elif hi >= target:
                    exit_px = target; reason = "target"
                elif i - entry_idx >= exit_bars:
                    exit_px = float(row.close); reason = "time"
                if exit_px is not None:
                    gross = (exit_px - entry_px) * qty
                    charges = calc_charges(entry_px, exit_px, qty).total
                    all_trades.append({
                        "date": date.strftime("%Y-%m-%d %H:%M") if is_intraday else date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "qty": qty,
                        "entry": round(entry_px, 2),
                        "exit": round(exit_px, 2),
                        "gross": round(gross, 2),
                        "charges": round(charges, 2),
                        "net": round(gross - charges, 2),
                        "reason": reason,
                    })
                    in_pos = False
                    qty = 0

    if not all_trades:
        return {"error": "No trades generated in this period — signals never triggered or all blocked."}

    tdf = pd.DataFrame(all_trades)
    tdf["date_day"] = pd.to_datetime(tdf["date"]).dt.normalize()
    wins = int((tdf["net"] > 0).sum())
    losses = int((tdf["net"] < 0).sum())
    daily = tdf.groupby("date_day").agg(
        net=("net", "sum"), gross=("gross", "sum"),
        charges=("charges", "sum"), trades=("net", "count"))
    daily["cum"] = daily["net"].cumsum()
    dd = daily["cum"] - daily["cum"].cummax()
    daily_ret = daily["net"] / CAPITAL
    sharpe = float((daily_ret.mean() / daily_ret.std()) * np.sqrt(252)) if daily_ret.std() > 0 else 0.0

    return {
        "id": str(uuid.uuid4()),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mode": "walk_forward_upstox",
        "interval": interval,
        "exit_bars": exit_bars,
        "days": days,
        "symbols_fetched": list(fetched.keys()),
        "symbols_skipped": [s for s in symbols if s not in fetched],
        "total_trades": len(tdf),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(tdf) * 100, 1),
        "gross_pnl": round(float(tdf["gross"].sum()), 2),
        "total_charges": round(float(tdf["charges"].sum()), 2),
        "net_pnl": round(float(tdf["net"].sum()), 2),
        "trading_days": int(daily.shape[0]),
        "avg_net_per_day": round(float(tdf["net"].sum()) / max(1, daily.shape[0]), 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(float(dd.min()) if not dd.empty else 0.0, 2),
        "target_hit_rate": round(float((daily["net"] >= TARGET_NET_DAILY).sum() / len(daily) * 100) if len(daily) else 0.0, 1),
        "equity_curve": [
            {"date": d.strftime("%Y-%m-%d"), "cum_net": round(float(v), 2)}
            for d, v in daily["cum"].items()
        ],
        "trades": all_trades[:200],
    }


async def save_result(result: dict) -> None:
    await get_db().walkforward_results.insert_one({**result})
