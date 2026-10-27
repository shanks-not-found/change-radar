import React, { useState } from "react";
import { Activity, Cpu, Sparkles, Server, Check, AlertCircle, ExternalLink, X } from "lucide-react";
import { HealthResponse } from "../types";
import { getApiBase, setApiBase } from "../api/client";

interface NavbarProps {
  health: HealthResponse | null;
  onReset: () => void;
  onOpenAsk: () => void;
  onRefreshHealth?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ health, onReset, onOpenAsk, onRefreshHealth }) => {
  const isMock = health?.llm_provider === "mock" || !health?.llm_configured;
  const isConnected = health !== null && health.status === "ok";

  const [showConfig, setShowConfig] = useState(false);
  const [customUrl, setCustomUrl] = useState(getApiBase());
  const [testStatus, setTestStatus] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTestAndSave = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const cleanUrl = customUrl.trim().replace(/\/$/, "");
      const res = await fetch(`${cleanUrl}/api/health`);
      if (res.ok) {
        setApiBase(cleanUrl);
        setTestStatus("success");
        if (onRefreshHealth) onRefreshHealth();
        setTimeout(() => setShowConfig(false), 900);
      } else {
        setTestStatus(`Failed (Status ${res.status})`);
      }
    } catch (err: any) {
      setTestStatus(`Unreachable: ${err.message}`);
    } finally {
      setIsTesting(false);
    }
  };

  const handleResetDefault = () => {
    setApiBase("");
    const def = getApiBase();
    setCustomUrl(def);
    setTestStatus(null);
    if (onRefreshHealth) onRefreshHealth();
  };

  return (
    <>
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-surface-700/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <div
            onClick={onReset}
            className="flex items-center gap-3 cursor-pointer group transition-transform active:scale-95"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 via-brand-500 to-emerald-400 p-[1px] shadow-lg shadow-brand-500/20">
              <div className="w-full h-full bg-surface-950 rounded-[11px] flex items-center justify-center group-hover:bg-surface-900 transition-colors">
                <Activity className="w-5 h-5 text-brand-400 animate-pulse" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  StackSignal
                </span>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  v1.0
                </span>
              </div>
              <p className="text-xs text-slate-400">Dependency Change Impact Radar</p>
            </div>
          </div>

          {/* Right status & actions */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            {/* Backend Connection Pill */}
            <button
              onClick={() => setShowConfig(true)}
              title="Click to configure backend tunnel API URL"
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                isConnected
                  ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300 hover:border-emerald-500/60"
                  : "bg-amber-950/40 border-amber-500/40 text-amber-300 hover:border-amber-500/70 animate-pulse"
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400" : "bg-amber-400"}`} />
              <Server className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {isConnected ? "Backend Connected" : "Backend Offline"}
              </span>
            </button>

            {/* Ask AI button */}
            <button
              onClick={onOpenAsk}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-surface-800/80 hover:bg-surface-700 text-slate-200 border border-surface-700 transition-all hover:border-slate-500 shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline">Ask Project AI</span>
            </button>

            {/* LLM Status Pill */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-900/90 border border-surface-800">
              <div className={`w-2 h-2 rounded-full ${isMock ? "bg-amber-400" : "bg-brand-400"}`} />
              <Cpu className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-slate-300">
                {isMock ? (
                  <span className="text-amber-300 font-medium">Demo LLM</span>
                ) : (
                  <span className="text-brand-300 font-medium">{health?.llm_provider || "AI"}</span>
                )}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Backend API Configuration Modal */}
      {showConfig && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-lg rounded-2xl bg-surface-900 border border-surface-700 shadow-2xl p-6 space-y-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${isConnected ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-amber-500/20 text-amber-400 border border-amber-500/30"}`}>
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Backend Connection Settings</h3>
                  <p className="text-xs text-slate-400">Configure Cloudflare Tunnel or local FastAPI server</p>
                </div>
              </div>
              <button
                onClick={() => setShowConfig(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-semibold text-slate-300 block">
                Backend API URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="https://your-tunnel.trycloudflare.com or http://localhost:8000"
                  className="flex-1 px-3.5 py-2.5 rounded-xl bg-surface-950 border border-surface-700 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
                />
                <button
                  onClick={handleTestAndSave}
                  disabled={isTesting}
                  className="px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-surface-950 text-xs font-bold transition disabled:opacity-50 shrink-0"
                >
                  {isTesting ? "Testing..." : "Test & Save"}
                </button>
              </div>

              {testStatus && (
                <div
                  className={`text-xs px-3 py-2 rounded-lg flex items-center gap-2 ${
                    testStatus === "success"
                      ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"
                      : "bg-red-500/10 text-red-300 border border-red-500/30"
                  }`}
                >
                  {testStatus === "success" ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Connected successfully! Reloading health status...</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                      <span className="truncate">{testStatus}</span>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Cloud vs Local Tabs / Guidance */}
            <div className="p-3.5 rounded-xl bg-surface-950/80 border border-surface-800 space-y-3 text-xs text-slate-400">
              <div className="space-y-1.5">
                <div className="font-semibold text-emerald-400 flex items-center gap-1.5">
                  <span>Option 1: 24/7 Online Cloud Backend (Recommended)</span>
                </div>
                <p className="leading-relaxed text-[11px] text-slate-300">
                  Deploy to <strong className="text-white">Render.com</strong> (Free 24/7 Python Web Service) from your GitHub repository using the included <code className="text-brand-300 font-mono">render.yaml</code>.
                </p>
                <p className="text-[10px] text-slate-500">
                  Once deployed on Render, paste your service URL (e.g. <code className="text-slate-300 font-mono">https://change-radar-backend.onrender.com</code>) above. It will stay online 24/7 even when your laptop and IDE are completely closed.
                </p>
              </div>

              <div className="pt-2 border-t border-surface-850 space-y-1.5">
                <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <span>Option 2: Local Development Tunnel (When PC is on)</span>
                </div>
                <p className="leading-relaxed text-[11px]">
                  To temporarily expose your local machine's backend via Cloudflare:
                </p>
                <pre className="p-2 rounded bg-surface-900 border border-surface-850 font-mono text-[11px] text-brand-300 overflow-x-auto select-all">
                  npx --yes cloudflared tunnel --url http://localhost:8000
                </pre>
              </div>
            </div>

            <div className="flex justify-between items-center pt-1 border-t border-surface-800 text-xs">
              <button
                onClick={handleResetDefault}
                className="text-slate-400 hover:text-slate-200 underline text-xs"
              >
                Reset Default
              </button>
              <button
                onClick={() => setShowConfig(false)}
                className="px-4 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
