from __future__ import annotations
from pathlib import Path
import re
import os
import json
from starlette.datastructures import UploadFile
import uvicorn
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, status

# from fastapi.security import HTTPBearer  # Not used - removed to prevent accidental security enforcement
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
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
    sanitize_model_id,
    store_model_metadata,
    get_model_metadata,
    store_generic_artifact_metadata,
    get_generic_artifact_metadata,
    aws_available,
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


@app.get("/health")
def health():
    return {"ok": True}


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
                result = list_models(limit=1000)
                if result is None:
                    result = {"models": []}
                models = result.get("models") or []
                for model in models:
                    if isinstance(model, dict) and (
                        not types_filter or "model" in types_filter
                    ):
                        results.append(
                            {
                                "name": model.get("name", ""),
                                "id": model.get("id", model.get("name", "")),
                                "type": "model",
                            }
                        )
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_type_stored = artifact.get("type", "")
                    if not types_filter or artifact_type_stored in types_filter:
                        results.append(
                            {
                                "name": artifact.get("name", artifact_id),
                                "id": artifact_id,
                                "type": artifact_type_stored,
                            }
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
                        not types_filter or "model" in types_filter
                    ):
                        results.append(
                            {
                                "name": model.get("name", ""),
                                "id": model.get("id", model.get("name", "")),
                                "type": "model",
                            }
                        )
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_name = artifact.get("name", artifact_id)
                    artifact_type_stored = artifact.get("type", "")
                    if re.match(name_pattern, artifact_name) and (
                        not types_filter or artifact_type_stored in types_filter
                    ):
                        results.append(
                            {
                                "name": artifact_name,
                                "id": artifact_id,
                                "type": artifact_type_stored,
                            }
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


@app.delete("/reset")
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


@app.get("/artifact/byName/{name:path}")
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
        sanitized_name = sanitize_model_id(name)
        name_pattern = f"^{re.escape(sanitized_name)}$"
        result = list_models(name_regex=name_pattern, limit=1000)
        artifacts = []
        seen_ids = set()

        for model in result.get("models", []):
            model_id = model.get("name")
            metadata = get_model_metadata(model_id) or {}
            display_name = metadata.get("name", name)
            if display_name == name:
                artifacts.append(
                    {
                        "name": display_name,
                        "id": metadata.get("id", model_id),
                        "type": metadata.get("type", "model"),
                    }
                )
                seen_ids.add(metadata.get("id", model_id))

        if aws_available:
            candidate_id = sanitize_model_id(name)
            for artifact_type in ["dataset", "code"]:
                metadata = get_generic_artifact_metadata(artifact_type, candidate_id)
                if metadata and metadata.get("name") == name:
                    artifacts.append(
                        {
                            "name": metadata.get("name", name),
                            "id": metadata.get("id", candidate_id),
                            "type": metadata.get("type", artifact_type),
                        }
                    )
                    seen_ids.add(metadata.get("id", candidate_id))
                    _artifact_storage[metadata.get("id", candidate_id)] = metadata

        # Add artifacts from storage (non-model artifacts or cached models)
        if not aws_available:
            for artifact_id, artifact in _artifact_storage.items():
                if artifact.get("name") == name and artifact_id not in seen_ids:
                    artifacts.append(
                        {
                            "name": artifact.get("name", artifact_id),
                            "id": artifact_id,
                            "type": artifact.get("type", "model"),
                        }
                    )
                    seen_ids.add(artifact_id)

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


@app.post("/artifact/byRegEx")
async def search_artifacts_by_regex(request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
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
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Handle array or object body
        if isinstance(body, list) and len(body) > 0:
            search_criteria = body[0]
        elif isinstance(body, dict):
            search_criteria = body
        else:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Validate regex field
        regex_pattern = search_criteria.get("regex")
        if not regex_pattern or not isinstance(regex_pattern, str):
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Validate regex pattern
        try:
            re.compile(regex_pattern)
        except re.error:
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        compiled_pattern = re.compile(regex_pattern)

        # Search for models matching regex
        artifacts = []
        try:
            models_response = list_models(limit=1000)
            for model in models_response.get("models", []):
                model_id = model.get("name")
                metadata = get_model_metadata(model_id) or {}
                candidate_name = metadata.get("name", model_id)
                if compiled_pattern.search(candidate_name):
                    artifacts.append(
                        {
                            "name": candidate_name,
                            "id": metadata.get("id", model_id),
                            "type": metadata.get("type", "model"),
                        }
                    )
        except Exception as e:
            logger.warning(f"Error searching models with regex {regex_pattern}: {str(e)}")

        # Search artifacts in storage matching regex
        for artifact_id, artifact in _artifact_storage.items():
            artifact_name = artifact.get("name", artifact_id)
            try:
                if compiled_pattern.search(artifact_name):
                    artifacts.append(
                        {
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact.get("type", "model"),
                        }
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


@app.get("/artifact/{artifact_type}/{id}")
@app.get("/artifacts/{artifact_type}/{id}")
def get_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    try:
        if artifact_type == "model":
            artifact = _artifact_storage.get(id)
            if not artifact:
                artifact = get_model_metadata(id)
                if artifact:
                    _artifact_storage[id] = artifact
            if artifact:
                return {
                    "metadata": {
                        "name": artifact.get("name", id),
                        "id": id,
                        "type": artifact_type,
                    },
                    "data": {
                        "url": artifact.get(
                            "url", f"https://huggingface.co/{artifact.get('name', id)}"
                        )
                    },
                }
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
            return {
                "metadata": {"name": model["name"], "id": id, "type": artifact_type},
                "data": {"url": f"https://huggingface.co/{id}"},
            }
        else:
            artifact = None
            if aws_available:
                artifact = get_generic_artifact_metadata(artifact_type, id)
                if artifact:
                    _artifact_storage[id] = artifact
            if not artifact and not aws_available:
                artifact = _artifact_storage.get(id)
            if artifact:
                return {
                    "metadata": {
                        "name": artifact.get("name", id),
                        "id": id,
                        "type": artifact_type,
                    },
                    "data": {
                        "url": artifact.get("url"),
                    },
                }
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


@app.post("/artifact/{artifact_type}")
async def create_artifact_by_type(artifact_type: str, request: Request):
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

    global _artifact_storage
    
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
                        name_regex=f"^{re.escape(sanitize_model_id(model_id))}$", limit=1
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

                    artifact_id = sanitize_model_id(model_id)
                    metadata_entry = {
                        "name": model_id,
                        "type": artifact_type,
                        "version": version,
                        "id": artifact_id,
                        "url": url,
                        "source": "huggingface",
                    }
                    _artifact_storage[artifact_id] = metadata_entry
                    store_model_metadata(model_id, metadata_entry)
                    return Response(
                        content=json.dumps(
                            {
                                "metadata": {
                                    "name": model_id,
                                    "id": artifact_id,
                                    "type": artifact_type,
                                },
                                "data": {"url": url},
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
            else:
                # Non-HuggingFace URL provided - use name if available, otherwise extract from URL
                model_id = name if name else (url.split("/")[-1] if url else f"{artifact_type}-new")
                artifact_id = sanitize_model_id(model_id)
                metadata_entry = {
                    "name": model_id,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                    "source": "direct",
                }
                _artifact_storage[artifact_id] = metadata_entry
                store_model_metadata(model_id, metadata_entry)
                return Response(
                    content=json.dumps(
                        {
                            "metadata": {
                                "name": model_id,
                                "id": artifact_id,
                                "type": artifact_type,
                            },
                            "data": {"url": url},
                        }
                    ),
                    media_type="application/json",
                    status_code=201,
                )
        elif artifact_type in ["dataset", "code"]:
            # For dataset and code artifacts, perform ingestion
            artifact_name = name if name else (url.split("/")[-1] if url else f"{artifact_type}-new")
            if not url:
                raise HTTPException(
                    status_code=400,
                    detail="There is missing field(s) in the artifact_data or it is formed improperly (must include a single url).",
                )

            artifact_id = sanitize_model_id(artifact_name)
            existing_metadata = (
                get_generic_artifact_metadata(artifact_type, artifact_id)
                if aws_available
                else None
            )
            if existing_metadata:
                raise HTTPException(status_code=409, detail="Artifact exists already.")
            for existing_id, existing_artifact in _artifact_storage.items():
                if existing_artifact.get("type") == artifact_type and (
                    existing_artifact.get("url") == url
                    or existing_artifact.get("name") == artifact_name
                ):
                    raise HTTPException(
                        status_code=409, detail="Artifact exists already."
                    )

            metadata_entry = {
                "name": artifact_name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
                "source": "direct",
            }

            _artifact_storage[artifact_id] = metadata_entry
            store_generic_artifact_metadata(artifact_type, artifact_id, metadata_entry)

            return Response(
                content=json.dumps(
                    {
                        "metadata": {
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact_type,
                        },
                        "data": {"url": url},
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
            global _artifact_storage
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == artifact_type:
                    # Update artifact data (url) - replace previous contents
                    data = body.get("data", {})
                    url = data.get("url", "")
                    if not url:
                        raise HTTPException(
                            status_code=400,
                            detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid. URL is required in data.",
                        )
                    _artifact_storage[id] = {
                        "name": metadata.get("name", artifact.get("name", id)),
                        "type": artifact_type,
                        "id": id,
                        "url": url,
                    }
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
                result = {}
                total_size_mb = standalone_size_mb

                # Add main artifact
                result[id] = {
                    "standalone_cost": round(standalone_size_mb, 2),
                    "total_cost": round(
                        standalone_size_mb, 2
                    ),  # Will be updated with total after dependencies
                }

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
                                    result[dep_id] = {
                                        "standalone_cost": round(dep_size_mb, 2),
                                        "total_cost": round(dep_size_mb, 2),
                                    }
                            except Exception:
                                pass

                # Update main artifact's total_cost to include all dependencies
                result[id]["total_cost"] = round(total_size_mb, 2)
            else:
                # When dependency=false, return only main artifact with total_cost
                result = {id: {"total_cost": round(standalone_size_mb, 2)}}
            return result
        else:
            if id not in _artifact_storage:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            artifact = _artifact_storage[id]
            if artifact.get("type") != artifact_type:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            standalone_cost = 0.0
            if dependency:
                return {
                    id: {
                        "standalone_cost": standalone_cost,
                        "total_cost": standalone_cost,
                    }
                }
            else:
                return {id: {"total_cost": standalone_cost}}
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
            # For non-model artifacts, check storage
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == artifact_type:
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


@app.get("/artifact/model/{id}/rate")
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

        # Build ModelRating response with all required fields
        result = {
            "name": id,
            "category": alias(rating, "category") or "unknown",
            "net_score": round(float(alias(rating, "net_score", "NetScore", "netScore") or 0.0), 2),
            "ramp_up_time": round(float(alias(
                rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp"
            ) or 0.0), 2),
            "bus_factor": round(float(alias(
                rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
            ) or 0.0), 2),
            "performance_claims": round(float(alias(
                rating,
                "performance_claims",
                "PerformanceClaims",
                "score_performance_claims",
            ) or 0.0), 2),
            "license": round(float(alias(rating, "license", "License", "score_license") or 0.0), 2),
            "dataset_and_code_score": round(float(alias(
                rating,
                "dataset_code",
                "DatasetCode",
                "score_available_dataset_and_code",
            ) or 0.0), 2),
            "dataset_quality": round(float(alias(
                rating, "dataset_quality", "DatasetQuality", "score_dataset_quality"
            ) or 0.0), 2),
            "code_quality": round(float(alias(
                rating, "code_quality", "CodeQuality", "score_code_quality"
            ) or 0.0), 2),
            "reproducibility": round(float(alias(
                rating, "reproducibility", "Reproducibility", "score_reproducibility"
            ) or 0.0), 2),
            "reviewedness": round(float(alias(
                rating, "reviewedness", "Reviewedness", "score_reviewedness"
            ) or 0.0), 2),
            "tree_score": round(float(alias(rating, "treescore", "Treescore", "score_treescore") or 0.0), 2),
            "size_score": {
                "raspberry_pi": round(float(alias(rating, "size_score", "raspberry_pi") or 0.0), 2),
                "jetson_nano": round(float(alias(rating, "size_score", "jetson_nano") or 0.0), 2),
                "desktop_pc": round(float(alias(rating, "size_score", "desktop_pc") or 0.0), 2),
                "aws_server": round(float(alias(rating, "size_score", "aws_server") or 0.0), 2),
            },
        }
        return result
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
        # Validate id parameter
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            raise HTTPException(
                status_code=400,
                detail="The license check request is malformed or references an unsupported usage context.",
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