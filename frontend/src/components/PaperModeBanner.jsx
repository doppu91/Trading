import React from "react";
import { Warning } from "@phosphor-icons/react";

export default function PaperModeBanner({ active }) {
  if (!active) return null;
  return (
    <div className="paper-stripes border-b border-amber-500/40 px-6 py-2" data-testid="paper-mode-banner">
      <div className="flex items-center gap-3 text-amber-400 text-[12px] font-mono uppercase tracking-[0.2em]">
        <Warning size={16} weight="bold" />
        <span>Paper Simulator Active — no real orders sent to Upstox</span>
      </div>
    </div>
  );
}
