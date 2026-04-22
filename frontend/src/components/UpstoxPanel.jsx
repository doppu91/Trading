import React, { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";

export default function UpstoxPanel({ status, onUpdate }) {
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!key || !secret) return toast.error("API key + secret required");
    setBusy(true);
    try {
      await api.post("/upstox/configure", { api_key: key, api_secret: secret, sandbox: true });
      toast.success("Upstox API configured");
      setKey(""); setSecret("");
      onUpdate?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  const saveToken = async () => {
    if (!token) return toast.error("Access token required");
    setBusy(true);
    try {
      await api.post("/upstox/token", { access_token: token });
      toast.success("Access token saved");
      setToken("");
      onUpdate?.();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const openAuthUrl = async () => {
    try {
      const r = await api.get("/upstox/auth-url");
      window.open(r.data.auth_url, "_blank");
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
  };

  const dot =
    status?.state === "connected" ? "bg-emerald-500" :
    status?.state === "configured_no_token" ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="p-6 h-full" data-testid="upstox-panel">
      <div className="flex items-center justify-between">
        <div className="label-xs">Upstox API</div>
        <span className="flex items-center gap-2">
          <span className={`w-2 h-2 ${dot} rounded-full live-dot`}></span>
          <span className="pill">{status?.state?.replace("_", " ").toUpperCase() || "UNKNOWN"}</span>
        </span>
      </div>

      {status?.configured ? (
        <div className="mt-3 font-mono text-[11px] text-zinc-400">
          Key: {status.api_key_preview}<br />
          Mode: {status.sandbox ? "Sandbox" : "Live"}<br />
          Token: {status.has_token ? `refreshed ${status.token_refreshed_at?.slice(0, 19)}Z` : "—"}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <input data-testid="up-key" placeholder="API Key" value={key} onChange={(e) => setKey(e.target.value)} className="w-full bg-transparent border border-border px-3 py-2 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none focus:border-white" />
          <input data-testid="up-secret" type="password" placeholder="API Secret" value={secret} onChange={(e) => setSecret(e.target.value)} className="w-full bg-transparent border border-border px-3 py-2 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none focus:border-white" />
          <button data-testid="up-save" onClick={save} disabled={busy} className="w-full bg-white text-black text-xs font-mono uppercase tracking-wider py-2 hover:bg-zinc-200 disabled:opacity-50">
            {busy ? "Saving…" : "Configure"}
          </button>
        </div>
      )}

      {status?.configured && !status?.has_token && (
        <div className="mt-4 border-t border-border pt-3 space-y-2">
          <button data-testid="up-authurl" onClick={openAuthUrl} className="w-full text-[11px] font-mono uppercase tracking-wider border border-border py-2 hover:bg-zinc-800/50">
            Open Upstox Auth URL
          </button>
          <div className="label-xs">…then paste access token</div>
          <input data-testid="up-token" placeholder="Access token" value={token} onChange={(e) => setToken(e.target.value)} className="w-full bg-transparent border border-border px-3 py-2 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none focus:border-white" />
          <button data-testid="up-save-token" onClick={saveToken} disabled={busy} className="w-full bg-white text-black text-xs font-mono uppercase tracking-wider py-2 hover:bg-zinc-200 disabled:opacity-50">Save Token</button>
        </div>
      )}
    </div>
  );
}
