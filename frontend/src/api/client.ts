import {
  HealthResponse,
  ProjectResponse,
  ProjectDetailResponse,
  ScanStatusResponse,
  ScanReportResponse,
  FindingEvidenceResponse,
  FindingExplainability,
  AskResponse,
} from "../types";

// Default live tunnel URL established via Cloudflare Tunnel
const DEFAULT_TUNNEL_URL = "https://strip-large-floors-unlike.trycloudflare.com";

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("STACKSIGNAL_API_URL");
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/$/, "");
    }
  }

  if (import.meta.env.VITE_API_URL) {
    return (import.meta.env.VITE_API_URL as string).replace(/\/$/, "");
  }

  if (import.meta.env.DEV) {
    return "http://localhost:8000";
  }

  return DEFAULT_TUNNEL_URL;
}

export function setApiBase(url: string) {
  if (typeof window !== "undefined") {
    if (url && url.trim()) {
      localStorage.setItem("STACKSIGNAL_API_URL", url.trim().replace(/\/$/, ""));
    } else {
      localStorage.removeItem("STACKSIGNAL_API_URL");
    }
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const base = getApiBase();
  const url = `${base}${endpoint}`;
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let errorDetail = `Request failed with status ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return resp.json();
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/api/health");
  },

  loadDemoProject(): Promise<ProjectDetailResponse> {
    return request<ProjectDetailResponse>("/api/demo/load", {
      method: "POST",
    });
  },

  async uploadProjectZip(file: File): Promise<ProjectDetailResponse> {
    const formData = new FormData();
    formData.append("file", file);
    return request<ProjectDetailResponse>("/api/projects/upload", {
      method: "POST",
      body: formData,
    });
  },

  importFromGitHub(repoUrl: string, name?: string): Promise<ProjectDetailResponse> {
    return request<ProjectDetailResponse>("/api/projects/from-github", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, name }),
    });
  },

  listProjects(): Promise<ProjectResponse[]> {
    return request<ProjectResponse[]>("/api/projects");
  },

  getProjectDetail(projectId: string): Promise<ProjectDetailResponse> {
    return request<ProjectDetailResponse>(`/api/projects/${projectId}`);
  },

  startScan(projectId: string): Promise<{ scan_id: string; project_id: string; status: string }> {
    return request(`/api/projects/${projectId}/scans`, {
      method: "POST",
    });
  },

  getScanStatus(scanId: string): Promise<ScanStatusResponse> {
    return request<ScanStatusResponse>(`/api/scans/${scanId}`);
  },

  getScanReport(scanId: string): Promise<ScanReportResponse> {
    return request<ScanReportResponse>(`/api/scans/${scanId}/report`);
  },

  getFindingEvidence(findingId: string): Promise<FindingEvidenceResponse> {
    return request<FindingEvidenceResponse>(`/api/findings/${findingId}/evidence`);
  },

  getFindingExplainability(findingId: string): Promise<FindingExplainability> {
    return request<FindingExplainability>(`/api/findings/${findingId}/explain`);
  },

  listProjectScans(projectId: string): Promise<ScanStatusResponse[]> {
    return request<ScanStatusResponse[]>(`/api/projects/${projectId}/scans`);
  },

  askQuestion(projectId: string, question: string): Promise<AskResponse> {
    return request<AskResponse>(`/api/projects/${projectId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  },

  getExportMarkdownUrl(scanId: string): string {
    return `${getApiBase()}/api/scans/${scanId}/export/markdown`;
  },

  getExportJsonUrl(scanId: string): string {
    return `${getApiBase()}/api/scans/${scanId}/export/json`;
  },
};
