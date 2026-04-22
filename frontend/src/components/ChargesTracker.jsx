import React from "react";
import { fmtINR } from "../lib/format";

export default function ChargesTracker({ charges }) {
  if (!charges) return null;
  const rows = [
    ["Brokerage", charges.brokerage],
    ["STT", charges.stt],
    ["Exchange", charges.exchange_txn],
    ["SEBI", charges.sebi],
    ["Stamp", charges.stamp],
    ["GST", charges.gst],
  ];
  return (
    <div className="p-6 h-full" data-testid="charges-tracker">
      <div className="flex items-center justify-between">
        <div className="label-xs">Charges Tracker — Today</div>
        <div className="font-mono text-xs text-zinc-400">₹100/rt est.</div>
      </div>
      <div className="mt-4 space-y-1">
        {rows.map(([label, v]) => (
          <div key={label} className="flex items-center justify-between font-mono text-[12px] py-1.5 border-b border-border">
            <span className="text-zinc-400 uppercase tracking-wider">{label}</span>
            <span className="text-zinc-200" data-testid={`charge-${label.toLowerCase()}`}>{fmtINR(v || 0)}</span>
          </div>
        ))}
        <div className="flex items-center justify-between font-mono text-sm pt-3">
          <span className="text-white font-bold uppercase tracking-wider">Total</span>
          <span className="text-white font-bold" data-testid="charge-total">{fmtINR(charges.total || 0)}</span>
        </div>
      </div>
    </div>
  );
}
