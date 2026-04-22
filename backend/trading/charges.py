"""Upstox intraday charge calculator — exact NSE formula."""
from dataclasses import dataclass


@dataclass
class ChargeBreakdown:
    brokerage: float
    stt: float
    exchange_txn: float
    sebi: float
    stamp: float
    gst: float
    total: float

    def to_dict(self) -> dict:
        return {
            "brokerage": round(self.brokerage, 2),
            "stt": round(self.stt, 2),
            "exchange_txn": round(self.exchange_txn, 2),
            "sebi": round(self.sebi, 2),
            "stamp": round(self.stamp, 2),
            "gst": round(self.gst, 2),
            "total": round(self.total, 2),
        }


def calc_charges(buy_price: float, sell_price: float, qty: int) -> ChargeBreakdown:
    """Calculate Upstox intraday round-trip charges.

    Formula:
      Brokerage:     ₹20/order × 2 orders  (flat)
      STT:           0.025% on sell turnover
      Exchange:      0.00297% on total turnover (both sides)
      SEBI:          ₹10 per crore on total turnover
      Stamp:         0.003% on buy turnover
      GST:           18% on (brokerage + exchange + sebi)
    """
    buy_turnover = buy_price * qty
    sell_turnover = sell_price * qty
    total_turnover = buy_turnover + sell_turnover

    brokerage = min(20.0, buy_turnover * 0.0005) + min(20.0, sell_turnover * 0.0005)
    stt = sell_turnover * 0.00025
    exchange_txn = total_turnover * 0.0000297
    sebi = total_turnover * 10 / 1e7
    stamp = buy_turnover * 0.00003
    gst = (brokerage + exchange_txn + sebi) * 0.18

    total = brokerage + stt + exchange_txn + sebi + stamp + gst
    return ChargeBreakdown(brokerage, stt, exchange_txn, sebi, stamp, gst, total)


def estimate_charge_for_value(trade_value: float) -> float:
    """Quick estimate for a round trip at given notional (assume flat price)."""
    if trade_value <= 0:
        return 0.0
    # assume price move ~0.5% between buy and sell
    buy = trade_value
    sell = trade_value * 1.005
    qty = 1
    return calc_charges(buy, sell, qty).total + (buy + sell) * 0  # qty=1 so use turnover math
