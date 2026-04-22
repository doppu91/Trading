import React from "react";
import { signedClass, fmtPct } from "../lib/format";

export default function GlobalCues({ cues }) {
  if (!cues) return null;
  const items = [
    { key: "sp500", label: "S&P 500" },
    { key: "nifty", label: "Nifty 50" },
    { key: "india_vix", label: "India VIX" },
    { key: "crude", label: "Crude" },
    { key: "usdinr", label: "USDINR" },
  ];
  return (
    <div className="p-6 h-full" data-testid="global-cues">
      <div className="label-xs">Global Cues · Overnight</div>
      <div className="mt-4 grid grid-cols-1 gap-px bg-border">
        {items.map(({ key, label }) => {
          const q = cues[key];
          if (!q) return (
            <div key={key} className="bg-[#09090B] p-3 flex items-center justify-between">
              <span className="text-zinc-500 text-xs font-mono uppercase tracking-wider">{label}</span>
              <span className="text-zinc-600 font-mono text-sm">—</span>
            </div>
          );
          return (
            <div key={key} className="bg-[#09090B] p-3 flex items-center justify-between" data-testid={`cue-${key}`}>
              <span className="text-zinc-300 text-xs font-mono uppercase tracking-wider">{label}</span>
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-sm">{q.price?.toLocaleString("en-IN")}</span>
                <span className={`font-mono text-xs ${signedClass(q.change_pct)}`}>{fmtPct(q.change_pct)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
