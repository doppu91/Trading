import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import PnLTarget from "../components/PnLTarget";
import RegimeCard from "../components/RegimeCard";
import GlobalCues from "../components/GlobalCues";
import SignalScanner from "../components/SignalScanner";
import Positions from "../components/Positions";
import TradesTable from "../components/TradesTable";
import ChargesTracker from "../components/ChargesTracker";
import RiskMonitor from "../components/RiskMonitor";
import RegimeTimeline from "../components/RegimeTimeline";
import TelegramPanel from "../components/TelegramPanel";
import UpstoxPanel from "../components/UpstoxPanel";

export default function Dashboard({ status, onStatusRefresh }) {
  const [brief, setBrief] = useState(null);
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [risk, setRisk] = useState(null);
  const [charges, setCharges] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [tg, setTg] = useState(null);
  const [eod, setEod] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    const fetches = [
      api.get("/morning-brief").then((r) => setBrief(r.data)).catch(() => {}),
      api.get("/signals").then((r) => setSignals(r.data.signals || [])).catch(() => {}),
      api.get("/positions").then((r) => setPositions(r.data.positions || [])).catch(() => {}),
      api.get("/trades?limit=50").then((r) => setTrades(r.data.trades || [])).catch(() => {}),
      api.get("/risk").then((r) => setRisk(r.data)).catch(() => {}),
      api.get("/charges/today").then((r) => setCharges(r.data)).catch(() => {}),
      api.get("/regime/timeline?days=90").then((r) => setTimeline(r.data.timeline || [])).catch(() => {}),
      api.get("/telegram/status").then((r) => setTg(r.data)).catch(() => {}),
      api.get("/eod-summary").then((r) => setEod(r.data)).catch(() => {}),
    ];
    await Promise.all(fetches);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 30000);
    return () => clearInterval(id);
  }, [loadAll]);

  return (
    <div className="min-h-[calc(100vh-3.5rem)]" data-testid="dashboard-page">
      {/* Row 1 — P&L target wide + Regime + Global cues */}
      <div className="grid grid-cols-12 gap-px bg-border border-b border-border">
        <div className="col-span-12 md:col-span-6 bg-[#09090B]"><PnLTarget today={status?.today} targetGross={status?.target_gross} targetNet={status?.target_net} /></div>
        <div className="col-span-6 md:col-span-3 bg-[#09090B]"><RegimeCard regime={brief?.regime} /></div>
        <div className="col-span-6 md:col-span-3 bg-[#09090B]"><GlobalCues cues={brief?.global_cues} /></div>
      </div>

      {/* Row 2 — Risk + Charges + Regime timeline + Upstox */}
      <div className="grid grid-cols-12 gap-px bg-border border-b border-border">
        <div className="col-span-12 md:col-span-3 bg-[#09090B]"><RiskMonitor risk={risk} /></div>
        <div className="col-span-12 md:col-span-3 bg-[#09090B]"><ChargesTracker charges={charges} /></div>
        <div className="col-span-12 md:col-span-3 bg-[#09090B]"><UpstoxPanel status={status?.upstox} onUpdate={onStatusRefresh} /></div>
        <div className="col-span-12 md:col-span-3 bg-[#09090B]"><TelegramPanel status={tg} onUpdate={() => { onStatusRefresh?.(); api.get('/telegram/status').then(r => setTg(r.data)); }} /></div>
      </div>

      {/* Row 3 — Regime timeline */}
      <div className="border-b border-border">
        <RegimeTimeline timeline={timeline} />
      </div>

      {/* Row 4 — Signal scanner */}
      <div className="border-b border-border">
        <SignalScanner signals={signals} threshold={status?.signal_threshold} onOpened={loadAll} />
      </div>

      {/* Row 5 — Positions */}
      <div className="border-b border-border">
        <Positions positions={positions} onChanged={loadAll} />
      </div>

      {/* Row 6 — Trades */}
      <div>
        <TradesTable trades={trades} />
      </div>
    </div>
  );
}
