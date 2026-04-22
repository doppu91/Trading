"""Market data layer — tries yfinance; falls back to synthetic data."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import yfinance as yf
from .config import INSTRUMENT_MAP
from .synthetic_data import synth_history, synth_quote

logger = logging.getLogger(__name__)

_quote_cache: dict[str, dict] = {}
_hist_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
CACHE_TTL_QUOTE = 60
CACHE_TTL_HIST = 3600


def get_yf_symbol(symbol: str) -> str:
    if symbol in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[symbol]["yf"]
    return symbol if symbol.endswith(".NS") or "^" in symbol or "=" in symbol else f"{symbol}.NS"


def get_live_quote(symbol: str) -> Optional[dict]:
    key = symbol
    now = datetime.now(timezone.utc)
    cached = _quote_cache.get(key)
    if cached and (now - cached["_ts"]).total_seconds() < CACHE_TTL_QUOTE:
        return cached["data"]
    data = None
    try:
        yf_sym = get_yf_symbol(symbol)
        t = yf.Ticker(yf_sym)
        fi = t.fast_info
        price = float(fi.get("last_price") or fi.get("lastPrice") or 0)
        if price > 0:
            prev = float(fi.get("previous_close") or fi.get("previousClose") or 0)
            vol = int(fi.get("last_volume") or fi.get("lastVolume") or 0)
            change_pct = ((price - prev) / prev * 100) if prev else 0.0
            data = {"symbol": symbol, "price": round(price, 2), "prev_close": round(prev, 2),
                    "change_pct": round(change_pct, 2), "volume": vol}
    except Exception as e:
        logger.debug(f"yf quote fail {symbol}: {e}")
    if data is None:
        # Use yf_symbol (^NSEI etc) so synth_data has base price
        key_for_synth = get_yf_symbol(symbol) if symbol not in ("^NSEI", "^GSPC", "^INDIAVIX", "USDINR=X", "CL=F") else symbol
        # Prefer INSTRUMENT_MAP direct symbol for synthetic
        sym_for_base = symbol if symbol in ["^NSEI", "^GSPC", "^INDIAVIX", "USDINR=X", "CL=F"] else symbol.split(".")[0]
        data = synth_quote(sym_for_base)
        data["synthetic"] = True
    _quote_cache[key] = {"_ts": now, "data": data}
    return data


def get_historical(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    key = f"{symbol}|{period}|{interval}"
    now = datetime.now(timezone.utc)
    cached = _hist_cache.get(key)
    if cached and (now - cached[0]).total_seconds() < CACHE_TTL_HIST:
        return cached[1]
    df = pd.DataFrame()
    try:
        yf_sym = get_yf_symbol(symbol)
        df = yf.Ticker(yf_sym).history(period=period, interval=interval, auto_adjust=False)
        if not df.empty:
            df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug(f"yf hist fail {symbol}: {e}")

    if df.empty:
        # Determine how many days to synthesize
        days_map = {"1mo": 25, "3mo": 80, "6mo": 150, "1y": 260, "2y": 520, "5y": 1260}
        days = days_map.get(period, 260)
        sym_for_base = symbol if symbol in ["^NSEI", "^GSPC", "^INDIAVIX", "USDINR=X", "CL=F"] else symbol.split(".")[0]
        df = synth_history(sym_for_base, days=days)

    _hist_cache[key] = (now, df)
    return df


def get_global_cues() -> dict:
    symbols = {
        "nifty": "^NSEI",
        "sp500": "^GSPC",
        "india_vix": "^INDIAVIX",
        "usdinr": "USDINR=X",
        "crude": "CL=F",
    }
    out = {}
    for name, sym in symbols.items():
        q = get_live_quote(sym)
        if q:
            out[name] = q
    return out
