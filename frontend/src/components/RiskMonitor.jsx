import React from "react";
import { fmtINR } from "../lib/format";

export default function RiskMonitor({ risk }) {
  if (!risk) return null;
  const pct = risk.loss_used_pct || 0;
  const barColor = pct > 70 ? "bg-red-500" : pct > 40 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="p-6 h-full" data-testid="risk-monitor">
      <div className="flex items-center justify-between">
        <div className="label-xs">Risk Monitor</div>
        <span className={`pill ${risk.trades_allowed ? "text-emerald-400 border-emerald-500/40" : "text-red-400 border-red-500/40"}`} data-testid="risk-status">
          {risk.trades_allowed ? "TRADES OK" : "BLOCKED"}
        </span>
      </div>
      {!risk.trades_allowed && (
        <div className="mt-2 text-[11px] font-mono text-red-400" data-testid="risk-reason">{risk.block_reason}</div>
      )}

      <div className="mt-5">
        <div className="flex items-center justify-between label-xs">
          <span>Daily Loss Cap</span>
          <span>{fmtINR(risk.loss_used)} / {fmtINR(risk.daily_loss_cap)}</span>
        </div>
        <div className="h-2 bg-zinc-900 border border-border mt-2">
          <div className={`h-full ${barColor}`} style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-px bg-border mt-5">
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Positions</div>
          <div className="font-mono text-sm mt-1">{risk.open_positions} / {risk.max_positions}</div>
        </div>
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Capital</div>
          <div className="font-mono text-sm mt-1">{fmtINR(risk.capital, 0)}</div>
        </div>
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">VIX</div>
          <div className={`font-mono text-sm mt-1 ${risk.vix > risk.vix_cap ? "text-red-400" : "text-zinc-200"}`}>
            {risk.vix?.toFixed(2) ?? "—"} / {risk.vix_cap}
          </div>
        </div>
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Regime</div>
          <div className="font-mono text-sm mt-1">{risk.regime || "—"}</div>
        </div>
      </div>
    </div>
  );
}
