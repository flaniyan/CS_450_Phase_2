from pydantic import BaseModel, Field, field_validator, field_serializer
from enum import Enum
from typing import List, Dict, Any, Optional, Union

class HealthStatus(str, Enum):
    """Aggregate health classification for monitored systems."""
    ok = "ok"
    degraded = "degraded"
    critical = "critical"
    unknown = "unknown"


# HealthMetricValue is a union type for flexible metric values
HealthMetricValue = Union[int, float, str, bool]


class HealthMetricMap(BaseModel):
    """Arbitrary metric key/value pairs describing component performance."""
    model_config = {"extra": "allow"}
    
    def model_dump(self) -> Dict[str, HealthMetricValue]:
        """Return as dictionary with metric names as keys."""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_') and isinstance(value, (int, float, str, bool)):
                result[key] = value
        return result


class HealthTimelineEntry(BaseModel):
    """Time-series datapoint for a component metric."""
    bucket: str = Field(..., description="Start timestamp of the sampled bucket (UTC).", format="date-time")
    value: float = Field(..., description="Observed value for the bucket (e.g., requests per minute).")
    unit: str | None = Field(None, description="Unit associated with the metric value.")


class HealthIssueSeverity(str, Enum):
    """Issue severity levels."""
    info = "info"
    warning = "warning"
    error = "error"


class HealthIssue(BaseModel):
    """Outstanding issue or alert impacting a component."""
    code: str = Field(..., description="Machine readable issue identifier.")
    severity: HealthIssueSeverity = Field(..., description="Issue severity.")
    summary: str = Field(..., description="Short description of the issue.")
    details: str | None = Field(None, description="Extended diagnostic detail and suggested remediation.")


class HealthLogReference(BaseModel):
    """Link or descriptor for logs relevant to a health component."""
    label: str = Field(..., description="Human readable log descriptor (e.g., \"Ingest Worker 1\").")
    url: str = Field(..., description="Direct link to download or tail the referenced log.", format="uri")
    tail_available: bool | None = Field(None, description="Indicates whether streaming tail access is supported.")
    last_updated_at: str | None = Field(None, description="Timestamp of the latest log entry available for this reference.", format="date-time")


class HealthRequestSummary(BaseModel):
    """Request activity observed within the health window."""
    window_start: str = Field(..., description="Beginning of the aggregation window (UTC).", format="date-time")
    window_end: str = Field(..., description="End of the aggregation window (UTC).", format="date-time")
    total_requests: int | None = Field(None, description="Number of API requests served during the window.", ge=0)
    per_route: Dict[str, int] | None = Field(None, description="Request counts grouped by API route.")
    per_artifact_type: Dict[str, int] | None = Field(None, description="Request counts grouped by artifact type (model/dataset/code).")
    unique_clients: int | None = Field(None, description="Distinct API clients observed in the window.", ge=0)


class HealthComponentBrief(BaseModel):
    """Lightweight component-level status summary."""
    id: str = Field(..., description="Stable identifier for the component (e.g., ingest-worker, metrics).")
    status: HealthStatus = Field(..., description="Component health status.")
    display_name: str | None = Field(None, description="Human readable component name.")
    issue_count: int | None = Field(None, description="Number of outstanding issues contributing to the status.", ge=0)
    last_event_at: str | None = Field(None, description="Last significant event timestamp for the component.", format="date-time")


class HealthComponentDetail(BaseModel):
    """Detailed status, metrics, and log references for a component."""
    id: str = Field(..., description="Stable identifier for the component.")
    status: HealthStatus = Field(..., description="Component health status.")
    observed_at: str = Field(..., description="Timestamp when data for this component was last collected (UTC).", format="date-time")
    display_name: str | None = Field(None, description="Human readable component name.")
    description: str | None = Field(None, description="Overview of the component's responsibility.")
    metrics: HealthMetricMap | None = Field(None, description="Component performance metrics.")
    issues: List[HealthIssue] | None = Field(None, description="Outstanding issues impacting the component.")
    timeline: List[HealthTimelineEntry] | None = Field(None, description="Time-series data for component metrics.")
    logs: List[HealthLogReference] | None = Field(None, description="Log references for the component.")


class HealthComponentCollection(BaseModel):
    """Detailed health diagnostics broken down per component."""
    components: List[HealthComponentDetail] = Field(..., description="Array of component health details.")
    generated_at: str = Field(..., description="Timestamp when the component report was created (UTC).", format="date-time")
    window_minutes: int | None = Field(None, description="Observation window applied to the component metrics.", ge=5)


class HealthSummaryResponse(BaseModel):
    """High-level snapshot summarizing registry health and recent activity."""
    status: HealthStatus = Field(..., description="Overall health status.")
    checked_at: str = Field(..., description="Timestamp when the health snapshot was generated (UTC).", format="date-time")
    window_minutes: int = Field(..., description="Size of the trailing observation window in minutes.", ge=5)
    uptime_seconds: int | None = Field(None, description="Seconds the registry API has been running.", ge=0)
    version: str | None = Field(None, description="Running service version or git SHA when available.")
    request_summary: HealthRequestSummary | None = Field(None, description="Request activity summary.")
    components: List[HealthComponentBrief] | None = Field(None, description="Rollup of component status ordered by severity.")
    logs: List[HealthLogReference] | None = Field(None, description="Quick links or descriptors for recent log files.")


class TrackName(str, Enum):
    """Track names that a student can implement."""
    performance_track = "Performance track"
    access_control_track = "Access control track"
    high_assurance_track = "High assurance track"
    other_security_track = "Other Security track"


class TracksResponse(BaseModel):
    """Response for the tracks endpoint."""
    plannedTracks: List[str] = Field(..., description="List of tracks the student plans to implement")


class ArtifactType(str, Enum):
    """Artifact category."""
    model = "model"
    dataset = "dataset"
    code = "code"


class ArtifactData(BaseModel):
    """
    Source location for ingesting an artifact.
    
    Provide a single downloadable url pointing to a bundle that contains the artifact assets.
    """
    url: str = Field(..., description="Artifact source url used during ingest.", format="uri")
    download_url: str | None = Field(None, description="Direct download link served by your server for retrieving the stored artifact bundle. Present only in responses.", format="uri", read_only=True)


# ArtifactID is a string with pattern validation - validated at field level
# Pattern: ^[a-zA-Z0-9\-]+$


class ArtifactName(str):
    """
    Name of an artifact.
    
    - Names should only use typical "keyboard" characters.
    - The name "*" is reserved. See the `/artifacts` API for its meaning.
    """


class ArtifactMetadata(BaseModel):
    """
    The `name` is provided when uploading an artifact.
    
    The `id` is used as an internal identifier for interacting with existing artifacts 
    and distinguishes artifacts that share a name.
    """
    name: str = Field(..., description="Name of the artifact")
    id: str = Field(..., description="Unique identifier for the artifact (pattern: ^[a-zA-Z0-9\-]+$)", pattern=r'^[a-zA-Z0-9\-]+$')
    type: ArtifactType = Field(..., description="Artifact category")


class Artifact(BaseModel):
    """Artifact envelope containing metadata and ingest details."""
    metadata: ArtifactMetadata
    data: ArtifactData


class ArtifactQuery(BaseModel):
    """Query for searching artifacts."""
    name: str = Field(..., description="Name of the artifact to search for")
    types: List[ArtifactType] | None = Field(None, description="Optional list of artifact types to filter results")


class ArtifactAuditAction(str, Enum):
    """Action types in audit history."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DOWNLOAD = "DOWNLOAD"
    RATE = "RATE"
    AUDIT = "AUDIT"


class User(BaseModel):
    """User model matching the OpenAPI spec."""
    name: str = Field(..., description="User name")
    is_admin: bool = Field(..., description="Is this user an admin?")


class UserAuthenticationInfo(BaseModel):
    """Authentication info for a user matching the OpenAPI spec."""
    password: str = Field(..., description="Password for a user. Per the spec, this should be a \"strong\" password.")


class AuthenticationToken(str):
    """The spec permits you to use any token format you like. You could, for example, look into JSON Web Tokens (\"JWT\", pronounced \"jots\"): https://jwt.io."""
    pass


class AuthenticationRequest(BaseModel):
    """Request for authentication."""
    user: User = Field(..., description="User information")
    secret: UserAuthenticationInfo = Field(..., description="User authentication info")


class EnumerateOffset(str):
    """Offset in pagination."""
    pass


class ArtifactAuditEntry(BaseModel):
    """One entry in an artifact's audit history."""
    user: User = Field(..., description="User who performed the action")
    date: str = Field(..., description="Date of activity using ISO-8601 Datetime standard in UTC format", format="date-time")
    artifact: ArtifactMetadata = Field(..., description="Artifact metadata")
    action: ArtifactAuditAction = Field(..., description="Action performed")


class ArtifactCostItem(BaseModel):
    """Cost information for a single artifact."""
    standalone_cost: float | None = Field(None, description="The standalone cost of this artifact excluding dependencies. Required when `dependency = true` in the request.")
    total_cost: float = Field(..., description="The total cost of the artifact")


class ArtifactCost(BaseModel):
    """
    Artifact Cost aggregates the total download size (in MB) required for the artifact, 
    optionally including dependencies.
    
    This is a dictionary-like structure where keys are artifact identifiers
    and values are ArtifactCostItem objects.
    """
    # In Pydantic v2, we can use model_config with extra="allow" for additionalProperties
    model_config = {"extra": "allow"}
    
    def model_dump(self) -> Dict[str, Dict[str, float]]:
        """Return as dictionary with artifact IDs as keys."""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_') and isinstance(value, ArtifactCostItem):
                result[key] = value.model_dump()
        return result


class ArtifactRegEx(BaseModel):
    """Regular expression search for artifacts."""
    regex: str = Field(..., description="A regular expression over artifact names and READMEs that is used for searching for an artifact")


class ArtifactLineageNode(BaseModel):
    """A single node in an artifact lineage graph."""
    artifact_id: str = Field(..., description="Unique identifier for the node (artifact or external dependency)", pattern=r'^[a-zA-Z0-9\-]+$')
    name: str = Field(..., description="Human-readable label for the node")
    source: str | None = Field(None, description="Provenance for how the node was discovered")
    metadata: Dict[str, Any] | None = Field(None, description="Optional metadata captured for lineage analysis")


class ArtifactLineageEdge(BaseModel):
    """Directed relationship between two lineage nodes."""
    from_node_artifact_id: str = Field(..., description="Identifier of the upstream node", pattern=r'^[a-zA-Z0-9\-]+$')
    to_node_artifact_id: str = Field(..., description="Identifier of the downstream node", pattern=r'^[a-zA-Z0-9\-]+$')
    relationship: str = Field(..., description="Qualitative description of the edge")


class ArtifactLineageGraph(BaseModel):
    """Complete lineage graph for an artifact."""
    nodes: List[ArtifactLineageNode] = Field(..., description="Nodes participating in the lineage graph")
    edges: List[ArtifactLineageEdge] = Field(..., description="Directed edges describing lineage relationships")


class SimpleLicenseCheckRequest(BaseModel):
    """Request payload for artifact license compatibility analysis."""
    github_url: str = Field(..., description="GitHub repository url to evaluate.", format="uri", example="https://github.com/google-research/bert")


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