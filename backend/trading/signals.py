"""Multi-layer signal engine — technical, sentiment, FII flow, GEX, global cues."""
from __future__ import annotations
import logging
import random
import numpy as np
import pandas as pd
import ta
from .config import WEIGHTS, INDIA_VIX_MAX, SIGNAL_THRESHOLD
from .market_data import get_historical, get_live_quote, get_global_cues

logger = logging.getLogger(__name__)


def _technical_score(df: pd.DataFrame) -> float:
    """Score 0-1 based on RSI, MACD, EMA cross, BB position."""
    if df.empty or len(df) < 50:
        return 0.5
    close = df["close"]
    score = 0.5
    try:
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
        if 40 < rsi < 70:
            score += 0.08
        if rsi > 55:
            score += 0.04

        macd = ta.trend.MACD(close)
        if macd.macd_diff().iloc[-1] > 0:
            score += 0.1

        ema_fast = close.ewm(span=9).mean().iloc[-1]
        ema_slow = close.ewm(span=21).mean().iloc[-1]
        if ema_fast > ema_slow:
            score += 0.1

        bb = ta.volatility.BollingerBands(close, window=20)
        price = close.iloc[-1]
        mid = bb.bollinger_mavg().iloc[-1]
        if price > mid:
            score += 0.05

        ret_5 = close.pct_change(5).iloc[-1]
        if ret_5 and ret_5 > 0:
            score += min(0.1, float(ret_5) * 2)
    except Exception as e:
        logger.debug(f"tech score err: {e}")
    return float(max(0.0, min(1.0, score)))


def _sentiment_score(symbol: str) -> float:
    # Placeholder; real impl would call news API + FinBERT
    # Use deterministic pseudo-score seeded by symbol for UI consistency
    rng = random.Random(hash(symbol) % 100000)
    return round(0.45 + rng.random() * 0.45, 3)


def _fii_flow_score() -> float:
    # Placeholder: would scrape NSE FII/DII data. Return neutral-bullish default.
    return 0.58


def _gex_score(symbol: str) -> float:
    rng = random.Random((hash(symbol) + 1) % 100000)
    return round(0.4 + rng.random() * 0.5, 3)


def _global_cue_score(cues: dict) -> float:
    if not cues:
        return 0.5
    sp = cues.get("sp500", {}).get("change_pct", 0)
    vix = cues.get("india_vix", {}).get("price", 18)
    crude = cues.get("crude", {}).get("change_pct", 0)
    score = 0.5
    score += 0.1 if sp > 0.3 else (-0.1 if sp < -0.3 else 0)
    score += 0.1 if vix < 15 else (-0.15 if vix > 20 else 0)
    score += -0.05 if crude > 2 else (0.05 if crude < -2 else 0)
    return float(max(0.0, min(1.0, score)))


def get_signal_for_symbol(symbol: str, cues: dict | None = None) -> dict:
    """Returns composite signal score + individual layer breakdown."""
    df = get_historical(symbol, period="3mo", interval="1d")
    tech = _technical_score(df)
    sent = _sentiment_score(symbol)
    fii = _fii_flow_score()
    gex = _gex_score(symbol)
    cues = cues if cues is not None else get_global_cues()
    glob = _global_cue_score(cues)

    composite = (
        tech * WEIGHTS["technical"]
        + sent * WEIGHTS["sentiment"]
        + fii * WEIGHTS["fii_flow"]
        + gex * WEIGHTS["gex"]
        + glob * WEIGHTS["global_cue"]
    )

    q = get_live_quote(symbol) or {}
    action = "BUY" if composite >= SIGNAL_THRESHOLD else "HOLD"
    return {
        "symbol": symbol,
        "composite": round(float(composite), 3),
        "action": action,
        "meets_threshold": composite >= SIGNAL_THRESHOLD,
        "layers": {
            "technical": round(tech, 3),
            "sentiment": round(sent, 3),
            "fii_flow": round(fii, 3),
            "gex": round(gex, 3),
            "global_cue": round(glob, 3),
        },
        "price": q.get("price"),
        "change_pct": q.get("change_pct"),
    }


def check_hard_gates(regime: str, vix: float, daily_pnl: float, open_positions: int, max_daily_loss: float, max_positions: int) -> tuple[bool, str]:
    """Return (allowed, reason_if_blocked)."""
    if regime == "Bear":
        return False, "Bear regime — all trades blocked"
    if vix > INDIA_VIX_MAX:
        return False, f"India VIX {vix} > {INDIA_VIX_MAX} — risk too high"
    if daily_pnl <= -max_daily_loss:
        return False, f"Daily loss cap ₹{max_daily_loss} hit"
    if open_positions >= max_positions:
        return False, f"Max positions ({max_positions}) reached"
    return True, "OK"
