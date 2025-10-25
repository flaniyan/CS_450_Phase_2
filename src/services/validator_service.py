import os, json, asyncio, subprocess, sys, time, uuid, contextlib, logging
from asyncio import Semaphore
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.utils.ddb_sanitize import to_ddb
from .secure_temp import register_sigterm_cleanup

# envs
VALIDATOR_TIMEOUT_MS  = int(os.getenv("VALIDATOR_TIMEOUT_MS",  "4000"))
VALIDATOR_HEAP_MB     = int(os.getenv("VALIDATOR_HEAP_MB",     "128"))
VALIDATOR_MAX_WORKERS = int(os.getenv("VALIDATOR_MAX_WORKERS", "2"))
MAX_SCRIPT_SIZE       = int(os.getenv("VALIDATOR_MAX_SCRIPT_SIZE", "200000"))
MAX_FILE_COUNT        = int(os.getenv("VALIDATOR_MAX_FILE_COUNT",  "10"))
MAX_PAYLOAD_BYTES     = int(os.getenv("VALIDATOR_MAX_PAYLOAD_BYTES","2097152"))  # 2MB

_SEM = Semaphore(VALIDATOR_MAX_WORKERS)

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
PACKAGES_TABLE = os.getenv("DDB_TABLE_PACKAGES", "packages")
DOWNLOADS_TABLE = os.getenv("DDB_TABLE_DOWNLOADS", "downloads")

app = FastAPI(title="Package Validator Service", version="1.0.0")


# Pydantic models
class ValidationRequest(BaseModel):
    pkg_name: str
    version: str
    user_id: str
    user_groups: list[str]


class ValidationResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    validation_result: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str


def get_package_metadata(pkg_name: str, version: str) -> Optional[Dict[str, Any]]:
    """Get package metadata from DynamoDB"""
    try:
        table = dynamodb.Table(PACKAGES_TABLE)
        response = table.get_item(Key={"pkg_key": f"{pkg_name}#{version}"})
        return response.get("Item")
    except Exception as e:
        logging.error(f"Error getting package metadata: {e}")
        return None


def get_validator_script(pkg_name: str, version: str) -> Optional[str]:
    """Get validator script from S3"""
    try:
        key = f"validators/{pkg_name}/{version}/validator.py"
        response = s3.get_object(Bucket=ARTIFACTS_BUCKET, Key=key)
        return response["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logging.error(f"Error getting validator script: {e}")
        return None


async def execute_validator(script_content: str, package_data: dict) -> dict:
    # fast fail / size guards
    if not isinstance(script_content, str) or len(script_content) > MAX_SCRIPT_SIZE:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "script too large"}}
    if len(json.dumps(package_data)) > MAX_PAYLOAD_BYTES:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "payload too large"}}
    if isinstance(package_data.get("files"), list) and len(package_data["files"]) > MAX_FILE_COUNT:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "too many files"}}

    req = {
        "script": script_content,
        "payload": package_data,
        "heap_mb": VALIDATOR_HEAP_MB,
        "cpu_s": max(1, VALIDATOR_TIMEOUT_MS // 1000 - 1)  # leave headroom
    }
    cmd = [sys.executable, "-u", "-m", "src.services.validator_sandbox"]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, lambda: proc.communicate(input=json.dumps(req).encode("utf-8"))
            ),
            timeout=VALIDATOR_TIMEOUT_MS / 1000
        )
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return {"ok": False, "error": {"code": "TIMEOUT", "message": f"exceeded {VALIDATOR_TIMEOUT_MS}ms"}}

    if proc.returncode != 0:
        return {"ok": False, "error": {"code": "INTERNAL", "message": (err or b'').decode(errors='ignore')[:300]}}

    result = json.loads(out.decode("utf-8"))
    return {"ok": bool(result.get("ok", True)), **{k: v for k, v in result.items() if k != "ok"}}


def log_download_event(
    pkg_name: str,
    version: str,
    user_id: str,
    status: str,
    reason: str = None,
    validation_result: Dict = None,
):
    """Log download event to DynamoDB"""
    try:
        table = dynamodb.Table(DOWNLOADS_TABLE)
        event_id = (
            f"{user_id}_{pkg_name}_{version}_{datetime.now(timezone.utc).isoformat()}"
        )

        item = {
            "event_id": event_id,
            "pkg_name": pkg_name,
            "version": version,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "reason": reason or "",
            "validation_result": validation_result or {},
        }

        table.put_item(Item=to_ddb(item))
    except Exception as e:
        logging.error(f"Error logging download event: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy", timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/validate", response_model=ValidationResponse)
async def validate_package(request: ValidationRequest):
    """Validate package access and execute custom validators"""
    register_sigterm_cleanup()
    async with _SEM:
        t0 = time.perf_counter()
        job_id = str(uuid.uuid4())
        
        # Get package metadata
        package_meta = get_package_metadata(request.pkg_name, request.version)
        if not package_meta:
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "blocked",
                "Package not found",
            )
            raise HTTPException(status_code=404, detail="Package not found")

        # Check if package is sensitive
        is_sensitive = package_meta.get("is_sensitive", False)
        allowed_groups = package_meta.get("allowed_groups", [])

        if not is_sensitive:
            # Non-sensitive package - allow access
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "allowed",
                "Non-sensitive package",
            )
            return ValidationResponse(allowed=True, reason="Non-sensitive package")

        # Check group access for sensitive packages
        user_has_access = any(group in request.user_groups for group in allowed_groups)
        if not user_has_access:
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "blocked",
                f"User not in required groups: {allowed_groups}",
            )
            return ValidationResponse(
                allowed=False,
                reason=f"Access denied: User not in required groups: {allowed_groups}",
            )

        # Get and execute validator script
        validator_script = get_validator_script(request.pkg_name, request.version)
        if validator_script:
            result = await execute_validator(validator_script, package_meta)
            result.setdefault("issues", [])
            result.setdefault("score", 0.0)
            result["duration_ms_total"] = int((time.perf_counter() - t0) * 1000)
            
            logging.info(f"job_id={job_id} ok={result.get('ok')} dur_ms={result['duration_ms_total']}")
            
            if not result.get("ok"):
                # Defensive error handling - normalize error shape
                raw_err = result.get("error")
                
                if raw_err is None:
                    norm_err = None
                elif isinstance(raw_err, dict):
                    # Already structured
                    norm_err = {
                        "code": raw_err.get("code", "VALIDATOR_ERROR"),
                        "message": raw_err.get("message", "Validator error"),
                        "details": raw_err.get("details") or {},
                    }
                else:
                    # String or something else
                    norm_err = {
                        "code": "VALIDATOR_ERROR",
                        "message": str(raw_err),
                        "details": {},
                    }
                
                result["error"] = norm_err
                
                # Now safe to access
                code = result["error"]["code"] if result["error"] else None
                msg = result["error"]["message"] if result["error"] else "Validation failed"
                
                raise HTTPException(
                    status_code=408 if code == "TIMEOUT" else 422,
                    detail=msg
                )
            
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "allowed",
                "Validation passed",
                result,
            )
            return ValidationResponse(
                allowed=True,
                reason="Validation passed",
                validation_result=result,
            )
        else:
            # No validator script - allow access for users with group access
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "allowed",
                "No validator script required",
            )
            return ValidationResponse(allowed=True, reason="No validator script required")


@app.get("/history/{user_id}")
async def get_user_history(user_id: str, limit: int = 50):
    """Get user's download history"""
    try:
        table = dynamodb.Table(DOWNLOADS_TABLE)

        response = table.query(
            IndexName="user-timestamp-index",
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            ScanIndexForward=False,  # Most recent first
            Limit=limit,
        )

        return {
            "user_id": user_id,
            "downloads": response.get("Items", []),
            "count": len(response.get("Items", [])),
        }
    except Exception as e:
        logging.error(f"Error getting user history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving history")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
