import React, { useEffect, useState, useCallback } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import { api } from "@/lib/api";
import Header from "@/components/Header";
import PaperModeBanner from "@/components/PaperModeBanner";
import Dashboard from "@/pages/Dashboard";
import Backtest from "@/pages/Backtest";
import Settings from "@/pages/Settings";

function App() {
  const [status, setStatus] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get("/status");
      setStatus(r.data);
    } catch (e) {
      console.error("status fail", e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 20000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <BrowserRouter>
      <div className="App bg-[#09090B] text-white min-h-screen">
        <Header status={status} />
        <PaperModeBanner active={status?.paper_mode} />
        <Routes>
          <Route path="/" element={<Dashboard status={status} onStatusRefresh={refresh} />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/settings" element={<Settings onRefresh={refresh} />} />
        </Routes>
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#121214",
              border: "1px solid #27272A",
              borderRadius: 0,
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "12px",
              color: "#fff",
            },
          }}
        />
      </div>
    </BrowserRouter>
  );
}

export default App;
