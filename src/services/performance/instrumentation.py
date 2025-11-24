"""
Performance instrumentation utilities
Provides decorators and helpers for adding CloudWatch metrics to services
"""
import boto3
import os
import time
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# AWS clients
region = os.getenv("AWS_REGION", "us-east-1")
cloudwatch = boto3.client("cloudwatch", region_name=region)

# Configuration
CLOUDWATCH_NAMESPACE = "ACME/Performance"


def publish_metric(
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: Optional[Dict[str, str]] = None
) -> bool:
    """
    Publish a single metric to CloudWatch.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement (Count, Milliseconds, Bytes, etc.)
        dimensions: Optional dimensions dictionary
        
    Returns:
        True if successful, False otherwise
    """
    try:
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.now(timezone.utc),
        }
        
        if dimensions:
            metric_data["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in dimensions.items()
            ]
        
        cloudwatch.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[metric_data]
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to publish metric {metric_name}: {str(e)}")
        return False


@contextmanager
def measure_operation(metric_name: str, dimensions: Optional[Dict[str, str]] = None):
    """
    Context manager to measure operation duration and publish as CloudWatch metric.
    
    Usage:
        with measure_operation("OperationName", {"Component": "S3"}):
            # do work
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        publish_metric(
            metric_name=metric_name,
            value=duration_ms,
            unit="Milliseconds",
            dimensions=dimensions
        )


def instrument_latency(metric_name: str, dimensions: Optional[Dict[str, str]] = None):
    """
    Decorator to measure function execution time and publish as CloudWatch metric.
    
    Usage:
        @instrument_latency("FunctionName", {"Component": "S3"})
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                publish_metric(
                    metric_name=metric_name,
                    value=duration_ms,
                    unit="Milliseconds",
                    dimensions=dimensions
                )
        return wrapper
    return decorator


def instrument_bytes(metric_name: str, get_bytes_func: Optional[Callable] = None, dimensions: Optional[Dict[str, str]] = None):
    """
    Decorator to measure bytes transferred and publish as CloudWatch metric.
    
    Args:
        metric_name: Name of the metric
        get_bytes_func: Optional function to extract bytes from result (defaults to len(result))
        dimensions: Optional dimensions dictionary
        
    Usage:
        @instrument_bytes("BytesTransferred", lambda r: len(r), {"Component": "S3"})
        def download_file():
            return bytes_data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                if get_bytes_func:
                    bytes_value = get_bytes_func(result)
                else:
                    bytes_value = len(result) if hasattr(result, '__len__') else 0
                
                publish_metric(
                    metric_name=metric_name,
                    value=float(bytes_value),
                    unit="Bytes",
                    dimensions=dimensions
                )
            except Exception as e:
                logger.warning(f"Failed to instrument bytes for {metric_name}: {str(e)}")
            return result
        return wrapper
    return decorator

