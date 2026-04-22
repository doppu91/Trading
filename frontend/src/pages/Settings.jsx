import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";

export default function Settings({ onRefresh }) {
  const [s, setS] = useState(null);
  const [edit, setEdit] = useState({});

  const load = useCallback(async () => {
    const r = await api.get("/settings");
    setS(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await api.put("/settings", edit);
      toast.success("Settings saved");
      setEdit({});
      await load();
      onRefresh?.();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
  };

  const togglePaper = async () => {
    try {
      await api.put("/settings", { paper_mode: !s.paper_mode });
      toast.success(`Paper mode ${!s.paper_mode ? "ON" : "OFF"}`);
      await load();
      onRefresh?.();
    } catch (e) { toast.error(e.message); }
  };

  const seed = async () => {
    try {
      await api.post("/seed-demo");
      toast.success("Demo trades seeded");
      onRefresh?.();
    } catch (e) { toast.error(e.message); }
  };

  if (!s) return <div className="p-8 text-zinc-500">Loading…</div>;

  const field = (k, label, step = 0.01, hint) => (
    <div className="p-4 border-b border-border">
      <div className="label-xs">{label}</div>
      <input
        type="number"
        step={step}
        data-testid={`input-${k}`}
        defaultValue={s[k]}
        onChange={(e) => setEdit((x) => ({ ...x, [k]: Number(e.target.value) }))}
        className="mt-2 w-full bg-transparent border border-border px-3 py-2 font-mono text-sm text-white focus:outline-none focus:border-white"
      />
      {hint && <div className="text-[11px] font-mono text-zinc-500 mt-1">{hint}</div>}
    </div>
  );

  return (
    <div className="min-h-[calc(100vh-3.5rem)]" data-testid="settings-page">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <div className="label-xs">System Settings</div>
          <h2 className="text-2xl font-black tracking-tight mt-1">Trading Parameters</h2>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="seed-demo-btn" onClick={seed} className="px-4 h-9 border border-border text-xs font-mono uppercase tracking-wider hover:bg-zinc-800/50">Seed Demo Trades</button>
          <button data-testid="save-settings-btn" onClick={save} disabled={!Object.keys(edit).length} className="px-5 h-9 bg-white text-black text-xs font-mono uppercase tracking-wider hover:bg-zinc-200 disabled:opacity-40">Save Changes</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border border-b border-border">
        <div className="bg-[#09090B]">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div>
              <div className="label-xs">Paper Mode</div>
              <div className="mt-2 font-mono text-sm">{s.paper_mode ? "ON (simulated)" : "OFF (LIVE)"}</div>
            </div>
            <button data-testid="toggle-paper-btn" onClick={togglePaper} className={`px-4 h-9 text-xs font-mono uppercase tracking-wider border ${s.paper_mode ? "bg-amber-500/10 border-amber-500/40 text-amber-400" : "bg-red-500/10 border-red-500/40 text-red-400"}`}>
              Toggle
            </button>
          </div>
          {field("capital", "Capital (₹)", 1000, "Starting capital")}
          {field("max_daily_loss", "Max Daily Loss (₹)", 100)}
        </div>

        <div className="bg-[#09090B]">
          {field("target_gross", "Target Gross Daily (₹)", 100, "Net after charges ~ target - 500")}
          {field("signal_threshold", "Signal Threshold", 0.01, "≥0.68 recommended")}
          <div className="p-4 border-b border-border">
            <div className="label-xs">Max Positions</div>
            <div className="font-mono text-sm mt-2">{s.max_positions}</div>
          </div>
        </div>

        <div className="bg-[#09090B]">
          <div className="p-4 border-b border-border">
            <div className="label-xs">Risk per Trade</div>
            <div className="font-mono text-sm mt-2">{(s.risk_per_trade_pct * 100).toFixed(2)}%</div>
          </div>
          <div className="p-4 border-b border-border">
            <div className="label-xs">Signal Weights</div>
            <div className="mt-2 space-y-1 font-mono text-xs">
              {Object.entries(s.weights).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between">
                  <span className="text-zinc-400 uppercase tracking-wider">{k}</span>
                  <span>{(v * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
          <div className="p-4">
            <div className="label-xs">Watchlist ({s.watchlist.length})</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {s.watchlist.map((w) => (
                <span key={w} className="pill">{w}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="p-6 text-xs text-zinc-500 font-mono leading-relaxed">
        <div className="label-xs mb-2">Notes</div>
        <p>• Live Upstox trading requires API key + secret + daily access token. Configure via Dashboard · Upstox panel.</p>
        <p>• Telegram bot required for Morning Brief + EOD Summary push notifications.</p>
        <p>• Tax: Intraday profits are business income — set aside ~25-30% of profitable months for advance tax (ITR-3).</p>
      </div>
    </div>
  );
}
