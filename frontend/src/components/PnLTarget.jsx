import React from "react";
import { fmtINR, signedClass } from "../lib/format";

/**
 * Target progress — gross and net vs daily target
 */
export default function PnLTarget({ today, targetGross = 4500, targetNet = 4000 }) {
  const gross = today?.gross_pnl ?? 0;
  const charges = today?.total_charges ?? 0;
  const net = today?.net_pnl ?? 0;
  const pct = Math.min(100, Math.max(0, (gross / targetGross) * 100));

  return (
    <div className="p-6" data-testid="pnl-target">
      <div className="flex items-center justify-between">
        <div className="label-xs">Today · Gross → Net</div>
        <div className="label-xs">Target ₹{targetGross.toLocaleString("en-IN")} gross</div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-px bg-border">
        <div className="bg-[#09090B] p-4">
          <div className="label-xs">Gross P&amp;L</div>
          <div className={`font-mono text-2xl font-bold mt-2 ${signedClass(gross)}`} data-testid="today-gross">
            {fmtINR(gross)}
          </div>
        </div>
        <div className="bg-[#09090B] p-4">
          <div className="label-xs">Charges</div>
          <div className="font-mono text-2xl font-bold mt-2 text-zinc-300" data-testid="today-charges">
            -{fmtINR(charges)}
          </div>
        </div>
        <div className="bg-[#09090B] p-4">
          <div className="label-xs">Net P&amp;L</div>
          <div className={`font-mono text-2xl font-bold mt-2 ${signedClass(net)}`} data-testid="today-net">
            {fmtINR(net)}
          </div>
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-[11px] font-mono mb-2">
          <span className="text-zinc-400 uppercase tracking-wider">Progress to target</span>
          <span className="text-white">{pct.toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-zinc-900 border border-border overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${gross >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
