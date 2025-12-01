"""
Performance workload trigger service
Handles triggering and coordinating performance workload runs
"""

import uuid
import logging
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from threading import Thread

logger = logging.getLogger(__name__)

# In-memory storage for workload run status
_workload_runs: Dict[str, Dict[str, Any]] = {}
_load_generators: Dict[str, Any] = {}  # Store LoadGenerator instances


def _run_load_generator_async(
    run_id: str,
    base_url: str,
    num_clients: int,
    model_id: str,
    version: str,
    duration_seconds: Optional[int],
):
    """
    Run load generator in async event loop (called from thread).

    Args:
        run_id: Unique run identifier
        base_url: Base URL of the API
        num_clients: Number of concurrent clients
        model_id: Model ID to download
        version: Model version
        duration_seconds: Optional duration limit
    """
    try:
        from .load_generator import LoadGenerator

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create and run load generator
        # Use performance path for performance testing
        generator = LoadGenerator(
            run_id=run_id,
            base_url=base_url,
            num_clients=num_clients,
            model_id=model_id,
            version=version,
            duration_seconds=duration_seconds,
            use_performance_path=True,  # Use performance/ path for performance testing
        )

        _load_generators[run_id] = generator

        # Run the load generator
        loop.run_until_complete(generator.run())

        # Update status to completed
        if run_id in _workload_runs:
            _workload_runs[run_id]["status"] = "completed"
            _workload_runs[run_id]["completed_at"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            _workload_runs[run_id]["metrics_count"] = len(generator.metrics)
            _workload_runs[run_id]["summary"] = generator.get_summary()

        logger.info(f"Load generator completed for run_id={run_id}")

    except Exception as e:
        logger.error(
            f"Error in load generator for run_id={run_id}: {str(e)}", exc_info=True
        )
        if run_id in _workload_runs:
            _workload_runs[run_id]["status"] = "failed"
            _workload_runs[run_id]["error"] = str(e)
    finally:
        loop.close()


def trigger_workload(
    num_clients: int = 100,
    model_id: str = "arnir0/Tiny-LLM",
    artifact_id: Optional[str] = None,
    duration_seconds: int = 300,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger a performance workload run.

    Args:
        num_clients: Number of concurrent clients (default: 100)
        model_id: Model ID to download (default: "arnir0/Tiny-LLM")
        artifact_id: Optional artifact ID
        duration_seconds: Duration of workload in seconds (default: 300)
        base_url: Base URL of the API (defaults to environment variable or API Gateway URL)

    Returns:
        Dictionary with run_id, status, and estimated_completion
    """
    # Generate unique run ID
    run_id = str(uuid.uuid4())

    # Get base URL - try environment variable, then default to API Gateway URL
    if not base_url:
        base_url = os.getenv(
            "API_BASE_URL",
            "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod",
        )

    # Calculate estimated completion time
    estimated_completion = datetime.now(timezone.utc) + timedelta(
        seconds=duration_seconds
    )

    # Store run metadata
    _workload_runs[run_id] = {
        "run_id": run_id,
        "status": "started",
        "num_clients": num_clients,
        "model_id": model_id,
        "artifact_id": artifact_id,
        "duration_seconds": duration_seconds,
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "estimated_completion": estimated_completion.isoformat().replace("+00:00", "Z"),
    }

    logger.info(
        f"Performance workload triggered: run_id={run_id}, num_clients={num_clients}, model_id={model_id}"
    )

    # Start load generator in background thread
    thread = Thread(
        target=_run_load_generator_async,
        args=(run_id, base_url, num_clients, model_id, "main", duration_seconds),
        daemon=True,
    )
    thread.start()

    return {
        "run_id": run_id,
        "status": "started",
        "estimated_completion": estimated_completion.isoformat().replace("+00:00", "Z"),
    }


def get_workload_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a workload run"""
    return _workload_runs.get(run_id)


def get_load_generator(run_id: str):
    """Get LoadGenerator instance for a run"""
    return _load_generators.get(run_id)


def get_latest_workload_metrics() -> Optional[Dict[str, Any]]:
    """
    Get metrics from the most recent completed workload run.
    Used for health dashboard display.
    
    Returns:
        Dictionary with latest performance metrics, or None if no runs completed
    """
    # Find the most recent completed run
    completed_runs = [
        (run_id, run_data)
        for run_id, run_data in _workload_runs.items()
        if run_data.get("status") == "completed" and "summary" in run_data
    ]
    
    if not completed_runs:
        return None
    
    # Sort by started_at (most recent first)
    completed_runs.sort(
        key=lambda x: x[1].get("started_at", ""),
        reverse=True
    )
    
    # Get the most recent run's summary
    latest_run_id, latest_run_data = completed_runs[0]
    summary = latest_run_data.get("summary", {})
    
    return {
        "latest_run_id": latest_run_id,
        "latest_throughput_mbps": summary.get("throughput_bps", 0) / (1024 * 1024) if summary.get("throughput_bps") else 0,
        "latest_p99_latency_ms": summary.get("p99_latency_ms", 0),
        "latest_mean_latency_ms": summary.get("mean_latency_ms", 0),
        "latest_median_latency_ms": summary.get("median_latency_ms", 0),
        "latest_success_rate": (
            summary.get("successful_requests", 0) / summary.get("total_requests", 1) * 100
            if summary.get("total_requests", 0) > 0
            else 0
        ),
        "total_runs_completed": len(completed_runs),
        "last_run_started_at": latest_run_data.get("started_at"),
        "last_run_completed_at": latest_run_data.get("completed_at"),
    }
