from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import boto3
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from datetime import datetime, timezone
from multiprocessing import get_context
from multiprocessing.queues import Queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
cloudwatch = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
PACKAGES_TABLE = os.getenv("DDB_TABLE_PACKAGES", "packages")
DOWNLOADS_TABLE = os.getenv("DDB_TABLE_DOWNLOADS", "downloads")
METRIC_NAMESPACE = os.getenv("VALIDATOR_METRIC_NAMESPACE", "ValidatorService")
METRIC_NAME_TIMEOUT = os.getenv("VALIDATOR_TIMEOUT_METRIC_NAME", "validator.timeout.count")

app = FastAPI(title="Package Validator Service", version="1.0.0")
security = HTTPBearer()


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
        response = table.get_item(Key={"pkg_key": f"{pkg_name}/{version}"})
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


def _run_validator_script(script_content: str, package_data: Dict[str, Any]) -> Dict[str, Any]:
    safe_globals = {
        "__builtins__": {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "min": min,
            "max": max,
            "sum": sum,
            "any": any,
            "all": all,
            "enumerate": enumerate,
            "zip": zip,
            "range": range,
            "print": print,
            "Exception": Exception,
            "RuntimeError": RuntimeError,
        }
    }

    exec(script_content, safe_globals)

    if "validate" not in safe_globals:
        raise ValueError("Validator script must define a validate() function")

    result = safe_globals["validate"](package_data)
    if result is None:
        raise ValueError("Validator returned no result")

    return {"valid": True, "result": result}


def _validator_worker(script: str, data: Dict[str, Any], queue: Queue):
    try:
        result = _run_validator_script(script, data)
        if result:
            queue.put({"status": "ok", "result": result})
        else:
            queue.put({"status": "error", "error": "Validator returned no result"})
    except Exception as exc:
        queue.put({"status": "error", "error": str(exc)})


def execute_validator(
    script_content: str, package_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute validator script safely with a timeout to prevent DoS."""
    timeout = int(os.getenv("VALIDATOR_TIMEOUT_SEC", "5"))
    ctx = get_context("spawn")
    queue: Queue = ctx.Queue()
    process = ctx.Process(target=_validator_worker, args=(script_content, package_data, queue))
    process.start()
    process.join(timeout)

    if process.is_alive():
        logging.error("Validator execution timed out after %s seconds", timeout)
        process.terminate()
        process.join()
        try:
            cloudwatch.put_metric_data(
                Namespace=METRIC_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": METRIC_NAME_TIMEOUT,
                        "Timestamp": datetime.now(timezone.utc),
                        "Value": 1,
                        "Unit": "Count",
                    }
                ],
            )
        except Exception as metric_error:
            logging.warning("Failed to publish timeout metric: %s", metric_error)
        return {
            "valid": False,
            "error": f"Validator execution timed out after {timeout} seconds",
        }

    if not queue.empty():
        message = queue.get()
        if message.get("status") == "ok":
            return message["result"]
        return {"valid": False, "error": message.get("error", "Unknown validator error")}

    return {"valid": False, "error": "Validator returned no result"}


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

        table.put_item(Item=item)
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
        validation_result = execute_validator(validator_script, package_meta)

        if validation_result["valid"]:
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "allowed",
                "Validation passed",
                validation_result,
            )
            return ValidationResponse(
                allowed=True,
                reason="Validation passed",
                validation_result=validation_result,
            )
        else:
            log_download_event(
                request.pkg_name,
                request.version,
                request.user_id,
                "blocked",
                f"Validation failed: {validation_result.get('error', 'Unknown error')}",
                validation_result,
            )
            return ValidationResponse(
                allowed=False,
                reason=f"Validation failed: {validation_result.get('error', 'Unknown error')}",
                validation_result=validation_result,
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
    logger.info(f"Starting validator service on port {port}")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start validator service: {e}", exc_info=True)
        raise
