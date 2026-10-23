import React, { useState } from "react";
import { X, Sparkles, Send, Loader2, ExternalLink, ShieldCheck, HelpCircle } from "lucide-react";
import { AskResponse } from "../types";
import { api } from "../api/client";

interface AskPanelProps {
  projectId: string;
  projectName: string;
  isOpen: boolean;
  onClose: () => void;
}

const PRESET_QUESTIONS = [
  "Does Pydantic V2 break our service models or methods?",
  "Are there any known CVE security vulnerabilities affecting our code?",
  "How does LangChain 0.2 affect our LLMChain usage?",
  "What is the recommended migration for ChromaDB Client?",
];

export const AskPanel: React.FC<AskPanelProps> = ({
  projectId,
  projectName,
  isOpen,
  onClose,
}) => {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<AskResponse[]>([]);

  if (!isOpen) return null;

  const handleSubmit = async (qText: string) => {
    if (!qText.trim() || loading) return;
    setLoading(true);
    try {
      const resp = await api.askQuestion(projectId, qText);
      setHistory((prev) => [resp, ...prev]);
      setQuestion("");
    } catch (err: any) {
      alert(`Error asking question: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-xl h-full bg-surface-900 border-l border-surface-700 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-surface-800 flex items-center justify-between bg-surface-950/60">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider font-bold text-brand-400 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Grounded Project Q&A</span>
              </span>
            </div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span>Ask about</span>
              <span className="font-mono text-brand-300">`{projectName}`</span>
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Suggestion Pills */}
        <div className="p-4 bg-surface-950/40 border-b border-surface-800 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Suggested Inquiries
          </p>
          <div className="flex flex-wrap gap-1.5">
            {PRESET_QUESTIONS.map((pq, idx) => (
              <button
                key={idx}
                onClick={() => handleSubmit(pq)}
                disabled={loading}
                className="text-left px-2.5 py-1 rounded-lg text-xs bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white border border-surface-700 transition-colors disabled:opacity-50"
              >
                {pq}
              </button>
            ))}
          </div>
        </div>

        {/* Chat / Answers stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {history.length === 0 ? (
            <div className="text-center py-12 space-y-3">
              <div className="w-12 h-12 rounded-xl bg-surface-800 mx-auto flex items-center justify-center text-slate-400 border border-surface-700">
                <HelpCircle className="w-6 h-6 text-brand-400" />
              </div>
              <p className="text-sm font-medium text-slate-300">
                Ask any question about your dependencies
              </p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Answers are grounded using hybrid retrieval over your code AST call sites and external release notes.
              </p>
            </div>
          ) : (
            history.map((item, idx) => (
              <div key={idx} className="space-y-3 bg-surface-950 p-4 rounded-xl border border-surface-800">
                {/* Question */}
                <div className="flex items-center gap-2 text-xs font-semibold text-brand-400">
                  <span>Q:</span>
                  <span className="text-white">{item.question}</span>
                </div>

                {/* Answer */}
                <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-line border-t border-surface-800/80 pt-3">
                  {item.answer}
                </div>

                {/* Cited Sources */}
                {item.cited_sources && item.cited_sources.length > 0 && (
                  <div className="space-y-1.5 border-t border-surface-800/80 pt-2.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Cited Sources ({item.cited_sources.length})
                    </p>
                    <div className="space-y-1.5">
                      {item.cited_sources.map((src, sIdx) => (
                        <div
                          key={sIdx}
                          className="p-2 rounded bg-surface-900 border border-surface-800 flex items-center justify-between text-[11px]"
                        >
                          <span className="font-mono text-slate-300">
                            {src.package} v{src.version}
                          </span>
                          {src.url && (
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300 hover:underline"
                            >
                              <span>Official Link</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Confidence & Caveats */}
                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                  <span>Confidence: {(item.confidence * 100).toFixed(0)}%</span>
                  {item.caveats && <span className="italic">{item.caveats}</span>}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-surface-800 bg-surface-950">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit(question);
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about breaking changes or code compatibility..."
              disabled={loading}
              className="flex-1 px-4 py-2.5 rounded-xl bg-surface-900 border border-surface-700 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-4 py-2.5 rounded-xl font-medium text-xs bg-brand-500 hover:bg-brand-600 text-surface-950 transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
