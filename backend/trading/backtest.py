# alphadesk/backtest.py

from __future__ import annotations
import numpy as np
import pandas as pd

from alphadesk.market_data import get_historical
from alphadesk.signals import get_signal_for_symbol

# ─────────────────────────────────────────────
# ⚙️ CONFIG
# ─────────────────────────────────────────────

INITIAL_CAPITAL = 1_00_000
RISK_PER_TRADE = 0.01        # 1%
CHARGES_PER_TRADE = 90       # round-turn estimate
MIN_HOLD = 3                 # candles
MAX_HOLD = 15                # candles
TIME_STOP_LOSS = 8           # if losing after N candles, exit
QUALITY_TECH_MIN = 0.60      # filter weak signals
SYMBOL = "RELIANCE"

# ─────────────────────────────────────────────
# 📊 HELPERS
# ─────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ─────────────────────────────────────────────
# 🚀 BACKTEST
# ─────────────────────────────────────────────

def run_backtest(symbol: str = SYMBOL, period: str = "5y"):
    df = get_historical(symbol, period=period, interval="1d")
    if df is None or df.empty:
        raise ValueError("No data returned. Fix market_data first.")

    df = df.copy().reset_index(drop=True)
    df["atr"] = atr(df)

    capital = INITIAL_CAPITAL
    equity_curve = [capital]

    position = None
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    qty = 0
    trade_duration = 0

    wins = 0
    losses = 0
    total_trades = 0

    trades = []

    # start after enough candles for indicators
    for i in range(60, len(df)):
        price = float(df.loc[i, "close"])
        cur_atr = float(df.loc[i, "atr"]) if not np.isnan(df.loc[i, "atr"]) else None

        # get signal on data till i (no lookahead)
        signal = get_signal_for_symbol(symbol)
        action = signal.get("action", "HOLD")
        tech = signal.get("layers", {}).get("technical", 0.5)

        # ───────── ENTRY ─────────
        if position is None:
            # quality filter (cuts trades)
            if tech < QUALITY_TECH_MIN:
                equity_curve.append(capital)
                continue

            if action in ["BUY", "STRONG_BUY"] and cur_atr:
                risk_amt = capital * RISK_PER_TRADE
                # assume 1 ATR stop
                stop_dist = cur_atr
                qty = max(1, int(risk_amt / stop_dist))

                entry_price = price
                sl = entry_price - 1.0 * cur_atr
                tp = entry_price + 3.5 * cur_atr   # larger RR
                position = "LONG"
                trade_duration = 0

        # ───────── MANAGE / EXIT ─────────
        elif position == "LONG":
            trade_duration += 1

            # current PnL
            pnl = (price - entry_price) * qty

            # 1) minimum hold
            if trade_duration < MIN_HOLD:
                equity_curve.append(capital)
                continue

            # 2) move to breakeven
            if price - entry_price > 1.0 * cur_atr:
                sl = max(sl, entry_price)

            # 3) trailing stop
            if price - entry_price > 2.0 * cur_atr:
                sl = max(sl, price - 1.0 * cur_atr)

            # 4) kill slow losers
            if trade_duration > TIME_STOP_LOSS and pnl < 0:
                reason = "time_sl"
                exit_flag = True
            # 5) max hold
            elif trade_duration > MAX_HOLD:
                reason = "time_exit"
                exit_flag = True
            # 6) SL / TP
            elif price <= sl:
                reason = "sl"
                exit_flag = True
            elif price >= tp:
                reason = "target"
                exit_flag = True
            # 7) signal exit
            elif action == "EXIT":
                reason = "signal"
                exit_flag = True
            else:
                exit_flag = False

            if exit_flag:
                gross = (price - entry_price) * qty
                net = gross - CHARGES_PER_TRADE
                capital += net

                trades.append({
                    "date": i,
                    "symbol": symbol,
                    "qty": qty,
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "gross": round(gross, 2),
                    "charges": CHARGES_PER_TRADE,
                    "net": round(net, 2),
                    "reason": reason
                })

                total_trades += 1
                if net > 0:
                    wins += 1
                else:
                    losses += 1

                # reset
                position = None
                entry_price = sl = tp = 0.0
                qty = 0
                trade_duration = 0

        equity_curve.append(capital)

    # ───────── METRICS ─────────
    equity = np.array(equity_curve, dtype=float)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min() * 100)

    total_pnl = float(capital - INITIAL_CAPITAL)
    win_rate = (wins / total_trades * 100) if total_trades else 0.0

    returns = pd.Series(equity).pct_change().dropna()
    sharpe = float((returns.mean() / returns.std()) * np.sqrt(252)) if returns.std() != 0 else 0.0

    # charges summary
    total_charges = total_trades * CHARGES_PER_TRADE
    gross_pnl = sum(t["gross"] for t in trades)

    print("\n--- Backtest Results ---")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Gross PnL: {gross_pnl:.2f}")
    print(f"Total Charges: {total_charges:.2f}")
    print(f"Net PnL: {total_pnl:.2f}")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    if len(equity) > 1:
        days = len(equity)
        print(f"Avg Net Per Day: {total_pnl / days:.2f}")

    print("\nSample Trades (Top 5):")
    for t in trades[:5]:
        print(t)

    return {
        "trades": trades,
        "equity": equity,
        "metrics": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "gross_pnl": gross_pnl,
            "charges": total_charges,
            "net_pnl": total_pnl,
            "max_dd": max_dd,
            "sharpe": sharpe,
        }
    }


if __name__ == "__main__":
    run_backtest(SYMBOL, period="5y")
