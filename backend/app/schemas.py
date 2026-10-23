from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# ------------------------------------------------------------------------------
# Code References and Evidence Models
# ------------------------------------------------------------------------------

class CodeReference(BaseModel):
    file_path: str = Field(description="Relative path of the source file in the project")
    line_number: int = Field(description="1-indexed line number where the API/symbol is used")
    snippet: str = Field(description="Code line or snippet showing actual API usage")
    symbol: Optional[str] = Field(default=None, description="Imported or invoked symbol name")

class EvidenceItem(BaseModel):
    chunk_id: str = Field(description="Unique ID of the retrieved chunk cited as evidence")
    url: str = Field(description="Official URL for the release note or advisory")
    version: str = Field(description="Target or affected version mentioned in evidence")
    date: Optional[str] = Field(default=None, description="Publication or release date")
    quoted_passage: str = Field(description="Exact or near-exact quote from the retrieved text that supports this finding")

# ------------------------------------------------------------------------------
# LLM Structured Output Models
# ------------------------------------------------------------------------------

ChangeType = Literal[
    "breaking",
    "deprecation",
    "removal",
    "security",
    "behavior_change",
    "feature",
    "other",
]

AffectsProject = Literal["yes", "likely", "unlikely", "unknown"]

Severity = Literal["critical", "high", "medium", "low", "info"]

class ImpactFinding(BaseModel):
    package: str = Field(description="Name of the affected Python package")
    change_summary: str = Field(description="Clear, concise summary of the external change")
    change_type: ChangeType = Field(description="Category of the detected change")
    affects_project: AffectsProject = Field(description="Whether the project's scanned code is affected")
    severity: Severity = Field(description="Impact severity rating")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    why_it_matters: str = Field(description="Explanation of why this matters to the user's specific codebase")
    code_references: List[CodeReference] = Field(default_factory=list, description="User code locations directly mapped to this change")
    recommended_checks: List[str] = Field(default_factory=list, description="Actionable verification checks for the developer")
    suggested_tests: List[str] = Field(default_factory=list, description="Specific unit or integration tests to write or run")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Grounded citations from retrieved release notes or advisories")
    uncertainty_notes: Optional[str] = Field(default="", description="Explicit caveats if evidence is ambiguous or incomplete")

class ImpactContext(BaseModel):
    package: str
    specifier: Optional[str] = None
    pinned_version: Optional[str] = None
    scanned_code_references: List[CodeReference] = Field(default_factory=list)
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)

class CitedSource(BaseModel):
    chunk_id: str
    url: str
    package: str
    version: str
    snippet: str

class GroundedAnswer(BaseModel):
    answer: str
    cited_sources: List[CitedSource] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    caveats: Optional[str] = None

# ------------------------------------------------------------------------------
# Project API Models
# ------------------------------------------------------------------------------

class ProjectCreateGitHub(BaseModel):
    repo_url: str = Field(description="Public GitHub repository URL (e.g. https://github.com/owner/repo)")
    name: Optional[str] = None

class DependencyInfo(BaseModel):
    id: Optional[int] = None
    package_name: str
    specifier: Optional[str] = None
    pinned_version: Optional[str] = None
    source_file: str
    latest_version: Optional[str] = None
    vulnerability_count: int = 0
    usage_count: int = 0

class CodeUsageSummary(BaseModel):
    symbol: str
    count: int
    files: List[str]

class ProjectResponse(BaseModel):
    id: str
    name: str
    source_type: Literal["zip", "github", "demo"]
    source_ref: Optional[str] = None
    created_at: datetime
    dependencies_count: int = 0
    scans_count: int = 0

class ProjectDetailResponse(ProjectResponse):
    dependencies: List[DependencyInfo] = Field(default_factory=list)
    total_code_references: int = 0
    symbols_used: List[str] = Field(default_factory=list)

# ------------------------------------------------------------------------------
# Scan API Models
# ------------------------------------------------------------------------------

ScanStage = Literal[
    "pending",
    "parsing",
    "scanning_code",
    "fetching_releases",
    "fetching_advisories",
    "indexing",
    "retrieving",
    "analyzing",
    "completed",
    "failed",
]

class ScanCreateResponse(BaseModel):
    scan_id: str
    project_id: str
    status: ScanStage
    message: str

class FindingExplainability(BaseModel):
    retrieval_scores: Dict[str, float] = Field(default_factory=dict)
    matched_symbols: List[str] = Field(default_factory=list)
    reasoning_trail: List[str] = Field(default_factory=list)
    validation_status: str = "verified"

class FindingResponse(ImpactFinding):
    id: str
    scan_id: str
    project_id: str
    created_at: datetime
    explainability: FindingExplainability

class SeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0

class ScanStatusResponse(BaseModel):
    scan_id: str
    project_id: str
    status: ScanStage
    stage_description: str
    progress_percentage: int = 0
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

class ScanReportResponse(BaseModel):
    scan_id: str
    project_id: str
    project_name: str
    status: ScanStage
    created_at: datetime
    total_findings: int
    severity_counts: SeverityCounts
    affects_counts: Dict[str, int]
    findings: List[FindingResponse]

# ------------------------------------------------------------------------------
# Evidence & Q&A Models
# ------------------------------------------------------------------------------

class FindingEvidenceResponse(BaseModel):
    finding_id: str
    package: str
    evidence_items: List[EvidenceItem]
    code_references: List[CodeReference]

class AskRequest(BaseModel):
    question: str = Field(min_length=3, description="User question regarding the project's dependencies and impact")

class AskResponse(BaseModel):
    question: str
    answer: str
    cited_sources: List[CitedSource]
    confidence: float
    caveats: Optional[str] = None

# ------------------------------------------------------------------------------
# Health Model
# ------------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_configured: bool
    groq_model: str
    embedding_model: str
    embedding_loaded: bool
    database_ok: bool
    chroma_ok: bool
