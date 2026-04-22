import React, { useState } from "react";
import { api } from "../lib/api";
import { fmtINR, fmtPct, signedClass } from "../lib/format";
import { toast } from "sonner";

export default function SignalScanner({ signals, threshold = 0.68, onOpened }) {
  const [busy, setBusy] = useState({});

  const openPaper = async (symbol) => {
    setBusy((b) => ({ ...b, [symbol]: true }));
    try {
      const r = await api.post("/paper/open", { symbol });
      toast.success(`Paper position opened: ${r.data.position.qty} ${symbol} @ ₹${r.data.position.entry_price}`);
      onOpened?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setBusy((b) => ({ ...b, [symbol]: false }));
    }
  };

  return (
    <div className="h-full" data-testid="signal-scanner">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div className="label-xs">Signal Scanner</div>
        <div className="label-xs">Threshold ≥ {threshold.toFixed(2)}</div>
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="text-right">Price</th>
            <th className="text-right">Change</th>
            <th className="text-right">Tech</th>
            <th className="text-right">Sent</th>
            <th className="text-right">FII</th>
            <th className="text-right">GEX</th>
            <th className="text-right">Global</th>
            <th className="text-right">Score</th>
            <th className="text-right">Action</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(signals || []).map((s) => {
            const meets = s.meets_threshold;
            return (
              <tr key={s.symbol} data-testid={`signal-row-${s.symbol}`}>
                <td className="font-mono font-semibold">
                  <span className="inline-flex items-center gap-1.5">
                    {s.symbol}
                    {s.ml_used && (
                      <span
                        title="LightGBM-scored"
                        className="px-1.5 py-0.5 text-[9px] font-bold tracking-wider border border-emerald-500/50 text-emerald-400 bg-emerald-500/10"
                        data-testid={`ml-badge-${s.symbol}`}
                      >ML</span>
                    )}
                  </span>
                </td>
                <td className="num">{s.price ? s.price.toFixed(2) : "—"}</td>
                <td className={`num ${signedClass(s.change_pct)}`}>{fmtPct(s.change_pct)}</td>
                <td className="num text-zinc-300">{s.layers.technical.toFixed(2)}</td>
                <td className="num text-zinc-300">{s.layers.sentiment.toFixed(2)}</td>
                <td className="num text-zinc-300">{s.layers.fii_flow.toFixed(2)}</td>
                <td className="num text-zinc-300">{s.layers.gex.toFixed(2)}</td>
                <td className="num text-zinc-300">{s.layers.global_cue.toFixed(2)}</td>
                <td className={`num font-bold ${meets ? "text-emerald-400" : "text-zinc-400"}`}>{s.composite.toFixed(3)}</td>
                <td className="num">
                  <span className={`pill ${meets ? "text-emerald-400 border-emerald-500/40" : "text-zinc-500"}`}>{s.action}</span>
                </td>
                <td className="num">
                  <button
                    disabled={!meets || busy[s.symbol]}
                    onClick={() => openPaper(s.symbol)}
                    data-testid={`open-paper-${s.symbol}`}
                    className={`px-3 h-7 text-[11px] font-mono uppercase tracking-wider border transition-colors ${
                      meets ? "bg-white text-black border-white hover:bg-zinc-200" : "border-border text-zinc-600 cursor-not-allowed"
                    }`}
                  >
                    {busy[s.symbol] ? "..." : "Paper"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
