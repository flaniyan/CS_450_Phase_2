import io
import re
import zipfile
from typing import Any, Dict, Optional

import boto3
from fastapi import HTTPException

region = "us-east-1"
access_point_name = "cs450-s3"

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
    account_id = "838693051036"  # Use the actual account ID from the URL
    ap_arn = f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"
    s3 = None
    aws_available = False


def parse_version(version_str: str) -> tuple:
    version_str = version_str.lstrip("v")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
<<<<<<< Updated upstream
    
=======


>>>>>>> Stashed changes
def version_matches_range(version_str: str, version_spec: str) -> bool:
    try:
        version = parse_version(version_str)
        if not version:
            return False
<<<<<<< Updated upstream
        if not any(op in version_spec for op in ['-', '~', '^']):
=======

        if not any(op in version_spec for op in ["-", "~", "^"]):
>>>>>>> Stashed changes
            spec_version = parse_version(version_spec)
            if spec_version:
                return spec_version == version
            else:
                return False
<<<<<<< Updated upstream
        if '-' in version_spec and not version_spec.startswith(('~', '^')):
            parts = version_spec.split('-', 1)
=======

        if "-" in version_spec and not version_spec.startswith(("~", "^")):
            parts = version_spec.split("-", 1)
>>>>>>> Stashed changes
            min_ver, max_ver = parse_version(parts[0]), parse_version(parts[1])
            if min_ver and max_ver:
                return min_ver <= version <= max_ver
            else:
                return False
<<<<<<< Updated upstream
        if version_spec.startswith('~'):
=======

        if version_spec.startswith("~"):
>>>>>>> Stashed changes
            base = parse_version(version_spec[1:])
            if base:
                return base <= version < (base[0], base[1] + 1, 0)
            else:
                return False
<<<<<<< Updated upstream
        if version_spec.startswith('^'):
=======

        if version_spec.startswith("^"):
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        return False
    except Exception:
        return False
        
=======

        return False
    except Exception:
        return False


>>>>>>> Stashed changes
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
                    if any(ext in f for ext in [".csv", ".json", ".txt", ".parquet"])
                ]
            else:
                return zip_content
<<<<<<< Updated upstream
            if not files:
                raise ValueError(f"No {component} files found")
=======

            if not files:
                raise ValueError(f"No {component} files found")

>>>>>>> Stashed changes
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for file in files:
                    new_zip.writestr(file, zip_file.read(file))
            return output.getvalue()
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")


def upload_model(
    file_content: bytes, model_id: str, version: str, debloat: bool = False
) -> Dict[str, str]:
    if not aws_available:
<<<<<<< Updated upstream
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
=======
        # For development/testing purposes, simulate successful upload
        print(
            f"AWS not active. Mock upload: {model_id} v{version} ({len(file_content)} bytes)"
        )
        # Store in mock storage
        _mock_models.append(
            {
                "model_id": model_id,
                "version": version,
                "size": len(file_content),
                "upload_time": "2024-01-01T00:00:00Z",
            }
        )
        return {"message": "Upload successful (mock mode - AWS not available)"}

    # AWS is available - proceed with real S3 upload
>>>>>>> Stashed changes
    try:
        validation = validate_huggingface_structure(file_content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid HuggingFace model structure. Missing: config.json={not validation['has_config']}, weights={not validation['has_weights']}",
            )
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
        s3_key = f"models/{model_id}/{version}/model.zip"
        s3.put_object(
            Bucket=ap_arn, Key=s3_key, Body=file_content, ContentType="application/zip"
        )
        print(
            f"AWS S3 upload successful: {model_id} v{version} ({len(file_content)} bytes) -> {s3_key}"
        )
        return {"message": "Upload successful"}
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
    except Exception as e:
        print(f"AWS S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"AWS upload failed: {str(e)}")


def download_model(model_id: str, version: str, component: str = "full") -> bytes:
    if not aws_available:
<<<<<<< Updated upstream
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
=======
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )

    # AWS is available - proceed with real S3 download
>>>>>>> Stashed changes
    try:
        s3_key = f"models/{model_id}/{version}/model.zip"
        print(f"AWS S3 download: {model_id} v{version} ({component}) -> {s3_key}")
        response = s3.get_object(Bucket=ap_arn, Key=s3_key)
<<<<<<< Updated upstream
        zip_content = response['Body'].read()
=======
        zip_content = response["Body"].read()

>>>>>>> Stashed changes
        if component != "full":
            try:
                result = extract_model_component(zip_content, component)
                print(
                    f"AWS S3 download successful: {model_id} v{version} ({component})"
                )
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
<<<<<<< Updated upstream
        print(f"AWS S3 download successful: {model_id} v{version} (full)")
        return zip_content
=======

        print(f"AWS S3 download successful: {model_id} v{version} (full)")
        return zip_content

>>>>>>> Stashed changes
    except Exception as e:
        print(f"AWS S3 download failed: {e}")
        raise HTTPException(status_code=500, detail=f"AWS download failed: {str(e)}")

<<<<<<< Updated upstream
# Cache for model card content to avoid repeated downloads
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
        zip_content = download_model(model_id, version, "full")
        if not zip_content:
            return False
        pattern = re.compile(regex_pattern, re.IGNORECASE)
        cached_content = []
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            for file_info in zip_file.filelist:
                filename = file_info.filename.lower()
                if any(ext in filename for ext in ['.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.ts', '.cfg', '.ini']):
                    try:
                        content = zip_file.read(file_info).decode('utf-8', errors='ignore')
                        cached_content.append(content)
                        if pattern.search(content):
                            _model_card_cache[cache_key] = cached_content
                            return True
                    except:
                        continue
        _model_card_cache[cache_key] = cached_content
        return False
    except Exception:
        return False

def list_models(name_regex: str = None, model_regex: str = None, version_range: str = None, limit: int = 100, continuation_token: str = None) -> Dict[str, Any]:
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
=======

def list_models(
    name_regex: str = None,
    model_regex: str = None,
    version_range: str = None,
    limit: int = 100,
    continuation_token: str = None,
) -> Dict[str, Any]:
    if not aws_available:
        # Return mock data for development
        filtered_models = []
        for model in _mock_models:
            # Apply name filtering if specified
            if name_regex:
                if not re.search(name_regex, model["model_id"], re.IGNORECASE):
                    continue

            # Apply version range filtering if specified
            if version_range:
                normalized_version = model["version"].lstrip("v")
                if not version_matches_range(normalized_version, version_range):
                    continue

            filtered_models.append(
                {
                    "model_id": model["model_id"],
                    "version": model["version"],
                    "size": model["size"],
                    "upload_time": model["upload_time"],
                    "download_url": f"http://localhost:3000/api/packages/models/{model['model_id']}/versions/{model['version']}/download",
                }
            )
        return {"models": filtered_models[:limit], "next_token": None}

>>>>>>> Stashed changes
    limit = min(limit, 1000)
    try:
        params = {"Bucket": ap_arn, "Prefix": "models/", "MaxKeys": limit}
        if continuation_token:
<<<<<<< Updated upstream
            params['ContinuationToken'] = continuation_token
        response = s3.list_objects_v2(**params)
        results = []
        if 'Contents' in response:
            name_pattern = None
            if name_regex:
                try:
                    name_pattern = re.compile(name_regex, re.IGNORECASE)
                except re.error as e:
                    raise HTTPException(status_code=400, detail=f"Invalid name regex: {str(e)}")
            for item in response['Contents']:
                key = item['Key']
                if key.endswith('/model.zip'):
                    if len(key.split('/')) >= 3:
                        model_name = key.split('/')[1]
                        model_version = key.split('/')[2]
                        if name_pattern and not name_pattern.search(model_name):
                            continue
=======
            params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**params)
        results = []

        if "Contents" in response:
            for item in response["Contents"]:
                key = item["Key"]
                if key.endswith("/model.zip"):
                    if len(key.split("/")) >= 3:
                        model_name = key.split("/")[1]
                        model_version = key.split("/")[2]
                        if name_regex or model_regex:
                            regex_pattern = name_regex or model_regex
                            try:
                                pattern = re.compile(regex_pattern, re.IGNORECASE)
                                if not pattern.search(model_name):
                                    continue
                            except re.error as e:
                                raise HTTPException(
                                    status_code=400, detail=f"Invalid regex: {str(e)}"
                                )
>>>>>>> Stashed changes
                        if version_range:
                            normalized_version = model_version.lstrip("v")
                            if not version_matches_range(
                                normalized_version, version_range
                            ):
                                continue
<<<<<<< Updated upstream
                        if model_regex:
                            try:
                                if not search_model_card_content(model_name, model_version, model_regex):
                                    continue
                            except re.error as e:
                                raise HTTPException(status_code=400, detail=f"Invalid model regex: {str(e)}")
                        results.append({
                            "name": model_name,
                            "version": model_version
                        })
        return {
            "models": results,
            "next_token": response.get('NextContinuationToken')
        }
=======
                        results.append({"name": model_name, "version": model_version})
        return {"models": results, "next_token": response.get("NextContinuationToken")}
>>>>>>> Stashed changes
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


def reset_registry() -> Dict[str, str]:
    if not aws_available:
<<<<<<< Updated upstream
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
    try:
        print("AWS S3 reset: Starting registry reset...")
        response = s3.list_objects_v2(Bucket=ap_arn, Prefix="models/")
        if 'Contents' in response:
=======
        raise HTTPException(
            status_code=503,
            detail="AWS services not available. Please check your AWS configuration.",
        )

    # AWS is available - proceed with real S3 reset
    try:
        print("AWS S3 reset: Starting registry reset...")
        response = s3.list_objects_v2(Bucket=ap_arn, Prefix="models/")

        if "Contents" in response:
>>>>>>> Stashed changes
            deleted_count = 0
            for item in response["Contents"]:
                s3.delete_object(Bucket=ap_arn, Key=item["Key"])
                deleted_count += 1
            print(f"AWS S3 reset successful: Deleted {deleted_count} objects")
        else:
            print("AWS S3 reset: No objects found to delete")
<<<<<<< Updated upstream
        return {"message": "Reset done successfully"}
    except Exception as e:
        print(f"AWS S3 reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset registry: {str(e)}")
=======

        return {"message": "Reset done successfully"}

    except Exception as e:
        print(f"AWS S3 reset failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to reset registry: {str(e)}"
        )
>>>>>>> Stashed changes
