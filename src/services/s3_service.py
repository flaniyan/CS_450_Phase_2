import boto3
import zipfile
import io
import re
from typing import Dict, Any, Optional
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
    version_str = version_str.lstrip('v')
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
def version_matches_range(version_str: str, version_spec: str) -> bool:
    try:
        version = parse_version(version_str)
        if not version:
            return False
        if not any(op in version_spec for op in ['-', '~', '^']):
            spec_version = parse_version(version_spec)
            if spec_version:
                return spec_version == version
            else:
                return False
        if '-' in version_spec and not version_spec.startswith(('~', '^')):
            parts = version_spec.split('-', 1)
            min_ver, max_ver = parse_version(parts[0]), parse_version(parts[1])
            if min_ver and max_ver:
                return min_ver <= version <= max_ver
            else:
                return False
        if version_spec.startswith('~'):
            base = parse_version(version_spec[1:])
            if base:
                return base <= version < (base[0], base[1] + 1, 0)
            else:
                return False
        if version_spec.startswith('^'):
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
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            file_list = zip_file.namelist()
            has_config = any('config.json' in f for f in file_list)
            has_weights = any(f.endswith(('.bin', '.safetensors')) for f in file_list)
            return {
                "valid": has_config and has_weights,
                "has_config": has_config,
                "has_weights": has_weights,
                "files": file_list
            }
    except zipfile.BadZipFile:
        return {"valid": False, "error": "Invalid ZIP file"}

def extract_model_component(zip_content: bytes, component: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            if component == "weights":
                files = [f for f in zip_file.namelist() if f.endswith(('.bin', '.safetensors'))]
            elif component == "datasets":
                files = [f for f in zip_file.namelist() if any(ext in f for ext in ['.txt', '.json'])]
            else:
                return zip_content
            if not files:
                raise ValueError(f"No {component} files found")
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                for file in files:
                    new_zip.writestr(file, zip_file.read(file))
            return output.getvalue()
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")

def upload_model(file_content: bytes, model_id: str, version: str, debloat: bool = False) -> Dict[str, str]:
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
    try:
        validation = validate_huggingface_structure(file_content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid HuggingFace model structure. Missing: config.json={not validation['has_config']}, weights={not validation['has_weights']}"
            )
        s3_key = f"models/{model_id}/{version}/model.zip"
        s3.put_object(
            Bucket=ap_arn,
            Key=s3_key,
            Body=file_content,
            ContentType='application/zip'
        )
        print(f"AWS S3 upload successful: {model_id} v{version} ({len(file_content)} bytes) -> {s3_key}")
        return {"message": "Upload successful"}
    except Exception as e:
        print(f"AWS S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"AWS upload failed: {str(e)}")

def download_model(model_id: str, version: str, component: str = "full") -> bytes:
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
    try:
        s3_key = f"models/{model_id}/{version}/model.zip"
        response = s3.get_object(Bucket=ap_arn, Key=s3_key)
        zip_content = response['Body'].read()
        if component != "full":
            try:
                result = extract_model_component(zip_content, component)
                print(f"AWS S3 download successful: {model_id} v{version} ({component})")
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
            '.' in regex_pattern and
            not any(char in regex_pattern for char in [' ', '\n', '\t']) and
            len(regex_pattern) < 50
        )
        if is_likely_filename:
            try:
                s3_key = f"models/{model_id}/{version}/model.zip"
                response = s3.head_object(Bucket=ap_arn, Key=s3_key)
                file_size = response['ContentLength']
                for tail_size in [32768, 65536, 131072]:  # 32KB, 64KB, 128KB
                    try:
                        range_start = max(0, file_size - tail_size)
                        response = s3.get_object(Bucket=ap_arn, Key=s3_key, Range=f'bytes={range_start}-{file_size-1}')
                        zip_tail = response['Body'].read()
                        with zipfile.ZipFile(io.BytesIO(zip_tail), 'r') as zip_file:
                            for file_info in zip_file.filelist:
                                filename = file_info.filename.lower()
                                if any(ext in filename for ext in ['.txt', '.json', '.md']):
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
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            for file_info in zip_file.filelist:
                filename = file_info.filename.lower()
                if any(ext in filename for ext in ['.txt', '.json', '.md']):
                    if pattern.search(filename):
                        _model_card_cache[cache_key] = cached_content
                        return True
                    try:
                        content = zip_file.read(file_info).decode('utf-8', errors='ignore')
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

def list_models(name_regex: str = None, model_regex: str = None, version_range: str = None, limit: int = 100, continuation_token: str = None) -> Dict[str, Any]:
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
    limit = min(limit, 1000)
    try:
        params = {'Bucket': ap_arn, 'Prefix': 'models/', 'MaxKeys': limit}
        if continuation_token:
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
                        if version_range:
                            normalized_version = model_version.lstrip('v')
                            if not version_matches_range(normalized_version, version_range):
                                continue
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")

def reset_registry() -> Dict[str, str]:
    if not aws_available:
        raise HTTPException(status_code=503, detail="AWS services not available. Please check your AWS configuration.")
    try:
        response = s3.list_objects_v2(Bucket=ap_arn, Prefix="models/")
        if 'Contents' in response:
            deleted_count = 0
            for item in response['Contents']:
                s3.delete_object(Bucket=ap_arn, Key=item['Key'])
                deleted_count += 1
            print(f"AWS S3 reset successful: Deleted {deleted_count} objects")
        else:
            print("AWS S3 reset successful: No objects found to delete")
        return {"message": "Reset done successfully"}
    except Exception as e:
        print(f"AWS S3 reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset registry: {str(e)}")