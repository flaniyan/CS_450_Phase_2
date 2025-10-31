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

# Request models
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
    """Get detailed component health diagnostics"""
    return {
        "components": [
            {
                "id": "validator-service",
                "display_name": "Validator Service", 
                "status": "ok",
                "observed_at": "2025-10-28T12:00:00Z",
                "details": {
                    "uptime": "99.9%",
                    "response_time": "45ms"
                }
            }
        ],
        "window_minutes": windowMinutes,
        "include_timeline": includeTimeline
    }

@app.put("/authenticate")
def authenticate(auth_request: AuthRequest):
    """Create an access token for authenticated requests"""
    try:
        if (auth_request.user.name == "ece30861defaultadminuser" and 
            auth_request.secret.password == "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"):
            # Return a mock JWT token
            token = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0.example"
            return token
        else:
            return {"error": "Invalid credentials"}, 401
    except Exception as e:
        return {"error": "Invalid request"}, 400

@app.post("/artifacts")
def create_artifact(request: Request):
    """Create a new artifact"""
    try:
        body = request.json()
        # Mock implementation - just return success
        return {
            "id": "artifact-123",
            "status": "created",
            "message": "Artifact created successfully"
        }
    except Exception as e:
        return {"error": "Failed to create artifact"}, 500

@app.delete("/reset")
def reset_system():
    """Reset the system (delete all artifacts)"""
    try:
        result = reset_registry()
        return {"message": "System reset successfully", "details": result}
    except Exception as e:
        return {"error": f"Reset failed: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}")
def get_artifact(artifact_type: str, id: str):
    """Get artifact by type and ID"""
    try:
        # Mock implementation - return artifact info
        return {
            "id": id,
            "type": artifact_type,
            "status": "active",
            "created_at": "2025-10-28T12:00:00Z"
        }
    except Exception as e:
        return {"error": f"Failed to get artifact: {str(e)}"}, 500

@app.post("/artifact/{artifact_type}")
def create_artifact_by_type(artifact_type: str, request: Request):
    """Create artifact by type"""
    try:
        # Mock implementation
        return {
            "id": f"{artifact_type}-123",
            "type": artifact_type,
            "status": "created"
        }
    except Exception as e:
        return {"error": f"Failed to create artifact: {str(e)}"}, 500

@app.get("/artifact/byName/{name}")
def get_artifact_by_name(name: str):
    """Get artifact by name"""
    try:
        # Mock implementation
        return {
            "name": name,
            "id": f"artifact-{name}",
            "status": "active"
        }
    except Exception as e:
        return {"error": f"Failed to get artifact by name: {str(e)}"}, 500

@app.post("/artifact/byRegEx")
def search_artifacts_by_regex(request: Request):
    """Search artifacts by regex"""
    try:
        # Mock implementation
        return {
            "artifacts": [],
            "total": 0,
            "message": "No artifacts found"
        }
    except Exception as e:
        return {"error": f"Failed to search artifacts: {str(e)}"}, 500

@app.put("/artifact/{artifact_type}/{id}")
async def update_artifact(artifact_type: str, id: str, request: Request):
    """Update an artifact"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        return {
            "id": id,
            "type": artifact_type,
            "status": "updated",
            "message": "Artifact updated successfully"
        }
    except Exception as e:
        return {"error": f"Failed to update artifact: {str(e)}"}, 500

@app.delete("/artifact/{artifact_type}/{id}")
def delete_artifact(artifact_type: str, id: str):
    """Delete an artifact"""
    try:
        return {
            "id": id,
            "type": artifact_type,
            "status": "deleted",
            "message": "Artifact deleted successfully"
        }
    except Exception as e:
        return {"error": f"Failed to delete artifact: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}/cost")
def get_artifact_cost(artifact_type: str, id: str, dependency: bool = False):
    """Get artifact cost in MB"""
    try:
        # For models, use get_model_sizes to calculate cost
        if artifact_type == "model":
            # Default to version 1.0.0 if not specified
            sizes = get_model_sizes(id, "1.0.0")
            if "error" in sizes:
                return {"error": sizes["error"]}, 404
            
            # Calculate cost (size in MB)
            total_size_mb = sizes.get("full", 0) / (1024 * 1024)
            
            result = {id: {"total_cost": round(total_size_mb, 2)}}
            if dependency:
                result[id]["standalone_cost"] = round(total_size_mb, 2)
                result[id]["total_cost"] = round(total_size_mb, 2)  # Simplified - add dependency calculation
            
            return result
        else:
            # For other artifact types, return mock data
            return {id: {"total_cost": 0.0}}
    except Exception as e:
        return {"error": f"Failed to get artifact cost: {str(e)}"}, 500

@app.get("/artifact/{artifact_type}/{id}/audit")
def get_artifact_audit(artifact_type: str, id: str):
    """Get artifact audit information"""
    try:
        return {
            "artifact_id": id,
            "artifact_type": artifact_type,
            "audit_log": [
                {
                    "timestamp": "2025-10-28T12:00:00Z",
                    "action": "created",
                    "user": "system"
                }
            ],
            "total_operations": 1
        }
    except Exception as e:
        return {"error": f"Failed to get artifact audit: {str(e)}"}, 500

@app.get("/artifact/model/{id}/rate")
def get_model_rate(id: str):
    """Get quality ratings for a model artifact"""
    try:
        # Try to get the model name/URL from the artifact
        # For now, use the ID as the name
        rating = run_scorer(id)
        
        return {
            "name": id,
            "net_score": alias(rating, "net_score", "NetScore", "netScore") or 0.0,
            "ramp_up_time": alias(rating, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0,
            "bus_factor": alias(rating, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0,
            "performance_claims": alias(rating, "performance_claims", "PerformanceClaims", "score_performance_claims") or 0.0,
            "license": alias(rating, "license", "License", "score_license") or 0.0,
            "dataset_and_code_score": alias(rating, "dataset_code", "DatasetCode", "score_available_dataset_and_code") or 0.0,
            "dataset_quality": alias(rating, "dataset_quality", "DatasetQuality", "score_dataset_quality") or 0.0,
            "code_quality": alias(rating, "code_quality", "CodeQuality", "score_code_quality") or 0.0,
            "reproducibility": alias(rating, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0,
            "reviewedness": alias(rating, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0,
            "tree_score": alias(rating, "treescore", "Treescore", "score_treescore") or 0.0,
        }
    except Exception as e:
        return {"error": f"Failed to get model rate: {str(e)}"}, 500

@app.get("/artifact/model/{id}/lineage")
def get_model_lineage(id: str):
    """Get model lineage information"""
    try:
        # Default to version 1.0.0 if not specified
        result = get_model_lineage_from_config(id, "1.0.0")
        
        if "error" in result:
            return {"error": result["error"]}, 404
        
        # Transform to match expected API format
        lineage_map = result.get("lineage_map", {})
        nodes = []
        edges = []
        
        # Extract nodes from lineage_map
        for model_id, metadata in lineage_map.items():
            nodes.append({
                "artifact_id": model_id,
                "name": metadata.get("name", model_id),
                "source": "config_json"
            })
        
        # Extract edges from lineage_map relationships
        # This is a simplified version - you may need to adjust based on your actual lineage structure
        
        return {
            "nodes": nodes,
            "edges": edges,
            "lineage_metadata": result.get("lineage_metadata", {})
        }
    except Exception as e:
        return {"error": f"Failed to get model lineage: {str(e)}"}, 500

@app.post("/artifact/model/{id}/license-check")
async def check_model_license(id: str, request: Request):
    """Check license compatibility for a model with a GitHub project"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        github_url = body.get("github_url", "")
        
        # Mock implementation - in real scenario, check license compatibility
        return True
    except Exception as e:
        return {"error": f"Failed to check license: {str(e)}"}, 500

@app.post("/artifact/model/{id}/upload")
async def upload_artifact_model(id: str, request: Request, file: UploadFile = File(...), version: str = None):
    """Upload a file for a specific model artifact"""
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
    """Download a specific model artifact"""
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
    """Get artifact ingestion status or initiate ingestion"""
    try:
        if name:
            # If name provided, try to ingest
            from .services.s3_service import model_ingestion
            result = model_ingestion(name, version)
            return {"message": "Ingest successful", "details": result}
        else:
            return {"message": "Provide name parameter to ingest artifact"}
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}, 500

@app.post("/artifact/ingest")
async def post_artifact_ingest(request: Request):
    """Initiate artifact ingestion via POST"""
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
    """Get artifact directory listing"""
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
        
        return {
            "artifacts": result.get("models", []),
            "total": len(result.get("models", [])),
            "next_token": result.get("next_token")
        }
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

@app.get("/")
def localHost_endpoints_home(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/directory")
def localHost_endpoints_directory(request: Request, q: str | None = None, name_regex: str | None = None, model_regex: str | None = None, version_range: str | None = None, version: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    packages = []
    try:
        effective_version_range = version_range or version
        if q:
            # Check if the query looks like a version (e.g., "1.0.0", "v1.0.0", "~1.0.0", "^1.0.0", "1.0.0-2.0.0")
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
        packages = result["models"]
    except Exception as e:
        print(f"Directory error: {e}")
        packages = []
    ctx = {"request": request, "packages": packages, "q": q or "", "name_regex": name_regex, "model_regex": model_regex, "version_range": effective_version_range, "version": version}
    return templates.TemplateResponse("directory.html", ctx)

@app.get(f"/artifact/model/{id}/rate")
def localHost_endpoints_rate(request: Request, name: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    rating = None
    if name:
        row = run_scorer(name)
        rating = {"NetScore": (alias(row, "net_score", "NetScore", "netScore") or 0.0), "RampUp": (alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0), "Correctness": (alias(row, "code_quality", "CodeQuality", "score_code_quality") or 0.0), "BusFactor": (alias(row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0), "ResponsiveMaintainer": (alias(row, "pull_requests", "PullRequests", "score_pull_requests") or 0.0), "LicenseScore": (alias(row, "license", "License", "score_license") or 0.0), "Reproducibility": (alias(row, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0), "Reviewedness": (alias(row, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0), "Treescore": (alias(row, "treescore", "Treescore", "score_treescore") or 0.0)}
    ctx = {"request": request, "name": name or "", "rating": rating}
    return templates.TemplateResponse("rate.html", ctx)

@app.get("/upload")
def localHost_endpoints_upload(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("upload.html", {"request": request})

@app.get("/admin")
def localHost_endpoints_admin(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/lineage")
def localHost_endpoints_lineage(request: Request, name: str | None = None, version: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    lineage_data = None
    if name:
        try:
            from .services.s3_service import get_model_lineage_from_config
            effective_version = version or "1.0.0"
            result = get_model_lineage_from_config(name, effective_version)
            lineage_data = {"model_id": name, "lineage_metadata": result.get("lineage_metadata", {}), "lineage_map": result.get("lineage_map", {}), "config": result.get("config", {}), "error": result.get("error")}
        except Exception as e:
            print(f"Lineage error: {e}")
            lineage_data = {"model_id": name, "error": str(e)}
    ctx = {"request": request, "name": name or "", "version": version or "1.0.0", "lineage": lineage_data}
    return templates.TemplateResponse("lineage.html", ctx)

@app.post("/lineage/sync-neptune")
def localHost_endpoints_sync_neptune():
    try:
        from .services.s3_service import sync_model_lineage_to_neptune
        result = sync_model_lineage_to_neptune()
        return {"message": "Sync successful", "details": result}
    except Exception as e:
        return {"error": f"Sync failed: {str(e)}"}

@app.get("/size-cost")
def localHost_endpoints_size_cost(request: Request, name: str | None = None, version: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    size_data = None
    if name:
        try:
            from .services.s3_service import get_model_sizes
            effective_version = version or "1.0.0"
            result = get_model_sizes(name, effective_version)
            size_data = {"model_id": name, "full_size": result.get("full", 0), "weights_size": result.get("weights", 0), "datasets_size": result.get("datasets", 0), "weights_uncompressed": result.get("weights_uncompressed", 0), "datasets_uncompressed": result.get("datasets_uncompressed", 0), "error": result.get("error")}
        except Exception as e:
            print(f"Size cost error: {e}")
            size_data = {"model_id": name, "error": str(e)}
    ctx = {"request": request, "name": name or "", "size_data": size_data}
    return templates.TemplateResponse("size_cost.html", ctx)

@app.get("/ingest")
def localHost_endpoints_ingest_get(request: Request, name: str | None = None, version: str = "main"):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    ctx = {"request": request, "name": name or "", "version": version, "result": None}
    return templates.TemplateResponse("ingest.html", ctx)

@app.post("/ingest")
async def localHost_endpoints_ingest_post(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    form = await request.form()
    name = form.get("name")
    version = form.get("version", "main")
    result = None
    if name:
        try:
            from .services.s3_service import model_ingestion
            ingestion_result = model_ingestion(name, version)
            result = {"message": "Ingest successful", "details": ingestion_result}
        except HTTPException as e:
            error_detail = e.detail
            if isinstance(error_detail, dict) and "error" in error_detail:
                result = {"error": error_detail.get("message", "Ingestion failed"), "details": {"metric_scores": error_detail.get("metric_scores"), "model_id": name, "version": version, "ingestible": False}}
            else:
                result = {"error": str(error_detail) if isinstance(error_detail, str) else "Ingestion failed", "details": {"model_id": name, "version": version, "ingestible": False}}
        except Exception as e:
            result = {"error": f"Ingest failed: {str(e)}"}
    ctx = {"request": request, "name": name or "", "version": version, "result": result}
    return templates.TemplateResponse("ingest.html", ctx)                

@app.post("/upload")
def localHost_endpoints_upload_post(request: Request, file: UploadFile = File(...), model_id: str = None, version: str = None):
    if not file.filename or not file.filename.endswith('.zip'):
        return {"error": "Only ZIP files are supported"}
    try:
        filename = file.filename.replace('.zip', '')
        effective_model_id = model_id or filename
        effective_version = version or "1.0.0"
        file_content = file.file.read()
        result = upload_model(file_content, effective_model_id, effective_version)
        return {"message": "Upload successful", "details": result}
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}

@app.get("/download/{model_id}/{version}")
def localHost_endpoints_download(model_id: str, version: str, component: str = "full"):
    try:
        file_content = download_model(model_id, version, component)
        if file_content:
            return Response(content=file_content, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"})
        else:
            return {"error": f"Failed to download {model_id} v{version}"}
    except Exception as e:
        return {"error": f"Download failed: {str(e)}"}

@app.post("/admin/reset")
def localHost_endpoints_reset():
    try:
        result = reset_registry()
        return {"message": "Reset successful", "details": result}
    except Exception as e:
        return {"error": f"Reset failed: {str(e)}"}

def main():
    """Main entry point for the application."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()