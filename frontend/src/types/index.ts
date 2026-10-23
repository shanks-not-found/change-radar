export type ChangeType =
  | "breaking"
  | "deprecation"
  | "removal"
  | "security"
  | "behavior_change"
  | "feature"
  | "other";

export type AffectsProject = "yes" | "likely" | "unlikely" | "unknown";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface CodeReference {
  file_path: string;
  line_number: number;
  snippet: string;
  symbol?: string | null;
}

export interface EvidenceItem {
  chunk_id: string;
  url: string;
  version: string;
  date?: string | null;
  quoted_passage: string;
}

export interface FindingExplainability {
  retrieval_scores: Record<string, number>;
  matched_symbols: string[];
  reasoning_trail: string[];
  validation_status: string;
}

export interface FindingResponse {
  id: string;
  scan_id: string;
  project_id: string;
  package: string;
  change_summary: string;
  change_type: ChangeType;
  affects_project: AffectsProject;
  severity: Severity;
  confidence: number;
  why_it_matters: string;
  code_references: CodeReference[];
  recommended_checks: string[];
  suggested_tests: string[];
  evidence: EvidenceItem[];
  uncertainty_notes?: string | null;
  explainability: FindingExplainability;
  created_at: string;
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export type ScanStage =
  | "pending"
  | "parsing"
  | "scanning_code"
  | "fetching_releases"
  | "fetching_advisories"
  | "indexing"
  | "retrieving"
  | "analyzing"
  | "completed"
  | "failed";

export interface ScanStatusResponse {
  scan_id: string;
  project_id: string;
  status: ScanStage;
  stage_description: string;
  progress_percentage: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface ScanReportResponse {
  scan_id: string;
  project_id: string;
  project_name: string;
  status: ScanStage;
  created_at: string;
  total_findings: number;
  severity_counts: SeverityCounts;
  affects_counts: Record<string, number>;
  findings: FindingResponse[];
}

export interface DependencyInfo {
  id?: number | null;
  package_name: string;
  specifier?: string | null;
  pinned_version?: string | null;
  source_file: string;
  latest_version?: string | null;
  vulnerability_count: number;
  usage_count: number;
}

export interface ProjectResponse {
  id: string;
  name: string;
  source_type: "zip" | "github" | "demo";
  source_ref?: string | null;
  created_at: string;
  dependencies_count: number;
  scans_count: number;
}

export interface ProjectDetailResponse extends ProjectResponse {
  dependencies: DependencyInfo[];
  total_code_references: number;
  symbols_used: string[];
}

export interface FindingEvidenceResponse {
  finding_id: string;
  package: string;
  evidence_items: EvidenceItem[];
  code_references: CodeReference[];
}

export interface CitedSource {
  chunk_id: string;
  url: string;
  package: string;
  version: string;
  snippet: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  cited_sources: CitedSource[];
  confidence: number;
  caveats?: string | null;
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  llm_configured: boolean;
  gemini_model: string;
  embedding_model: string;
  embedding_loaded: boolean;
  database_ok: boolean;
  chroma_ok: boolean;
}
