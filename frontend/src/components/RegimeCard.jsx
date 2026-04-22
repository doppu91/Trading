import React from "react";
import { regimeColor } from "../lib/format";

export default function RegimeCard({ regime }) {
  if (!regime) return null;
  const c = regimeColor(regime.regime);
  const feats = regime.features || {};
  const probs = regime.probabilities || {};
  return (
    <div className="p-6 h-full" data-testid="regime-card">
      <div className="label-xs">HMM Regime</div>
      <div className="flex items-center gap-3 mt-3">
        <span className={`w-2.5 h-2.5 rounded-full live-dot ${c.dot}`}></span>
        <div className={`text-3xl font-black tracking-tight ${c.text}`} data-testid="regime-label">
          {regime.regime || "—"}
        </div>
      </div>
      <div className="mt-2 font-mono text-xs text-zinc-400">
        Confidence {((regime.confidence || 0) * 100).toFixed(0)}%
      </div>

      <div className="grid grid-cols-3 gap-px bg-border mt-5">
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Ret 20D</div>
          <div className="font-mono text-sm mt-1">{feats.ret_20 ?? "—"}%</div>
        </div>
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Vol 20D</div>
          <div className="font-mono text-sm mt-1">{feats.vol_20 ?? "—"}%</div>
        </div>
        <div className="bg-[#09090B] p-3">
          <div className="label-xs">Ret 5D</div>
          <div className="font-mono text-sm mt-1">{feats.ret_5 ?? "—"}%</div>
        </div>
      </div>

      <div className="mt-5 space-y-1.5">
        {Object.entries(probs).map(([k, v]) => (
          <div key={k} className="flex items-center gap-3 font-mono text-[11px]">
            <span className="w-16 text-zinc-400 uppercase tracking-wider">{k}</span>
            <div className="flex-1 h-1 bg-zinc-900">
              <div
                className={k === "Bull" ? "bg-emerald-500 h-full" : k === "Bear" ? "bg-red-500 h-full" : "bg-amber-500 h-full"}
                style={{ width: `${v * 100}%` }}
              />
            </div>
            <span className="text-zinc-300 w-10 text-right">{(v * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
