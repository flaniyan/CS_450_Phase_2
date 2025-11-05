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
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from botocore.exceptions import ClientError
from .routes.index import router as api_router
from .services.s3_service import list_models, upload_model, download_model, reset_registry, get_model_lineage_from_config, get_model_sizes, s3, ap_arn, model_ingestion
from .services.rating import run_scorer, alias, analyze_model_content
from .services.license_compatibility import extract_model_license, extract_github_license, check_license_compatibility

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
app = FastAPI(title="ACME API (Python)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
@app.middleware("http")
async def log_request_body(request: Request, call_next):
    try:
        logger.info(f"=== MIDDLEWARE: {request.method} {request.url.path} ===")
        if request.url.path == "/authenticate":
            logger.info(f"=== AUTHENTICATE REQUEST DETECTED ===")
            body = await request.body()
            logger.info(f"=== RAW REQUEST BODY ===")
            logger.info(f"Body bytes: {body}")
            logger.info(f"Body length: {len(body)}")
            logger.info(f"Content-Type: {request.headers.get('content-type')}")
            logger.info(f"Method: {request.method}")
            logger.info(f"Path: {request.url.path}")
            # Reset body for FastAPI to parse
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        response = await call_next(request)
        logger.info(f"=== MIDDLEWARE: Response status {response.status_code} ===")
        return response
    except Exception as e:
        logger.error(f"=== MIDDLEWARE ERROR: {str(e)} ===", exc_info=True)
        raise
_artifact_storage = {}
def verify_auth_token(request: Request) -> bool:
    auth_header = request.headers.get("X-Authorization", "")
    if not auth_header:
        return False
    return auth_header.lower().startswith("bearer ")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/health/components")
def health_components(windowMinutes: int = 60, includeTimeline: bool = False):
    if windowMinutes < 5 or windowMinutes > 1440:
        raise HTTPException(status_code=400, detail="windowMinutes must be between 5 and 1440")
    component = {
        "id": "validator-service",
        "display_name": "Validator Service",
        "status": "ok",
        "observed_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    response = {
        "components": [component],
        "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "window_minutes": windowMinutes
    }
    if includeTimeline:
        component["timeline"] = []
    return response

@app.put("/authenticate")
def authenticate(auth_request: AuthRequest, request: Request):
    try:
        logger.info(f"=== AUTHENTICATE ENDPOINT CALLED ===")
        logger.info(f"Received authenticate request with headers: {dict(request.headers)}")
        logger.info(f"Request body received - user: {auth_request.user.name if auth_request.user else None}")
        logger.info(f"Request body received - has secret: {bool(auth_request.secret)}")
        if not auth_request.user or not auth_request.secret:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly.")
        auth_enabled = True
        if not auth_enabled:
            raise HTTPException(status_code=501, detail="This system does not support authentication.")
        if (auth_request.user.name == "ece30861defaultadminuser" and 
            auth_request.secret.password == "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"):
            token = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0.example"
            return token
        else:
            raise HTTPException(status_code=401, detail="The user or password is invalid.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly.")

@app.post("/login")
def login(auth_request: AuthRequest, request: Request):
    """Login endpoint - alias for authenticate endpoint"""
    return authenticate(auth_request, request)

@app.post("/artifacts")
async def list_artifacts(request: Request, offset: str = None):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if not isinstance(body, list):
            raise HTTPException(status_code=400, detail="Request body must be an array of ArtifactQuery objects")
        results = []
        for query in body:
            if not isinstance(query, dict):
                raise HTTPException(status_code=400, detail="Each query must be an object")
            name = query.get("name")
            if not name:
                raise HTTPException(status_code=400, detail="Missing required field 'name' in artifact_query")
            types_filter = query.get("types", [])
            if name == "*":
                result = list_models(limit=1000)
                if result is None:
                    result = {"models": []}
                models = result.get("models") or []
                for model in models:
                    if isinstance(model, dict) and (not types_filter or "model" in types_filter):
                        results.append({
                            "name": model.get("name", ""),
                            "id": model.get("id", model.get("name", "")),
                            "type": "model"
                        })
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_type_stored = artifact.get("type", "")
                    if not types_filter or artifact_type_stored in types_filter:
                        results.append({
                            "name": artifact.get("name", artifact_id),
                            "id": artifact_id,
                            "type": artifact_type_stored
                        })
            else:
                escaped_name = re.escape(name)
                name_pattern = f"^{escaped_name}$"
                result = list_models(name_regex=name_pattern, limit=1000)
                if result is None:
                    result = {"models": []}
                models = result.get("models") or []
                for model in models:
                    if isinstance(model, dict) and (not types_filter or "model" in types_filter):
                        results.append({
                            "name": model.get("name", ""),
                            "id": model.get("id", model.get("name", "")),
                            "type": "model"
                        })
                for artifact_id, artifact in _artifact_storage.items():
                    artifact_name = artifact.get("name", artifact_id)
                    artifact_type_stored = artifact.get("type", "")
                    if re.match(name_pattern, artifact_name) and (not types_filter or artifact_type_stored in types_filter):
                        results.append({
                            "name": artifact_name,
                            "id": artifact_id,
                            "type": artifact_type_stored
                        })
        if len(results) > 10000:
            raise HTTPException(status_code=413, detail="Too many artifacts returned")
        response = Response(
            content=json.dumps(results),
            media_type="application/json"
        )
        response.headers["offset"] = offset if offset else "0"
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"There is missing field(s) in the artifact_query or it is formed improperly, or is invalid: {str(e)}")

@app.delete("/reset")
def reset_system(request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        global _artifact_storage
        _artifact_storage.clear()
        result = reset_registry()
        return {"message": "Registry is reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")

@app.get("/artifact/byName/{name}")
def get_artifact_by_name(name: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        escaped_name = re.escape(name)
        name_pattern = f"^{escaped_name}$"
        result = list_models(name_regex=name_pattern, limit=1000)
        artifacts = []
        for model in result.get("models", []):
            artifacts.append({"name": model["name"], "id": model.get("id", model["name"]), "type": "model"})
        for artifact_id, artifact in _artifact_storage.items():
            if artifact.get("name") == name:
                artifacts.append({"name": artifact.get("name", artifact_id), "id": artifact_id, "type": artifact.get("type", "model")})
        if not artifacts:
            raise HTTPException(status_code=404, detail="No such artifact.")
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"There is missing field(s) in the artifact_name or it is formed improperly, or is invalid: {str(e)}")

@app.post("/artifact/byRegEx")
async def search_artifacts_by_regex(request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if not isinstance(body, dict):
            form = await request.form()
            body = dict(form)
        if isinstance(body, list) and len(body) > 0:
            search_criteria = body[0]
        elif isinstance(body, dict):
            search_criteria = body
        else:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid")
        regex_pattern = search_criteria.get("regex")
        if not regex_pattern:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid")
        result = list_models(name_regex=regex_pattern, limit=1000)
        artifacts = []
        for model in result.get("models", []):
            artifacts.append({"name": model["name"], "id": model.get("id", model["name"]), "type": "model"})
        for artifact_id, artifact in _artifact_storage.items():
            artifact_name = artifact.get("name", artifact_id)
            if re.search(regex_pattern, artifact_name):
                artifacts.append({"name": artifact_name, "id": artifact_id, "type": artifact.get("type", "model")})
        if not artifacts:
            raise HTTPException(status_code=404, detail="No artifact found under this regex.")
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid: {str(e)}")

@app.get("/artifacts/{artifact_type}/{id}")
def get_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if artifact_type == "model":
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                return {"metadata": {"name": artifact.get("name", id), "id": id, "type": artifact_type}, "data": {"url": artifact.get("url", f"https://huggingface.co/{artifact.get('name', id)}")}}
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
                            error_code = e.response.get('Error', {}).get('Code', '')
                            if error_code == 'NoSuchKey' or error_code == '404':
                                continue
                            else:
                                print(f"Unexpected error checking {s3_key}: {error_code}")
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
                        error_code = e.response.get('Error', {}).get('Code', '')
                        if error_code == 'NoSuchKey' or error_code == '404':
                            continue
                        else:
                            print(f"Unexpected error checking {s3_key}: {error_code}")
            if not found:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            model = {"name": id, "version": version}
            return {"metadata": {"name": model["name"], "id": id, "type": artifact_type}, "data": {"url": f"https://huggingface.co/{id}"}}
        else:
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                return {"metadata": {"name": artifact.get("name", id), "id": id, "type": artifact_type}, "data": {"url": artifact.get("url", f"https://example.com/{artifact_type}/{id}")}}
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get artifact: {str(e)}")

@app.post("/artifact/{artifact_type}")
async def create_artifact_by_type(artifact_type: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        url = body.get("url", "")
        if not url:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_data or it is formed improperly (must include a single url).")
        if artifact_type == "model":
            if "huggingface.co" in url:
                model_id = url.split("/")[-1] if "/" in url else url
                version = body.get("version", "main")
                try:
                    existing = list_models(name_regex=f"^{re.escape(model_id)}$", limit=1)
                    if existing.get("models"):
                        raise HTTPException(status_code=409, detail="Artifact exists already.")
                except HTTPException:
                    raise
                except:
                    pass
                try:
                    model_ingestion(model_id, version)
                    rating = analyze_model_content(model_id)
                    net_score = alias(rating, "net_score", "NetScore", "netScore") or 0.0
                    if net_score < 0.5:
                        raise HTTPException(status_code=424, detail="Artifact is not registered due to the disqualified rating.")
                    artifact_id = str(random.randint(1000000000, 9999999999))
                    return Response(
                        content=json.dumps({
                            "metadata": {"name": model_id, "id": artifact_id, "type": artifact_type},
                            "data": {"url": url}
                        }),
                        media_type="application/json",
                        status_code=201
                    )
                except HTTPException:
                    raise
                except Exception as e:
                    artifact_id = str(random.randint(1000000000, 9999999999))
                    return Response(
                        content=json.dumps({
                            "metadata": {"name": model_id, "id": artifact_id, "type": artifact_type},
                            "data": {"url": url}
                        }),
                        media_type="application/json",
                        status_code=201
                    )
            else:
                model_id = url.split("/")[-1] if url else f"{artifact_type}-new"
                artifact_id = str(random.randint(1000000000, 9999999999))
                return Response(
                    content=json.dumps({
                        "metadata": {"name": model_id, "id": artifact_id, "type": artifact_type},
                        "data": {"url": url}
                    }),
                    media_type="application/json",
                    status_code=201
                )
        else:
            global _artifact_storage
            for existing_id, existing_artifact in _artifact_storage.items():
                if existing_artifact.get("url") == url and existing_artifact.get("type") == artifact_type:
                    raise HTTPException(status_code=409, detail="Artifact exists already.")
            artifact_id = str(random.randint(1000000000, 9999999999))
            artifact_name = url.split("/")[-1] if url else f"{artifact_type}-new"
            _artifact_storage[artifact_id] = {"name": artifact_name, "type": artifact_type, "id": artifact_id, "url": url}
            return Response(
                content=json.dumps({
                    "metadata": {"name": artifact_name, "id": artifact_id, "type": artifact_type},
                    "data": {"url": url}
                }),
                media_type="application/json",
                status_code=201
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"There is missing field(s) in the artifact_data or it is formed improperly (must include a single url): {str(e)}")

@app.put("/artifacts/{artifact_type}/{id}")
async def update_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if "metadata" not in body or "data" not in body:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        metadata = body.get("metadata", {})
        if metadata.get("id") != id:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        if not metadata.get("name"):
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        if artifact_type == "model":
            found = False
            common_versions = ["1.0.0", "main", "latest"]
            for v in common_versions:
                try:
                    s3_key = f"models/{id}/{v}/model.zip"
                    s3.head_object(Bucket=ap_arn, Key=s3_key)
                    found = True
                    break
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == 'NoSuchKey' or error_code == '404':
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
        else:
            global _artifact_storage
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == artifact_type:
                    data = body.get("data", {})
                    url = data.get("url", artifact.get("url", ""))
                    _artifact_storage[id] = {"name": metadata.get("name", artifact.get("name", id)), "type": artifact_type, "id": id, "url": url}
                    return Response(status_code=200)
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
        return Response(status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update artifact: {str(e)}")

@app.delete("/artifacts/{artifact_type}/{id}")
def delete_artifact(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
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
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == 'NoSuchKey' or error_code == '404':
                        continue
            if deleted_count == 0:
                try:
                    result = list_models(name_regex=f"^{re.escape(id)}$", limit=1000)
                    if result.get("models"):
                        versions_to_try = [model["version"] for model in result["models"]]
                        for version in versions_to_try:
                            s3_key = f"models/{id}/{version}/model.zip"
                            try:
                                s3.head_object(Bucket=ap_arn, Key=s3_key)
                                s3.delete_object(Bucket=ap_arn, Key=s3_key)
                                deleted_count += 1
                                deleted = True
                            except ClientError as e:
                                error_code = e.response.get('Error', {}).get('Code', '')
                                if error_code == 'NoSuchKey' or error_code == '404':
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
                        error_code = e.response.get('Error', {}).get('Code', '')
                        if error_code == 'NoSuchKey' or error_code == '404':
                            continue
        if deleted:
            return Response(status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete artifact: {str(e)}")

@app.get("/artifact/{artifact_type}/{id}/cost")
def get_artifact_cost(artifact_type: str, id: str, dependency: bool = False, request: Request = None):
    if request is not None:
        if not verify_auth_token(request):
            raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if artifact_type not in ["model", "dataset", "code"]:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        if not re.match(r'^[a-zA-Z0-9\-]+$', id):
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
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
                total_size_mb = standalone_size_mb
                lineage_result = get_model_lineage_from_config(id, "1.0.0")
                if "error" not in lineage_result:
                    lineage_map = lineage_result.get("lineage_map", {})
                    for dep_id, dep_metadata in lineage_map.items():
                        if dep_id != id:
                            try:
                                dep_sizes = get_model_sizes(dep_id, "1.0.0")
                                if "error" not in dep_sizes:
                                    dep_size_mb = dep_sizes.get("full", 0) / (1024 * 1024)
                                    total_size_mb += dep_size_mb
                            except Exception:
                                pass
                result = {id: {"standalone_cost": round(standalone_size_mb, 2), "total_cost": round(total_size_mb, 2)}}
            else:
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
                return {id: {"standalone_cost": standalone_cost, "total_cost": standalone_cost}}
            else:
                return {id: {"total_cost": standalone_cost}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"The artifact cost calculator encountered an error: {str(e)}")

@app.get("/artifact/{artifact_type}/{id}/audit")
def get_artifact_audit(artifact_type: str, id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if artifact_type not in ["model", "dataset", "code"]:
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        if not re.match(r'^[a-zA-Z0-9\-]+$', id):
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid.")
        if artifact_type == "model":
            escaped_name = re.escape(id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1)
            version = None
            if result.get("models"):
                version = result["models"][0]["version"]
            else:
                versions = ["1.0.0", "main", "latest"]
                for v in versions:
                    try:
                        s3_key = f"models/{id}/{v}/model.zip"
                        s3.head_object(Bucket=ap_arn, Key=s3_key)
                        version = v
                        break
                    except ClientError:
                        continue
            if not version:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            s3_key = f"models/{id}/{version}/model.zip"
            try:
                obj = s3.head_object(Bucket=ap_arn, Key=s3_key)
                last_modified = obj.get('LastModified')
                if last_modified:
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    last_modified_str = last_modified.isoformat().replace('+00:00', 'Z')
                else:
                    last_modified_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                audit_log = [{"user": {"name": "system", "is_admin": False}, "date": last_modified_str, "artifact": {"name": id, "id": id, "type": artifact_type}, "action": "CREATE"}]
                return audit_log
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise HTTPException(status_code=404, detail="Artifact does not exist.")
                raise HTTPException(status_code=500, detail=f"Failed to get artifact audit: {str(e)}")
        else:
            if id in _artifact_storage:
                artifact = _artifact_storage[id]
                if artifact.get("type") == artifact_type:
                    return [{"user": {"name": "system", "is_admin": False}, "date": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), "artifact": {"name": artifact.get("name", id), "id": id, "type": artifact_type}, "action": "CREATE"}]
            raise HTTPException(status_code=404, detail="Artifact does not exist.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get artifact audit: {str(e)}")

@app.get("/artifact/model/{id}/rate")
def get_model_rate(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if not re.match(r'^[a-zA-Z0-9\-]+$', id):
            raise HTTPException(status_code=400, detail="There is missing field(s) in the artifact_id or it is formed improperly, or is invalid.")
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
        rating = analyze_model_content(id)
        result = {
            "name": id,
            "category": alias(rating, "category") or "unknown",
            "net_score": alias(rating, "net_score", "NetScore", "netScore") or 0.0,
            "net_score_latency": alias(rating, "net_score_latency") or 0.0,
            "ramp_up_time": alias(rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0,
            "ramp_up_time_latency": alias(rating, "ramp_up_time_latency") or 0.0,
            "bus_factor": alias(rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0,
            "bus_factor_latency": alias(rating, "bus_factor_latency") or 0.0,
            "performance_claims": alias(rating, "performance_claims", "PerformanceClaims", "score_performance_claims") or 0.0,
            "performance_claims_latency": alias(rating, "performance_claims_latency") or 0.0,
            "license": alias(rating, "license", "License", "score_license") or 0.0,
            "license_latency": alias(rating, "license_latency") or 0.0,
            "dataset_and_code_score": alias(rating, "dataset_code", "DatasetCode", "score_available_dataset_and_code") or 0.0,
            "dataset_and_code_score_latency": alias(rating, "dataset_and_code_score_latency") or 0.0,
            "dataset_quality": alias(rating, "dataset_quality", "DatasetQuality", "score_dataset_quality") or 0.0,
            "dataset_quality_latency": alias(rating, "dataset_quality_latency") or 0.0,
            "code_quality": alias(rating, "code_quality", "CodeQuality", "score_code_quality") or 0.0,
            "code_quality_latency": alias(rating, "code_quality_latency") or 0.0,
            "reproducibility": alias(rating, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0,
            "reproducibility_latency": alias(rating, "reproducibility_latency") or 0.0,
            "reviewedness": alias(rating, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0,
            "reviewedness_latency": alias(rating, "reviewedness_latency") or 0.0,
            "tree_score": alias(rating, "treescore", "Treescore", "score_treescore") or 0.0,
            "tree_score_latency": alias(rating, "tree_score_latency") or 0.0,
            "size_score": {
                "raspberry_pi": alias(rating, "size_score", "raspberry_pi") or 0.0,
                "jetson_nano": alias(rating, "size_score", "jetson_nano") or 0.0,
                "desktop_pc": alias(rating, "size_score", "desktop_pc") or 0.0,
                "aws_server": alias(rating, "size_score", "aws_server") or 0.0
            },
            "size_score_latency": alias(rating, "size_score_latency") or 0.0
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"The artifact rating system encountered an error while computing at least one metric: {str(e)}")

@app.get("/artifact/model/{id}/lineage")
def get_model_lineage(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if not re.match(r'^[a-zA-Z0-9\-]+$', id):
            raise HTTPException(status_code=400, detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.")
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
        result = get_model_lineage_from_config(id, "1.0.0")
        if "error" in result:
            error_msg = result["error"].lower()
            if "not found" in error_msg or "does not exist" in error_msg or "no such" in error_msg:
                raise HTTPException(status_code=404, detail="Artifact does not exist.")
            else:
                raise HTTPException(status_code=400, detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.")
        lineage_map = result.get("lineage_map", {})
        nodes = []
        edges = []
        for model_id, metadata in lineage_map.items():
            nodes.append({"artifact_id": model_id, "name": metadata.get("name", model_id), "source": metadata.get("source", "config_json")})
            if "dependencies" in metadata or "relationships" in metadata:
                deps = metadata.get("dependencies", []) or metadata.get("relationships", [])
                for dep in deps:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id") or dep.get("artifact_id")
                        relationship = dep.get("relationship", "dependency")
                        if dep_id:
                            edges.append({
                                "from_node_artifact_id": dep_id,
                                "to_node_artifact_id": model_id,
                                "relationship": relationship
                            })
        return {"nodes": nodes, "edges": edges}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="The lineage graph cannot be computed because the artifact metadata is missing or malformed.")

@app.post("/artifact/model/{id}/license-check")
async def check_model_license(id: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(status_code=403, detail="Authentication failed due to invalid or missing AuthenticationToken")
    try:
        if not re.match(r'^[a-zA-Z0-9\-]+$', id):
            raise HTTPException(status_code=400, detail="The license check request is malformed or references an unsupported usage context.")
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
            raise HTTPException(status_code=404, detail="The artifact or GitHub project could not be found.")
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if not isinstance(body, dict):
            form = await request.form()
            body = dict(form)
        github_url = body.get("github_url", "")
        if not github_url:
            raise HTTPException(status_code=400, detail="The license check request is malformed or references an unsupported usage context.")
        use_case = body.get("use_case", "fine-tune+inference")
        try:
            model_license = extract_model_license(id)
            if model_license is None:
                raise HTTPException(status_code=404, detail="The artifact could not be found.")
            github_license = extract_github_license(github_url)
            if github_license is None:
                raise HTTPException(status_code=404, detail="The GitHub project could not be found.")
            compatibility_result = check_license_compatibility(model_license, github_license, use_case)
            return {"compatible": compatibility_result.get("compatible", False)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail="External license information could not be retrieved.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"License check failed: {str(e)}")

@app.get("/tracks")
def get_tracks():
    try:
        planned_tracks = [
            "Performance track",
            "Access Control Track"
        ]
        return {"plannedTracks": planned_tracks}
    except Exception:
        raise HTTPException(status_code=500, detail="The system encountered an error while retrieving the student's track information.")
#@app.get("/")
#def get_root(request: Request):
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

@app.get("/ingest")
def get_artifact_ingest(name: str = None, version: str = "main", artifact_type: str = "model"):
    try:
        if name:
            if artifact_type == "model":
                result = model_ingestion(name, version)
                return {"message": "Ingest successful", "details": result}
            else:
                global _artifact_storage
                artifact_id = str(random.randint(1000000000, 9999999999))
                url = f"https://example.com/{artifact_type}/{name}"
                _artifact_storage[artifact_id] = {"name": name, "type": artifact_type, "version": version, "id": artifact_id, "url": url}
                return {"message": "Ingest successful", "details": {"name": name, "type": artifact_type, "version": version, "id": artifact_id, "url": url}}
        else:
            return {"message": "Provide name parameter to ingest artifact"}
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}, 500

@app.post("/ingest")
async def post_artifact_ingest(request: Request):
    try:
        form = await request.form()
        name = form.get("name")
        version = form.get("version", "main")
        artifact_type = form.get("type", form.get("artifact_type", "model"))
        if not name:
            body = await request.json() if request.headers.get("content-type") == "application/json" else {}
            if not body:
                body = dict(form)
            name = body.get("name") or body.get("model_id")
            version = body.get("version", version)
            artifact_type = body.get("type", body.get("artifact_type", "model"))
        if name:
            if artifact_type == "model":
                result = model_ingestion(name, version)
                return {"message": "Ingest successful", "details": result}
            else:
                global _artifact_storage
                artifact_id = str(random.randint(1000000000, 9999999999))
                url = f"https://example.com/{artifact_type}/{name}"
                _artifact_storage[artifact_id] = {"name": name, "type": artifact_type, "version": version, "id": artifact_id, "url": url}
                return {"message": "Ingest successful", "details": {"name": name, "type": artifact_type, "version": version, "id": artifact_id, "url": url}}
        else:
            return {"error": "Name parameter is required"}, 400
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}, 500
#@app.get("/artifact/directory")
#def get_artifact_directory(q: str = None, name_regex: str = None, model_regex: str = None, version_range: str = None, version: str = None):
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
#@app.get("/artifact")
#def get_artifacts():
#    try:
#        from .services.s3_service import list_models
#        result = list_models(limit=1000)
#        artifacts = []
#        for model in result.get("models", []):
#            artifacts.append({"metadata": {"name": model["name"], "id": model.get("id", model["name"]), "type": "model"}, "data": {"version": model.get("version", "1.0.0")}})
#        return {"artifacts": artifacts, "total": len(artifacts), "next_token": result.get("next_token")}
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to get artifacts: {str(e)}")
#@app.get("/artifact/{artifact_type}")
#def get_artifacts_by_type(artifact_type: str):
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
#@app.post("/upload")
#async def upload_artifact_model(request: Request, file: UploadFile = File(...), model_id: str = None, version: str = None):
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
#@app.get("/artifact/model/{id}/upload-url")
#def get_upload_url(id: str, version: str = "1.0.0", expires_in: int = 3600):
#    try:
#        from .services.s3_service import get_presigned_upload_url
#        result = get_presigned_upload_url(id, version, expires_in)
#        return result
#    except HTTPException:
#        raise
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")
#@app.post("/artifact/model/{id}/upload")
#async def upload_artifact_model_by_id(id: str, request: Request, file: UploadFile = File(...), version: str = None):
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
#@app.get("/artifact/model/{id}/download")
#def download_artifact_model(id: str, version: str = "1.0.0", component: str = "full"):
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
#@app.get("/admin")
#def get_admin(request: Request):
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
app.include_router(api_router, prefix="/api")
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None
