import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Circle, Gauge, Flask, ChartLineUp, Gear, PaperPlaneTilt } from "@phosphor-icons/react";

export default function Header({ status }) {
  const loc = useLocation();
  const paper = status?.paper_mode;
  const upstoxState = status?.upstox?.state || "disconnected";
  const tgConfigured = status?.telegram?.configured;

  const nav = [
    { to: "/", label: "Dashboard", icon: Gauge },
    { to: "/backtest", label: "Backtest", icon: ChartLineUp },
    { to: "/settings", label: "Settings", icon: Gear },
  ];

  const upstoxDot =
    upstoxState === "connected" ? "bg-emerald-500" :
    upstoxState === "configured_no_token" ? "bg-amber-500" : "bg-red-500";

  return (
    <header className="border-b border-border" data-testid="app-header">
      <div className="flex items-center justify-between px-6 h-14">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-white text-black flex items-center justify-center font-black text-sm tracking-tighter">A</div>
            <div className="font-black tracking-tight text-[15px]">ALPHA<span className="text-zinc-500">/DESK</span></div>
            <div className="label-xs ml-3 border-l border-border pl-3">UPSTOX · NSE</div>
          </div>
          <nav className="flex items-center gap-1 ml-6">
            {nav.map(({ to, label, icon: Icon }) => {
              const active = loc.pathname === to;
              return (
                <Link
                  key={to}
                  to={to}
                  data-testid={`nav-${label.toLowerCase()}`}
                  className={`flex items-center gap-2 px-3 h-9 text-[13px] transition-colors duration-150 ${
                    active ? "bg-white text-black font-semibold" : "text-zinc-400 hover:bg-zinc-800/50 hover:text-white"
                  }`}
                >
                  <Icon size={14} weight="bold" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-4 text-[11px] font-mono">
          <div className="flex items-center gap-2" data-testid="status-upstox">
            <span className={`w-2 h-2 ${upstoxDot} rounded-full live-dot`}></span>
            <span className="uppercase tracking-wider text-zinc-400">Upstox</span>
            <span className="uppercase tracking-wider">{upstoxState.replace("_", " ")}</span>
          </div>
          <div className="flex items-center gap-2" data-testid="status-telegram">
            <PaperPlaneTilt size={14} className={tgConfigured ? "text-emerald-400" : "text-zinc-600"} weight="bold" />
            <span className="uppercase tracking-wider text-zinc-400">TG</span>
            <span className="uppercase tracking-wider">{tgConfigured ? "Linked" : "—"}</span>
          </div>
          <div className="pill" data-testid="status-mode">
            <Flask size={12} weight="bold" />
            <span>{paper ? "PAPER" : "LIVE"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
