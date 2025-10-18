from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, Request  # type: ignore[import]
from fastapi.staticfiles import StaticFiles  # type: ignore[import]
from fastapi.templating import Jinja2Templates  # type: ignore[import]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[import]

from .routes.index import router as api_router

app = FastAPI(title="ACME API (Python)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(api_router, prefix="/api")


# ---- Serve frontend (Jinja templates + static) on same server ----
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = (
    Jinja2Templates(directory=str(TEMPLATES_DIR))
    if TEMPLATES_DIR.exists()
    else None
)


@app.get("/")
def frontend_home(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/directory")
def frontend_directory(request: Request, q: str = ""):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    
    # Fetch packages from the API
    try:
        from .services.s3_service import list_models
        result = list_models(name_regex=q if q else None, limit=100)
        packages = result["models"]
    except Exception as e:
        # If there's an error fetching packages, show empty list
        packages = []
    
    ctx = {"request": request, "packages": packages, "q": q}
    return templates.TemplateResponse("directory.html", ctx)


@app.get("/rate")
def frontend_rate(request: Request, name: str | None = None):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    rating = None
    if name:
        # Reuse scoring to provide a simple rating view
        from .services.rating import run_scorer, alias  # lazy import to avoid circulars
        row = run_scorer(name)
        rating = {
            "NetScore": (
                alias(row, "net_score", "NetScore", "netScore") or 0.0
            ),
            "RampUp": (
                alias(
                    row,
                    "ramp_up",
                    "RampUp",
                    "score_ramp_up",
                    "rampUp",
                )
                or 0.0
            ),
            "Correctness": (
                alias(row, "code_quality", "CodeQuality", "score_code_quality") or 0.0
            ),
            "BusFactor": (
                alias(
                    row,
                    "bus_factor",
                    "BusFactor",
                    "score_bus_factor",
                    "busFactor",
                )
                or 0.0
            ),
            "ResponsiveMaintainer": (
                alias(
                    row,
                    "pull_requests",
                    "PullRequests",
                    "score_pull_requests",
                )
                or 0.0
            ),
            "LicenseScore": (
                alias(row, "license", "License", "score_license") or 0.0
            ),
            "Reproducibility": (
                alias(row, "reproducibility", "Reproducibility", "score_reproducibility") or 0.0
            ),
            "Reviewedness": (
                alias(row, "reviewedness", "Reviewedness", "score_reviewedness") or 0.0
            ),
            "Treescore": (
                alias(row, "treescore", "Treescore", "score_treescore") or 0.0
            ),
        }
    ctx = {"request": request, "name": name or "", "rating": rating}
    return templates.TemplateResponse("rate.html", ctx)


@app.get("/upload")
def frontend_upload(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload")
async def frontend_upload_post(request: Request):
    from fastapi import Form, UploadFile, File
    from fastapi.responses import RedirectResponse
    
    try:
        # Get form data
        form = await request.form()
        file = form.get("file")
        debloat = form.get("debloat") == "on"
        
        if not file or not hasattr(file, 'filename'):
            return {"error": "No file uploaded"}
        
        # Generate model_id and version from filename or use defaults
        filename = file.filename
        if not filename.endswith('.zip'):
            return {"error": "Only ZIP files are supported"}
        
        # Extract model name from filename (remove .zip extension)
        model_id = filename[:-4]  # Remove .zip
        version = "1.0.0"  # Default version
        
        # Read file content
        file_content = await file.read()
        
        # Upload to S3
        from .services.s3_service import upload_model
        result = upload_model(file_content, model_id, version, debloat)
        
        # Redirect to directory page with success message
        return RedirectResponse(url="/directory", status_code=303)
        
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}


@app.get("/admin")
def frontend_admin(request: Request):
    if not templates:
        return {"message": "Frontend not found. Ensure frontend/templates exists."}
    return templates.TemplateResponse("admin.html", {"request": request})


if __name__ == "__main__":
    import uvicorn  # type: ignore[import]
    import os
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
