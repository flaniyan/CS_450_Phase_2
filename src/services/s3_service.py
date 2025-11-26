import boto3
import zipfile
import io
import re
import json
import os
import logging
import urllib.request
import urllib.error
import requests
import shutil
import tempfile
from typing import Dict, Any, Optional
from fastapi import HTTPException
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import get_credentials
from botocore.session import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..acmecli.types import MetricValue
from ..acmecli.hf_handler import fetch_hf_metadata
from ..acmecli.metrics import METRIC_FUNCTIONS

region = os.getenv("AWS_REGION", "us-east-1")
access_point_name = os.getenv("S3_ACCESS_POINT_NAME", "cs450-s3")

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize AWS clients with error handling for development
try:
    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]
    # Use the correct access point ARN format
    ap_arn = f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"
    # Use regular S3 client - boto3 handles access points automatically
    s3 = boto3.client("s3", region_name=region)
    # Test if S3 client actually works with access point
    s3.list_objects_v2(Bucket=ap_arn, Prefix="models/", MaxKeys=1)
    aws_available = True
    print(f"AWS S3 connected successfully to access point {ap_arn}")
except Exception as e:
    # AWS not available - set dummy values for development
    print(f"AWS initialization failed: {e}")
    sts = None
    account_id = os.getenv("AWS_ACCOUNT_ID", "")
    if account_id:
        ap_arn = f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"
    else:
        ap_arn = None
    s3 = None
    aws_available = False


def parse_version(version_str: str) -> tuple:
    version_str = version_str.lstrip("v")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def version_matches_range(version_str: str, version_spec: str) -> bool:
    try:
        version = parse_version(version_str)
        if not version:
            return False
        if not any(op in version_spec for op in ["-", "~", "^"]):
            spec_version = parse_version(version_spec)
            if spec_version:
                return spec_version == version
            else:
                return False
        if "-" in version_spec and not version_spec.startswith(("~", "^")):
            parts = version_spec.split("-", 1)
            min_ver, max_ver = parse_version(parts[0]), parse_version(parts[1])
            if min_ver and max_ver:
                return min_ver <= version <= max_ver
            else:
                return False
        if version_spec.startswith("~"):
            base = parse_version(version_spec[1:])
            if base:
                return base <= version < (base[0], base[1] + 1, 0)
            else:
                return False
        if version_spec.startswith("^"):
            base = parse_version(version_spec[1:])
            if not base:
                return False
            if base[0] > 0:
                max_ver = (base[0] + 1, 0, 0)
            elif base[1] > 0:
                max_ver = (0, base[1] + 1, 0)
            else:
                max_ver = (0, 0, base[2] + 1)
            return base <= version < max_ver
        return False
    except Exception:
        return False


def validate_huggingface_structure(zip_content: bytes) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
            file_list = zip_file.namelist()
            has_config = any("config.json" in f for f in file_list)
            has_weights = any(f.endswith((".bin", ".safetensors")) for f in file_list)
            return {
                "valid": has_config and has_weights,
                "has_config": has_config,
                "has_weights": has_weights,
                "files": file_list,
            }
    except zipfile.BadZipFile:
        return {"valid": False, "error": "Invalid ZIP file"}


def get_model_sizes(model_id: str, version: str) -> Dict[str, Any]:
    if not aws_available:
        return {
            "full": 0,
            "weights": 0,
            "datasets": 0,
            "error": "AWS services not available",
        }
    try:
        from botocore.exceptions import ClientError

        s3_key = f"models/{model_id}/{version}/model.zip"
        response = s3.head_object(Bucket=ap_arn, Key=s3_key)
        full_size = response["ContentLength"]
        s3_response = s3.get_object(Bucket=ap_arn, Key=s3_key)
        zip_content = s3_response["Body"].read()
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
            weight_files = [
                f for f in zip_file.namelist() if f.endswith((".bin", ".safetensors"))
            ]
            dataset_files = [
                f
                for f in zip_file.namelist()
                if any(ext in f for ext in [".csv", ".json", ".txt", ".parquet"])
            ]
            weights_size = sum(zip_file.getinfo(f).compress_size for f in weight_files)
            datasets_size = sum(
                zip_file.getinfo(f).compress_size for f in dataset_files
            )
            weights_uncompressed = sum(
                zip_file.getinfo(f).file_size for f in weight_files
            )
            datasets_uncompressed = sum(
                zip_file.getinfo(f).file_size for f in dataset_files
            )
        return {
            "full": full_size,
            "weights": weights_size,
            "datasets": datasets_size,
            "weights_uncompressed": weights_uncompressed,
            "datasets_uncompressed": datasets_uncompressed,
            "model_id": model_id,
            "version": version,
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            return {
                "full": 0,
                "weights": 0,
                "datasets": 0,
                "error": f"Model '{model_id}' not found in registry. Upload it first using the Upload or Ingest page.",
            }
        return {"full": 0, "weights": 0, "datasets": 0, "error": str(e)}
    except Exception as e:
        print(f"Error getting model sizes: {e}")
        return {"full": 0, "weights": 0, "datasets": 0, "error": str(e)}


def extract_model_component(zip_content: bytes, component: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
            if component == "weights":
                files = [
                    f
                    for f in zip_file.namelist()
                    if f.endswith((".bin", ".safetensors"))
                ]
            elif component == "datasets":
                files = [
                    f
                    for f in zip_file.namelist()
                    if any(ext in f for ext in [".txt", ".json"])
                ]
            else:
                return zip_content
            if not files:
                raise ValueError(f"No {component} files found")
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for file in files:
                    new_zip.writestr(file, zip_file.read(file))
            return output.getvalue()
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")


def get_presigned_upload_url(
    model_id: str, version: str, expires_in: int = 3600
) -> Dict[str, str]:
    """Generate presigned URL for direct S3 upload (bypasses API Gateway 10MB limit)"""
    if not aws_available:
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )
    try:
        s3_key = f"models/{model_id}/{version}/model.zip"
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": ap_arn, "Key": s3_key, "ContentType": "application/zip"},
            ExpiresIn=expires_in,
        )
        return {
            "upload_url": url,
            "model_id": model_id,
            "version": version,
            "s3_key": s3_key,
            "expires_in": expires_in,
        }
    except Exception as e:
        print(f"AWS S3 presigned URL generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
        )


def upload_model(
    file_content: bytes, model_id: str, version: str, debloat: bool = False
) -> Dict[str, str]:
    if not aws_available:
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )
    if not file_content or len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Cannot upload empty file content")
    try:
        # Sanitize model_id and version for S3 key
        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
        s3_key = f"models/{safe_model_id}/{safe_version}/model.zip"

        s3.put_object(
            Bucket=ap_arn, Key=s3_key, Body=file_content, ContentType="application/zip"
        )
        print(
            f"AWS S3 upload successful: {model_id} v{version} ({len(file_content)} bytes) -> {s3_key}"
        )
        return {"message": "Upload successful"}
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"AWS S3 upload failed for {model_id} v{version}: {error_msg}",
            exc_info=True,
        )
        print(f"AWS S3 upload failed: {e}")
        # Provide more specific error messages
        if "AccessDenied" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(
                status_code=403,
                detail=f"AWS S3 access denied. Check IAM permissions for bucket {ap_arn}",
            )
        elif "NoSuchBucket" in error_msg or "InvalidBucketName" in error_msg:
            raise HTTPException(
                status_code=503, detail=f"Invalid S3 bucket/access point: {ap_arn}"
            )
        else:
            raise HTTPException(
                status_code=500, detail=f"AWS upload failed: {error_msg}"
            )


def download_model(model_id: str, version: str, component: str = "full") -> bytes:
    if not aws_available:
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )
    
    # Import instrumentation here to avoid circular imports
    from .performance.instrumentation import measure_operation, publish_metric
    
    try:
        s3_key = f"models/{model_id}/{version}/model.zip"
        
        # Measure S3 download latency
        with measure_operation("S3DownloadLatency", {"Component": "S3"}):
            response = s3.get_object(Bucket=ap_arn, Key=s3_key)
            zip_content = response["Body"].read()
        
        # Publish bytes transferred metric
        bytes_transferred = len(zip_content)
        publish_metric(
            "S3DownloadBytes",
            value=float(bytes_transferred),
            unit="Bytes",
            dimensions={"Component": "S3"}
        )
        
        if component != "full":
            try:
                result = extract_model_component(zip_content, component)
                print(
                    f"AWS S3 download successful: {model_id} v{version} ({component})"
                )
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        print(f"AWS S3 download successful: {model_id} v{version} (full)")
        return zip_content
    except Exception as e:
        print(f"AWS S3 download failed: {e}")
        raise HTTPException(status_code=500, detail=f"AWS download failed: {str(e)}")


_model_card_cache = {}


def clear_model_card_cache():
    global _model_card_cache
    _model_card_cache.clear()


def search_model_card_content(model_id: str, version: str, regex_pattern: str) -> bool:
    try:
        cache_key = f"{model_id}@{version}"
        if cache_key in _model_card_cache:
            cached_content = _model_card_cache[cache_key]
            pattern = re.compile(regex_pattern, re.IGNORECASE)
            return any(pattern.search(content) for content in cached_content)
        pattern = re.compile(regex_pattern, re.IGNORECASE)
        is_likely_filename = (
            "." in regex_pattern
            and not any(char in regex_pattern for char in [" ", "\n", "\t"])
            and len(regex_pattern) < 50
        )
        if is_likely_filename:
            try:
                s3_key = f"models/{model_id}/{version}/model.zip"
                response = s3.head_object(Bucket=ap_arn, Key=s3_key)
                file_size = response["ContentLength"]
                for tail_size in [32768, 65536, 131072]:  # 32KB, 64KB, 128KB
                    try:
                        range_start = max(0, file_size - tail_size)
                        response = s3.get_object(
                            Bucket=ap_arn,
                            Key=s3_key,
                            Range=f"bytes={range_start}-{file_size-1}",
                        )
                        zip_tail = response["Body"].read()
                        with zipfile.ZipFile(io.BytesIO(zip_tail), "r") as zip_file:
                            for file_info in zip_file.filelist:
                                filename = file_info.filename.lower()
                                if any(
                                    ext in filename for ext in [".txt", ".json", ".md"]
                                ):
                                    if pattern.search(filename):
                                        return True
                        break
                    except:
                        continue

            except:
                pass
        zip_content = download_model(model_id, version, "full")
        if not zip_content:
            return False
        cached_content = []
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
            for file_info in zip_file.filelist:
                filename = file_info.filename.lower()
                if any(ext in filename for ext in [".txt", ".json", ".md"]):
                    if pattern.search(filename):
                        _model_card_cache[cache_key] = cached_content
                        return True
                    try:
                        content = zip_file.read(file_info).decode(
                            "utf-8", errors="ignore"
                        )
                        cached_content.append(content)
                        if pattern.search(content):
                            _model_card_cache[cache_key] = cached_content
                            return True
                    except Exception:
                        continue
        _model_card_cache[cache_key] = cached_content
        return False
    except Exception:
        return False


def list_models(
    name_regex: str = None,
    model_regex: str = None,
    version_range: str = None,
    limit: int = 100,
    continuation_token: str = None,
) -> Dict[str, Any]:
    if not aws_available:
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )
    limit = min(limit, 1000)
    try:
        params = {"Bucket": ap_arn, "Prefix": "models/", "MaxKeys": limit}
        if continuation_token:
            params["ContinuationToken"] = continuation_token
        response = s3.list_objects_v2(**params)
        results = []
        if "Contents" in response:
            name_pattern = None
            if name_regex:
                try:
                    name_pattern = re.compile(name_regex, re.IGNORECASE)
                except re.error as e:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid name regex: {str(e)}"
                    )
            for item in response["Contents"]:
                key = item["Key"]
                if key.endswith("/model.zip"):
                    if len(key.split("/")) >= 3:
                        model_name = key.split("/")[1]
                        model_version = key.split("/")[2]
                        if name_pattern and not name_pattern.search(model_name):
                            continue
                        if version_range:
                            normalized_version = model_version.lstrip("v")
                            if not version_matches_range(
                                normalized_version, version_range
                            ):
                                continue
                        if model_regex:
                            try:
                                if not search_model_card_content(
                                    model_name, model_version, model_regex
                                ):
                                    continue
                            except re.error as e:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Invalid model regex: {str(e)}",
                                )
                        results.append({"name": model_name, "version": model_version})
        return {"models": results, "next_token": response.get("NextContinuationToken")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


def reset_registry() -> Dict[str, str]:
    if not aws_available:
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )
    try:
        deleted_count = 0
        
        # Use paginator to handle all objects, not just first 1000
        # Delete ALL artifact types: models, datasets, codes, and packages
        paginator = s3.get_paginator('list_objects_v2')
        
        # Delete all artifact types
        prefixes = ["models/", "datasets/", "codes/", "packages/"]
        
        for prefix in prefixes:
            pages = paginator.paginate(Bucket=ap_arn, Prefix=prefix)
            for page in pages:
                if "Contents" in page:
                    for item in page["Contents"]:
                        s3.delete_object(Bucket=ap_arn, Key=item["Key"])
                        deleted_count += 1
        
        if deleted_count > 0:
            print(f"AWS S3 reset successful: Deleted {deleted_count} objects")
        else:
            print("AWS S3 reset successful: No objects found to delete")
        return {"message": "Reset done successfully"}
    except Exception as e:
        print(f"AWS S3 reset failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to reset registry: {str(e)}"
        )


def store_artifact_metadata(
    artifact_id: str, artifact_name: str, artifact_type: str, version: str, url: str
) -> Dict[str, str]:
    """
    Store artifact metadata in S3 for all artifact types (model, dataset, code).
    For models, the actual file is already stored via upload_model.
    For datasets and code, we store a metadata JSON file.
    """
    if not aws_available:
        return {"status": "skipped", "reason": "AWS not available"}
    
    try:
        from datetime import datetime, timezone
        from botocore.exceptions import ClientError
        
        # Sanitize artifact name for S3 key
        sanitized_name = (
            artifact_name.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
        
        # Store metadata.json file
        metadata = {
            "artifact_id": artifact_id,
            "name": artifact_name,
            "type": artifact_type,
            "version": version,
            "url": url,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        
        s3_key = f"{artifact_type}s/{sanitized_name}/{safe_version}/metadata.json"
        logger.info(f"DEBUG: Storing metadata to S3 key: {s3_key}")
        logger.info(f"DEBUG: Metadata content: {json.dumps(metadata, indent=2)}")
        
        s3.put_object(
            Bucket=ap_arn,
            Key=s3_key,
            Body=json.dumps(metadata, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        
        logger.info(f"DEBUG: ✅✅✅ Successfully stored artifact metadata to S3: {s3_key} ✅✅✅")
        logger.info(f"DEBUG: Metadata includes: artifact_id='{artifact_id}', name='{artifact_name}', type='{artifact_type}'")
        return {"status": "success", "s3_key": s3_key}
    except Exception as e:
        logger.error(f"Failed to store artifact metadata: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}


def find_artifact_metadata_by_id(artifact_id: str) -> Optional[Dict[str, Any]]:
    """
    Find artifact metadata by artifact_id by searching S3 metadata files.
    Searches all artifact types (models, datasets, code).
    Uses pagination to search through all metadata files.
    For models, also tries to find by listing recent models first (faster).
    
    Args:
        artifact_id: The artifact ID to search for
    
    Returns:
        Dict with artifact metadata if found, None otherwise
    """
    logger.info(f"DEBUG: ===== FIND_ARTIFACT_METADATA_BY_ID START =====")
    logger.info(f"DEBUG: Searching for artifact_id: '{artifact_id}'")
    
    if not aws_available:
        logger.warning(f"DEBUG: AWS not available, returning None")
        return None
    
    try:
        from botocore.exceptions import ClientError
        
        # First, try to find in models by listing recent models and checking their metadata
        # This is faster than searching all metadata files
        logger.info(f"DEBUG: Step 1: Fast lookup - checking recent models")
        try:
            recent_models = list_models(limit=100)  # Get recent models
            model_count = len(recent_models.get("models", []))
            logger.info(f"DEBUG: Found {model_count} recent models to check")
            
            checked_count = 0
            for model in recent_models.get("models", []):
                model_name = model.get("name", "")
                version = model.get("version", "main")
                checked_count += 1
                logger.debug(f"DEBUG: Checking model {checked_count}/{model_count}: name='{model_name}', version='{version}'")
                
                # Construct the metadata key
                sanitized_name = (
                    model_name.replace("https://huggingface.co/", "")
                    .replace("http://huggingface.co/", "")
                    .replace("/", "_")
                    .replace(":", "_")
                    .replace("\\", "_")
                    .replace("?", "_")
                    .replace("*", "_")
                    .replace('"', "_")
                    .replace("<", "_")
                    .replace(">", "_")
                    .replace("|", "_")
                )
                safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
                metadata_key = f"models/{sanitized_name}/{safe_version}/metadata.json"
                logger.debug(f"DEBUG: Checking metadata key: {metadata_key}")
                
                try:
                    response = s3.get_object(Bucket=ap_arn, Key=metadata_key)
                    metadata_json = response["Body"].read().decode("utf-8")
                    metadata = json.loads(metadata_json)
                    found_artifact_id = metadata.get("artifact_id")
                    logger.debug(f"DEBUG: Metadata file found, artifact_id in file: '{found_artifact_id}'")
                    
                    if found_artifact_id == artifact_id:
                        logger.info(f"DEBUG: ✅✅✅ MATCH FOUND in fast lookup! ✅✅✅")
                        logger.info(f"DEBUG: Found artifact metadata by ID: {artifact_id} in {metadata_key}")
                        result = {
                            "artifact_id": artifact_id,
                            "name": metadata.get("name"),
                            "type": "model",
                            "version": metadata.get("version", version),
                            "url": metadata.get("url"),
                            "s3_key": metadata_key
                        }
                        logger.info(f"DEBUG: Returning: {result}")
                        return result
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    logger.debug(f"DEBUG: Metadata file {metadata_key} not found: {error_code}")
                    continue
                except Exception as e:
                    logger.debug(f"DEBUG: Error reading metadata from {metadata_key}: {str(e)}")
                    continue
            
            logger.info(f"DEBUG: Fast lookup checked {checked_count} models, no match found")
        except Exception as e:
            logger.warning(f"DEBUG: Error in fast lookup for models: {str(e)}", exc_info=True)
        
        # If not found in recent models, search all metadata files (slower but comprehensive)
        logger.info(f"DEBUG: Step 2: Comprehensive search - checking all metadata files")
        for artifact_type in ["model", "dataset", "code"]:
            logger.info(f"DEBUG: Searching {artifact_type} artifacts...")
            prefix = f"{artifact_type}s/"
            params = {"Bucket": ap_arn, "Prefix": prefix, "MaxKeys": 1000}
            
            try:
                paginator = s3.get_paginator("list_objects_v2")
                page_count = 0
                file_count = 0
                for page in paginator.paginate(**params):
                    page_count += 1
                    if "Contents" not in page:
                        logger.debug(f"DEBUG: Page {page_count} has no contents")
                        continue
                    
                    logger.debug(f"DEBUG: Page {page_count} has {len(page['Contents'])} items")
                    for item in page["Contents"]:
                        key = item["Key"]
                        # Check metadata.json files for all types
                        if key.endswith("/metadata.json"):
                            file_count += 1
                            if file_count % 10 == 0:
                                logger.debug(f"DEBUG: Checked {file_count} metadata files so far...")
                            try:
                                # Download and parse metadata
                                response = s3.get_object(Bucket=ap_arn, Key=key)
                                metadata_json = response["Body"].read().decode("utf-8")
                                metadata = json.loads(metadata_json)
                                
                                found_artifact_id = metadata.get("artifact_id")
                                # Check if artifact_id matches
                                if found_artifact_id == artifact_id:
                                    logger.info(f"DEBUG: ✅✅✅ MATCH FOUND in comprehensive search! ✅✅✅")
                                    logger.info(f"DEBUG: Found artifact metadata by ID: {artifact_id} in {key}")
                                    result = {
                                        "artifact_id": artifact_id,
                                        "name": metadata.get("name"),
                                        "type": metadata.get("type", artifact_type),
                                        "version": metadata.get("version", "main"),
                                        "url": metadata.get("url"),
                                        "s3_key": key
                                    }
                                    logger.info(f"DEBUG: Returning: {result}")
                                    return result
                            except json.JSONDecodeError as e:
                                logger.debug(f"DEBUG: Invalid JSON in metadata file {key}: {str(e)}")
                                continue
                            except Exception as e:
                                logger.debug(f"DEBUG: Error reading metadata from {key}: {str(e)}")
                                continue
                
                logger.info(f"DEBUG: Searched {file_count} {artifact_type} metadata files, no match")
            except Exception as e:
                logger.warning(f"DEBUG: Error listing objects for {artifact_type}: {str(e)}", exc_info=True)
                continue
        
        logger.warning(f"DEBUG: ❌❌❌ Artifact metadata NOT FOUND for ID: {artifact_id} ❌❌❌")
        logger.warning(f"DEBUG: Searched all artifact types (model, dataset, code)")
        return None
    except Exception as e:
        logger.error(f"DEBUG: ❌ Exception in find_artifact_metadata_by_id: {str(e)}", exc_info=True)
        return None


def list_artifacts_from_s3(
    artifact_type: str = "model",
    name_regex: str = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    List artifacts from S3 for a given type (model, dataset, code).
    For models, looks for model.zip files.
    For datasets and code, looks for metadata.json files.
    """
    if not aws_available:
        return {"artifacts": []}
    
    try:
        from botocore.exceptions import ClientError
        
        artifacts = []
        prefix = f"{artifact_type}s/"
        params = {"Bucket": ap_arn, "Prefix": prefix, "MaxKeys": limit}
        
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(**params):
            if "Contents" not in page:
                continue
            
            for item in page["Contents"]:
                key = item["Key"]
                
                if artifact_type == "model":
                    # For models, look for model.zip files
                    if key.endswith("/model.zip"):
                        # Extract model name and version from path
                        # Format: models/{name}/{version}/model.zip
                        parts = key.replace(f"{prefix}", "").split("/")
                        if len(parts) >= 2:
                            model_name = parts[0].replace("_", "/")
                            version = parts[1]
                            artifacts.append({
                                "name": model_name,
                                "version": version,
                                "type": artifact_type,
                            })
                else:
                    # For datasets and code, look for metadata.json files
                    if key.endswith("/metadata.json"):
                        try:
                            response = s3.get_object(Bucket=ap_arn, Key=key)
                            metadata_json = response["Body"].read().decode("utf-8")
                            metadata = json.loads(metadata_json)
                            artifacts.append({
                                "name": metadata.get("name"),
                                "version": metadata.get("version", "main"),
                                "type": artifact_type,
                                "artifact_id": metadata.get("artifact_id"),
                            })
                        except Exception as e:
                            logger.debug(f"Error reading metadata from {key}: {str(e)}")
                            continue
        
        # Apply regex filter if provided
        if name_regex:
            import re
            pattern = re.compile(name_regex)
            artifacts = [a for a in artifacts if pattern.match(a.get("name", ""))]
        
        return {"artifacts": artifacts[:limit]}
    except Exception as e:
        logger.error(f"Failed to list artifacts from S3: {str(e)}", exc_info=True)
        return {"artifacts": []}


def extract_config_from_model(model_zip_content: bytes) -> Optional[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(model_zip_content), "r") as zip_file:
            config_files = [
                f
                for f in zip_file.namelist()
                if f.endswith("config.json") or f == "config.json"
            ]
            if not config_files:
                return None
            config_content = zip_file.read(config_files[0])
            return json.loads(config_content.decode("utf-8"))
    except Exception as e:
        print(f"Error extracting config.json: {e}")
        return None


def extract_github_url_from_zip(zip_content: bytes) -> Optional[str]:
    """
    Extract GitHub URL from all text files in the zip archive.
    Searches through README files first, then other text files.
    """
    if not zip_content:
        return None
    
    import zipfile
    import io
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_file:
            file_list = zip_file.namelist()
            
            # Text file extensions to search
            text_extensions = (
                ".md", ".txt", ".rst", ".org", ".py", ".js", ".ts", ".json", 
                ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sh", 
                ".bat", ".cmd", ".ps1", ".html", ".htm", ".xml", ".csv"
            )
            
            # Priority files (README files first)
            priority_files = []
            other_text_files = []
            
            for filename in file_list:
                filename_lower = filename.lower()
                # Skip binary files and very large files
                if any(filename_lower.endswith(ext) for ext in text_extensions):
                    if "readme" in filename_lower or filename_lower == "readme":
                        priority_files.append(filename)
                    else:
                        other_text_files.append(filename)
            
            # Search priority files first (README files)
            for filename in priority_files:
                try:
                    content = zip_file.read(filename)
                    # Try to decode as text
                    try:
                        text = content.decode("utf-8", errors="ignore")
                    except:
                        try:
                            text = content.decode("latin-1", errors="ignore")
                        except:
                            continue
                    
                    if text:
                        github_url = extract_github_url_from_text(text)
                        if github_url:
                            print(f"[INGEST] Found GitHub URL in {filename}: {github_url}")
                            return github_url
                except Exception as e:
                    print(f"[INGEST] Warning: Could not read {filename}: {e}")
                    continue
            
            # Search other text files
            for filename in other_text_files:
                try:
                    content = zip_file.read(filename)
                    # Limit file size to avoid memory issues (max 1MB)
                    if len(content) > 1024 * 1024:
                        continue
                    
                    # Try to decode as text
                    try:
                        text = content.decode("utf-8", errors="ignore")
                    except:
                        try:
                            text = content.decode("latin-1", errors="ignore")
                        except:
                            continue
                    
                    if text:
                        github_url = extract_github_url_from_text(text)
                        if github_url:
                            print(f"[INGEST] Found GitHub URL in {filename}: {github_url}")
                            return github_url
                except Exception as e:
                    print(f"[INGEST] Warning: Could not read {filename}: {e}")
                    continue
            
            # Also check config.json specifically (it's often a string, not a file)
            try:
                config = extract_config_from_model(zip_content)
                if config:
                    config_str = json.dumps(config)
                    github_url = extract_github_url_from_text(config_str)
                    if github_url:
                        print(f"[INGEST] Found GitHub URL in config.json: {github_url}")
                        return github_url
            except Exception as e:
                print(f"[INGEST] Warning: Could not extract GitHub URL from config.json: {e}")
            
    except Exception as e:
        print(f"[INGEST] Error searching zip for GitHub URL: {e}")
    
    return None


def extract_github_url_from_text(text: str) -> Optional[str]:
    """
    Extract GitHub URL from text (README, config, etc.) using multiple patterns.
    Carefully reads the README to find GitHub links in various formats.
    """
    if not text:
        return None

    import re

    # Normalize text - handle markdown code blocks and HTML
    text_normalized = text
    
    # Try multiple patterns in order of specificity
    
    # 1. HTML hyperlink (e.g., <a href="https://github.com/owner/repo">Click here</a>)
    # Using pattern: href=["'](.*?)["']
    html_href_pattern = r'href=["\'](.*?)["\']'
    html_matches = re.finditer(html_href_pattern, text_normalized, re.IGNORECASE)
    for match in html_matches:
        url = match.group(1).strip()
        if url.startswith(('http://', 'https://')) and 'github.com' in url.lower():
            # Extract owner/repo from GitHub URL
            github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
            if github_match:
                owner, repo = github_match.groups()
                owner = owner.rstrip(".").strip().rstrip("/")
                repo = repo.rstrip(".").strip().rstrip("/")
                if owner and repo:
                    return f"https://github.com/{owner}/{repo}"
    
    # 2. Markdown hyperlink (e.g., [Click here](https://github.com/owner/repo))
    # Using pattern: \]\((https?://[^\s)]+)\)
    markdown_pattern = r'\]\((https?://[^\s)]+)\)'
    markdown_matches = re.finditer(markdown_pattern, text_normalized, re.IGNORECASE)
    for match in markdown_matches:
        url = match.group(1).strip()
        if 'github.com' in url.lower():
            github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
            if github_match:
                owner, repo = github_match.groups()
                owner = owner.rstrip(".").strip().rstrip("/")
                repo = repo.rstrip(".").strip().rstrip("/")
                if owner and repo:
                    return f"https://github.com/{owner}/{repo}"
    
    # 3. Generic URL finder (any URL in plain text)
    # Using pattern: https?://[^\s"'>)]+
    generic_url_pattern = r'https?://[^\s"\'>)]+'
    generic_matches = re.finditer(generic_url_pattern, text_normalized, re.IGNORECASE)
    for match in generic_matches:
        url = match.group(0).strip()
        if 'github.com' in url.lower():
            github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
            if github_match:
                owner, repo = github_match.groups()
                owner = owner.rstrip(".").strip().rstrip("/")
                repo = repo.rstrip(".").strip().rstrip("/")
                if owner and repo:
                    return f"https://github.com/{owner}/{repo}"

    # 5. GitHub URLs in plain text with common prefixes
    prefix_patterns = [
        r"(?:repository|repo|source|code|github)[\s:]*[:=]?\s*(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)",
        r"(?:check|see|view|visit)[\s]+(?:out|at)?[\s]*(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)",
        r"(?:available|found|located)[\s]+(?:at|on)?[\s]*(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)",
    ]
    for pattern in prefix_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            owner, repo = match.group(1), match.group(2)
            owner = owner.rstrip(".").strip().rstrip("/")
            repo = repo.rstrip(".").strip().rstrip("/")
            if owner and repo:
                return f"https://github.com/{owner}/{repo}"

    # 6. Owner/repo format without full URL (e.g., "github.com/owner/repo" or "owner/repo")
    owner_repo_pattern = r"(?:github\.com/)?([a-zA-Z0-9_-]+)/([a-zA-Z0-9_\-\.]+)"
    owner_repo_matches = re.findall(owner_repo_pattern, text_normalized)
    # Filter out common false positives
    false_positives = ["com/", "org/", "net/", "io/", "co/"]
    for owner, repo in owner_repo_matches:
        if f"{owner}/{repo}".lower() not in false_positives:
            owner = owner.rstrip(".").strip().rstrip("/")
            repo = repo.rstrip(".").strip().rstrip("/")
            if owner and repo and len(owner) > 0 and len(repo) > 0:
                # Only use if it looks like a valid GitHub repo (not too generic)
                if len(owner) >= 1 and len(repo) >= 1:
                    return f"https://github.com/{owner}/{repo}"

    return None


def parse_lineage_from_config(config: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    lineage_metadata = {
        "model_id": model_id,
        "base_model": None,
        "architecture": None,
        "transformers_version": None,
        "model_type": None,
        "architectures": [],
        "vocab_size": None,
        "hidden_size": None,
    }
    base_model_fields = [
        "base_model_name_or_path",
        "_name_or_path",
        "parent_model",
        "pretrained_model_name_or_path",
    ]
    for field in base_model_fields:
        if field in config:
            lineage_metadata["base_model"] = config[field]
            break
    lineage_metadata["architecture"] = config.get("model_type")
    lineage_metadata["model_type"] = config.get("model_type")
    lineage_metadata["transformers_version"] = config.get("transformers_version")
    lineage_metadata["architectures"] = config.get("architectures") or []
    lineage_metadata["vocab_size"] = config.get("vocab_size")
    lineage_metadata["hidden_size"] = config.get("hidden_size")
    return lineage_metadata


def get_model_lineage_from_config(model_id: str, version: str) -> Dict[str, Any]:
    try:
        model_content = download_model(model_id, version)
        config = extract_config_from_model(model_content)
        if not config:
            return {"model_id": model_id, "error": "No config.json found in model"}
        lineage_metadata = parse_lineage_from_config(config, model_id)
        lineage_map = {}
        if lineage_metadata.get("base_model"):
            parent_model = lineage_metadata["base_model"]
            lineage_map[parent_model] = [model_id]
        return {
            "model_id": model_id,
            "lineage_metadata": lineage_metadata,
            "lineage_map": lineage_map,
            "config": config,
        }
    except HTTPException as e:
        # Extract detail from HTTPException for better error handling
        error_detail = e.detail if hasattr(e, 'detail') else str(e)
        return {"model_id": model_id, "error": error_detail}
    except Exception as e:
        print(f"Error getting lineage from config: {e}")
        return {"model_id": model_id, "error": str(e)}


def sign_request(request):
    credentials = get_credentials(Session())
    auth = SigV4Auth(
        credentials, "neptune-db", os.environ.get("AWS_REGION", "us-east-1")
    )
    auth.add_auth(request)
    return dict(request.headers)


def send_request(url, headers, data):
    req = urllib.request.Request(
        url, data=data.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(e.read().decode("utf-8"))
        raise


def write_to_neptune(lineage_data):
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    if not neptune_endpoint:
        print("NEPTUNE_ENDPOINT not configured, skipping Neptune write")
        return
    endpoint = neptune_endpoint
    clear_query = "g.V().drop()"
    request = AWSRequest(
        method="POST", url=endpoint, data=json.dumps({"gremlin": clear_query})
    )
    signed_headers = sign_request(request)
    response = send_request(
        endpoint, signed_headers, json.dumps({"gremlin": clear_query})
    )
    print(f"Clear database response: {response}")
    verify_query = "g.V().count()"
    request = AWSRequest(
        method="POST", url=endpoint, data=json.dumps({"gremlin": verify_query})
    )
    signed_headers = sign_request(request)
    response = send_request(
        endpoint, signed_headers, json.dumps({"gremlin": verify_query})
    )
    print(f"Vertex count after clearing: {response}")

    def process_node(node, children):
        query = f"g.V().has('lineage_node', 'node_name', '{node}').fold().coalesce(unfold(), addV('lineage_node').property('node_name', '{node}'))"
        request = AWSRequest(
            method="POST", url=endpoint, data=json.dumps({"gremlin": query})
        )
        signed_headers = sign_request(request)
        response = send_request(
            endpoint, signed_headers, json.dumps({"gremlin": query})
        )
        print(f"Add node response for {node}: {response}")
        for child_node in children:
            query = f"g.V().has('lineage_node', 'node_name', '{child_node}').fold().coalesce(unfold(), addV('lineage_node').property('node_name', '{child_node}'))"
            request = AWSRequest(
                method="POST", url=endpoint, data=json.dumps({"gremlin": query})
            )
            signed_headers = sign_request(request)
            response = send_request(
                endpoint, signed_headers, json.dumps({"gremlin": query})
            )
            print(f"Add child node response for {child_node}: {response}")
            query = f"g.V().has('lineage_node', 'node_name', '{node}').as('a').V().has('lineage_node', 'node_name', '{child_node}').coalesce(inE('lineage_edge').where(outV().as('a')), addE('lineage_edge').from('a').property('edge_name', ' '))"
            request = AWSRequest(
                method="POST", url=endpoint, data=json.dumps({"gremlin": query})
            )
            signed_headers = sign_request(request)
            response = send_request(
                endpoint, signed_headers, json.dumps({"gremlin": query})
            )
            print(f"Add edge response for {node} -> {child_node}: {response}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_node, node, children)
            for node, children in lineage_data.items()
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in processing node: {str(e)}")


def sync_model_lineage_to_neptune():
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available")
    try:
        lineage_map = {}
        response = list_models(limit=1000)
        models = response.get("models", [])
        print(f"Analyzing lineage for {len(models)} models from config.json")
        for model in models:
            model_id = model.get("Name")
            version = model.get("Version", "1.0.0")
            if not model_id:
                continue
            try:
                lineage_info = get_model_lineage_from_config(model_id, version)
                if lineage_info.get("lineage_map"):
                    for parent, children in lineage_info["lineage_map"].items():
                        if parent in lineage_map:
                            lineage_map[parent].extend(children)
                        else:
                            lineage_map[parent] = children
                    print(
                        f"Extracted lineage for {model_id}: {lineage_info.get('lineage_metadata', {}).get('base_model')}"
                    )
            except Exception as e:
                print(f"Error processing model {model_id}: {e}")
                continue
        print(f"Built lineage map with {len(lineage_map)} relationships")
        write_to_neptune(lineage_map)
        return {
            "message": "Model lineage successfully synced to Neptune",
            "source": "config.json analysis",
            "relationships": len(lineage_map),
        }
    except Exception as e:
        print(f"Error syncing lineage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync lineage: {str(e)}")


def download_file(url: str, timeout: int = 120) -> bytes | None:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.content
    except Exception:
        return None
    return None


def download_from_huggingface(model_id: str, version: str = "main") -> bytes:
    try:
        clean_model_id = model_id
        if model_id.startswith("https://huggingface.co/"):
            clean_model_id = model_id.replace("https://huggingface.co/", "")
        elif model_id.startswith("http://huggingface.co/"):
            clean_model_id = model_id.replace("http://huggingface.co/", "")

        api_url = f"https://huggingface.co/api/models/{clean_model_id}"
        try:
            response = requests.get(api_url, timeout=30)
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail=f"Timeout connecting to HuggingFace API for model {clean_model_id}",
            )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to HuggingFace API: {str(e)}",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=404,
                detail=f"Model {clean_model_id} not found on HuggingFace",
            )

        try:
            model_info = response.json()
        except ValueError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Invalid response from HuggingFace API: {str(e)}",
            )

        all_files = []
        for sibling in model_info.get("siblings", []):
            if sibling.get("rfilename"):
                all_files.append(sibling["rfilename"])

        essential_files = []
        for filename in all_files:
            if filename.endswith((".json", ".md", ".txt", ".yml", ".yaml")):
                essential_files.append(filename)
            elif filename.startswith("README") or filename.startswith("readme"):
                essential_files.append(filename)
            elif (
                filename == "config.json"
                or filename == "LICENSE"
                or filename == "license"
                or filename == "LICENCE"
                or filename == "licence"
            ):
                essential_files.append(filename)

        if not essential_files:
            raise HTTPException(
                status_code=400,
                detail=f"No essential files found for model {clean_model_id}. Model may be empty or inaccessible.",
            )

        urls_to_download = [
            (
                f"https://huggingface.co/{clean_model_id}/resolve/{version}/{filename}",
                filename,
            )
            for filename in essential_files
        ]

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(download_file, url[0], 120): url[1]
                    for url in urls_to_download
                }
                downloaded_count = 0
                for future in as_completed(futures):
                    filename = futures[future]
                    try:
                        result = future.result()
                        if result:
                            zip_file.writestr(filename, result)
                            downloaded_count += 1
                    except Exception as e:
                        print(f"[DOWNLOAD] Warning: Failed to download {filename}: {e}")

                if downloaded_count == 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to download any files for model {clean_model_id}",
                    )

        zip_content = output.getvalue()
        if not zip_content or len(zip_content) == 0:
            raise HTTPException(
                status_code=500,
                detail=f"Downloaded zip file is empty for model {clean_model_id}",
            )

        return zip_content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error downloading from HuggingFace for {model_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download model from HuggingFace: {str(e)}",
        )


def model_ingestion(model_id: str, version: str) -> Dict[str, Any]:
    from ..services.rating import create_metadata_from_files, run_acme_metrics
    import time
    import tempfile

    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available")
    try:
        start_time = time.time()

        zip_content = download_from_huggingface(model_id, version)
        download_time = time.time() - start_time
        print(f"[INGEST] Downloaded in {download_time:.2f}s")

        validation = validate_huggingface_structure(zip_content)
        if not validation.get("has_config"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model structure. Missing: config.json={not validation.get('has_config')}",
            )

        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        temp_dir = tempfile.mkdtemp(prefix=f"ingest_{safe_model_id}_{os.getpid()}_")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            meta = create_metadata_from_files(temp_dir, model_id)
            config = extract_config_from_model(zip_content)
            if config:
                meta["config"] = config
            zip_size_bytes = len(zip_content)
            zip_size_kb = zip_size_bytes / 1024
            meta["size"] = int(zip_size_kb)
            meta["contributors"] = {}
            meta["pushed_at"] = None
            meta["github_url"] = ""
            meta["parents"] = []
            meta["full_name"] = model_id
            meta["stars"] = 0
            meta["forks"] = 0
            meta["has_wiki"] = False
            meta["has_pages"] = False
            meta["language"] = "python"
            meta["open_issues_count"] = 0
            meta["github"] = {}
            meta["license"] = ""

            repo_url = None
            import re

            if config:
                config_str = json.dumps(config)
                
                # Pattern 1: HTML hyperlink in config.json (e.g., <a href="https://github.com/owner/repo">)
                # Using pattern: href=["'](.*?)["']
                html_href_pattern = r'href=["\'](.*?)["\']'
                html_matches = re.finditer(html_href_pattern, config_str, re.IGNORECASE)
                for match in html_matches:
                    url = match.group(1).strip()
                    if url.startswith(('http://', 'https://')) and 'github.com' in url.lower():
                        github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
                        if github_match:
                            owner, repo = github_match.groups()
                            repo_url = f"https://github.com/{owner}/{repo}"
                            break
                
                # Pattern 2: Markdown hyperlink in config.json (e.g., [text](https://github.com/owner/repo))
                # Using pattern: \]\((https?://[^\s)]+)\)
                if not repo_url:
                    markdown_pattern = r'\]\((https?://[^\s)]+)\)'
                    markdown_matches = re.finditer(markdown_pattern, config_str, re.IGNORECASE)
                    for match in markdown_matches:
                        url = match.group(1).strip()
                        if 'github.com' in url.lower():
                            github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
                            if github_match:
                                owner, repo = github_match.groups()
                                repo_url = f"https://github.com/{owner}/{repo}"
                                break
                
                # Pattern 3: Generic URL finder in config.json
                # Using pattern: https?://[^\s"'>)]+
                if not repo_url:
                    generic_url_pattern = r'https?://[^\s"\'>)]+'
                    generic_matches = re.finditer(generic_url_pattern, config_str, re.IGNORECASE)
                    for match in generic_matches:
                        url = match.group(0).strip()
                        if 'github.com' in url.lower():
                            github_match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', url, re.IGNORECASE)
                            if github_match:
                                owner, repo = github_match.groups()
                                repo_url = f"https://github.com/{owner}/{repo}"
                                break
                
                # Fallback: Legacy patterns for JSON fields
                if not repo_url:
                    github_patterns = [
                        r"https?://(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)",
                        r'"github"\s*:\s*"([^"]+)"',
                        r'"repository"\s*:\s*"([^"]+)"',
                        r'"repo"\s*:\s*"([^"]+)"',
                        r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                    ]
                    for pattern in github_patterns:
                        matches = re.findall(pattern, config_str, re.IGNORECASE)
                        if matches:
                            if isinstance(matches[0], tuple) and len(matches[0]) == 2:
                                # Pattern matched owner/repo
                                owner, repo = matches[0]
                                repo_url = f"https://github.com/{owner}/{repo}"
                            elif isinstance(matches[0], str):
                                # Pattern matched URL string
                                url_match = matches[0]
                                if url_match.startswith("http"):
                                    repo_url = url_match
                                elif "/" in url_match and len(url_match.split("/")) >= 2:
                                    parts = url_match.split("/")
                                    if "github.com" in parts:
                                        idx = parts.index("github.com")
                                        if idx + 2 < len(parts):
                                            owner = parts[idx + 1]
                                            repo = (
                                            parts[idx + 2]
                                            .split("/")[0]
                                            .split("?")[0]
                                            .split("#")[0]
                                        )
                                        repo_url = f"https://github.com/{owner}/{repo}"
                                else:
                                    # Assume it's owner/repo format
                                    owner, repo = url_match.split("/")[:2]
                                    repo_url = f"https://github.com/{owner}/{repo}"
                        break

            try:
                from ..acmecli.hf_handler import fetch_hf_metadata

                clean_model_id = model_id.replace(
                    "https://huggingface.co/", ""
                ).replace("http://huggingface.co/", "")
                hf_url = f"https://huggingface.co/{clean_model_id}"
                hf_meta = fetch_hf_metadata(hf_url)
                if hf_meta:
                    meta["stars"] = hf_meta.get("likes", 0)
                    meta["downloads"] = hf_meta.get("downloads", 0)
                    if hf_meta.get("modelId"):
                        meta["full_name"] = hf_meta.get("modelId", model_id)
                    # Extract description for better scoring
                    description = hf_meta.get("description", "") or hf_meta.get(
                        "cardData", {}
                    ).get("description", "")
                    if description and not meta.get("readme_text"):
                        meta["readme_text"] = description
                    elif description and meta.get("readme_text"):
                        # Append description to readme if not already present
                        if (
                            description.lower()
                            not in meta.get("readme_text", "").lower()
                        ):
                            meta["readme_text"] = (
                                description + "\n\n" + meta.get("readme_text", "")
                            )
                    # Extract tags/topics for better scoring
                    tags = hf_meta.get("tags", []) or hf_meta.get("cardData", {}).get(
                        "tags", []
                    )
                    if tags:
                        meta["tags"] = tags
                    hf_license = hf_meta.get("license", "") or hf_meta.get(
                        "cardData", {}
                    ).get("license", "")
                    if hf_license and not meta.get("license"):
                        meta["license"] = hf_license.lower()
                    
                    # Check description for GitHub URL early
                    if description and not repo_url:
                        repo_url = extract_github_url_from_text(description)
                        if repo_url:
                            print(f"[INGEST] Found GitHub URL in description: {repo_url}")

                    if not repo_url:
                        if isinstance(hf_meta, dict):
                            github_field = hf_meta.get("github", "")
                            if github_field:
                                print(f"[INGEST] Found github field in hf_meta: {github_field} (type: {type(github_field)})")
                                if isinstance(github_field, str):
                                    if github_field.startswith("http"):
                                        repo_url = github_field
                                    else:
                                        repo_url = f"https://github.com/{github_field}"
                                    print(f"[INGEST] Extracted GitHub URL from github field: {repo_url}")
                                elif isinstance(github_field, dict):
                                    repo_url = github_field.get(
                                        "url"
                                    ) or github_field.get("repo")
                                    if repo_url:
                                        print(f"[INGEST] Extracted GitHub URL from github dict: {repo_url}")
                            
                            if not repo_url:
                                card_data = hf_meta.get("cardData", {})
                                if isinstance(card_data, dict):
                                    readme_text = card_data.get("---", "")
                                    if isinstance(readme_text, str) and not meta.get(
                                        "readme_text"
                                    ):
                                        meta["readme_text"] = readme_text
                                    card_license = card_data.get("license", "")
                                    if card_license and not meta.get("license"):
                                        meta["license"] = card_license.lower()
                                    for key, value in card_data.items():
                                        if isinstance(value, str) and (
                                            "github.com" in value.lower()
                                            or "github" in key.lower()
                                        ):
                                            github_match = re.search(
                                                r"https?://github\.com/[\w\-\.]+/[\w\-\.]+",
                                                value,
                                            )
                                            if github_match:
                                                repo_url = github_match.group(0)
                                                break
                                            elif (
                                                "/" in value and len(value.split("/")) == 2
                                            ):
                                                potential_repo = value.strip()
                                                if not potential_repo.startswith("http"):
                                                    repo_url = f"https://github.com/{potential_repo}"
                                                break
                            
                            if not repo_url:
                                hf_meta_str = json.dumps(hf_meta)
                                repo_url = extract_github_url_from_text(hf_meta_str)
                                if repo_url:
                                    print(f"[INGEST] Found GitHub URL in HuggingFace metadata: {repo_url}")
                            
                            if not repo_url:
                                tags = hf_meta.get("tags", []) or []
                                for tag in tags:
                                    if isinstance(tag, str) and "github.com" in tag.lower():
                                        github_match = re.search(
                                            r"https?://github\.com/[\w\-\.]+/[\w\-\.]+",
                                            tag,
                                        )
                                        if github_match:
                                            repo_url = github_match.group(0)
                                            break
                            
                            if not repo_url:
                                model_index = hf_meta.get("model_index", "")
                                if isinstance(model_index, str):
                                    repo_url = extract_github_url_from_text(model_index)
                                    if repo_url:
                                        print(f"[INGEST] Found GitHub URL in model_index: {repo_url}")

                    if not repo_url:
                        print(f"[INGEST] Searching entire zip file for GitHub URL...")
                        repo_url = extract_github_url_from_zip(zip_content)
                        if repo_url:
                            print(f"[INGEST] Found GitHub URL in zip file: {repo_url}")
                        else:
                            print(f"[INGEST] No GitHub URL found in zip file")
                    
                    if not repo_url and meta.get("readme_text"):
                        readme = meta.get("readme_text", "")
                        print(f"[INGEST] Extracting GitHub URL from README text (length: {len(readme)})")
                        repo_url = extract_github_url_from_text(readme)
                        if repo_url:
                            print(f"[INGEST] Found GitHub URL in README: {repo_url}")
                        else:
                            print(f"[INGEST] No GitHub URL found in README text")
                    
                    if not repo_url:
                        print(f"[INGEST] WARNING: No GitHub URL found after all extraction attempts")
                        print(f"[INGEST] hf_meta keys: {list(hf_meta.keys()) if isinstance(hf_meta, dict) else 'N/A'}")
                        if isinstance(hf_meta, dict):
                            print(f"[INGEST] hf_meta.get('github'): {hf_meta.get('github')}")
                    
                    if repo_url:
                        meta["github_url"] = repo_url
                        print(f"[INGEST] Successfully set github_url: {repo_url}")
                        meta["github"] = {"prs": [], "direct_commits": []}
                        from ..acmecli.github_handler import fetch_github_metadata

                        try:
                            print(f"[INGEST] Fetching GitHub metadata for {repo_url}")
                            gh_meta = fetch_github_metadata(repo_url)
                            if gh_meta:
                                meta["contributors"] = gh_meta.get("contributors", {})
                                meta["stars"] = gh_meta.get("stars", meta["stars"])
                                meta["forks"] = gh_meta.get("forks", 0)
                                meta["full_name"] = gh_meta.get(
                                    "full_name", meta["full_name"]
                                )
                                meta["pushed_at"] = gh_meta.get("pushed_at")
                                meta["has_wiki"] = gh_meta.get("has_wiki", False)
                                meta["has_pages"] = gh_meta.get("has_pages", False)
                                meta["language"] = gh_meta.get("language", "python")
                                meta["open_issues_count"] = gh_meta.get(
                                    "open_issues_count", 0
                                )
                                gh_size_kb = gh_meta.get("size", 0)
                                if gh_size_kb and gh_size_kb > 0:
                                    meta["size"] = gh_size_kb
                                gh_license = gh_meta.get("license", "")
                                if gh_license and not meta.get("license"):
                                    meta["license"] = gh_license.lower()
                                if gh_meta.get("readme_text") and not meta.get(
                                    "readme_text"
                                ):
                                    meta["readme_text"] = gh_meta.get("readme_text", "")
                                if gh_meta.get("repo_files"):
                                    meta["repo_files"] = meta.get(
                                        "repo_files", set()
                                    ) | gh_meta.get("repo_files", set())
                                if gh_meta.get("github"):
                                    meta["github"] = gh_meta.get("github", {})
                        except Exception as gh_fetch_error:
                            print(
                                f"[INGEST] Warning: Could not fetch GitHub metadata for {repo_url}: {gh_fetch_error}"
                            )
                            print(
                                f"[INGEST] Note: github_url is set but GitHub API data unavailable (may be rate limited)"
                            )
                if config:
                    base_model = (
                        config.get("_name_or_path")
                        or config.get("base_model_name_or_path")
                        or config.get("pretrained_model_name_or_path")
                    )
                    if base_model:
                        parent_id = base_model.replace(
                            "https://huggingface.co/", ""
                        ).replace("http://huggingface.co/", "")
                        if parent_id != clean_model_id:
                            # Simplified parent lookup - just use the parent ID from config
                            # Skip expensive parent model analysis to speed up ingestion
                            parent_score = None

                            # Always set parents array - even if score is None, treescore needs the parent info
                            if parent_score is not None:
                                meta["parents"] = [
                                    {"score": parent_score, "id": parent_id}
                                ]
                            else:
                                # If no score found, set to None but still include parent in lineage
                                meta["parents"] = [{"score": None, "id": parent_id}]
            except Exception as gh_error:
                print(f"[INGEST] Warning: Could not fetch GitHub metadata: {gh_error}")
            license_text_content = meta.get("license_text", "")
            if license_text_content and not meta.get("license"):
                license_text_lower = license_text_content[:100].lower()
                if license_text_lower:
                    meta["license"] = license_text_lower
            if not meta.get("readme_text"):
                print(f"[INGEST] Warning: No README text found for {model_id}")

            print(f"[INGEST] Computing metrics...")
            metrics_start = time.time()

            from ..acmecli.metrics.license_metric import LicenseMetric
            from ..acmecli.metrics.ramp_up_metric import RampUpMetric
            from ..acmecli.metrics.bus_factor_metric import BusFactorMetric
            from ..acmecli.metrics.performance_claims_metric import (
                PerformanceClaimsMetric,
            )
            from ..acmecli.metrics.size_metric import SizeMetric
            from ..acmecli.metrics.dataset_and_code_metric import DatasetAndCodeMetric
            from ..acmecli.metrics.dataset_quality_metric import DatasetQualityMetric
            from ..acmecli.metrics.code_quality_metric import CodeQualityMetric
            from ..acmecli.metrics.reproducibility_metric import ReproducibilityMetric
            from ..acmecli.metrics.reviewedness_metric import ReviewednessMetric
            from ..acmecli.metrics.treescore_metric import TreescoreMetric

            quick_metrics = {
                "license": LicenseMetric().score,
                "ramp_up_time": RampUpMetric().score,
                "bus_factor": BusFactorMetric().score,
                "performance_claims": PerformanceClaimsMetric().score,
                "size_score": SizeMetric().score,
                "dataset_and_code_score": DatasetAndCodeMetric().score,
                "dataset_quality": DatasetQualityMetric().score,
                "code_quality": CodeQualityMetric().score,
                "Reproducibility": ReproducibilityMetric().score,
                "Reviewedness": ReviewednessMetric().score,
                "Treescore": TreescoreMetric().score,
            }
            metric_results = run_acme_metrics(meta, quick_metrics)
            metrics_time = time.time() - metrics_start
            print(f"[INGEST] Computed metrics in {metrics_time:.2f}s")
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        REQUIRED_NON_LATENCY_METRICS = [
            "license",
            "ramp_up",
            "bus_factor",
            "performance_claims",
            "size",
            "dataset_code",
            "dataset_quality",
            "code_quality",
            "reproducibility",
            "reviewedness",
            "treescore",
        ]
        failures = []
        metric_scores_dict = {}
        for metric_name in REQUIRED_NON_LATENCY_METRICS:
            from ..services.rating_config import DEFAULT_SCORE
            result = metric_results.get(metric_name)
            score = DEFAULT_SCORE
            if result is None:
                print(f"[INGEST] WARNING: {metric_name} not found in metric_results. Available keys: {list(metric_results.keys())}")
                failures.append(f"{metric_name}=MISSING")
                metric_scores_dict[metric_name] = DEFAULT_SCORE
                continue
            elif hasattr(result, "value"):
                score = float(result.value) if result.value is not None else DEFAULT_SCORE
            elif isinstance(result, (int, float)):
                score = float(result)
            else:
                print(f"[INGEST] WARNING: {metric_name} has unexpected type: {type(result)}, value: {result}")
                score = DEFAULT_SCORE
            metric_scores_dict[metric_name] = score
            print(f"[INGEST] {metric_name} = {score:.2f}")
            from ..services.rating_config import INGESTIBILITY_THRESHOLD
            if score < INGESTIBILITY_THRESHOLD:
                failures.append(f"{metric_name}={score:.2f}")
        if failures:
            from ..services.rating_config import INGESTIBILITY_THRESHOLD
            print(f"[INGEST] Failed: {', '.join(failures)}")
            msg = f"Model failed ingestibility requirements. Failed metrics: {', '.join(failures)}"
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "INGESTIBILITY_FAILURE",
                    "message": msg,
                    "metric_scores": metric_scores_dict,
                    "required_threshold": INGESTIBILITY_THRESHOLD,
                },
            )

        upload_model(zip_content, model_id, version)
        total_time = time.time() - start_time
        print(f"[INGEST] Success in {total_time:.2f}s")
        return {
            "message": "Model ingestion successful",
            "model_id": model_id,
            "version": version,
            "metric_scores": metric_scores_dict,
            "ingestible": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        print(f"[INGEST] ERROR in model_ingestion: {str(e)}")
        print(f"[INGEST] TRACEBACK:\n{error_traceback}")
        logger.error(f"Failed to ingest model {model_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ingest model: {str(e)}")