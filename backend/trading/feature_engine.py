"""18-feature engineering for ML signal classifier.

Features computed per bar from OHLCV:
 1.  rsi_14
 2.  macd_diff
 3.  ema9_over_ema21
 4.  atr_pct (ATR / price)
 5.  bollinger_position (price vs upper/lower band)
 6.  ret_1d
 7.  ret_5d
 8.  ret_20d
 9.  vol_5d (5-day stdev of returns)
 10. vol_20d
 11. volume_ratio (vol / 20-day avg)
 12. close_over_high20
 13. close_over_low20
 14. day_range (today's H-L / close)
 15. gap_pct (today open vs yesterday close)
 16. dist_to_ema21 (% distance)
 17. roc_10 (rate of change 10-bar)
 18. trend_strength (ema9-ema21)/atr
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import ta

FEATURE_COLS = [
    "rsi_14", "macd_diff", "ema9_over_ema21", "atr_pct", "bb_pos",
    "ret_1d", "ret_5d", "ret_20d", "vol_5d", "vol_20d",
    "volume_ratio", "close_over_high20", "close_over_low20",
    "day_range", "gap_pct", "dist_to_ema21", "roc_10", "trend_strength",
]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame indexed same as df with FEATURE_COLS columns."""
    out = pd.DataFrame(index=df.index)
    close = df["close"]; high = df["high"]; low = df["low"]; vol = df["volume"]

    out["rsi_14"] = ta.momentum.RSIIndicator(close, 14).rsi()
    out["macd_diff"] = ta.trend.MACD(close).macd_diff()

    ema9 = close.ewm(span=9).mean()
    ema21 = close.ewm(span=21).mean()
    out["ema9_over_ema21"] = (ema9 / ema21) - 1.0

    atr = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()
    out["atr_pct"] = atr / close

    bb = ta.volatility.BollingerBands(close, 20)
    upper = bb.bollinger_hband(); lower = bb.bollinger_lband()
    rng = (upper - lower).replace(0, np.nan)
    out["bb_pos"] = (close - lower) / rng

    rets = close.pct_change()
    out["ret_1d"] = rets
    out["ret_5d"] = close.pct_change(5)
    out["ret_20d"] = close.pct_change(20)
    out["vol_5d"] = rets.rolling(5).std()
    out["vol_20d"] = rets.rolling(20).std()

    out["volume_ratio"] = vol / vol.rolling(20).mean()

    out["close_over_high20"] = close / high.rolling(20).max()
    out["close_over_low20"] = close / low.rolling(20).min()

    out["day_range"] = (high - low) / close
    out["gap_pct"] = (df["open"] - close.shift(1)) / close.shift(1)
    out["dist_to_ema21"] = (close - ema21) / ema21
    out["roc_10"] = close.pct_change(10)
    out["trend_strength"] = (ema9 - ema21) / atr.replace(0, np.nan)

    return out[FEATURE_COLS]


def build_labels(df: pd.DataFrame, horizon: int = 3, threshold: float = 0.005) -> pd.Series:
    """Binary label: 1 if forward `horizon`-bar return > threshold, else 0."""
    fwd = df["close"].shift(-horizon) / df["close"] - 1.0
    return (fwd > threshold).astype(int)
