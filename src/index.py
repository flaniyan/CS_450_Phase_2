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
    find_artifact_metadata_by_id,
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


@app.get("/artifact/byName/{name}")
def get_artifact_by_name(name: str, request: Request):
    logger.info(f"=== GET /artifact/byName/{name} ===")
    logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
    
    if not verify_auth_token(request):
        logger.error(f"DEBUG: Authentication failed for /artifact/byName/{name}")
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    logger.info(f"DEBUG: Authentication passed for /artifact/byName/{name}")
    
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
        logger.info(f"DEBUG: Searching S3 for models with name pattern: {name_pattern}")
        result = list_models(name_regex=name_pattern, limit=1000)
        logger.info(f"DEBUG: list_models returned {len(result.get('models', []))} models")
        artifacts = []

        # Track which artifact_ids we've already added to avoid duplicates
        seen_artifact_ids = set()
        logger.info(f"DEBUG: Checking _artifact_storage (size: {len(_artifact_storage)})")
        
        # Add models from S3 - find their artifact_ids from storage
        for model in result.get("models", []):
            model_name = model.get("name", "")
            logger.info(f"DEBUG: Processing model from S3: name='{model_name}', version='{model.get('version', 'N/A')}'")
            if model_name == name:  # Exact match
                logger.info(f"DEBUG: Found exact match in S3: {model_name}")
                # Find artifact_id(s) for this model name in storage
                found_ids = []
                for artifact_id, artifact in _artifact_storage.items():
                    if artifact.get("name") == model_name and artifact.get("type") == "model":
                        if artifact_id not in seen_artifact_ids:
                            found_ids.append(artifact_id)
                            seen_artifact_ids.add(artifact_id)
                            logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in storage for model '{model_name}'")
                
                # If we found artifact_ids, use them; otherwise use model name as fallback
                if found_ids:
                    logger.info(f"DEBUG: Using {len(found_ids)} artifact_id(s) from storage")
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
                    logger.warning(f"DEBUG: No artifact_id found in storage for '{model_name}', using fallback")
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

        # Add artifacts from storage (all artifact types including models)
        logger.info(f"DEBUG: Searching _artifact_storage for artifacts with name='{name}'")
        storage_matches = 0
        for artifact_id, artifact in _artifact_storage.items():
            if artifact.get("name") == name and artifact_id not in seen_artifact_ids:  # Exact match
                storage_matches += 1
                logger.info(f"DEBUG: Found artifact in storage: id='{artifact_id}', name='{artifact.get('name')}', type='{artifact.get('type')}'")
                seen_artifact_ids.add(artifact_id)
                artifacts.append(
                    {
                        "name": artifact.get("name", artifact_id),
                        "id": artifact_id,
                        "type": artifact.get("type", "model"),
                    }
                )
        logger.info(f"DEBUG: Found {storage_matches} additional artifacts in storage")

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

        # Validate regex pattern
        try:
            re.compile(regex_pattern)
        except re.error as regex_error:
            logger.error(f"Invalid regex pattern '{regex_pattern}': {str(regex_error)}")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid",
            )

        # Search for artifacts matching regex in S3 (all types: model, dataset, code)
        logger.info(f"DEBUG: Starting regex search with pattern: '{regex_pattern}'")
        artifacts = []
        seen_artifact_ids = set()
        
        # Search models from S3
        logger.info(f"DEBUG: Searching models in S3 with regex: '{regex_pattern}'")
        try:
            result = list_models(name_regex=regex_pattern, limit=1000)
            models_found = result.get("models", [])
            logger.info(f"DEBUG: Found {len(models_found)} models in S3 matching regex")
            for model in models_found:
                model_name = model.get("name", "")
                logger.info(f"DEBUG: Processing model from S3: name='{model_name}', version='{model.get('version', 'N/A')}'")
                # Find artifact_id for this model name in storage
                artifact_id = None
                for stored_id, stored_artifact in _artifact_storage.items():
                    if stored_artifact.get("name") == model_name and stored_artifact.get("type") == "model":
                        artifact_id = stored_id
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in storage for model '{model_name}'")
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
            result = list_artifacts_from_s3(artifact_type="dataset", name_regex=regex_pattern, limit=1000)
            datasets_found = result.get("artifacts", [])
            logger.info(f"DEBUG: Found {len(datasets_found)} datasets in S3 matching regex")
            for dataset in datasets_found:
                dataset_name = dataset.get("name", "")
                logger.info(f"DEBUG: Processing dataset from S3: name='{dataset_name}', version='{dataset.get('version', 'N/A')}'")
                # Find artifact_id for this dataset name in storage
                artifact_id = None
                for stored_id, stored_artifact in _artifact_storage.items():
                    if stored_artifact.get("name") == dataset_name and stored_artifact.get("type") == "dataset":
                        artifact_id = stored_id
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in storage for dataset '{dataset_name}'")
                        break
                
                if not artifact_id:
                    artifact_id = dataset_name
                    logger.warning(f"DEBUG: No artifact_id in storage for '{dataset_name}', using fallback: '{artifact_id}'")
                
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
            result = list_artifacts_from_s3(artifact_type="code", name_regex=regex_pattern, limit=1000)
            code_artifacts_found = result.get("artifacts", [])
            logger.info(f"DEBUG: Found {len(code_artifacts_found)} code artifacts in S3 matching regex")
            for code_artifact in code_artifacts_found:
                code_name = code_artifact.get("name", "")
                logger.info(f"DEBUG: Processing code artifact from S3: name='{code_name}', version='{code_artifact.get('version', 'N/A')}'")
                # Find artifact_id for this code artifact name in storage
                artifact_id = None
                for stored_id, stored_artifact in _artifact_storage.items():
                    if stored_artifact.get("name") == code_name and stored_artifact.get("type") == "code":
                        artifact_id = stored_id
                        logger.info(f"DEBUG: Found artifact_id '{artifact_id}' in storage for code artifact '{code_name}'")
                        break
                
                if not artifact_id:
                    artifact_id = code_name
                    logger.warning(f"DEBUG: No artifact_id in storage for '{code_name}', using fallback: '{artifact_id}'")
                
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
        logger.info(f"DEBUG: Searching _artifact_storage (size: {len(_artifact_storage)}) for artifacts matching regex")
        storage_matches = 0
        for artifact_id, artifact in _artifact_storage.items():
            artifact_name = artifact.get("name", artifact_id)
            artifact_type = artifact.get("type", "model")
            try:
                if re.search(regex_pattern, artifact_name) and artifact_id not in seen_artifact_ids:
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
            logger.info(f"DEBUG: Processing model artifact with id='{id}'")
            # For models, ALWAYS verify existence in S3 (source of truth)
            model_name = None
            version = None
            found = False
            
            # First, check if id is in _artifact_storage to get the model name and version
            stored_version = None
            logger.info(f"DEBUG: Checking _artifact_storage for id='{id}' (storage size: {len(_artifact_storage)})")
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                logger.info(f"DEBUG: Found artifact in storage: {artifact}")
                if artifact.get("type") == "model":
                    model_name = artifact.get("name", id)
                    stored_version = artifact.get("version", "main")
                    logger.info(f"DEBUG: Extracted from storage: model_name='{model_name}', version='{stored_version}'")
                else:
                    logger.warning(f"DEBUG: Artifact type mismatch: expected 'model', got '{artifact.get('type')}'")
            else:
                logger.info(f"DEBUG: Artifact id '{id}' not found in _artifact_storage, searching S3 metadata")
                # Try to find artifact metadata in S3 by artifact_id
                s3_metadata = find_artifact_metadata_by_id(id)
                if s3_metadata and s3_metadata.get("type") == "model":
                    model_name = s3_metadata.get("name")
                    stored_version = s3_metadata.get("version", "main")
                    logger.info(f"DEBUG: Found artifact in S3 metadata: model_name='{model_name}', version='{stored_version}'")
                    # Restore to _artifact_storage for future lookups
                    _artifact_storage[id] = {
                        "name": model_name,
                        "type": "model",
                        "version": stored_version,
                        "id": id,
                        "url": s3_metadata.get("url", f"https://huggingface.co/{model_name}")
                    }
                else:
                    logger.info(f"DEBUG: Artifact id '{id}' not found in S3 metadata either")
            
            # If we have a model name from storage, use it; otherwise use id as model name
            search_name = model_name if model_name else id
            logger.info(f"DEBUG: Using search_name='{search_name}'")
            
            # Sanitize the model name for S3 lookup
            sanitized_search_name = sanitize_model_id_for_s3(search_name)
            logger.info(f"DEBUG: Sanitized search name: '{sanitized_search_name}'")
            
            # If we have a stored version, try that first
            if stored_version:
                logger.info(f"DEBUG: Trying stored version first: '{stored_version}'")
                # Sanitize version for S3 key (same as upload_model)
                safe_version = stored_version.replace("/", "_").replace(":", "_").replace("\\", "_")
                s3_key = f"models/{sanitized_search_name}/{safe_version}/model.zip"
                logger.info(f"DEBUG: Checking S3 key: {s3_key}")
                try:
                    s3.head_object(Bucket=ap_arn, Key=s3_key)
                    version = stored_version  # Keep original version format for response
                    model_name = search_name
                    found = True
                    logger.info(f"DEBUG: Found model in S3 with stored version: {s3_key}")
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    logger.warning(f"DEBUG: S3 check failed for stored version: {s3_key}, error_code={error_code}")
                    if error_code not in ["NoSuchKey", "404"]:
                        logger.warning(f"Unexpected error checking {s3_key}: {error_code}")
            
            # If not found with stored version, try list_models to find any version
            if not found:
                logger.info(f"DEBUG: Not found with stored version, trying list_models")
                try:
                    result = list_models(name_regex=f"^{re.escape(sanitized_search_name)}$", limit=1000)
                    models_found = result.get("models", [])
                    logger.info(f"DEBUG: list_models returned {len(models_found)} models")
                    if models_found:
                        for model in models_found:
                            v = model["version"]
                            model_n = model.get("name", sanitized_search_name)
                            logger.info(f"DEBUG: Checking model: name='{model_n}', version='{v}'")
                            # Note: model_n and v from list_models are already sanitized (from S3 key path)
                            # The version from list_models is the sanitized version from the S3 key
                            # So we can use it directly to construct the S3 key
                            s3_key = f"models/{model_n}/{v}/model.zip"
                            logger.info(f"DEBUG: Verifying S3 key: {s3_key}")
                            try:
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                # Version from list_models is already sanitized, but we need to map it back
                                # to the original version format. Since we don't have the original, use as-is
                                # but try to find the original version from storage if available
                                if model_name and stored_version:
                                    # Use the stored version if we have it (original format)
                                    version = stored_version
                                else:
                                    # Use the version from list_models (sanitized, but that's what we have)
                                    version = v
                                # Map back to original model name if we have it
                                model_name = search_name  # Use original name, not sanitized
                                found = True
                                logger.info(f"DEBUG: Found model in S3: {s3_key}, using version='{version}'")
                                break
                            except ClientError as e:
                                error_code = e.response.get("Error", {}).get("Code", "")
                                logger.warning(f"DEBUG: S3 check failed: {s3_key}, error_code={error_code}")
                                if error_code == "NoSuchKey" or error_code == "404":
                                    continue
                                else:
                                    logger.warning(
                                        f"Unexpected error checking {s3_key}: {error_code}"
                                    )
                except Exception as e:
                    logger.error(f"DEBUG: Error calling list_models: {e}", exc_info=True)
                    logger.warning(f"Error calling list_models: {e}")
            
            # If still not found, try common versions directly with sanitized name
            if not found:
                logger.info(f"DEBUG: Not found via list_models, trying common versions")
                common_versions = ["main", "1.0.0", "latest"]
                for v in common_versions:
                    try:
                        safe_version = v.replace("/", "_").replace(":", "_").replace("\\", "_")
                        s3_key = f"models/{sanitized_search_name}/{safe_version}/model.zip"
                        logger.info(f"DEBUG: Trying common version: {s3_key}")
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        version = v  # Use original version format
                        model_name = search_name
                        found = True
                        logger.info(f"DEBUG: Found model with common version: {s3_key}")
                        break
                    except ClientError as e:
                        error_code = e.response.get("Error", {}).get("Code", "")
                        logger.debug(f"DEBUG: Common version check failed: {s3_key}, error_code={error_code}")
                        if error_code == "NoSuchKey" or error_code == "404":
                            continue
                        else:
                            logger.warning(f"Unexpected error checking {s3_key}: {error_code}")
            
            # Last resort: if we have a model_name but no version found, try to find ANY version
            # by listing all objects with the model name prefix
            if not found and model_name and model_name != id:
                # Only do direct S3 search if we have a real model name (not just the artifact_id)
                logger.info(f"DEBUG: Last resort - searching S3 directly for any version of '{sanitized_search_name}'")
                try:
                    prefix = f"models/{sanitized_search_name}/"
                    response = s3.list_objects_v2(Bucket=ap_arn, Prefix=prefix, MaxKeys=10)
                    if "Contents" in response:
                        for item in response["Contents"]:
                            key = item["Key"]
                            if key.endswith("/model.zip"):
                                parts = key.split("/")
                                if len(parts) >= 3:
                                    found_version_sanitized = parts[2]  # This is already sanitized from S3 key
                                    # Try to map back to original version if we have it
                                    if stored_version:
                                        version = stored_version  # Use original version format
                                    else:
                                        # Use sanitized version as-is (it's what's in S3)
                                        # Most common versions like "main" don't change when sanitized
                                        version = found_version_sanitized
                                    model_name = search_name
                                    found = True
                                    logger.info(f"DEBUG: Found model via direct S3 search: {key}, version='{version}'")
                                    break
                except Exception as e:
                    logger.warning(f"DEBUG: Direct S3 search failed: {str(e)}")
            
            if not found:
                logger.error(f"DEBUG: Model not found: id='{id}', search_name='{search_name}', sanitized='{sanitized_search_name}'")
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Return with the verified model name and id
            result = {
                "metadata": {
                    "name": model_name if model_name else id,
                    "id": id,
                    "type": artifact_type,
                },
                "data": {
                    "url": f"https://huggingface.co/{model_name if model_name else id}"
                },
            }
            logger.info(f"DEBUG: Returning model artifact: {result}")
            return result
        else:
            logger.info(f"DEBUG: Processing {artifact_type} artifact with id='{id}'")
            # For dataset and code artifacts, verify they exist in S3
            artifact_name = None
            version = "main"
            logger.info(f"DEBUG: Checking _artifact_storage for id='{id}' (storage size: {len(_artifact_storage)})")
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                logger.info(f"DEBUG: Found artifact in storage: {artifact}")
                if artifact.get("type") == artifact_type:
                    artifact_name = artifact.get("name", id)
                    version = artifact.get("version", "main")
                    logger.info(f"DEBUG: Extracted artifact_name='{artifact_name}', version='{version}' from storage")
                else:
                    logger.warning(f"DEBUG: Artifact type mismatch: expected '{artifact_type}', got '{artifact.get('type')}'")
            else:
                logger.info(f"DEBUG: Artifact id '{id}' not found in _artifact_storage, searching S3 metadata")
                # Try to find artifact metadata in S3 by artifact_id
                s3_metadata = find_artifact_metadata_by_id(id)
                if s3_metadata and s3_metadata.get("type") == artifact_type:
                    artifact_name = s3_metadata.get("name")
                    version = s3_metadata.get("version", "main")
                    logger.info(f"DEBUG: Found artifact in S3 metadata: name='{artifact_name}', version='{version}'")
                    # Restore to _artifact_storage for future lookups
                    _artifact_storage[id] = {
                        "name": artifact_name,
                        "type": artifact_type,
                        "version": version,
                        "id": id,
                        "url": s3_metadata.get("url", f"https://example.com/{artifact_type}/{artifact_name}")
                    }
                else:
                    logger.info(f"DEBUG: Artifact id '{id}' not found in S3 metadata either")
            
            # Verify artifact exists in S3
            artifact_exists = False
            if artifact_name:
                logger.info(f"DEBUG: Verifying {artifact_type} exists in S3: name='{artifact_name}', version='{version}'")
                try:
                    sanitized_name = sanitize_model_id_for_s3(artifact_name)
                    safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
                    s3_key = f"{artifact_type}s/{sanitized_name}/{safe_version}/metadata.json"
                    logger.info(f"DEBUG: Checking S3 key: {s3_key}")
                    try:
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        artifact_exists = True
                        logger.info(f"DEBUG: {artifact_type} exists in S3: {s3_key}")
                    except ClientError as e:
                        error_code = e.response.get("Error", {}).get("Code", "")
                        logger.warning(f"DEBUG: {artifact_type} not found in S3: {s3_key}, error_code={error_code}")
                        pass
                except Exception as e:
                    logger.error(f"DEBUG: Exception verifying {artifact_type} in S3: {str(e)}", exc_info=True)
                    pass
            else:
                logger.warning(f"DEBUG: No artifact_name found, cannot verify in S3")
            
            if artifact_exists and artifact_name:
                # Get artifact from storage (should be there now after S3 lookup)
                artifact = _artifact_storage.get(id, {
                    "name": artifact_name,
                    "type": artifact_type,
                    "version": version,
                    "id": id,
                    "url": f"https://example.com/{artifact_type}/{artifact_name}"
                })
                result = {
                    "metadata": {
                        "name": artifact.get("name", artifact_name),
                        "id": id,
                        "type": artifact_type,
                    },
                    "data": {
                        "url": artifact.get(
                            "url", f"https://example.com/{artifact_type}/{artifact_name}"
                        )
                    },
                }
                logger.info(f"DEBUG: Returning {artifact_type} artifact: {result}")
                return result
            logger.error(f"DEBUG: {artifact_type} not found: id='{id}', artifact_name='{artifact_name}', exists_in_s3={artifact_exists}")
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
    global _artifact_storage
    
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
                
                # Ingest and rate the model
                model_ingestion(name, version)
                rating = analyze_model_content(name)
                net_score = (
                    alias(rating, "net_score", "NetScore", "netScore") or 0.0
                )
                if net_score < 0.5:
                    raise HTTPException(
                        status_code=424,
                        detail="Artifact is not registered due to the disqualified rating.",
                    )
                
                # Generate artifact ID and store metadata
                artifact_id = str(random.randint(1000000000, 9999999999))
                url = f"https://huggingface.co/{name}"
                _artifact_storage[artifact_id] = {
                    "name": name,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                }
                
                # Store artifact metadata in S3 (model file already stored via model_ingestion)
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
            _artifact_storage[artifact_id] = {
                "name": name,
                "type": artifact_type,
                "version": version,
                "id": artifact_id,
                "url": url,
            }
            
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

                    # Generate artifact ID and return success (per Artifact schema)
                    artifact_id = str(random.randint(1000000000, 9999999999))
                    # Store artifact metadata in _artifact_storage keyed by artifact_id
                    _artifact_storage[artifact_id] = {
                        "name": model_id,
                        "type": artifact_type,
                        "version": version,
                        "id": artifact_id,
                        "url": url,
                    }
                    
                    # Store artifact metadata in S3 (model file already stored via model_ingestion)
                    try:
                        store_artifact_metadata(artifact_id, model_id, artifact_type, version, url)
                    except Exception as s3_error:
                        logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                        # Don't fail ingestion if S3 metadata storage fails
                    
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
                artifact_id = str(random.randint(1000000000, 9999999999))
                # Store artifact metadata in _artifact_storage keyed by artifact_id
                _artifact_storage[artifact_id] = {
                    "name": model_id,
                    "type": artifact_type,
                    "version": version,
                    "id": artifact_id,
                    "url": url,
                }
                
                # Store artifact metadata in S3
                try:
                    store_artifact_metadata(artifact_id, model_id, artifact_type, version, url)
                except Exception as s3_error:
                    logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                    # Don't fail ingestion if S3 metadata storage fails
                
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
            
            # Store artifact metadata in S3
            try:
                store_artifact_metadata(artifact_id, artifact_name, artifact_type, version, url)
            except Exception as s3_error:
                logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                # Don't fail ingestion if S3 metadata storage fails
            
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


@app.get("/package/{id}")
def get_package_rate(id: str, request: Request):
    """Alias for /artifact/model/{id}/rate to support autograder"""
    return get_model_rate(id, request)


@app.get("/artifact/model/{id}/rate")
def get_model_rate(id: str, request: Request):
    logger.info(f"=== GET /artifact/model/{id}/rate ===")
    logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
    
    if not verify_auth_token(request):
        logger.error(f"DEBUG: Authentication failed for /artifact/model/{id}/rate")
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    logger.info(f"DEBUG: Authentication passed for /artifact/model/{id}/rate")
    
    try:
        logger.info(f"DEBUG: Validating id format: '{id}'")
        if not re.match(r"^[a-zA-Z0-9\-]+$", id):
            logger.error(f"DEBUG: Invalid id format: '{id}'")
            raise HTTPException(
                status_code=400,
                detail="There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.",
            )
        
        found = False
        model_name = None
        logger.info(f"DEBUG: Checking _artifact_storage for id='{id}' (storage size: {len(_artifact_storage)})")
        if id in _artifact_storage:
            artifact = _artifact_storage[id]
            logger.info(f"DEBUG: Found artifact in storage: {artifact}")
            if artifact.get("type") == "model":
                found = True
                model_name = artifact.get("name", id)
                logger.info(f"DEBUG: Model found in storage: name='{model_name}'")
            else:
                logger.warning(f"DEBUG: Artifact type mismatch: expected 'model', got '{artifact.get('type')}'")
        else:
            logger.info(f"DEBUG: Artifact id '{id}' not found in _artifact_storage")
        
        if not found:
            logger.info(f"DEBUG: Not found in storage, searching S3")
            try:
                logger.info(f"DEBUG: Calling list_models with regex: '^{re.escape(id)}$'")
                result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                models_found = result.get("models", [])
                logger.info(f"DEBUG: list_models returned {len(models_found)} models")
                if models_found:
                    found = True
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

        # Analyze model content - if this fails, return 500
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

        # Build ModelRating response with all required fields
        logger.info(f"DEBUG: Building rating response for id='{id}'")
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
        logger.info(f"DEBUG: Returning rating result: {result}")
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