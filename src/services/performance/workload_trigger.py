"""
Performance workload trigger service
Handles triggering and coordinating performance workload runs
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from threading import Thread

logger = logging.getLogger(__name__)

# In-memory storage for workload run status
_workload_runs: Dict[str, Dict[str, Any]] = {}


def trigger_workload(
    num_clients: int = 100,
    model_id: str = "arnir0/Tiny-LLM",
    artifact_id: Optional[str] = None,
    duration_seconds: int = 300
) -> Dict[str, Any]:
    """
    Trigger a performance workload run.
    
    Args:
        num_clients: Number of concurrent clients (default: 100)
        model_id: Model ID to download (default: "arnir0/Tiny-LLM")
        artifact_id: Optional artifact ID
        duration_seconds: Duration of workload in seconds (default: 300)
    
    Returns:
        Dictionary with run_id, status, and estimated_completion
    """
    # Generate unique run ID
    run_id = str(uuid.uuid4())
    
    # Calculate estimated completion time
    estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    
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
    
    logger.info(f"Performance workload triggered: run_id={run_id}, num_clients={num_clients}, model_id={model_id}")
    
    # TODO: Phase 1.3 - Start actual load generator in background thread
    # For now, just mark as started
    
    return {
        "run_id": run_id,
        "status": "started",
        "estimated_completion": estimated_completion.isoformat().replace("+00:00", "Z"),
    }


def get_workload_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a workload run"""
    return _workload_runs.get(run_id)

