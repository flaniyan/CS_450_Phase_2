from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import io
from botocore.exceptions import ClientError

from ..services.s3_service import upload_model, download_model

router = APIRouter()


@router.get("")
##def list_packages():
 ##   return {"packages": []}
##work in progress

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
        return {
            "message": "Model uploaded successfully",
            "data": result
        }
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


