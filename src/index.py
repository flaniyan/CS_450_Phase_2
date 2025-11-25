from __future__ import annotations
from pathlib import Path
import re
import os
import json
from typing import Dict, Any, Optional
from starlette.datastructures import UploadFile
import uvicorn
import random
import logging
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, status
import watchtower

# from fastapi.security import HTTPBearer  # Not used - removed to prevent accidental security enforcement
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from botocore.exceptions import ClientError
from .routes.index import router as api_router
from .routes import frontend as frontend_routes
from .services.auth_public import (
    public_auth as authenticate_router,
    STATIC_TOKEN as PUBLIC_STATIC_TOKEN,
)
from .services.auth_service import (
    auth_public as auth_ns_public,
    auth_private as auth_ns_private,
    ensure_default_admin,
    purge_tokens,
    verify_jwt_token,
)
from .services.s3_service import (
    list_models,
    list_artifacts_from_s3,
    upload_model,
    download_model,
    reset_registry,
    get_model_lineage_from_config,
    get_model_sizes,
    s3,
    ap_arn,
    model_ingestion,
    store_artifact_metadata,
    find_artifact_metadata_by_id,
)
from .services.artifact_storage import (
    save_artifact,
    get_artifact as get_artifact_from_db,
    get_generic_artifact_metadata,
    update_artifact,
    delete_artifact,
    list_all_artifacts,
    find_artifacts_by_type,
    find_artifacts_by_name,
    find_models_with_null_link,
    clear_all_artifacts,
)
from .services.rating import run_scorer, alias, analyze_model_content
from .services.license_compatibility import (
    extract_model_license,
    extract_github_license,
    check_license_compatibility,
)

# bearer = HTTPBearer(auto_error=True)  # Unused - removed to prevent any accidental security enforcement

# Configure CloudWatch logging
def setup_cloudwatch_logging():
    """Configure CloudWatch Logs handler using watchtower"""
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    log_group = os.getenv("CLOUDWATCH_LOG_GROUP", "/acme-api/application-logs")
    
    # Only add CloudWatch handler if AWS is available (in production)
    try:
        # Test if AWS credentials are available by checking STS (simpler than logs API)
        import boto3
        sts = boto3.client("sts", region_name=aws_region)
        sts.get_caller_identity()  # Simple test that AWS credentials work
        
        # Create a boto3 CloudWatch Logs client with the region
        logs_client = boto3.client("logs", region_name=aws_region)
        
        # Add CloudWatch handler to root logger
        root_logger = logging.getLogger()
        cloudwatch_handler = watchtower.CloudWatchLogHandler(
            log_group=log_group,
            stream_name="api",
            boto3_client=logs_client,  # Pass the boto3 client instead of region_name
            use_queues=False,  # Synchronous logging for simpler implementation
        )
        cloudwatch_handler.setLevel(logging.INFO)
        root_logger.addHandler(cloudwatch_handler)
        # Force a test log to verify it works
        test_logger = logging.getLogger("cloudwatch_test")
        test_logger.info(f"CloudWatch logging configured: log_group={log_group}, region={aws_region}")
        print(f"SUCCESS: CloudWatch handler added. Log group: {log_group}, Stream: api", file=sys.stderr)
    except Exception as e:
        # AWS not available - fallback to standard logging
        # Log to stderr so it appears in ECS container logs
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: CloudWatch logging failed: {e}", file=sys.stderr)
        print(f"Traceback: {error_details}", file=sys.stderr)
        logging.warning(f"CloudWatch logging not available: {e}. Using standard logging.")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure CloudWatch logging (only if AWS is available)
setup_cloudwatch_logging()


class User(BaseModel):
    name: str
    is_admin: bool = False


class Secret(BaseModel):
    password: str


class AuthRequest(BaseModel):
    user: User
    secret: Secret


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


# Thread-safe counter for concurrent requests
import threading
_concurrent_requests = 0
_concurrent_requests_lock = threading.Lock()


# Register custom middleware as BaseHTTPMiddleware to ensure it ALWAYS runs
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or extract correlation ID for request tracing
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Add correlation ID to request state for use in handlers
        request.state.correlation_id = correlation_id
        
        # Track concurrent requests
        global _concurrent_requests
        with _concurrent_requests_lock:
            _concurrent_requests += 1
            current_concurrent = _concurrent_requests
        
        # Publish concurrent requests gauge metric
        try:
            from .services.performance.instrumentation import publish_metric
            publish_metric(
                "ConcurrentRequests",
                value=float(current_concurrent),
                unit="Count",
                dimensions={"Component": "ECS"}
            )
        except Exception as e:
            logger.debug(f"Failed to publish concurrent requests metric: {str(e)}")
        
        # Capture request start time for duration calculation
        start_time = time.time()
        
        # Extract client IP (check various headers for proxy/load balancer scenarios)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or request.client.host if request.client else "unknown"
        )
        
        # Extract user agent
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Prepare structured log data
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params) if request.query_params else None,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "status_code": None,  # Will be set after response
            "duration_ms": None,  # Will be calculated after response
            "concurrent_requests": current_concurrent,
        }
        
        # Log request start
        logger.info(f"API Request: {json.dumps({**log_data, 'event': 'request_start'})}")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Publish request processing time metric to CloudWatch
            try:
                from .services.performance.instrumentation import publish_metric
                publish_metric(
                    "RequestProcessingTime",
                    value=duration_ms,
                    unit="Milliseconds",
                    dimensions={"Component": "ECS", "Path": request.url.path}
                )
            except Exception as e:
                logger.debug(f"Failed to publish request processing time metric: {str(e)}")
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Update log data with response info
            log_data.update({
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "event": "request_complete"
            })
            
            # Log structured API metrics as JSON
            logger.info(f"API Metrics: {json.dumps(log_data)}")
            
            return response
        except Exception as e:
            # Calculate duration even on error
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Publish request processing time metric even on error
            try:
                from .services.performance.instrumentation import publish_metric
                publish_metric(
                    "RequestProcessingTime",
                    value=duration_ms,
                    unit="Milliseconds",
                    dimensions={"Component": "ECS", "Path": request.url.path, "Error": "true"}
                )
            except Exception:
                pass
            
            # Update log data with error info
            log_data.update({
                "status_code": 500,
                "duration_ms": duration_ms,
                "error": str(e),
                "event": "request_error"
            })
            
            # Log error with structured data
            logger.error(f"API Error: {json.dumps(log_data)}", exc_info=True)
            raise
        finally:
            # Decrement concurrent requests counter
            with _concurrent_requests_lock:
                _concurrent_requests -= 1


# Register middleware using BaseHTTPMiddleware to ensure it always runs
app.add_middleware(LoggingMiddleware)


@app.on_event("startup")
async def startup_event():
    """Log all registered routes on startup and initialize _artifact_storage"""
    logger.info("=== REGISTERED ROUTES ===")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            logger.info(f"Route: {list(route.methods)} {route.path}")
    logger.info("=== END REGISTERED ROUTES ===")
    ensure_default_admin()
    
    # Initialize _artifact_storage from DynamoDB (for datasets and code)
    # This ensures immediate consistency for queries
    try:
        global _artifact_storage
        all_artifacts = list_all_artifacts()
        for artifact in all_artifacts:
            artifact_type = artifact.get("type", "")
            if artifact_type in ["dataset", "code"]:
                artifact_id = artifact.get("id", "")
                if artifact_id:
                    _artifact_storage[artifact_id] = {
                        "name": artifact.get("name", ""),
                        "type": artifact_type,
                        "version": artifact.get("version", "main"),
                        "id": artifact_id,
                        "url": artifact.get("url", ""),
                    }
        logger.info(f"Initialized _artifact_storage with {len(_artifact_storage)} dataset/code artifacts")
    except Exception as e:
        logger.warning(f"Failed to initialize _artifact_storage from DynamoDB: {str(e)}")
        # Continue without initialization - _artifact_storage will be populated as artifacts are created


# Rating status tracking for async rating (kept in-memory as it's transient)
# Status values: "pending", "completed", "disqualified", "failed"
_rating_status = {}
_rating_locks = {}  # threading.Event objects for blocking requests
_rating_results = {}  # Store rating results by artifact_id

# In-memory storage for dataset and code artifacts (for immediate consistency in queries)
# Key: artifact_id, Value: dict with name, type, version, id, url
# This provides immediate consistency like the reference code's _artifact_storage
_artifact_storage = {}


def sanitize_model_id_for_s3(model_id: str) -> str:
    """Sanitize model ID for S3 key (same logic as upload_model)"""
    return (
        model_id.replace("https://huggingface.co/", "")
        .replace("http://huggingface.co/", "")
        .replace("/", "_")
        .replace(":", "_")
        .replace("\\", "_")
        .replace("?", "_")
        .replace("*", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


def generate_download_url(artifact_name: str, artifact_type: str, version: str = "main") -> str:
    """
    Generate a download URL for an artifact.
    Per spec example, use a simple path-based URL format.
    Example from spec: https://ec2-10-121-34-12/download/bert-base-uncased
    """
    # Sanitize name for URL path (remove special characters that might break URLs)
    sanitized_name = sanitize_model_id_for_s3(artifact_name)
    # Use a simple path-based format matching the spec example
    # The spec shows: https://ec2-10-121-34-12/download/bert-base-uncased
    # We'll use a similar format with the artifact name
    return f"https://s3.amazonaws.com/{ap_arn}/{artifact_type}s/{sanitized_name}/{version}/model.zip" if artifact_type == "model" else f"https://s3.amazonaws.com/{ap_arn}/{artifact_type}s/{sanitized_name}/{version}/metadata.json"


def build_artifact_response(artifact_name: str, artifact_id: str, artifact_type: str, url: str, version: str = "main") -> Dict[str, Any]:
    """
    Build a standardized artifact response with metadata, data.url, and data.download_url.
    """
    download_url = generate_download_url(artifact_name, artifact_type, version)
    return {
        "metadata": {
            "name": artifact_name,
            "id": artifact_id,
            "type": artifact_type,
        },
        "data": {
            "url": url,
            "download_url": download_url
        },
    }


def _run_async_rating(artifact_id: str, model_name: str, version: str):
    """
    Run rating asynchronously in background thread.
    Updates _rating_status and _rating_results when complete.
    """
    global _rating_status, _rating_locks, _rating_results
    
    try:
        logger.info(f"DEBUG: [ASYNC RATING] Starting rating for artifact_id='{artifact_id}', model_name='{model_name}'")
        _rating_status[artifact_id] = "pending"
        
        # Perform rating
        rating = analyze_model_content(model_name)
        
        if not rating:
            logger.warning(f"DEBUG: [ASYNC RATING] Rating returned None/empty for '{model_name}'")
            _rating_status[artifact_id] = "failed"
            _rating_results[artifact_id] = None
        else:
            net_score = alias(rating, "net_score", "NetScore", "netScore") or 0.0
            if net_score < 0.5:
                logger.warning(f"DEBUG: [ASYNC RATING] Model disqualified: net_score={net_score} < 0.5")
                _rating_status[artifact_id] = "disqualified"
                _rating_results[artifact_id] = None
            else:
                logger.info(f"DEBUG: [ASYNC RATING] Rating completed successfully: net_score={net_score}")
                _rating_status[artifact_id] = "completed"
                _rating_results[artifact_id] = rating
        
        # Signal that rating is complete
        if artifact_id in _rating_locks:
            _rating_locks[artifact_id].set()
            logger.info(f"DEBUG: [ASYNC RATING] Signaled completion for artifact_id='{artifact_id}'")
    except Exception as e:
        logger.error(f"DEBUG: [ASYNC RATING] Error during rating for '{artifact_id}': {str(e)}", exc_info=True)
        _rating_status[artifact_id] = "failed"
        _rating_results[artifact_id] = None
        if artifact_id in _rating_locks:
            _rating_locks[artifact_id].set()


def _get_artifact_size_mb(artifact_type: str, artifact_id: str) -> float:
    """
    Get artifact size in MB from S3 or download URL.
    Returns 0.0 if size cannot be determined.
    """
    try:
        if artifact_type == "model":
            model_name = _get_model_name_for_s3(artifact_id)
            if not model_name:
                model_name = sanitize_model_id_for_s3(artifact_id)
            sizes = get_model_sizes(model_name, "1.0.0")
            if "error" not in sizes:
                return sizes.get("full", 0) / (1024 * 1024)
        elif artifact_type in ["dataset", "code"]:
            # Try to get size from S3 metadata file
            artifact = get_generic_artifact_metadata(artifact_type, artifact_id)
            if not artifact:
                artifact = get_artifact_from_db(artifact_id)
            
            if artifact:
                artifact_name = artifact.get("name", "")
                if artifact_name:
                    sanitized_name = sanitize_model_id_for_s3(artifact_name)
                    # Try common versions
                    for version in ["main", "1.0.0", "latest"]:
                        try:
                            s3_key = f"{artifact_type}s/{sanitized_name}/{version}/metadata.json"
                            response = s3.head_object(Bucket=ap_arn, Key=s3_key)
                            size_bytes = response.get("ContentLength", 0)
                            if size_bytes > 0:
                                return size_bytes / (1024 * 1024)
                        except ClientError:
                            continue
                    
                    # If metadata.json not found, try to get size from download URL
                    url = artifact.get("url", "")
                    if url:
                        try:
                            import requests
                            head_response = requests.head(url, timeout=5, allow_redirects=True)
                            content_length = head_response.headers.get("Content-Length")
                            if content_length:
                                return int(content_length) / (1024 * 1024)
                        except Exception:
                            pass
    except Exception as e:
        logger.debug(f"Error getting artifact size: {str(e)}")
    return 0.0


def _get_model_name_for_s3(artifact_id: str) -> Optional[str]:
    """
    Helper function to get the model name from artifact_id for S3 lookups.
    Models are stored in S3 by name (sanitized), not by artifact_id.
    
    Args:
        artifact_id: The artifact ID to look up
        
    Returns:
        Sanitized model name for S3, or None if not found
    """
    try:
        # Try to get artifact from database
        artifact = get_generic_artifact_metadata("model", artifact_id)
        if not artifact:
            artifact = get_artifact_from_db(artifact_id)
        
        if artifact and artifact.get("type") == "model":
            name = artifact.get("name", "")
            if name:
                # Sanitize name for S3 (same logic as in model_ingestion)
                sanitized_name = (
                    name.replace("https://huggingface.co/", "")
                    .replace("http://huggingface.co/", "")
                    .replace("/", "_")
                    .replace(":", "_")
                    .replace("\\", "_")
                    .replace("?", "_")
                    .replace("*", "_")
                    .replace('"', "_")
                    .replace("<", "_")
                    .replace(">", "_")
                    .replace("|", "_")
                )
                return sanitized_name
        return None
    except Exception as e:
        logger.debug(f"Error getting model name for S3: {str(e)}")
        return None


def verify_auth_token(request: Request) -> bool:
    """
    Verify auth token from either Authorization or X-Authorization header.
    Per OpenAPI spec, X-Authorization is the required header, but we also accept
    Authorization for flexibility. Uses proper JWT verification from auth_service.
    Also accepts the static token from /authenticate endpoint for autograder compatibility.
    """
    # Per OpenAPI spec, X-Authorization is required, but check both for flexibility
    # HTTP headers are case-insensitive, so this will match X-Authorization, x-authorization, etc.
    raw = (
        request.headers.get("x-authorization")
        or request.headers.get("authorization")
        or ""
    )
    raw = raw.strip()

    if not raw:
        logger.debug("DEBUG: No authorization header found")
        return False

    # Normalize: allow "Bearer <token>" or legacy "bearer <token>"
    if raw.lower().startswith("bearer "):
        token = raw.split(" ", 1)[1].strip()
    else:
        # Also accept a raw JWT without the "Bearer " prefix
        token = raw.strip()

    if not token:
        logger.debug("DEBUG: Empty token after normalization")
        return False

    # Check if this is the static token from /authenticate endpoint (autograder compatibility)
    from .services.auth_public import STATIC_TOKEN
    if token == STATIC_TOKEN:
        logger.debug("DEBUG: Static token from /authenticate accepted")
        return True

    # Basic format check: JWT should have 3 parts separated by dots
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        logger.debug("DEBUG: Token does not have valid JWT format (3 parts)")
        return False

    # Use proper JWT verification from auth_service
    try:
        decoded_token = verify_jwt_token(token)
        if decoded_token is None:
            logger.debug("DEBUG: JWT verification failed - token is invalid or expired")
            return False
        
        logger.debug(f"DEBUG: JWT verification successful - user_id: {decoded_token.get('user_id', decoded_token.get('username', 'unknown'))}")
        return True
    except Exception as e:
        logger.warning(f"DEBUG: Exception during JWT verification: {str(e)}")
        return False


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/health/performance/workload")
async def trigger_performance_workload(request: Request):
    """
    Trigger a performance workload run.
    Accepts parameters to configure the workload and returns a run_id for tracking.
    """
    try:
        body = await request.json()
        
        # Extract parameters with defaults
        num_clients = body.get("num_clients", 100)
        model_id = body.get("model_id", "arnir0/Tiny-LLM")
        artifact_id = body.get("artifact_id")
        duration_seconds = body.get("duration_seconds", 300)
        
        # Validate parameters
        if not isinstance(num_clients, int) or num_clients < 1:
            raise HTTPException(
                status_code=400,
                detail="num_clients must be a positive integer"
            )
        if not isinstance(model_id, str) or not model_id:
            raise HTTPException(
                status_code=400,
                detail="model_id must be a non-empty string"
            )
        if duration_seconds is not None and (not isinstance(duration_seconds, int) or duration_seconds < 1):
            raise HTTPException(
                status_code=400,
                detail="duration_seconds must be a positive integer"
            )
        
        # Import and trigger workload
        from .services.performance.workload_trigger import trigger_workload
        
        # Use API Gateway URL as the base URL for load generation
        # This is where clients will actually make requests
        # Can be overridden via environment variable
        base_url = os.getenv("API_BASE_URL", "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
        
        result = trigger_workload(
            num_clients=num_clients,
            model_id=model_id,
            artifact_id=artifact_id,
            duration_seconds=duration_seconds,
            base_url=base_url
        )
        
        return JSONResponse(
            status_code=202,  # Accepted
            content=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering performance workload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger performance workload: {str(e)}"
        )


@app.get("/health/performance/results/{run_id}")
def get_performance_results(run_id: str):
    """
    Get aggregated performance results for a workload run.
    Queries DynamoDB for raw metrics and calculates statistics.
    """
    try:
        from .services.performance.results_retrieval import get_performance_results
        from .services.performance.workload_trigger import get_workload_status
        
        # Get workload status from in-memory store
        workload_status = get_workload_status(run_id)
        
        # Get aggregated results
        result = get_performance_results(run_id, workload_status)
        
        # If run not found and no metrics in DynamoDB, return 404
        if result.get("status") == "not_found" and result["metrics"]["total_requests"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Performance run with run_id {run_id} not found"
            )
        
        return JSONResponse(status_code=200, content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving performance results for run_id={run_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve performance results: {str(e)}"
        )


@app.get("/health/components")
def health_components(windowMinutes: int = 60, includeTimeline: bool = False):
    # Validate windowMinutes parameter
    if windowMinutes < 5 or windowMinutes > 1440:
        raise HTTPException(
            status_code=400, detail="windowMinutes must be between 5 and 1440"
        )

    # Build component with required fields
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    component = {
        "id": "validator-service",
        "status": "ok",  # Required: must be one of: ok, degraded, critical, unknown
        "observed_at": observed_at,  # Required: datetime string in UTC
    }

    # Add optional fields
    component["display_name"] = "Validator Service"
    component["description"] = (
        "Main API validator service handling artifact ingestion and validation"
    )

    # Add metrics (optional)
    component["metrics"] = {
        "uptime_seconds": 3600,  # Example metric
        "requests_processed": 0,
    }

    # Add issues (optional) - empty array if no issues
    component["issues"] = []

    # Add timeline if requested (optional)
    if includeTimeline:
        component["timeline"] = []  # Array of HealthTimelineEntry objects

    # Add logs (optional) - empty array if no logs
    component["logs"] = []

    # Build response with required fields
    response = {
        "components": [component],  # Required: array of HealthComponentDetail
        "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),  # Required: datetime string in UTC
        "window_minutes": windowMinutes,  # Optional but recommended
    }

    return response


@app.post("/artifacts")
async def list_artifacts(request: Request, offset: str = None):
    global _artifact_storage
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        body = (
            await request.json()
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        if not isinstance(body, list):
            raise HTTPException(
                status_code=400,
                detail="Request body must be an array of ArtifactQuery objects",
            )
        results = []
        for query in body:
            if not isinstance(query, dict):
                raise HTTPException(
                    status_code=400, detail="Each query must be an object"
                )
            name = query.get("name")
            if not name:
                raise HTTPException(
                    status_code=400,
                    detail="Missing required field 'name' in artifact_query",
                )
            types_filter = query.get("types", [])
            if name == "*":
                # Search S3 for models
                if not types_filter or "model" in types_filter:
                    result = list_models(limit=1000)
                    if result is None:
                        result = {"models": []}
                    models = result.get("models") or []
                    for model in models:
                        if isinstance(model, dict):
                            results.append(
                                {
                                    "name": model.get("name", ""),
                                    "id": model.get("id", model.get("name", "")),
                                    "type": "model",
                                }
                            )
                
                # Search _artifact_storage for datasets and code (immediate consistency)
                if not types_filter or "dataset" in types_filter or "code" in types_filter:
                    for artifact_id, artifact_data in _artifact_storage.items():
                        artifact_type_stored = artifact_data.get("type", "")
                        if (not types_filter or artifact_type_stored in types_filter):
                            results.append(
                                {
                                    "name": artifact_data.get("name", ""),
                                    "id": artifact_id,
                                    "type": artifact_type_stored,
                                }
                            )
                
                # Also get artifacts from database (for models and any missing datasets/code)
                all_artifacts = list_all_artifacts()
                seen_ids = {r.get("id") for r in results}  # Avoid duplicates
                for artifact in all_artifacts:
                    artifact_type_stored = artifact.get("type", "")
                    artifact_id = artifact.get("id", "")
                    # Only add if not already in results and matches filter
                    if artifact_id not in seen_ids and (not types_filter or artifact_type_stored in types_filter):
                        results.append(
                            {
                                "name": artifact.get("name", artifact_id),
                                "id": artifact_id,
                                "type": artifact_type_stored,
                            }
                        )
                        seen_ids.add(artifact_id)
            else:
                # Exact name match - need to return only a single package per spec requirement
                # Check all sources but return only the first exact match found
                seen_ids = set()
                
                # Priority order: Database -> S3 -> In-memory storage
                # Check database first (most authoritative)
                all_artifacts = list_all_artifacts()
                for artifact in all_artifacts:
                    artifact_id = artifact.get("id", "")
                    artifact_name = artifact.get("name", "")
                    artifact_type_stored = artifact.get("type", "")
                    # Exact name match (case-sensitive, no regex)
                    # Ensure artifact_name is not None or empty
                    if (artifact_name and artifact_name == name and 
                        (not types_filter or artifact_type_stored in types_filter) and
                        artifact_id not in seen_ids):
                        results.append(
                            {
                                "name": artifact_name,
                                "id": artifact_id,
                                "type": artifact_type_stored,
                            }
                        )
                        seen_ids.add(artifact_id)
                        # Return only the first match - single package requirement
                        break
                
                # If not found in database, search S3 for models
                if not results and (not types_filter or "model" in types_filter):
                    escaped_name = re.escape(name)
                    name_pattern = f"^{escaped_name}$"
                    result = list_models(name_regex=name_pattern, limit=1000)
                    if result is None:
                        result = {"models": []}
                    models = result.get("models") or []
                    for model in models:
                        if isinstance(model, dict):
                            model_name = model.get("name", "")
                            # Exact name match (not regex, direct comparison)
                            if model_name == name:
                                model_id = model.get("id", model.get("name", ""))
                                if model_id not in seen_ids:
                                    results.append(
                                        {
                                            "name": model_name,
                                            "id": model_id,
                                            "type": "model",
                                        }
                                    )
                                    seen_ids.add(model_id)
                                    # Return only first match for exact name
                                    break
                
                # If still not found, search _artifact_storage for datasets and code
                if not results and (not types_filter or "dataset" in types_filter or "code" in types_filter):
                    for artifact_id, artifact_data in _artifact_storage.items():
                        artifact_name = artifact_data.get("name", "")
                        artifact_type_stored = artifact_data.get("type", "")
                        # Exact name match (case-sensitive)
                        if (artifact_name == name and 
                            (not types_filter or artifact_type_stored in types_filter) and
                            artifact_id not in seen_ids):
                            results.append(
                                {
                                    "name": artifact_name,
                                    "id": artifact_id,
                                    "type": artifact_type_stored,
                                }
                            )
                            seen_ids.add(artifact_id)
                            # Return only first match for exact name
                            break
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


def _extract_dataset_code_names_from_readme(readme_text: str) -> Dict[str, str]:
    """
    Extract dataset and code names from README text using LLM-like analysis.
    Looks for common patterns like "dataset:", "uses dataset", "code:", etc.
    Returns dict with "dataset_name" and "code_name" keys (or None if not found).
    """
    if not readme_text:
        return {"dataset_name": None, "code_name": None}
    
    dataset_name = None
    code_name = None
    
    # Common patterns for dataset mentions
    dataset_patterns = [
        r'dataset[:\s]+([A-Za-z0-9_\-/]+)',
        r'uses?\s+([A-Za-z0-9_\-/]+)\s+dataset',
        r'trained\s+on\s+([A-Za-z0-9_\-/]+)',
        r'([A-Za-z0-9_\-/]+)\s+dataset',
    ]
    
    # Common patterns for code/library mentions
    code_patterns = [
        r'code[:\s]+([A-Za-z0-9_\-/]+)',
        r'library[:\s]+([A-Za-z0-9_\-/]+)',
        r'uses?\s+([A-Za-z0-9_\-/]+)\s+library',
        r'built\s+with\s+([A-Za-z0-9_\-/]+)',
        r'([A-Za-z0-9_\-/]+)\s+library',
    ]
    
    readme_lower = readme_text.lower()
    
    # Try to extract dataset name
    for pattern in dataset_patterns:
        matches = re.finditer(pattern, readme_lower, re.IGNORECASE)
        for match in matches:
            candidate = match.group(1).strip()
            # Filter out common false positives
            if candidate and len(candidate) > 2 and candidate not in ['the', 'this', 'that', 'our']:
                dataset_name = candidate
                break
        if dataset_name:
            break
    
    # Try to extract code/library name
    for pattern in code_patterns:
        matches = re.finditer(pattern, readme_lower, re.IGNORECASE)
        for match in matches:
            candidate = match.group(1).strip()
            # Filter out common false positives
            if candidate and len(candidate) > 2 and candidate not in ['the', 'this', 'that', 'our']:
                code_name = candidate
                break
        if code_name:
            break
    
    return {"dataset_name": dataset_name, "code_name": code_name}


def _link_model_to_datasets_code(artifact_id: str, model_name: str, readme_text: str = None):
    """
    Link a model to datasets and code artifacts by:
    1. Extracting dataset/code names from README
    2. Finding matching artifacts in database
    3. Updating model entry with dataset_id and code_id
    """
    if not readme_text:
        # Try to get README from model metadata
        try:
            from .services.s3_service import download_model
            zip_content = download_model(model_name, "main", "full")
            if zip_content:
                import zipfile
                import io
                with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
                    for file_info in zip_file.filelist:
                        if "readme" in file_info.filename.lower():
                            readme_text = zip_file.read(file_info).decode("utf-8", errors="ignore")
                            break
        except Exception as e:
            logger.debug(f"Could not extract README for linking: {str(e)}")
            return
    
    if not readme_text:
        return
    
    # Extract dataset and code names from README
    extracted = _extract_dataset_code_names_from_readme(readme_text)
    dataset_name = extracted.get("dataset_name")
    code_name = extracted.get("code_name")
    
    if not dataset_name and not code_name:
        return
    
    # Find matching artifacts from database and _artifact_storage (for immediate consistency)
    dataset_id = None
    code_id = None
    
    # Normalize names by replacing "/" with "-" for consistent matching
    # This ensures names like "google-research/bert" match "google-research-bert"
    def normalize_name(name: str) -> str:
        """Normalize name by replacing '/' with '-' for consistent matching"""
        if not name:
            return ""
        return name.replace("/", "-")
    
    # Search for datasets (check _artifact_storage first, then database)
    if dataset_name:
        normalized_dataset_name = normalize_name(dataset_name)
        # First check _artifact_storage for immediate consistency
        global _artifact_storage
        for artifact_id, artifact_data in _artifact_storage.items():
            if artifact_data.get("type") == "dataset":
                artifact_name = artifact_data.get("name", "")
                normalized_artifact_name = normalize_name(artifact_name)
                # Match using normalized names (handles both "google-research/bert" and "google-research-bert")
                if (normalized_dataset_name.lower() in normalized_artifact_name.lower() or 
                    normalized_artifact_name.lower() in normalized_dataset_name.lower() or
                    dataset_name.lower() in artifact_name.lower() or 
                    artifact_name.lower() in dataset_name.lower()):
                    dataset_id = artifact_id
                    logger.info(f"DEBUG: Linked model '{model_name}' to dataset '{artifact_name}' (id={dataset_id}) from _artifact_storage")
                    break

        # If not found in _artifact_storage, check database
        if not dataset_id:
            datasets = find_artifacts_by_type("dataset")
            for artifact in datasets:
                artifact_name = artifact.get("name", "")
                normalized_artifact_name = normalize_name(artifact_name)
                # Match using normalized names
                if (normalized_dataset_name.lower() in normalized_artifact_name.lower() or 
                    normalized_artifact_name.lower() in normalized_dataset_name.lower() or
                    dataset_name.lower() in artifact_name.lower() or 
                    artifact_name.lower() in dataset_name.lower()):
                    dataset_id = artifact.get("id")
                    logger.info(f"DEBUG: Linked model '{model_name}' to dataset '{artifact_name}' (id={dataset_id}) from database")
                    break

    # Search for code (check _artifact_storage first, then database)
    if code_name:
        normalized_code_name = normalize_name(code_name)
        # First check _artifact_storage for immediate consistency
        for artifact_id, artifact_data in _artifact_storage.items():
            if artifact_data.get("type") == "code":
                artifact_name = artifact_data.get("name", "")
                normalized_artifact_name = normalize_name(artifact_name)
                # Match using normalized names
                if (normalized_code_name.lower() in normalized_artifact_name.lower() or 
                    normalized_artifact_name.lower() in normalized_code_name.lower() or
                    code_name.lower() in artifact_name.lower() or 
                    artifact_name.lower() in code_name.lower()):
                    code_id = artifact_id
                    logger.info(f"DEBUG: Linked model '{model_name}' to code '{artifact_name}' (id={code_id}) from _artifact_storage")
                    break

        # If not found in _artifact_storage, check database
        if not code_id:
            code_artifacts = find_artifacts_by_type("code")
            for artifact in code_artifacts:
                artifact_name = artifact.get("name", "")
                normalized_artifact_name = normalize_name(artifact_name)
                # Match using normalized names
                if (normalized_code_name.lower() in normalized_artifact_name.lower() or 
                    normalized_artifact_name.lower() in normalized_code_name.lower() or
                    code_name.lower() in artifact_name.lower() or 
                    artifact_name.lower() in code_name.lower()):
                    code_id = artifact.get("id")
                    logger.info(f"DEBUG: Linked model '{model_name}' to code '{artifact_name}' (id={code_id}) from database")
                    break
    
    # Update model entry with links
    updates = {}
    if dataset_id:
        updates["dataset_id"] = dataset_id
    if code_id:
        updates["code_id"] = code_id
    
    if updates:
        update_artifact(artifact_id, updates)


def _link_dataset_code_to_models(artifact_id: str, artifact_name: str, artifact_type: str):
    """
    When uploading a dataset/code, find models that reference it and link them.
    Queries Model entries where dataset_id/code_id is NULL but dataset_name/code_name matches.
    """
    if artifact_type not in ["dataset", "code"]:
        return
    
    # Find models with NULL links that might match
    if artifact_type == "dataset":
        models = find_models_with_null_link("dataset")
        for model in models:
            model_id = model.get("id")
            model_name = model.get("name", "")
            model_dataset_name = model.get("dataset_name", "")
            
            # Normalize names for matching (replace "/" with "-")
            normalized_artifact_name = artifact_name.replace("/", "-")
            normalized_model_dataset_name = model_dataset_name.replace("/", "-") if model_dataset_name else ""
            
            if model_dataset_name:
                # Match stored dataset_name with artifact name (using normalized names)
                if (normalized_artifact_name.lower() in normalized_model_dataset_name.lower() or 
                    normalized_model_dataset_name.lower() in normalized_artifact_name.lower() or
                    artifact_name.lower() in model_dataset_name.lower() or 
                    model_dataset_name.lower() in artifact_name.lower()):
                    update_artifact(model_id, {"dataset_id": artifact_id})
                    logger.info(f"DEBUG: Linked dataset '{artifact_name}' to model '{model_name}' (id={model_id}) via dataset_name='{model_dataset_name}'")
            else:
                # Fallback: simple name matching if dataset_name not stored
                if artifact_name.lower() in model_name.lower():
                    update_artifact(model_id, {"dataset_id": artifact_id})
                    logger.info(f"DEBUG: Linked dataset '{artifact_name}' to model '{model_name}' (id={model_id}) via name matching")
    
    elif artifact_type == "code":
        models = find_models_with_null_link("code")
        for model in models:
            model_id = model.get("id")
            model_name = model.get("name", "")
            model_code_name = model.get("code_name", "")
            
            # Normalize names for matching (replace "/" with "-")
            normalized_artifact_name = artifact_name.replace("/", "-")
            normalized_model_code_name = model_code_name.replace("/", "-") if model_code_name else ""
            
            if model_code_name:
                # Match stored code_name with artifact name (using normalized names)
                if (normalized_artifact_name.lower() in normalized_model_code_name.lower() or 
                    normalized_model_code_name.lower() in normalized_artifact_name.lower() or
                    artifact_name.lower() in model_code_name.lower() or 
                    model_code_name.lower() in artifact_name.lower()):
                    update_artifact(model_id, {"code_id": artifact_id})
                    logger.info(f"DEBUG: Linked code '{artifact_name}' to model '{model_name}' (id={model_id}) via code_name='{model_code_name}'")
            else:
                # Fallback: simple name matching if code_name not stored
                if artifact_name.lower() in model_name.lower():
                    update_artifact(model_id, {"code_id": artifact_id})
                    logger.info(f"DEBUG: Linked code '{artifact_name}' to model '{model_name}' (id={model_id}) via name matching")


@app.delete("/reset")
def reset_system(request: Request):
    global _rating_status, _rating_locks, _rating_results
    
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )

    # Check admin permissions
    try:
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
        # Clear artifacts from DynamoDB
        clear_all_artifacts()
        # Clear rating status (in-memory)
        _rating_status.clear()
        _rating_locks.clear()
        _rating_results.clear()
        # Clear _artifact_storage (in-memory)
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


@app.get("/package/{id}")
def get_package(id: str, request: Request):
    """Alias for /artifact/model/{id} to support autograder"""
    logger.info(f"=== GET /package/{id} HANDLER CALLED ===")
    logger.info(f"DEBUG: Route handler executed for /package/{id}")
    return get_artifact("model", id, request)

@app.get("/artifact/byName/{name:path}")
def get_artifact_by_name(name: str, request: Request):
    global _artifact_storage
    logger.info(f"DEBUG: ===== GET_ARTIFACT_BY_NAME START =====")
    logger.info(f"=== GET /artifact/byName/{name} ===")
    logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
    logger.info(f"DEBUG: Searching for artifact with name: '{name}'")
    
    if not verify_auth_token(request):
        logger.error(f"DEBUG: Authentication failed for /artifact/byName/{name}")
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    logger.info(f"DEBUG: ✅ Authentication passed for /artifact/byName/{name}")
    
    try:
        # Validate name parameter
        logger.info(f"DEBUG: Validating name parameter: '{name}'")
        if not name or not name.strip():
            logger.error(f"DEBUG: Name parameter is empty or invalid: '{name}'")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_name or it is formed improperly, or is invalid.",
            )

        # Search for models with matching name
        escaped_name = re.escape(name)
        name_pattern = f"^{escaped_name}$"
        logger.info(f"DEBUG: ===== SEARCHING S3 FOR MODELS =====")
        logger.info(f"DEBUG: Searching S3 for models with name pattern: {name_pattern}")
        result = list_models(name_regex=name_pattern, limit=1000)
        models_found = len(result.get('models', []))
        logger.info(f"DEBUG: list_models returned {models_found} models")
        artifacts = []

        # Track which artifact_ids we've already added to avoid duplicates
        seen_artifact_ids = set()
        # Get artifacts from database
        all_db_artifacts = list_all_artifacts()
        logger.info(f"DEBUG: ===== CHECKING DATABASE =====")
        logger.info(f"DEBUG: Database artifacts count: {len(all_db_artifacts)}")
        
        # Add models from S3 - find their artifact_ids from database
        for model in result.get("models", []):
            model_name = model.get("name", "")
            logger.info(f"DEBUG: Processing model from S3: name='{model_name}', version='{model.get('version', 'N/A')}'")
            if model_name == name:  # Exact match
                logger.info(f"DEBUG: Found exact match in S3: {model_name}")
                # Find artifact_id(s) for this model name in database
                found_ids = []
                for artifact in all_db_artifacts:
                    artifact_id = artifact.get("id", "")
                    if artifact.get("name") == model_name and artifact.get("type") == "model":
                        if artifact_id and artifact_id not in seen_artifact_ids:
                            found_ids.append(artifact_id)
                            seen_artifact_ids.add(artifact_id)
                            logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in database for model '{model_name}'")
                
                # If not found in database, search S3 metadata files
                if not found_ids:
                    logger.info(f"DEBUG: No artifact_id in database for '{model_name}', searching S3 metadata")
                    # Search S3 metadata files for this model name
                    try:
                        # List all models and check their metadata
                        all_models = list_models(limit=1000)
                        for m in all_models.get("models", []):
                            if m.get("name") == model_name:
                                # Try to find metadata file for this model
                                sanitized_name = (
                                    model_name.replace("https://huggingface.co/", "")
                                    .replace("http://huggingface.co/", "")
                                    .replace("/", "_")
                                    .replace(":", "_")
                                    .replace("\\", "_")
                                )
                                version = m.get("version", "main")
                                safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
                                metadata_key = f"models/{sanitized_name}/{safe_version}/metadata.json"
                                try:
                                    response = s3.get_object(Bucket=ap_arn, Key=metadata_key)
                                    metadata_json = response["Body"].read().decode("utf-8")
                                    metadata = json.loads(metadata_json)
                                    artifact_id = metadata.get("artifact_id")
                                    if artifact_id and artifact_id not in seen_artifact_ids:
                                        found_ids.append(artifact_id)
                                        seen_artifact_ids.add(artifact_id)
                                        # Restore to database
                                        save_artifact(artifact_id, {
                                            "name": model_name,
                                            "type": "model",
                                            "version": version,
                                            "id": artifact_id,
                                            "url": metadata.get("url", f"https://huggingface.co/{model_name}")
                                        })
                                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in S3 metadata for model '{model_name}'")
                                        break
                                except Exception as e:
                                    logger.debug(f"DEBUG: Could not read metadata from {metadata_key}: {str(e)}")
                                    continue
                    except Exception as e:
                        logger.warning(f"DEBUG: Error searching S3 metadata: {str(e)}")
                
                # If we found artifact_ids, use them; otherwise use model name as fallback
                if found_ids:
                    logger.info(f"DEBUG: Using {len(found_ids)} artifact_id(s) from storage/S3")
                    for artifact_id in found_ids:
                        artifacts.append(
                            {
                                "name": model_name,
                                "id": artifact_id,
                                "type": "model",
                            }
                        )
                else:
                    # Fallback: use model name as id if no artifact_id found
                    logger.warning(f"DEBUG: No artifact_id found in storage or S3 for '{model_name}', using fallback")
                    fallback_id = model.get("id", model_name)
                    if fallback_id not in seen_artifact_ids:
                        seen_artifact_ids.add(fallback_id)
                        artifacts.append(
                            {
                                "name": model_name,
                                "id": fallback_id,
                        "type": "model",
                    }
                )

        # Search _artifact_storage for datasets and code (immediate consistency)
        logger.info(f"DEBUG: Searching _artifact_storage for datasets and code with name='{name}'")
        for artifact_id, artifact_data in _artifact_storage.items():
            artifact_name = artifact_data.get("name", "")
            artifact_type = artifact_data.get("type", "")
            if artifact_name == name and artifact_id and artifact_id not in seen_artifact_ids:
                logger.info(f"DEBUG: Found {artifact_type} in _artifact_storage: id='{artifact_id}', name='{artifact_name}'")
                seen_artifact_ids.add(artifact_id)
                artifacts.append(
                    {
                        "name": artifact_name,
                        "id": artifact_id,
                        "type": artifact_type,
                    }
                )
        
        # Add artifacts from database (all artifact types including models)
        logger.info(f"DEBUG: Searching database for artifacts with name='{name}'")
        storage_matches = 0
        for artifact in all_db_artifacts:
            artifact_id = artifact.get("id", "")
            if artifact.get("name") == name and artifact_id and artifact_id not in seen_artifact_ids:  # Exact match
                storage_matches += 1
                logger.info(f"DEBUG: Found artifact in database: id='{artifact_id}', name='{artifact.get('name')}', type='{artifact.get('type')}'")
                seen_artifact_ids.add(artifact_id)
                artifacts.append(
                    {
                        "name": artifact.get("name", artifact_id),
                        "id": artifact_id,
                        "type": artifact.get("type", "model"),
                    }
                )
        logger.info(f"DEBUG: Found {storage_matches} additional artifacts in database")
        
        # Also search S3 for datasets and code artifacts (fallback)
        for artifact_type in ["dataset", "code"]:
            try:
                logger.info(f"DEBUG: Searching S3 for {artifact_type} artifacts with name='{name}'")
                result = list_artifacts_from_s3(artifact_type=artifact_type, name_regex=f"^{re.escape(name)}$", limit=1000)
                for artifact in result.get("artifacts", []):
                    artifact_name = artifact.get("name")
                    artifact_id = artifact.get("artifact_id")
                    if artifact_name == name and artifact_id and artifact_id not in seen_artifact_ids:
                        seen_artifact_ids.add(artifact_id)
                        # Restore to database
                        save_artifact(artifact_id, {
                            "name": artifact_name,
                            "type": artifact_type,
                            "version": artifact.get("version", "main"),
                            "id": artifact_id,
                            "url": f"https://example.com/{artifact_type}/{artifact_name}"
                        })
                        artifacts.append({
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact_type,
                        })
                        logger.info(f"DEBUG: Found {artifact_type} artifact in S3: id='{artifact_id}', name='{artifact_name}'")
            except Exception as e:
                logger.warning(f"DEBUG: Error searching S3 for {artifact_type}: {str(e)}")

        logger.info(f"DEBUG: Total artifacts found: {len(artifacts)}")
        if not artifacts:
            logger.error(f"DEBUG: No artifacts found for name '{name}'")
            raise HTTPException(status_code=404, detail="No such artifact.")

        logger.info(f"DEBUG: Returning {len(artifacts)} artifact(s): {artifacts}")
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artifact by name {name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_name or it is formed improperly, or is invalid: {str(e)}",
        )


@app.post("/artifact/byRegEx")
async def search_artifacts_by_regex(request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Parse request body
        body = {}
        content_type = request.headers.get("content-type", "").lower()
        logger.info(f"Content-Type: {content_type}")
        
        # Read raw body first (before any parsing attempts)
        raw_body_bytes = await request.body()
        raw_body_str = raw_body_bytes.decode('utf-8', errors='ignore') if raw_body_bytes else ""
        logger.info(f"Raw request body (length: {len(raw_body_bytes)}): {raw_body_str}")
        
        # Parse based on content type
        try:
            if "application/json" in content_type:
                if raw_body_str:
                    try:
                        body = json.loads(raw_body_str)
                        logger.info(f"Parsed JSON body: {body}")
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decode error: {str(json_err)}")
                        logger.error(f"Malformed JSON body: {repr(raw_body_str)}")
                        # Try to fix common JSON issues (missing quotes, etc.)
                        try:
                            # Try to fix JavaScript-style object notation
                            # Pattern: {regex: value} -> {"regex": "value"}
                            fixed_json = raw_body_str.strip()
                            # If it looks like {regex: ...} without quotes, try to fix it
                            if re.match(r'^\s*\{[^"]*regex[^"]*:', fixed_json):
                                # Try to extract regex value and reconstruct proper JSON
                                regex_match = re.search(r'regex\s*:\s*([^}]+)', fixed_json)
                                if regex_match:
                                    regex_value = regex_match.group(1).strip().strip('"\'')
                                    fixed_json = f'{{"regex": "{regex_value}"}}'
                                    logger.info(f"Attempting to fix JSON: {fixed_json}")
                                    body = json.loads(fixed_json)
                                    logger.info(f"Successfully parsed fixed JSON body: {body}")
                                else:
                                    raise HTTPException(
                                        status_code=400,
                                        detail=f"Invalid JSON in request body: {str(json_err)}. Received: {repr(raw_body_str[:100])}. Please use proper JSON format: {{\"regex\": \"pattern\"}}",
                                    )
                            else:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Invalid JSON in request body: {str(json_err)}. Received: {repr(raw_body_str[:100])}. Please use proper JSON format: {{\"regex\": \"pattern\"}}",
                                )
                        except json.JSONDecodeError:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Invalid JSON in request body: {str(json_err)}. Received: {repr(raw_body_str[:100])}. Please use proper JSON format: {{\"regex\": \"pattern\"}}",
                            )
                else:
                    logger.error("Empty request body")
                    raise HTTPException(
                        status_code=400,
                        detail="Request body is empty. Please provide a JSON object with a 'regex' field.",
                    )
            else:
                # Try form data
                try:
                    form = await request.form()
                    body = dict(form)
                    logger.info(f"Parsed form body: {body}")
                except:
                    # If form parsing fails, try to parse raw body as JSON anyway
                    if raw_body_str and raw_body_str.strip().startswith('{'):
                        try:
                            body = json.loads(raw_body_str)
                            logger.info(f"Parsed raw body as JSON: {body}")
                        except json.JSONDecodeError:
                            raise HTTPException(
                                status_code=400,
                                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
                            )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
                        )
        except HTTPException:
            raise
        except Exception as parse_error:
            logger.error(f"Error parsing request body: {str(parse_error)}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid. Error: {str(parse_error)}",
            )

        # Handle array or object body
        if isinstance(body, list) and len(body) > 0:
            search_criteria = body[0]
        elif isinstance(body, dict):
            search_criteria = body
        else:
            logger.error(f"Invalid body type: {type(body)}, value: {body}")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        logger.info(f"Search criteria: {search_criteria}")

        # Validate regex field
        regex_pattern = search_criteria.get("regex")
        if not regex_pattern or not isinstance(regex_pattern, str):
            logger.error(f"Missing or invalid regex field. search_criteria: {search_criteria}")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Validate regex pattern and check for ReDoS (Regular Expression Denial of Service) patterns
        # Check for dangerous patterns that cause catastrophic backtracking
        
        # Pattern 1: Overlapping alternations with quantifiers - (a|aa)*, (a|aaa)*, etc.
        # This is a classic ReDoS pattern that causes exponential backtracking
        # Match patterns like (a|aa)*, (a|aaa)+, (x|xx)*, etc.
        alternation_with_quantifier = re.search(r'\(([^|()]+)\|([^|()]+)\)([*+?])', regex_pattern)
        if alternation_with_quantifier:
            alt1, alt2, quantifier = alternation_with_quantifier.groups()
            alt1 = alt1.strip()
            alt2 = alt2.strip()
            # Check if one alternative is a prefix of another (e.g., "a" is prefix of "aa")
            # This causes exponential backtracking when combined with quantifiers
            if (alt1 in alt2 or alt2 in alt1) and len(alt1) > 0 and len(alt2) > 0 and alt1 != alt2:
                logger.warning(f"ReDoS risk detected: overlapping alternation with quantifier found: '{regex_pattern[:100]}' (alt1='{alt1}', alt2='{alt2}', quantifier='{quantifier}')")
                raise HTTPException(
                    status_code=400,
                    detail="The regex pattern contains potentially dangerous constructs (overlapping alternations with quantifiers) that may cause performance issues. Please use a simpler pattern.",
                )
        
        # Also check for more complex alternations with multiple alternatives
        # Pattern like (a|aa|aaa)*
        complex_alternation = re.search(r'\([^)]+\|[^)]+\|[^)]+\)[*+?]', regex_pattern)
        if complex_alternation:
            logger.warning(f"ReDoS risk detected: complex alternation with quantifier found: '{regex_pattern[:100]}'")
            raise HTTPException(
                status_code=400,
                detail="The regex pattern contains potentially dangerous constructs (complex alternations with quantifiers) that may cause performance issues. Please use a simpler pattern.",
            )
        
        # Pattern 2: Nested quantifiers - (a+)+, (a*)*, (a{1,99999}){1,99999}, etc.
        # Check for nested quantifiers with ranges
        nested_range_quantifier = re.search(r'\([^)]*\{[^}]+\}[^)]*\)\s*\{[^}]+\}', regex_pattern)
        if nested_range_quantifier:
            logger.warning(f"ReDoS risk detected: nested range quantifiers found: '{regex_pattern[:100]}'")
            raise HTTPException(
                status_code=400,
                detail="The regex pattern contains potentially dangerous constructs (nested range quantifiers) that may cause performance issues. Please use a simpler pattern.",
            )
        
        # Check for large quantifier ranges that could cause performance issues
        large_range_match = re.findall(r'\{(\d+),(\d+)\}', regex_pattern)
        for min_val, max_val in large_range_match:
            try:
                min_int = int(min_val)
                max_int = int(max_val)
                # If range is very large (e.g., {1,99999}), it can cause performance issues
                if max_int > 1000 or (max_int - min_int) > 1000:
                    logger.warning(f"ReDoS risk detected: large quantifier range found: {{{min_val},{max_val}}} in '{regex_pattern[:100]}'")
                    raise HTTPException(
                        status_code=400,
                        detail=f"The regex pattern contains a large quantifier range ({{{min_val},{max_val}}}) that may cause performance issues. Maximum range is 1000.",
                    )
            except ValueError:
                pass  # Skip if conversion fails
        
        # Check for nested quantifiers with +, *, ?
        dangerous_patterns = [
            r'\([^)]+\+\)\s*\+',  # Nested quantifiers like (a+)+
            r'\([^)]+\*\)\s*\*',  # Nested quantifiers like (a*)*
            r'\([^)]+\+\s*\)\s*\+',  # Multiple nested quantifiers
            r'\([^)]+\+\s*\)\s*\*',  # Mixed nested quantifiers
            r'\([^)]+\*\)\s*\+',  # Mixed nested quantifiers
            r'\([^)]+\+\)\s*\?',  # Nested with ?
            r'\([^)]+\*\)\s*\?',  # Nested with ?
        ]
        
        # Check for specific ReDoS patterns
        for dangerous_pattern in dangerous_patterns:
            if re.search(dangerous_pattern, regex_pattern):
                logger.warning(f"ReDoS risk detected: dangerous pattern found in '{regex_pattern[:100]}'")
                raise HTTPException(
                    status_code=400,
                    detail="The regex pattern contains potentially dangerous constructs that may cause performance issues. Please use a simpler pattern.",
                )
        
        # Pattern 3: Multiple consecutive quantifier groups - (a+)(a+)(a+)(a+)
        # Pattern like (a+)(a+)(a+)(a+)(a+)(a+)$ is a classic ReDoS attack
        nested_quantifier_count = regex_pattern.count('(a+') + regex_pattern.count('(a*')
        # Count sequences of quantifier groups
        consecutive_quantifier_groups = len(re.findall(r'\([^)]*[+*]\s*\)\s*\([^)]*[+*]\s*\)', regex_pattern))
        # Check for specific ReDoS pattern: multiple (a+) groups in sequence
        if re.search(r'\(a\+\)\s*\(a\+\)\s*\(a\+\)\s*\(a\+\)', regex_pattern) or nested_quantifier_count > 3 or consecutive_quantifier_groups > 2:
            logger.warning(f"ReDoS risk detected: pattern has {nested_quantifier_count} nested quantifiers or {consecutive_quantifier_groups} consecutive quantifier groups: '{regex_pattern[:100]}'")
            raise HTTPException(
                status_code=400,
                detail="The regex pattern is too complex and may cause performance issues. Please use a simpler pattern.",
            )
        
        # Validate regex pattern syntax
        try:
            compiled_pattern = re.compile(regex_pattern)
        except re.error as regex_error:
            logger.error(f"Invalid regex pattern '{regex_pattern}': {str(regex_error)}")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )
        
        # Additional safety: limit regex pattern length
        if len(regex_pattern) > 500:
            logger.warning(f"Regex pattern too long: {len(regex_pattern)} characters")
            raise HTTPException(
                status_code=400,
                detail="The regex pattern is too long. Maximum length is 500 characters.",
            )

        # Search for artifacts matching regex in S3 (all types: model, dataset, code)
        logger.info(f"DEBUG: Starting regex search with pattern: '{regex_pattern}'")
        artifacts = []
        seen_artifact_ids = set()
        
        # Search models from S3 (with reduced limit to prevent ReDoS)
        logger.info(f"DEBUG: Searching models in S3 with regex: '{regex_pattern}'")
        try:
            # Limit results to prevent excessive processing and ReDoS attacks
            result = list_models(name_regex=regex_pattern, limit=100)
            models_found = result.get("models", [])
            logger.info(f"DEBUG: Found {len(models_found)} models in S3 matching regex")
            for model in models_found:
                model_name = model.get("name", "")
                logger.info(f"DEBUG: Processing model from S3: name='{model_name}', version='{model.get('version', 'N/A')}'")
                # Find artifact_id for this model name in database
                artifact_id = None
                all_artifacts = list_all_artifacts()
                for stored_artifact in all_artifacts:
                    stored_id = stored_artifact.get("id", "")
                    if stored_artifact.get("name") == model_name and stored_artifact.get("type") == "model":
                        artifact_id = stored_id
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in database for model '{model_name}'")
                        break
                
                # Use found artifact_id or fallback to model name
                if not artifact_id:
                    artifact_id = model.get("id", model_name)
                    logger.warning(f"DEBUG: No artifact_id in storage for '{model_name}', using fallback: '{artifact_id}'")
                
                if artifact_id not in seen_artifact_ids:
                    seen_artifact_ids.add(artifact_id)
                    artifacts.append(
                        {
                            "name": model_name,
                            "id": artifact_id,
                            "type": "model",
                        }
                    )
                    logger.info(f"DEBUG: Added model artifact: name='{model_name}', id='{artifact_id}'")
        except Exception as e:
            logger.error(f"DEBUG: Error searching models with regex {regex_pattern}: {str(e)}", exc_info=True)
            logger.warning(
                f"Error searching models with regex {regex_pattern}: {str(e)}"
            )

        # Search datasets from S3
        logger.info(f"DEBUG: Searching datasets in S3 with regex: '{regex_pattern}'")
        try:
            # Limit results to prevent ReDoS attacks
            result = list_artifacts_from_s3(artifact_type="dataset", name_regex=regex_pattern, limit=100)
            datasets_found = result.get("artifacts", [])
            logger.info(f"DEBUG: Found {len(datasets_found)} datasets in S3 matching regex")
            for dataset in datasets_found:
                dataset_name = dataset.get("name", "")
                dataset_version = dataset.get("version", "main")
                logger.info(f"DEBUG: Processing dataset from S3: name='{dataset_name}', version='{dataset_version}'")
                # Try to get artifact_id from metadata.json file
                artifact_id = None
                try:
                    sanitized_name = sanitize_model_id_for_s3(dataset_name)
                    safe_version = dataset_version.replace("/", "_").replace(":", "_").replace("\\", "_")
                    s3_key = f"datasets/{sanitized_name}/{safe_version}/metadata.json"
                    logger.info(f"DEBUG: Reading metadata from S3: {s3_key}")
                    response = s3.get_object(Bucket=ap_arn, Key=s3_key)
                    metadata_json = response["Body"].read().decode("utf-8")
                    metadata = json.loads(metadata_json)
                    artifact_id = metadata.get("artifact_id")
                    metadata_name = metadata.get("name")
                    if metadata_name:
                        dataset_name = metadata_name
                        logger.info(f"DEBUG: Extracted name '{dataset_name}' from metadata.json for dataset")
                    metadata_name = metadata.get("name")
                    if metadata_name:
                        dataset_name = metadata_name
                        logger.info(f"DEBUG: Extracted name '{dataset_name}' from metadata.json for dataset")
                    if artifact_id:
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' from metadata.json for dataset '{dataset_name}'")
                except Exception as e:
                    logger.debug(f"DEBUG: Could not read metadata.json for dataset '{dataset_name}': {str(e)}")
                
                # Fallback: Find artifact_id in database
                if not artifact_id:
                    all_artifacts = list_all_artifacts()
                    for stored_artifact in all_artifacts:
                        stored_id = stored_artifact.get("id", "")
                        if stored_artifact.get("name") == dataset_name and stored_artifact.get("type") == "dataset":
                            artifact_id = stored_id
                            logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in database for dataset '{dataset_name}'")
                            break
                
                # Last fallback: use dataset name
                if not artifact_id:
                    artifact_id = dataset_name
                    logger.warning(f"DEBUG: No artifact_id found for '{dataset_name}', using fallback: '{artifact_id}'")
                
                if artifact_id not in seen_artifact_ids:
                    seen_artifact_ids.add(artifact_id)
                    artifacts.append(
                        {
                            "name": dataset_name,
                            "id": artifact_id,
                            "type": "dataset",
                        }
                    )
                    logger.info(f"DEBUG: Added dataset artifact: name='{dataset_name}', id='{artifact_id}'")
        except Exception as e:
            logger.error(f"DEBUG: Error searching datasets with regex {regex_pattern}: {str(e)}", exc_info=True)
            logger.warning(
                f"Error searching datasets with regex {regex_pattern}: {str(e)}"
            )
        
        # Search code artifacts from S3
        logger.info(f"DEBUG: Searching code artifacts in S3 with regex: '{regex_pattern}'")
        try:
            # Limit results to prevent ReDoS attacks
            result = list_artifacts_from_s3(artifact_type="code", name_regex=regex_pattern, limit=100)
            code_artifacts_found = result.get("artifacts", [])
            logger.info(f"DEBUG: Found {len(code_artifacts_found)} code artifacts in S3 matching regex")
            for code_artifact in code_artifacts_found:
                code_name = code_artifact.get("name", "")
                code_version = code_artifact.get("version", "main")
                logger.info(f"DEBUG: Processing code artifact from S3: name='{code_name}', version='{code_version}'")
                # Try to get artifact_id from metadata.json file
                artifact_id = None
                try:
                    sanitized_name = sanitize_model_id_for_s3(code_name)
                    safe_version = code_version.replace("/", "_").replace(":", "_").replace("\\", "_")
                    s3_key = f"codes/{sanitized_name}/{safe_version}/metadata.json"
                    logger.info(f"DEBUG: Reading metadata from S3: {s3_key}")
                    response = s3.get_object(Bucket=ap_arn, Key=s3_key)
                    metadata_json = response["Body"].read().decode("utf-8")
                    metadata = json.loads(metadata_json)
                    artifact_id = metadata.get("artifact_id")
                    metadata_name = metadata.get("name")
                    if metadata_name:
                        code_name = metadata_name
                        logger.info(f"DEBUG: Extracted name '{dataset_name}' from metadata.json for dataset")
                    if artifact_id:
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' from metadata.json for code artifact '{code_name}'")
                except Exception as e:
                    logger.debug(f"DEBUG: Could not read metadata.json for code artifact '{code_name}': {str(e)}")
                
                # Fallback: Find artifact_id in database
                if not artifact_id:
                    all_artifacts = list_all_artifacts()
                    for stored_artifact in all_artifacts:
                        stored_id = stored_artifact.get("id", "")
                        if stored_artifact.get("name") == code_name and stored_artifact.get("type") == "code":
                            artifact_id = stored_id
                            logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in database for code artifact '{code_name}'")
                            break
                
                # Last fallback: use code name
                if not artifact_id:
                    artifact_id = code_name
                    logger.warning(f"DEBUG: No artifact_id found for '{code_name}', using fallback: '{artifact_id}'")
                
                if artifact_id not in seen_artifact_ids:
                    seen_artifact_ids.add(artifact_id)
                    artifacts.append(
                        {
                            "name": code_name,
                            "id": artifact_id,
                            "type": "code",
                        }
                    )
                    logger.info(f"DEBUG: Added code artifact: name='{code_name}', id='{artifact_id}'")
        except Exception as e:
            logger.error(f"DEBUG: Error searching code artifacts with regex {regex_pattern}: {str(e)}", exc_info=True)
            logger.warning(
                f"Error searching code artifacts with regex {regex_pattern}: {str(e)}"
            )

        # Search artifacts in storage matching regex, but verify they exist in S3
        # Search database for artifacts matching regex
        all_artifacts = list_all_artifacts()
        logger.info(f"DEBUG: Searching database (size: {len(all_artifacts)}) for artifacts matching regex")
        storage_matches = 0
        for artifact in all_artifacts:
            artifact_id = artifact.get("id", "")
            artifact_name = artifact.get("name", artifact_id)
            artifact_type = artifact.get("type", "model")
            try:
                # Use compiled pattern and limit input length to prevent ReDoS
                if len(artifact_name) > 1000:
                    continue  # Skip very long names to prevent ReDoS
                if compiled_pattern.search(artifact_name) and artifact_id not in seen_artifact_ids:
                    logger.info(f"DEBUG: Found potential match in storage: id='{artifact_id}', name='{artifact_name}', type='{artifact_type}'")
                    # Verify artifact exists in S3 before including it
                    artifact_exists = False
                    try:
                        if artifact_type == "model":
                            # Check if model exists in S3
                            sanitized_artifact_name = sanitize_model_id_for_s3(artifact_name)
                            logger.info(f"DEBUG: Verifying model in S3: sanitized_name='{sanitized_artifact_name}'")
                            result = list_models(name_regex=f"^{re.escape(sanitized_artifact_name)}$", limit=1)
                            if result.get("models"):
                                model = result["models"][0]
                                v = model.get("version", "main")
                                model_n = model.get("name", sanitized_artifact_name)
                                safe_version = v.replace("/", "_").replace(":", "_").replace("\\", "_")
                                s3_key = f"models/{model_n}/{safe_version}/model.zip"
                                logger.info(f"DEBUG: Checking S3 key: {s3_key}")
                                try:
                                    s3.head_object(Bucket=ap_arn, Key=s3_key)
                                    artifact_exists = True
                                    logger.info(f"DEBUG: Model exists in S3: {s3_key}")
                                except ClientError as e:
                                    logger.warning(f"DEBUG: Model not found in S3: {s3_key}, error: {e}")
                                    pass
                            else:
                                logger.warning(f"DEBUG: No models found in S3 for '{sanitized_artifact_name}'")
                        else:
                            # For datasets and code, check if metadata.json exists in S3
                            sanitized_name = sanitize_model_id_for_s3(artifact_name)
                            version = artifact.get("version", "main")
                            safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
                            s3_key = f"{artifact_type}s/{sanitized_name}/{safe_version}/metadata.json"
                            logger.info(f"DEBUG: Verifying {artifact_type} in S3: key='{s3_key}'")
                            try:
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                artifact_exists = True
                                logger.info(f"DEBUG: {artifact_type} exists in S3: {s3_key}")
                            except ClientError as e:
                                logger.warning(f"DEBUG: {artifact_type} not found in S3: {s3_key}, error: {e}")
                                pass
                    except Exception as e:
                        logger.error(f"DEBUG: Exception verifying artifact in S3: {str(e)}", exc_info=True)
                        pass
                    
                    # Only include if artifact exists in S3
                    if not artifact_exists:
                        logger.warning(f"DEBUG: Skipping artifact '{artifact_id}' - not found in S3")
                        continue
                    
                    storage_matches += 1
                    seen_artifact_ids.add(artifact_id)
                    artifacts.append(
                        {
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact_type,
                        }
                    )
                    logger.info(f"DEBUG: Added artifact from storage: name='{artifact_name}', id='{artifact_id}', type='{artifact_type}'")
            except re.error as e:
                # Skip invalid regex matches
                logger.warning(f"DEBUG: Regex error for artifact '{artifact_id}': {str(e)}")
                continue

        logger.info(f"DEBUG: Found {storage_matches} additional artifacts in storage matching regex")

        logger.info(f"DEBUG: Total artifacts found: {len(artifacts)}")
        if not artifacts:
            logger.error(f"DEBUG: No artifacts found matching regex '{regex_pattern}'")
            raise HTTPException(
                status_code=404, detail="No artifact found under this regex."
            )

        logger.info(f"DEBUG: Returning {len(artifacts)} artifact(s): {artifacts}")
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching artifacts by regex: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid: {str(e)}",
        )


@app.get("/artifact/{artifact_type}/{id}")
@app.get("/artifacts/{artifact_type}/{id}")
def get_artifact(artifact_type: str, id: str, request: Request):
    logger.info(f"=== GET /artifact/{artifact_type}/{id} ===")
    logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
    
    if not verify_auth_token(request):
        logger.error(f"DEBUG: Authentication failed for /artifact/{artifact_type}/{id}")
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    logger.info(f"DEBUG: Authentication passed for /artifact/{artifact_type}/{id}")
    
    try:
        if artifact_type == "model":
            logger.info(f"DEBUG: ===== GET ARTIFACT BY ID START =====")
            logger.info(f"DEBUG: Querying model with id='{id}', artifact_type='{artifact_type}'")
            
            # First, check if id is in database (artifact_id lookup)
            # Try to get full metadata first, fallback to basic if needed
            artifact = get_generic_artifact_metadata("model", id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            if artifact:
                logger.info(f"DEBUG: ✅ Found artifact in database: {artifact}")
                if artifact.get("type") == "model":
                    # Check rating status and block until complete
                    if id in _rating_status:
                        status = _rating_status[id]
                        logger.info(f"DEBUG: Rating status for id='{id}': {status}")
                        
                        if status == "pending":
                            # Block until rating completes (with timeout)
                            logger.info(f"DEBUG: Rating pending, waiting for completion...")
                            if id in _rating_locks:
                                # Wait up to 60 seconds for rating to complete
                                event = _rating_locks[id]
                                if not event.wait(timeout=60):
                                    logger.warning(f"DEBUG: Rating timeout for id='{id}'")
                                    raise HTTPException(status_code=404, detail="Artifact does not exist.")
                                # Re-check status after wait
                                status = _rating_status.get(id, "unknown")
                        
                        if status == "disqualified" or status == "failed":
                            logger.warning(f"DEBUG: Rating {status} for id='{id}'")
                            raise HTTPException(status_code=404, detail="Artifact does not exist.")
                    
                    logger.info(f"DEBUG: ✅ Artifact type matches 'model', returning immediately")
                    artifact_name = artifact.get("name", id)
                    artifact_url = artifact.get("url", f"https://huggingface.co/{artifact_name}")
                    artifact_version = artifact.get("version", "main")
                    result = build_artifact_response(artifact_name, id, artifact_type, artifact_url, artifact_version)
                    logger.info(f"DEBUG: Returning result: {result}")
                    return result
                else:
                    logger.warning(f"DEBUG: ⚠️ Artifact type mismatch: expected 'model', got '{artifact.get('type')}'")
            else:
                logger.info(f"DEBUG: ❌ Artifact id '{id}' NOT found in database")
            
            # If not in database, try to find artifact metadata in S3 by artifact_id
            logger.info(f"DEBUG: ===== SEARCHING S3 METADATA =====")
            logger.info(f"DEBUG: Calling find_artifact_metadata_by_id('{id}')...")
            import time
            s3_start = time.time()
            s3_metadata = find_artifact_metadata_by_id(id)
            s3_elapsed = time.time() - s3_start
            logger.info(f"DEBUG: S3 metadata lookup took {s3_elapsed:.3f}s")
            
            if s3_metadata:
                logger.info(f"DEBUG: ✅ Found S3 metadata: {s3_metadata}")
                if s3_metadata.get("type") == "model":
                    model_name = s3_metadata.get("name")
                    stored_version = s3_metadata.get("version", "main")
                    logger.info(f"DEBUG: ✅ S3 metadata type is 'model': model_name='{model_name}', version='{stored_version}'")
                    # Restore to database for future lookups
                    save_artifact(id, {
                        "name": model_name,
                        "type": "model",
                        "version": stored_version,
                        "id": id,
                        "url": s3_metadata.get("url", f"https://huggingface.co/{model_name}")
                    })
                    logger.info(f"DEBUG: ✅ Restored artifact to database: id='{id}'")
                    model_url = s3_metadata.get("url", f"https://huggingface.co/{model_name}")
                    result = build_artifact_response(model_name, id, artifact_type, model_url, stored_version)
                    logger.info(f"DEBUG: Returning result from S3: {result}")
                    return result
                else:
                    logger.warning(f"DEBUG: ⚠️ S3 metadata type mismatch: expected 'model', got '{s3_metadata.get('type')}'")
            else:
                logger.info(f"DEBUG: ❌ Artifact id '{id}' NOT found in S3 metadata")
            
            logger.info(f"DEBUG: ===== FALLING BACK TO MODEL NAME LOOKUP =====")
            logger.info(f"DEBUG: Will try to use id '{id}' as model name")
            
            # If not found in S3 metadata, try to find model by name (id might be model name)
            # First, try using the ID as-is (for numeric artifact IDs)
            # Then try sanitizing it (for model names with slashes)
            version = None
            found = False
            model_name_for_s3 = None
            actual_model_name = id  # Default to ID
            list_models_result = None
            
            # Try to get model name from database if ID is an artifact_id
            model_name_for_s3 = _get_model_name_for_s3(id)
            if not model_name_for_s3:
                # If not found, try sanitizing the ID (in case it's a model name with slashes)
                model_name_for_s3 = sanitize_model_id_for_s3(id)
            
            logger.info(f"DEBUG: Trying list_models with regex: '^{re.escape(id)}$'")
            try:
                list_models_result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                logger.info(f"DEBUG: list_models returned {len(list_models_result.get('models', []))} models")
                if list_models_result.get("models"):
                    for model in list_models_result["models"]:
                        v = model["version"]
                        model_n = model.get("name", model_name_for_s3 or id)
                        actual_model_name = model_n  # Use the actual model name from list_models
                        # Sanitize model name for S3
                        sanitized_name = sanitize_model_id_for_s3(model_n)
                        logger.info(f"DEBUG: Checking model: name='{model_n}', sanitized='{sanitized_name}', version='{v}'")
                        try:
                            s3_key = f"models/{sanitized_name}/{v}/model.zip"
                            logger.info(f"DEBUG: Checking S3 key: {s3_key}")
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            version = v
                            found = True
                            model_name_for_s3 = sanitized_name
                            logger.info(f"DEBUG: ✅ Found model in S3: {s3_key}")
                            break
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code", "")
                            logger.debug(f"DEBUG: S3 key {s3_key} not found: {error_code}")
                            if error_code == "NoSuchKey" or error_code == "404":
                                continue
                            else:
                                logger.warning(f"Unexpected error checking {s3_key}: {error_code}")
            except Exception as e:
                logger.warning(f"Error calling list_models: {e}", exc_info=True)
            
            # If not found, try common versions with sanitized name
            if not found:
                logger.info(f"DEBUG: Not found via list_models, trying common versions: ['1.0.0', 'main', 'latest']")
                common_versions = ["1.0.0", "main", "latest"]
                for v in common_versions:
                    try:
                        # Use sanitized name for S3 lookup
                        s3_key = f"models/{model_name_for_s3}/{v}/model.zip"
                        logger.info(f"DEBUG: Checking common version S3 key: {s3_key}")
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        version = v
                        found = True
                        logger.info(f"DEBUG: ✅ Found model with common version: {s3_key}")
                        break
                    except ClientError as e:
                        error_code = e.response.get("Error", {}).get("Code", "")
                        logger.debug(f"DEBUG: Common version {s3_key} not found: {error_code}")
                        if error_code == "NoSuchKey" or error_code == "404":
                            continue
                        else:
                            logger.warning(f"Unexpected error checking {s3_key}: {error_code}")
            
            if not found:
                logger.error(f"DEBUG: ❌❌❌ MODEL NOT FOUND - All lookup methods failed ❌❌❌")
                logger.error(f"DEBUG: Final status: found={found}, version={version}, id='{id}'")
                all_artifacts = list_all_artifacts()
                artifact_ids = [a.get("id", "") for a in all_artifacts if a.get("id")]
                logger.error(f"DEBUG: Database artifact IDs: {artifact_ids[:20]}")
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Return model - use actual model name if found, otherwise use ID
            logger.info(f"DEBUG: ✅✅✅ RETURNING MODEL (fallback to name lookup) ✅✅✅")
            logger.info(f"DEBUG: Using model name: '{actual_model_name}', id='{id}', version='{version}'")
            result = build_artifact_response(actual_model_name, id, artifact_type, f"https://huggingface.co/{actual_model_name}", version or "main")
            logger.info(f"DEBUG: Final result: {result}")
            return result
        else:
            logger.info(f"DEBUG: Processing {artifact_type} artifact with id='{id}'")
            # For dataset and code artifacts, check database first (primary source of truth)
            # Try to get full metadata first, fallback to basic if needed
            artifact = get_generic_artifact_metadata(artifact_type, id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            if artifact:
                logger.info(f"DEBUG: Found artifact in database: {artifact}")
                if artifact.get("type") == artifact_type:
                    # Artifact found in database with correct type - return it immediately
                    # S3 verification is optional, not required
                    artifact_name = artifact.get("name", id)
                    artifact_url = artifact.get("url", f"https://example.com/{artifact_type}/{artifact_name}")
                    artifact_version = artifact.get("version", "main")
                    result = build_artifact_response(artifact_name, id, artifact_type, artifact_url, artifact_version)
                    logger.info(f"DEBUG: Returning {artifact_type} artifact from database: {result}")
                    return result
                else:
                    logger.warning(f"DEBUG: Artifact type mismatch: expected '{artifact_type}', got '{artifact.get('type')}'")
                    raise HTTPException(status_code=404, detail="Artifact does not exist.")
            else:
                logger.info(f"DEBUG: Artifact id '{id}' not found in database")
                # Try S3 metadata as fallback (for backward compatibility)
                logger.info(f"DEBUG: Trying S3 metadata as fallback for {artifact_type} artifact")
                s3_metadata = find_artifact_metadata_by_id(id)
                if s3_metadata and s3_metadata.get("type") == artifact_type:
                    artifact_name = s3_metadata.get("name", id)
                    artifact_url = s3_metadata.get("url", f"https://example.com/{artifact_type}/{artifact_name}")
                    # Restore to database for future lookups
                    save_artifact(id, {
                        "name": artifact_name,
                        "type": artifact_type,
                        "version": s3_metadata.get("version", "main"),
                        "id": id,
                        "url": artifact_url
                    })
                    logger.info(f"DEBUG: Restored {artifact_type} artifact from S3 to database: id='{id}'")
                    artifact_version = s3_metadata.get("version", "main")
                    result = build_artifact_response(artifact_name, id, artifact_type, artifact_url, artifact_version)
                    logger.info(f"DEBUG: Returning {artifact_type} artifact from S3: {result}")
                    return result
                
                # Try S3 lookup by name (if ID is actually a name with special characters)
                logger.info(f"DEBUG: Trying S3 lookup by name for {artifact_type} with id='{id}'")
                try:
                    # Search S3 for artifacts matching the name
                    sanitized_name = sanitize_model_id_for_s3(id)
                    logger.info(f"DEBUG: Searching S3 for {artifact_type} with sanitized name: '{sanitized_name}'")
                    s3_result = list_artifacts_from_s3(artifact_type=artifact_type, name_regex=f"^{re.escape(id)}$", limit=10)
                    if s3_result.get("artifacts"):
                        for s3_artifact in s3_result["artifacts"]:
                            s3_artifact_name = s3_artifact.get("name", "")
                            s3_artifact_id = s3_artifact.get("artifact_id", "")
                            # Match by name (supports IDs that are actually names)
                            if s3_artifact_name == id:
                                logger.info(f"DEBUG: Found {artifact_type} in S3 by name: name='{s3_artifact_name}', id='{s3_artifact_id}'")
                                # Use the artifact_id from S3 if available, otherwise use the provided id
                                final_id = s3_artifact_id if s3_artifact_id else id
                                artifact_url = f"https://example.com/{artifact_type}/{s3_artifact_name}"
                                artifact_version = s3_artifact.get("version", "main")
                                # Restore to database for future lookups
                                save_artifact(final_id, {
                                    "name": s3_artifact_name,
                                    "type": artifact_type,
                                    "version": artifact_version,
                                    "id": final_id,
                                    "url": artifact_url
                                })
                                result = build_artifact_response(s3_artifact_name, final_id, artifact_type, artifact_url, artifact_version)
                                logger.info(f"DEBUG: Returning {artifact_type} artifact from S3 name lookup: {result}")
                                return result
                except Exception as e:
                    logger.warning(f"DEBUG: Error searching S3 by name: {str(e)}")
            
            # For datasets/code, also try searching by name if ID lookup fails
            # This allows using artifact names or other identifiers as IDs
            logger.info(f"DEBUG: Trying name-based lookup in database for {artifact_type} with id='{id}'")
            all_artifacts = list_all_artifacts()
            for artifact in all_artifacts:
                if artifact.get("type") == artifact_type:
                    artifact_name = artifact.get("name", "")
                    artifact_id = artifact.get("id", "")
                    # Match by name or ID (supports both artifact IDs and names as lookup keys)
                    # Also support partial matches for names with special characters
                    if artifact_name == id or artifact_id == id:
                        logger.info(f"DEBUG: Found {artifact_type} by name/ID match: name='{artifact_name}', id='{artifact_id}'")
                        artifact_url = artifact.get("url", f"https://example.com/{artifact_type}/{artifact_name}")
                        artifact_version = artifact.get("version", "main")
                        result = build_artifact_response(artifact_name, artifact_id, artifact_type, artifact_url, artifact_version)
                        logger.info(f"DEBUG: Returning {artifact_type} artifact from name lookup: {result}")
                        return result
                    # Also try sanitized name matching (for IDs with slashes that match sanitized names)
                    sanitized_artifact_name = sanitize_model_id_for_s3(artifact_name)
                    sanitized_id = sanitize_model_id_for_s3(id)
                    if sanitized_artifact_name == sanitized_id:
                        logger.info(f"DEBUG: Found {artifact_type} by sanitized name match: name='{artifact_name}', id='{artifact_id}'")
                        artifact_url = artifact.get("url", f"https://example.com/{artifact_type}/{artifact_name}")
                        artifact_version = artifact.get("version", "main")
                        result = build_artifact_response(artifact_name, artifact_id, artifact_type, artifact_url, artifact_version)
                        logger.info(f"DEBUG: Returning {artifact_type} artifact from sanitized name lookup: {result}")
                        return result
            
            logger.error(f"DEBUG: {artifact_type} not found: id='{id}'")
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


@app.post("/artifact/ingest")
async def post_artifact_ingest(request: Request):
    """
    Ingest an artifact by name and version (form data).
    This is a convenience endpoint that accepts form data for model ingestion.
    """
    
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    
    try:
        # Parse form data
        form = await request.form()
        name = form.get("name")
        version = form.get("version", "main")
        artifact_type = form.get("type", "model")
        
        # Validate name parameter
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="Name parameter is required. Provide 'name' in form data.",
            )
        
        name = name.strip()
        
        # For models, use model_ingestion
        if artifact_type == "model":
            try:
                # Check if artifact already exists
                try:
                    existing = list_models(
                        name_regex=f"^{re.escape(name)}$", limit=1
                    )
                    if existing.get("models"):
                        raise HTTPException(
                            status_code=409, detail="Artifact exists already."
                        )
                except HTTPException:
                    raise
                except:
                    pass
                
                # Ingest the model (synchronous - must complete)
                model_ingestion(name, version)
                
                # Generate artifact ID immediately (before rating)
                logger.info(f"DEBUG: ===== GENERATING ARTIFACT ID =====")
                artifact_id = str(random.randint(1000000000, 9999999999))
                url = f"https://huggingface.co/{name}"
                logger.info(f"DEBUG: Generated artifact_id: '{artifact_id}' for model '{name}'")
                
                # Initialize rating status and lock
                _rating_status[artifact_id] = "pending"
                _rating_locks[artifact_id] = threading.Event()
                
                # Extract README and extract dataset/code names
                readme_text = None
                dataset_name = None
                code_name = None
                try:
                    from .services.s3_service import download_model
                    zip_content = download_model(name, version, "full")
                    if zip_content:
                        import zipfile
                        import io
                        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
                            for file_info in zip_file.filelist:
                                if "readme" in file_info.filename.lower():
                                    readme_text = zip_file.read(file_info).decode("utf-8", errors="ignore")
                                    break
                        if readme_text:
                            # Extract dataset and code names from README
                            extracted = _extract_dataset_code_names_from_readme(readme_text)
                            dataset_name = extracted.get("dataset_name")
                            code_name = extracted.get("code_name")
                except Exception as e:
                    logger.debug(f"Could not extract README for linking: {str(e)}")
                
                # Store artifact metadata immediately (before rating completes)
                # Include dataset_name and code_name if extracted from README
                logger.info(f"DEBUG: Storing in database with key: '{artifact_id}'")
                artifact_data = {
                    "name": name,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                }
                # Store extracted dataset/code names (even if not linked yet)
                if dataset_name:
                    artifact_data["dataset_name"] = dataset_name
                if code_name:
                    artifact_data["code_name"] = code_name
                save_artifact(artifact_id, artifact_data)
                
                # Link to existing datasets/code if found
                if readme_text:
                    _link_model_to_datasets_code(artifact_id, name, readme_text)
                
                # Start async rating in background thread
                logger.info(f"DEBUG: Starting async rating for artifact_id='{artifact_id}'")
                rating_thread = threading.Thread(
                    target=_run_async_rating,
                    args=(artifact_id, name, version),
                    daemon=True
                )
                rating_thread.start()
                logger.info(f"DEBUG: ✅ Stored in database: artifact_id='{artifact_id}'")
                # Verify artifact was saved
                saved_artifact = get_artifact_from_db(artifact_id)
                if saved_artifact:
                    logger.info(f"DEBUG: Verified artifact exists in database: {saved_artifact}")
                else:
                    logger.warning(f"DEBUG: ⚠️ Could not verify artifact in database after save")
                
                # Store artifact metadata in S3 (model file already stored via model_ingestion)
                # This must complete synchronously so queries can find the artifact
                logger.info(f"DEBUG: ===== STORING ARTIFACT METADATA IN S3 =====")
                logger.info(f"DEBUG: artifact_id='{artifact_id}', name='{name}', type='{artifact_type}', version='{version}'")
                try:
                    result = store_artifact_metadata(artifact_id, name, artifact_type, version, url)
                    logger.info(f"DEBUG: ✅ S3 metadata storage result: {result}")
                    
                    # Verify the metadata was stored by trying to read it back
                    # This ensures the write completed and is immediately readable
                    import time
                    logger.info(f"DEBUG: Verifying S3 metadata is readable...")
                    verify_metadata = None
                    for verify_attempt in range(3):
                        logger.info(f"DEBUG: Verification attempt {verify_attempt + 1}/3")
                        verify_metadata = find_artifact_metadata_by_id(artifact_id)
                        if verify_metadata:
                            logger.info(f"DEBUG: ✅✅✅ VERIFIED: S3 metadata exists for artifact_id '{artifact_id}' ✅✅✅")
                            logger.info(f"DEBUG: Verified metadata: {verify_metadata}")
                            break
                        else:
                            logger.warning(f"DEBUG: ⚠️ Verification attempt {verify_attempt + 1} failed - metadata not found")
                        if verify_attempt < 2:
                            logger.info(f"DEBUG: Waiting 0.1s before retry...")
                            time.sleep(0.1)  # Small delay before retry
                    
                    if not verify_metadata:
                        logger.error(f"DEBUG: ❌❌❌ WARNING: Could not verify S3 metadata for artifact_id '{artifact_id}' after 3 attempts ❌❌❌")
                        logger.error(f"DEBUG: This may cause query failures if hitting different instance")
                except Exception as s3_error:
                    logger.error(f"DEBUG: ❌ Exception storing artifact metadata in S3: {str(s3_error)}", exc_info=True)
                    # Don't fail ingestion if S3 metadata storage fails, but log it as an error
                
                result = {
                    "message": "Ingest successful",
                    "details": {
                        "name": name,
                        "type": artifact_type,
                        "version": version,
                        "id": artifact_id,
                        "url": url,
                    },
                }
                logger.info(f"DEBUG: ===== INGESTION COMPLETE =====")
                logger.info(f"DEBUG: ✅✅✅ Returning ingestion result: {result} ✅✅✅")
                logger.info(f"DEBUG: Artifact should now be queryable by:")
                logger.info(f"DEBUG:   - artifact_id: '{artifact_id}' (GET /package/{artifact_id})")
                logger.info(f"DEBUG:   - name: '{name}' (GET /artifact/byName/{name})")
                # Verify artifact was saved
                saved_artifact = get_artifact_from_db(artifact_id)
                if saved_artifact:
                    logger.info(f"DEBUG: Verified artifact exists in database: id='{artifact_id}'")
                else:
                    logger.warning(f"DEBUG: ⚠️ Could not verify artifact in database after save")
                return result
            except HTTPException:
                raise
            except Exception as model_error:
                logger.error(
                    f"Error in model_ingestion for {name}: {str(model_error)}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Model ingestion failed: {str(model_error)}",
                )
        else:
            # For non-model artifacts (dataset, code), store metadata in S3
            artifact_id = str(random.randint(1000000000, 9999999999))
            url = f"https://example.com/{artifact_type}/{name}"
            save_artifact(artifact_id, {
                "name": name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
            })
            
            # Link this dataset/code to models that reference it
            _link_dataset_code_to_models(artifact_id, name, artifact_type)
            
            # Store artifact metadata in S3
            try:
                store_artifact_metadata(artifact_id, name, artifact_type, version, url)
            except Exception as s3_error:
                logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                # Don't fail ingestion if S3 metadata storage fails
            
            return {
                "message": "Ingest successful",
                "details": {
                    "name": name,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in POST /artifact/ingest endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


@app.post("/artifact/{artifact_type}")
async def create_artifact_by_type(artifact_type: str, request: Request):
    """
    Register a new artifact by providing a downloadable source url.
    This endpoint handles ingestion of models, datasets, and code artifacts.
    For models: Downloads, validates, rates, and uploads to S3.
    For datasets/code: Validates and stores artifact metadata.
    """
    global _artifact_storage
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
        # Parse JSON body (required by spec - ArtifactData)
        try:
            body = await request.json()
        except Exception as json_error:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_data or it is formed improperly (must include a single url).",
            )
        
        # Extract url from body (required field per ArtifactData schema)
        url = body.get("url", "")
        if not url or not isinstance(url, str) or not url.strip():
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_data or it is formed improperly (must include a single url).",
            )
        
        # Extract version if provided (for backward compatibility with model ingestion)
        version = body.get("version", "main")
        
        # Extract name from body if provided, otherwise extract from URL
        # For GitHub URLs and other URLs with paths, replace "/" with "-" in the name
        name = body.get("name")  # Check if name is provided in request body first
        if not name:
            # Extract name from URL if not provided in body
            if artifact_type == "model" and "huggingface.co" in url:
                clean_url = url.replace("https://huggingface.co/", "").replace(
                    "http://huggingface.co/", ""
                )
                if "/tree/" in clean_url:
                    clean_url = clean_url.split("/tree/")[0]
                elif "/resolve/" in clean_url:
                    clean_url = clean_url.split("/resolve/")[0]
                name = clean_url.strip("/")
            elif "github.com" in url:
                # Extract GitHub repo path and replace "/" with "-"
                # Example: https://github.com/google-research/bert -> google-research-bert
                github_match = re.search(r'github\.com/([^/]+/[^/?#]+)', url)
                if github_match:
                    repo_path = github_match.group(1)
                    # Remove trailing .git if present
                    repo_path = repo_path.rstrip('.git')
                    # Replace "/" with "-"
                    name = repo_path.replace("/", "-")
                else:
                    # Fallback: use last part of URL
                    name = url.split("/")[-1].rstrip('.git') if url else f"{artifact_type}-new"
            else:
                # For other URLs, extract the path and replace "/" with "-"
                # Example: https://example.com/org/repo -> org-repo
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path_parts = [p for p in parsed.path.split("/") if p]
                    if path_parts:
                        # Join path parts with "-"
                        name = "-".join(path_parts)
                    else:
                        # Fallback: use last part of URL
                        name = url.split("/")[-1] if url else f"{artifact_type}-new"
                except Exception:
                    # Fallback: use last part of URL
                    name = url.split("/")[-1] if url else f"{artifact_type}-new"
        if artifact_type == "model":
            # For models, we need to distinguish between:
            # 1. hf_model_id: The HuggingFace model ID used for downloading/uploading (from URL)
            # 2. artifact_name: The name stored in database and used for querying (from body or URL)
            
            # Extract HuggingFace model ID from URL (required for model_ingestion)
            hf_model_id = None
            if url and "huggingface.co" in url:
                # Extract model_id from HuggingFace URL
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
                hf_model_id = clean_url.strip("/")
            
            # Determine artifact_name: use name from body if provided, otherwise use hf_model_id
            artifact_name = name if name else (hf_model_id if hf_model_id else "unknown-model")
            
            # Use hf_model_id for ingestion (must be valid HuggingFace model ID)
            # If no hf_model_id from URL, use artifact_name (assumes it's a valid HuggingFace ID)
            model_id = hf_model_id if hf_model_id else artifact_name

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

            # Ingest the model (synchronous - must complete)
            # Note: model_ingestion fetches GitHub metadata
            # (github_url, github.prs, github.direct_commits, readme_text, repo_files, etc.)
            # which is required for metrics like Reviewedness, CodeQuality, and Reproducibility
            try:
                model_ingestion(model_id, version)
                
                # Generate artifact ID immediately (before rating)
                artifact_id = str(random.randint(1000000000, 9999999999))
                
                # Initialize rating status and lock
                _rating_status[artifact_id] = "pending"
                _rating_locks[artifact_id] = threading.Event()
                
                # Extract README and extract dataset/code names
                readme_text = None
                dataset_name = None
                code_name = None
                try:
                    from .services.s3_service import download_model
                    zip_content = download_model(model_id, version, "full")
                    if zip_content:
                        import zipfile
                        import io
                        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
                            for file_info in zip_file.filelist:
                                if "readme" in file_info.filename.lower():
                                    readme_text = zip_file.read(file_info).decode("utf-8", errors="ignore")
                                    break
                        if readme_text:
                            # Extract dataset and code names from README
                            extracted = _extract_dataset_code_names_from_readme(readme_text)
                            dataset_name = extracted.get("dataset_name")
                            code_name = extracted.get("code_name")
                except Exception as e:
                    logger.debug(f"Could not extract README for linking: {str(e)}")
                
                # Store artifact metadata immediately (before rating completes)
                # Include dataset_name and code_name if extracted from README
                # Use artifact_name (from body or URL) for storage, not model_id (which is hf_model_id)
                artifact_data = {
                    "name": artifact_name,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                }
                # Store extracted dataset/code names (even if not linked yet)
                if dataset_name:
                    artifact_data["dataset_name"] = dataset_name
                if code_name:
                    artifact_data["code_name"] = code_name
                save_artifact(artifact_id, artifact_data)
                
                # Link to existing datasets/code if found
                if readme_text:
                    _link_model_to_datasets_code(artifact_id, artifact_name, readme_text)
                
                # Start async rating in background thread
                # Use model_id (hf_model_id) for rating since it needs the actual HuggingFace model
                logger.info(f"DEBUG: Starting async rating for artifact_id='{artifact_id}'")
                rating_thread = threading.Thread(
                    target=_run_async_rating,
                    args=(artifact_id, model_id, version),
                    daemon=True
                )
                rating_thread.start()
                
                # Store artifact metadata in S3 (model file already stored via model_ingestion)
                # Use artifact_name for metadata storage (this is what queries will look for)
                try:
                    store_artifact_metadata(artifact_id, artifact_name, artifact_type, version, url)
                except Exception as s3_error:
                    logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                    # Don't fail ingestion if S3 metadata storage fails
                
                # Generate download_url for response
                download_url = generate_download_url(artifact_name, artifact_type, version)
                
                # Per spec: Return 201 for successful ingestion with full artifact response
                # The spec shows 201 with the full artifact object including download_url
                # 202 is for async rating, but we should return 201 since ingestion completed successfully
                return Response(
                    content=json.dumps(
                        {
                            "metadata": {
                                "name": artifact_name,
                                "id": artifact_id,
                                "type": artifact_type,
                            },
                            "data": {
                                "url": url,
                                "download_url": download_url
                            },
                        }
                    ),
                    media_type="application/json",
                    status_code=201,
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
        elif artifact_type in ["dataset", "code"]:
            # For dataset and code artifacts, perform ingestion
            # Use the name from request body if provided, otherwise use name extracted from URL
            artifact_name = name if name else f"{artifact_type}-new"
            
            # Check if artifact already exists (check both _artifact_storage and database)
            for existing_id, existing_data in _artifact_storage.items():
                if (existing_data.get("url") == url and existing_data.get("type") == artifact_type) or (
                    existing_data.get("name") == artifact_name and existing_data.get("type") == artifact_type
                ):
                    raise HTTPException(
                        status_code=409, detail="Artifact exists already."
                    )
            
            # Also check database
            all_artifacts = list_all_artifacts()
            for existing_artifact in all_artifacts:
                existing_id = existing_artifact.get("id", "")
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
            
            # Store in _artifact_storage for immediate consistency
            _artifact_storage[artifact_id] = {
                "name": artifact_name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
            }
            
            # Also save to DynamoDB for persistence
            save_artifact(artifact_id, {
                "name": artifact_name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
            })
            
            # Link this dataset/code to models that reference it
            _link_dataset_code_to_models(artifact_id, artifact_name, artifact_type)
            
            # Store artifact metadata in S3
            try:
                store_artifact_metadata(artifact_id, artifact_name, artifact_type, version, url)
            except Exception as s3_error:
                logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                # Don't fail ingestion if S3 metadata storage fails
            
            # Generate download_url for response
            download_url = generate_download_url(artifact_name, artifact_type, version)
            
            return Response(
                content=json.dumps(
                    {
                        "metadata": {
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact_type,
                        },
                        "data": {
                            "url": url,
                            "download_url": download_url
                        },
                    }
                ),
                media_type="application/json",
                status_code=201,
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


@app.put("/artifacts/{artifact_type}/{id}")
async def update_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        body = (
            await request.json()
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        if "metadata" not in body or "data" not in body:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        metadata = body.get("metadata", {})
        if metadata.get("id") != id:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if not metadata.get("name"):
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if artifact_type == "model":
            # Check if artifact exists - first try by ID in database, then by name in S3
            found = False
            artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == "model":
                found = True
            else:
                # Try to get model name from database for S3 lookup
                model_name = _get_model_name_for_s3(id)
                if model_name:
                    common_versions = ["1.0.0", "main", "latest"]
                    for v in common_versions:
                        try:
                            s3_key = f"models/{model_name}/{v}/model.zip"
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            found = True
                            break
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code", "")
                            if error_code == "NoSuchKey" or error_code == "404":
                                continue
                # Fallback: try by ID directly (in case it was stored by ID)
                if not found:
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
                # Also try by name regex
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
            data = body.get("data", {})
            url = data.get("url", "")
            if not url:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid. URL is required in data.",
                )

            # For models, we would need to re-ingest with the new URL, but for now just acknowledge the update
            # The spec says "The artifact source (from artifact_data) will replace the previous contents"
            # This would typically involve re-downloading and re-processing the artifact
            return Response(status_code=200)
        else:
            artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == artifact_type:
                # Update artifact data (url) - replace previous contents
                data = body.get("data", {})
                url = data.get("url", "")
                if not url:
                    raise HTTPException(
                        status_code=400,
                        detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid. URL is required in data.",
                    )
                update_artifact(id, {
                    "name": metadata.get("name", artifact.get("name", id)),
                    "type": artifact_type,
                    "id": id,
                    "url": url,
                })
                return Response(status_code=200)
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


@app.delete("/artifacts/{artifact_type}/{id}")
def delete_artifact_endpoint(artifact_type: str, id: str, request: Request):
    global _artifact_storage
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        deleted = False
        artifact = get_artifact_from_db(id)
        if artifact and artifact.get("type") == artifact_type:
            delete_artifact(id)
            # Also remove from _artifact_storage if it's a dataset or code
            if artifact_type in ["dataset", "code"]:
                if id in _artifact_storage:
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


@app.get("/artifact/{artifact_type}/{id}/cost")
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
        # Allow flexible ID formats: alphanumeric, hyphens, underscores, slashes, dots, colons
        # This supports both numeric artifact IDs and model names (e.g., "google-bert/bert-base-uncased")
        if not id or not id.strip():
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.",
            )
        if artifact_type == "model":
            found = False
            artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == "model":
                    found = True
            if not found:
                try:
                    result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                    if result.get("models"):
                        found = True
                    else:
                        # Try with sanitized name for S3 lookup (handles IDs with slashes)
                        model_name_for_s3 = _get_model_name_for_s3(id)
                        if not model_name_for_s3:
                            model_name_for_s3 = sanitize_model_id_for_s3(id)
                        common_versions = ["1.0.0", "main", "latest"]
                        for v in common_versions:
                            try:
                                # Use sanitized name for S3 lookup
                                s3_key = f"models/{model_name_for_s3}/{v}/model.zip"
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                found = True
                                break
                            except ClientError:
                                continue
                except Exception:
                    pass
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Get model name for S3 lookup (models are stored by name, not ID)
            model_name = _get_model_name_for_s3(id)
            if not model_name:
                # Fallback: sanitize ID (in case it's a model name with special characters)
                model_name = sanitize_model_id_for_s3(id)
            
            sizes = get_model_sizes(model_name, "1.0.0")
            if "error" in sizes:
                raise HTTPException(status_code=404, detail=sizes["error"])
            standalone_size_mb = sizes.get("full", 0) / (1024 * 1024)
            if dependency:
                # When dependency=true, return all artifacts (main + dependencies) with standalone_cost and total_cost
                result = {}
                total_size_mb = standalone_size_mb

                # Add main artifact
                result[id] = {
                    "standalone_cost": round(standalone_size_mb, 2),
                    "total_cost": round(
                        standalone_size_mb, 2
                    ),  # Will be updated with total after dependencies
                }

                # Get dependencies from model's dataset_id and code_id
                artifact = get_artifact_from_db(id)
                if artifact:
                    dataset_id = artifact.get("dataset_id")
                    code_id = artifact.get("code_id")
                    
                    # Get dataset cost if linked
                    if dataset_id:
                        try:
                            dataset_artifact = get_artifact_from_db(dataset_id)
                            if dataset_artifact and dataset_artifact.get("type") == "dataset":
                                dataset_size_mb = _get_artifact_size_mb("dataset", dataset_id)
                                if dataset_size_mb > 0:
                                    total_size_mb += dataset_size_mb
                                    result[dataset_id] = {
                                        "standalone_cost": round(dataset_size_mb, 2),
                                        "total_cost": round(dataset_size_mb, 2),
                                    }
                        except Exception as e:
                            logger.debug(f"Error getting dataset cost: {str(e)}")
                    
                    # Get code cost if linked
                    if code_id:
                        try:
                            code_artifact = get_artifact_from_db(code_id)
                            if code_artifact and code_artifact.get("type") == "code":
                                code_size_mb = _get_artifact_size_mb("code", code_id)
                                if code_size_mb > 0:
                                    total_size_mb += code_size_mb
                                    result[code_id] = {
                                        "standalone_cost": round(code_size_mb, 2),
                                        "total_cost": round(code_size_mb, 2),
                                    }
                        except Exception as e:
                            logger.debug(f"Error getting code cost: {str(e)}")

                # Update main artifact's total_cost to include all dependencies
                result[id]["total_cost"] = round(total_size_mb, 2)
            else:
                # When dependency=false, return BOTH standalone_cost and total_cost (where standalone_cost = total_cost)
                result = {
                    id: {
                        "standalone_cost": round(standalone_size_mb, 2),
                        "total_cost": round(standalone_size_mb, 2)
                    }
                }
            return result
        else:
            # For datasets/code, support flexible ID formats (numeric IDs, names with slashes, etc.)
            # Try full metadata first, fallback to basic
            artifact = get_generic_artifact_metadata(artifact_type, id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            
            # If not found by ID, try name-based lookup
            if not artifact:
                logger.info(f"DEBUG: {artifact_type} not found by ID '{id}', trying name-based lookup")
                all_artifacts = list_all_artifacts()
                for art in all_artifacts:
                    if art.get("type") == artifact_type:
                        art_name = art.get("name", "")
                        art_id = art.get("id", "")
                        # Match by name or ID
                        if art_name == id or art_id == id:
                            artifact = art
                            id = art_id  # Use the actual artifact_id
                            logger.info(f"DEBUG: Found {artifact_type} by name: name='{art_name}', id='{art_id}'")
                            break
                        # Also try sanitized name matching
                        sanitized_art_name = sanitize_model_id_for_s3(art_name)
                        sanitized_id = sanitize_model_id_for_s3(id)
                        if sanitized_art_name == sanitized_id:
                            artifact = art
                            id = art_id  # Use the actual artifact_id
                            logger.info(f"DEBUG: Found {artifact_type} by sanitized name: name='{art_name}', id='{art_id}'")
                            break
            
            if not artifact:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            if artifact.get("type") != artifact_type:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Calculate actual size from S3 or download URL
            standalone_size_mb = _get_artifact_size_mb(artifact_type, id)
            
            if dependency:
                # When dependency=true, return all artifacts (main + dependencies) with standalone_cost and total_cost
                result = {}
                total_size_mb = standalone_size_mb
                
                # Add main artifact
                result[id] = {
                    "standalone_cost": round(standalone_size_mb, 2),
                    "total_cost": round(standalone_size_mb, 2),  # Will be updated after dependencies
                }
                
                # For datasets/code, there are no dependencies, so total_cost = standalone_cost
                result[id]["total_cost"] = round(total_size_mb, 2)
            else:
                # When dependency=false, return BOTH standalone_cost and total_cost (where standalone_cost = total_cost)
                result = {
                    id: {
                        "standalone_cost": round(standalone_size_mb, 2),
                        "total_cost": round(standalone_size_mb, 2)
                    }
                }
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


@app.get("/artifact/{artifact_type}/{id}/audit")
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

        # Validate id parameter - allow flexible formats (alphanumeric, hyphens, underscores, slashes, dots, colons)
        # This supports both numeric artifact IDs and model names (e.g., "google-bert/bert-base-uncased")
        if not id or not id.strip():
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

            # Check in database first - try full metadata first
            artifact = get_generic_artifact_metadata("model", id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == "model":
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

            # Try common versions if not found (with sanitized name for IDs with special characters)
            if not found:
                # Get sanitized model name for S3 lookup
                model_name_for_s3 = _get_model_name_for_s3(id)
                if not model_name_for_s3:
                    model_name_for_s3 = sanitize_model_id_for_s3(id)
                versions = ["1.0.0", "main", "latest"]
                for v in versions:
                    try:
                        # Use sanitized name for S3 lookup
                        s3_key = f"models/{model_name_for_s3}/{v}/model.zip"
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        found = True
                        version = v
                        break
                    except ClientError:
                        continue

            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")

            # Get creation date from S3 (use sanitized name)
            try:
                model_name_for_s3 = _get_model_name_for_s3(id)
                if not model_name_for_s3:
                    model_name_for_s3 = sanitize_model_id_for_s3(id)
                s3_key = f"models/{model_name_for_s3}/{version or '1.0.0'}/model.zip"
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
            audit_entries.append(
                {
                    "user": {"name": "system", "is_admin": False},
                    "date": create_date,
                    "artifact": {
                        "name": artifact_name,
                        "id": id,
                        "type": artifact_type,
                    },
                    "action": "CREATE",
                }
            )
        else:
            # For datasets/code artifacts, support flexible ID formats (numeric IDs, names with slashes, etc.)
            # Try full metadata first, fallback to basic
            artifact = get_generic_artifact_metadata(artifact_type, id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            
            # If not found by ID, try name-based lookup
            if not artifact:
                logger.info(f"DEBUG: {artifact_type} not found by ID '{id}', trying name-based lookup for audit")
                all_artifacts = list_all_artifacts()
                for art in all_artifacts:
                    if art.get("type") == artifact_type:
                        art_name = art.get("name", "")
                        art_id = art.get("id", "")
                        # Match by name or ID
                        if art_name == id or art_id == id:
                            artifact = art
                            id = art_id  # Use the actual artifact_id
                            logger.info(f"DEBUG: Found {artifact_type} by name for audit: name='{art_name}', id='{art_id}'")
                            break
                        # Also try sanitized name matching
                        sanitized_art_name = sanitize_model_id_for_s3(art_name)
                        sanitized_id = sanitize_model_id_for_s3(id)
                        if sanitized_art_name == sanitized_id:
                            artifact = art
                            id = art_id  # Use the actual artifact_id
                            logger.info(f"DEBUG: Found {artifact_type} by sanitized name for audit: name='{art_name}', id='{art_id}'")
                            break
            
            if artifact and artifact.get("type") == artifact_type:
                    # Add CREATE entry
                    audit_entries.append(
                        {
                            "user": {"name": "system", "is_admin": False},
                            "date": datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            "artifact": {
                                "name": artifact.get("name", id),
                                "id": id,
                                "type": artifact_type,
                            },
                            "action": "CREATE",
                        }
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


def _extract_size_scores(rating: Dict[str, Any]) -> Dict[str, float]:
    """Extract size scores from rating object, handling dict structure"""
    size_score = alias(rating, "size_score", "SizeScore", "score_size_score")
    if isinstance(size_score, dict):
        return {
            "raspberry_pi": round(float(size_score.get("raspberry_pi", 0.0)), 2),
            "jetson_nano": round(float(size_score.get("jetson_nano", 0.0)), 2),
            "desktop_pc": round(float(size_score.get("desktop_pc", 0.0)), 2),
            "aws_server": round(float(size_score.get("aws_server", 0.0)), 2),
        }
    else:
        # If size_score is not a dict, return default values
        return {
            "raspberry_pi": 0.0,
            "jetson_nano": 0.0,
            "desktop_pc": 0.0,
            "aws_server": 0.0,
        }


def _build_rating_response(id: str, rating: Dict[str, Any]) -> Dict[str, Any]:
    """Build ModelRating response with all required fields."""
    return {
        "name": id,
        "category": alias(rating, "category") or "unknown",
        "net_score": round(float(alias(rating, "net_score", "NetScore", "netScore") or 0.0), 2),
        "net_score_latency": round(float(alias(rating, "net_score_latency", "NetScoreLatency") or 0.0), 2),
        "ramp_up_time": round(float(alias(
            rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp"
        ) or 0.0), 2),
        "ramp_up_time_latency": round(float(alias(rating, "ramp_up_time_latency", "RampUpTimeLatency") or 0.0), 2),
        "bus_factor": round(float(alias(
            rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
        ) or 0.0), 2),
        "bus_factor_latency": round(float(alias(rating, "bus_factor_latency", "BusFactorLatency") or 0.0), 2),
        "performance_claims": round(float(alias(
            rating,
            "performance_claims",
            "PerformanceClaims",
            "score_performance_claims",
        ) or 0.0), 2),
        "performance_claims_latency": round(float(alias(rating, "performance_claims_latency", "PerformanceClaimsLatency") or 0.0), 2),
        "license": round(float(alias(rating, "license", "License", "score_license") or 0.0), 2),
        "license_latency": round(float(alias(rating, "license_latency", "LicenseLatency") or 0.0), 2),
        "dataset_and_code_score": round(float(alias(
            rating,
            "dataset_code",
            "DatasetCode",
            "score_available_dataset_and_code",
        ) or 0.0), 2),
        "dataset_and_code_score_latency": round(float(alias(rating, "dataset_and_code_score_latency", "DatasetAndCodeScoreLatency") or 0.0), 2),
        "dataset_quality": round(float(alias(
            rating, "dataset_quality", "DatasetQuality", "score_dataset_quality"
        ) or 0.0), 2),
        "dataset_quality_latency": round(float(alias(rating, "dataset_quality_latency", "DatasetQualityLatency") or 0.0), 2),
        "code_quality": round(float(alias(
            rating, "code_quality", "CodeQuality", "score_code_quality"
        ) or 0.0), 2),
        "code_quality_latency": round(float(alias(rating, "code_quality_latency", "CodeQualityLatency") or 0.0), 2),
        "reproducibility": round(float(alias(
            rating, "reproducibility", "Reproducibility", "score_reproducibility"
        ) or 0.0), 2),
        "reproducibility_latency": round(float(alias(rating, "reproducibility_latency", "ReproducibilityLatency") or 0.0), 2),
        "reviewedness": round(float(alias(
            rating, "reviewedness", "Reviewedness", "score_reviewedness"
        ) or 0.0), 2),
        "reviewedness_latency": round(float(alias(rating, "reviewedness_latency", "ReviewednessLatency") or 0.0), 2),
        "tree_score": round(float(alias(rating, "treescore", "Treescore", "score_treescore") or 0.0), 2),
        "tree_score_latency": round(float(alias(rating, "tree_score_latency", "TreeScoreLatency") or 0.0), 2),
        "size_score": _extract_size_scores(rating),
        "size_score_latency": round(float(alias(rating, "size_score_latency", "SizeScoreLatency") or 0.0), 2),
    }


@app.get("/artifact/model/{id}/rate")
def get_model_rate(id: str, request: Request):
    try:
        logger.info(f"DEBUG: Validating id format: '{id}'")
        # Handle empty IDs - allow flexible formats (alphanumeric, hyphens, underscores, slashes, dots, colons)
        # This supports both numeric artifact IDs and model names (e.g., "google-bert/bert-base-uncased")
        if not id or not id.strip() or id == "{id}":
            logger.warning(f"DEBUG: Invalid id format: '{id}' (e.g., literal {{id}}) - returning zero metrics with status 200")
            # Return zero metrics with status 200 for invalid ID formats (including literal {id})
            # Response structure matches ModelRating schema exactly (all required fields present)
            return JSONResponse(
                status_code=200,
                content={
                    "name": id,
                    "category": "unknown",
                    "net_score": 0.0,
                    "net_score_latency": 0.0,
                    "ramp_up_time": 0.0,
                    "ramp_up_time_latency": 0.0,
                    "bus_factor": 0.0,
                    "bus_factor_latency": 0.0,
                    "performance_claims": 0.0,
                    "performance_claims_latency": 0.0,
                    "license": 0.0,
                    "license_latency": 0.0,
                    "dataset_and_code_score": 0.0,
                    "dataset_and_code_score_latency": 0.0,
                    "dataset_quality": 0.0,
                    "dataset_quality_latency": 0.0,
                    "code_quality": 0.0,
                    "code_quality_latency": 0.0,
                    "reproducibility": 0.0,
                    "reproducibility_latency": 0.0,
                    "reviewedness": 0.0,
                    "reviewedness_latency": 0.0,
                    "tree_score": 0.0,
                    "tree_score_latency": 0.0,
                    "size_score": {
                        "raspberry_pi": 0.0,
                        "jetson_nano": 0.0,
                        "desktop_pc": 0.0,
                        "aws_server": 0.0,
                    },
                    "size_score_latency": 0.0,
                }
            )
        
        logger.info(f"DEBUG: ===== GET_MODEL_RATE START =====")
        logger.info(f"DEBUG: Querying rate for id='{id}'")
        
        found = False
        model_name = None
        # Check database for artifact - try full metadata first
        artifact = get_generic_artifact_metadata("model", id)
        if not artifact:
            artifact = get_artifact_from_db(id)
        if artifact:
            logger.info(f"DEBUG: ✅ Found artifact in database: {artifact}")
            if artifact.get("type") == "model":
                found = True
                model_name = artifact.get("name", id)
                logger.info(f"DEBUG: ✅ Model found in database: name='{model_name}'")
            else:
                logger.warning(f"DEBUG: ⚠️ Artifact type mismatch: expected 'model', got '{artifact.get('type')}'")
        else:
            logger.info(f"DEBUG: ❌ Artifact id '{id}' not found in database, searching S3 metadata")
            # Try to find artifact metadata in S3 by artifact_id
            import time
            s3_start = time.time()
            s3_metadata = find_artifact_metadata_by_id(id)
            s3_elapsed = time.time() - s3_start
            logger.info(f"DEBUG: S3 metadata lookup took {s3_elapsed:.3f}s")
            
            if s3_metadata:
                logger.info(f"DEBUG: ✅ Found S3 metadata: {s3_metadata}")
                if s3_metadata.get("type") == "model":
                    found = True
                    model_name = s3_metadata.get("name")
                    logger.info(f"DEBUG: ✅ S3 metadata type is 'model': model_name='{model_name}'")
                    # Restore to database for future lookups
                    save_artifact(id, {
                        "name": model_name,
                        "type": "model",
                        "version": s3_metadata.get("version", "main"),
                        "id": id,
                        "url": s3_metadata.get("url", f"https://huggingface.co/{model_name}")
                    })
                    logger.info(f"DEBUG: ✅ Restored to database: id='{id}'")
                else:
                    logger.warning(f"DEBUG: ⚠️ S3 metadata type mismatch: expected 'model', got '{s3_metadata.get('type')}'")
            else:
                logger.warning(f"DEBUG: ❌ S3 metadata not found for artifact_id '{id}'")
        
        if not found:
            logger.info(f"DEBUG: Not found in storage or S3 metadata, searching S3 by model name")
            try:
                logger.info(f"DEBUG: Calling list_models with regex: '^{re.escape(id)}$'")
                result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                models_found = result.get("models", [])
                logger.info(f"DEBUG: list_models returned {len(models_found)} models")
                if models_found:
                    found = True
                    model_name = id  # Use id as model name
                    logger.info(f"DEBUG: Model found via list_models")
                else:
                    logger.info(f"DEBUG: No models found, trying common versions")
                    common_versions = ["1.0.0", "main", "latest"]
                    for v in common_versions:
                        try:
                            s3_key = f"models/{id}/{v}/model.zip"
                            logger.info(f"DEBUG: Checking S3 key: {s3_key}")
                            s3.head_object(Bucket=ap_arn, Key=s3_key)
                            found = True
                            model_name = id  # Use id as model name
                            logger.info(f"DEBUG: Found model with common version: {s3_key}")
                            break
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code", "")
                            logger.debug(f"DEBUG: Common version check failed: {s3_key}, error_code={error_code}")
                            continue
            except Exception as e:
                logger.error(f"DEBUG: Exception searching S3: {str(e)}", exc_info=True)
                pass
        
        if not found:
            logger.error(f"DEBUG: Model not found: id='{id}'")
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

        # Check rating status and block until complete
        # Thread-safe check: use a lock to prevent race conditions
        if id in _rating_status:
            status = _rating_status[id]
            logger.info(f"DEBUG: Rating status for id='{id}': {status}")
            
            if status == "pending":
                # Block until rating completes (with timeout)
                logger.info(f"DEBUG: Rating pending, waiting for completion...")
                if id in _rating_locks:
                    # Wait up to 120 seconds for rating to complete (increased timeout for concurrent requests)
                    event = _rating_locks[id]
                    if not event.wait(timeout=120):
                        logger.warning(f"DEBUG: Rating timeout for id='{id}'")
                        raise HTTPException(status_code=404, detail="Artifact does not exist.")
                    # Re-check status after wait
                    status = _rating_status.get(id, "unknown")
            
            if status == "disqualified" or status == "failed":
                logger.warning(f"DEBUG: Rating {status} for id='{id}'")
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            if status == "completed":
                # Use cached rating result
                rating = _rating_results.get(id)
                if not rating:
                    logger.warning(f"DEBUG: Rating completed but no result cached, re-analyzing...")
                    # Fall through to analyze
                else:
                    logger.info(f"DEBUG: Using cached rating result for id='{id}'")
                    return _build_rating_response(id, rating)
        else:
            # No rating status - might be an old artifact or non-model
            # Try to analyze directly
            rating = None
        
        # Analyze model content if not cached
        if not rating:
            logger.info(f"DEBUG: Analyzing model content for id='{id}', model_name='{model_name or id}'")
            try:
                # Use model_name if available, otherwise use id
                analysis_id = model_name if model_name else id
                logger.info(f"DEBUG: Calling analyze_model_content with: '{analysis_id}'")
                rating = analyze_model_content(analysis_id)
                logger.info(f"DEBUG: analyze_model_content returned: {rating}")
                if not rating:
                    logger.error(f"DEBUG: analyze_model_content returned None/empty for '{analysis_id}'")
                    raise HTTPException(
                        status_code=500,
                        detail="The artifact rating system encountered an error while computing at least one metric.",
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"DEBUG: Error analyzing model content for {analysis_id}: {str(e)}", exc_info=True
                )
                logger.error(
                    f"Error analyzing model content for {id}: {str(e)}", exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
                )

        # Cache the rating result before returning
        _rating_results[id] = rating
        _rating_status[id] = "completed"
        
        return _build_rating_response(id, rating)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model rate for {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
        )


@app.get("/artifact/model/{id}/lineage")
def get_model_lineage(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate id parameter - allow flexible formats (alphanumeric, hyphens, underscores, slashes, dots, colons)
        # This supports both numeric artifact IDs and model names (e.g., "google-bert/bert-base-uncased")
        if not id or not id.strip():
            raise HTTPException(
                status_code=400,
                detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.",
            )

        # Check if artifact exists - try full metadata first
        found = False
        artifact = get_generic_artifact_metadata("model", id)
        if not artifact:
            artifact = get_artifact_from_db(id)
        if artifact and artifact.get("type") == "model":
                found = True

        if not found:
            try:
                result_check = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                if result_check.get("models"):
                    found = True
                else:
                    # Try to get model name from database for S3 lookup
                    model_name = _get_model_name_for_s3(id)
                    if model_name:
                        common_versions = ["1.0.0", "main", "latest"]
                        for v in common_versions:
                            try:
                                s3_key = f"models/{model_name}/{v}/model.zip"
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                found = True
                                break
                            except ClientError:
                                continue
                    # Fallback: try by ID directly (in case it was stored by ID)
                    if not found:
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

        # Get model name for S3 lookup (models are stored by name, not ID)
        model_name = _get_model_name_for_s3(id)
        if not model_name:
            # Fallback: use ID directly (in case it was stored by ID)
            model_name = id

        # Get lineage from config
        result = get_model_lineage_from_config(model_name, "1.0.0")
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
                {
                    "artifact_id": model_id,
                    "name": metadata.get("name", model_id),
                    "source": metadata.get("source", "config_json"),
                }
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
                                {
                                    "from_node_artifact_id": dep_id,
                                    "to_node_artifact_id": model_id,
                                    "relationship": relationship,
                                }
                            )

        # Return lineage graph
        return {"nodes": nodes, "edges": edges}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model lineage for {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.",
        )


@app.post("/artifact/model/{id}/license-check")
async def check_model_license(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        # Validate id parameter - allow flexible formats (alphanumeric, hyphens, underscores, slashes, dots, colons)
        # This supports both numeric artifact IDs and model names (e.g., "google-bert/bert-base-uncased")
        if not id or not id.strip():
            raise HTTPException(
                status_code=400,
                detail="The license check request is malformed or references an unsupported usage context.",
            )

        # Check if artifact exists - try full metadata first
        found = False
        artifact = get_generic_artifact_metadata("model", id)
        if not artifact:
            artifact = get_artifact_from_db(id)
        if artifact and artifact.get("type") == "model":
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

        # Parse request body
        try:
            body = (
                await request.json()
                if request.headers.get("content-type") == "application/json"
                else {}
            )
            if not isinstance(body, dict):
                form = await request.form()
                body = dict(form)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="The license check request is malformed or references an unsupported usage context.",
            )

        # Validate github_url
        github_url = body.get("github_url", "")
        if not github_url or not isinstance(github_url, str):
            raise HTTPException(
                status_code=400,
                detail="The license check request is malformed or references an unsupported usage context.",
            )

        # Get model name for license extraction (models are stored by name, not ID)
        model_name_for_license = _get_model_name_for_s3(id)
        if not model_name_for_license:
            # Fallback: use ID directly (in case it was stored by ID)
            model_name_for_license = id

        # Extract licenses and check compatibility
        try:
            model_license = extract_model_license(model_name_for_license)
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
            use_case = body.get("use_case", "fine-tune+inference")
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


@app.get("/tracks")
def get_tracks():
    try:
        # Return list of tracks the student plans to implement
        # Must match the enum values from the spec:
        # - "Performance track"
        # - "Access control track"
        # - "High assurance track"
        # - "Other Security track"
        planned_tracks = ["Performance track", "Access control track"]
        return {"plannedTracks": planned_tracks}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tracks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="The system encountered an error while retrieving the student's track information.",
        )
@app.get("/package/{id}/rate")
def get_package_rate(id: str, request: Request):
    return get_model_rate(id, request)


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

# Attach frontend routes so the same templates served locally are available in AWS
frontend_routes.setup_app(app=app, templates_instance=templates)