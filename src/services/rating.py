from __future__ import annotations
import subprocess
import time
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]

def python_cmd() -> str:
    return "python" if sys.platform == "win32" else "python3"

def alias(obj: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None

class RateRequest(BaseModel):
    target: str

def analyze_model_content(target: str) -> Dict[str, Any]:
    import zipfile
    import io
    import tempfile
    import os
    from ..services.s3_service import download_model
    from ..acmecli.metrics import METRIC_FUNCTIONS
    from ..acmecli.types import MetricValue
    try:
        model_content = download_model(target, "1.0.0", "full")
        if not model_content:
            for version in ["1.0", "latest", "main"]:
                model_content = download_model(target, version, "full")
                if model_content:
                    break
        if not model_content:
            raise ValueError(f"No model content found for {target}. Cannot compute metrics without model data.")
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, f"{target}.zip")
            with open(zip_path, 'wb') as f:
                f.write(model_content)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            meta = create_metadata_from_files(temp_dir, target)
            print(f"Running ACME metrics for {target} with {len(meta['repo_files'])} files")
            return run_acme_metrics(meta, METRIC_FUNCTIONS)
    except Exception as e:
        print(f"Error analyzing model {target}: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Failed to analyze model {target}: {str(e)}")

def create_metadata_from_files(temp_dir: str, model_name: str) -> Dict[str, Any]:
    import os
    import glob
    meta = {
        "repo_files": set(),
        "readme_text": "",
        "license_text": "",
        "repo_path": temp_dir,
        "repo_name": model_name,
        "url": f"local://{model_name}"
    }
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), temp_dir)
            meta["repo_files"].add(file_path.replace("\\", "/"))
    readme_files = glob.glob(os.path.join(temp_dir, "**", "*readme*"), recursive=True)
    for readme_file in readme_files:
        try:
            with open(readme_file, 'r', encoding='utf-8', errors='ignore') as f:
                meta["readme_text"] += f.read() + "\n"
        except:
            pass
    license_files = glob.glob(os.path.join(temp_dir, "**", "*license*"), recursive=True)
    license_files.extend(glob.glob(os.path.join(temp_dir, "**", "*licence*"), recursive=True))
    for license_file in license_files:
        try:
            with open(license_file, 'r', encoding='utf-8', errors='ignore') as f:
                meta["license_text"] += f.read() + "\n"
        except:
            pass
    return meta

def run_acme_metrics(meta: Dict[str, Any], metric_functions: Dict[str, Any]) -> Dict[str, Any]:
    from ..acmecli.scoring import compute_net_score
    from ..acmecli.types import MetricValue
    results = {}
    for metric_name, metric_func in metric_functions.items():
        try:
            if metric_name in ["dependencies", "pull_requests"]:
                score, latency = metric_func(meta)
                results[metric_name] = MetricValue(metric_name, score, int(latency))
            else:
                metric_value = metric_func(meta)
                if isinstance(metric_value, MetricValue):
                    results[metric_name] = metric_value
                elif isinstance(metric_value, (int, float)):
                    results[metric_name] = MetricValue(metric_name, float(metric_value), 0)
                else:
                    print(f"Unexpected metric result type for {metric_name}: {type(metric_value)}")
                    results[metric_name] = MetricValue(metric_name, 0.0, 0)
        except Exception as e:
            print(f"Error running metric {metric_name}: {e}")
            results[metric_name] = MetricValue(metric_name, 0.0, 0)
    net_score, net_score_latency = compute_net_score(results)
    scores = {
        "net_score": net_score,
        "aggregation_latency": net_score_latency / 1000.0
    }
    metric_mapping = {
        "ramp_up": "ramp_up",
        "license": "license",
        "bus_factor": "bus_factor",
        "code_quality": "code_quality",
        "reproducibility": "reproducibility",
        "reviewedness": "reviewedness",
        "treescore": "treescore",
        "dependencies": "pull_requests",
        "pull_requests": "pull_requests"
    }
    for metric_name, output_name in metric_mapping.items():
        if metric_name in results:
            metric_value = results[metric_name]
            if hasattr(metric_value, 'value'):
                scores[output_name] = metric_value.value
            elif isinstance(metric_value, (int, float)):
                scores[output_name] = float(metric_value)
            else:
                scores[output_name] = 0.0
    return scores


def run_scorer(target: str) -> Dict[str, Any]:
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token or github_token == "ghp_test_token_placeholder":
        return analyze_model_content(target)
    urls_file = ROOT / f".tmp_urls_{os.getpid()}_{int(time.time()*1000)}.txt"
    urls_file.write_text(target + "\n", encoding="utf-8")
    try:
        env = os.environ.copy()
        if sys.platform == "win32":
            proc = subprocess.run(
                ["bash", "run", str(urls_file)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
        else:
            proc = subprocess.run(
                ["./run", str(urls_file)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
            raise HTTPException(status_code=502, detail=f"Scoring failed: {error_msg}")
        line = next((s for s in (x.strip() for x in proc.stdout.splitlines()) if s), None)
        if not line:
            raise HTTPException(status_code=502, detail="No scoring output received from Python tool")
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="Invalid JSON from scorer")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="Scoring tool timed out")
    finally:
        try:
            urls_file.unlink(missing_ok=True)
        except Exception:
            pass

@router.post("/registry/models/{modelId}/rate")
def rate_model(modelId: str, body: RateRequest, enforce: bool = Query(False)):
    if not body.target or not isinstance(body.target, str):
        raise HTTPException(status_code=400, detail="target is required (GitHub/HF URL string)")
    row = run_scorer(body.target)
    subscores = {
        "license": alias(row, "license", "License", "score_license"),
        "ramp_up": alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp"),
        "bus_factor": alias(row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"),
        "performance_claims": alias(row, "performance_claims", "PerformanceClaims", "score_performance_claims", "performanceClaims"),
        "size": alias(row, "size", "Size", "score_size"),
        "dataset_code": alias(row, "dataset_code", "DatasetCode", "score_available_dataset_and_code", "available_dataset_and_code"),
        "dataset_quality": alias(row, "dataset_quality", "DatasetQuality", "score_dataset_quality"),
        "code_quality": alias(row, "code_quality", "CodeQuality", "score_code_quality"),
        "reproducibility": alias(row, "reproducibility", "Reproducibility", "score_reproducibility"),
        "reviewedness": alias(row, "reviewedness", "Reviewedness", "score_reviewedness"),
        "treescore": alias(row, "treescore", "Treescore", "score_treescore"),
        "dependencies": alias(row, "dependencies", "Dependencies", "score_dependencies"),
        "pull_requests": alias(row, "pull_requests", "PullRequests", "score_pull_requests"),
    }
    netScore = alias(row, "net_score", "NetScore", "netScore")
    latency = alias(row, "aggregation_latency", "AggregationLatency", "latency", "total_latency")
    if enforce:
        failures = [(k, v) for k, v in subscores.items() if v is not None and float(v) <= 0.5]
        if failures:
            raise HTTPException(status_code=422, detail={
                "error": "INGESTIBILITY_FAILURE",
                "message": "Failed ingestibility: " + ", ".join(f"{k}={v}" for k, v in failures),
                "data": {"modelId": modelId, "target": body.target, "netScore": netScore, "subscores": subscores, "latency": latency},
            })
    return {"data": {"modelId": modelId, "target": body.target, "netScore": netScore, "subscores": subscores, "latency": latency}}