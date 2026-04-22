import pandas as pd
import numpy as np
from alphadesk.signals import get_signal_for_symbol
from alphadesk.market_data import get_historical

INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.01
CHARGE_PER_TRADE = 90


def run_backtest(symbol="RELIANCE"):
    df = get_historical(symbol, period="2y")
    df = df.reset_index()

    capital = INITIAL_CAPITAL
    equity_curve = []
    trades = []

    position = None
    entry_price = 0
    qty = 0

    wins = 0
    total_trades = 0

    for i in range(50, len(df)):
        data = df.iloc[:i]

        signal = get_signal_for_symbol(symbol)

        price = df.iloc[i]["close"]

        # ───────── ENTRY ─────────
        if position is None and signal["action"] in ["BUY", "STRONG_BUY"]:
            position = "LONG"
            entry_price = price

            risk_amount = capital * RISK_PER_TRADE
            qty = int(risk_amount / (price * 0.01))  # 1% move assumption

        # ───────── EXIT ─────────
        elif position == "LONG":
            exit_flag = False

            if signal["action"] == "EXIT":
                exit_flag = True
                reason = "signal"

            elif price <= entry_price * 0.99:
                exit_flag = True
                reason = "sl"

            elif price >= entry_price * 1.03:
                exit_flag = True
                reason = "target"

            if exit_flag:
                pnl = (price - entry_price) * qty
                net = pnl - CHARGE_PER_TRADE

                capital += net
                equity_curve.append(capital)

                trades.append({
                    "entry": entry_price,
                    "exit": price,
                    "qty": qty,
                    "net": net,
                    "reason": reason
                })

                total_trades += 1
                if net > 0:
                    wins += 1

                position = None

        equity_curve.append(capital)

    # ───────── METRICS ─────────

    equity_curve = np.array(equity_curve)

    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min() * 100

    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    total_pnl = capital - INITIAL_CAPITAL

    returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0

    print("\n--- Backtest Results ---")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Net PnL: {total_pnl:.2f}")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")

    return trades


if __name__ == "__main__":
    run_backtest("RELIANCE")
