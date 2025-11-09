from __future__ import annotations
import subprocess
import time
import json
import os
import sys
import zipfile
import io
import tempfile
import glob
import traceback
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..services.s3_service import download_model
from ..acmecli.metrics import METRIC_FUNCTIONS
from ..acmecli.types import MetricValue
from ..acmecli.scoring import compute_net_score

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


def analyze_model_content(
    target: str, suppress_errors: bool = False
) -> Optional[Dict[str, Any]]:
    try:
        from ..services.s3_service import (
            extract_config_from_model,
            download_from_huggingface,
        )
        from fastapi import HTTPException

        model_content = None
        clean_model_id = target

        # Check if this looks like a valid HuggingFace model ID (not a file path)
        is_valid_hf_id = (
            target.startswith("http://") or target.startswith("https://")
        ) or (
            not target.startswith("/")
            and not target.startswith("\\")
            and (":" not in target or target.startswith("http"))
            and (
                "/" in target
                or "-" in target
                or target.replace("-", "").replace("_", "").isalnum()
            )
        )

        if is_valid_hf_id:
            try:
                if target.startswith("https://huggingface.co/"):
                    clean_model_id = target.replace("https://huggingface.co/", "")
                elif target.startswith("http://huggingface.co/"):
                    clean_model_id = target.replace("http://huggingface.co/", "")
                if clean_model_id != target:
                    model_content = download_from_huggingface(clean_model_id, "main")
                elif not target.startswith("http"):
                    # Try to download if it looks like a HuggingFace model ID
                    model_content = download_from_huggingface(clean_model_id, "main")
            except (HTTPException, ValueError) as hf_error:
                if suppress_errors:
                    return None
                raise ValueError(
                    f"No model content found for {target} on HuggingFace. Cannot compute metrics without model data. Error: {str(hf_error)}"
                )
            except Exception as hf_error:
                if suppress_errors:
                    return None
                raise ValueError(
                    f"No model content found for {target} on HuggingFace. Cannot compute metrics without model data. Error: {str(hf_error)}"
                )
        else:
            # Looks like a file path, not a valid model ID
            if suppress_errors:
                return None
            raise ValueError(
                f"Invalid model ID format: {target}. Expected HuggingFace model ID (e.g., 'username/model-name') or HTTP URL, not a file path."
            )
        effective_model_id = clean_model_id if clean_model_id != target else target

        # Check if we have model content before proceeding
        if not model_content:
            if suppress_errors:
                return None
            raise ValueError(
                f"No model content found for {target} on HuggingFace. Cannot compute metrics without model data."
            )

        # Sanitize model ID for file system (remove path separators, invalid chars)
        safe_model_id = (
            effective_model_id.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
            .strip(".")
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, f"{safe_model_id}.zip")
            with open(zip_path, "wb") as f:
                f.write(model_content)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            meta = create_metadata_from_files(temp_dir, effective_model_id)
            config = extract_config_from_model(model_content)
            if config:
                meta["config"] = config
            zip_size_bytes = len(model_content)
            zip_size_kb = zip_size_bytes / 1024
            meta["size"] = int(zip_size_kb)
            meta["contributors"] = {}
            meta["pushed_at"] = None
            meta["github_url"] = ""
            meta["parents"] = []
            meta["full_name"] = effective_model_id
            meta["stars"] = 0
            meta["forks"] = 0
            meta["has_wiki"] = False
            meta["has_pages"] = False
            meta["language"] = "python"
            meta["open_issues_count"] = 0
            meta["github"] = {}
            meta["license"] = ""
            try:
                from ..acmecli.hf_handler import fetch_hf_metadata

                hf_url = f"https://huggingface.co/{effective_model_id}"
                hf_meta = fetch_hf_metadata(hf_url)
                if hf_meta:
                    meta["stars"] = hf_meta.get("likes", 0)
                    meta["downloads"] = hf_meta.get("downloads", 0)
                    if hf_meta.get("modelId"):
                        meta["full_name"] = hf_meta.get("modelId", effective_model_id)
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
                    
                    # Check description for GitHub URL early
                    if description and not repo_url:
                        from ..services.s3_service import extract_github_url_from_text
                        repo_url = extract_github_url_from_text(description)
                        if repo_url:
                            print(f"[RATE] Found GitHub URL in description: {repo_url}")
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
                    repo_url = None
                    import re

                    if isinstance(hf_meta, dict):
                        github_field = hf_meta.get("github", "")
                        if github_field:
                            if isinstance(github_field, str):
                                if github_field.startswith("http"):
                                    repo_url = github_field
                                else:
                                    repo_url = f"https://github.com/{github_field}"
                            elif isinstance(github_field, dict):
                                repo_url = github_field.get("url") or github_field.get(
                                    "repo"
                                )
                        
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
                                        elif "/" in value and len(value.split("/")) == 2:
                                            potential_repo = value.strip()
                                            if not potential_repo.startswith("http"):
                                                repo_url = (
                                                    f"https://github.com/{potential_repo}"
                                                )
                                                break
                        
                        if not repo_url:
                            import json
                            hf_meta_str = json.dumps(hf_meta)
                            from ..services.s3_service import extract_github_url_from_text
                            repo_url = extract_github_url_from_text(hf_meta_str)
                            if repo_url:
                                print(f"[RATE] Found GitHub URL in HuggingFace metadata: {repo_url}")
                        
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
                                from ..services.s3_service import extract_github_url_from_text
                                repo_url = extract_github_url_from_text(model_index)
                                if repo_url:
                                    print(f"[RATE] Found GitHub URL in model_index: {repo_url}")
                        if not repo_url:
                            print(f"[RATE] Searching entire zip file for GitHub URL...")
                            from ..services.s3_service import extract_github_url_from_zip
                            repo_url = extract_github_url_from_zip(model_content)
                            if repo_url:
                                print(f"[RATE] Found GitHub URL in zip file: {repo_url}")
                            else:
                                print(f"[RATE] No GitHub URL found in zip file")
                        
                        if not repo_url and meta.get("readme_text"):
                            readme = meta.get("readme_text", "")
                            print(f"[RATE] Extracting GitHub URL from README text (length: {len(readme)})")
                            from ..services.s3_service import extract_github_url_from_text
                            repo_url = extract_github_url_from_text(readme)
                            if repo_url:
                                print(f"[RATE] Found GitHub URL in README: {repo_url}")
                            else:
                                print(f"[RATE] No GitHub URL found in README text")
                    if repo_url:
                        meta["github_url"] = repo_url
                        meta["github"] = {"prs": [], "direct_commits": []}
                        from ..acmecli.github_handler import fetch_github_metadata

                        try:
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
                                f"[RATE] Warning: Could not fetch GitHub metadata for {repo_url}: {gh_fetch_error}"
                            )
                            print(
                                f"[RATE] Note: github_url is set but GitHub API data unavailable (may be rate limited)"
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
                        if parent_id != effective_model_id:
                            meta["parents"] = [{"score": None, "id": parent_id}]
            except Exception as gh_error:
                print(f"[RATE] Warning: Could not fetch GitHub metadata: {gh_error}")
            license_text_content = meta.get("license_text", "")
            if license_text_content and not meta.get("license"):
                license_text_lower = license_text_content[:100].lower()
                if license_text_lower:
                    meta["license"] = license_text_lower
            if not meta.get("readme_text"):
                print(f"[RATE] Warning: No README text found for {target}")
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
            print(
                f"Running ACME metrics for {target} with {len(meta['repo_files'])} files"
            )
            return run_acme_metrics(meta, quick_metrics)
    except Exception as e:
        if suppress_errors:
            return None
        print(f"Error analyzing model {target}: {e}")
        traceback.print_exc()
        raise RuntimeError(f"Failed to analyze model {target}: {str(e)}")


def create_metadata_from_files(temp_dir: str, model_name: str) -> Dict[str, Any]:
    meta = {
        "repo_files": set(),
        "readme_text": "",
        "license_text": "",
        "repo_path": temp_dir,
        "repo_name": model_name,
        "url": f"local://{model_name}",
    }
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), temp_dir)
            meta["repo_files"].add(file_path.replace("\\", "/"))
    readme_files = glob.glob(os.path.join(temp_dir, "**", "*readme*"), recursive=True)
    if not readme_files:
        readme_files.extend(
            glob.glob(os.path.join(temp_dir, "**", "README*"), recursive=True)
        )
        readme_files.extend(
            glob.glob(os.path.join(temp_dir, "**", "readme*"), recursive=True)
        )
        readme_files.extend(
            glob.glob(os.path.join(temp_dir, "README*"), recursive=False)
        )
    for readme_file in readme_files:
        try:
            with open(readme_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if content:
                    meta["readme_text"] += content + "\n"
        except Exception as e:
            print(f"Warning: Could not read README file {readme_file}: {e}")
            pass
    license_files = glob.glob(os.path.join(temp_dir, "**", "*license*"), recursive=True)
    license_files.extend(
        glob.glob(os.path.join(temp_dir, "**", "*licence*"), recursive=True)
    )
    for license_file in license_files:
        try:
            with open(license_file, "r", encoding="utf-8", errors="ignore") as f:
                meta["license_text"] += f.read() + "\n"
        except:
            pass
    return meta


def run_acme_metrics(
    meta: Dict[str, Any], metric_functions: Dict[str, Any]
) -> Dict[str, Any]:
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
                    results[metric_name] = MetricValue(
                        metric_name, float(metric_value), 0
                    )
                elif isinstance(metric_value, dict) and metric_name == "size_score":
                    avg_score = (
                        sum(metric_value.values()) / len(metric_value)
                        if metric_value
                        else 0.0
                    )
                    results[metric_name] = MetricValue(metric_name, avg_score, 0)
                else:
                    print(
                        f"Unexpected metric result type for {metric_name}: {type(metric_value)}"
                    )
                    results[metric_name] = MetricValue(metric_name, 0.0, 0)
        except Exception as e:
            print(f"Error running metric {metric_name}: {e}")
            results[metric_name] = MetricValue(metric_name, 0.0, 0)
    net_score, net_score_latency = compute_net_score(results)
    scores = {"net_score": round(float(net_score), 2), "aggregation_latency": round(net_score_latency / 1000.0, 2)}
    metric_mapping = {
        "ramp_up_time": "ramp_up",
        "license": "license",
        "bus_factor": "bus_factor",
        "performance_claims": "performance_claims",
        "size_score": "size",
        "Treescore": "treescore",
        "Reviewedness": "reviewedness",
        "dataset_and_code_score": "dataset_code",
        "dataset_quality": "dataset_quality",
        "code_quality": "code_quality",
        "Reproducibility": "reproducibility",
        "dependencies": "pull_requests",
        "pull_requests": "pull_requests",
    }
    for metric_name, output_name in metric_mapping.items():
        if metric_name in results:
            metric_value = results[metric_name]
            if hasattr(metric_value, "value"):
                val = metric_value.value
                if isinstance(val, dict) and len(val) > 0:
                    scores[output_name] = round(float(sum(val.values()) / len(val)), 2)
                else:
                    scores[output_name] = round(float(val) if val is not None else 0.0, 2)
                if hasattr(metric_value, "latency_ms"):
                    scores[f"{output_name}_latency"] = int(metric_value.latency_ms)
            elif isinstance(metric_value, dict) and len(metric_value) > 0:
                scores[output_name] = round(float(
                    sum(metric_value.values()) / len(metric_value)
                ), 2)
            elif isinstance(metric_value, (int, float)):
                scores[output_name] = round(float(metric_value), 2)
            else:
                scores[output_name] = round(0.0, 2)
        else:
            scores[output_name] = round(0.0, 2)
    
    if "size_score" in results:
        size_result = results["size_score"]
        if hasattr(size_result, "value") and isinstance(size_result.value, dict):
            scores["size_score"] = {platform: round(float(score), 2) for platform, score in size_result.value.items()}
        if hasattr(size_result, "latency_ms"):
            scores["size_score_latency"] = int(size_result.latency_ms)
    
    if "net_score_latency" not in scores:
        scores["net_score_latency"] = int(net_score_latency)
    
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
                env=env,
            )
        else:
            proc = subprocess.run(
                ["./run", str(urls_file)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
            raise HTTPException(status_code=502, detail=f"Scoring failed: {error_msg}")
        line = next(
            (s for s in (x.strip() for x in proc.stdout.splitlines()) if s), None
        )
        if not line:
            raise HTTPException(
                status_code=502, detail="No scoring output received from Python tool"
            )
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
        raise HTTPException(
            status_code=400, detail="target is required (GitHub/HF URL string)"
        )
    row = run_scorer(body.target)
    subscores = {
        "license": alias(row, "license", "License", "score_license"),
        "ramp_up": alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp"),
        "bus_factor": alias(
            row, "bus_factor", "BusFactor", "score_bus_factor", "busFactor"
        ),
        "performance_claims": alias(
            row,
            "performance_claims",
            "PerformanceClaims",
            "score_performance_claims",
            "performanceClaims",
        ),
        "size": alias(row, "size", "Size", "score_size"),
        "dataset_code": alias(
            row,
            "dataset_code",
            "DatasetCode",
            "score_available_dataset_and_code",
            "available_dataset_and_code",
        ),
        "dataset_quality": alias(
            row, "dataset_quality", "DatasetQuality", "score_dataset_quality"
        ),
        "code_quality": alias(row, "code_quality", "CodeQuality", "score_code_quality"),
        "reproducibility": alias(
            row, "reproducibility", "Reproducibility", "score_reproducibility"
        ),
        "reviewedness": alias(
            row, "reviewedness", "Reviewedness", "score_reviewedness"
        ),
        "treescore": alias(row, "treescore", "Treescore", "score_treescore"),
        "dependencies": alias(
            row, "dependencies", "Dependencies", "score_dependencies"
        ),
        "pull_requests": alias(
            row, "pull_requests", "PullRequests", "score_pull_requests"
        ),
    }
    netScore = alias(row, "net_score", "NetScore", "netScore")
    latency = alias(
        row, "aggregation_latency", "AggregationLatency", "latency", "total_latency"
    )
    if enforce:
        failures = [
            (k, v) for k, v in subscores.items() if v is not None and float(v) <= 0.5
        ]
        if failures:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "INGESTIBILITY_FAILURE",
                    "message": "Failed ingestibility: "
                    + ", ".join(f"{k}={v}" for k, v in failures),
                    "data": {
                        "modelId": modelId,
                        "target": body.target,
                        "netScore": netScore,
                        "subscores": subscores,
                        "latency": latency,
                    },
                },
            )
    return {
        "data": {
            "modelId": modelId,
            "target": body.target,
            "netScore": netScore,
            "subscores": subscores,
            "latency": latency,
        }
    }
