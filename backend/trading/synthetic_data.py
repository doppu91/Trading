"""Synthetic market data fallback — deterministic, realistic-looking OHLCV.

Used when live yfinance isn't reachable (e.g., inside locked-down containers).
Produces stable series so regime, backtest, and signals all work end-to-end.
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

# Base prices per symbol (approximate real NSE ranges)
BASES = {
    "RELIANCE": 2850, "HDFCBANK": 1680, "INFY": 1520, "ICICIBANK": 1120,
    "TCS": 3960, "KOTAKBANK": 1785, "LT": 3620, "AXISBANK": 1165,
    "SBIN": 815, "BAJFINANCE": 6950,
    "^NSEI": 24350, "^GSPC": 5210, "^INDIAVIX": 14.8,
    "USDINR=X": 83.45, "CL=F": 82.3,
}


def _seed(symbol: str) -> int:
    h = hashlib.md5(symbol.encode()).hexdigest()
    return int(h[:8], 16)


def synth_history(symbol: str, days: int = 1260) -> pd.DataFrame:
    """Generate OHLCV for a symbol — deterministic per symbol."""
    base = BASES.get(symbol, 1000)
    rng = np.random.default_rng(_seed(symbol))

    # Log returns: mix of regimes
    n = days
    rets = np.zeros(n)
    i = 0
    while i < n:
        regime = rng.choice(["bull", "side", "bear"], p=[0.55, 0.30, 0.15])
        length = rng.integers(20, 80)
        length = min(length, n - i)
        if regime == "bull":
            mu, sigma = 0.0009, 0.012
        elif regime == "bear":
            mu, sigma = -0.0010, 0.018
        else:
            mu, sigma = 0.0001, 0.009
        rets[i : i + length] = rng.normal(mu, sigma, length)
        i += length

    prices = base * np.exp(np.cumsum(rets))
    # OHLC derived from close + intraday range
    intraday_range = np.abs(rng.normal(0, 0.008, n))
    high = prices * (1 + intraday_range)
    low = prices * (1 - intraday_range)
    open_ = np.concatenate(([base], prices[:-1]))
    volume = rng.integers(500_000, 5_000_000, n)

    # Dates = recent business days
    end = datetime.now(timezone.utc).date()
    dates = pd.bdate_range(end=end, periods=n)
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume,
    }, index=dates)
    return df


def synth_quote(symbol: str) -> dict:
    df = synth_history(symbol, days=5)
    price = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2])
    change_pct = (price - prev) / prev * 100 if prev else 0
    return {
        "symbol": symbol,
        "price": round(price, 2),
        "prev_close": round(prev, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(df["volume"].iloc[-1]),
    }
