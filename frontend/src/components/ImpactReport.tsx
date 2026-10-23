import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle,
  HelpCircle,
  Search,
  Filter,
  Download,
  ExternalLink,
  Code2,
  FileCheck2,
  Sparkles,
  ArrowLeft,
  ChevronDown,
} from "lucide-react";
import {
  ScanReportResponse,
  FindingResponse,
  Severity,
  ChangeType,
  AffectsProject,
} from "../types";
import { api } from "../api/client";

interface ImpactReportProps {
  report: ScanReportResponse;
  onOpenEvidence: (finding: FindingResponse) => void;
  onOpenExplain: (finding: FindingResponse) => void;
  onBackToProject: () => void;
}

export const ImpactReport: React.FC<ImpactReportProps> = ({
  report,
  onOpenEvidence,
  onOpenExplain,
  onBackToProject,
}) => {
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [selectedPackage, setSelectedPackage] = useState<string>("all");
  const [selectedAffects, setSelectedAffects] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Extract unique packages
  const packagesList = useMemo(() => {
    return Array.from(new Set(report.findings.map((f) => f.package))).sort();
  }, [report.findings]);

  // Filter findings
  const filteredFindings = useMemo(() => {
    return report.findings.filter((f) => {
      if (selectedSeverity !== "all" && f.severity !== selectedSeverity) return false;
      if (selectedPackage !== "all" && f.package !== selectedPackage) return false;
      if (selectedAffects !== "all" && f.affects_project !== selectedAffects) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesSummary = f.change_summary.toLowerCase().includes(q);
        const matchesWhy = f.why_it_matters.toLowerCase().includes(q);
        const matchesPkg = f.package.toLowerCase().includes(q);
        return matchesSummary || matchesWhy || matchesPkg;
      }
      return true;
    });
  }, [report.findings, selectedSeverity, selectedPackage, selectedAffects, searchQuery]);

  const getSeverityBadge = (sev: Severity) => {
    switch (sev) {
      case "critical":
        return "bg-rose-500/15 text-rose-300 border-rose-500/30";
      case "high":
        return "bg-orange-500/15 text-orange-300 border-orange-500/30";
      case "medium":
        return "bg-amber-500/15 text-amber-300 border-amber-500/30";
      case "low":
        return "bg-blue-500/15 text-blue-300 border-blue-500/30";
      default:
        return "bg-slate-500/15 text-slate-300 border-slate-500/30";
    }
  };

  const getAffectsBadge = (aff: AffectsProject) => {
    switch (aff) {
      case "yes":
        return "bg-rose-500/10 text-rose-300 border-rose-500/20";
      case "likely":
        return "bg-amber-500/10 text-amber-300 border-amber-500/20";
      case "unlikely":
        return "bg-slate-500/10 text-slate-400 border-slate-500/20";
      default:
        return "bg-surface-800 text-slate-400 border-surface-700";
    }
  };

  return (
    <div className="space-y-8 py-4 max-w-6xl mx-auto">
      {/* Report Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-800 pb-6">
        <div className="space-y-1">
          <button
            onClick={onBackToProject}
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Project Overview</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Change Impact Report
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-300 border border-brand-500/20">
              {report.findings.length} findings
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Project: <strong className="text-slate-200">{report.project_name}</strong> • Scan ID: <code className="text-slate-400">{report.scan_id.slice(0, 8)}</code>
          </p>
        </div>

        {/* Export buttons */}
        <div className="flex items-center gap-2">
          <a
            href={api.getExportMarkdownUrl(report.scan_id)}
            download
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-surface-800 hover:bg-surface-700 text-slate-200 border border-surface-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-brand-400" />
            <span>Export Markdown</span>
          </a>
          <a
            href={api.getExportJsonUrl(report.scan_id)}
            download
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-surface-800 hover:bg-surface-700 text-slate-200 border border-surface-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-teal-400" />
            <span>Export JSON</span>
          </a>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
        <div className="p-4 rounded-xl glass-card border border-surface-800 text-center space-y-1">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total</p>
          <p className="text-2xl font-extrabold text-white">{report.total_findings}</p>
        </div>
        <div className="p-4 rounded-xl glass-card border border-rose-500/20 text-center space-y-1">
          <p className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider">Critical</p>
          <p className="text-2xl font-extrabold text-rose-300">{report.severity_counts.critical}</p>
        </div>
        <div className="p-4 rounded-xl glass-card border border-orange-500/20 text-center space-y-1">
          <p className="text-[11px] font-semibold text-orange-400 uppercase tracking-wider">High</p>
          <p className="text-2xl font-extrabold text-orange-300">{report.severity_counts.high}</p>
        </div>
        <div className="p-4 rounded-xl glass-card border border-amber-500/20 text-center space-y-1">
          <p className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">Medium</p>
          <p className="text-2xl font-extrabold text-amber-300">{report.severity_counts.medium}</p>
        </div>
        <div className="p-4 rounded-xl glass-card border border-blue-500/20 text-center space-y-1">
          <p className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider">Low</p>
          <p className="text-2xl font-extrabold text-blue-300">{report.severity_counts.low}</p>
        </div>
        <div className="p-4 rounded-xl glass-card border border-slate-500/20 text-center space-y-1">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Info</p>
          <p className="text-2xl font-extrabold text-slate-300">{report.severity_counts.info}</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-xl glass-panel border border-surface-800 flex flex-wrap items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search change summaries, symbols, or packages..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-2">
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </select>

          {/* Package Filter */}
          <select
            value={selectedPackage}
            onChange={(e) => setSelectedPackage(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Packages</option>
            {packagesList.map((pkg) => (
              <option key={pkg} value={pkg}>
                {pkg}
              </option>
            ))}
          </select>

          {/* Affects Filter */}
          <select
            value={selectedAffects}
            onChange={(e) => setSelectedAffects(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="all">Affects Project?</option>
            <option value="yes">Affects: Yes</option>
            <option value="likely">Affects: Likely</option>
            <option value="unlikely">Affects: Unlikely</option>
            <option value="unknown">Affects: Unknown</option>
          </select>
        </div>
      </div>

      {/* Findings List */}
      <div className="space-y-4">
        {filteredFindings.length === 0 ? (
          <div className="p-12 text-center rounded-2xl glass-panel border border-surface-800 space-y-2">
            <CheckCircle className="w-8 h-8 text-brand-400 mx-auto" />
            <h3 className="font-semibold text-white text-base">No Matching Findings</h3>
            <p className="text-xs text-slate-400">
              No findings matched the selected severity or search criteria.
            </p>
          </div>
        ) : (
          filteredFindings.map((finding) => (
            <div
              key={finding.id}
              className="p-6 rounded-2xl glass-card border border-surface-800 space-y-4 hover:border-slate-700 transition-all shadow-md"
            >
              {/* Finding Header */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="font-bold font-mono text-sm text-brand-300 bg-surface-900 px-2.5 py-1 rounded-lg border border-surface-700">
                    {finding.package}
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider border ${getSeverityBadge(
                      finding.severity
                    )}`}
                  >
                    {finding.severity}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wider bg-surface-800 text-slate-400 border border-surface-700">
                    {finding.change_type.replace("_", " ")}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getAffectsBadge(
                      finding.affects_project
                    )}`}
                  >
                    Affects Code: <span className="uppercase">{finding.affects_project}</span>
                  </span>
                  <span className="text-xs text-slate-500 font-mono">
                    {(finding.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>

              {/* Change Summary */}
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-white leading-snug">
                  {finding.change_summary}
                </h3>
                <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800/80 text-xs text-slate-300 leading-relaxed">
                  <span className="text-brand-400 font-semibold">Why this matters: </span>
                  {finding.why_it_matters}
                </div>
              </div>

              {/* Code references preview */}
              {finding.code_references.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
                    <Code2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Mapped Code Locations ({finding.code_references.length})</span>
                  </div>
                  <div className="space-y-1.5">
                    {finding.code_references.slice(0, 2).map((ref, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-lg bg-surface-950 border border-surface-800 text-xs font-mono flex items-center justify-between"
                      >
                        <span className="text-emerald-300 truncate max-w-md">
                          {ref.snippet}
                        </span>
                        <span className="text-slate-500 shrink-0 font-sans text-[11px]">
                          {ref.file_path}:{ref.line_number}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Checks */}
              {finding.recommended_checks.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <FileCheck2 className="w-3.5 h-3.5 text-brand-400" />
                    <span>Recommended Checks</span>
                  </p>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-slate-300">
                    {finding.recommended_checks.map((chk, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-surface-900/60 p-2 rounded-lg border border-surface-800/60">
                        <span className="text-brand-400 font-bold">•</span>
                        <span>{chk}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Actions Footer */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-surface-800/70">
                <div className="flex items-center gap-2">
                  {finding.suggested_tests.slice(0, 2).map((tst, idx) => (
                    <span
                      key={idx}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-900 text-slate-400 border border-surface-800"
                    >
                      {tst}
                    </span>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onOpenExplain(finding)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white border border-surface-700 transition-colors flex items-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-teal-400" />
                    <span>Why was this flagged?</span>
                  </button>

                  <button
                    onClick={() => onOpenEvidence(finding)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/15 hover:bg-brand-500/25 text-brand-300 border border-brand-500/30 transition-colors flex items-center gap-1.5"
                  >
                    <span>View Evidence</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
