import React from "react";
import { fmtINR, signedClass } from "../lib/format";

export default function TradesTable({ trades }) {
  return (
    <div data-testid="trades-table">
      <div className="px-6 py-4 border-b border-border">
        <div className="label-xs">Trade History</div>
        <div className="font-mono text-xl font-bold mt-1">{trades?.length ?? 0} trades</div>
      </div>
      {trades?.length ? (
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th className="text-right">Qty</th>
                <th className="text-right">Entry</th>
                <th className="text-right">Exit</th>
                <th className="text-right">Gross</th>
                <th className="text-right">Chg</th>
                <th className="text-right">Net</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const dt = new Date(t.closed_at);
                return (
                  <tr key={t.id} data-testid={`trade-row-${t.id}`}>
                    <td className="font-mono text-[11px] text-zinc-400">{dt.toLocaleTimeString("en-IN", { hour12: false })}</td>
                    <td className="font-mono font-semibold">{t.symbol}</td>
                    <td className="num">{t.qty}</td>
                    <td className="num">{t.entry_price?.toFixed(2)}</td>
                    <td className="num">{t.exit_price?.toFixed(2)}</td>
                    <td className={`num ${signedClass(t.gross_pnl)}`}>{fmtINR(t.gross_pnl)}</td>
                    <td className="num text-zinc-400">-{fmtINR(t.charges?.total)}</td>
                    <td className={`num font-bold ${signedClass(t.net_pnl)}`}>{fmtINR(t.net_pnl)}</td>
                    <td className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">{t.reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-8 text-center text-zinc-500 text-sm">No closed trades yet.</div>
      )}
    </div>
  );
}
