import React from "react";
import { X, HelpCircle, Activity, Sparkles, CheckCircle2, Search, Cpu } from "lucide-react";
import { FindingExplainability } from "../types";

interface ExplainModalProps {
  package_name: string;
  explainability: FindingExplainability | null;
  onClose: () => void;
}

export const ExplainModal: React.FC<ExplainModalProps> = ({
  package_name,
  explainability,
  onClose,
}) => {
  if (!explainability) return null;

  const scores = explainability.retrieval_scores || {};

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-surface-900 border border-surface-700 rounded-2xl shadow-2xl overflow-hidden space-y-6">
        {/* Header */}
        <div className="p-6 border-b border-surface-800 flex items-center justify-between bg-surface-950/60">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider font-bold text-teal-400">
                Explainability & Reasoning Provenance
              </span>
            </div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span>Why was</span>
              <span className="font-mono text-brand-300">`{package_name}`</span>
              <span>flagged?</span>
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6 text-sm">
          {/* Retrieval Scores Matrix */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Search className="w-4 h-4 text-brand-400" />
              <span>Hybrid Retrieval Confidence Scores</span>
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-surface-950 border border-surface-800 text-center space-y-1">
                <p className="text-[11px] text-slate-400">Reciprocal Rank (RRF)</p>
                <p className="text-lg font-bold text-brand-400">
                  {typeof scores.top_rrf_score === "number" ? scores.top_rrf_score.toFixed(4) : "N/A"}
                </p>
                <p className="text-[10px] text-slate-500">Dense + Sparse Fusion</p>
              </div>

              <div className="p-3.5 rounded-xl bg-surface-950 border border-surface-800 text-center space-y-1">
                <p className="text-[11px] text-slate-400">Vector Similarity</p>
                <p className="text-lg font-bold text-emerald-400">
                  {typeof scores.top_vector_score === "number" ? `${(scores.top_vector_score * 100).toFixed(1)}%` : "N/A"}
                </p>
                <p className="text-[10px] text-slate-500">ChromaDB Cosine</p>
              </div>

              <div className="p-3.5 rounded-xl bg-surface-950 border border-surface-800 text-center space-y-1">
                <p className="text-[11px] text-slate-400">Keyword BM25 Match</p>
                <p className="text-lg font-bold text-teal-400">
                  {typeof scores.top_keyword_score === "number" ? `${(scores.top_keyword_score * 100).toFixed(1)}%` : "N/A"}
                </p>
                <p className="text-[10px] text-slate-500">SQLite FTS5 Porter</p>
              </div>
            </div>
          </div>

          {/* Matched API Symbols */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              <span>Direct AST Symbol Overlap ({explainability.matched_symbols.length})</span>
            </h4>
            {explainability.matched_symbols.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No exact symbol tokens detected in top chunk.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {explainability.matched_symbols.map((sym) => (
                  <span
                    key={sym}
                    className="px-3 py-1 rounded-lg text-xs font-mono font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20"
                  >
                    {sym}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Reasoning Trail */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-brand-400" />
              <span>Step-by-Step Reasoning Trail</span>
            </h4>
            <div className="space-y-2 bg-surface-950 p-4 rounded-xl border border-surface-800">
              {explainability.reasoning_trail.map((step, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-xs text-slate-300">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-surface-800 text-slate-400 font-mono text-[10px] flex items-center justify-center font-bold">
                    {idx + 1}
                  </span>
                  <span className="leading-relaxed">{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Grounding Status Pill */}
          <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-brand-400" />
              <span>Grounding Anti-Hallucination Verification</span>
            </div>
            <span className="px-2.5 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-brand-500/10 text-brand-300 border border-brand-500/30">
              {explainability.validation_status}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-800 bg-surface-950 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-medium bg-surface-800 hover:bg-surface-700 text-slate-200 transition-colors"
          >
            Close Explanation
          </button>
        </div>
      </div>
    </div>
  );
};
