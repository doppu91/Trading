"""
Upgraded Multi-layer Signal Engine
+ Time-based intelligence
+ Dynamic thresholds
+ Strong entry/exit logic
"""

from __future__ import annotations
import logging
import asyncio
import random
import numpy as np
import pandas as pd
import ta

from .config import WEIGHTS, INDIA_VIX_MAX, SIGNAL_THRESHOLD
from .market_data import get_historical, get_live_quote, get_global_cues
from .feature_engine import compute_features, FEATURE_COLS
from .lgbm_trainer import predict_score as lgbm_predict_score, get_model
from . import scrapers

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 📊 TECHNICAL SCORE (RULE)
# ─────────────────────────────────────────────

def _technical_score_rule(df: pd.DataFrame) -> float:
    if df.empty or len(df) < 50:
        return 0.5

    close = df["close"]
    score = 0.5

    try:
        rsi = ta.momentum.RSIIndicator(close, 14).rsi().iloc[-1]
        if 40 < rsi < 70: score += 0.08
        if rsi > 55: score += 0.04

        macd = ta.trend.MACD(close)
        if macd.macd_diff().iloc[-1] > 0: score += 0.1

        ema_fast = close.ewm(span=9).mean().iloc[-1]
        ema_slow = close.ewm(span=21).mean().iloc[-1]
        if ema_fast > ema_slow: score += 0.1

        bb = ta.volatility.BollingerBands(close, 20)
        if close.iloc[-1] > bb.bollinger_mavg().iloc[-1]: score += 0.05

        ret_5 = close.pct_change(5).iloc[-1]
        if ret_5 and ret_5 > 0:
            score += min(0.1, float(ret_5) * 2)

    except Exception as e:
        logger.debug(f"rule tech err: {e}")

    return float(max(0.0, min(1.0, score)))


# ─────────────────────────────────────────────
# 🤖 ML SCORE
# ─────────────────────────────────────────────

def _technical_score_ml(df: pd.DataFrame) -> tuple[float, bool]:
    if get_model() is None or df.empty or len(df) < 30:
        return _technical_score_rule(df), False

    try:
        feats = compute_features(df).iloc[-1]
        feats_dict = {
            c: float(feats[c]) if not pd.isna(feats[c]) else 0.0
            for c in FEATURE_COLS
        }

        score = lgbm_predict_score(feats_dict)
        if score is None:
            return _technical_score_rule(df), False

        return float(max(0.0, min(1.0, score))), True

    except Exception as e:
        logger.debug(f"ml tech err: {e}")
        return _technical_score_rule(df), False


# ─────────────────────────────────────────────
# ⏱ TIME SCORE (NEW — YOUR EDGE)
# ─────────────────────────────────────────────

def _time_score(df: pd.DataFrame) -> float:
    if len(df) < 20:
        return 0.5

    returns = df["close"].pct_change()
    trend_strength = returns.rolling(5).mean().iloc[-1]

    if pd.isna(trend_strength):
        return 0.5

    score = 0.5 + trend_strength * 10
    return float(max(0.0, min(1.0, score)))


# ─────────────────────────────────────────────
# 🌍 GLOBAL SCORE
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# 🎯 MAIN SIGNAL FUNCTION
# ─────────────────────────────────────────────

def get_signal_for_symbol(symbol: str, cues: dict | None = None,
                         sentiment: dict | None = None,
                         fii: dict | None = None,
                         gex: dict | None = None) -> dict:

    df = get_historical(symbol, period="3mo", interval="1d")

    tech, used_ml = _technical_score_ml(df)
    time_score = _time_score(df)

    sent = sentiment["score"] if sentiment else 0.55
    fii_score = fii["score"] if fii else 0.58
    gex_score = gex["score"] if gex else 0.55

    cues = cues if cues is not None else get_global_cues()
    glob = _global_cue_score(cues)

    # 📊 Volatility-based threshold
    vix = cues.get("india_vix", {}).get("price", 15)
    dynamic_threshold = SIGNAL_THRESHOLD

    if vix > 20:
        dynamic_threshold += 0.05
    elif vix < 14:
        dynamic_threshold -= 0.05

    # 🧠 Composite score
    composite = (
        tech * WEIGHTS["technical"]
        + sent * WEIGHTS["sentiment"]
        + fii_score * WEIGHTS["fii_flow"]
        + gex_score * WEIGHTS["gex"]
        + glob * WEIGHTS["global_cue"]
        + time_score * 0.15   # ⭐ NEW
    )

    # 🎯 Strong filtering
    if tech < 0.55:
        action = "HOLD"

    else:
        if composite >= dynamic_threshold + 0.05:
            action = "STRONG_BUY"
        elif composite >= dynamic_threshold:
            action = "BUY"
        elif composite < 0.4:
            action = "EXIT"
        else:
            action = "HOLD"

    q = get_live_quote(symbol) or {}

    return {
        "symbol": symbol,
        "composite": round(float(composite), 3),
        "action": action,
        "ml_used": used_ml,
        "time_score": round(time_score, 3),
        "price": q.get("price"),
        "change_pct": q.get("change_pct"),
        "layers": {
            "technical": round(tech, 3),
            "sentiment": round(sent, 3),
            "fii_flow": round(fii_score, 3),
            "gex": round(gex_score, 3),
            "global_cue": round(glob, 3),
            "time": round(time_score, 3),
        },
    }


# ─────────────────────────────────────────────
# ⚡ ASYNC BATCH
# ─────────────────────────────────────────────

async def get_signals_with_scrapers(symbols: list[str], cues: dict | None = None):

    fii_task = scrapers.fetch_fii_flow()
    gex_task = scrapers.fetch_gex("NIFTY")
    sent_tasks = [scrapers.fetch_sentiment(s) for s in symbols]

    fii_data, gex_data, *sent_data = await asyncio.gather(
        fii_task, gex_task, *sent_tasks, return_exceptions=True
    )

    fii_data = fii_data if isinstance(fii_data, dict) else None
    gex_data = gex_data if isinstance(gex_data, dict) else None

    results = []
    for sym, sent in zip(symbols, sent_data):
        sent = sent if isinstance(sent, dict) else None
        results.append(
            get_signal_for_symbol(sym, cues=cues, sentiment=sent, fii=fii_data, gex=gex_data)
        )

    return results


# ─────────────────────────────────────────────
# 🛑 HARD RISK GATES
# ─────────────────────────────────────────────

def check_hard_gates(regime: str, vix: float, daily_pnl: float,
                     open_positions: int, max_daily_loss: float, max_positions: int):

    if regime == "Bear":
        return False, "Bear regime — all trades blocked"

    if vix > INDIA_VIX_MAX:
        return False, f"India VIX {vix} too high"

    if daily_pnl <= -max_daily_loss:
        return False, f"Daily loss cap hit"

    if open_positions >= max_positions:
        return False, f"Max positions reached"

    return True, "OK"
