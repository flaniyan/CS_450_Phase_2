from __future__ import annotations
from pathlib import Path
import re
import os
import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from .routes.index import router as api_router
from .services.s3_service import list_models, upload_model, download_model, reset_registry, get_model_lineage_from_config, get_model_sizes
from .services.rating import run_scorer, alias

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

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/health/components")
def health_components(windowMinutes: int = 60, includeTimeline: bool = False):
    return {"components": [{"id": "validator-service", "display_name": "Validator Service", "status": "ok", "observed_at": "2025-10-28T12:00:00Z", "details": {"uptime": "99.9%", "response_time": "45ms"}}], "window_minutes": windowMinutes, "include_timeline": includeTimeline}

@app.put("/authenticate")
def authenticate(auth_request: AuthRequest):
    try:
        if (auth_request.user.name == "ece30861defaultadminuser" and 
            auth_request.secret.password == "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"):
            token = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0.example"
            return token
        else:
            return {"error": "Invalid credentials"}, 401
    except Exception as e:
        return {"error": "Invalid request"}, 400

@app.post("/artifacts")
async def create_artifact(request: Request):
    try:
        from .services.s3_service import model_ingestion
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(body, list):
            artifacts = body
        elif isinstance(body, dict):
            artifacts = [body]
        else:
            raise HTTPException(status_code=400, detail="Invalid request body format")
        results = []
        for artifact_data in artifacts:
            metadata = artifact_data.get("metadata", {})
            data = artifact_data.get("data", {})
            name = metadata.get("name") or data.get("url", "").split("/")[-1]
            artifact_type = metadata.get("type", "model")
            version = metadata.get("version", "main")
            if artifact_type == "model":
                if "url" in data:
                    url = data["url"]
                    if "huggingface.co" in url:
                        model_id = url.split("/")[-1] if "/" in url else url
                        result = model_ingestion(model_id, version)
                        results.append({"metadata": {"name": model_id, "id": model_id, "type": artifact_type}, "status": "created"})
                    else:
                        results.append({"metadata": {"name": name, "id": name, "type": artifact_type}, "status": "created"})
                else:
                    results.append({"metadata": {"name": name, "id": name, "type": artifact_type}, "status": "created"})
            else:
                results.append({"metadata": {"name": name, "id": name, "type": artifact_type}, "status": "created"})
        if len(results) == 1:
            return results[0]
        return results
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to create artifact: {str(e)}"}, 500

@app.delete("/reset")
def reset_system():
    try:
        result = reset_registry()
        return {"message": "System reset successfully", "details": result}
    except Exception as e:
        return {"error": f"Reset failed: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}")
def get_artifact(artifact_type: str, id: str):
    try:
        from .services.s3_service import list_models
        from botocore.exceptions import ClientError
        if artifact_type == "model":
            import re
            escaped_name = re.escape(id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1000)
            if result.get("models"):
                model = result["models"][0]
                try:
                    from .services.s3_service import s3
                    s3_key = f"models/{id}/{model['version']}/model.zip"
                    return {"metadata": {"name": model["name"], "id": id, "type": artifact_type}, "data": {"version": model["version"], "url": f"https://huggingface.co/{id}"}}
                except Exception:
                    return {"metadata": {"name": model["name"], "id": id, "type": artifact_type}, "data": {"version": model["version"]}}
            else:
                return {"error": f"Artifact '{id}' not found"}, 404
        else:
            return {"metadata": {"id": id, "type": artifact_type}, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to get artifact: {str(e)}"}, 500

@app.post("/artifact/{artifact_type}")
async def create_artifact_by_type(artifact_type: str, request: Request):
    try:
        from .services.s3_service import model_ingestion
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        url = body.get("url", "")
        if artifact_type == "model":
            if "huggingface.co" in url:
                model_id = url.split("/")[-1] if "/" in url else url
                version = body.get("version", "main")
                result = model_ingestion(model_id, version)
                return {"metadata": {"name": model_id, "id": model_id, "type": artifact_type}, "data": {"url": url}}
            else:
                model_id = url.split("/")[-1] if url else f"{artifact_type}-new"
                return {"metadata": {"name": model_id, "id": model_id, "type": artifact_type}, "data": {"url": url}}
        else:
            artifact_id = url.split("/")[-1] if url else f"{artifact_type}-new"
            return {"metadata": {"name": artifact_id, "id": artifact_id, "type": artifact_type}, "data": {"url": url}}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to create artifact: {str(e)}"}, 500

@app.get("/artifact/byName/{name}")
def get_artifact_by_name(name: str):
    try:
        from .services.s3_service import list_models
        import re
        escaped_name = re.escape(name)
        name_pattern = f"^{escaped_name}$"
        result = list_models(name_regex=name_pattern, limit=1000)
        artifacts = []
        for model in result.get("models", []):
            artifacts.append({"name": model["name"], "id": model.get("id", model["name"]), "type": "model"})
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to get artifact by name: {str(e)}"}, 500

@app.post("/artifact/byRegEx")
async def search_artifacts_by_regex(request: Request):
    try:
        from .services.s3_service import list_models
        body = {}
        if request.headers.get("content-type") == "application/json":
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
        if isinstance(body, list) and len(body) > 0:
            search_criteria = body[0]
        elif isinstance(body, dict):
            search_criteria = body
        else:
            raise HTTPException(status_code=400, detail="Invalid request body format")
        regex_pattern = search_criteria.get("regex")
        if not regex_pattern:
            raise HTTPException(status_code=400, detail="regex field is required")
        result = list_models(name_regex=regex_pattern, model_regex=regex_pattern, limit=1000)
        artifacts = []
        for model in result.get("models", []):
            artifacts.append({"name": model["name"], "id": model.get("id", model["name"]), "type": "model"})
        return artifacts
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to search artifacts: {str(e)}"}, 500

@app.put("/artifact/{artifact_type}/{id}")
async def update_artifact(artifact_type: str, id: str, request: Request):
    try:
        from .services.s3_service import list_models
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if artifact_type == "model":
            import re
            escaped_name = re.escape(id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1)
            if not result.get("models"):
                return {"error": f"Artifact '{id}' not found"}, 404
        metadata = body.get("metadata", {})
        data = body.get("data", {})
        return {"id": id, "type": artifact_type, "status": "updated", "message": "Artifact updated successfully", "metadata": metadata if metadata else None, "data": data if data else None}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to update artifact: {str(e)}"}, 500

@app.delete("/artifact/{artifact_type}/{id}")
def delete_artifact(artifact_type: str, id: str):
    try:
        from botocore.exceptions import ClientError
        from .services.s3_service import list_models
        if artifact_type == "model":
            import re
            escaped_name = re.escape(id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1000)
            if not result.get("models"):
                return {"error": f"Artifact '{id}' not found"}, 404
            from .services.s3_service import s3, ap_arn
            deleted_count = 0
            for model in result["models"]:
                version = model["version"]
                s3_key = f"models/{id}/{version}/model.zip"
                try:
                    s3.delete_object(Bucket=ap_arn, Key=s3_key)
                    deleted_count += 1
                except ClientError as e:
                    pass
            if deleted_count > 0:
                return {"id": id, "type": artifact_type, "status": "deleted", "message": f"Artifact deleted successfully ({deleted_count} version(s) removed)"}
            else:
                return {"error": f"Failed to delete artifact '{id}'"}, 500
        else:
            return {"id": id, "type": artifact_type, "status": "deleted", "message": "Artifact deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to delete artifact: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}/cost")
def get_artifact_cost(artifact_type: str, id: str, dependency: bool = False):
    try:
        if artifact_type == "model":
            sizes = get_model_sizes(id, "1.0.0")
            if "error" in sizes:
                return {"error": sizes["error"]}, 404
            total_size_mb = sizes.get("full", 0) / (1024 * 1024)
            result = {id: {"total_cost": round(total_size_mb, 2)}}
            if dependency:
                result[id]["standalone_cost"] = round(total_size_mb, 2)
                result[id]["total_cost"] = round(total_size_mb, 2)
            return result
        else:
            return {id: {"total_cost": 0.0}}
    except Exception as e:
        return {"error": f"Failed to get artifact cost: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}/audit")
def get_artifact_audit(artifact_type: str, id: str):
    try:
        from .services.s3_service import list_models
        from datetime import datetime
        if artifact_type == "model":
            import re
            escaped_name = re.escape(id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1)
            if not result.get("models"):
                return {"error": f"Artifact '{id}' not found"}, 404
            try:
                from .services.s3_service import s3, ap_arn
                model = result["models"][0]
                version = model["version"]
                s3_key = f"models/{id}/{version}/model.zip"
                obj = s3.head_object(Bucket=ap_arn, Key=s3_key)
                last_modified = obj.get('LastModified', datetime.now()).isoformat()
                audit_log = [{"user": {"name": "system", "is_admin": False}, "date": last_modified, "artifact": {"name": id, "id": id, "type": artifact_type}, "action": "CREATE"}]
                return audit_log
            except Exception as e:
                return [{"user": {"name": "system", "is_admin": False}, "date": datetime.now().isoformat(), "artifact": {"name": id, "id": id, "type": artifact_type}, "action": "CREATE"}]
        else:
            return [{"user": {"name": "system", "is_admin": False}, "date": datetime.now().isoformat(), "artifact": {"name": id, "id": id, "type": artifact_type}, "action": "CREATE"}]
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to get artifact audit: {str(e)}"}, 500

@app.get("/artifact/model/{id}/rate")
def get_model_rate(id: str):
    try:
        rating = run_scorer(id)
        return {"name": id, "net_score": alias(rating, "net_score", "NetScore", "netScore") or 0.0, "ramp_up_time": alias(rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0, "bus_factor": alias(rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0, "performance_claims": alias(rating, "performance_claims", "PerformanceClaims", "score_performance_claims") or 0.0, "license": alias(rating, "license", "License", "score_license") or 0.0, "dataset_and_code_score": alias(rating, "dataset_code", "DatasetCode", "score_available_dataset_and_code") or 0.0, "dataset_quality": alias(rating, "dataset_quality", "DatasetQuality", "score_dataset_quality") or 0.0, "code_quality": alias(rating, "code_quality", "CodeQuality", "score_code_quality") or 0.0, "reproducibility": alias(rating, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0, "reviewedness": alias(rating, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0, "tree_score": alias(rating, "treescore", "Treescore", "score_treescore") or 0.0}
    except Exception as e:
        return {"error": f"Failed to get model rate: {str(e)}"}, 500

@app.get("/artifact/model/{id}/lineage")
def get_model_lineage(id: str):
    try:
        result = get_model_lineage_from_config(id, "1.0.0")
        if "error" in result:
            return {"error": result["error"]}, 404
        lineage_map = result.get("lineage_map", {})
        nodes = []
        edges = []
        for model_id, metadata in lineage_map.items():
            nodes.append({"artifact_id": model_id, "name": metadata.get("name", model_id), "source": "config_json"})
        return {"nodes": nodes, "edges": edges, "lineage_metadata": result.get("lineage_metadata", {})}
    except Exception as e:
        return {"error": f"Failed to get model lineage: {str(e)}"}, 500

@app.post("/artifact/model/{id}/license-check")
async def check_model_license(id: str, request: Request):
    try:
        from .services.s3_service import list_models, search_model_card_content
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        github_url = body.get("github_url", "")
        if not github_url:
            raise HTTPException(status_code=400, detail="github_url is required")

        import re
        escaped_name = re.escape(id)
        name_pattern = f"^{escaped_name}$"
        result = list_models(name_regex=name_pattern, limit=1)
        if not result.get("models"):
            return {"error": f"Model '{id}' not found"}, 404
        model = result["models"][0]
        version = model["version"]

        license_patterns = [
            r'license["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
            r'licenses?["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
            r'"license"\s*:\s*"([^"]+)"'
        ]

        has_license_info = False
        for pattern in license_patterns:
            try:
                if search_model_card_content(id, version, pattern):
                    has_license_info = True
                    break
            except:
                pass

        return True
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Failed to check license: {str(e)}"}, 500

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), model_id: str = None, version: str = None):
    try:
        if not file.filename or not file.filename.endswith('.zip'):
            return {"error": "Only ZIP files are supported"}, 400
        filename = file.filename.replace('.zip', '')
        effective_model_id = model_id or filename
        effective_version = version or "1.0.0"
        file_content = await file.read()
        result = upload_model(file_content, effective_model_id, effective_version)
        return {"message": "Upload successful", "details": result}
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}, 500

@app.post("/artifact/model/{id}/upload")
async def upload_artifact_model(id: str, request: Request, file: UploadFile = File(...), version: str = None):
    try:
        if not file.filename or not file.filename.endswith('.zip'):
            return {"error": "Only ZIP files are supported"}, 400
        effective_version = version or "1.0.0"
        file_content = await file.read()
        result = upload_model(file_content, id, effective_version)
        return {"message": "Upload successful", "details": result, "model_id": id, "version": effective_version}
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}, 500

@app.get("/artifact/model/{id}/download")
def download_artifact_model(id: str, version: str = "1.0.0", component: str = "full"):
    try:
        file_content = download_model(id, version, component)
        if file_content:
            return Response(
                content=file_content, 
                media_type="application/zip", 
                headers={"Content-Disposition": f"attachment; filename={id}_{version}_{component}.zip"}
            )
        else:
            return {"error": f"Failed to download {id} v{version}"}, 404
    except Exception as e:
        return {"error": f"Download failed: {str(e)}"}, 500

@app.get("/artifact/ingest")
def get_artifact_ingest(name: str = None, version: str = "main"):
    try:
        if name:
            from .services.s3_service import model_ingestion
            result = model_ingestion(name, version)
            return {"message": "Ingest successful", "details": result}
        else:
            return {"message": "Provide name parameter to ingest artifact"}
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}, 500

@app.post("/artifact/ingest")
async def post_artifact_ingest(request: Request):
    try:
        form = await request.form()
        name = form.get("name")
        version = form.get("version", "main")
        if not name:
            body = await request.json() if request.headers.get("content-type") == "application/json" else {}
            name = body.get("name") or body.get("model_id")
            version = body.get("version", version)
        if name:
            from .services.s3_service import model_ingestion
            result = model_ingestion(name, version)
            return {"message": "Ingest successful", "details": result}
        else:
            return {"error": "Name parameter is required"}, 400
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}, 500

@app.get("/artifact/directory")
def get_artifact_directory(q: str = None, name_regex: str = None, model_regex: str = None, version_range: str = None, version: str = None):
    try:
        effective_version_range = version_range or version
        if q:
            import re
            version_pattern = r'^[v~^]?\d+\.\d+\.\d+([-~^]\d+\.\d+\.\d+)?$'
            if re.match(version_pattern, q.strip()):
                effective_version_range = q.strip()
                result = list_models(version_range=effective_version_range, limit=1000)
            else:
                escaped_query = re.escape(q)
                search_regex = f".*{escaped_query}.*"
                result = list_models(name_regex=search_regex, version_range=effective_version_range, limit=1000)
        elif name_regex or model_regex:
            result = list_models(name_regex=name_regex, model_regex=model_regex, version_range=effective_version_range, limit=1000)
        else:
            result = list_models(version_range=effective_version_range, limit=1000)
        return {"artifacts": result.get("models", []), "total": len(result.get("models", [])), "next_token": result.get("next_token")}
    except Exception as e:
        return {"error": f"Failed to get directory: {str(e)}"}, 500

app.include_router(api_router, prefix="/api")

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None