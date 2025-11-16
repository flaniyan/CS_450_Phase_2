"""
Pydantic models for OpenAPI spec schemas.
All models match the schemas defined in ece461_fall_2025_openapi_spec.yaml
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Annotated
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class ArtifactType(str, Enum):
    """Artifact category."""
    model = "model"
    dataset = "dataset"
    code = "code"


class HealthStatus(str, Enum):
    """Aggregate health classification for monitored systems."""
    ok = "ok"
    degraded = "degraded"
    critical = "critical"
    unknown = "unknown"


class AuditAction(str, Enum):
    """Artifact audit action types."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DOWNLOAD = "DOWNLOAD"
    RATE = "RATE"
    AUDIT = "AUDIT"


class IssueSeverity(str, Enum):
    """Issue severity levels."""
    info = "info"
    warning = "warning"
    error = "error"


# ============================================================================
# Base Types
# ============================================================================

# ArtifactID with pattern validation
ArtifactID = Annotated[
    str,
    Field(
        ...,
        pattern=r'^[a-zA-Z0-9\-]+$',
        description="Unique identifier for use with artifact endpoints."
    )
]


class ArtifactName(str):
    """Name of an artifact."""
    pass


class AuthenticationToken(str):
    """Authentication token (e.g., JWT)."""
    pass


class EnumerateOffset(str):
    """Offset in pagination."""
    pass


# ============================================================================
# User & Authentication Schemas
# ============================================================================

class User(BaseModel):
    """User information."""
    name: str
    is_admin: bool


class UserAuthenticationInfo(BaseModel):
    """Authentication info for a user."""
    password: str = Field(..., description="Password for a user. Per the spec, this should be a \"strong\" password.")


class AuthenticationRequest(BaseModel):
    """Authentication request payload."""
    user: User
    secret: UserAuthenticationInfo


# ============================================================================
# Artifact Schemas
# ============================================================================

class ArtifactMetadata(BaseModel):
    """Artifact metadata containing name, id, and type."""
    name: ArtifactName
    id: ArtifactID
    type: ArtifactType


class ArtifactData(BaseModel):
    """Source location for ingesting an artifact."""
    url: HttpUrl = Field(..., description="Artifact source url used during ingest.")
    download_url: Optional[HttpUrl] = Field(
        None,
        description="Direct download link served by your server for retrieving the stored artifact bundle. Present only in responses.",
        read_only=True
    )


class Artifact(BaseModel):
    """Artifact envelope containing metadata and ingest details."""
    metadata: ArtifactMetadata
    data: ArtifactData


class ArtifactQuery(BaseModel):
    """Query for searching artifacts."""
    name: ArtifactName
    types: Optional[List[ArtifactType]] = Field(
        None,
        description="Optional list of artifact types to filter results."
    )


class ArtifactRegEx(BaseModel):
    """Regular expression query for searching artifacts."""
    regex: str = Field(
        ...,
        description="A regular expression over artifact names and READMEs that is used for searching for an artifact"
    )


class ArtifactCostEntry(BaseModel):
    """Cost entry for a single artifact."""
    standalone_cost: Optional[float] = Field(
        None,
        description="The standalone cost of this artifact excluding dependencies. Required when `dependency = true` in the request."
    )
    total_cost: float = Field(..., description="The total cost of the artifact.")


class ArtifactCost(BaseModel):
    """
    Artifact Cost aggregates the total download size (in MB) required for the artifact.
    This is a dictionary-like model that allows dynamic artifact IDs as keys.
    """
    model_config = ConfigDict(extra="allow")
    
    def __getitem__(self, key: str) -> ArtifactCostEntry:
        """Get cost entry for an artifact ID."""
        value = getattr(self, key, None)
        if value is None:
            raise KeyError(key)
        if isinstance(value, dict):
            return ArtifactCostEntry(**value)
        return value
    
    def get(self, key: str, default: Optional[ArtifactCostEntry] = None) -> Optional[ArtifactCostEntry]:
        """Get cost entry with optional default."""
        value = getattr(self, key, None)
        if value is None:
            return default
        if isinstance(value, dict):
            return ArtifactCostEntry(**value)
        return value
    
    def keys(self):
        """Get all artifact IDs."""
        return [k for k in self.__dict__.keys() if k != "model_config"]
    
    def values(self):
        """Get all cost entries."""
        return [self[k] for k in self.keys()]
    
    def items(self):
        """Get all (artifact_id, cost_entry) pairs."""
        return [(k, self[k]) for k in self.keys()]
    
    def model_dump(self, **kwargs) -> Dict[str, Dict[str, float]]:
        """Convert to dict format for JSON serialization."""
        result = {}
        for key in self.keys():
            entry = self[key]
            if isinstance(entry, ArtifactCostEntry):
                result[key] = entry.model_dump(**kwargs)
            else:
                result[key] = entry
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Dict[str, float]]) -> "ArtifactCost":
        """Create from dict format."""
        instance = cls()
        for key, value in data.items():
            setattr(instance, key, ArtifactCostEntry(**value))
        return instance


class ArtifactAuditEntry(BaseModel):
    """One entry in an artifact's audit history."""
    user: User
    date: datetime = Field(..., description="Date of activity using ISO-8601 Datetime standard in UTC format.")
    artifact: ArtifactMetadata
    action: AuditAction


# ============================================================================
# Lineage Schemas
# ============================================================================

class ArtifactLineageNode(BaseModel):
    """A single node in an artifact lineage graph."""
    artifact_id: ArtifactID
    name: str = Field(..., description="Human-readable label for the node.")
    source: str = Field(..., description="Provenance for how the node was discovered.")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata captured for lineage analysis."
    )


class ArtifactLineageEdge(BaseModel):
    """Directed relationship between two lineage nodes."""
    from_node_artifact_id: ArtifactID = Field(..., description="Identifier of the upstream node.")
    to_node_artifact_id: ArtifactID = Field(..., description="Identifier of the downstream node.")
    relationship: str = Field(..., description="Qualitative description of the edge.")


class ArtifactLineageGraph(BaseModel):
    """Complete lineage graph for an artifact."""
    nodes: List[ArtifactLineageNode] = Field(..., description="Nodes participating in the lineage graph.")
    edges: List[ArtifactLineageEdge] = Field(..., description="Directed edges describing lineage relationships.")


# ============================================================================
# License Check Schema
# ============================================================================

class SimpleLicenseCheckRequest(BaseModel):
    """Request payload for artifact license compatibility analysis."""
    github_url: HttpUrl = Field(..., description="GitHub repository url to evaluate.")


# ============================================================================
# Model Rating Schema
# ============================================================================

class SizeScore(BaseModel):
    """Size suitability scores for common deployment targets."""
    raspberry_pi: float = Field(..., description="Size score for Raspberry Pi class devices.")
    jetson_nano: float = Field(..., description="Size score for Jetson Nano deployments.")
    desktop_pc: float = Field(..., description="Size score for desktop deployments.")
    aws_server: float = Field(..., description="Size score for cloud server deployments.")


class ModelRating(BaseModel):
    """Model rating summary generated by the evaluation service."""
    name: str = Field(..., description="Human-friendly label for the evaluated model.")
    category: str = Field(..., description="Model category assigned during evaluation.")
    net_score: float = Field(..., description="Overall score synthesizing all metrics.")
    net_score_latency: float = Field(..., description="Time (seconds) required to compute `net_score`.")
    ramp_up_time: float = Field(..., description="Ease-of-adoption rating for the model.")
    ramp_up_time_latency: float = Field(..., description="Time (seconds) required to compute `ramp_up_time`.")
    bus_factor: float = Field(..., description="Team redundancy score for the upstream project.")
    bus_factor_latency: float = Field(..., description="Time (seconds) required to compute `bus_factor`.")
    performance_claims: float = Field(..., description="Alignment between stated and observed performance.")
    performance_claims_latency: float = Field(..., description="Time (seconds) required to compute `performance_claims`.")
    license: float = Field(..., description="Licensing suitability score.")
    license_latency: float = Field(..., description="Time (seconds) required to compute `license`.")
    dataset_and_code_score: float = Field(..., description="Availability and quality of accompanying datasets and code.")
    dataset_and_code_score_latency: float = Field(..., description="Time (seconds) required to compute `dataset_and_code_score`.")
    dataset_quality: float = Field(..., description="Quality rating for associated datasets.")
    dataset_quality_latency: float = Field(..., description="Time (seconds) required to compute `dataset_quality`.")
    code_quality: float = Field(..., description="Quality rating for provided code artifacts.")
    code_quality_latency: float = Field(..., description="Time (seconds) required to compute `code_quality`.")
    reproducibility: float = Field(..., description="Likelihood that reported results can be reproduced.")
    reproducibility_latency: float = Field(..., description="Time (seconds) required to compute `reproducibility`.")
    reviewedness: float = Field(..., description="Measure of peer or community review coverage.")
    reviewedness_latency: float = Field(..., description="Time (seconds) required to compute `reviewedness`.")
    tree_score: float = Field(..., description="Supply-chain health score for model dependencies.")
    tree_score_latency: float = Field(..., description="Time (seconds) required to compute `tree_score`.")
    size_score: SizeScore = Field(..., description="Size suitability scores for common deployment targets.")
    size_score_latency: float = Field(..., description="Time (seconds) required to compute `size_score`.")


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthRequestSummary(BaseModel):
    """Request activity observed within the health window."""
    window_start: datetime = Field(..., description="Beginning of the aggregation window (UTC).")
    window_end: datetime = Field(..., description="End of the aggregation window (UTC).")
    total_requests: int = Field(0, ge=0, description="Number of API requests served during the window.")
    per_route: Dict[str, int] = Field(
        default_factory=dict,
        description="Request counts grouped by API route."
    )
    per_artifact_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Request counts grouped by artifact type (model/dataset/code)."
    )
    unique_clients: int = Field(0, ge=0, description="Distinct API clients observed in the window.")


class HealthComponentBrief(BaseModel):
    """Lightweight component-level status summary."""
    id: str = Field(..., description="Stable identifier for the component (e.g., ingest-worker, metrics).")
    status: HealthStatus
    display_name: Optional[str] = Field(None, description="Human readable component name.")
    issue_count: int = Field(0, ge=0, description="Number of outstanding issues contributing to the status.")
    last_event_at: Optional[datetime] = Field(None, description="Last significant event timestamp for the component.")


class HealthLogReference(BaseModel):
    """Link or descriptor for logs relevant to a health component."""
    label: str = Field(..., description="Human readable log descriptor (e.g., \"Ingest Worker 1\").")
    url: HttpUrl = Field(..., description="Direct link to download or tail the referenced log.")
    tail_available: Optional[bool] = Field(None, description="Indicates whether streaming tail access is supported.")
    last_updated_at: Optional[datetime] = Field(None, description="Timestamp of the latest log entry available for this reference.")


class HealthSummaryResponse(BaseModel):
    """High-level snapshot summarizing registry health and recent activity."""
    status: HealthStatus
    checked_at: datetime = Field(..., description="Timestamp when the health snapshot was generated (UTC).")
    window_minutes: int = Field(..., ge=5, description="Size of the trailing observation window in minutes.")
    uptime_seconds: Optional[int] = Field(None, ge=0, description="Seconds the registry API has been running.")
    version: Optional[str] = Field(None, description="Running service version or git SHA when available.")
    request_summary: Optional[HealthRequestSummary] = None
    components: Optional[List[HealthComponentBrief]] = Field(
        None,
        description="Rollup of component status ordered by severity."
    )
    logs: Optional[List[HealthLogReference]] = Field(
        None,
        description="Quick links or descriptors for recent log files."
    )


# HealthMetricValue is represented as Union[int, float, str, bool] directly
# No need for a separate model since it's used in Dict[str, Union[...]]


class HealthMetricMap(BaseModel):
    """Arbitrary metric key/value pairs describing component performance."""
    # Using Dict to represent additionalProperties
    metrics: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)


class HealthTimelineEntry(BaseModel):
    """Time-series datapoint for a component metric."""
    bucket: datetime = Field(..., description="Start timestamp of the sampled bucket (UTC).")
    value: float = Field(..., description="Observed value for the bucket (e.g., requests per minute).")
    unit: Optional[str] = Field(None, description="Unit associated with the metric value.")


class HealthIssue(BaseModel):
    """Outstanding issue or alert impacting a component."""
    code: str = Field(..., description="Machine readable issue identifier.")
    severity: IssueSeverity
    summary: str = Field(..., description="Short description of the issue.")
    details: Optional[str] = Field(None, description="Extended diagnostic detail and suggested remediation.")


class HealthComponentDetail(BaseModel):
    """Detailed status, metrics, and log references for a component."""
    id: str = Field(..., description="Stable identifier for the component.")
    status: HealthStatus
    observed_at: datetime = Field(..., description="Timestamp when data for this component was last collected (UTC).")
    display_name: Optional[str] = Field(None, description="Human readable component name.")
    description: Optional[str] = Field(None, description="Overview of the component's responsibility.")
    metrics: Optional[HealthMetricMap] = None
    issues: Optional[List[HealthIssue]] = Field(None, description="Outstanding issues impacting the component.")
    timeline: Optional[List[HealthTimelineEntry]] = Field(None, description="Time-series data for component metrics.")
    logs: Optional[List[HealthLogReference]] = Field(None, description="Log references for this component.")


class HealthComponentCollection(BaseModel):
    """Detailed health diagnostics broken down per component."""
    components: List[HealthComponentDetail] = Field(..., description="List of component health details.")
    generated_at: datetime = Field(..., description="Timestamp when the component report was created (UTC).")
    window_minutes: Optional[int] = Field(None, ge=5, description="Observation window applied to the component metrics.")

