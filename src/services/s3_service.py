import boto3
import zipfile
import io
import re
import json
import os
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
            return {"valid": has_config and has_weights, "has_config": has_config, "has_weights": has_weights, "files": file_list}
    except zipfile.BadZipFile:
        return {"valid": False, "error": "Invalid ZIP file"}

def get_model_sizes(model_id: str, version: str) -> Dict[str, Any]:
    if not aws_available:
        return {"full": 0, "weights": 0, "datasets": 0, "error": "AWS services not available"}
    try:
        from botocore.exceptions import ClientError
        s3_key = f"models/{model_id}/{version}/model.zip"
        response = s3.head_object(Bucket=ap_arn, Key=s3_key)
        full_size = response['ContentLength']
        s3_response = s3.get_object(Bucket=ap_arn, Key=s3_key)
        zip_content = s3_response['Body'].read()
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
            weight_files = [f for f in zip_file.namelist() if f.endswith(('.bin', '.safetensors'))]
            dataset_files = [f for f in zip_file.namelist() if any(ext in f for ext in ['.csv', '.json', '.txt', '.parquet'])]
            weights_size = sum(zip_file.getinfo(f).compress_size for f in weight_files)
            datasets_size = sum(zip_file.getinfo(f).compress_size for f in dataset_files)
            weights_uncompressed = sum(zip_file.getinfo(f).file_size for f in weight_files)
            datasets_uncompressed = sum(zip_file.getinfo(f).file_size for f in dataset_files)
        return {"full": full_size, "weights": weights_size, "datasets": datasets_size, "weights_uncompressed": weights_uncompressed, "datasets_uncompressed": datasets_uncompressed, "model_id": model_id, "version": version}
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == '404':
            return {"full": 0, "weights": 0, "datasets": 0, "error": f"Model '{model_id}' not found in registry. Upload it first using the Upload or Ingest page."}
        return {"full": 0, "weights": 0, "datasets": 0, "error": str(e)}
    except Exception as e:
        print(f"Error getting model sizes: {e}")
        return {"full": 0, "weights": 0, "datasets": 0, "error": str(e)}
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
            raise HTTPException(status_code=400, detail=f"Invalid HuggingFace model structure. Missing: config.json={not validation['has_config']}, weights={not validation['has_weights']}")
        s3_key = f"models/{model_id}/{version}/model.zip"
        s3.put_object(Bucket=ap_arn, Key=s3_key, Body=file_content, ContentType='application/zip')
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
                        results.append({"name": model_name, "version": model_version})
        return {"models": results, "next_token": response.get('NextContinuationToken')}
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

def extract_config_from_model(model_zip_content: bytes) -> Optional[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(model_zip_content), 'r') as zip_file:
            config_files = [f for f in zip_file.namelist() if f.endswith('config.json') or f == 'config.json']
            if not config_files:
                return None
            config_content = zip_file.read(config_files[0])
            return json.loads(config_content.decode('utf-8'))
    except Exception as e:
        print(f"Error extracting config.json: {e}")
        return None
def parse_lineage_from_config(config: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    lineage_metadata = {"model_id": model_id, "base_model": None, "architecture": None, "transformers_version": None, "model_type": None, "architectures": [], "vocab_size": None, "hidden_size": None}
    base_model_fields = ["base_model_name_or_path", "_name_or_path", "parent_model", "pretrained_model_name_or_path"]
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
        return {"model_id": model_id, "lineage_metadata": lineage_metadata, "lineage_map": lineage_map, "config": config}
    except Exception as e:
        print(f"Error getting lineage from config: {e}")
        return {"model_id": model_id, "error": str(e)}

def sign_request(request):
    credentials = get_credentials(Session())
    auth = SigV4Auth(credentials, 'neptune-db', os.environ.get('AWS_REGION', 'us-east-1'))
    auth.add_auth(request)
    return dict(request.headers)

def send_request(url, headers, data):
    req = urllib.request.Request(url, data=data.encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(e.read().decode('utf-8'))
        raise

def write_to_neptune(lineage_data):
    neptune_endpoint = os.environ.get('NEPTUNE_ENDPOINT', '')
    if not neptune_endpoint:
        print("NEPTUNE_ENDPOINT not configured, skipping Neptune write")
        return
    endpoint = neptune_endpoint
    clear_query = "g.V().drop()"
    request = AWSRequest(method='POST', url=endpoint, data=json.dumps({'gremlin': clear_query}))
    signed_headers = sign_request(request)
    response = send_request(endpoint, signed_headers, json.dumps({'gremlin': clear_query}))
    print(f"Clear database response: {response}")
    verify_query = "g.V().count()"
    request = AWSRequest(method='POST', url=endpoint, data=json.dumps({'gremlin': verify_query}))
    signed_headers = sign_request(request)
    response = send_request(endpoint, signed_headers, json.dumps({'gremlin': verify_query}))
    print(f"Vertex count after clearing: {response}")
    
    def process_node(node, children):
        query = f"g.V().has('lineage_node', 'node_name', '{node}').fold().coalesce(unfold(), addV('lineage_node').property('node_name', '{node}'))"
        request = AWSRequest(method='POST', url=endpoint, data=json.dumps({'gremlin': query}))
        signed_headers = sign_request(request)
        response = send_request(endpoint, signed_headers, json.dumps({'gremlin': query}))
        print(f"Add node response for {node}: {response}")
        for child_node in children:
            query = f"g.V().has('lineage_node', 'node_name', '{child_node}').fold().coalesce(unfold(), addV('lineage_node').property('node_name', '{child_node}'))"
            request = AWSRequest(method='POST', url=endpoint, data=json.dumps({'gremlin': query}))
            signed_headers = sign_request(request)
            response = send_request(endpoint, signed_headers, json.dumps({'gremlin': query}))
            print(f"Add child node response for {child_node}: {response}")
            query = f"g.V().has('lineage_node', 'node_name', '{node}').as('a').V().has('lineage_node', 'node_name', '{child_node}').coalesce(inE('lineage_edge').where(outV().as('a')), addE('lineage_edge').from('a').property('edge_name', ' '))"
            request = AWSRequest(method='POST', url=endpoint, data=json.dumps({'gremlin': query}))
            signed_headers = sign_request(request)
            response = send_request(endpoint, signed_headers, json.dumps({'gremlin': query}))
            print(f"Add edge response for {node} -> {child_node}: {response}")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_node, node, children) for node, children in lineage_data.items()]
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
                    print(f"Extracted lineage for {model_id}: {lineage_info.get('lineage_metadata', {}).get('base_model')}")
            except Exception as e:
                print(f"Error processing model {model_id}: {e}")
                continue
        print(f"Built lineage map with {len(lineage_map)} relationships")
        write_to_neptune(lineage_map)
        return {"message": "Model lineage successfully synced to Neptune", "source": "config.json analysis", "relationships": len(lineage_map)}
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
    clean_model_id = model_id
    if model_id.startswith("https://huggingface.co/"):
        clean_model_id = model_id.replace("https://huggingface.co/", "")
    elif model_id.startswith("http://huggingface.co/"):
        clean_model_id = model_id.replace("http://huggingface.co/", "")
    api_url = f"https://huggingface.co/api/models/{clean_model_id}"
    response = requests.get(api_url, timeout=30)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Model {clean_model_id} not found on HuggingFace")
    model_info = response.json()
    
    all_files = []
    for sibling in model_info.get("siblings", []):
        if sibling.get("rfilename"):
            all_files.append(sibling["rfilename"])
    
    essential_files = []
    for filename in all_files:
        if filename.endswith(('.json', '.md', '.txt', '.yml', '.yaml')):
            essential_files.append(filename)
        elif filename.startswith('README') or filename.startswith('readme'):
            essential_files.append(filename)
        elif filename == 'config.json' or filename == 'LICENSE' or filename == 'license' or filename == 'LICENCE' or filename == 'licence':
            essential_files.append(filename)
    
    urls_to_download = [(f"https://huggingface.co/{clean_model_id}/resolve/{version}/{filename}", filename) for filename in essential_files]
    
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(download_file, url[0], 120): url[1] for url in urls_to_download}
            for future in as_completed(futures):
                filename = futures[future]
                result = future.result()
                if result:
                    zip_file.writestr(filename, result)
    return output.getvalue()

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
        if not validation.get('has_config'):
            raise HTTPException(status_code=400, detail=f"Invalid model structure. Missing: config.json={not validation.get('has_config')}")
        
        safe_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").replace("/", "_").replace(":", "_").replace("\\", "_").replace("?", "_").replace("*", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")
        temp_dir = tempfile.mkdtemp(prefix=f"ingest_{safe_model_id}_{os.getpid()}_")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            meta = create_metadata_from_files(temp_dir, model_id)
            config = extract_config_from_model(zip_content)
            if config:
                meta["config"] = config
            
            meta["contributors"] = {}
            meta["pushed_at"] = None
            meta["github_url"] = ""
            meta["parents"] = []
            meta["license"] = meta.get("license_text", "")[:100].lower() if meta.get("license_text") else ""
            
            print(f"[INGEST] Computing metrics...")
            metrics_start = time.time()
            
            from ..acmecli.metrics.license_metric import LicenseMetric
            from ..acmecli.metrics.ramp_up_metric import RampUpMetric
            from ..acmecli.metrics.bus_factor_metric import BusFactorMetric
            from ..acmecli.metrics.performance_claims_metric import PerformanceClaimsMetric
            from ..acmecli.metrics.size_metric import SizeMetric
            from ..acmecli.metrics.dataset_and_code_metric import DatasetAndCodeMetric
            from ..acmecli.metrics.dataset_quality_metric import DatasetQualityMetric
            from ..acmecli.metrics.code_quality_metric import CodeQualityMetric
            from ..acmecli.metrics.reproducibility_metric import ReproducibilityMetric
            from ..acmecli.metrics.reviewedness_metric import ReviewednessMetric
            from ..acmecli.metrics.treescore_metric import TreescoreMetric
            
            quick_metrics = {'license': LicenseMetric().score, 'ramp_up_time': RampUpMetric().score, 'bus_factor': BusFactorMetric().score, 'performance_claims': PerformanceClaimsMetric().score, 'size_score': SizeMetric().score, 'dataset_and_code_score': DatasetAndCodeMetric().score, 'dataset_quality': DatasetQualityMetric().score, 'code_quality': CodeQualityMetric().score, 'Reproducibility': ReproducibilityMetric().score, 'Reviewedness': ReviewednessMetric().score, 'Treescore': TreescoreMetric().score}
            metric_results = run_acme_metrics(meta, quick_metrics)
            metrics_time = time.time() - metrics_start
            print(f"[INGEST] Computed metrics in {metrics_time:.2f}s")
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
        REQUIRED_NON_LATENCY_METRICS = ['license', 'ramp_up', 'bus_factor', 'performance_claims', 'size', 'dataset_code', 'dataset_quality', 'code_quality', 'reproducibility', 'reviewedness', 'treescore']
        failures = []
        metric_scores_dict = {}
        for metric_name in REQUIRED_NON_LATENCY_METRICS:
            result = metric_results.get(metric_name)
            score = 0.0
            if result is None:
                failures.append(f"{metric_name}=MISSING")
                metric_scores_dict[metric_name] = 0.0
                continue
            elif hasattr(result, 'value'):
                score = float(result.value) if result.value is not None else 0.0
            elif isinstance(result, (int, float)):
                score = float(result)
            else:
                score = 0.0
            metric_scores_dict[metric_name] = score
            if score < 0.5:
                failures.append(f"{metric_name}={score:.2f}")
        if failures:
            print(f"[INGEST] Failed: {', '.join(failures)}")
            msg = f"Model failed ingestibility requirements. Failed metrics: {', '.join(failures)}"
            raise HTTPException(status_code=422, detail={"error": "INGESTIBILITY_FAILURE", "message": msg, "metric_scores": metric_scores_dict, "required_threshold": 0.5})
        
        upload_model(zip_content, model_id, version)
        total_time = time.time() - start_time
        print(f"[INGEST] Success in {total_time:.2f}s")
        return {"message": "Model ingestion successful", "model_id": model_id, "version": version, "metric_scores": metric_scores_dict, "ingestible": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest model: {str(e)}")
