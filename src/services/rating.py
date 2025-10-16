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


def run_scorer(target: str) -> Dict[str, Any]:
    urls_file = ROOT / f".tmp_urls_{os.getpid()}_{int(time.time()*1000)}.txt"
    urls_file.write_text(target + "\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            [python_cmd(), "run.py", "score", str(urls_file)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if proc.returncode != 0:
            raise HTTPException(status_code=502, detail=f"Scoring failed: {proc.stderr[:500]}")

        # take first non-empty line
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
            urls_file.unlink(missing_ok=True)  # type: ignore[arg-type]
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


