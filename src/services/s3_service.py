import boto3
import zipfile
import io
import re
from typing import Dict, Any, Optional
from fastapi import HTTPException

region = "us-east-1"
access_point_name = "cs450-s3"
sts = boto3.client("sts")
account_id = sts.get_caller_identity()["Account"]
ap_arn = f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"
s3 = boto3.client("s3", region_name=region)

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
                return min_ver <= version < max_ver
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
                files = [f for f in zip_file.namelist() if any(ext in f for ext in ['.csv', '.json', '.txt', '.parquet'])]
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
    return {"message": "Upload successful"}

def download_model(model_id: str, version: str, component: str = "full") -> bytes:
    s3_key = f"models/{model_id}/{version}/model.zip"
    response = s3.get_object(Bucket=ap_arn, Key=s3_key)
    zip_content = response['Body'].read()
    if component != "full":
        try:
            return extract_model_component(zip_content, component)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return zip_content

def list_models(name_regex: str = None, model_regex: str = None, version_range: str = None, limit: int = 100, continuation_token: str = None) -> Dict[str, Any]:
    limit = min(limit, 1000)
    try:
        params = {'Bucket': ap_arn, 'Prefix': 'models/', 'MaxKeys': limit}
        if continuation_token:
            params['ContinuationToken'] = continuation_token
        
        response = s3.list_objects_v2(**params)
        results = []
        
        if 'Contents' in response:
            for item in response['Contents']:
                key = item['Key']
                if key.endswith('/model.zip'):
                    if len(key.split('/')) >= 3:
                        model_name = key.split('/')[1]
                        model_version = key.split('/')[2]
                        if name_regex or model_regex:
                            regex_pattern = name_regex or model_regex
                            try:
                                pattern = re.compile(regex_pattern, re.IGNORECASE)
                                if not pattern.search(model_name):
                                    continue
                            except re.error as e:
                                raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")
                        if version_range:
                            normalized_version = model_version.lstrip('v')
                            if not version_matches_range(normalized_version, version_range):
                                continue
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
    try:
        response = s3.list_objects_v2(Bucket=ap_arn, Prefix="models/")
        if 'Contents' in response:
            for item in response['Contents']:
                s3.delete_object(Bucket=ap_arn, Key=item['Key'])
        return {"message": "Reset done successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset registry: {str(e)}")
