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
        generator = LoadGenerator(
            run_id=run_id,
            base_url=base_url,
            num_clients=num_clients,
            model_id=model_id,
            version=version,
            duration_seconds=duration_seconds,
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
