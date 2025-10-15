from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io
from botocore.exceptions import ClientError

from ..services.s3_service import upload_model, download_model, list_models, reset_registry

router = APIRouter()


@router.get("")
def list_packages(limit: int = Query(100, ge=1, le=1000),continuation_token: str = Query(None),name_regex: str = Query(None, description="Regex to match model names"), model_regex: str = Query(None, description="Regex to match model cards"), version_range: str = Query(None, description="Version specification: exact (1.2.3), bounded (1.2.3-2.1.0), tilde (~1.2.0), or caret (^1.2.0)")):
    try:
        result = list_models(name_regex=name_regex,model_regex=model_regex,version_range=version_range,limit=limit, continuation_token=continuation_token)
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list packages: {str(e)}")


@router.post("/models/{model_id}/versions/{version}/upload")
def upload_model_file(
    model_id: str,
    version: str,
    file: UploadFile = File(...)
):
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    try:
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version)
        return result
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == 'AccessDenied':
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/models/{model_id}/versions/{version}/download")
def download_model_file(
    model_id: str,
    version: str,
    component: str = Query("full", description="Component to download: 'full', 'weights', or 'datasets'")
):
    try:
        file_content = download_model(model_id, version, component)
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"
            }
        )
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail=f"Model {model_id} version {version} not found")
        elif error_code == 'NoSuchBucket':
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == 'AccessDenied':
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/reset")
def reset_system():
    try:
        result = reset_registry()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset system: {str(e)}")


