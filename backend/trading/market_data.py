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

_INDEX_SYMBOLS = ("^NSEI", "^GSPC", "^INDIAVIX", "USDINR=X", "CL=F")
_PERIOD_DAYS = {"1mo": 25, "3mo": 80, "6mo": 150, "1y": 260, "2y": 520, "5y": 1260}
_quote_cache: dict[str, dict] = {}
_hist_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
CACHE_TTL_QUOTE = 60
CACHE_TTL_HIST = 3600

# Killswitch: after N consecutive yfinance failures we skip yfinance entirely.
_yf_failures = 0
_yf_disabled = False
_YF_FAIL_LIMIT = 3


def _yf_is_live() -> bool:
    return not _yf_disabled


def _note_yf_failure() -> None:
    global _yf_failures, _yf_disabled
    _yf_failures += 1
    if _yf_failures >= _YF_FAIL_LIMIT and not _yf_disabled:
        _yf_disabled = True
        logger.warning("yfinance disabled after %d failures — using synthetic data only", _yf_failures)


def get_yf_symbol(symbol: str) -> str:
    if symbol in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[symbol]["yf"]
    if symbol.endswith(".NS") or "^" in symbol or "=" in symbol:
        return symbol
    return f"{symbol}.NS"


def _synth_base_key(symbol: str) -> str:
    if symbol in _INDEX_SYMBOLS:
        return symbol
    return symbol.split(".")[0]


def _cached_quote(key: str, now: datetime) -> Optional[dict]:
    cached = _quote_cache.get(key)
    if cached and (now - cached["_ts"]).total_seconds() < CACHE_TTL_QUOTE:
        return cached["data"]
    return None


def _fetch_yf_quote(symbol: str) -> Optional[dict]:
    if not _yf_is_live():
        return None
    try:
        fi = yf.Ticker(get_yf_symbol(symbol)).fast_info
        price = float(fi.get("last_price") or fi.get("lastPrice") or 0)
        if price <= 0:
            _note_yf_failure()
            return None
        prev = float(fi.get("previous_close") or fi.get("previousClose") or 0)
        vol = int(fi.get("last_volume") or fi.get("lastVolume") or 0)
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        return {"symbol": symbol, "price": round(price, 2), "prev_close": round(prev, 2),
                "change_pct": round(change_pct, 2), "volume": vol}
    except Exception as e:
        logger.debug(f"yf quote fail {symbol}: {e}")
        _note_yf_failure()
        return None


def get_live_quote(symbol: str) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    cached = _cached_quote(symbol, now)
    if cached:
        return cached
    data = _fetch_yf_quote(symbol)
    if data is None:
        data = synth_quote(_synth_base_key(symbol))
        data["synthetic"] = True
    _quote_cache[symbol] = {"_ts": now, "data": data}
    return data


def _fetch_yf_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    if not _yf_is_live():
        return pd.DataFrame()
    try:
        df = yf.Ticker(get_yf_symbol(symbol)).history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            _note_yf_failure()
            return df
        return df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug(f"yf hist fail {symbol}: {e}")
        _note_yf_failure()
        return pd.DataFrame()


def get_historical(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    key = f"{symbol}|{period}|{interval}"
    now = datetime.now(timezone.utc)
    cached = _hist_cache.get(key)
    if cached and (now - cached[0]).total_seconds() < CACHE_TTL_HIST:
        return cached[1]

    df = _fetch_yf_history(symbol, period, interval)
    if df.empty:
        df = synth_history(_synth_base_key(symbol), days=_PERIOD_DAYS.get(period, 260))

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
