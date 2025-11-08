from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import boto3
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from datetime import datetime, timezone

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
PACKAGES_TABLE = os.getenv("DDB_TABLE_PACKAGES", "packages")
DOWNLOADS_TABLE = os.getenv("DDB_TABLE_DOWNLOADS", "downloads")

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


def execute_validator(
    script_content: str, package_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute validator script safely"""
    try:
        # Create a safe execution environment
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
            }
        }

        # Execute the validator script
        exec(script_content, safe_globals)

        # Call the validate function if it exists
        if "validate" in safe_globals:
            result = safe_globals["validate"](package_data)
            return {"valid": True, "result": result}
        else:
            return {"valid": False, "error": "No validate function found"}

    except Exception as e:
        logging.error(f"Validator execution error: {e}")
        return {"valid": False, "error": str(e)}


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

    port = int(os.getenv("PORT", "3001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
