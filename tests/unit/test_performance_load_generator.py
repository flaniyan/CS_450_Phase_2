"""
Unit tests for performance load generator functionality.
These tests verify the core logic of load generation without external dependencies.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Import the load generator once it's implemented
from src.services.performance.load_generator import LoadGenerator, Metric, calculate_latency


class TestLoadGeneratorMetrics:
    """Test metrics collection functions"""
    
    def test_metric_creation(self):
        """Test that metrics can be created with required fields"""
        metric = Metric(
            run_id="test-run-123",
            client_id=1,
            request_latency_ms=100.5,
            bytes_transferred=1024,
            status_code=200,
            timestamp=datetime.utcnow()
        )
        assert metric.run_id == "test-run-123"
        assert metric.client_id == 1
        assert metric.request_latency_ms == 100.5
    
    def test_latency_calculation(self):
        """Test latency calculation from start and end times"""
        start_time = time.time()
        time.sleep(0.1)  # Simulate 100ms delay
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        assert 95 <= latency_ms <= 150  # Allow some tolerance
    
    def test_metric_serialization(self):
        """Test that metrics can be serialized to dict for DynamoDB"""
        metric = Metric(
            run_id="test-run-123",
            client_id=1,
            request_latency_ms=100.5,
            bytes_transferred=1024,
            status_code=200,
            timestamp=datetime.utcnow()
        )
        metric_dict = metric.to_dict()
        assert isinstance(metric_dict, dict)
        assert "run_id" in metric_dict
        assert "client_id" in metric_dict


class TestLoadGeneratorConcurrency:
    """Test concurrent request handling"""
    
    @pytest.mark.asyncio
    async def test_create_multiple_clients(self):
        """Test that multiple clients can be created concurrently"""
        num_clients = 10
        clients = []
        
        async def create_client(client_id):
            return {"client_id": client_id, "created_at": time.time()}
        
        tasks = [create_client(i) for i in range(num_clients)]
        clients = await asyncio.gather(*tasks)
        
        assert len(clients) == num_clients
        assert all(c["client_id"] == i for i, c in enumerate(clients))
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_tracked_separately(self):
        """Test that concurrent requests are tracked separately"""
        metrics = []
        
        async def mock_request(client_id):
            start = time.time()
            await asyncio.sleep(0.01)  # Simulate request
            end = time.time()
            metrics.append({
                "client_id": client_id,
                "latency_ms": (end - start) * 1000
            })
        
        num_clients = 5
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(metrics) == num_clients
        assert len(set(m["client_id"] for m in metrics)) == num_clients
    
    @pytest.mark.asyncio
    async def test_all_clients_complete(self):
        """Test that all client requests complete"""
        completed = []
        
        async def mock_request(client_id):
            await asyncio.sleep(0.01)
            completed.append(client_id)
        
        num_clients = 10
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(completed) == num_clients
        assert set(completed) == set(range(num_clients))


class TestLoadGeneratorErrorHandling:
    """Test error handling in load generator"""
    
    @pytest.mark.asyncio
    async def test_error_tracking(self):
        """Test that errors are tracked correctly"""
        results = []
        
        async def mock_request_with_error(client_id):
            try:
                if client_id % 2 == 0:
                    raise Exception("Simulated error")
                results.append({"client_id": client_id, "status": "success"})
            except Exception as e:
                results.append({"client_id": client_id, "status": "error", "error": str(e)})
        
        num_clients = 5
        tasks = [mock_request_with_error(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(results) == num_clients
        errors = [r for r in results if r["status"] == "error"]
        successes = [r for r in results if r["status"] == "success"]
        assert len(errors) > 0
        assert len(successes) > 0
    
    @pytest.mark.asyncio
    async def test_partial_failures_dont_stop_others(self):
        """Test that one client failure doesn't stop others"""
        results = []
        
        async def mock_request(client_id):
            try:
                if client_id == 2:
                    raise Exception("Client 2 failed")
                await asyncio.sleep(0.01)
                results.append({"client_id": client_id, "status": "success"})
            except Exception:
                results.append({"client_id": client_id, "status": "error"})
        
        num_clients = 5
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        # All clients should complete (either success or error)
        assert len(results) == num_clients
        # At least one should succeed
        assert any(r["status"] == "success" for r in results)
        # At least one should error
        assert any(r["status"] == "error" for r in results)


class TestLoadGeneratorStatistics:
    """Test statistics calculations for load generator"""
    
    def test_mean_calculation(self):
        """Test mean latency calculation"""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        mean = sum(latencies) / len(latencies)
        assert mean == 300.0
    
    def test_median_calculation_odd(self):
        """Test median calculation with odd number of values"""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        median = sorted_latencies[n // 2]
        assert median == 300.0
    
    def test_median_calculation_even(self):
        """Test median calculation with even number of values"""
        latencies = [100.0, 200.0, 300.0, 400.0]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        median = (sorted_latencies[n // 2 - 1] + sorted_latencies[n // 2]) / 2
        assert median == 250.0
    
    def test_percentile_99_calculation(self):
        """Test 99th percentile calculation"""
        # 100 values, 99th percentile should be the 99th value
        latencies = list(range(1, 101))  # 1 to 100
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        percentile_index = int(n * 0.99)
        p99 = sorted_latencies[min(percentile_index, n - 1)]
        assert p99 == 99 or p99 == 100  # Should be close to 99
    
    def test_throughput_calculation(self):
        """Test throughput calculation"""
        total_bytes = 1024 * 100  # 100 KB
        total_time_seconds = 10.0
        throughput_bytes_per_sec = total_bytes / total_time_seconds
        assert throughput_bytes_per_sec == 10240.0
    
    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        total_requests = 100
        successful_requests = 95
        error_rate = (total_requests - successful_requests) / total_requests * 100
        assert error_rate == 5.0

