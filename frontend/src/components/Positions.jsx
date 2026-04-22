import React, { useState } from "react";
import { api } from "../lib/api";
import { fmtINR, signedClass } from "../lib/format";
import { toast } from "sonner";

export default function Positions({ positions, onChanged }) {
  const [busy, setBusy] = useState({});
  const close = async (id) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try {
      const r = await api.post(`/paper/close/${id}`);
      const net = r.data.trade.net_pnl;
      toast[net >= 0 ? "success" : "error"](`Closed: Net ${fmtINR(net)}`);
      onChanged?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  };

  const closeAll = async () => {
    try {
      const r = await api.post("/paper/close-all");
      toast.success(`Closed ${r.data.count} positions`);
      onChanged?.();
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div data-testid="positions-panel">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <div className="label-xs">Active Positions</div>
          <div className="font-mono text-xl font-bold mt-1" data-testid="positions-count">{positions?.length ?? 0} / 2</div>
        </div>
        <button
          onClick={closeAll}
          data-testid="close-all-btn"
          disabled={!positions?.length}
          className="px-3 h-8 text-[11px] font-mono uppercase tracking-wider border border-red-500/40 text-red-400 hover:bg-red-500/10 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Close All
        </button>
      </div>
      {positions?.length ? (
        <table className="tbl">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Entry</th>
              <th className="text-right">LTP</th>
              <th className="text-right">SL</th>
              <th className="text-right">Target</th>
              <th className="text-right">Unrealized</th>
              <th className="text-right">Signal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id} data-testid={`position-row-${p.symbol}`}>
                <td className="font-mono font-semibold">{p.symbol}</td>
                <td className="num">{p.qty}</td>
                <td className="num">{p.entry_price?.toFixed(2)}</td>
                <td className="num">{p.ltp?.toFixed(2)}</td>
                <td className="num text-red-400">{p.stop_loss?.toFixed(2)}</td>
                <td className="num text-emerald-400">{p.target?.toFixed(2)}</td>
                <td className={`num font-bold ${signedClass(p.unrealized_pnl)}`}>{fmtINR(p.unrealized_pnl)}</td>
                <td className="num text-zinc-400">{p.signal_score?.toFixed(2)}</td>
                <td className="num">
                  <button
                    disabled={busy[p.id]}
                    onClick={() => close(p.id)}
                    data-testid={`close-pos-${p.symbol}`}
                    className="px-2 h-7 text-[10px] font-mono uppercase tracking-wider border border-border hover:bg-zinc-800/50"
                  >
                    {busy[p.id] ? "..." : "Close"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="p-8 text-center text-zinc-500 text-sm">No open positions. Fire signals above to simulate trades.</div>
      )}
    </div>
  );
}
