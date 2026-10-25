import React, { useEffect, useState, useRef } from "react";
import { Navbar } from "./components/Navbar";
import { UploadSection } from "./components/UploadSection";
import { ProjectOverview } from "./components/ProjectOverview";
import { ScanProgress } from "./components/ScanProgress";
import { ImpactReport } from "./components/ImpactReport";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { ExplainModal } from "./components/ExplainModal";
import { AskPanel } from "./components/AskPanel";
import {
  HealthResponse,
  ProjectResponse,
  ProjectDetailResponse,
  ScanStatusResponse,
  ScanReportResponse,
  FindingResponse,
  FindingEvidenceResponse,
  FindingExplainability,
} from "./types";
import { api } from "./api/client";

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [recentProjects, setRecentProjects] = useState<ProjectResponse[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectDetailResponse | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatusResponse | null>(null);
  const [currentReport, setCurrentReport] = useState<ScanReportResponse | null>(null);
  
  // Modals & Panels
  const [activeEvidence, setActiveEvidence] = useState<FindingEvidenceResponse | null>(null);
  const [activeExplain, setActiveExplain] = useState<{
    package: string;
    explainability: FindingExplainability;
  } | null>(null);
  const [isAskOpen, setIsAskOpen] = useState(false);

  // Loading flags
  const [isLoading, setIsLoading] = useState(false);
  const [view, setView] = useState<"upload" | "project" | "scanning" | "report">("upload");

  const pollIntervalRef = useRef<number | null>(null);

  // Initial load
  useEffect(() => {
    fetchHealth();
    loadProjects();
  }, []);

  const fetchHealth = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch {
      // Backend not yet reachable
    }
  };

  const loadProjects = async () => {
    try {
      const list = await api.listProjects();
      setRecentProjects(list);
    } catch {
      // Ignore initial load failure
    }
  };

  // Upload ZIP
  const handleUploadZip = async (file: File) => {
    setIsLoading(true);
    try {
      const proj = await api.uploadProjectZip(file);
      setCurrentProject(proj);
      setView("project");
      loadProjects();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Import GitHub URL
  const handleImportGithub = async (url: string) => {
    setIsLoading(true);
    try {
      const proj = await api.importFromGitHub(url);
      setCurrentProject(proj);
      setView("project");
      loadProjects();
    } catch (err: any) {
      alert(`GitHub import failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Load Demo Project
  const handleLoadDemo = async () => {
    setIsLoading(true);
    try {
      const proj = await api.loadDemoProject();
      setCurrentProject(proj);
      setView("project");
      loadProjects();
    } catch (err: any) {
      alert(`Failed to load demo project: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Select project from past list
  const handleSelectProject = async (id: string) => {
    setIsLoading(true);
    try {
      const proj = await api.getProjectDetail(id);
      setCurrentProject(proj);

      // Check if project has an existing completed scan
      const pastScans = await api.listProjectScans(id);
      if (pastScans.length > 0 && pastScans[0].status === "completed") {
        const rep = await api.getScanReport(pastScans[0].scan_id);
        setCurrentReport(rep);
        setView("report");
      } else {
        setView("project");
      }
    } catch (err: any) {
      alert(`Failed to select project: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Start scan
  const handleStartScan = async () => {
    if (!currentProject) return;
    setIsLoading(true);
    try {
      const res = await api.startScan(currentProject.id);
      setView("scanning");
      pollScanProgress(res.scan_id);
    } catch (err: any) {
      alert(`Failed to start scan: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Poll scan progress
  const pollScanProgress = (scanId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    const check = async () => {
      try {
        const status = await api.getScanStatus(scanId);
        setScanStatus(status);

        if (status.status === "completed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          const rep = await api.getScanReport(scanId);
          setCurrentReport(rep);
          setView("report");
          loadProjects();
        } else if (status.status === "failed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      } catch {
        // Polling retry
      }
    };

    check();
    pollIntervalRef.current = window.setInterval(check, 1000);
  };

  // Open Evidence Drawer
  const handleOpenEvidence = async (finding: FindingResponse) => {
    try {
      const ev = await api.getFindingEvidence(finding.id);
      setActiveEvidence(ev);
    } catch (err: any) {
      alert(`Could not fetch evidence: ${err.message}`);
    }
  };

  // Open Explain Modal
  const handleOpenExplain = async (finding: FindingResponse) => {
    try {
      const ex = await api.getFindingExplainability(finding.id);
      setActiveExplain({
        package: finding.package,
        explainability: ex,
      });
    } catch (err: any) {
      alert(`Could not fetch explainability: ${err.message}`);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-surface-950 text-slate-100 selection:bg-brand-500/25">
      <Navbar
        health={health}
        onReset={() => setView("upload")}
        onRefreshHealth={() => {
          fetchHealth();
          loadProjects();
        }}
        onOpenAsk={() => {
          if (!currentProject) {
            alert("Please select or load a project before asking AI questions.");
            return;
          }
          setIsAskOpen(true);
        }}
      />

      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6">
        {view === "upload" && (
          <UploadSection
            onUploadZip={handleUploadZip}
            onImportGithub={handleImportGithub}
            onLoadDemo={handleLoadDemo}
            recentProjects={recentProjects}
            onSelectProject={handleSelectProject}
            isLoading={isLoading}
          />
        )}

        {view === "project" && currentProject && (
          <ProjectOverview
            project={currentProject}
            onStartScan={handleStartScan}
            onBack={() => setView("upload")}
            isScanning={isLoading}
          />
        )}

        {view === "scanning" && scanStatus && (
          <ScanProgress status={scanStatus} />
        )}

        {view === "report" && currentReport && (
          <ImpactReport
            report={currentReport}
            onOpenEvidence={handleOpenEvidence}
            onOpenExplain={handleOpenExplain}
            onBackToProject={() => setView("project")}
          />
        )}
      </main>

      {/* Slide-out Evidence Drawer */}
      <EvidenceDrawer
        evidence={activeEvidence}
        onClose={() => setActiveEvidence(null)}
      />

      {/* Explainability Modal */}
      {activeExplain && (
        <ExplainModal
          package_name={activeExplain.package}
          explainability={activeExplain.explainability}
          onClose={() => setActiveExplain(null)}
        />
      )}

      {/* Ask AI Assistant Panel */}
      {currentProject && (
        <AskPanel
          projectId={currentProject.id}
          projectName={currentProject.name}
          isOpen={isAskOpen}
          onClose={() => setIsAskOpen(false)}
        />
      )}

      <footer className="border-t border-surface-800/80 py-6 text-center text-xs text-slate-500 glass-panel">
        <p>StackSignal — AI Dependency Change Impact Analysis • Local Hybrid Retrieval & AST Verification</p>
      </footer>
    </div>
  );
};
