"""Position sizing + risk management."""
from __future__ import annotations
import math
from .config import CAPITAL, RISK_PER_TRADE_PCT


def calc_position_size(price: float, atr: float, capital: float = CAPITAL) -> dict:
    """Compute qty based on 1.5% risk per trade, 1.5×ATR stop, 1:2 R:R."""
    if price <= 0 or atr <= 0:
        return {"quantity": 0, "stop_loss": 0, "target": 0, "risk": 0}
    risk_amount = capital * RISK_PER_TRADE_PCT
    stop_distance = atr * 1.5
    qty = math.floor(risk_amount / stop_distance)
    max_qty = math.floor(capital * 0.20 / price)
    qty = min(qty, max_qty)
    sl = round(price - stop_distance, 2)
    target = round(price + (stop_distance * 2), 2)
    return {
        "quantity": max(int(qty), 0),
        "stop_loss": sl,
        "target": target,
        "stop_distance": round(stop_distance, 2),
        "risk": round(risk_amount, 2),
        "rr_ratio": 2.0,
    }
