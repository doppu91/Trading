"""HMM regime detector proxy using GaussianMixture on Nifty returns + volatility.

Classifies market into Bull / Sideways / Bear based on 20-day returns and
realized volatility. Trained on historical Nifty data, cached in memory.
"""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from .market_data import get_historical

logger = logging.getLogger(__name__)

_model: GaussianMixture | None = None
_label_map: dict[int, str] = {}


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    f["ret_20"] = df["close"].pct_change(20)
    f["vol_20"] = df["close"].pct_change().rolling(20).std()
    f["ret_5"] = df["close"].pct_change(5)
    return f.dropna()


def _fit() -> bool:
    global _model, _label_map
    df = get_historical("^NSEI", period="5y", interval="1d")
    if df.empty or len(df) < 100:
        logger.warning("Not enough Nifty data for regime fit")
        return False
    feats = _build_features(df)
    if len(feats) < 50:
        return False
    X = feats.values
    model = GaussianMixture(n_components=3, covariance_type="full", random_state=42, n_init=3)
    model.fit(X)
    preds = model.predict(X)
    # Label: highest mean ret_20 = Bull, lowest = Bear, middle = Sideways
    means = [feats[preds == i]["ret_20"].mean() for i in range(3)]
    order = np.argsort(means)  # ascending
    _label_map = {int(order[0]): "Bear", int(order[1]): "Sideways", int(order[2]): "Bull"}
    _model = model
    logger.info(f"Regime model fit. Labels: {_label_map}")
    return True


def get_current_regime() -> dict:
    """Return {regime, confidence, features, timestamp}."""
    global _model
    if _model is None:
        if not _fit():
            return {"regime": "Unknown", "confidence": 0.0, "features": {}, "fallback": True}
    df = get_historical("^NSEI", period="6mo", interval="1d")
    if df.empty:
        return {"regime": "Unknown", "confidence": 0.0, "features": {}}
    feats = _build_features(df)
    if feats.empty:
        return {"regime": "Unknown", "confidence": 0.0, "features": {}}
    last = feats.iloc[-1:].values
    probs = _model.predict_proba(last)[0]
    idx = int(np.argmax(probs))
    regime = _label_map.get(idx, "Unknown")
    return {
        "regime": regime,
        "confidence": float(probs[idx]),
        "features": {
            "ret_20": round(float(feats.iloc[-1]["ret_20"]) * 100, 2),
            "vol_20": round(float(feats.iloc[-1]["vol_20"]) * 100, 2),
            "ret_5": round(float(feats.iloc[-1]["ret_5"]) * 100, 2),
        },
        "probabilities": {
            _label_map.get(i, f"c{i}"): round(float(probs[i]), 3) for i in range(3)
        },
    }


def get_regime_timeline(days: int = 90) -> list[dict]:
    """Return historical regime sequence for last N days."""
    global _model
    if _model is None and not _fit():
        return []
    df = get_historical("^NSEI", period="1y", interval="1d")
    feats = _build_features(df)
    if feats.empty:
        return []
    preds = _model.predict(feats.values[-days:])
    out = []
    for dt, p in zip(feats.index[-days:], preds):
        out.append({
            "date": dt.strftime("%Y-%m-%d"),
            "regime": _label_map.get(int(p), "Unknown"),
        })
    return out
