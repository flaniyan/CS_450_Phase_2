from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io
import re
from botocore.exceptions import ClientError
from ..services.s3_service import (
    upload_model,
    download_model,
    list_models,
    reset_registry,
    sync_model_lineage_to_neptune,
    get_model_lineage_from_config,
    get_model_sizes,
    model_ingestion,
)

router = APIRouter()


@router.get("/rate/{name}")
def rate_package(name: str):
    try:
        from ..services.rating import run_scorer

        result = run_scorer(name)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rate package: {str(e)}")


@router.get("/search")
def search_packages(q: str = Query(..., description="Search query for model names")):
    try:
        import re

        escaped_query = re.escape(q)
        name_regex = f".*{escaped_query}.*"
        result = list_models(name_regex=name_regex, limit=100)
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search packages: {str(e)}"
        )


@router.get("/search/model-cards")
def search_model_cards(
    q: str = Query(..., description="Search query for model card content")
):
    try:
        import re

        escaped_query = re.escape(q)
        model_regex = f".*{escaped_query}.*"
        result = list_models(model_regex=model_regex, limit=100)
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search model cards: {str(e)}"
        )


@router.get("/search/advanced")
def advanced_search(
    name_regex: Optional[str] = Query(
        None, description="Regex pattern for model names"
    ),
    model_regex: Optional[str] = Query(
        None, description="Regex pattern for model card content"
    ),
    version_range: Optional[str] = Query(
        None, description="Version range specification"
    ),
    limit: int = Query(100, ge=1, le=1000),
):
    try:
        result = list_models(
            name_regex=name_regex,
            model_regex=model_regex,
            version_range=version_range,
            limit=limit,
        )
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to perform advanced search: {str(e)}"
        )


@router.get("")
def list_packages(
    limit: int = Query(100, ge=1, le=1000),
    continuation_token: str = Query(None),
    name_regex: str = Query(None, description="Regex to match model names"),
    model_regex: str = Query(None, description="Regex to match model cards"),
    version_range: str = Query(
        None,
        description="Version specification: exact (1.2.3), bounded (1.2.3-2.1.0), tilde (~1.2.0), or caret (^1.2.0)",
    ),
):
    try:
        result = list_models(
            name_regex=name_regex,
            model_regex=model_regex,
            version_range=version_range,
            limit=limit,
            continuation_token=continuation_token,
        )
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list packages: {str(e)}"
        )


@router.post("/models/{model_id}/{version}/model.zip")
def upload_model_file(model_id: str, version: str, file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    try:
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version)
        return result
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == "AccessDenied":
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/models/{model_id}/{version}/model.zip")
def download_model_file(
    model_id: str,
    version: str,
    component: str = Query(
        "full", description="Component to download: 'full', 'weights', or 'datasets'"
    ),
):
    try:
        file_content = download_model(model_id, version, component, use_performance_path=False)
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"
            },
        )
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise HTTPException(
                status_code=404, detail=f"Model {model_id} version {version} not found"
            )
        elif error_code == "NoSuchBucket":
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == "AccessDenied":
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/performance/{model_id}/{version}/model.zip")
def download_performance_model_file(
    model_id: str,
    version: str,
    component: str = Query(
        "full", description="Component to download: 'full', 'weights', or 'datasets'"
    ),
):
    """
    Download model from performance/ S3 path for performance testing.
    """
    try:
        file_content = download_model(model_id, version, component, use_performance_path=True)
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"
            },
        )
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise HTTPException(
                status_code=404, detail=f"Model {model_id} version {version} not found in performance/ path"
            )
        elif error_code == "NoSuchBucket":
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == "AccessDenied":
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/upload")
def upload_package(file: UploadFile = File(...), debloat: bool = Query(False)):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    try:
        filename = file.filename.replace(".zip", "")
        model_id = filename
        version = "1.0.0"
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version, debloat)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/reset")
def reset_system():
    try:
        result = reset_registry()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset system: {str(e)}")


@router.post("/sync-neptune")
def sync_neptune():
    try:
        result = sync_model_lineage_to_neptune()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync Neptune: {str(e)}")


@router.get("/models/{model_id}/{version}/lineage")
def get_model_lineage_from_config_api(model_id: str, version: str):
    try:
        result = get_model_lineage_from_config(model_id, version)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get lineage: {str(e)}")


@router.get("/models/{model_id}/{version}/size")
def get_model_sizes_api(model_id: str, version: str):
    try:
        result = get_model_sizes(model_id, version)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get model sizes: {str(e)}"
        )


@router.post("/models/ingest")
def ingest_model(
    model_id: str = Query(..., description="HuggingFace model ID to ingest"),
    version: str = Query("main", description="Model version/revision"),
):
    try:
        result = model_ingestion(model_id, version)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest model: {str(e)}")
