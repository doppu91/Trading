import React from "react";

export default function RegimeTimeline({ timeline }) {
  if (!timeline?.length) {
    return (
      <div className="p-6" data-testid="regime-timeline">
        <div className="label-xs">Regime Timeline · 90D</div>
        <div className="mt-3 text-zinc-500 text-xs">No data</div>
      </div>
    );
  }
  const color = {
    Bull: "bg-emerald-500",
    Bear: "bg-red-500",
    Sideways: "bg-amber-500",
    Unknown: "bg-zinc-700",
  };
  return (
    <div className="p-6" data-testid="regime-timeline">
      <div className="flex items-center justify-between">
        <div className="label-xs">Regime Timeline · 90D</div>
        <div className="flex items-center gap-3 text-[10px] font-mono uppercase tracking-wider">
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500"></span>Bull</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-amber-500"></span>Side</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500"></span>Bear</span>
        </div>
      </div>
      <div className="mt-4 flex items-end gap-[2px] h-16">
        {timeline.map((t) => (
          <div
            key={t.date}
            className={`flex-1 ${color[t.regime] || color.Unknown} hover:opacity-70 transition-opacity`}
            title={`${t.date} — ${t.regime}`}
            style={{ height: "100%" }}
          />
        ))}
      </div>
      <div className="flex items-center justify-between mt-2 font-mono text-[10px] text-zinc-500">
        <span>{timeline[0]?.date}</span>
        <span>{timeline[timeline.length - 1]?.date}</span>
      </div>
    </div>
  );
}
