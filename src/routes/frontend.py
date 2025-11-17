from __future__ import annotations

import re
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..services.s3_service import (
    list_models,
    upload_model,
    download_model,
    reset_registry,
    get_model_lineage_from_config,
    get_model_sizes,
)
from ..services.rating import run_scorer, alias

templates: Jinja2Templates | None = None
routes_registered = False


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
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    if templates_instance:
        set_templates(templates_instance)

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
    def rate_get(request: Request, name: str | None = None):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        rating = None
        if name:
            row = run_scorer(name)
            rating = {
                "NetScore": (alias(row, "net_score", "NetScore", "netScore") or 0.0),
                "RampUp": (
                    alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0
                ),
                "Correctness": (
                    alias(row, "code_quality", "CodeQuality", "score_code_quality")
                    or 0.0
                ),
                "BusFactor": (
                    alias(
                        row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
                    )
                    or 0.0
                ),
                "ResponsiveMaintainer": (
                    alias(row, "pull_requests", "PullRequests", "score_pull_requests")
                    or 0.0
                ),
                "LicenseScore": (
                    alias(row, "license", "License", "score_license") or 0.0
                ),
                "Reproducibility": (
                    alias(
                        row,
                        "reproducibility",
                        "Reproducibility",
                        "score_reproducibility",
                    )
                    or 0.0
                ),
                "Reviewedness": (
                    alias(row, "reviewedness", "Reviewedness", "score_reviewedness")
                    or 0.0
                ),
                "Treescore": (
                    alias(row, "treescore", "Treescore", "score_treescore") or 0.0
                ),
            }
        ctx = {"request": request, "name": name or "", "rating": rating}
        return templates.TemplateResponse("rate.html", ctx)

    @app.get("/artifact/model/{id}/rate")
    def rate_by_id(request: Request, id: str, name: str | None = None):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        rating = None
        effective_name = name or id
        if effective_name:
            row = run_scorer(effective_name)
            rating = {
                "NetScore": (alias(row, "net_score", "NetScore", "netScore") or 0.0),
                "RampUp": (
                    alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp") or 0.0
                ),
                "Correctness": (
                    alias(row, "code_quality", "CodeQuality", "score_code_quality")
                    or 0.0
                ),
                "BusFactor": (
                    alias(
                        row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
                    )
                    or 0.0
                ),
                "ResponsiveMaintainer": (
                    alias(row, "pull_requests", "PullRequests", "score_pull_requests")
                    or 0.0
                ),
                "LicenseScore": (
                    alias(row, "license", "License", "score_license") or 0.0
                ),
                "Reproducibility": (
                    alias(
                        row,
                        "reproducibility",
                        "Reproducibility",
                        "score_reproducibility",
                    )
                    or 0.0
                ),
                "Reviewedness": (
                    alias(row, "reviewedness", "Reviewedness", "score_reviewedness")
                    or 0.0
                ),
                "Treescore": (
                    alias(row, "treescore", "Treescore", "score_treescore") or 0.0
                ),
            }
        ctx = {"request": request, "name": effective_name or "", "rating": rating}
        return templates.TemplateResponse("rate.html", ctx)

    @app.get("/upload")
    def upload_get(request: Request):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        return templates.TemplateResponse("upload.html", {"request": request})

    @app.post("/upload")
    def upload_post(
        request: Request,
        file: UploadFile = File(...),
        model_id: str = None,
        version: str = None,
    ):
        if not file.filename or not file.filename.endswith(".zip"):
            return {"error": "Only ZIP files are supported"}
        try:
            filename = file.filename.replace(".zip", "")
            effective_model_id = model_id or filename
            effective_version = version or "1.0.0"
            file_content = file.file.read()
            result = upload_model(file_content, effective_model_id, effective_version)
            return {"message": "Upload successful", "details": result}
        except Exception as e:
            return {"error": f"Upload failed: {str(e)}"}

    @app.get("/admin")
    def admin(request: Request):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        return templates.TemplateResponse("admin.html", {"request": request})

    @app.get("/lineage")
    def lineage(request: Request, name: str | None = None, version: str | None = None):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        lineage_data = None
        if name:
            try:
                from ..services.s3_service import get_model_lineage_from_config

                effective_version = version or "1.0.0"
                result = get_model_lineage_from_config(name, effective_version)
                lineage_data = {
                    "model_id": name,
                    "lineage_metadata": result.get("lineage_metadata", {}),
                    "lineage_map": result.get("lineage_map", {}),
                    "config": result.get("config", {}),
                    "error": result.get("error"),
                }
            except Exception as e:
                print(f"Lineage error: {e}")
                lineage_data = {"model_id": name, "error": str(e)}
        ctx = {
            "request": request,
            "name": name or "",
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
        request: Request, name: str | None = None, version: str | None = None
    ):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        size_data = None
        if name:
            try:
                from ..services.s3_service import get_model_sizes

                effective_version = version or "1.0.0"
                result = get_model_sizes(name, effective_version)
                size_data = {
                    "model_id": name,
                    "full_size": result.get("full", 0),
                    "weights_size": result.get("weights", 0),
                    "datasets_size": result.get("datasets", 0),
                    "weights_uncompressed": result.get("weights_uncompressed", 0),
                    "datasets_uncompressed": result.get("datasets_uncompressed", 0),
                    "error": result.get("error"),
                }
            except Exception as e:
                print(f"Size cost error: {e}")
                size_data = {"model_id": name, "error": str(e)}
        ctx = {"request": request, "name": name or "", "size_data": size_data}
        return templates.TemplateResponse("size_cost.html", ctx)

    @app.get("/ingest")
    def ingest_get(request: Request, name: str | None = None, version: str = "main"):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        ctx = {
            "request": request,
            "name": name or "",
            "version": version,
            "result": None,
        }
        return templates.TemplateResponse("ingest.html", ctx)

    @app.post("/ingest")
    async def ingest_post(request: Request):
        if not templates:
            return {"message": "Frontend not found. Ensure frontend/templates exists."}
        form = await request.form()
        name = form.get("name")
        version = form.get("version", "main")
        result = None
        if name:
            try:
                from ..services.s3_service import model_ingestion

                ingestion_result = model_ingestion(name, version)
                result = {"message": "Ingest successful", "details": ingestion_result}
            except HTTPException as e:
                error_detail = e.detail
                if isinstance(error_detail, dict) and "error" in error_detail:
                    result = {
                        "error": error_detail.get("message", "Ingestion failed"),
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
                            else "Ingestion failed"
                        ),
                        "details": {
                            "model_id": name,
                            "version": version,
                            "ingestible": False,
                        },
                    }
            except Exception as e:
                result = {"error": f"Ingest failed: {str(e)}"}
        ctx = {
            "request": request,
            "name": name or "",
            "version": version,
            "result": result,
        }
        return templates.TemplateResponse("ingest.html", ctx)

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

    routes_registered = True


def main():
    port = int(os.getenv("PORT", "8000"))
    app = setup_app()
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
