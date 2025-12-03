"""
Metrics storage service for performance track
Stores metrics in DynamoDB and publishes to CloudWatch
"""

import boto3
import os
import uuid
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS clients
region = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=region)
cloudwatch = boto3.client("cloudwatch", region_name=region)

# Configuration
PERFORMANCE_METRICS_TABLE = os.getenv(
    "DDB_TABLE_PERFORMANCE_METRICS", "performance_metrics"
)
CLOUDWATCH_NAMESPACE = "ACME/Performance"


def store_metrics_in_dynamodb(metrics: List[Dict[str, Any]]) -> int:
    """
    Store raw metrics in DynamoDB table.

    Args:
        metrics: List of metric dictionaries

    Returns:
        Number of metrics successfully stored
    """
    if not metrics:
        return 0

    try:
        table = dynamodb.Table(PERFORMANCE_METRICS_TABLE)
        stored_count = 0

        # Use batch_writer for efficient batch writes
        with table.batch_writer() as batch:
            for idx, metric in enumerate(metrics):
                try:
                    # Generate unique metric_id for range key
                    # Use client_id and index to ensure uniqueness
                    metric_id = (
                        f"{metric.get('client_id', 0)}_{idx}_{uuid.uuid4().hex[:8]}"
                    )

                    item = {
                        "run_id": metric["run_id"],
                        "metric_id": metric_id,  # Range key
                        "timestamp": metric.get(
                            "timestamp", datetime.now(timezone.utc).isoformat()
                        ),
                        "client_id": int(metric.get("client_id", 0)),
                        # DynamoDB requires Decimal for float values, not float
                        "request_latency_ms": Decimal(
                            str(metric.get("request_latency_ms", 0))
                        ),
                        "bytes_transferred": int(metric.get("bytes_transferred", 0)),
                        "status_code": int(metric.get("status_code", 0)),
                    }

                    batch.put_item(Item=item)
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store metric: {str(e)}")

        logger.info(f"Stored {stored_count}/{len(metrics)} metrics in DynamoDB")
        return stored_count

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(
                f"Performance metrics table doesn't exist: {PERFORMANCE_METRICS_TABLE}"
            )
        else:
            logger.error(f"Error storing metrics in DynamoDB: {error_code} - {str(e)}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error storing metrics: {type(e).__name__}: {str(e)}")
        return 0


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


def publish_metrics_to_cloudwatch(
    run_id: str, metrics: List[Dict[str, Any]], total_duration_seconds: float
) -> bool:
    """
    Publish aggregated metrics to CloudWatch.

    Args:
        run_id: Unique run identifier
        metrics: List of metric dictionaries
        total_duration_seconds: Total duration of the workload

    Returns:
        True if successful, False otherwise
    """
    if not metrics:
        return False

    try:
        # Calculate statistics
        latencies = [
            m.get("request_latency_ms", 0)
            for m in metrics
            if m.get("status_code") == 200
        ]
        successful_metrics = [m for m in metrics if m.get("status_code") == 200]

        if not latencies:
            logger.warning("No successful requests to publish metrics for")
            return False

        # Sort latencies for percentile calculation
        sorted_latencies = sorted(latencies)

        # Calculate percentiles
        mean_latency = sum(latencies) / len(latencies) if latencies else 0
        median_latency = calculate_percentile(sorted_latencies, 50.0)
        p99_latency = calculate_percentile(sorted_latencies, 99.0)

        # Calculate throughput (bytes per second)
        total_bytes = sum(m.get("bytes_transferred", 0) for m in successful_metrics)
        throughput_bps = (
            total_bytes / total_duration_seconds if total_duration_seconds > 0 else 0
        )

        # Prepare CloudWatch metrics
        metric_data = [
            {
                "MetricName": "RequestLatencyMean",
                "Value": mean_latency,
                "Unit": "Milliseconds",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
            {
                "MetricName": "RequestLatencyMedian",
                "Value": median_latency,
                "Unit": "Milliseconds",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
            {
                "MetricName": "RequestLatencyP99",
                "Value": p99_latency,
                "Unit": "Milliseconds",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
            {
                "MetricName": "Throughput",
                "Value": throughput_bps,
                "Unit": "Bytes/Second",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
            {
                "MetricName": "TotalRequests",
                "Value": len(metrics),
                "Unit": "Count",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
            {
                "MetricName": "SuccessfulRequests",
                "Value": len(successful_metrics),
                "Unit": "Count",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "RunId", "Value": run_id}],
            },
        ]

        # Publish to CloudWatch (split into batches of 20 if needed)
        batch_size = 20
        for i in range(0, len(metric_data), batch_size):
            batch = metric_data[i : i + batch_size]
            cloudwatch.put_metric_data(Namespace=CLOUDWATCH_NAMESPACE, MetricData=batch)

        logger.info(
            f"Published metrics to CloudWatch: run_id={run_id}, "
            f"mean_latency={mean_latency:.2f}ms, median={median_latency:.2f}ms, "
            f"p99={p99_latency:.2f}ms, throughput={throughput_bps:.2f} B/s"
        )
        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"Error publishing metrics to CloudWatch: {error_code} - {str(e)}")
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error publishing metrics: {type(e).__name__}: {str(e)}"
        )
        return False


def store_and_publish_metrics(
    run_id: str, metrics: List[Dict[str, Any]], total_duration_seconds: float
) -> Dict[str, Any]:
    """
    Store metrics in DynamoDB and publish to CloudWatch.

    Args:
        run_id: Unique run identifier
        metrics: List of metric dictionaries
        total_duration_seconds: Total duration of the workload

    Returns:
        Dictionary with storage results
    """
    stored_count = store_metrics_in_dynamodb(metrics)
    cloudwatch_success = publish_metrics_to_cloudwatch(
        run_id, metrics, total_duration_seconds
    )

    return {
        "dynamodb_stored": stored_count,
        "cloudwatch_published": cloudwatch_success,
        "total_metrics": len(metrics),
    }
