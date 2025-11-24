"""
Results retrieval service for performance track
Queries DynamoDB and calculates aggregated statistics from raw metrics
"""
import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS clients
region = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=region)

# Configuration
PERFORMANCE_METRICS_TABLE = os.getenv("DDB_TABLE_PERFORMANCE_METRICS", "performance_metrics")


def calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """
    Calculate percentile from sorted list of values.
    
    Args:
        sorted_values: Sorted list of numeric values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        Percentile value
    """
    if not sorted_values:
        return 0.0
    
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    floor = int(k)
    ceil = floor + 1
    
    if ceil >= len(sorted_values):
        return sorted_values[-1]
    
    weight = k - floor
    return sorted_values[floor] * (1 - weight) + sorted_values[ceil] * weight


def query_metrics_by_run_id(run_id: str) -> List[Dict[str, Any]]:
    """
    Query all metrics for a specific run_id from DynamoDB.
    
    Args:
        run_id: Unique run identifier
        
    Returns:
        List of metric dictionaries
    """
    try:
        table = dynamodb.Table(PERFORMANCE_METRICS_TABLE)
        all_items = []
        
        # Query by partition key (run_id)
        response = table.query(
            KeyConditionExpression="run_id = :run_id",
            ExpressionAttributeValues={":run_id": run_id}
        )
        
        all_items.extend(response.get("Items", []))
        
        # Handle pagination if needed
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression="run_id = :run_id",
                ExpressionAttributeValues={":run_id": run_id},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            all_items.extend(response.get("Items", []))
        
        # Convert DynamoDB numeric types to Python types
        metrics = []
        for item in all_items:
            metric = {
                "run_id": item.get("run_id"),
                "metric_id": item.get("metric_id"),
                "timestamp": item.get("timestamp"),
                "client_id": int(item.get("client_id", 0)) if isinstance(item.get("client_id"), (int, str)) else 0,
                "request_latency_ms": float(item.get("request_latency_ms", 0)) if isinstance(item.get("request_latency_ms"), (int, float, str)) else 0.0,
                "bytes_transferred": int(item.get("bytes_transferred", 0)) if isinstance(item.get("bytes_transferred"), (int, str)) else 0,
                "status_code": int(item.get("status_code", 0)) if isinstance(item.get("status_code"), (int, str)) else 0,
            }
            metrics.append(metric)
        
        logger.info(f"Retrieved {len(metrics)} metrics for run_id={run_id}")
        return metrics
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Performance metrics table doesn't exist: {PERFORMANCE_METRICS_TABLE}")
        else:
            logger.error(f"Error querying metrics from DynamoDB: {error_code} - {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error querying metrics: {type(e).__name__}: {str(e)}")
        return []


def calculate_statistics(metrics: List[Dict[str, Any]], started_at: Optional[str] = None, completed_at: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate aggregated statistics from raw metrics.
    
    Args:
        metrics: List of metric dictionaries
        started_at: ISO8601 timestamp when workload started (optional)
        completed_at: ISO8601 timestamp when workload completed (optional)
        
    Returns:
        Dictionary with calculated statistics
    """
    if not metrics:
        return {
            "throughput": {
                "requests_per_second": 0.0,
                "bytes_per_second": 0.0
            },
            "latency": {
                "mean_ms": 0.0,
                "median_ms": 0.0,
                "p99_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0
            },
            "error_rate": 0.0,
            "total_requests": 0,
            "total_bytes": 0
        }
    
    # Extract data from metrics
    total_requests = len(metrics)
    successful_metrics = [m for m in metrics if m.get("status_code") == 200]
    failed_requests = total_requests - len(successful_metrics)
    
    # Calculate error rate
    error_rate = (failed_requests / total_requests * 100.0) if total_requests > 0 else 0.0
    
    # Calculate total bytes transferred
    total_bytes = sum(m.get("bytes_transferred", 0) for m in successful_metrics)
    
    # Calculate latencies
    latencies = [float(m.get("request_latency_ms", 0)) for m in metrics]
    sorted_latencies = sorted(latencies)
    
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    median_latency = calculate_percentile(sorted_latencies, 50.0)
    p99_latency = calculate_percentile(sorted_latencies, 99.0)
    min_latency = min(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0
    
    # Calculate throughput
    # Use timestamps if available, otherwise estimate from latency
    if started_at and completed_at:
        try:
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            total_duration_seconds = (end_dt - start_dt).total_seconds()
        except (ValueError, AttributeError):
            # Fallback: use max latency as proxy for duration
            total_duration_seconds = max_latency / 1000.0 if max_latency > 0 else 1.0
    else:
        # Use max latency as proxy for duration
        total_duration_seconds = max_latency / 1000.0 if max_latency > 0 else 1.0
    
    requests_per_second = total_requests / total_duration_seconds if total_duration_seconds > 0 else 0.0
    bytes_per_second = total_bytes / total_duration_seconds if total_duration_seconds > 0 else 0.0
    
    return {
        "throughput": {
            "requests_per_second": round(requests_per_second, 2),
            "bytes_per_second": round(bytes_per_second, 2)
        },
        "latency": {
            "mean_ms": round(mean_latency, 2),
            "median_ms": round(median_latency, 2),
            "p99_ms": round(p99_latency, 2),
            "min_ms": round(min_latency, 2),
            "max_ms": round(max_latency, 2)
        },
        "error_rate": round(error_rate, 2),
        "total_requests": total_requests,
        "total_bytes": total_bytes
    }


def get_performance_results(run_id: str, workload_status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get aggregated performance results for a run_id.
    
    Args:
        run_id: Unique run identifier
        workload_status: Optional workload status dictionary from workload_trigger
        
    Returns:
        Dictionary with run_id, status, timestamps, and calculated metrics
    """
    # Query metrics from DynamoDB
    metrics = query_metrics_by_run_id(run_id)
    
    # Get workload status info if not provided
    if not workload_status:
        from .workload_trigger import get_workload_status
        workload_status = get_workload_status(run_id)
    
    # Determine status
    if not workload_status:
        status = "not_found"
        started_at = None
        completed_at = None
    else:
        status = workload_status.get("status", "unknown")
        started_at = workload_status.get("started_at")
        completed_at = workload_status.get("completed_at")
    
    # Calculate statistics
    statistics = calculate_statistics(metrics, started_at, completed_at)
    
    # Build response
    result = {
        "run_id": run_id,
        "status": status,
        "metrics": statistics
    }
    
    if started_at:
        result["started_at"] = started_at
    if completed_at:
        result["completed_at"] = completed_at
    
    return result

