import React, { useState, useRef } from "react";
import { UploadCloud, Github, Sparkles, FolderArchive, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import { ProjectResponse } from "../types";

interface UploadSectionProps {
  onUploadZip: (file: File) => Promise<void>;
  onImportGithub: (url: string) => Promise<void>;
  onLoadDemo: () => Promise<void>;
  recentProjects: ProjectResponse[];
  onSelectProject: (id: string) => void;
  isLoading: boolean;
}

export const UploadSection: React.FC<UploadSectionProps> = ({
  onUploadZip,
  onImportGithub,
  onLoadDemo,
  recentProjects,
  onSelectProject,
  isLoading,
}) => {
  const [githubUrl, setGithubUrl] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith(".zip")) {
        await onUploadZip(file);
      } else {
        alert("Please drop a valid .zip archive.");
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await onUploadZip(e.target.files[0]);
    }
  };

  const handleGithubSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;
    await onImportGithub(githubUrl.trim());
  };

  return (
    <div className="space-y-10 py-6 max-w-5xl mx-auto">
      {/* Hero Header */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold tracking-wide">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Real External Evidence Mapped to Your Code</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
          Detect Breaking Changes & Advisories{" "}
          <span className="bg-gradient-to-r from-brand-400 via-emerald-400 to-teal-300 bg-clip-text text-transparent">
            Before They Break Production
          </span>
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
          Upload any Python repository. StackSignal extracts your pinned dependencies, retrieves official GitHub release notes & OSV advisories via hybrid search, and pinpoints exact AST code locations affected.
        </p>
      </div>

      {/* Demo Project Quick Launch Hero */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-brand-950/40 via-surface-900 to-surface-900 border border-brand-500/30 shadow-xl shadow-brand-950/50 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-1.5 text-center sm:text-left">
          <div className="flex items-center justify-center sm:justify-start gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-brand-500/20 text-brand-400 border border-brand-500/30">
              One-Click Demo
            </span>
            <span className="text-xs text-slate-400">FastAPI + LangChain + ChromaDB</span>
          </div>
          <h2 className="text-lg font-bold text-white">
            Explore the Pre-bundled Sample Project
          </h2>
          <p className="text-xs text-slate-400 max-w-xl">
            Contains pinned dependencies (FastAPI 0.109, Pydantic 2.5, LangChain 0.1, ChromaDB 0.4) with realistic code call sites ready for instant scanning.
          </p>
        </div>
        <button
          onClick={onLoadDemo}
          disabled={isLoading}
          className="whitespace-nowrap px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-brand-500 to-emerald-500 hover:from-brand-600 hover:to-emerald-600 text-surface-950 shadow-lg shadow-brand-500/25 transition-all active:scale-95 disabled:opacity-50 flex items-center gap-2 group"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <span>Load Sample Demo</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </>
          )}
        </button>
      </div>

      {/* Upload Inputs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ZIP Upload Card */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`p-8 rounded-2xl glass-card glass-card-hover border-2 border-dashed cursor-pointer flex flex-col items-center justify-center text-center gap-4 transition-all ${
            isDragging ? "border-brand-400 bg-brand-500/5 scale-[1.01]" : "border-surface-700 hover:border-slate-500"
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".zip"
            className="hidden"
          />
          <div className="w-14 h-14 rounded-2xl bg-surface-800 border border-surface-700 flex items-center justify-center text-brand-400 shadow-inner">
            <UploadCloud className="w-7 h-7" />
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-white text-base">Drop your Python Project ZIP</h3>
            <p className="text-xs text-slate-400">
              Or click to browse from local disk (max 50 MB)
            </p>
          </div>
          <div className="text-[11px] text-slate-500 flex items-center gap-2">
            <span>Parses requirements.txt & pyproject.toml</span>
          </div>
        </div>

        {/* GitHub Repo Card */}
        <div className="p-8 rounded-2xl glass-card flex flex-col justify-between gap-6 border border-surface-800">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-surface-800 border border-surface-700 flex items-center justify-center text-slate-200">
                <Github className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-base">Import from Public GitHub URL</h3>
                <p className="text-xs text-slate-400">Clone and scan public repository archive</p>
              </div>
            </div>

            <form onSubmit={handleGithubSubmit} className="space-y-3">
              <input
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/fastapi/fastapi"
                disabled={isLoading}
                className="w-full px-4 py-2.5 rounded-xl bg-surface-900 border border-surface-700 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
              <button
                type="submit"
                disabled={isLoading || !githubUrl.trim()}
                className="w-full py-2.5 rounded-xl font-medium text-xs bg-surface-800 hover:bg-surface-700 text-slate-100 border border-surface-700 hover:border-slate-500 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Fetch & Scan Repository"}
              </button>
            </form>
          </div>

          <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-brand-400" />
            <span>Static AST analysis only; code is never executed.</span>
          </div>
        </div>
      </div>

      {/* Recent Projects List */}
      {recentProjects.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              Previous Projects ({recentProjects.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {recentProjects.map((p) => (
              <div
                key={p.id}
                onClick={() => onSelectProject(p.id)}
                className="p-4 rounded-xl glass-card hover:bg-surface-800/60 border border-surface-800 hover:border-slate-600 cursor-pointer transition-all flex items-center justify-between group"
              >
                <div className="space-y-1 truncate pr-2">
                  <h4 className="text-sm font-medium text-white truncate group-hover:text-brand-300">
                    {p.name}
                  </h4>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="capitalize">{p.source_type}</span>
                    <span>•</span>
                    <span>{p.dependencies_count} deps</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-slate-200 group-hover:translate-x-0.5 transition-all shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
