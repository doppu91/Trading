from __future__ import annotations
import numpy as np
import pandas as pd

from alphadesk.market_data import get_historical
from alphadesk.signals import get_signal_for_symbol

# ─────────────────────────────────────────────
# ⚙️ CONFIG
# ─────────────────────────────────────────────

INITIAL_CAPITAL = 1000000
RISK_PER_TRADE = 0.02
CHARGES = 90

MIN_HOLD = 3
TIME_STOP = 10
MAX_HOLD = 20

TECH_THRESHOLD = 0.6
SYMBOL = "RELIANCE"

# ─────────────────────────────────────────────
# 📊 ATR
# ─────────────────────────────────────────────

def atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ─────────────────────────────────────────────
# 🚀 BACKTEST
# ─────────────────────────────────────────────

def run_backtest(symbol=SYMBOL):

    df = get_historical(symbol, period="5y")
    df = df.reset_index(drop=True)

    df["ATR"] = atr(df)

    capital = INITIAL_CAPITAL
    equity_curve = [capital]

    position = None
    entry = 0
    sl = 0
    tp = 0
    qty = 0
    duration = 0

    trades = []
    wins = 0
    total = 0

    for i in range(60, len(df)):

        price = df.loc[i, "close"]
        atr_val = df.loc[i, "ATR"]

        if np.isnan(atr_val):
            equity_curve.append(capital)
            continue

        signal = get_signal_for_symbol(symbol)
        action = signal.get("action", "HOLD")
        tech = signal.get("layers", {}).get("technical", 0.5)

        # ───────── ENTRY ─────────
        if position is None:

            # 🔥 QUALITY FILTER (reduces trades)
            if tech < TECH_THRESHOLD:
                equity_curve.append(capital)
                continue

            if action in ["BUY", "STRONG_BUY"]:

                risk_amt = capital * RISK_PER_TRADE
                qty = int(risk_amt / atr_val)

                # avoid tiny trades
                if qty <= 0:
                    equity_curve.append(capital)
                    continue

                entry = price
                sl = entry - atr_val
                tp = entry + 4 * atr_val  # 🔥 bigger RR

                position = "LONG"
                duration = 0

        # ───────── EXIT ─────────
        elif position == "LONG":

            duration += 1
            pnl = (price - entry) * qty

            exit_flag = False

            # 🔥 Minimum hold
            if duration < MIN_HOLD:
                equity_curve.append(capital)
                continue

            # 🔥 Breakeven
            if pnl > atr_val:
                sl = max(sl, entry)

            # 🔥 Trailing
            if pnl > 2 * atr_val:
                sl = max(sl, price - atr_val)

            # 🔥 Kill slow losers
            if duration > TIME_STOP and pnl < 0:
                reason = "time_sl"
                exit_flag = True

            # 🔥 Max hold exit
            elif duration > MAX_HOLD:
                reason = "time_profit"
                exit_flag = True

            # SL / TP
            elif price <= sl:
                reason = "sl"
                exit_flag = True

            elif price >= tp:
                reason = "target"
                exit_flag = True

            elif action == "EXIT":
                reason = "signal"
                exit_flag = True

            if exit_flag:

                gross = (price - entry) * qty
                net = gross - CHARGES

                capital += net

                trades.append({
                    "entry": round(entry, 2),
                    "exit": round(price, 2),
                    "qty": qty,
                    "gross": round(gross, 2),
                    "net": round(net, 2),
                    "reason": reason
                })

                total += 1
                if net > 0:
                    wins += 1

                position = None

        equity_curve.append(capital)

    # ───────── METRICS ─────────

    equity = np.array(equity_curve)

    # 🔥 FIXED DRAWDOWN
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = dd.min() * 100

    total_pnl = capital - INITIAL_CAPITAL
    win_rate = (wins / total * 100) if total > 0 else 0

    gross_pnl = sum(t["gross"] for t in trades)
    total_charges = total * CHARGES

    returns = pd.Series(equity).pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0

    print("\n--- Backtest Results ---")
    print(f"Total Trades: {total}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Gross PnL: {gross_pnl:.2f}")
    print(f"Total Charges: {total_charges:.2f}")
    print(f"Net PnL: {total_pnl:.2f}")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Avg Net Per Day: {total_pnl / len(equity):.2f}")

    print("\nSample Trades:")
    for t in trades[:5]:
        print(t)

    return trades


if __name__ == "__main__":
    run_backtest()
