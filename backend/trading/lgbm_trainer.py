"""LightGBM classifier — supports daily (shared) and per-symbol intraday models.

Models are saved to /app/backend/models_data/{key}.pkl where key is:
- 'lgbm_classifier'        — daily, all symbols pooled
- 'intraday_RELIANCE' etc  — per-symbol intraday (30-min bars)
"""
from __future__ import annotations
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
from .feature_engine import FEATURE_COLS, compute_features, build_labels
from .upstox_client import get_historical as upstox_history
from .config import WATCHLIST
from .db import get_db

logger = logging.getLogger(__name__)

MODEL_DIR = Path("/app/backend/models_data")
MODEL_DIR.mkdir(exist_ok=True)
DEFAULT_KEY = "lgbm_classifier"

_loaded_models: dict[str, object] = {}


def _model_path(key: str | None = None) -> Path:
    return MODEL_DIR / f"{key or DEFAULT_KEY}.pkl"


def get_model(key: str | None = None):
    k = key or DEFAULT_KEY
    if k in _loaded_models:
        return _loaded_models[k]
    p = _model_path(k)
    if p.exists():
        try:
            _loaded_models[k] = joblib.load(p)
            return _loaded_models[k]
        except Exception as e:
            logger.warning(f"model load fail {k}: {e}")
    return None


def predict_score(features_row: dict, model_key: str | None = None) -> float | None:
    model = get_model(model_key)
    if model is None:
        return None
    x = np.array([[features_row.get(c, 0.0) for c in FEATURE_COLS]])
    if np.isnan(x).any():
        x = np.nan_to_num(x, nan=0.0)
    return float(model.predict_proba(x)[0, 1])


async def _fetch_upstox_df(symbol: str, days_back: int, interval: str = "day") -> pd.DataFrame:
    candles = await upstox_history(symbol, interval=interval, days_back=days_back)
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").set_index("ts")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _train_one(X: np.ndarray, y: np.ndarray, key: str) -> dict:
    n = len(X)
    cut = max(20, int(n * 0.8))
    X_tr, X_te = X[:cut], X[cut:]
    y_tr, y_te = y[:cut], y[cut:]
    model = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=6,
        num_leaves=31, min_child_samples=20, random_state=42,
        verbose=-1,
    )
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)
    y_prob = model.predict_proba(X_te)[:, 1]
    acc = float((y_pred == y_te).mean()) if len(y_te) else 0.0
    try:
        from sklearn.metrics import roc_auc_score
        auc = float(roc_auc_score(y_te, y_prob)) if len(set(y_te)) > 1 else None
    except Exception:
        auc = None
    p = _model_path(key)
    joblib.dump(model, p)
    _loaded_models[key] = model
    importance = sorted(
        [(c, float(v)) for c, v in zip(FEATURE_COLS, model.feature_importances_)],
        key=lambda x: x[1], reverse=True,
    )[:5]
    return {
        "key": key,
        "n_samples": int(n),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "accuracy": round(acc, 4),
        "auc": round(auc, 4) if auc is not None else None,
        "top_features": importance,
    }


async def train(days_back: int = 730, horizon: int = 3, threshold: float = 0.005) -> dict:
    """Train pooled DAILY classifier on all watchlist symbols."""
    coros = [_fetch_upstox_df(s, days_back, "day") for s in WATCHLIST]
    results = await asyncio.gather(*coros, return_exceptions=True)

    X_parts, y_parts, skipped = [], [], []
    for sym, res in zip(WATCHLIST, results):
        if isinstance(res, pd.DataFrame) and len(res) > 60:
            feats = compute_features(res)
            labels = build_labels(res, horizon=horizon, threshold=threshold)
            combined = feats.copy()
            combined["_y"] = labels
            combined = combined.dropna()
            if len(combined) > 30:
                X_parts.append(combined[FEATURE_COLS])
                y_parts.append(combined["_y"])
            else:
                skipped.append(sym)
        else:
            skipped.append(sym)

    if not X_parts:
        return {"error": "No training data fetched. Check Upstox token."}

    X = pd.concat(X_parts).values
    y = pd.concat(y_parts).values
    metrics = _train_one(X, y, DEFAULT_KEY)
    metrics.update({
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "mode": "daily_pooled",
        "horizon_days": horizon,
        "label_threshold": threshold,
        "symbols_used": [s for s in WATCHLIST if s not in skipped],
        "symbols_skipped": skipped,
    })
    await get_db().model_runs.insert_one({**metrics})
    return metrics


async def train_intraday_per_symbol(days_back: int = 90, horizon: int = 6,
                                    threshold: float = 0.003,
                                    interval: str = "30minute") -> dict:
    """Train ONE LightGBM model per symbol on intraday bars.
    horizon: bars to look ahead (6 × 30min = 3h forward return)
    threshold: smaller (0.3%) since intraday moves are smaller.
    """
    results: list[dict] = []
    skipped: list[str] = []
    coros = [_fetch_upstox_df(s, days_back, interval) for s in WATCHLIST]
    fetched = await asyncio.gather(*coros, return_exceptions=True)

    for sym, df in zip(WATCHLIST, fetched):
        if not isinstance(df, pd.DataFrame) or len(df) < 100:
            skipped.append(sym)
            continue
        feats = compute_features(df)
        labels = build_labels(df, horizon=horizon, threshold=threshold)
        combined = feats.copy()
        combined["_y"] = labels
        combined = combined.dropna()
        if len(combined) < 50:
            skipped.append(sym)
            continue
        X = combined[FEATURE_COLS].values
        y = combined["_y"].values
        m = _train_one(X, y, f"intraday_{sym}")
        m["symbol"] = sym
        results.append(m)

    summary = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "mode": "intraday_per_symbol",
        "interval": interval,
        "horizon_bars": horizon,
        "label_threshold": threshold,
        "models_trained": len(results),
        "symbols_skipped": skipped,
        "per_model": results,
        "avg_accuracy": round(sum(r["accuracy"] for r in results) / len(results), 4) if results else 0,
        "avg_auc": round(sum(r["auc"] for r in results if r["auc"] is not None) /
                         max(1, sum(1 for r in results if r["auc"] is not None)), 4) if results else None,
    }
    await get_db().model_runs.insert_one({**summary})
    return summary


async def latest_run() -> dict | None:
    return await get_db().model_runs.find_one({}, {"_id": 0}, sort=[("trained_at", -1)])


def model_status() -> dict:
    files = sorted(MODEL_DIR.glob("*.pkl"))
    return {
        "model_dir": str(MODEL_DIR),
        "models": [
            {"key": p.stem, "size_kb": round(p.stat().st_size / 1024, 1)}
            for p in files
        ],
        "loaded_keys": list(_loaded_models.keys()),
    }
