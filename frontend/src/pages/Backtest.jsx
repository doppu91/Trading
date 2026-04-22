import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { fmtINR, signedClass } from "../lib/format";

export default function Backtest() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [period, setPeriod] = useState("2y");

  const loadLatest = useCallback(async () => {
    try {
      const r = await api.get("/backtest/latest");
      if (!r.data.none) setResult(r.data);
    } catch (e) {
      console.error("loadLatest failed", e);
    }
  }, []);

  useEffect(() => { loadLatest(); }, [loadLatest]);

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.post("/backtest/run", { period });
      setResult(r.data);
      toast.success(`Backtest done: ${r.data.total_trades} trades, net ${fmtINR(r.data.net_pnl)}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)]" data-testid="backtest-page">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <div className="label-xs">Backtest Runner</div>
          <h2 className="text-2xl font-black tracking-tight mt-1">2-Year Historical Simulation</h2>
          <div className="text-xs text-zinc-400 mt-1 font-mono">Applies ₹100/round-trip charges on every simulated trade.</div>
        </div>
        <div className="flex items-center gap-2">
          <select
            data-testid="period-select"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-transparent border border-border px-3 h-9 text-xs font-mono uppercase tracking-wider text-white focus:outline-none"
          >
            <option value="1y">1Y</option>
            <option value="2y">2Y</option>
            <option value="5y">5Y</option>
          </select>
          <button
            data-testid="run-backtest-btn"
            onClick={run}
            disabled={busy}
            className="px-5 h-9 bg-white text-black text-xs font-mono uppercase tracking-wider hover:bg-zinc-200 disabled:opacity-50"
          >
            {busy ? "Running…" : "Run Backtest"}
          </button>
        </div>
      </div>

      {!result && !busy && (
        <div className="p-12 text-center text-zinc-500">
          <div className="text-sm">No results yet. Run a backtest to see performance over historical data.</div>
        </div>
      )}
      {busy && (
        <div className="p-12 text-center text-zinc-400">
          <div className="text-sm font-mono uppercase tracking-wider animate-pulse">Fetching historical data + simulating…</div>
          <div className="text-xs text-zinc-600 mt-2">Usually 15-30 seconds</div>
        </div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-px bg-border border-b border-border">
            {[
              { label: "Total Trades", val: result.total_trades, tid: "bt-total" },
              { label: "Win Rate", val: `${result.win_rate}%`, tid: "bt-win" },
              { label: "Gross P&L", val: fmtINR(result.gross_pnl, 0), cls: signedClass(result.gross_pnl), tid: "bt-gross" },
              { label: "Charges", val: fmtINR(result.total_charges, 0), cls: "text-zinc-300", tid: "bt-charges" },
              { label: "Net P&L", val: fmtINR(result.net_pnl, 0), cls: signedClass(result.net_pnl), tid: "bt-net" },
              { label: "Target Hit Rate", val: `${result.target_hit_rate}%`, tid: "bt-tgt" },
              { label: "Avg Gross/Day", val: fmtINR(result.avg_gross_per_day, 0), tid: "bt-avggross" },
              { label: "Avg Charges/Day", val: fmtINR(result.avg_charges_per_day, 0), tid: "bt-avgcharges" },
              { label: "Avg Net/Day", val: fmtINR(result.avg_net_per_day, 0), cls: signedClass(result.avg_net_per_day), tid: "bt-avgnet" },
              { label: "Sharpe Ratio", val: result.sharpe, tid: "bt-sharpe" },
              { label: "Max Drawdown", val: fmtINR(result.max_drawdown, 0), cls: "text-red-400", tid: "bt-dd" },
              { label: "Trading Days", val: result.trading_days, tid: "bt-days" },
            ].map((m) => (
              <div key={m.label} className="bg-[#09090B] p-4" data-testid={m.tid}>
                <div className="label-xs">{m.label}</div>
                <div className={`font-mono text-lg font-bold mt-1 ${m.cls || "text-white"}`}>{m.val}</div>
              </div>
            ))}
          </div>

          {/* Monthly breakdown */}
          <div className="border-b border-border">
            <div className="px-6 py-4 border-b border-border"><div className="label-xs">Monthly Breakdown</div></div>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Month</th>
                  <th className="text-right">Trades</th>
                  <th className="text-right">Gross</th>
                  <th className="text-right">Charges</th>
                  <th className="text-right">Net</th>
                </tr>
              </thead>
              <tbody>
                {result.monthly.map((m) => (
                  <tr key={m.month}>
                    <td className="font-mono">{m.month}</td>
                    <td className="num">{m.trades}</td>
                    <td className={`num ${signedClass(m.gross)}`}>{fmtINR(m.gross, 0)}</td>
                    <td className="num text-zinc-400">-{fmtINR(m.charges, 0)}</td>
                    <td className={`num font-bold ${signedClass(m.net)}`}>{fmtINR(m.net, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sample trades */}
          <div>
            <div className="px-6 py-4 border-b border-border"><div className="label-xs">Sample Trades · First 100</div></div>
            <div className="overflow-x-auto max-h-[480px]">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Symbol</th>
                    <th className="text-right">Qty</th>
                    <th className="text-right">Entry</th>
                    <th className="text-right">Exit</th>
                    <th className="text-right">Gross</th>
                    <th className="text-right">Charges</th>
                    <th className="text-right">Net</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.sample_trades.map((t, i) => (
                    <tr key={`${t.date}-${t.symbol}-${i}`}>
                      <td className="font-mono text-[11px] text-zinc-400">{t.date}</td>
                      <td className="font-mono">{t.symbol}</td>
                      <td className="num">{t.qty}</td>
                      <td className="num">{t.entry?.toFixed(2)}</td>
                      <td className="num">{t.exit?.toFixed(2)}</td>
                      <td className={`num ${signedClass(t.gross)}`}>{fmtINR(t.gross)}</td>
                      <td className="num text-zinc-400">-{fmtINR(t.charges)}</td>
                      <td className={`num font-bold ${signedClass(t.net)}`}>{fmtINR(t.net)}</td>
                      <td className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">{t.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
