from __future__ import annotations
from pathlib import Path
import re
import os
import uvicorn
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from .routes.index import router as api_router
from .services.s3_service import list_models, upload_model, download_model, reset_registry
from .services.rating import run_scorer, alias

app = FastAPI(title="ACME API (Python)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(api_router, prefix="/api")

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

@app.get("/")
def frontend_home(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/directory")
def frontend_directory(request: Request, q: str | None = None, name_regex: str | None = None, model_regex: str | None = None, version_range: str | None = None, version: str | None = None):
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

@app.get("/rate")
def frontend_rate(request: Request, name: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    rating = None
    if name:
        row = run_scorer(name)
        rating = {
            "NetScore": (alias(row, "net_score", "NetScore", "netScore") or 0.0),
            "RampUp": (alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0),
            "Correctness": (alias(row, "code_quality", "CodeQuality", "score_code_quality") or 0.0),
            "BusFactor": (alias(row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor") or 0.0),
            "ResponsiveMaintainer": (alias(row, "pull_requests", "PullRequests", "score_pull_requests") or 0.0),
            "LicenseScore": (alias(row, "license", "License", "score_license") or 0.0),
            "Reproducibility": (alias(row, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0),
            "Reviewedness": (alias(row, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0),
            "Treescore": (alias(row, "treescore", "Treescore", "score_treescore") or 0.0),
        }
    ctx = {"request": request, "name": name or "", "rating": rating}
    return templates.TemplateResponse("rate.html", ctx)

@app.get("/upload")
def frontend_upload(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("upload.html", {"request": request})

@app.get("/admin")
def frontend_admin(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/lineage")
def frontend_lineage(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("lineage.html", {"request": request})

@app.get("/size-cost")
def frontend_size_cost(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("size_cost.html", {"request": request})

@app.get("/ingest")
def frontend_ingest(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("ingest.html", {"request": request})

@app.post("/upload")
def frontend_upload_post(request: Request, file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.zip'):
        return {"error": "Only ZIP files are supported"}
    try:
        filename = file.filename.replace('.zip', '')
        model_id = filename
        version = "1.0.0"
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version)
        return {"message": "Upload successful", "details": result}
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}

@app.get("/download/{model_id}/{version}")
def frontend_download(model_id: str, version: str, component: str = "full"):
    try:
        file_content = download_model(model_id, version, component)
        if file_content:
            return Response(content=file_content, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"})
        else:
            return {"error": f"Failed to download {model_id} v{version}"}
    except Exception as e:
        return {"error": f"Download failed: {str(e)}"}

@app.post("/admin/reset")
def frontend_reset():
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