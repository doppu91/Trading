"""LightGBM classifier — trains on real Upstox historical data + 18 features.

Single binary classifier (BUY/HOLD) for v1, with model saved to disk.
Inference: load_model() then predict_proba(features) → composite score [0..1].
"""
from __future__ import annotations
import logging
import os
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
MODEL_PATH = MODEL_DIR / "lgbm_classifier.pkl"

_loaded_model = None


def get_model():
    global _loaded_model
    if _loaded_model is None and MODEL_PATH.exists():
        try:
            _loaded_model = joblib.load(MODEL_PATH)
        except Exception as e:
            logger.warning(f"model load fail: {e}")
    return _loaded_model


def predict_score(features_row: dict) -> float | None:
    """Inference: features dict → probability of profitable trade."""
    model = get_model()
    if model is None:
        return None
    x = np.array([[features_row.get(c, 0.0) for c in FEATURE_COLS]])
    if np.isnan(x).any():
        x = np.nan_to_num(x, nan=0.0)
    return float(model.predict_proba(x)[0, 1])


async def _fetch_upstox_df(symbol: str, days_back: int) -> pd.DataFrame:
    candles = await upstox_history(symbol, interval="day", days_back=days_back)
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").set_index("ts")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


async def train(days_back: int = 730, horizon: int = 3, threshold: float = 0.005) -> dict:
    """Train LightGBM classifier on real Upstox historical data.

    Returns metrics dict (n_samples, accuracy, auc, feature_importance).
    """
    coros = [_fetch_upstox_df(s, days_back) for s in WATCHLIST]
    results = await asyncio.gather(*coros, return_exceptions=True)

    X_parts = []
    y_parts = []
    skipped = []
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

    # Time-respecting split: 80% train / 20% test
    n = len(X)
    cut = int(n * 0.8)
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
    acc = float((y_pred == y_te).mean())
    # ROC-AUC manual
    try:
        from sklearn.metrics import roc_auc_score
        auc = float(roc_auc_score(y_te, y_prob)) if len(set(y_te)) > 1 else None
    except Exception:
        auc = None

    importance = sorted(
        [(c, float(v)) for c, v in zip(FEATURE_COLS, model.feature_importances_)],
        key=lambda x: x[1], reverse=True,
    )

    joblib.dump(model, MODEL_PATH)
    global _loaded_model
    _loaded_model = model

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": int(n),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "accuracy": round(acc, 4),
        "auc": round(auc, 4) if auc is not None else None,
        "horizon_days": horizon,
        "label_threshold": threshold,
        "symbols_used": [s for s in WATCHLIST if s not in skipped],
        "symbols_skipped": skipped,
        "feature_importance": importance[:10],
        "model_path": str(MODEL_PATH),
    }

    db = get_db()
    await db.model_runs.insert_one({**metrics})
    return metrics


async def latest_run() -> dict | None:
    db = get_db()
    return await db.model_runs.find_one({}, {"_id": 0}, sort=[("trained_at", -1)])


def model_status() -> dict:
    return {
        "model_exists": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH) if MODEL_PATH.exists() else None,
        "model_size_kb": round(MODEL_PATH.stat().st_size / 1024, 1) if MODEL_PATH.exists() else 0,
        "loaded": _loaded_model is not None,
    }
