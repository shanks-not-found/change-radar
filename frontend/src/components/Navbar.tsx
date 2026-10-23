import React from "react";
import { Activity, ShieldAlert, Cpu, Sparkles, Terminal } from "lucide-react";
import { HealthResponse } from "../types";

interface NavbarProps {
  health: HealthResponse | null;
  onReset: () => void;
  onOpenAsk: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ health, onReset, onOpenAsk }) => {
  const isMock = health?.llm_provider === "mock" || !health?.llm_configured;

  return (
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
        <div className="flex items-center gap-3">
          {/* Ask AI button */}
          <button
            onClick={onOpenAsk}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-surface-800/80 hover:bg-surface-700 text-slate-200 border border-surface-700 transition-all hover:border-slate-500 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Ask Project AI</span>
          </button>

          {/* LLM Status Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-900/90 border border-surface-800">
            <div className={`w-2 h-2 rounded-full ${isMock ? "bg-amber-400" : "bg-brand-400 animate-ping"}`} />
            <Cpu className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-300">
              {isMock ? (
                <span className="text-amber-300 font-medium">Demo / Mock LLM</span>
              ) : (
                <span className="text-brand-300 font-medium">Gemini ({health?.gemini_model || "Flash"})</span>
              )}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
