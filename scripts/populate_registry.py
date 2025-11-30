#!/usr/bin/env python3
"""
Populate Registry with 500 Real HuggingFace Models

This script populates the ACME Model Registry with 500 real models from HuggingFace,
including the required Tiny-LLM model for performance testing.

Usage:
    # Use remote API (default):
    python scripts/populate_registry.py
    
    # Use local server:
    python scripts/populate_registry.py --local
    
    # Use custom URL:
    python scripts/populate_registry.py --url http://localhost:8000
    
    # Performance mode (stores in performance/ S3 path, bypasses API):
    python scripts/populate_registry.py --performance
    
    # Or with environment variable:
    API_BASE_URL=http://localhost:3000 python scripts/populate_registry.py
"""
import sys
import os
import time
import requests
import json
import argparse
import boto3
import uuid
import zipfile
import io
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"

HF_API_BASE = "https://huggingface.co/api"
MAX_RETRIES = 3
RETRY_DELAY = 2

# AWS Configuration (for performance mode)
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_POINT_NAME = os.getenv("S3_ACCESS_POINT_NAME", "cs450-s3")
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")

# Required model (must be included)
REQUIRED_MODEL = "arnir0/Tiny-LLM"

# Import the hardcoded list of 500 models
try:
    from scripts.huggingface_models_list import HF_MODELS_500
    POPULAR_MODELS = HF_MODELS_500
except ImportError:
    # Fallback if import fails - use minimal list
    POPULAR_MODELS = [
        "arnir0/Tiny-LLM",
        "bert-base-uncased",
        "distilbert-base-uncased",
        "roberta-base",
        "gpt2",
        "t5-small",
        "t5-base",
        "facebook/bart-base",
    ]


def get_authentication_token(api_base_url: str) -> Optional[str]:
    """Get authentication token for API requests"""
    try:
        response = requests.put(
            f"{api_base_url}/authenticate",
            json={
                "user": {
                    "name": "ece30861defaultadminuser",
                    "is_admin": True
                },
                "secret": {
                    "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
                }
            },
            timeout=10
        )
        if response.status_code == 200:
            token = response.text.strip('"')
            return token
        else:
            print(f"Warning: Authentication failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"Warning: Could not authenticate: {e}")
        return None


def get_hardcoded_models(count: int = 500) -> List[str]:
    """
    Get hardcoded list of 500 real HuggingFace models.
    No API calls - just returns the pre-defined list.
    """
    models = POPULAR_MODELS.copy()
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
        models.insert(0, REQUIRED_MODEL)
    
    # Limit to exactly count
    models = models[:count]
    
    return models


# Removed check_model_exists - we'll skip existence checks and just ingest


def check_model_exists_on_hf(model_id: str) -> bool:
    """Check if a model exists on HuggingFace before attempting ingestion"""
    try:
        clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "")
        api_url = f"https://huggingface.co/api/models/{clean_model_id}"
        response = requests.get(api_url, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def get_s3_client_and_arn():
    """Get S3 client and access point ARN for performance mode"""
    try:
        sts = boto3.client("sts", region_name=REGION)
        account_id = sts.get_caller_identity()["Account"]
        ap_arn = f"arn:aws:s3:{REGION}:{account_id}:accesspoint/{ACCESS_POINT_NAME}"
        s3 = boto3.client("s3", region_name=REGION)
        # Test connection
        s3.list_objects_v2(Bucket=ap_arn, Prefix="performance/", MaxKeys=1)
        return s3, ap_arn
    except Exception as e:
        print(f"Error initializing S3: {e}")
        print("Make sure AWS credentials are configured and S3 access point exists")
        return None, None


def get_dynamodb_table():
    """Get DynamoDB artifacts table for performance mode"""
    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(ARTIFACTS_TABLE)
        # Test access
        table.scan(Limit=1)
        return table
    except Exception as e:
        print(f"Error accessing DynamoDB: {e}")
        return None


def download_from_huggingface(model_id: str, version: str = "main", download_all: bool = False) -> bytes:
    """Download model files from HuggingFace and create ZIP
    
    Args:
        model_id: HuggingFace model identifier
        version: Model version/branch (default: "main")
        download_all: If True, download all files including model weights. If False, only essential/config files.
                      WARNING: download_all=True can be very slow for large models (several GB).
    """
    try:
        clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "")
        api_url = f"https://huggingface.co/api/models/{clean_model_id}"
        
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Model {clean_model_id} not found on HuggingFace")
        
        model_info = response.json()
        all_files = []
        for sibling in model_info.get("siblings", []):
            if sibling.get("rfilename"):
                all_files.append(sibling["rfilename"])
        
        if download_all:
            # Smart download: essential files + ONE main weight file + tokenizer files
            # This matches what the original API does but includes the actual model binary
            
            # 1. Essential files (config, README, etc.)
            essential_files = []
            for filename in all_files:
                if filename.endswith((".json", ".md", ".txt", ".yml", ".yaml")):
                    essential_files.append(filename)
                elif filename.startswith("README") or filename.startswith("readme"):
                    essential_files.append(filename)
                elif filename in ["config.json", "LICENSE", "license", "LICENCE", "licence"]:
                    essential_files.append(filename)
            
            # 2. Find ONE main weight file (prefer .safetensors, then pytorch_model.bin, skip CoreML/others)
            weight_files = [f for f in all_files if any(f.endswith(ext) for ext in [".safetensors", ".bin", ".pt", ".pth"]) 
                          and not any(exclude in f.lower() for exclude in ["coreml", "onnx", "tf", "tflite", "mlpackage"])]
            main_weight_file = None
            if weight_files:
                # Prefer model.safetensors or pytorch_model.bin in root
                for preferred in ["model.safetensors", "pytorch_model.bin"]:
                    if preferred in weight_files:
                        main_weight_file = preferred
                        break
                # If no preferred found, take the first one (smallest path usually)
                if not main_weight_file:
                    # Prefer files in root directory (shorter paths)
                    root_files = [f for f in weight_files if "/" not in f]
                    main_weight_file = root_files[0] if root_files else weight_files[0]
            
            # 3. Tokenizer files (needed for model to work)
            tokenizer_files = [f for f in all_files if "tokenizer" in f.lower() and 
                              (f.endswith(".json") or f.endswith(".model") or "vocab" in f.lower())]
            
            # Combine: essential + one weight file + tokenizer files
            files_to_download = essential_files.copy()
            if main_weight_file:
                files_to_download.append(main_weight_file)
            files_to_download.extend(tokenizer_files)
            
            # Remove duplicates
            files_to_download = list(dict.fromkeys(files_to_download))  # Preserves order
            
            print(f"    Downloading {len(files_to_download)} files", end="")
            if main_weight_file:
                print(f" (1 weight file: {main_weight_file.split('/')[-1]})", end="")
            if tokenizer_files:
                print(f", {len(tokenizer_files)} tokenizer file(s)", end="")
            print("...")
        else:
            # Get essential files only (same logic as s3_service.py)
            essential_files = []
            for filename in all_files:
                if filename.endswith((".json", ".md", ".txt", ".yml", ".yaml")):
                    essential_files.append(filename)
                elif filename.startswith("README") or filename.startswith("readme"):
                    essential_files.append(filename)
                elif filename in ["config.json", "LICENSE", "license", "LICENCE", "licence"]:
                    essential_files.append(filename)
            files_to_download = essential_files
        
        if not files_to_download:
            raise Exception(f"No files found for model {clean_model_id}")
        
        if not download_all:
            print(f"    Downloading {len(files_to_download)} essential file(s)...")
        
        # Download files and create ZIP
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
            def download_file(url: str, filename: str) -> tuple:
                try:
                    is_large_file = any(filename.endswith(ext) for ext in [".bin", ".safetensors", ".pt", ".pth", ".ckpt"])
                    if is_large_file:
                        print(f"      Downloading {filename} (model weights, may take a moment)...")
                    else:
                        print(f"      Downloading {filename}...")
                    
                    # Use streaming for large files, regular for small ones
                    if is_large_file:
                        file_response = requests.get(url, timeout=600, stream=True)
                    else:
                        file_response = requests.get(url, timeout=120)
                    
                    if file_response.status_code == 200:
                        if is_large_file and hasattr(file_response, 'iter_content'):
                            # Stream large files to avoid memory issues
                            content = b""
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    content += chunk
                        else:
                            content = file_response.content
                        
                        size_mb = len(content) / (1024 * 1024)
                        if size_mb > 1:
                            print(f"      ✓ Downloaded {filename} ({size_mb:.2f} MB)")
                        else:
                            size_kb = len(content) / 1024
                            print(f"      ✓ Downloaded {filename} ({size_kb:.1f} KB)")
                        return (filename, content)
                    else:
                        print(f"      ✗ Failed to download {filename}: HTTP {file_response.status_code}")
                        return (filename, None)
                except requests.exceptions.Timeout:
                    print(f"      ✗ Timeout downloading {filename} (file may be too large)")
                    return (filename, None)
                except Exception as e:
                    print(f"      ✗ Error downloading {filename}: {str(e)}")
                    return (filename, None)
            
            urls = [
                (f"https://huggingface.co/{clean_model_id}/resolve/{version}/{filename}", filename)
                for filename in files_to_download
            ]
            
            # Download sequentially to avoid overwhelming memory and network
            # This also gives better progress visibility
            downloaded_count = 0
            failed_count = 0
            total_size = 0
            
            for i, (url, filename) in enumerate(urls, 1):
                filename_result, content = download_file(url, filename)
                if content:
                    zip_file.writestr(filename_result, content)
                    downloaded_count += 1
                    total_size += len(content)
                else:
                    failed_count += 1
                    # Don't fail completely if a non-critical file fails
                    if filename in ["config.json"]:
                        raise Exception(f"Failed to download critical file: {filename}")
            
            if downloaded_count == 0:
                raise Exception(f"Failed to download any files for model {clean_model_id}")
            
            if failed_count > 0:
                print(f"    ⚠ {failed_count} file(s) failed to download (continuing with {downloaded_count} successful)")
            
            total_mb = total_size / (1024 * 1024)
            print(f"    Total downloaded: {total_mb:.2f} MB ({downloaded_count} files)")
        
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Failed to download from HuggingFace: {str(e)}")


def upload_model_to_performance_s3(s3, ap_arn: str, model_id: str, version: str, zip_content: bytes) -> str:
    """Upload model ZIP directly to S3 at performance/ path"""
    # Sanitize model_id for S3 key (same logic as s3_service.py)
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
    
    # Use performance/ prefix instead of models/
    s3_key = f"performance/{safe_model_id}/{safe_version}/model.zip"
    
    s3.put_object(
        Bucket=ap_arn,
        Key=s3_key,
        Body=zip_content,
        ContentType="application/zip"
    )
    
    return s3_key


def create_dummy_model_metadata(table, model_id: str, version: str = "main") -> bool:
    """Create a dummy model entry in DynamoDB (metadata-only, no actual file)"""
    try:
        artifact_id = str(uuid.uuid4())
        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
        )
        
        item = {
            "artifact_id": artifact_id,
            "name": model_id,  # Original name
            "type": "model",
            "version": version,
            "url": f"https://huggingface.co/{model_id}",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        
        table.put_item(Item=item)
        return True
    except Exception as e:
        print(f"  Error creating metadata for {model_id}: {str(e)}")
        return False


def ingest_model_performance_mode(s3, ap_arn: str, table, model_id: str, version: str = "main", skip_missing: bool = True) -> tuple:
    """
    Ingest model in performance mode: download from HF and upload to S3 at performance/ path.
    - Tiny-LLM: Downloads full model including binary (needed for performance testing)
    - Other models: Downloads only essential files (config, README, etc.) for speed
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
    """
    # Check if model exists on HuggingFace first
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"  ⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    # Full ingestion: download and upload to S3
    try:
        # Tiny-LLM needs the full model (including binary) for performance testing
        # Other models only need essential files for registry population
        is_tiny_llm = (model_id == REQUIRED_MODEL)
        
        if is_tiny_llm:
            print(f"  Downloading full model from HuggingFace (including model weights for performance testing)...")
            # Download essential files + ONE main weight file + tokenizer files
            zip_content = download_from_huggingface(model_id, version, download_all=True)
        else:
            print(f"  Downloading essential files from HuggingFace (config, README, etc.)...")
            # Download only essential files (no model weights - faster!)
            zip_content = download_from_huggingface(model_id, version, download_all=False)
        
        zip_size_mb = len(zip_content) / (1024 * 1024)
        print(f"  ✓ Downloaded {len(zip_content):,} bytes ({zip_size_mb:.2f} MB) total")
        
        print(f"  Uploading to S3 at performance/ path...")
        s3_key = upload_model_to_performance_s3(s3, ap_arn, model_id, version, zip_content)
        print(f"  ✓ Uploaded to: {s3_key}")
        
        # Create metadata in DynamoDB
        artifact_id = str(uuid.uuid4())
        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
        )
        
        item = {
            "artifact_id": artifact_id,
            "name": model_id,
            "type": "model",
            "version": version,
            "url": f"https://huggingface.co/{model_id}",
            "s3_path": s3_key,  # Store the performance/ path
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        
        table.put_item(Item=item)
        print(f"  ✓ Metadata created in DynamoDB")
        
        return (True, None)
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "404" in error_msg:
            print(f"  ⊘ Model not found: {model_id} (skipping)")
            return (False, "not_found")
        else:
            print(f"  ✗ Failed: {error_msg}")
            return (False, "error")


def ingest_model(api_base_url: str, model_id: str, auth_token: Optional[str], retry: int = 0, skip_missing: bool = True) -> tuple:
    """
    Ingest a single model into the registry.
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
    """
    # Quick check if model exists on HuggingFace (avoid unnecessary API calls)
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    try:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["X-Authorization"] = auth_token
        
        # Use the /artifact/model endpoint to ingest
        url = f"{api_base_url}/artifact/model"
        payload = {
            "url": f"https://huggingface.co/{model_id}"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code in [200, 201, 202]:
            print(f"✓ Successfully ingested: {model_id}")
            return (True, None)
        elif response.status_code == 409:
            print(f"⊘ Already exists: {model_id} (skipping)")
            return (True, None)  # Consider existing models as success
        elif response.status_code == 404:
            # Model doesn't exist - don't retry
            error_text = response.text[:200]
            if "not found on HuggingFace" in error_text or "not found" in error_text.lower():
                print(f"⊘ Model not found: {model_id} (skipping)")
                return (False, "not_found")
            else:
                print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {error_text}")
                return (False, "error")
        else:
            print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {response.text[:200]}")
            if retry < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
            return (False, "error")
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout ingesting {model_id}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
        return (False, "error")
    except Exception as e:
        print(f"✗ Error ingesting {model_id}: {str(e)}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
        return (False, "error")


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Populate ACME Model Registry with 500 HuggingFace models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/populate_registry.py              # Use remote API (default)
  python scripts/populate_registry.py --local      # Use local server (localhost:8000)
  python scripts/populate_registry.py --url http://localhost:3000  # Use custom URL
  python scripts/populate_registry.py --performance  # Performance mode (stores in performance/ S3 path)
  python scripts/populate_registry.py --local --performance  # Performance mode (bypasses API, --local ignored)
        """
    )
    
    # --local and --url are mutually exclusive
    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument(
        "--local",
        action="store_true",
        help=f"Use local server at {DEFAULT_LOCAL_URL} (ignored in --performance mode)"
    )
    url_group.add_argument(
        "--url",
        type=str,
        metavar="URL",
        help="Custom API base URL (e.g., http://localhost:8000). Ignored in --performance mode."
    )
    
    # --performance is independent (bypasses API, so --local/--url are ignored)
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Performance mode: directly upload to S3 at performance/ path (bypasses API, --local/--url ignored)"
    )
    
    return parser.parse_args()


def get_api_base_url(args: argparse.Namespace) -> str:
    """Determine the API base URL from arguments or environment"""
    # Priority: CLI args > environment variable > default
    if args.url:
        return args.url.rstrip("/")
    elif args.local:
        return DEFAULT_LOCAL_URL
    elif os.getenv("API_BASE_URL"):
        return os.getenv("API_BASE_URL").rstrip("/")
    else:
        return DEFAULT_API_URL


def main():
    """Main function to populate registry with 500 models"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Performance mode: direct S3/DynamoDB writes (bypasses API, ignores --local/--url)
    if args.performance:
        if args.local or args.url:
            print("Note: --performance mode bypasses API, so --local/--url flags are ignored")
        return main_performance_mode()
    
    # Normal mode: use API
    api_base_url = get_api_base_url(args)
    
    print("=" * 80)
    print("ACME Model Registry Population Script")
    print("=" * 80)
    print(f"API Base URL: {api_base_url}")
    if args.local:
        print("Mode: Local")
    elif args.url:
        print(f"Mode: Custom URL")
    elif os.getenv("API_BASE_URL"):
        print("Mode: Environment Variable")
    else:
        print("Mode: Remote API (default)")
    print()
    
    # Get authentication token
    print("Authenticating...")
    auth_token = get_authentication_token(api_base_url)
    if auth_token:
        print("✓ Authentication successful")
    else:
        print("⊘ No authentication token (some endpoints may fail)")
    print()
    
    # Get hardcoded list of 500 models
    print("Loading hardcoded list of 500 HuggingFace models...")
    models = get_hardcoded_models(count=500)
    print(f"✓ Loaded {len(models)} models to ingest")
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
    models.insert(0, REQUIRED_MODEL)
    models = models[:500]  # Ensure exactly 500
    
    print(f"Will ingest {len(models)} models (starting with {REQUIRED_MODEL})")
    print()
    
    # Start ingesting models (check existence first to avoid wasting time)
    print("Starting model ingestion...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    not_found = 0
    not_found_models = []
    
    for i, model_id in enumerate(models, 1):
        print(f"[{i}/{len(models)}] Ingesting: {model_id}")
        
        result, status = ingest_model(api_base_url, model_id, auth_token, skip_missing=True)
        if result:
            successful += 1
        elif status == "not_found":
            not_found += 1
            not_found_models.append(model_id)
        else:
            failed += 1
        
        # Small delay to avoid rate limiting
        if i < len(models):
            time.sleep(0.5)
        
        # Progress update every 50 models
        if i % 50 == 0:
            print()
            print(f"Progress: {i}/{len(models)} ({successful} successful, {failed} failed, {not_found} not found)")
            print()
    
    # Final summary
    print()
    print("=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Total models processed: {len(models)}")
    print(f"  - Successfully ingested: {successful}")
    print(f"  - Not found on HuggingFace: {not_found}")
    print(f"  - Failed (other errors): {failed}")
    print(f"Total successful: {successful}")
    print()
    
    # Report models that don't exist
    if not_found_models:
        print(f"⚠ {len(not_found_models)} models not found on HuggingFace:")
        print("   These models should be removed from the list:")
        for model in not_found_models[:20]:  # Show first 20
            print(f"     - {model}")
        if len(not_found_models) > 20:
            print(f"     ... and {len(not_found_models) - 20} more")
        print()
    
    # Verify Tiny-LLM was in the list
    if REQUIRED_MODEL in models:
        print(f"✓ Required model '{REQUIRED_MODEL}' was included in ingestion list")
    
    if successful >= 500:
        print("✓ Registry should have 500+ models")
        return 0
    else:
        print(f"⚠ Successfully ingested {successful} models (target: 500)")
        return 1 if failed > successful else 0


def main_performance_mode():
    """Main function for performance mode: direct S3/DynamoDB writes"""
    print("=" * 80)
    print("ACME Model Registry Population Script")
    print("PERFORMANCE MODE (stores in performance/ S3 path)")
    print("=" * 80)
    print()
    
    # Initialize AWS clients
    print("Initializing AWS clients...")
    s3, ap_arn = get_s3_client_and_arn()
    if not s3 or not ap_arn:
        print("✗ Failed to initialize S3 client")
        return 1
    
    table = get_dynamodb_table()
    if not table:
        print("✗ Failed to access DynamoDB table")
        return 1
    
    print(f"✓ S3 Access Point: {ap_arn}")
    print(f"✓ DynamoDB Table: {ARTIFACTS_TABLE}")
    print()
    
    # Get model list
    models = get_hardcoded_models(count=500)
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
    models.insert(0, REQUIRED_MODEL)
    models = models[:500]
    
    print(f"Will populate registry with {len(models)} models")
    print(f"  - Tiny-LLM: Full model download (including binary - needed for performance testing)")
    print(f"  - Other {len(models) - 1} models: Essential files only (config, README, etc. - for speed)")
    print(f"  - All files will be uploaded to performance/ S3 path")
    print()
    
    # Start processing
    print("Starting model ingestion (this will take a while - downloading and uploading 500 models)...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    not_found = 0
    not_found_models = []
    tiny_llm_ingested = False
    
    for i, model_id in enumerate(models, 1):
        print(f"[{i}/{len(models)}] Ingesting: {model_id}")
        
        result, status = ingest_model_performance_mode(s3, ap_arn, table, model_id, "main", skip_missing=True)
        if result:
            successful += 1
            if model_id == REQUIRED_MODEL:
                tiny_llm_ingested = True
            print(f"✓ Successfully ingested {model_id} to performance/ S3 path")
        elif status == "not_found":
            not_found += 1
            not_found_models.append(model_id)
        else:
            failed += 1
        
        # Small delay to avoid rate limiting
        if i < len(models):
            time.sleep(0.5)
        
        # Progress update
        if i % 50 == 0:
            print()
            print(f"Progress: {i}/{len(models)} ({successful} successful, {failed} failed, {not_found} not found)")
            print()
    
    # Final summary
    print()
    print("=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Total models processed: {len(models)}")
    print(f"  - Successfully ingested to performance/ S3 path: {successful}")
    print(f"  - Tiny-LLM ingested: {'✓' if tiny_llm_ingested else '✗'}")
    print(f"  - Not found on HuggingFace: {not_found}")
    print(f"  - Failed (other errors): {failed}")
    print(f"Total successful: {successful}")
    print()
    
    if not_found_models:
        print(f"⚠ {len(not_found_models)} models not found on HuggingFace:")
        for model in not_found_models[:10]:
            print(f"     - {model}")
        if len(not_found_models) > 10:
            print(f"     ... and {len(not_found_models) - 10} more")
        print()
    
    if successful >= 500:
        print("✓ Registry populated with 500 models for performance testing")
        print("  Note: Models stored in performance/ S3 path (not models/)")
        return 0
    else:
        print(f"⚠ Only {successful} models processed (target: 500)")
        return 1 if failed > successful else 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

