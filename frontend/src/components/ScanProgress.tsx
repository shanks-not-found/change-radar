import React from "react";
import { Loader2, CheckCircle2, AlertCircle, FileSearch, GitBranch, Database, Sparkles, Binary } from "lucide-react";
import { ScanStatusResponse, ScanStage } from "../types";

interface ScanProgressProps {
  status: ScanStatusResponse;
}

const STAGES: { key: ScanStage; label: string; icon: React.FC<{ className?: string }> }[] = [
  { key: "parsing", label: "Parse Dependencies", icon: FileSearch },
  { key: "scanning_code", label: "AST Code Walk", icon: Binary },
  { key: "fetching_releases", label: "GitHub Releases", icon: GitBranch },
  { key: "fetching_advisories", label: "OSV Advisories", icon: Database },
  { key: "indexing", label: "Hybrid Indexing", icon: Database },
  { key: "analyzing", label: "LLM Reasoning", icon: Sparkles },
  { key: "completed", label: "Report Ready", icon: CheckCircle2 },
];

export const ScanProgress: React.FC<ScanProgressProps> = ({ status }) => {
  const getStageIndex = (stage: ScanStage): number => {
    const idx = STAGES.findIndex((s) => s.key === stage);
    return idx === -1 ? 0 : idx;
  };

  const currentIdx = getStageIndex(status.status);
  const isFailed = status.status === "failed";

  return (
    <div className="py-12 max-w-3xl mx-auto space-y-8">
      {/* Center status card */}
      <div className="p-8 rounded-2xl glass-panel border border-surface-700/80 shadow-2xl text-center space-y-6">
        <div className="flex justify-center">
          {isFailed ? (
            <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <AlertCircle className="w-8 h-8" />
            </div>
          ) : (
            <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 shadow-lg shadow-brand-500/10">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          )}
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white">
            {isFailed ? "Scan Encountered an Error" : "Analyzing Dependency Impact"}
          </h2>
          <p className="text-sm text-slate-300 font-mono">
            {status.stage_description || "Processing project..."}
          </p>
          {status.error_message && (
            <p className="text-xs text-rose-400 bg-rose-500/10 p-3 rounded-lg border border-rose-500/20 max-w-lg mx-auto">
              {status.error_message}
            </p>
          )}
        </div>

        {/* Progress Bar */}
        <div className="space-y-2 max-w-md mx-auto">
          <div className="w-full bg-surface-800 rounded-full h-2.5 overflow-hidden p-0.5 border border-surface-700">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isFailed ? "bg-rose-500" : "bg-gradient-to-r from-brand-500 to-emerald-400"
              }`}
              style={{ width: `${Math.max(5, status.progress_percentage)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-slate-400 font-mono">
            <span>Stage {Math.min(currentIdx + 1, STAGES.length)} of {STAGES.length}</span>
            <span>{status.progress_percentage}%</span>
          </div>
        </div>
      </div>

      {/* Visual Step Tracker */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
        {STAGES.map((s, idx) => {
          const isDone = currentIdx > idx || status.status === "completed";
          const isCurrent = currentIdx === idx && !isFailed && status.status !== "completed";
          const Icon = s.icon;

          return (
            <div
              key={s.key}
              className={`p-3 rounded-xl border flex flex-col items-center text-center gap-1.5 transition-all ${
                isDone
                  ? "bg-brand-500/10 border-brand-500/30 text-brand-300"
                  : isCurrent
                  ? "bg-surface-800 border-brand-400 text-white shadow-md shadow-brand-500/10"
                  : "bg-surface-900/40 border-surface-800 text-slate-500"
              }`}
            >
              <div className="w-6 h-6 flex items-center justify-center">
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-brand-400" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>
              <span className="text-[10px] font-medium leading-tight">{s.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
