import React from "react";
import { Package, Code2, Play, Calendar, FileCode, CheckCircle, ShieldAlert, ArrowLeft } from "lucide-react";
import { ProjectDetailResponse } from "../types";

interface ProjectOverviewProps {
  project: ProjectDetailResponse;
  onStartScan: () => Promise<void>;
  onBack: () => void;
  isScanning: boolean;
}

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  project,
  onStartScan,
  onBack,
  isScanning,
}) => {
  return (
    <div className="space-y-8 py-4 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-800 pb-6">
        <div className="space-y-2">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Switch Project</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {project.name}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize bg-surface-800 text-slate-300 border border-surface-700">
              {project.source_type}
            </span>
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5" />
            <span>Created {new Date(project.created_at).toLocaleString()}</span>
          </p>
        </div>

        {/* Primary Action Button */}
        <div>
          <button
            onClick={onStartScan}
            disabled={isScanning}
            className="w-full sm:w-auto px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-brand-500 to-emerald-500 hover:from-brand-600 hover:to-emerald-600 text-surface-950 shadow-lg shadow-brand-500/20 transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>{isScanning ? "Scan in Progress..." : "Run Impact Analysis"}</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-xl glass-card border border-surface-800 space-y-1">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
            <Package className="w-4 h-4 text-brand-400" />
            <span>Detected Dependencies</span>
          </div>
          <p className="text-2xl font-bold text-white">{project.dependencies_count}</p>
          <p className="text-[11px] text-slate-500">From requirements.txt & pyproject.toml</p>
        </div>

        <div className="p-5 rounded-xl glass-card border border-surface-800 space-y-1">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
            <Code2 className="w-4 h-4 text-emerald-400" />
            <span>AST Code References</span>
          </div>
          <p className="text-2xl font-bold text-white">{project.total_code_references}</p>
          <p className="text-[11px] text-slate-500">Static AST call sites and imports tracked</p>
        </div>

        <div className="p-5 rounded-xl glass-card border border-surface-800 space-y-1">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
            <FileCode className="w-4 h-4 text-teal-400" />
            <span>Unique API Symbols</span>
          </div>
          <p className="text-2xl font-bold text-white">{project.symbols_used.length}</p>
          <p className="text-[11px] text-slate-500">Functions, classes & attributes invoked</p>
        </div>
      </div>

      {/* Dependencies Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Project Dependencies</h2>
          <span className="text-xs text-slate-400">{project.dependencies.length} packages pinned</span>
        </div>

        <div className="rounded-xl glass-panel border border-surface-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-surface-900/90 text-xs uppercase text-slate-400 tracking-wider border-b border-surface-800">
                <tr>
                  <th className="px-6 py-3.5">Package</th>
                  <th className="px-6 py-3.5">Pinned Version</th>
                  <th className="px-6 py-3.5">Source File</th>
                  <th className="px-6 py-3.5 text-right">AST Usage Count</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60 font-mono text-xs">
                {project.dependencies.map((dep) => (
                  <tr key={dep.package_name} className="hover:bg-surface-800/40 transition-colors">
                    <td className="px-6 py-3.5 font-medium text-white flex items-center gap-2 font-sans">
                      <div className="w-2 h-2 rounded-full bg-brand-400" />
                      <span>{dep.package_name}</span>
                    </td>
                    <td className="px-6 py-3.5">
                      {dep.pinned_version ? (
                        <span className="px-2 py-0.5 rounded bg-surface-800 text-brand-300 border border-brand-500/20">
                          {dep.pinned_version}
                        </span>
                      ) : (
                        <span className="text-slate-500">{dep.specifier || "*"}</span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 text-slate-400 font-sans">
                      {dep.source_file}
                    </td>
                    <td className="px-6 py-3.5 text-right font-sans">
                      <span className="px-2 py-0.5 rounded bg-surface-800 text-slate-300">
                        {dep.usage_count} call sites
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Invoked Symbols Cloud */}
      {project.symbols_used.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Detected API Symbols in Scanned Code ({project.symbols_used.length})
          </h3>
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-3 rounded-xl glass-card border border-surface-800">
            {project.symbols_used.map((sym) => (
              <span
                key={sym}
                className="px-2.5 py-1 rounded-md text-xs font-mono bg-surface-900 text-slate-300 border border-surface-700/60"
              >
                {sym}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
