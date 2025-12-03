from __future__ import annotations

import re
import os
import random
import threading
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from botocore.exceptions import ClientError

from ..services.s3_service import (
    list_models,
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
from ..services.rating import run_scorer, alias, analyze_model_content
from ..services.artifact_storage import (
    save_artifact,
    get_artifact as get_artifact_from_db,
    get_generic_artifact_metadata,
    update_artifact as update_artifact_in_db,
    delete_artifact,
    list_all_artifacts,
)
from ..services.license_compatibility import (
    extract_model_license,
    extract_github_license,
    check_license_compatibility,
)

logger = logging.getLogger(__name__)

templates: Jinja2Templates | None = None
routes_registered = False

# Shared rating state (same as index.py)
_rating_lock = threading.Lock()
_rating_status: Dict[str, str] = {}
_rating_results: Dict[str, Any] = {}
_rating_locks: Dict[str, threading.Event] = {}
_rating_start_times: Dict[str, float] = {}
_artifact_storage: Dict[str, Dict[str, Any]] = {}


# Helper functions (same logic as index.py)
def sanitize_model_id_for_s3(model_id: str) -> str:
    """Sanitize model ID for S3 key (same logic as index.py)"""
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


def _get_model_name_for_s3(artifact_id: str) -> Optional[str]:
    """Get the model name from artifact_id for S3 lookups (same logic as index.py)"""
    try:
        artifact = get_generic_artifact_metadata("model", artifact_id)
        if not artifact:
            artifact = get_artifact_from_db(artifact_id)
        if artifact and artifact.get("type") == "model":
            name = artifact.get("name", "")
            if name:
                return sanitize_model_id_for_s3(name)
        return None
    except Exception as e:
        logger.debug(f"Error getting model name for S3: {str(e)}")
        return None


def _find_model_by_id(id: str) -> tuple[bool, Optional[str]]:
    """
    Find model by ID using same logic as index.py get_model_rate.
    Returns (found, model_name)
    """
    found = False
    model_name = None
    
    # Check database for artifact
    artifact = get_generic_artifact_metadata("model", id)
    if not artifact:
        artifact = get_artifact_from_db(id)
    if artifact:
        if artifact.get("type") == "model":
            found = True
            model_name = artifact.get("name", id)
    else:
        # Try to find artifact metadata in S3
        s3_metadata = find_artifact_metadata_by_id(id)
        if s3_metadata and s3_metadata.get("type") == "model":
            found = True
            model_name = s3_metadata.get("name")
            # Restore to database
            save_artifact(
                id,
                {
                    "name": model_name,
                    "type": "model",
                    "version": s3_metadata.get("version", "main"),
                    "id": id,
                    "url": s3_metadata.get("url", f"https://huggingface.co/{model_name}"),
                },
            )
    
    if not found:
        # Search S3 by model name
        try:
            result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
            models_found = result.get("models", [])
            if models_found:
                found = True
                model_name = models_found[0].get("name", id)
            else:
                # Try common versions
                common_versions = ["1.0.0", "main", "latest"]
                for v in common_versions:
                    try:
                        s3_key = f"models/{id}/{v}/model.zip"
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        found = True
                        model_name = id
                        break
                    except ClientError:
                        continue
        except Exception:
            pass
    
    return (found, model_name)


def _build_rating_response(model_name: str, rating: Dict[str, Any]) -> Dict[str, Any]:
    """Build ModelRating response with all required fields (same as index.py)"""
    return {
        "name": model_name,
        "category": alias(rating, "category") or "unknown",
        "net_score": round(float(alias(rating, "net_score", "NetScore", "netScore") or 0.0), 2),
        "ramp_up_time": round(float(alias(rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0), 2),
        "bus_factor": round(float(alias(rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0), 2),
        "performance_claims": round(float(alias(rating, "performance_claims", "PerformanceClaims", "score_performance_claims") or 0.0), 2),
        "license": round(float(alias(rating, "license", "License", "score_license") or 0.0), 2),
        "dataset_and_code_score": round(float(alias(rating, "dataset_code", "DatasetCode", "score_available_dataset_and_code") or 0.0), 2),
        "dataset_quality": round(float(alias(rating, "dataset_quality", "DatasetQuality", "score_dataset_quality") or 0.0), 2),
        "code_quality": round(float(alias(rating, "code_quality", "CodeQuality", "score_code_quality") or 0.0), 2),
        "reproducibility": round(float(alias(rating, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0), 2),
        "reviewedness": round(float(alias(rating, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0), 2),
        "treescore": round(float(alias(rating, "treescore", "Treescore", "score_treescore") or 0.0), 2),
    }


def set_templates(templates_instance: Jinja2Templates | None):
    global templates
    templates = templates_instance


def setup_app(
    app: FastAPI | None = None,
    templates_instance: Jinja2Templates | None = None,
) -> FastAPI:
    """
    Attach frontend routes to the provided FastAPI app. If no app is provided,
    a standalone FastAPI instance is created for local/frontend-only testing.
    """

    if app is None:
        app = FastAPI(title="ACME Frontend")
        frontend_root = Path(__file__).resolve().parents[2] / "frontend"
        templates_path = frontend_root / "templates"
        static_path = frontend_root / "static"
        if templates_path.exists():
            templates_instance = Jinja2Templates(directory=str(templates_path))
            # Add urlencode filters for URL encoding in templates
            if templates_instance.env:
                # urlencode for query parameters (uses + for spaces)
                templates_instance.env.filters['urlencode'] = lambda u: quote_plus(str(u)) if u else ''
                # pathencode for path segments (uses %20 for spaces)
                templates_instance.env.filters['pathencode'] = lambda u: quote(str(u), safe='') if u else ''
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    if templates_instance:
        set_templates(templates_instance)
        # Ensure urlencode filters are available
        if templates_instance.env:
            if 'urlencode' not in templates_instance.env.filters:
                templates_instance.env.filters['urlencode'] = lambda u: quote_plus(str(u)) if u else ''
            if 'pathencode' not in templates_instance.env.filters:
                templates_instance.env.filters['pathencode'] = lambda u: quote(str(u), safe='') if u else ''

    register_routes(app)
    return app


def register_routes(app: FastAPI):
    global routes_registered

    # Prevent duplicate registration when setup_app is called multiple times
    if routes_registered:
        return

    @app.get("/")
    def home(request: Request):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        return templates.TemplateResponse("home.html", {"request": request})

    @app.get("/directory")
    def directory(
        request: Request,
        q: str | None = None,
        name_regex: str | None = None,
        model_regex: str | None = None,
        version_range: str | None = None,
        version: str | None = None,
    ):
        """Directory endpoint - shows list of all models with artifact IDs"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        packages = []
        try:
            effective_version_range = version_range or version
            if q:
                version_pattern = r"^[v~^]?\d+\.\d+\.\d+([-~^]\d+\.\d+\.\d+)?$"
                if re.match(version_pattern, q.strip()):
                    effective_version_range = q.strip()
                    result = list_models(
                        version_range=effective_version_range, limit=1000
                    )
                else:
                    escaped_query = re.escape(q)
                    search_regex = f".*{escaped_query}.*"
                    result = list_models(
                        name_regex=search_regex,
                        version_range=effective_version_range,
                        limit=1000,
                    )
            elif name_regex or model_regex:
                result = list_models(
                    name_regex=name_regex,
                    model_regex=model_regex,
                    version_range=effective_version_range,
                    limit=1000,
                )
            else:
                result = list_models(version_range=effective_version_range, limit=1000)
            
            # Get all artifacts from database to map names to artifact IDs
            all_db_artifacts = list_all_artifacts()
            artifact_map = {}
            for artifact in all_db_artifacts:
                if artifact.get("type") == "model":
                    name = artifact.get("name", "")
                    artifact_id = artifact.get("id", "")
                    if name and artifact_id:
                        # Handle multiple artifacts with same name
                        if name not in artifact_map:
                            artifact_map[name] = []
                        artifact_map[name].append(artifact_id)
            
            # Add artifact IDs to packages
            for model in result.get("models", []):
                model_name = model.get("name", "")
                # Find artifact ID(s) for this model
                artifact_ids = artifact_map.get(model_name, [])
                if artifact_ids:
                    # Use first artifact ID if multiple exist
                    model["id"] = artifact_ids[0]
                else:
                    # Fallback: try to find from S3 metadata or use name as ID
                    model["id"] = model_name
            
            packages = result["models"]
        except Exception as e:
            print(f"Directory error: {e}")
            packages = []
        ctx = {
            "request": request,
            "packages": packages,
            "q": q or "",
            "name_regex": name_regex,
            "model_regex": model_regex,
            "version_range": effective_version_range,
            "version": version,
        }
        return templates.TemplateResponse("directory.html", ctx)

    @app.get("/rate")
    def rate_get(request: Request, name: str | None = None, id: str | None = None):
        """Rate endpoint - can search models and returns rating with all metrics"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        rating = None
        model_id = id
        model_name = name
        
        # If ID provided, find model name
        if model_id and not model_name:
            found, found_name = _find_model_by_id(model_id)
            if found:
                model_name = found_name or model_id
        
        # If name provided, find model ID
        if model_name and not model_id:
            # Search for artifact ID by name
            all_db_artifacts = list_all_artifacts()
            for artifact in all_db_artifacts:
                if artifact.get("name") == model_name and artifact.get("type") == "model":
                    model_id = artifact.get("id")
                    break
        
        # Use model_id as cache key if available, otherwise use model_name
        cache_key = model_id if model_id else model_name
        
        if model_name:
            try:
                # Check cache first (same as index.py)
                rating_raw = None
                if cache_key and cache_key in _rating_status:
                    status = _rating_status[cache_key]
                    if status == "completed":
                        rating_raw = _rating_results.get(cache_key)
                        if rating_raw:
                            logger.info(f"[RATE] Using cached rating for {cache_key}")
                
                # If not cached, compute rating
                if not rating_raw:
                    logger.info(f"[RATE] Computing rating for {model_name} (cache_key={cache_key})")
                    try:
                        rating_raw = analyze_model_content(model_name, suppress_errors=False)
                    except RuntimeError as e:
                        logger.error(f"[RATE] RuntimeError analyzing {model_name}: {str(e)}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to analyze model: {str(e)}",
                        )
                    except Exception as e:
                        logger.error(f"[RATE] Exception analyzing {model_name}: {str(e)}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail=f"The artifact rating system encountered an error: {str(e)}",
                        )
                    if not rating_raw:
                        raise HTTPException(
                            status_code=500,
                            detail="The artifact rating system encountered an error while computing at least one metric.",
                        )
                    # Cache the result if we have a cache key
                    if cache_key:
                        with _rating_lock:
                            _rating_results[cache_key] = rating_raw
                            _rating_status[cache_key] = "completed"
                
                rating = _build_rating_response(model_name, rating_raw)
                # Add model ID to rating if available
                if model_id:
                    rating["id"] = model_id
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error rating model {model_name}: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
                )
        ctx = {"request": request, "name": model_name or "", "id": model_id or "", "rating": rating}
        return templates.TemplateResponse("rate.html", ctx)

    @app.get("/artifact/model/{id}/rate")
    def rate_by_id(request: Request, id: str, name: str | None = None):
        """Rate endpoint using same logic as index.py"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        
        try:
            # Validate id format (same as index.py)
            if not id or not id.strip() or id == "{id}":
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Find model using same logic as index.py
            found, model_name = _find_model_by_id(id)
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Use model_name if available, otherwise use id
            effective_name = model_name if model_name else id
            
            # Check rating status (same as index.py)
            rating = None
            if id in _rating_status:
                status = _rating_status[id]
                if status == "completed":
                    rating = _rating_results.get(id)
                    if rating:
                        rating_dict = _build_rating_response(effective_name, rating)
                        ctx = {"request": request, "name": effective_name, "rating": rating_dict}
                        return templates.TemplateResponse("rate.html", ctx)
            
            # Analyze model content if not cached
            if not rating:
                rating = analyze_model_content(effective_name)
                if not rating:
                    raise HTTPException(
                        status_code=500,
                        detail="The artifact rating system encountered an error while computing at least one metric.",
                    )
                # Cache the result
                with _rating_lock:
                    _rating_results[id] = rating
                    _rating_status[id] = "completed"
            
            rating_dict = _build_rating_response(effective_name, rating)
            ctx = {"request": request, "name": effective_name, "rating": rating_dict}
            return templates.TemplateResponse("rate.html", ctx)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model rate for {id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}",
            )

    @app.get("/upload")
    def upload_get(request: Request, name: str | None = None, version: str = "main"):
        """Upload endpoint - uses ingest logic"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        ctx = {
            "request": request,
            "name": name or "",
            "version": version,
            "result": None,
        }
        return templates.TemplateResponse("upload.html", ctx)

    @app.post("/upload")
    async def upload_post(request: Request):
        """Upload endpoint - accepts ZIP file uploads and uses ingest logic"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        
        try:
            form = await request.form()
            file = form.get("file")
            name = form.get("name")
            version = form.get("version", "main")
            artifact_type = form.get("type", "model")
            
            # Check if file was uploaded
            if not file:
                result = {"error": "ZIP file is required."}
            elif not isinstance(file, UploadFile):
                result = {"error": "Invalid file upload."}
            elif not file.filename or not file.filename.endswith(".zip"):
                result = {"error": "Only ZIP files are supported."}
            else:
                # Read ZIP file content
                file_content = await file.read()
                
                # Extract model name from filename if not provided
                if not name or not name.strip():
                    name = file.filename.replace(".zip", "").strip()
                
                name = name.strip()
                
                # For models, upload ZIP and use ingest logic
                if artifact_type == "model":
                    try:
                        # Check if artifact already exists
                        existing = list_models(name_regex=f"^{re.escape(name)}$", limit=1)
                        if existing.get("models"):
                            result = {"error": "Artifact exists already."}
                        else:
                            # Upload the ZIP file to S3
                            upload_model(file_content, name, version)
                            
                            # Generate artifact ID (same as index.py)
                            artifact_id = str(random.randint(1000000000, 9999999999))
                            url = f"https://huggingface.co/{name}"
                            
                            # Initialize rating status
                            with _rating_lock:
                                _rating_status[artifact_id] = "pending"
                                _rating_locks[artifact_id] = threading.Event()
                                _rating_start_times[artifact_id] = time.time()
                            
                            # Store artifact metadata
                            artifact_data = {
                                "name": name,
                                "type": artifact_type,
                                "version": version,
                                "id": artifact_id,
                                "url": url,
                            }
                            save_artifact(artifact_id, artifact_data)
                            
                            # Store in S3 metadata
                            try:
                                store_artifact_metadata(artifact_id, name, artifact_type, version, url)
                            except Exception as s3_error:
                                logger.warning(f"Failed to store artifact metadata in S3: {str(s3_error)}")
                            
                            result = {
                                "message": "Upload successful",
                                "details": {
                                    "name": name,
                                    "type": artifact_type,
                                    "version": version,
                                    "id": artifact_id,
                                    "url": url,
                                },
                            }
                    except HTTPException as e:
                        error_detail = e.detail
                        if isinstance(error_detail, dict) and "error" in error_detail:
                            result = {
                                "error": error_detail.get("message", "Upload failed"),
                                "details": {
                                    "metric_scores": error_detail.get("metric_scores"),
                                    "model_id": name,
                                    "version": version,
                                    "ingestible": False,
                                },
                            }
                        else:
                            result = {
                                "error": (
                                    str(error_detail)
                                    if isinstance(error_detail, str)
                                    else "Upload failed"
                                ),
                                "details": {
                                    "model_id": name,
                                    "version": version,
                                    "ingestible": False,
                                },
                            }
                    except Exception as e:
                        logger.error(f"Error uploading model {name}: {str(e)}", exc_info=True)
                        result = {"error": f"Model upload failed: {str(e)}"}
                else:
                    result = {"error": "Only model artifacts are supported via ZIP upload."}
        except Exception as e:
            logger.error(f"Error in POST /upload endpoint: {str(e)}", exc_info=True)
            result = {"error": f"Upload failed: {str(e)}"}
        
        ctx = {
            "request": request,
            "name": name or "",
            "version": version,
            "result": result,
        }
        return templates.TemplateResponse("upload.html", ctx)

    @app.get("/admin")
    def admin(request: Request):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        return templates.TemplateResponse("admin.html", {"request": request})

    @app.get("/lineage")
    def lineage(request: Request, name: str | None = None, id: str | None = None, version: str | None = None):
        """Lineage endpoint - can search models and returns model relationships"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        lineage_data = None
        model_id = id
        model_name = name
        
        # If ID provided, find model name
        if model_id and not model_name:
            found, found_name = _find_model_by_id(model_id)
            if found:
                model_name = found_name or model_id
        
        # If name provided, find model ID
        if model_name and not model_id:
            # Search for artifact ID by name
            all_db_artifacts = list_all_artifacts()
            for artifact in all_db_artifacts:
                if artifact.get("name") == model_name and artifact.get("type") == "model":
                    model_id = artifact.get("id")
                    break
        
        if model_name:
            try:
                # Get model name for S3 lookup (same logic as index.py)
                s3_model_name = _get_model_name_for_s3(model_id) if model_id else None
                if not s3_model_name:
                    s3_model_name = sanitize_model_id_for_s3(model_name)
                
                # Try multiple versions (same as index.py)
                result = None
                versions_to_try = ["1.0.0", "main", "latest"]
                effective_version = version or "1.0.0"
                if effective_version not in versions_to_try:
                    versions_to_try.insert(0, effective_version)
                
                for v in versions_to_try:
                    try:
                        test_result = get_model_lineage_from_config(s3_model_name, v)
                        if "error" not in test_result:
                            result = test_result
                            break
                        # Try with original name if sanitized failed
                        if sanitize_model_id_for_s3(model_name) != s3_model_name:
                            test_result = get_model_lineage_from_config(model_name, v)
                            if "error" not in test_result:
                                result = test_result
                                break
                    except Exception:
                        continue
                
                if result and "error" not in result:
                    lineage_data = {
                        "model_id": model_id or model_name,
                        "model_name": model_name,
                        "lineage_metadata": result.get("lineage_metadata", {}),
                        "lineage_map": result.get("lineage_map", {}),
                        "config": result.get("config", {}),
                    }
                else:
                    # Return empty lineage instead of error
                    lineage_data = {
                        "model_id": model_id or model_name,
                        "model_name": model_name,
                        "lineage_metadata": {},
                        "lineage_map": {},
                        "config": {},
                    }
            except Exception as e:
                logger.error(f"Lineage error: {e}", exc_info=True)
                lineage_data = {"model_id": model_id or model_name, "model_name": model_name, "error": str(e)}
        ctx = {
            "request": request,
            "name": model_name or "",
            "id": model_id or "",
            "version": version or "1.0.0",
            "lineage": lineage_data,
        }
        return templates.TemplateResponse("lineage.html", ctx)

    @app.post("/lineage/sync-neptune")
    def sync_neptune():
        try:
            from ..services.s3_service import sync_model_lineage_to_neptune

            result = sync_model_lineage_to_neptune()
            return {"message": "Sync successful", "details": result}
        except Exception as e:
            return {"error": f"Sync failed: {str(e)}"}

    @app.get("/size-cost")
    def size_cost(
        request: Request, name: str | None = None, id: str | None = None, version: str | None = None
    ):
        """Size-cost endpoint - can search models and returns weights size and datasets size"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        size_data = None
        model_id = id
        model_name = name
        
        # If ID provided, find model name
        if model_id and not model_name:
            found, found_name = _find_model_by_id(model_id)
            if found:
                model_name = found_name or model_id
        
        # If name provided, find model ID
        if model_name and not model_id:
            # Search for artifact ID by name
            all_db_artifacts = list_all_artifacts()
            for artifact in all_db_artifacts:
                if artifact.get("name") == model_name and artifact.get("type") == "model":
                    model_id = artifact.get("id")
                    break
        
        if model_name:
            try:
                from ..services.s3_service import get_model_sizes

                # Get model name for S3 lookup
                s3_model_name = _get_model_name_for_s3(model_id) if model_id else None
                if not s3_model_name:
                    s3_model_name = sanitize_model_id_for_s3(model_name)

                effective_version = version or "1.0.0"
                result = get_model_sizes(s3_model_name, effective_version)
                size_data = {
                    "model_id": model_id or model_name,
                    "model_name": model_name,
                    "weights_size": result.get("weights", 0),
                    "datasets_size": result.get("datasets", 0),
                    "weights_size_mb": round(result.get("weights", 0) / (1024 * 1024), 2) if result.get("weights", 0) else 0,
                    "datasets_size_mb": round(result.get("datasets", 0) / (1024 * 1024), 2) if result.get("datasets", 0) else 0,
                    "full_size": result.get("full", 0),
                    "error": result.get("error"),
                }
            except Exception as e:
                print(f"Size cost error: {e}")
                size_data = {"model_id": model_id or model_name, "model_name": model_name, "error": str(e)}
        ctx = {"request": request, "name": model_name or "", "id": model_id or "", "size_data": size_data}
        return templates.TemplateResponse("size_cost.html", ctx)

    @app.get("/cost/{id}")
    def get_cost(request: Request, id: str, type: str = "model", dependency: bool = False):
        """Get artifact cost (simplified path matching spec)"""
        try:
            # Find artifact
            found, model_name = _find_model_by_id(id)
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Get model name for S3 lookup
            model_name_for_s3 = _get_model_name_for_s3(id)
            if not model_name_for_s3:
                model_name_for_s3 = sanitize_model_id_for_s3(id)
            
            # Get size in MB
            standalone_size_mb = 0.0
            for version in ["1.0.0", "main", "latest"]:
                sizes = get_model_sizes(model_name_for_s3, version)
                if "error" not in sizes:
                    size_bytes = sizes.get("full", 0)
                    if size_bytes > 0:
                        standalone_size_mb = size_bytes / (1024 * 1024)
                        break
            
            # Build response according to spec
            cost_response = {id: {"total_cost": standalone_size_mb}}
            if dependency:
                cost_response[id]["standalone_cost"] = standalone_size_mb
                # For now, total_cost with dependencies equals standalone (no dependency tracking)
                cost_response[id]["total_cost"] = standalone_size_mb
            
            return cost_response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting cost for {id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="The artifact cost calculator encountered an error.",
            )


    @app.get("/download/{model_id}/{version}")
    def download(model_id: str, version: str, component: str = "full"):
        try:
            file_content = download_model(model_id, version, component)
            if file_content:
                return Response(
                    content=file_content,
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"
                    },
                )
            else:
                return {"error": f"Failed to download {model_id} v{version}"}
        except Exception as e:
            return {"error": f"Download failed: {str(e)}"}

    @app.post("/admin/reset")
    def reset():
        try:
            result = reset_registry()
            return {"message": "Reset successful", "details": result}
        except Exception as e:
            return {"error": f"Reset failed: {str(e)}"}

    @app.get("/health")
    def health():
        """Health check endpoint (BASELINE)"""
        return Response(status_code=200)

    @app.get("/health/components")
    def health_components(request: Request, windowMinutes: int = 60, includeTimeline: bool = False):
        """Component health endpoint (NON-BASELINE)"""
        # Simplified implementation - return basic health status
        return {
            "components": [
                {
                    "id": "api",
                    "display_name": "API Server",
                    "status": "ok",
                    "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            ],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_minutes": windowMinutes,
        }

    @app.get("/artifact/{id}")
    def get_artifact_simple(request: Request, id: str, type: str = "model"):
        """Get artifact by ID (simplified path)"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        try:
            # Use same logic as index.py
            artifact = get_generic_artifact_metadata(type, id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == type:
                artifact_name = artifact.get("name", id)
                artifact_url = artifact.get("url", f"https://huggingface.co/{artifact_name}")
                artifact_version = artifact.get("version", "main")
                ctx = {
                    "request": request,
                    "artifact": {
                        "metadata": {
                            "name": artifact_name,
                            "id": id,
                            "type": type,
                        },
                        "data": {
                            "url": artifact_url,
                        },
                    },
                }
                return templates.TemplateResponse("directory.html", ctx)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting artifact {id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

    @app.put("/artifact/{id}")
    async def update_artifact_simple(request: Request, id: str, type: str = "model"):
        """Update artifact (simplified path)"""
        try:
            body = await request.json() if request.headers.get("content-type") == "application/json" else {}
            if "metadata" not in body or "data" not in body:
                raise HTTPException(status_code=400, detail="Missing required fields.")
            metadata = body.get("metadata", {})
            if metadata.get("id") != id:
                raise HTTPException(status_code=400, detail="ID mismatch.")
            # Check if artifact exists
            artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == type:
                url = body.get("data", {}).get("url", "")
                if url:
                    update_artifact_in_db(id, {
                        "name": metadata.get("name", artifact.get("name", id)),
                        "type": type,
                        "id": id,
                        "url": url,
                    })
                    return Response(status_code=200)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating artifact {id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail="Update failed.")

    @app.delete("/artifact/{id}")
    def delete_artifact_simple(request: Request, id: str, type: str = "model"):
        """Delete artifact (simplified path)"""
        try:
            artifact = get_artifact_from_db(id)
            if artifact and artifact.get("type") == type:
                delete_artifact(id)
                # Delete from S3 if model
                if type == "model":
                    model_name = artifact.get("name", id)
                    sanitized_name = sanitize_model_id_for_s3(model_name)
                    common_versions = ["1.0.0", "main", "latest"]
                    for version in common_versions:
                        try:
                            s3_key = f"models/{sanitized_name}/{version}/model.zip"
                            s3.delete_object(Bucket=ap_arn, Key=s3_key)
                        except ClientError:
                            continue
                return Response(status_code=200)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting artifact {id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

    @app.get("/byname/{name}")
    def get_by_name(request: Request, name: str):
        """Get artifacts by name (simplified path)"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        try:
            artifacts = []
            # Search database
            all_db_artifacts = list_all_artifacts()
            for artifact in all_db_artifacts:
                if artifact.get("name") == name:
                    artifacts.append({
                        "name": artifact.get("name", artifact.get("id")),
                        "id": artifact.get("id"),
                        "type": artifact.get("type", "model"),
                    })
            # Search S3 for models
            try:
                result = list_models(name_regex=f"^{re.escape(name)}$", limit=1000)
                for model in result.get("models", []):
                    if model.get("name") == name:
                        # Find artifact_id from database
                        artifact_id = None
                        for db_artifact in all_db_artifacts:
                            if db_artifact.get("name") == name and db_artifact.get("type") == "model":
                                artifact_id = db_artifact.get("id")
                                break
                        if artifact_id:
                            artifacts.append({
                                "name": name,
                                "id": artifact_id,
                                "type": "model",
                            })
            except Exception:
                pass
            if not artifacts:
                raise HTTPException(status_code=404, detail="No such artifact.")
            ctx = {"request": request, "artifacts": artifacts, "name": name}
            return templates.TemplateResponse("directory.html", ctx)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting artifacts by name {name}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="No such artifact.")

    @app.get("/license-check")
    def license_check_get(request: Request, id: str = None, github_url: str = None):
        """License check endpoint (GET for UI)"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        ctx = {
            "request": request,
            "id": id or "",
            "github_url": github_url or "",
            "result": None,
        }
        return templates.TemplateResponse("license-check.html", ctx)

    @app.post("/license-check")
    async def license_check_post(request: Request):
        """License check endpoint - Given GitHub URL and Model ID, assess license compatibility for fine-tune + inference"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        try:
            form = await request.form()
            model_id = form.get("id", "")
            github_url = form.get("github_url", "")
            
            if not model_id or not github_url:
                result = {"error": "Both model ID and GitHub URL are required."}
            else:
                # Find model
                found, model_name = _find_model_by_id(model_id)
                if not found:
                    result = {"error": "Artifact does not exist."}
                else:
                    # Get model name for license extraction
                    model_name_for_license = _get_model_name_for_s3(model_id)
                    if not model_name_for_license:
                        model_name_for_license = model_name or model_id
                    
                    # Extract licenses
                    model_license = extract_model_license(model_name_for_license)
                    if model_license is None:
                        result = {"error": "Model license not found."}
                    else:
                        github_license = extract_github_license(github_url)
                        if github_license is None:
                            result = {"error": "GitHub license not found."}
                        else:
                            # Use case is always "fine-tune+inference" per requirements
                            use_case = "fine-tune+inference"
                            compatibility_result = check_license_compatibility(
                                model_license, github_license, use_case
                            )
                            result = {
                                "compatible": compatibility_result.get("compatible", False),
                                "model_id": model_id,
                                "model_name": model_name,
                                "model_license": model_license,
                                "github_url": github_url,
                                "github_license": github_license,
                                "use_case": use_case,
                                "reason": compatibility_result.get("reason", ""),
                            }
        except Exception as e:
            logger.error(f"Error in license check: {str(e)}", exc_info=True)
            result = {"error": f"License check failed: {str(e)}"}
        
        ctx = {
            "request": request,
            "id": model_id or "",
            "github_url": github_url or "",
            "result": result,
        }
        return templates.TemplateResponse("license-check.html", ctx)

    @app.get("/audit/{id}")
    def get_audit(request: Request, id: str, type: str = "model"):
        """Get audit trail for artifact (simplified path)"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        try:
            # Check if artifact exists
            artifact = get_generic_artifact_metadata(type, id)
            if not artifact:
                artifact = get_artifact_from_db(id)
            if not artifact or artifact.get("type") != type:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            
            # Build simple audit trail
            audit_entries = []
            artifact_name = artifact.get("name", id)
            
            # Get creation date from S3 if model
            if type == "model":
                try:
                    model_name_for_s3 = _get_model_name_for_s3(id)
                    if not model_name_for_s3:
                        model_name_for_s3 = sanitize_model_id_for_s3(id)
                    version = artifact.get("version", "1.0.0")
                    s3_key = f"models/{model_name_for_s3}/{version}/model.zip"
                    obj = s3.head_object(Bucket=ap_arn, Key=s3_key)
                    last_modified = obj.get("LastModified")
                    if last_modified:
                        create_date = last_modified.isoformat().replace("+00:00", "Z")
                    else:
                        create_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                except Exception:
                    create_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                
                # Add CREATE entry
                audit_entries.append({
                    "user": {"name": "System", "is_admin": True},
                    "date": create_date,
                    "artifact": {
                        "name": artifact_name,
                        "id": id,
                        "type": type,
                    },
                    "action": "CREATE",
                })
            
            ctx = {
                "request": request,
                "id": id,
                "type": type,
                "audit_entries": audit_entries,
            }
            return templates.TemplateResponse("directory.html", ctx)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting audit for {id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")

    @app.post("/search")
    async def search_by_regex(request: Request):
        """Search artifacts by regex (simplified path)"""
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        try:
            form = await request.form()
            regex = form.get("regex", "")
            if not regex:
                # Try JSON body
                try:
                    body = await request.json()
                    regex = body.get("regex", "")
                except:
                    pass
            
            if not regex:
                raise HTTPException(status_code=400, detail="Regex parameter is required.")
            
            # Search models
            artifacts = []
            try:
                result = list_models(name_regex=regex, limit=1000)
                for model in result.get("models", []):
                    # Find artifact_id from database
                    all_db_artifacts = list_all_artifacts()
                    for db_artifact in all_db_artifacts:
                        if db_artifact.get("name") == model.get("name") and db_artifact.get("type") == "model":
                            artifacts.append({
                                "name": model.get("name"),
                                "id": db_artifact.get("id"),
                                "type": "model",
                            })
                            break
            except Exception as e:
                logger.warning(f"Error searching models: {str(e)}")
            
            # Search database for other artifact types
            all_db_artifacts = list_all_artifacts()
            for artifact in all_db_artifacts:
                if artifact.get("type") != "model":
                    artifact_name = artifact.get("name", "")
                    if regex and re.search(regex, artifact_name, re.IGNORECASE):
                        artifacts.append({
                            "name": artifact_name,
                            "id": artifact.get("id"),
                            "type": artifact.get("type", "model"),
                        })
            
            if not artifacts:
                raise HTTPException(status_code=404, detail="No artifact found under this regex.")
            
            ctx = {"request": request, "artifacts": artifacts, "regex": regex}
            return templates.TemplateResponse("directory.html", ctx)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error searching artifacts: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail="Search failed.")

    @app.get("/tracks")
    def get_tracks():
        """Get planned tracks"""
        try:
            planned_tracks = ["Performance track", "Access control track"]
            return {"plannedTracks": planned_tracks}
        except Exception as e:
            logger.error(f"Error retrieving tracks: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="The system encountered an error while retrieving the student's track information.",
            )

    routes_registered = True


def main():
    port = int(os.getenv("PORT", "8000"))
    app = setup_app()
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
