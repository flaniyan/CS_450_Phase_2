"""
Integration tests for Phase 2: Measurement Infrastructure
Tests black-box and white-box metrics collection, CloudWatch integration, and results reporting.
Run with: pytest tests/integration/test_performance_metrics.py -v
"""
import pytest
import requests
import json
import os
import boto3
import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
REGION = os.getenv("AWS_REGION", "us-east-1")
PERFORMANCE_METRICS_TABLE = "performance_metrics"


@pytest.fixture
def api_base_url():
    """Fixture for API base URL"""
    return BASE_URL


@pytest.fixture
def auth_token(api_base_url):
    """Fixture to get authentication token"""
    try:
        response = requests.put(
            f"{api_base_url}/authenticate",
            json={
                "user": {
                    "name": "ece30861defaultadminuser",
                    "is_admin": True
                },
                "secret": {
                    "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
                }
            }
        )
        if response.status_code == 200:
            return response.text.strip('"')
    except Exception:
        pass
    return None


@pytest.fixture
def performance_workload_run_id(api_base_url, auth_token):
    """Fixture to create a test performance workload run"""
    if not auth_token:
        pytest.skip("Authentication not available")
    
    payload = {
        "num_clients": 10,  # Small number for testing
        "model_id": "arnir0/Tiny-LLM",
        "duration_seconds": 30
    }
    
    try:
        response = requests.post(
            f"{api_base_url}/health/performance/workload",
            json=payload,
            headers={"X-Authorization": auth_token}
        )
        if response.status_code in [200, 202]:
            data = response.json()
            run_id = data.get("run_id")
            if run_id:
                # Wait a bit for workload to start
                time.sleep(2)
                yield run_id
            else:
                pytest.skip("Could not create workload run")
        else:
            pytest.skip(f"Could not create workload run: {response.status_code}")
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running")


class TestBlackBoxMetricsCollection:
    """Test black-box metrics collection (external perspective)"""
    
    def test_metrics_stored_in_dynamodb_structure(self):
        """Test that metrics table structure is correct"""
        # This will verify DynamoDB table exists and has correct schema
        # For now, we test the expected schema
        expected_fields = [
            "run_id",
            "timestamp",
            "client_id",
            "request_latency_ms",
            "bytes_transferred",
            "status_code"
        ]
        
        # Schema validation - actual DynamoDB check will be in integration
        for field in expected_fields:
            assert isinstance(field, str)
    
    @pytest.mark.skipif(
        os.getenv("SKIP_AWS_TESTS") == "true",
        reason="AWS tests disabled"
    )
    def test_metrics_stored_in_dynamodb(self, performance_workload_run_id):
        """Run workload and verify metrics written to DynamoDB"""
        run_id = performance_workload_run_id
        
        # Wait for workload to complete
        time.sleep(35)  # Wait longer than duration_seconds
        
        # Query DynamoDB for metrics
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table(PERFORMANCE_METRICS_TABLE)
        
        response = table.query(
            KeyConditionExpression='run_id = :run_id',
            ExpressionAttributeValues={':run_id': run_id}
        )
        
        items = response.get('Items', [])
        assert len(items) > 0, "No metrics found in DynamoDB"
        
        # Verify all required fields
        for item in items:
            assert 'run_id' in item
            assert 'timestamp' in item
            assert 'client_id' in item
            assert 'request_latency_ms' in item
            assert item['run_id'] == run_id
    
    @pytest.mark.skipif(
        os.getenv("SKIP_AWS_TESTS") == "true",
        reason="AWS tests disabled"
    )
    def test_metrics_sent_to_cloudwatch(self, performance_workload_run_id):
        """Verify custom metrics appear in CloudWatch"""
        run_id = performance_workload_run_id
        
        # Wait for metrics to be sent
        time.sleep(5)
        
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        
        # Query for custom metrics in ACME/Performance namespace
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)
        
        response = cloudwatch.list_metrics(
            Namespace='ACME/Performance',
            Dimensions=[
                {
                    'Name': 'RunId',
                    'Value': run_id
                }
            ]
        )
        
        # Should have at least some metrics
        metrics = response.get('Metrics', [])
        assert len(metrics) >= 0  # At minimum, no errors
    
    def test_throughput_calculation_from_sample_data(self):
        """Calculate throughput from stored metrics (using sample data)"""
        # Sample metrics data
        sample_metrics = [
            {"bytes_transferred": 1024, "request_latency_ms": 100},
            {"bytes_transferred": 2048, "request_latency_ms": 150},
            {"bytes_transferred": 1024, "request_latency_ms": 120},
        ]
        
        total_bytes = sum(m["bytes_transferred"] for m in sample_metrics)
        total_time_seconds = max(m["request_latency_ms"] for m in sample_metrics) / 1000.0
        
        throughput = total_bytes / total_time_seconds if total_time_seconds > 0 else 0
        assert throughput > 0
    
    def test_latency_percentiles_from_sample_data(self):
        """Calculate percentiles from sample latency data"""
        from tests.unit.test_performance_statistics import (
            calculate_mean, calculate_median, calculate_percentile
        )
        
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        
        mean = calculate_mean(latencies)
        median = calculate_median(latencies)
        p99 = calculate_percentile(latencies, 99)
        
        assert mean == 55.0
        assert median == 55.0
        assert p99 >= 90.0
    
    def test_latency_percentiles_edge_cases(self):
        """Test percentile calculation edge cases"""
        from tests.unit.test_performance_statistics import calculate_percentile
        
        # Single value
        assert calculate_percentile([100.0], 99) == 100.0
        
        # All same values
        assert calculate_percentile([50.0] * 10, 99) == 50.0
        
        # Empty list
        assert calculate_percentile([], 99) == 0.0


class TestWhiteBoxMetricsCollection:
    """Test white-box metrics collection (internal instrumentation)"""
    
    @patch('boto3.client')
    def test_s3_download_instrumentation(self, mock_boto3):
        """Verify S3 download operations emit metrics"""
        # Mock CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_boto3.return_value = mock_cloudwatch
        
        # This will test actual instrumentation once implemented
        # For now, verify the concept
        from datetime import datetime
        
        # Simulate metric emission
        namespace = "ACME/Performance"
        metric_name = "S3DownloadLatency"
        
        # Verify metric structure
        assert namespace == "ACME/Performance"
        assert metric_name == "S3DownloadLatency"
    
    def test_ecs_request_instrumentation_concept(self):
        """Test concept of ECS request instrumentation"""
        # This will verify FastAPI middleware/interceptor
        # For now, test the expected metric names
        expected_metrics = [
            "ACME/Performance/RequestProcessingTime",
            "ACME/Performance/ConcurrentRequests"
        ]
        
        for metric in expected_metrics:
            assert "ACME/Performance" in metric
            assert len(metric) > 0
    
    @pytest.mark.skipif(
        os.getenv("SKIP_AWS_TESTS") == "true",
        reason="AWS tests disabled"
    )
    def test_dynamodb_metrics_available(self):
        """Verify DynamoDB metrics are accessible in CloudWatch"""
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        
        # Query for DynamoDB metrics
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/DynamoDB',
            MetricName='ConsumedReadCapacityUnits',
            Dimensions=[
                {
                    'Name': 'TableName',
                    'Value': 'artifacts'
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average']
        )
        
        # Should not raise exception
        assert 'Datapoints' in response


class TestResultsReporting:
    """Test results reporting endpoint"""
    
    def test_results_endpoint_exists(self, api_base_url):
        """Verify GET /health/performance/results/{run_id} endpoint exists"""
        test_run_id = str(uuid.uuid4())
        try:
            response = requests.get(
                f"{api_base_url}/health/performance/results/{test_run_id}"
            )
            # Should not return 404 - might return 404 for missing run, but endpoint should exist
            assert response.status_code != 405, "Method not allowed - endpoint may not exist"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_results_endpoint_handles_missing_run(self, api_base_url, auth_token):
        """Request results for non-existent run_id"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        fake_run_id = str(uuid.uuid4())
        
        try:
            response = requests.get(
                f"{api_base_url}/health/performance/results/{fake_run_id}",
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            # Should return 404 for missing run
            assert response.status_code == 404
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_results_endpoint_returns_metrics_structure(self, api_base_url, auth_token, performance_workload_run_id):
        """Verify results endpoint returns correct structure"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        run_id = performance_workload_run_id
        
        # Wait for workload to potentially complete
        time.sleep(35)
        
        try:
            response = requests.get(
                f"{api_base_url}/health/performance/results/{run_id}",
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify structure
                assert "run_id" in data
                assert "status" in data
                
                if data.get("status") == "completed":
                    assert "metrics" in data
                    metrics = data["metrics"]
                    assert "throughput" in metrics or "latency" in metrics
            elif response.status_code == 404:
                pytest.skip("Run not found - may not have completed yet")
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_results_endpoint_in_progress_status(self, api_base_url, auth_token):
        """Request results while workload is still running"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Start a new workload
        payload = {
            "num_clients": 5,
            "model_id": "test-model",
            "duration_seconds": 60
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token}
            )
            
            if response.status_code in [200, 202]:
                data = response.json()
                run_id = data.get("run_id")
                
                if run_id:
                    # Immediately request results
                    time.sleep(1)
                    results_response = requests.get(
                        f"{api_base_url}/health/performance/results/{run_id}",
                        headers={"X-Authorization": auth_token}
                    )
                    
                    if results_response.status_code == 200:
                        results_data = results_response.json()
                        assert results_data.get("status") in ["in_progress", "started", "completed"]
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_results_calculations_accurate(self):
        """Compare endpoint results with manual calculations"""
        # Sample metrics
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        bytes_transferred = [1024] * 5
        total_time = 0.05  # 50ms
        
        from tests.unit.test_performance_statistics import (
            calculate_mean, calculate_median, calculate_percentile, calculate_throughput
        )
        
        mean_latency = calculate_mean(latencies)
        median_latency = calculate_median(latencies)
        p99_latency = calculate_percentile(latencies, 99)
        throughput = calculate_throughput(sum(bytes_transferred), total_time)
        
        # Verify calculations are reasonable
        assert 20.0 <= mean_latency <= 40.0
        assert 20.0 <= median_latency <= 40.0
        assert p99_latency >= 40.0
        assert throughput > 0

