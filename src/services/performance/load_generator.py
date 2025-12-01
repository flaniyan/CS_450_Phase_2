"""
Performance load generator service
Generates concurrent download requests and tracks metrics
"""

import asyncio
import aiohttp
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """Single performance metric for a request"""

    run_id: str
    client_id: int
    request_latency_ms: float
    bytes_transferred: int
    status_code: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary for storage"""
        return {
            "run_id": self.run_id,
            "client_id": self.client_id,
            "request_latency_ms": self.request_latency_ms,
            "bytes_transferred": self.bytes_transferred,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }


class LoadGenerator:
    """
    Generates concurrent load for performance testing.
    Makes concurrent download requests and collects metrics.
    """

    def __init__(
        self,
        run_id: str,
        base_url: str,
        num_clients: int = 100,
        model_id: str = "arnir0/Tiny-LLM",
        version: str = "main",
        duration_seconds: Optional[int] = None,
        use_performance_path: bool = False,
    ):
        """
        Initialize load generator.

        Args:
            run_id: Unique identifier for this workload run
            base_url: Base URL of the API (e.g., "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
            num_clients: Number of concurrent clients to simulate
            model_id: Model ID to download
            version: Model version (default: "main")
            duration_seconds: Optional duration limit in seconds
            use_performance_path: If True, use performance/ path instead of models/ path
        """
        self.run_id = run_id
        self.base_url = base_url.rstrip("/")
        self.num_clients = num_clients
        self.model_id = model_id
        self.version = version
        self.duration_seconds = duration_seconds
        self.use_performance_path = use_performance_path

        # Store metrics
        self.metrics: List[Metric] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def _get_download_url(self) -> str:
        """Construct download URL for model"""
        # Sanitize model_id for URL - use same logic as the API
        # Replace special characters that might break URLs
        sanitized_model_id = (
            self.model_id.replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        # Use performance/ path if specified, otherwise models/
        path_prefix = "performance" if self.use_performance_path else "models"
        return f"{self.base_url}/{path_prefix}/{sanitized_model_id}/{self.version}/model.zip"

    async def _make_request(
        self, client_id: int, session: aiohttp.ClientSession
    ) -> Metric:
        """
        Make a single download request and return metrics.

        Args:
            client_id: ID of this client (1-based)
            session: aiohttp session for making requests

        Returns:
            Metric object with request details
        """
        url = self._get_download_url()
        timestamp = datetime.now(timezone.utc)
        start_time = time.time()

        try:
            async with session.get(url) as response:
                # Read response content to measure bytes
                content = await response.read()
                end_time = time.time()

                latency_ms = (end_time - start_time) * 1000
                bytes_transferred = len(content)
                status_code = response.status

                metric = Metric(
                    run_id=self.run_id,
                    client_id=client_id,
                    request_latency_ms=latency_ms,
                    bytes_transferred=bytes_transferred,
                    status_code=status_code,
                    timestamp=timestamp,
                )

                logger.debug(
                    f"Request completed: client_id={client_id}, "
                    f"status={status_code}, latency={latency_ms:.2f}ms, "
                    f"bytes={bytes_transferred}"
                )

                return metric

        except asyncio.TimeoutError:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            logger.warning(f"Request timeout for client_id={client_id}")
            return Metric(
                run_id=self.run_id,
                client_id=client_id,
                request_latency_ms=latency_ms,
                bytes_transferred=0,
                status_code=0,  # 0 indicates timeout/error
                timestamp=timestamp,
            )

        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            logger.error(f"Request error for client_id={client_id}: {str(e)}")
            return Metric(
                run_id=self.run_id,
                client_id=client_id,
                request_latency_ms=latency_ms,
                bytes_transferred=0,
                status_code=0,  # 0 indicates error
                timestamp=timestamp,
            )

    async def _run_client(self, client_id: int, session: aiohttp.ClientSession):
        """
        Run a single client - makes one or more requests depending on duration.

        Args:
            client_id: ID of this client (1-based)
            session: aiohttp session for making requests
        """
        if self.duration_seconds:
            # Run for specified duration
            end_time = time.time() + self.duration_seconds
            request_count = 0

            while time.time() < end_time:
                metric = await self._make_request(client_id, session)
                self.metrics.append(metric)
                request_count += 1

                # Small delay between requests to avoid overwhelming the server
                await asyncio.sleep(0.1)
        else:
            # Single request per client
            metric = await self._make_request(client_id, session)
            self.metrics.append(metric)

    async def run(self):
        """
        Run the load generator with all clients concurrently.
        Collects metrics for all requests.
        """
        logger.info(
            f"Starting load generator: run_id={self.run_id}, "
            f"num_clients={self.num_clients}, model_id={self.model_id}"
        )

        self.start_time = time.time()

        # Create aiohttp session with timeout
        # Set timeout to allow for large file downloads (24MB model file)
        # total: total timeout for the entire operation
        # connect: timeout for establishing connection
        # sock_read: timeout for reading data from socket
        timeout = aiohttp.ClientTimeout(
            total=600,  # 10 minute total timeout per request (for large downloads)
            connect=60,  # 1 minute to establish connection
            sock_read=300  # 5 minute timeout for reading data
        )
        connector = aiohttp.TCPConnector(limit=self.num_clients)

        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            # Create tasks for all clients (client_id is 1-based)
            tasks = [
                self._run_client(client_id, session)
                for client_id in range(1, self.num_clients + 1)
            ]

            # Run all clients concurrently
            await asyncio.gather(*tasks)

        self.end_time = time.time()

        total_duration = self.end_time - self.start_time
        logger.info(
            f"Load generator completed: run_id={self.run_id}, "
            f"duration={total_duration:.2f}s, "
            f"total_requests={len(self.metrics)}"
        )

        # Store metrics in DynamoDB and publish to CloudWatch
        try:
            from .metrics_storage import store_and_publish_metrics

            metrics_dict = self.get_metrics()
            storage_result = store_and_publish_metrics(
                run_id=self.run_id,
                metrics=metrics_dict,
                total_duration_seconds=total_duration,
            )
            logger.info(
                f"Metrics storage completed: DynamoDB={storage_result['dynamodb_stored']}, "
                f"CloudWatch={storage_result['cloudwatch_published']}"
            )
        except Exception as e:
            logger.error(f"Failed to store/publish metrics: {str(e)}", exc_info=True)

    def get_metrics(self) -> List[Dict[str, Any]]:
        """
        Get all collected metrics as dictionaries.

        Returns:
            List of metric dictionaries
        """
        return [metric.to_dict() for metric in self.metrics]

    def _calculate_percentile(
        self, sorted_values: List[float], percentile: float
    ) -> float:
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

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics from collected metrics.
        Calculates mean, median, and 99th percentile latency, plus throughput.

        Returns:
            Dictionary with summary statistics
        """
        if not self.metrics:
            return {
                "total_requests": 0,
                "total_duration_seconds": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "mean_latency_ms": 0,
                "median_latency_ms": 0,
                "p99_latency_ms": 0,
                "throughput_bps": 0,
            }

        successful = [m for m in self.metrics if m.status_code == 200]
        failed = [m for m in self.metrics if m.status_code != 200]

        latencies = [m.request_latency_ms for m in self.metrics]
        successful_latencies = [m.request_latency_ms for m in successful]
        total_bytes = sum(m.bytes_transferred for m in successful)
        total_duration = (
            (self.end_time - self.start_time)
            if self.end_time and self.start_time
            else 0
        )

        # Calculate percentiles
        sorted_latencies = sorted(latencies) if latencies else []
        sorted_successful_latencies = (
            sorted(successful_latencies) if successful_latencies else []
        )

        mean_latency = sum(latencies) / len(latencies) if latencies else 0
        median_latency = self._calculate_percentile(sorted_latencies, 50.0)
        p99_latency = self._calculate_percentile(sorted_latencies, 99.0)

        # Calculate throughput (bytes per second)
        throughput_bps = total_bytes / total_duration if total_duration > 0 else 0

        return {
            "total_requests": len(self.metrics),
            "total_duration_seconds": total_duration,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "total_bytes_transferred": total_bytes,
            "mean_latency_ms": mean_latency,
            "median_latency_ms": median_latency,
            "p99_latency_ms": p99_latency,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "throughput_bps": throughput_bps,
        }


def calculate_latency(start_time: float, end_time: float) -> float:
    """Calculate latency in milliseconds from start and end times"""
    return (end_time - start_time) * 1000
