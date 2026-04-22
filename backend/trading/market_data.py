# alphadesk/market_data.py

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import yfinance as yf
import time

from .config import INSTRUMENT_MAP

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# ⚙️ CONFIG
# ─────────────────────────────────────────────

CACHE_TTL_QUOTE = 60
CACHE_TTL_HIST = 3600

_quote_cache: dict[str, dict] = {}
_hist_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}

# ─────────────────────────────────────────────
# 🔧 SYMBOL HANDLING
# ─────────────────────────────────────────────

def get_yf_symbol(symbol: str) -> str:
    if symbol in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[symbol]["yf"]
    if symbol.endswith(".NS") or "^" in symbol or "=" in symbol:
        return symbol
    return f"{symbol}.NS"

# ─────────────────────────────────────────────
# 📊 HISTORICAL DATA (FIXED)
# ─────────────────────────────────────────────

def get_historical(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    key = f"{symbol}|{period}|{interval}"
    now = datetime.now(timezone.utc)

    # ✅ Cache check
    cached = _hist_cache.get(key)
    if cached and (now - cached[0]).total_seconds() < CACHE_TTL_HIST:
        return cached[1]

    yf_symbol = get_yf_symbol(symbol)

    # ✅ Retry mechanism (fix yfinance errors)
    for attempt in range(3):
        try:
            df = yf.download(
                yf_symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False
            )

            if df is not None and not df.empty:
                df = df.rename(columns=str.lower)

                df = df[["open", "high", "low", "close", "volume"]]
                df = df.dropna()

                _hist_cache[key] = (now, df)
                return df

        except Exception as e:
            logger.warning(f"{symbol} fetch attempt {attempt+1} failed: {e}")
            time.sleep(2)

    # ❌ HARD FAIL (no fake data)
    logger.error(f"❌ Failed to fetch real data for {symbol}")
    return pd.DataFrame()

# ─────────────────────────────────────────────
# 💰 LIVE QUOTE
# ─────────────────────────────────────────────

def get_live_quote(symbol: str) -> Optional[dict]:
    now = datetime.now(timezone.utc)

    cached = _quote_cache.get(symbol)
    if cached and (now - cached["_ts"]).total_seconds() < CACHE_TTL_QUOTE:
        return cached["data"]

    yf_symbol = get_yf_symbol(symbol)

    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="1d")

        if hist is None or hist.empty:
            return None

        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Open"].iloc[-1])

        change_pct = ((price - prev) / prev * 100) if prev else 0

        data = {
            "symbol": symbol,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
        }

        _quote_cache[symbol] = {"_ts": now, "data": data}
        return data

    except Exception as e:
        logger.warning(f"Quote error for {symbol}: {e}")
        return None

# ─────────────────────────────────────────────
# 🌍 GLOBAL MARKET CUES
# ─────────────────────────────────────────────

def get_global_cues() -> dict:
    symbols = {
        "nifty": "^NSEI",
        "sp500": "^GSPC",
        "india_vix": "^INDIAVIX",
        "usdinr": "USDINR=X",
        "crude": "CL=F",
    }

    def get_change(df):
        if df is None or len(df) < 2:
            return 0
        return float((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100)

    out = {}

    for name, sym in symbols.items():
        try:
            df = yf.download(sym, period="2d", interval="1d", progress=False, threads=False)

            if df is None or df.empty:
                continue

            out[name] = {
                "change_pct": get_change(df),
                "price": float(df["Close"].iloc[-1])
            }

        except Exception as e:
            logger.warning(f"Global cue error {name}: {e}")

    return out
