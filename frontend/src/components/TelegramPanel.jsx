import React, { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { PaperPlaneTilt } from "@phosphor-icons/react";

export default function TelegramPanel({ status, onUpdate }) {
  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!token || !chatId) return toast.error("Both bot token and chat ID required");
    setBusy(true);
    try {
      await api.post("/telegram/configure", { bot_token: token, chat_id: chatId });
      toast.success("Telegram linked");
      setToken(""); setChatId("");
      onUpdate?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  const sendTest = async () => {
    try {
      const r = await api.post("/telegram/send-test");
      if (r.data.ok) toast.success("Test message sent");
      else toast.error(r.data.error || "Send failed");
      onUpdate?.();
    } catch (e) { toast.error(e.message); }
  };

  const sendBrief = async () => {
    try {
      await api.post("/telegram/send-morning-brief");
      toast.success("Morning brief sent");
      onUpdate?.();
    } catch (e) { toast.error(e.message); }
  };

  const sendEod = async () => {
    try {
      await api.post("/telegram/send-eod");
      toast.success("EOD summary sent");
      onUpdate?.();
    } catch (e) { toast.error(e.message); }
  };

  return (
    <div className="p-6 h-full" data-testid="telegram-panel">
      <div className="flex items-center justify-between">
        <div className="label-xs">Telegram Bot</div>
        <span className={`pill ${status?.configured ? "text-emerald-400 border-emerald-500/40" : "text-zinc-500"}`}>
          {status?.configured ? "LINKED" : "NOT LINKED"}
        </span>
      </div>

      {status?.configured ? (
        <div className="mt-3 font-mono text-[11px] text-zinc-400 break-all">
          Bot: {status.bot_token_preview}<br />
          Chat ID: {status.chat_id}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <input
            data-testid="tg-token-input"
            placeholder="Bot token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="w-full bg-transparent border border-border px-3 py-2 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none focus:border-white"
          />
          <input
            data-testid="tg-chat-input"
            placeholder="Chat ID"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="w-full bg-transparent border border-border px-3 py-2 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none focus:border-white"
          />
          <button
            data-testid="tg-save-btn"
            onClick={save}
            disabled={busy}
            className="w-full bg-white text-black text-xs font-mono uppercase tracking-wider py-2 hover:bg-zinc-200 disabled:opacity-50"
          >
            {busy ? "Linking…" : "Link Bot"}
          </button>
        </div>
      )}

      <div className="mt-4 grid grid-cols-3 gap-2">
        <button data-testid="tg-test-btn" onClick={sendTest} disabled={!status?.configured} className="text-[10px] font-mono uppercase tracking-wider border border-border py-2 hover:bg-zinc-800/50 disabled:opacity-30">Test</button>
        <button data-testid="tg-brief-btn" onClick={sendBrief} disabled={!status?.configured} className="text-[10px] font-mono uppercase tracking-wider border border-border py-2 hover:bg-zinc-800/50 disabled:opacity-30">Brief</button>
        <button data-testid="tg-eod-btn" onClick={sendEod} disabled={!status?.configured} className="text-[10px] font-mono uppercase tracking-wider border border-border py-2 hover:bg-zinc-800/50 disabled:opacity-30">EOD</button>
      </div>

      {status?.recent?.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="label-xs mb-2">Recent</div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {status.recent.slice(0, 6).map((r) => (
              <div key={r.ts} className="font-mono text-[10px] text-zinc-500 flex gap-2">
                <PaperPlaneTilt size={10} weight="bold" className={r.ok ? "text-emerald-500" : "text-red-500"} />
                <span>{new Date(r.ts).toLocaleTimeString("en-IN", { hour12: false })}</span>
                <span className="truncate">{(r.text || "").replace(/<[^>]*>/g, "").slice(0, 40)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
