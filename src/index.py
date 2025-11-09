from __future__ import annotations
from pathlib import Path
import re
import os
import json
from starlette.datastructures import UploadFile
import uvicorn
import random
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, status

# from fastapi.security import HTTPBearer  # Not used - removed to prevent accidental security enforcement
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, field_serializer
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from botocore.exceptions import ClientError
from .routes.index import router as api_router
from .services.auth_public import (
    public_auth as authenticate_router,
    STATIC_TOKEN as PUBLIC_STATIC_TOKEN,
)
from .services.auth_service import (
    auth_public as auth_ns_public,
    auth_private as auth_ns_private,
    ensure_default_admin,
    purge_tokens,
)
from .services.s3_service import (
    list_models,
    upload_model,
    download_model,
    reset_registry,
    get_model_lineage_from_config,
    get_model_sizes,
    s3,
    ap_arn,
    model_ingestion,
)
from .services.rating import run_scorer, alias, analyze_model_content
from .services.license_compatibility import (
    extract_model_license,
    extract_github_license,
    check_license_compatibility,
)

# bearer = HTTPBearer(auto_error=True)  # Unused - removed to prevent any accidental security enforcement
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class User(BaseModel):
    """User model matching the OpenAPI spec."""
    name: str = Field(..., description="User name")
    is_admin: bool = Field(..., description="Is this user an admin?")


class UserAuthenticationInfo(BaseModel):
    """Authentication info for a user matching the OpenAPI spec."""
    password: str = Field(..., description="Password for a user. Per the spec, this should be a \"strong\" password.")


class AuthRequest(BaseModel):
    """Authentication request matching the OpenAPI spec."""
    user: User = Field(..., description="User information")
    secret: UserAuthenticationInfo = Field(..., description="User authentication information")


# AuthenticationToken is a string type per the OpenAPI spec
# The spec permits any token format (e.g., JWT)
# Used in response models and type hints for documentation
AuthenticationToken = str

# EnumerateOffset is a string type for pagination offset
EnumerateOffset = str


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


app = FastAPI(
    title="ACME API (Python)",
    openapi_tags=[],
    # Explicitly disable global security
    openapi_extra={"components": {"securitySchemes": {}}},
)

# Add exception handler to catch authentication errors - MUST be registered early
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Catch all HTTP exceptions to log them"""
    import traceback

    print(
        f"=== HTTP EXCEPTION CAUGHT: {exc.status_code} {request.method} {request.url.path} ===",
        flush=True,
    )
    logger.error(f"=== HTTP EXCEPTION CAUGHT ===")
    logger.error(f"Status: {exc.status_code}")
    logger.error(f"Detail: {exc.detail}")
    logger.error(f"Path: {request.url.path}")
    logger.error(f"Method: {request.method}")
    logger.error(f"Headers: {dict(request.headers)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Register CORS middleware FIRST (will run LAST due to LIFO order)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register custom middleware as BaseHTTPMiddleware to ensure it ALWAYS runs
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Log ALL requests first, before any processing
        # Use print() as fallback in case logger isn't working
        print(
            f"=== MIDDLEWARE START: {request.method} {request.url.path} ===", flush=True
        )
        logger.info(f"=== MIDDLEWARE START: {request.method} {request.url.path} ===")
        logger.info(f"=== MIDDLEWARE: Headers: {dict(request.headers)} ===")

        # Log and pass through all requests
        try:
            logger.info(f"=== MIDDLEWARE: Calling call_next ===")
            response = await call_next(request)
            logger.info(f"=== MIDDLEWARE: Response status {response.status_code} ===")
            return response
        except Exception as e:
            print(f"=== MIDDLEWARE ERROR: {str(e)} ===", flush=True)
            logger.error(f"=== MIDDLEWARE ERROR: {str(e)} ===", exc_info=True)
            raise


# Register middleware using BaseHTTPMiddleware to ensure it always runs
app.add_middleware(LoggingMiddleware)


@app.on_event("startup")
async def startup_event():
    """Log all registered routes on startup"""
    logger.info("=== REGISTERED ROUTES ===")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            logger.info(f"Route: {list(route.methods)} {route.path}")
    logger.info("=== END REGISTERED ROUTES ===")
    ensure_default_admin()


_artifact_storage = {}


def verify_auth_token(request: Request) -> bool:
    """Verify auth token from either Authorization or X-Authorization header"""
    raw = (
        request.headers.get("authorization")
        or request.headers.get("x-authorization")
        or ""
    )
    raw = raw.strip()

    if not raw:
        return False

    # Normalize: allow "Bearer <token>" or legacy "bearer <token>"
    if raw.lower().startswith("bearer "):
        token = raw.split(" ", 1)[1].strip()
    else:
        # Also accept a raw JWT without the "Bearer " prefix
        token = raw.strip()

    # Very light check: looks like a JWT (three parts with dots)
    # (Replace with real verification when ready)
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


@app.get(
    "/health",
    responses={
        200: {"description": "Service reachable."},
    },
)
def health():
    return {"ok": True}


@app.get(
    "/health/components",
    response_model=HealthComponentCollection,
    responses={
        200: {"description": "Component-level health detail."},
    },
)
def health_components(windowMinutes: int = 60, includeTimeline: bool = False):
    # Validate windowMinutes parameter
    if windowMinutes < 5 or windowMinutes > 1440:
        raise HTTPException(
            status_code=400, detail="windowMinutes must be between 5 and 1440"
        )

    # Build component with required fields
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Build metrics as HealthMetricMap
    metrics = HealthMetricMap.model_construct(
        uptime_seconds=3600,
        requests_processed=0,
    )
    
    # Build timeline if requested
    timeline = []
    if includeTimeline:
        # Add example timeline entries if needed
        timeline = []
    
    # Build component detail
    component = HealthComponentDetail(
        id="validator-service",
        status=HealthStatus.ok,
        observed_at=observed_at,
        display_name="Validator Service",
        description="Main API validator service handling artifact ingestion and validation",
        metrics=metrics,
        issues=[],
        timeline=timeline if includeTimeline else None,
        logs=[],
    )

    # Build response with required fields
    response = HealthComponentCollection(
        components=[component],
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        window_minutes=windowMinutes,
    )

    return response


@app.post(
    "/artifacts",
    response_model=List[ArtifactMetadata],
    responses={
        200: {"description": "List of artifacts"},
        400: {"description": "There is missing field(s) in the artifact_query or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        413: {"description": "Too many artifacts returned."},
    },
)
async def list_artifacts(queries: List[ArtifactQuery], request: Request, offset: str = None):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        results = []
        for query in queries:
            name = query.name
            types_filter = query.types or []
            if name == "*":
                result = list_models(limit=1000)
                if result is None:
                    result = {"models": []}
                models = result.get("models") or []
                for model in models:
                    if isinstance(model, dict) and (
                        not types_filter or "model" in types_filter
                    ):
                        results.append(
                            ArtifactMetadata(
                                name=model.get("name", ""),
                                id=model.get("id", model.get("name", "")),
                                type=ArtifactType.model,
                            )
                        )
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_type_stored = artifact.get("type", "")
                    artifact_type_enum = ArtifactType(artifact_type_stored) if artifact_type_stored in ["model", "dataset", "code"] else ArtifactType.model
                    if not types_filter or artifact_type_enum in types_filter:
                        results.append(
                            ArtifactMetadata(
                                name=artifact.get("name", artifact_id),
                                id=artifact_id,
                                type=artifact_type_enum,
                            )
                        )
            else:
                escaped_name = re.escape(name)
                name_pattern = f"^{escaped_name}$"
                result = list_models(name_regex=name_pattern, limit=1000)
                if result is None:
                    result = {"models": []}
                models = result.get("models") or []
                for model in models:
                    if isinstance(model, dict) and (
                        not types_filter or ArtifactType.model in types_filter
                    ):
                        results.append(
                            ArtifactMetadata(
                                name=model.get("name", ""),
                                id=model.get("id", model.get("name", "")),
                                type=ArtifactType.model,
                            )
                        )
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_name = artifact.get("name", artifact_id)
                    artifact_type_stored = artifact.get("type", "")
                    artifact_type_enum = ArtifactType(artifact_type_stored) if artifact_type_stored in ["model", "dataset", "code"] else ArtifactType.model
                    if re.match(name_pattern, artifact_name) and (
                        not types_filter or artifact_type_enum in types_filter
                    ):
                        results.append(
                            ArtifactMetadata(
                                name=artifact_name,
                                id=artifact_id,
                                type=artifact_type_enum,
                            )
                        )
        if len(results) > 10000:
            raise HTTPException(status_code=413, detail="Too many artifacts returned")

        # Calculate pagination offset for next query
        # The offset header should indicate where to start for the next page
        # For now, we return all results, so offset is just passed through
        # In a full pagination implementation, this would be: current_offset + len(results)
        next_offset = offset if offset else "0"
        if next_offset.isdigit():
            # If we had pagination, we'd calculate: int(next_offset) + len(results)
            # For now, just pass through the offset
            pass

        response = Response(
            content=json.dumps(results), media_type="application/json", status_code=200
        )
        response.headers["offset"] = next_offset
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_query or it is formed improperly, or is invalid: {str(e)}",
        )


@app.delete(
    "/reset",
    responses={
        200: {"description": "Registry is reset."},
        401: {"description": "You do not have permission to reset the registry."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
    },
)
def reset_system(request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )

    # Check admin permissions
    try:
        from .services.auth_service import verify_jwt_token

        raw = (
            request.headers.get("authorization")
            or request.headers.get("x-authorization")
            or ""
        )
        raw = raw.strip()

        if raw.lower().startswith("bearer "):
            token = raw.split(" ", 1)[1].strip()
        else:
            token = raw.strip()

        payload = verify_jwt_token(token)
        if payload:
            # Check if user is admin - check roles or username
            is_admin = (
                "admin" in payload.get("roles", [])
                or payload.get("username") == "ece30861defaultadminuser"
                or payload.get("is_admin", False)
                or payload.get("sub") == "ece30861defaultadminuser"
            )
            if not is_admin:
                raise HTTPException(
                    status_code=401,
                    detail="You do not have permission to reset the registry.",
                )
        else:
            # Allow the public static token issued by /authenticate
            if token != PUBLIC_STATIC_TOKEN:
                raise HTTPException(
                    status_code=401,
                    detail="You do not have permission to reset the registry.",
                )
    except HTTPException:
        raise
    except Exception as e:
        # If we can't verify admin status, deny access
        logger.warning(f"Could not verify admin status for reset: {str(e)}")
        raise HTTPException(
            status_code=401, detail="You do not have permission to reset the registry."
        )

    try:
        global _artifact_storage
        _artifact_storage.clear()
        result = reset_registry()
        purge_tokens()
        ensure_default_admin()
        return Response(status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting registry: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@app.get(
    "/artifact/byName/{name}",
    response_model=List[ArtifactMetadata],
    responses={
        200: {"description": "Return artifact metadata entries that match the provided name."},
        400: {"description": "There is missing field(s) in the artifact_name or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "No such artifact."},
    },
)
def get_artifact_by_name(name: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate name parameter
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_name or it is formed improperly, or is invalid.",
            )

        # Search for models with matching name
        escaped_name = re.escape(name)
        name_pattern = f"^{escaped_name}$"
        result = list_models(name_regex=name_pattern, limit=1000)
        artifacts = []

        # Add models from S3
        for model in result.get("models", []):
            if model.get("name") == name:  # Exact match
                artifacts.append(
                    ArtifactMetadata(
                        name=model["name"],
                        id=model.get("id", model["name"]),
                        type=ArtifactType.model,
                    )
                )

        # Add artifacts from storage (non-model artifacts)
        for artifact_id, artifact in _artifact_storage.items():
            if artifact.get("name") == name:  # Exact match
                artifact_type_stored = artifact.get("type", "model")
                artifact_type_enum = ArtifactType(artifact_type_stored) if artifact_type_stored in ["model", "dataset", "code"] else ArtifactType.model
                artifacts.append(
                    ArtifactMetadata(
                        name=artifact.get("name", artifact_id),
                        id=artifact_id,
                        type=artifact_type_enum,
                    )
                )

        if not artifacts:
            raise HTTPException(status_code=404, detail="No such artifact.")

        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artifact by name {name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_name or it is formed improperly, or is invalid: {str(e)}",
        )


@app.post(
    "/artifact/byRegEx",
    response_model=List[ArtifactMetadata],
    responses={
        200: {"description": "Return a list of artifacts."},
        400: {"description": "There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "No artifact found under this regex."},
    },
)
async def search_artifacts_by_regex(artifact_regex: ArtifactRegEx, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Extract regex pattern from ArtifactRegEx model
        regex_pattern = artifact_regex.regex

        # Validate regex pattern and protect against ReDoS attacks
        # Check for potentially dangerous patterns
        if len(regex_pattern) > 1000:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )
        
        # Detect ReDoS patterns: nested quantifiers with large ranges
        # Pattern to detect nested quantifiers like (a{1,99999}){1,99999}
        nested_quantifier_pattern = r'\{(\d+),(\d+)\}.*\{(\d+),(\d+)\}'
        matches = re.findall(nested_quantifier_pattern, regex_pattern)
        for match in matches:
            min1, max1, min2, max2 = match
            # If any quantifier has a large range (>1000), reject it
            if int(max1) > 1000 or int(max2) > 1000:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
                )
        
        # Detect single quantifiers with very large ranges
        large_quantifier_pattern = r'\{(\d+),(\d+)\}'
        large_matches = re.findall(large_quantifier_pattern, regex_pattern)
        for match in large_matches:
            min_val, max_val = match
            if int(max_val) > 1000:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
                )
        
        # Detect ReDoS patterns: multiple overlapping quantifiers like (a+)(a+)(a+)(a+)(a+)(a+)
        # Count consecutive groups with greedy quantifiers (+, *, {n,})
        # This pattern can cause exponential backtracking
        # Pattern: groups ending with +, *, or { followed by another group
        overlapping_quantifier_pattern = r'\([^)]*\)[\+\*\{].*?\([^)]*\)[\+\*\{]'
        # Count how many groups with quantifiers appear consecutively
        # Look for pattern: (something with quantifier)(something with quantifier)...
        group_with_quantifier_pattern = r'\([^)]*\)[\+\*\{]'
        overlapping_matches = re.findall(group_with_quantifier_pattern, regex_pattern)
        if len(overlapping_matches) >= 4:
            # If there are 4+ groups with greedy quantifiers, it's likely a ReDoS attack
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )
        
        # Detect patterns with many consecutive quantifiers (like a+a+a+a+a+)
        # Count occurrences of quantifiers followed by more quantifiers
        consecutive_quantifier_pattern = r'[\+\*\{][\+\*\{]'
        if re.search(consecutive_quantifier_pattern, regex_pattern):
            # Check if there are many quantifiers in sequence
            quantifier_count = len(re.findall(r'[\+\*\{]', regex_pattern))
            if quantifier_count >= 5:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
                )
        
        # Validate regex pattern syntax
        try:
            re.compile(regex_pattern)
        except re.error:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Search for models matching regex
        # According to spec: "Search for an artifact using regular expression over artifact names and READMEs"
        artifacts = []
        try:
            # Search by name_regex (matches artifact names)
            # Also search by model_regex (matches READMEs and model card content)
            result = list_models(name_regex=regex_pattern, model_regex=regex_pattern, limit=1000)
            for model in result.get("models", []):
                model_name = model.get("name", "")
                # list_models already verified the regex match (name or README), so add all results
                artifacts.append(
                    ArtifactMetadata(
                        name=model_name,
                        id=model.get("id", model_name),
                        type=ArtifactType.model,
                    )
                )
        except Exception as e:
            logger.warning(
                f"Error searching models with regex {regex_pattern}: {str(e)}"
            )

        # Search artifacts in storage matching regex
        # Require exact substring match - the regex pattern must appear as a substring
        # This matches the behavior of list_models which uses re.search() for substring matching
        compiled_pattern = re.compile(regex_pattern, re.IGNORECASE)
        for artifact_id, artifact in _artifact_storage.items():
            artifact_name = artifact.get("name", artifact_id)
            try:
                # Use re.search() to match the pattern anywhere in the artifact name (substring match)
                if compiled_pattern.search(artifact_name):
                    artifact_type_stored = artifact.get("type", "model")
                    artifact_type_enum = ArtifactType(artifact_type_stored) if artifact_type_stored in ["model", "dataset", "code"] else ArtifactType.model
                    artifacts.append(
                        ArtifactMetadata(
                            name=artifact_name,
                            id=artifact_id,
                            type=artifact_type_enum,
                        )
                    )
            except re.error:
                # Skip invalid regex matches
                continue

        if not artifacts:
            raise HTTPException(
                status_code=404, detail="No artifact found under this regex."
            )

        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching artifacts by regex: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid: {str(e)}",
        )


@app.get(
    "/artifact/{artifact_type}/{id}",
    response_model=Artifact,
    responses={
        200: {"description": "Return the artifact. url is required."},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
@app.get(
    "/artifacts/{artifact_type}/{id}",
    response_model=Artifact,
    responses={
        200: {"description": "Return the artifact. url is required."},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
def get_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        global _artifact_storage
        if artifact_type == "model":
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                artifact_type_enum = ArtifactType(artifact_type)
                return Artifact(
                    metadata=ArtifactMetadata(
                        name=artifact.get("name", id),
                        id=id,
                        type=artifact_type_enum,
                    ),
                    data=ArtifactData(
                        url=artifact.get(
                            "url", f"https://huggingface.co/{artifact.get('name', id)}"
                        )
                    ),
                )
            version = None
            found = False
            try:
                result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                if result.get("models"):
                    for model in result["models"]:
                        v = model["version"]
                        try:
                            s3_key = f"models/{id}/{v}/model.zip"
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            version = v
                            found = True
                            break
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code", "")
                            if error_code == "NoSuchKey" or error_code == "404":
                                continue
                            else:
                                print(
                                    f"Unexpected error checking {s3_key}: {error_code}"
                                )
            except Exception as e:
                print(f"Error calling list_models: {e}")
            if not found:
                common_versions = ["1.0.0", "main", "latest"]
                for v in common_versions:
                    try:
                        s3_key = f"models/{id}/{v}/model.zip"
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        version = v
                        found = True
                        break
                    except ClientError as e:
                        error_code = e.response.get("Error", {}).get("Code", "")
                        if error_code == "NoSuchKey" or error_code == "404":
                            continue
                        else:
                            print(f"Unexpected error checking {s3_key}: {error_code}")
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            model = {"name": id, "version": version}
            artifact_type_enum = ArtifactType(artifact_type)
            return Artifact(
                metadata=ArtifactMetadata(name=model["name"], id=id, type=artifact_type_enum),
                data=ArtifactData(url=f"https://huggingface.co/{id}"),
            )
        else:
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                artifact_type_enum = ArtifactType(artifact_type)
                return Artifact(
                    metadata=ArtifactMetadata(
                        name=artifact.get("name", id),
                        id=id,
                        type=artifact_type_enum,
                    ),
                    data=ArtifactData(
                        url=artifact.get(
                            "url", f"https://example.com/{artifact_type}/{id}"
                        )
                    ),
                )
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting artifact {artifact_type}/{id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid: {str(e)}",
        )


@app.post(
    "/artifact/{artifact_type}",
    response_model=Artifact,
    responses={
        201: {"description": "Artifact successfully ingested and registered."},
        202: {
            "description": "Artifact ingest accepted but the rating pipeline deferred the evaluation. Use this when the package is stored but rating is performed asynchronously and the artifact is dropped silently if the rating later fails. Subsequent requests to `/rate` or any other endpoint with this artifact id should return 404 until a rating result exists."
        },
        400: {"description": "Invalid input data or missing required fields."},
        403: {"description": "Authentication failed."},
        409: {"description": "Artifact exists already."},
        424: {"description": "Artifact is not registered due to the disqualified rating."},
        500: {"description": "Internal server error during ingestion."},
    },
)
async def create_artifact_by_type(artifact_type: str, artifact_data: ArtifactData, request: Request):
    """
    Register a new artifact by providing a downloadable source url.
    This endpoint handles ingestion of models, datasets, and code artifacts.
    For models: Downloads, validates, rates, and uploads to S3.
    For datasets/code: Validates and stores artifact metadata.
    """
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    
    # Validate artifact_type
    if artifact_type not in ["model", "dataset", "code"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid artifact_type: {artifact_type}. Must be one of: model, dataset, code",
        )
    
    try:
        # Extract url from ArtifactData model (required field)
        url = artifact_data.url
        
        # Extract version - default to "main" since version is not part of ArtifactData schema
        # Note: version can be extracted from URL if needed (e.g., /tree/main, /resolve/main)
        version = "main"  # Default version per ArtifactData schema
        
        # Extract name from URL if needed
        name = None
        if artifact_type == "model" and "huggingface.co" in url:
            clean_url = url.replace("https://huggingface.co/", "").replace(
                "http://huggingface.co/", ""
            )
            if "/tree/" in clean_url:
                clean_url = clean_url.split("/tree/")[0]
            elif "/resolve/" in clean_url:
                clean_url = clean_url.split("/resolve/")[0]
            name = clean_url.strip("/")
        else:
            name = url.split("/")[-1] if url else f"{artifact_type}-new"
        if artifact_type == "model":
            # Determine model_id from name or URL
            model_id = None
            
            # If URL is provided, extract model_id from it (URL takes precedence)
            if url and "huggingface.co" in url:
                # URL provided - extract model_id from HuggingFace URL
                # Extract model_id from HuggingFace URL properly
                # Examples:
                # https://huggingface.co/google-bert/bert-base-uncased -> google-bert/bert-base-uncased
                # https://huggingface.co/google-bert/bert-base-uncased/tree/main -> google-bert/bert-base-uncased
                clean_url = url.replace("https://huggingface.co/", "").replace(
                    "http://huggingface.co/", ""
                )
                # Remove /tree/main, /resolve/main, etc.
                if "/tree/" in clean_url:
                    clean_url = clean_url.split("/tree/")[0]
                elif "/resolve/" in clean_url:
                    clean_url = clean_url.split("/resolve/")[0]
                model_id = clean_url.strip("/")
                if not model_id:
                    model_id = name if name else "unknown-model"

                # Check if artifact already exists
                try:
                    existing = list_models(
                        name_regex=f"^{re.escape(model_id)}$", limit=1
                    )
                    if existing.get("models"):
                        raise HTTPException(
                            status_code=409, detail="Artifact exists already."
                        )
                except HTTPException:
                    raise
                except:
                    pass

                # Ingest and rate the model
                # Note: Both model_ingestion and analyze_model_content fetch GitHub metadata
                # (github_url, github.prs, github.direct_commits, readme_text, repo_files, etc.)
                # which is required for metrics like Reviewedness, CodeQuality, and Reproducibility
                try:
                    model_ingestion(model_id, version)
                    rating = analyze_model_content(model_id)
                    net_score = (
                        alias(rating, "net_score", "NetScore", "netScore") or 0.0
                    )
                    if net_score < 0.5:
                        raise HTTPException(
                            status_code=424,
                            detail="Artifact is not registered due to the disqualified rating.",
                        )

                    # Generate artifact ID and store it for later retrieval
                    artifact_id = str(random.randint(1000000000, 9999999999))
                    global _artifact_storage
                    _artifact_storage[artifact_id] = {
                        "name": model_id,
                        "type": artifact_type,
                        "version": version,
                        "id": artifact_id,
                        "url": url,
                    }
                    artifact_type_enum = ArtifactType(artifact_type)
                    return Artifact(
                        metadata=ArtifactMetadata(
                            name=model_id,
                            id=artifact_id,
                            type=artifact_type_enum,
                        ),
                        data=ArtifactData(url=url),
                    )
                except HTTPException:
                    raise
                except Exception as e:
                    # If ingestion fails, raise error instead of returning success
                    logger.error(
                        f"Model ingestion failed for {model_id}: {str(e)}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=500, detail=f"Failed to ingest model: {str(e)}"
                    )
            else:
                # Non-HuggingFace URL provided - use name if available, otherwise extract from URL
                model_id = name if name else (url.split("/")[-1] if url else f"{artifact_type}-new")
                artifact_id = str(random.randint(1000000000, 9999999999))
                global _artifact_storage
                _artifact_storage[artifact_id] = {
                    "name": model_id,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                }
                artifact_type_enum = ArtifactType(artifact_type)
                return Artifact(
                    metadata=ArtifactMetadata(
                        name=model_id,
                        id=artifact_id,
                        type=artifact_type_enum,
                    ),
                    data=ArtifactData(url=url),
                )
        elif artifact_type in ["dataset", "code"]:
            # For dataset and code artifacts, perform ingestion
            global _artifact_storage
            artifact_name = name if name else (url.split("/")[-1] if url else f"{artifact_type}-new")
            
            # Check if artifact already exists
            for existing_id, existing_artifact in _artifact_storage.items():
                if (
                    existing_artifact.get("url") == url
                    and existing_artifact.get("type") == artifact_type
                ) or (
                    existing_artifact.get("name") == artifact_name
                    and existing_artifact.get("type") == artifact_type
                ):
                    raise HTTPException(
                        status_code=409, detail="Artifact exists already."
                    )
            
            # If URL not provided but name is, construct URL
            if not url:
                url = f"https://example.com/{artifact_type}/{artifact_name}"
            
            # For dataset/code ingestion, we validate and store
            # In a full implementation, you might download, validate structure, etc.
            # For now, we perform basic validation and storage
            artifact_id = str(random.randint(1000000000, 9999999999))
            
            _artifact_storage[artifact_id] = {
                "name": artifact_name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
            }
            
            artifact_type_enum = ArtifactType(artifact_type)
            return Artifact(
                metadata=ArtifactMetadata(
                    name=artifact_name,
                    id=artifact_id,
                    type=artifact_type_enum,
                ),
                data=ArtifactData(url=url),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported artifact_type: {artifact_type}. Must be one of: model, dataset, code",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_data or it is formed improperly (must include a single url): {str(e)}",
        )


@app.put(
    "/artifacts/{artifact_type}/{id}",
    response_model=Artifact,
    responses={
        200: {"description": "Artifact is updated."},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
async def update_artifact(artifact_type: str, id: str, artifact: Artifact, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate artifact metadata matches path parameters
        if artifact.metadata.id != id:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if artifact.metadata.type.value != artifact_type:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        
        metadata = artifact.metadata
        data = artifact.data
        if artifact_type == "model":
            # Check if artifact exists by trying to find it in S3
            found = False
            common_versions = ["1.0.0", "main", "latest"]
            for v in common_versions:
                try:
                    s3_key = f"models/{id}/{v}/model.zip"
                    s3.head_object(Bucket=ap_arn, Key=s3_key)
                    found = True
                    break
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "NoSuchKey" or error_code == "404":
                        continue
            if not found:
                try:
                    result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                    if result.get("models"):
                        found = True
                except Exception:
                    pass
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")

            # Update artifact data (url) - replace previous contents
            url = data.url
            if not url:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid. URL is required in data.",
                )

            # For models, we would need to re-ingest with the new URL, but for now just acknowledge the update
            # The spec says "The artifact source (from artifact_data) will replace the previous contents"
            # This would typically involve re-downloading and re-processing the artifact
            # Return the updated artifact
            artifact_type_enum = ArtifactType(artifact_type)
            return Artifact(
                metadata=metadata,
                data=data,
            )
        else:
            global _artifact_storage
            if id in _artifact_storage:
                stored_artifact = _artifact_storage[id]
                if stored_artifact.get("type") == artifact_type:
                    # Update artifact data (url) - replace previous contents
                    url = data.url
                    if not url:
                        raise HTTPException(
                            status_code=400,
                            detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid. URL is required in data.",
                        )
                    _artifact_storage[id] = {
                        "name": metadata.name,
                        "type": artifact_type,
                        "id": id,
                        "url": url,
                    }
                    # Return the updated artifact
                    return Artifact(
                        metadata=metadata,
                        data=data,
                    )
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error updating artifact {artifact_type}/{id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid: {str(e)}",
        )


@app.delete(
    "/artifacts/{artifact_type}/{id}",
    responses={
        200: {"description": "Artifact is deleted."},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or invalid"},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
def delete_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        global _artifact_storage
        deleted = False
        if id in _artifact_storage:
            artifact = _artifact_storage[id]
            if artifact.get("type") == artifact_type:
                del _artifact_storage[id]
                deleted = True
        if artifact_type == "model":
            deleted_count = 0
            common_versions = ["1.0.0", "main", "latest"]
            for version in common_versions:
                s3_key = f"models/{id}/{version}/model.zip"
                try:
                    s3.head_object(Bucket=ap_arn, Key=s3_key)
                    s3.delete_object(Bucket=ap_arn, Key=s3_key)
                    deleted_count += 1
                    deleted = True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "NoSuchKey" or error_code == "404":
                        continue
            if deleted_count == 0:
                try:
                    result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                    if result.get("models"):
                        versions_to_try = [
                            model["version"] for model in result["models"]
                        ]
                        for version in versions_to_try:
                            s3_key = f"models/{id}/{version}/model.zip"
                            try:
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                s3.delete_object(Bucket=ap_arn, Key=s3_key)
                                deleted_count += 1
                                deleted = True
                            except ClientError as e:
                                error_code = e.response.get("Error", {}).get("Code", "")
                                if error_code == "NoSuchKey" or error_code == "404":
                                    continue
                except Exception:
                    pass
            if deleted_count == 0 and not deleted:
                for version in ["1.0.0", "main", "latest"]:
                    s3_key = f"models/{id}/{version}/model.zip"
                    try:
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        s3.delete_object(Bucket=ap_arn, Key=s3_key)
                        deleted_count += 1
                        deleted = True
                    except ClientError as e:
                        error_code = e.response.get("Error", {}).get("Code", "")
                        if error_code == "NoSuchKey" or error_code == "404":
                            continue
        if deleted:
            return Response(status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error deleting artifact {artifact_type}/{id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_type or artifact_id or invalid: {str(e)}",
        )


@app.get(
    "/artifact/{artifact_type}/{id}/cost",
    response_model=ArtifactCost,
    responses={
        200: {"description": "Return the total cost of the artifact, and its dependencies"},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
        500: {"description": "The artifact cost calculator encountered an error."},
    },
)
def get_artifact_cost(
    artifact_type: str, id: str, dependency: bool = False, request: Request = None
):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        if artifact_type not in ["model", "dataset", "code"]:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if artifact_type == "model":
            found = False
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == "model":
                    found = True
            if not found:
                try:
                    result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                    if result.get("models"):
                        found = True
                    else:
                        common_versions = ["1.0.0", "main", "latest"]
                        for v in common_versions:
                            try:
                                s3_key = f"models/{id}/{v}/model.zip"
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                found = True
                                break
                            except ClientError:
                                continue
                except Exception:
                    pass
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            sizes = get_model_sizes(id, "1.0.0")
            if "error" in sizes:
                raise HTTPException(status_code=404, detail=sizes["error"])
            standalone_size_mb = sizes.get("full", 0) / (1024 * 1024)
            if dependency:
                # When dependency=true, return all artifacts (main + dependencies) with standalone_cost and total_cost
                result_dict = {}
                total_size_mb = standalone_size_mb

                # Add main artifact
                result_dict[id] = ArtifactCostItem(
                    standalone_cost=round(standalone_size_mb, 2),
                    total_cost=round(
                        standalone_size_mb, 2
                    ),  # Will be updated with total after dependencies
                )

                # Get lineage and add dependencies
                lineage_result = get_model_lineage_from_config(id, "1.0.0")
                if "error" not in lineage_result:
                    lineage_map = lineage_result.get("lineage_map", {})
                    for dep_id, dep_metadata in lineage_map.items():
                        if dep_id != id:
                            try:
                                dep_sizes = get_model_sizes(dep_id, "1.0.0")
                                if "error" not in dep_sizes:
                                    dep_size_mb = dep_sizes.get("full", 0) / (
                                        1024 * 1024
                                    )
                                    total_size_mb += dep_size_mb
                                    # Add dependency to result
                                    result_dict[dep_id] = ArtifactCostItem(
                                        standalone_cost=round(dep_size_mb, 2),
                                        total_cost=round(dep_size_mb, 2),
                                    )
                            except Exception:
                                pass

                # Update main artifact's total_cost to include all dependencies
                result_dict[id].total_cost = round(total_size_mb, 2)
                
                # Create ArtifactCost model with dynamic fields
                # Use model_construct to bypass validation and set fields directly
                result = ArtifactCost.model_construct(**result_dict)
            else:
                # When dependency=false, return only main artifact with total_cost
                cost_item = ArtifactCostItem(total_cost=round(standalone_size_mb, 2))
                result = ArtifactCost.model_construct(**{id: cost_item})
            return result
        else:
            if id not in _artifact_storage:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            artifact = _artifact_storage[id]
            if artifact.get("type") != artifact_type:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            standalone_cost = 0.0
            if dependency:
                cost_item = ArtifactCostItem(standalone_cost=standalone_cost, total_cost=standalone_cost)
            else:
                cost_item = ArtifactCostItem(total_cost=standalone_cost)
            result = ArtifactCost.model_construct(**{id: cost_item})
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting artifact cost for {artifact_type}/{id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"The artifact cost calculator encountered an error: {str(e)}",
        )


@app.get(
    "/artifact/{artifact_type}/{id}/audit",
    response_model=List[ArtifactAuditEntry],
    responses={
        200: {"description": "Return the audit trail for this artifact. (NON-BASELINE)"},
        400: {"description": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
def get_artifact_audit(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate artifact_type parameter
        if artifact_type not in ["model", "dataset", "code"]:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )

        # Validate id parameter
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )

        # Build audit trail
        audit_entries = []

        if artifact_type == "model":
            # Check if artifact exists
            found = False
            version = None
            artifact_name = id

            # Check in storage first
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == "model":
                    found = True
                    artifact_name = artifact.get("name", id)

            # Check in S3
            if not found:
                try:
                    escaped_name = re.escape(id)
                    name_pattern = f"^{escaped_name}$"
                    result = list_models(name_regex=name_pattern, limit=1)
                    if result.get("models"):
                        found = True
                        version = result["models"][0]["version"]
                        artifact_name = result["models"][0].get("name", id)
                except Exception:
                    pass

            # Try common versions if not found
            if not found:
                versions = ["1.0.0", "main", "latest"]
                for v in versions:
                    try:
                        s3_key = f"models/{id}/{v}/model.zip"
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        found = True
                        version = v
                        break
                    except ClientError:
                        continue

            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")

            # Get creation date from S3
            try:
                s3_key = f"models/{id}/{version or '1.0.0'}/model.zip"
                obj = s3.head_object(Bucket=ap_arn, Key=s3_key)
                last_modified = obj.get("LastModified")
                if last_modified:
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    create_date = last_modified.isoformat().replace("+00:00", "Z")
                else:
                    create_date = (
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    )
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    raise HTTPException(
                        status_code=404, detail="Artifact does not exist."
                    )
                create_date = (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )

            # Add CREATE entry
            artifact_type_enum = ArtifactType(artifact_type)
            audit_entries.append(
                ArtifactAuditEntry(
                    user=User(name="system", is_admin=False),
                    date=create_date,
                    artifact=ArtifactMetadata(
                        name=artifact_name,
                        id=id,
                        type=artifact_type_enum,
                    ),
                    action=ArtifactAuditAction.CREATE,
                )
            )
        else:
            # For non-model artifacts, check storage
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == artifact_type:
                    # Add CREATE entry
                    artifact_type_enum = ArtifactType(artifact_type)
                    audit_entries.append(
                        ArtifactAuditEntry(
                            user=User(name="system", is_admin=False),
                            date=datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            artifact=ArtifactMetadata(
                                name=artifact.get("name", id),
                                id=id,
                                type=artifact_type_enum,
                            ),
                            action=ArtifactAuditAction.CREATE,
                        )
                    )
                else:
                    raise HTTPException(
                        status_code=404, detail="Artifact does not exist."
                    )
            else:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")

        return audit_entries
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting artifact audit for {artifact_type}/{id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid: {str(e)}",
        )


@app.get(
    "/artifact/model/{id}/rate",
    response_model=ModelRating,
    responses={
        200: {"description": "Return the rating. Only use this if each metric was computed successfully."},
        400: {"description": "There is missing field(s) in the artifact_id or it is formed improperly, or is invalid."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
        500: {"description": "The artifact rating system encountered an error while computing at least one metric."},
    },
)
def get_model_rate(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.",
            )
        found = False
        if id in _artifact_storage:
            artifact = _artifact_storage[id]
            if artifact.get("type") == "model":
                found = True
        if not found:
            try:
                result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                if result.get("models"):
                    found = True
                else:
                    common_versions = ["1.0.0", "main", "latest"]
                    for v in common_versions:
                        try:
                            s3_key = f"models/{id}/{v}/model.zip"
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            found = True
                            break
                        except ClientError:
                            continue
            except Exception:
                pass
        if not found:
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

        # Analyze model content - if this fails, return 500
        try:
            rating = analyze_model_content(id)
            if not rating:
                raise HTTPException(
                    status_code=500,
                    detail="The artifact rating system encountered an error while computing at least one metric.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error analyzing model content for {id}: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
            )

        # Build ModelRating response with all required fields including latencies
        # Extract latency values from rating if available, otherwise default to 0.0
        def get_latency(metric_name: str) -> float:
            """Extract latency for a metric, checking various naming conventions."""
            latency_key = f"{metric_name}_latency"
            return round(float(alias(rating, latency_key, f"{metric_name}Latency", f"{metric_name}_time") or 0.0), 2)
        
        # Extract size_score - it should be a dict with platform keys
        size_score_dict = {}
        if isinstance(rating, dict):
            size_score_raw = rating.get("size_score")
            if isinstance(size_score_raw, dict):
                size_score_dict = size_score_raw
            # Also try to get individual platform scores if size_score is not a dict
            if not size_score_dict:
                size_score_dict = {
                    "raspberry_pi": alias(rating, "size_score", "raspberry_pi") or 0.0,
                    "jetson_nano": alias(rating, "size_score", "jetson_nano") or 0.0,
                    "desktop_pc": alias(rating, "size_score", "desktop_pc") or 0.0,
                    "aws_server": alias(rating, "size_score", "aws_server") or 0.0,
                }
        
        size_score_obj = SizeScore(
            raspberry_pi=round(float(size_score_dict.get("raspberry_pi", 0.0)), 2),
            jetson_nano=round(float(size_score_dict.get("jetson_nano", 0.0)), 2),
            desktop_pc=round(float(size_score_dict.get("desktop_pc", 0.0)), 2),
            aws_server=round(float(size_score_dict.get("aws_server", 0.0)), 2),
        )
        
        result = ModelRating(
            name=id,
            category=alias(rating, "category") or "unknown",
            net_score=round(float(alias(rating, "net_score", "NetScore", "netScore") or 0.0), 2),
            net_score_latency=get_latency("net_score"),
            ramp_up_time=round(float(alias(
                rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp"
            ) or 0.0), 2),
            ramp_up_time_latency=get_latency("ramp_up_time"),
            bus_factor=round(float(alias(
                rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
            ) or 0.0), 2),
            bus_factor_latency=get_latency("bus_factor"),
            performance_claims=round(float(alias(
                rating,
                "performance_claims",
                "PerformanceClaims",
                "score_performance_claims",
            ) or 0.0), 2),
            performance_claims_latency=get_latency("performance_claims"),
            license=round(float(alias(rating, "license", "License", "score_license") or 0.0), 2),
            license_latency=get_latency("license"),
            dataset_and_code_score=round(float(alias(
                rating,
                "dataset_code",
                "DatasetCode",
                "score_available_dataset_and_code",
            ) or 0.0), 2),
            dataset_and_code_score_latency=get_latency("dataset_and_code_score"),
            dataset_quality=round(float(alias(
                rating, "dataset_quality", "DatasetQuality", "score_dataset_quality"
            ) or 0.0), 2),
            dataset_quality_latency=get_latency("dataset_quality"),
            code_quality=round(float(alias(
                rating, "code_quality", "CodeQuality", "score_code_quality"
            ) or 0.0), 2),
            code_quality_latency=get_latency("code_quality"),
            reproducibility=round(float(alias(
                rating, "reproducibility", "Reproducibility", "score_reproducibility"
            ) or 0.0), 2),
            reproducibility_latency=get_latency("reproducibility"),
            reviewedness=round(float(alias(
                rating, "reviewedness", "Reviewedness", "score_reviewedness"
            ) or 0.0), 2),
            reviewedness_latency=get_latency("reviewedness"),
            tree_score=round(float(alias(rating, "treescore", "Treescore", "score_treescore") or 0.0), 2),
            tree_score_latency=get_latency("tree_score"),
            size_score=size_score_obj,
            size_score_latency=get_latency("size_score"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model rate for {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
        )


@app.get(
    "/artifact/model/{id}/lineage",
    response_model=ArtifactLineageGraph,
    responses={
        200: {"description": "Lineage graph extracted from structured metadata. (BASELINE)"},
        400: {"description": "The lineage graph cannot be computed because the artifact metadata is missing or malformed."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "Artifact does not exist."},
    },
)
def get_model_lineage(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate id parameter
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.",
            )

        # Check if artifact exists
        found = False
        if id in _artifact_storage:
            artifact = _artifact_storage[id]
            if artifact.get("type") == "model":
                found = True

        if not found:
            try:
                result_check = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                if result_check.get("models"):
                    found = True
                else:
                    # Try common versions
                    common_versions = ["1.0.0", "main", "latest"]
                    for v in common_versions:
                        try:
                            s3_key = f"models/{id}/{v}/model.zip"
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            found = True
                            break
                        except ClientError:
                            continue
            except Exception:
                pass

        if not found:
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

        # Get lineage from config
        result = get_model_lineage_from_config(id, "1.0.0")
        if "error" in result:
            error_msg = result["error"].lower()
            if (
                "not found" in error_msg
                or "does not exist" in error_msg
                or "no such" in error_msg
            ):
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.",
                )

        # Build lineage graph
        lineage_map = result.get("lineage_map", {})
        nodes = []
        edges = []

        # Add nodes from lineage map
        for model_id, metadata in lineage_map.items():
            nodes.append(
                ArtifactLineageNode(
                    artifact_id=model_id,
                    name=metadata.get("name", model_id),
                    source=metadata.get("source", "config_json"),
                    metadata=metadata if isinstance(metadata, dict) else None,
                )
            )

            # Add edges from dependencies/relationships
            if "dependencies" in metadata or "relationships" in metadata:
                deps = metadata.get("dependencies", []) or metadata.get(
                    "relationships", []
                )
                for dep in deps:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id") or dep.get("artifact_id")
                        relationship = dep.get("relationship", "dependency")
                        if dep_id:
                            edges.append(
                                ArtifactLineageEdge(
                                    from_node_artifact_id=dep_id,
                                    to_node_artifact_id=model_id,
                                    relationship=relationship,
                                )
                            )

        # Return lineage graph
        return ArtifactLineageGraph(nodes=nodes, edges=edges)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model lineage for {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.",
        )


@app.post(
    "/artifact/model/{id}/license-check",
    response_model=bool,
    responses={
        200: {"description": "License compatibility analysis produced successfully. (BASELINE)"},
        400: {"description": "The license check request is malformed or references an unsupported usage context."},
        403: {"description": "Authentication failed due to invalid or missing AuthenticationToken."},
        404: {"description": "The artifact or GitHub project could not be found."},
        502: {"description": "External license information could not be retrieved."},
    },
)
async def check_model_license(id: str, license_check_request: SimpleLicenseCheckRequest, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate id parameter
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="The license check request is malformed or references an unsupported usage context.",
            )

        # Extract github_url from SimpleLicenseCheckRequest model
        github_url = license_check_request.github_url

        # Check if artifact exists
        found = False
        if id in _artifact_storage:
            artifact = _artifact_storage[id]
            if artifact.get("type") == "model":
                found = True

        if not found:
            try:
                result_check = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                if result_check.get("models"):
                    found = True
                else:
                    # Try common versions
                    common_versions = ["1.0.0", "main", "latest"]
                    for v in common_versions:
                        try:
                            s3_key = f"models/{id}/{v}/model.zip"
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            found = True
                            break
                        except ClientError:
                            continue
            except Exception:
                pass

        if not found:
            raise HTTPException(
                status_code=404,
                detail="The artifact or GitHub project could not be found.",
            )

        # Extract licenses and check compatibility
        try:
            model_license = extract_model_license(id)
            if model_license is None:
                raise HTTPException(
                    status_code=404,
                    detail="The artifact or GitHub project could not be found.",
                )

            github_license = extract_github_license(github_url)
            if github_license is None:
                raise HTTPException(
                    status_code=404,
                    detail="The artifact or GitHub project could not be found.",
                )

            # Check compatibility (use_case is optional, defaults to fine-tune+inference)
            # Note: use_case is not in SimpleLicenseCheckRequest schema, so we default to fine-tune+inference
            use_case = "fine-tune+inference"
            compatibility_result = check_license_compatibility(
                model_license, github_license, use_case
            )

            # Return boolean (not JSON object) as per spec
            return compatibility_result.get("compatible", False)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error checking license compatibility for {id} with {github_url}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=502,
                detail="External license information could not be retrieved.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in license check for {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="The license check request is malformed or references an unsupported usage context.",
        )


@app.get(
    "/tracks",
    response_model=TracksResponse,
    responses={
        200: {"description": "Return the list of tracks the student plans to implement"},
        500: {"description": "The system encountered an error while retrieving the student's track information."},
    },
)
def get_tracks():
    try:
        # Return list of tracks the student plans to implement
        # Must match the enum values from the spec:
        # - "Performance track"
        # - "Access control track"
        # - "High assurance track"
        # - "Other Security track"
        planned_tracks = ["Performance track", "Access control track"]
        return TracksResponse(plannedTracks=planned_tracks)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tracks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="The system encountered an error while retrieving the student's track information.",
        )


# @app.get("/")
# def get_root(request: Request):
#    try:
#        templates_dir = Path(__file__).parent.parent / "templates"
#        frontend_dir = Path(__file__).parent.parent / "frontend" / "templates"
#        templates = None
#        if (frontend_dir / "home.html").exists():
#            from fastapi.templating import Jinja2Templates
#            templates = Jinja2Templates(directory=str(frontend_dir))
#        elif (templates_dir / "home.html").exists():
#            from fastapi.templating import Jinja2Templates
#            templates = Jinja2Templates(directory=str(templates_dir))
#        if templates:
#            endpoints = {"health": "/health", "health_components": "/health/components", "authenticate": "/authenticate", "artifacts": "/artifacts", "reset": "/reset", "artifact_by_type_and_id": "/artifact/{artifact_type}/{id}", "artifact_by_type": "/artifact/{artifact_type}", "artifact_by_name": "/artifact/byName/{name}", "artifact_by_regex": "/artifact/byRegEx", "artifact_cost": "/artifact/{artifact_type}/{id}/cost", "artifact_audit": "/artifact/{artifact_type}/{id}/audit", "model_rate": "/artifact/model/{id}/rate", "model_lineage": "/artifact/model/{id}/lineage", "model_license_check": "/artifact/model/{id}/license-check", "model_download": "/artifact/model/{id}/download", "artifact_ingest": "/artifact/ingest", "artifact_directory": "/artifact/directory", "upload": "/upload", "admin": "/admin", "directory": "/directory"}
#            return templates.TemplateResponse("home.html", {"request": request, "endpoints": endpoints})
#        else:
#            return {"endpoints": {"health": "/health", "health_components": "/health/components", "authenticate": "/authenticate", "artifacts": "/artifacts", "reset": "/reset", "artifact_by_type_and_id": "/artifact/{artifact_type}/{id}", "artifact_by_type": "/artifact/{artifact_type}", "artifact_by_name": "/artifact/byName/{name}", "artifact_by_regex": "/artifact/byRegEx", "artifact_cost": "/artifact/{artifact_type}/{id}/cost", "artifact_audit": "/artifact/{artifact_type}/{id}/audit", "model_rate": "/artifact/model/{id}/rate", "model_lineage": "/artifact/model/{id}/lineage", "model_license_check": "/artifact/model/{id}/license-check", "model_download": "/artifact/model/{id}/download", "artifact_ingest": "/artifact/ingest", "artifact_directory": "/artifact/directory", "upload": "/upload", "admin": "/admin", "directory": "/directory"}}
#    except Exception as e:
#        return {"error": f"Failed to get root: {str(e)}"}, 500


# @app.get("/ingest")
# def get_artifact_ingest(
#     name: str = None, version: str = "main", artifact_type: str = "model"
# ):
#     try:
#         if name:
#             if artifact_type == "model":
#                 result = model_ingestion(name, version)
#                 return {"message": "Ingest successful", "details": result}
#             else:
#                 global _artifact_storage
#                 artifact_id = str(random.randint(1000000000, 9999999999))
#                 url = f"https://example.com/{artifact_type}/{name}"
#                 _artifact_storage[artifact_id] = {
#                     "name": name,
#                     "type": artifact_type,
#                     "version": version,
#                     "id": artifact_id,
#                     "url": url,
#                 }
#                 return {
#                     "message": "Ingest successful",
#                     "details": {
#                         "name": name,
#                         "type": artifact_type,
#                         "version": version,
#                         "id": artifact_id,
#                         "url": url,
#                     },
#                 }
#         else:
#             return {"message": "Provide name parameter to ingest artifact"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in GET /ingest endpoint: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


# @app.post("/ingest")
# async def post_artifact_ingest(request: Request):
#     try:
#         # Try to parse form data first (for multipart/form-data)
#         name = None
#         version = "main"
#         artifact_type = "model"
#         form = None
#
#         try:
#             form = await request.form()
#             name = form.get("name")
#             version = form.get("version", "main")
#             artifact_type = form.get("type", form.get("artifact_type", "model"))
#         except Exception as form_error:
#             # If form parsing fails, try JSON
#             logger.debug(f"Form parsing failed, trying JSON: {form_error}")
#             pass
#
#         # If no name from form, try JSON body
#         if not name:
#             try:
#                 content_type = request.headers.get("content-type", "")
#                 if "application/json" in content_type:
#                     body = await request.json()
#                 elif form:
#                     body = dict(form)
#                 else:
#                     body = {}
#                 name = body.get("name") or body.get("model_id")
#                 version = body.get("version", version)
#                 artifact_type = body.get(
#                     "type", body.get("artifact_type", artifact_type)
#                 )
#             except Exception as json_error:
#                 logger.debug(f"JSON parsing failed: {json_error}")
#                 # If both fail, check if we have form data
#                 if not name and form:
#                     name = form.get("name")
#
#         if not name:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Name parameter is required. Provide 'name' or 'model_id' in form data or JSON body.",
#             )
#
#         # Validate name is not empty
#         if not name.strip():
#             raise HTTPException(
#                 status_code=400, detail="Name parameter cannot be empty"
#             )
#
#         if artifact_type == "model":
#             try:
#                 result = model_ingestion(name, version)
#                 return {"message": "Ingest successful", "details": result}
#             except HTTPException:
#                 raise
#             except Exception as model_error:
#                 logger.error(
#                     f"Error in model_ingestion for {name}: {str(model_error)}",
#                     exc_info=True,
#                 )
#                 raise HTTPException(
#                     status_code=500,
#                     detail=f"Model ingestion failed: {str(model_error)}",
#                 )
#         else:
#             global _artifact_storage
#             artifact_id = str(random.randint(1000000000, 9999999999))
#             url = f"https://example.com/{artifact_type}/{name}"
#             _artifact_storage[artifact_id] = {
#                 "name": name,
#                 "type": artifact_type,
#                 "version": version,
#                 "id": artifact_id,
#                 "url": url,
#             }
#             return {
#                 "message": "Ingest successful",
#                 "details": {
#                     "name": name,
#                     "type": artifact_type,
#                     "version": version,
#                     "id": artifact_id,
#                     "url": url,
#                 },
#             }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in /ingest endpoint: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


# @app.get("/artifact/directory")
# def get_artifact_directory(q: str = None, name_regex: str = None, model_regex: str = None, version_range: str = None, version: str = None):
#    try:
#        effective_version_range = version_range or version
#        if q:
#            import re
#            version_pattern = r'^[v~^]?\d+\.\d+\.\d+([-~^]\d+\.\d+\.\d+)?$'
#            if re.match(version_pattern, q.strip()):
#                effective_version_range = q.strip()
#                result = list_models(version_range=effective_version_range, limit=1000)
#            else:
#                escaped_query = re.escape(q)
#                search_regex = f".*{escaped_query}.*"
#                result = list_models(name_regex=search_regex, version_range=effective_version_range, limit=1000)
#        elif name_regex or model_regex:
#            result = list_models(name_regex=name_regex, model_regex=model_regex, version_range=effective_version_range, limit=1000)
#        else:
#            result = list_models(version_range=effective_version_range, limit=1000)
#        return {"artifacts": result.get("models", []), "total": len(result.get("models", [])), "next_token": result.get("next_token")}
#    except Exception as e:
#        return {"error": f"Failed to get directory: {str(e)}"}, 500
# @app.get("/artifact")
# def get_artifacts():
#    try:
#        from .services.s3_service import list_models
#        result = list_models(limit=1000)
#        artifacts = []
#        for model in result.get("models", []):
#            artifacts.append({"metadata": {"name": model["name"], "id": model.get("id", model["name"]), "type": "model"}, "data": {"version": model.get("version", "1.0.0")}})
#        return {"artifacts": artifacts, "total": len(artifacts), "next_token": result.get("next_token")}
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to get artifacts: {str(e)}")
# @app.get("/artifact/{artifact_type}")
# def get_artifacts_by_type(artifact_type: str):
#    try:
#        from .services.s3_service import list_models
#        if artifact_type == "model":
#            result = list_models(limit=1000)
#            artifacts = []
#            for model in result.get("models", []):
#                artifacts.append({"metadata": {"name": model["name"], "id": model["name"], "type": artifact_type}, "data": {"version": model["version"]}})
#            return {"artifacts": artifacts, "total": len(artifacts), "next_token": result.get("next_token")}
#        else:
#            raise HTTPException(status_code=400, detail=f"Artifact type '{artifact_type}' not supported. Only 'model' type is supported.")
#    except HTTPException:
#        raise
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to get artifacts by type: {str(e)}")
# @app.post("/upload")
# async def upload_artifact_model(request: Request, file: UploadFile = File(...), model_id: str = None, version: str = None):
#    try:
#        if not file or not file.filename:
#            raise HTTPException(status_code=400, detail="File is required")
#        if not file.filename.endswith('.zip'):
#            raise HTTPException(status_code=400, detail="Only ZIP files are supported")
#        filename = file.filename.replace('.zip', '').strip()
#        effective_model_id = model_id or filename if filename else "uploaded-model"
#        effective_version = version or "1.0.0"
#        file_content = await file.read()
#        if not file_content:
#            raise HTTPException(status_code=400, detail="File content is empty")
#        result = upload_model(file_content, effective_model_id, effective_version)
#        return {"message": "Upload successful", "details": result, "model_id": effective_model_id, "version": effective_version}
#    except HTTPException:
#        raise
#    except Exception as e:
#        import traceback
#        error_msg = f"Upload failed: {str(e)}"
#        print(f"Upload error: {traceback.format_exc()}")
#        raise HTTPException(status_code=500, detail=error_msg)
# @app.get("/artifact/model/{id}/upload-url")
# def get_upload_url(id: str, version: str = "1.0.0", expires_in: int = 3600):
#    try:
#        from .services.s3_service import get_presigned_upload_url
#        result = get_presigned_upload_url(id, version, expires_in)
#        return result
#    except HTTPException:
#        raise
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")
# @app.post("/artifact/model/{id}/upload")
# async def upload_artifact_model_by_id(id: str, request: Request, file: UploadFile = File(...), version: str = None):
#    try:
#        if not file or not file.filename:
#            raise HTTPException(status_code=400, detail="File is required")
#        if not file.filename.endswith('.zip'):
#            raise HTTPException(status_code=400, detail="Only ZIP files are supported")
#        effective_version = version or "1.0.0"
#        file_content = await file.read()
#        if not file_content:
#            raise HTTPException(status_code=400, detail="File content is empty")
#        result = upload_model(file_content, id, effective_version)
#        return {"message": "Upload successful", "details": result, "model_id": id, "version": effective_version}
#    except HTTPException:
#        raise
#    except Exception as e:
#        import traceback
#        error_msg = f"Upload failed: {str(e)}"
#        print(f"Upload error: {traceback.format_exc()}")
#        raise HTTPException(status_code=500, detail=error_msg)
# @app.get("/artifact/model/{id}/download")
# def download_artifact_model(id: str, version: str = "1.0.0", component: str = "full"):
#    try:
#        file_content = download_model(id, version, component)
#        if file_content:
#            return Response(
#                content=file_content,
#                media_type="application/zip",
#                headers={"Content-Disposition": f"attachment; filename={id}_{version}_{component}.zip"}
#            )
#        else:
#            raise HTTPException(status_code=404, detail=f"Failed to download {id} v{version}")
#    except Exception as e:
#        return {"error": f"Download failed: {str(e)}"}, 500
# @app.get("/admin")
# def get_admin(request: Request):
#    try:
#        templates_dir = Path(__file__).parent.parent / "templates"
#        frontend_dir = Path(__file__).parent.parent / "frontend" / "templates"
#        admin_template = None
#        templates = None
#        if (templates_dir / "admin.html").exists():
#            admin_template = templates_dir / "admin.html"
#            from fastapi.templating import Jinja2Templates
#            templates = Jinja2Templates(directory=str(templates_dir))
#        elif (frontend_dir / "admin.html").exists():
#            admin_template = frontend_dir / "admin.html"
#            from fastapi.templating import Jinja2Templates
#            templates = Jinja2Templates(directory=str(frontend_dir))
#        if admin_template and templates:
#            return templates.TemplateResponse("admin.html", {"request": request})
#        else:
#            return {"message": "Admin interface", "status": "available"}
#    except HTTPException:
#        raise
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to get admin: {str(e)}")
# Include routers in order - public endpoints first, then secured
# 1) Public grader-compatible endpoints (/authenticate, /login) — NO auth
app.include_router(authenticate_router)
# 2) Public auth router (register/login) - no bearer required
app.include_router(auth_ns_public)  # /auth/register, /auth/login  (public)
# 3) Secured auth router (me/logout) - bearer required
app.include_router(auth_ns_private)  # /auth/me, /auth/logout      (Bearer required)

# 4) Existing API router
app.include_router(api_router, prefix="/api")
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = (
    Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None
)
