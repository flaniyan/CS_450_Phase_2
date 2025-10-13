import boto3
import zipfile
import io
from typing import Dict, Any, List
from fastapi import HTTPException
from botocore.exceptions import ClientError

def build_accesspoint_arn(region: str, account_id: str, access_point_name: str) -> str:
    return f"arn:aws:s3:{region}:{account_id}:accesspoint/{access_point_name}"

region = "us-east-1"
access_point_name = "cs450-s3"

sts = boto3.client("sts")
account_id = sts.get_caller_identity()["Account"]

ap_arn = build_accesspoint_arn(region, account_id, access_point_name)
s3 = boto3.client("s3", region_name=region)

def validate_huggingface_structure(zip_content: bytes) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            file_list = zip_file.namelist()
            has_config = any('config.json' in f for f in file_list)
            has_weights = any(f.endswith(('.bin', '.safetensors')) for f in file_list)
            has_readme = any('README.md' in f for f in file_list)
            return {
                "valid": has_config and has_weights,
                "has_config": has_config,
                "has_weights": has_weights,
                "has_readme": has_readme,
                "files": file_list
            }
    except zipfile.BadZipFile:
        return {"valid": False, "error": "Invalid ZIP file"}

def extract_model_component(zip_content: bytes, component: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            if component == "weights":
                weight_files = [f for f in zip_file.namelist() if f.endswith(('.bin', '.safetensors'))]
                if not weight_files:
                    raise ValueError("No weight files found")
                output = io.BytesIO()
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                    for file in weight_files:
                        new_zip.writestr(file, zip_file.read(file))
                return output.getvalue()
            elif component == "datasets":
                dataset_files = [f for f in zip_file.namelist() if any(ext in f for ext in ['.csv', '.json', '.txt', '.parquet'])]
                if not dataset_files:
                    raise ValueError("No dataset files found")
                output = io.BytesIO()
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                    for file in dataset_files:
                        new_zip.writestr(file, zip_file.read(file))
                return output.getvalue()
            else:
                return zip_content
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")

def upload_model(file_content: bytes, model_id: str, version: str, debloat: bool = False) -> Dict[str, Any]:
    validation = validate_huggingface_structure(file_content)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid HuggingFace model structure. Missing: config.json={not validation['has_config']}, weights={not validation['has_weights']}"
        )
    s3_key = f"models/{model_id}/{version}/model.zip"
    body = file_content
    s3.put_object(
        Bucket=ap_arn,
        Key=s3_key,
        Body=body,
        ContentType='application/zip'
    )
    return {
        "model_id": model_id,
        "version": version,
        "size": len(file_content)
    }

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
