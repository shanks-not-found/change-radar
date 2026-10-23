import React from "react";
import { X, ExternalLink, Quote, FileCode, CheckCircle, Calendar, Hash } from "lucide-react";
import { FindingEvidenceResponse } from "../types";

interface EvidenceDrawerProps {
  evidence: FindingEvidenceResponse | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ evidence, onClose }) => {
  if (!evidence) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-xl h-full bg-surface-900 border-l border-surface-700 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-surface-800 flex items-center justify-between bg-surface-950/60">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider font-bold text-brand-400">
                Grounded Citations & Code Map
              </span>
            </div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span>Evidence for</span>
              <span className="font-mono text-brand-300">`{evidence.package}`</span>
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* External Evidence Passages */}
          <div className="space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Quote className="w-4 h-4 text-brand-400" />
              <span>Retrieved External Evidence ({evidence.evidence_items.length})</span>
            </h4>

            {evidence.evidence_items.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No external citations directly recorded.</p>
            ) : (
              evidence.evidence_items.map((ev, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-surface-950/80 border border-surface-800 space-y-3"
                >
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-mono flex items-center gap-1 text-slate-300">
                      <Hash className="w-3 h-3 text-slate-500" />
                      {ev.chunk_id}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-surface-800 text-slate-300 font-mono">
                        v{ev.version}
                      </span>
                      {ev.date && (
                        <span className="flex items-center gap-1 text-[11px] text-slate-500">
                          <Calendar className="w-3 h-3" />
                          {ev.date.split("T")[0]}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Quoted Passage */}
                  <blockquote className="border-l-2 border-brand-500 pl-3.5 py-1 text-xs text-slate-200 italic leading-relaxed bg-brand-500/5 rounded-r">
                    "{ev.quoted_passage}"
                  </blockquote>

                  {/* Source link */}
                  {ev.url && (
                    <div className="pt-1">
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 hover:underline"
                      >
                        <span>Open official source release note</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Matched Project Code References */}
          <div className="space-y-4 border-t border-surface-800 pt-6">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <FileCode className="w-4 h-4 text-emerald-400" />
              <span>Matched Code Call Sites ({evidence.code_references.length})</span>
            </h4>

            {evidence.code_references.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No direct code lines matched for this package.</p>
            ) : (
              evidence.code_references.map((ref, idx) => (
                <div
                  key={idx}
                  className="rounded-xl bg-surface-950 border border-surface-800 overflow-hidden font-mono text-xs"
                >
                  <div className="px-3 py-2 bg-surface-900 border-b border-surface-800 flex items-center justify-between text-slate-400">
                    <span className="text-slate-300 font-sans font-medium text-xs">
                      {ref.file_path}
                    </span>
                    <span className="text-slate-500">Line {ref.line_number}</span>
                  </div>
                  <div className="p-3 bg-slate-950 text-emerald-300 overflow-x-auto">
                    <code>{ref.snippet}</code>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-800 bg-surface-950 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-medium bg-surface-800 hover:bg-surface-700 text-slate-200 transition-colors"
          >
            Close Evidence Drawer
          </button>
        </div>
      </div>
    </div>
  );
};
