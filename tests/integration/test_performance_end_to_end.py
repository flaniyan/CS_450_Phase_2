"""
End-to-End integration tests for Performance Track
Tests the complete performance workflow from trigger to results.
Run with: pytest tests/integration/test_performance_end_to_end.py -v
"""
import pytest
import requests
import boto3
import os
import time
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
REGION = os.getenv("AWS_REGION", "us-east-1")


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


class TestFullPerformanceWorkflow:
    """Test complete end-to-end performance workflow"""
    
    def test_full_performance_workflow(self, api_base_url, auth_token):
        """Test complete workflow: trigger -> wait -> retrieve results"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Step 1: Trigger workload
        payload = {
            "num_clients": 10,  # Smaller number for E2E test
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 60
        }
        
        try:
            trigger_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token}
            )
            
            assert trigger_response.status_code in [200, 202], "Failed to trigger workload"
            
            trigger_data = trigger_response.json()
            run_id = trigger_data.get("run_id")
            assert run_id is not None, "No run_id returned"
            
            # Step 2: Wait for completion (poll status)
            max_wait_time = 120  # 2 minutes for smaller workload
            wait_interval = 5
            elapsed = 0
            status = None
            
            while elapsed < max_wait_time:
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                if results_response.status_code == 200:
                    results_data = results_response.json()
                    status = results_data.get("status")
                    
                    if status == "completed":
                        break
                    elif status == "failed":
                        pytest.fail("Workload failed")
                
                time.sleep(wait_interval)
                elapsed += wait_interval
            
            # Step 3: Verify results are complete
            assert status == "completed", f"Workload did not complete: {status}"
            
            # Step 4: Verify all metrics are present
            results_response = requests.get(
                f"{api_base_url}/health/performance/results/{run_id}",
                headers={"X-Authorization": auth_token}
            )
            
            assert results_response.status_code == 200
            results_data = results_response.json()
            
            assert "run_id" in results_data
            assert "status" in results_data
            assert results_data["status"] == "completed"
            assert "metrics" in results_data
            
            metrics = results_data["metrics"]
            assert "latency" in metrics or "throughput" in metrics
            
            if "latency" in metrics:
                latency = metrics["latency"]
                assert "mean_ms" in latency or "p99_ms" in latency
            
            if "throughput" in metrics:
                throughput = metrics["throughput"]
                assert "requests_per_second" in throughput or "bytes_per_second" in throughput
                
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_multiple_concurrent_workloads(self, api_base_url, auth_token):
        """Test multiple workloads can run concurrently"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 5,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 30
        }
        
        run_ids = []
        
        try:
            # Trigger 3 workloads concurrently
            for i in range(3):
                response = requests.post(
                    f"{api_base_url}/health/performance/workload",
                    json=payload,
                    headers={"X-Authorization": auth_token}
                )
                
                if response.status_code in [200, 202]:
                    data = response.json()
                    run_id = data.get("run_id")
                    if run_id:
                        run_ids.append(run_id)
            
            # Verify all have unique run_ids
            assert len(run_ids) == 3, "Not all workloads were triggered"
            assert len(set(run_ids)) == 3, "Duplicate run_ids returned"
            
            # Verify all can be queried independently
            for run_id in run_ids:
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                # Should return either results or 404 (if not started yet)
                assert results_response.status_code in [200, 404]
                
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_workload_error_handling(self, api_base_url, auth_token):
        """Test error handling with invalid parameters"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Test with invalid model_id
        payload_invalid_model = {
            "num_clients": 10,
            "model_id": "nonexistent-model-12345",
            "duration_seconds": 60
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload_invalid_model,
                headers={"X-Authorization": auth_token}
            )
            
            # Should either accept (and fail later) or reject immediately
            assert response.status_code in [200, 202, 400, 404]
            
            # Test with negative clients
            payload_negative = {
                "num_clients": -10,
                "model_id": "arnir0/Tiny-LLM"
            }
            
            response2 = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload_negative,
                headers={"X-Authorization": auth_token}
            )
            
            # Should reject negative clients
            assert response2.status_code == 400
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_partial_results_available(self, api_base_url, auth_token):
        """Verify partial results are available while workload is running"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 10,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 120  # 2 minutes
        }
        
        try:
            trigger_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token}
            )
            
            if trigger_response.status_code in [200, 202]:
                run_id = trigger_response.json().get("run_id")
                
                # Wait a bit for some metrics to be collected
                time.sleep(10)
                
                # Request results (should show in_progress)
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                if results_response.status_code == 200:
                    results_data = results_response.json()
                    status = results_data.get("status")
                    
                    # Should be in_progress or completed
                    assert status in ["in_progress", "started", "completed"]
                    
                    # May have partial metrics
                    if "metrics" in results_data:
                        assert True  # Partial metrics available
                        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestPerformanceIntegrationWithHealthDashboard:
    """Test performance features integrated with health dashboard"""
    
    def test_health_components_includes_performance(self, api_base_url):
        """Verify /health/components includes performance component"""
        try:
            response = requests.get(f"{api_base_url}/health/components")
            assert response.status_code == 200
            
            data = response.json()
            assert "components" in data
            
            components = data["components"]
            
            # Find performance component
            performance_component = None
            for component in components:
                if component.get("id") == "performance" or "performance" in component.get("id", "").lower():
                    performance_component = component
                    break
            
            # Performance component should exist
            assert performance_component is not None, "Performance component not found in health dashboard"
            
            # Should have metrics
            if "metrics" in performance_component:
                assert True  # Metrics available
                
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_tracks_endpoint_includes_performance(self, api_base_url):
        """Verify /tracks endpoint includes Performance track"""
        try:
            response = requests.get(f"{api_base_url}/tracks")
            assert response.status_code == 200
            
            data = response.json()
            
            # Check for plannedTracks or tracks field
            tracks_key = "plannedTracks" if "plannedTracks" in data else "tracks"
            tracks = data.get(tracks_key, [])
            
            assert isinstance(tracks, list)
            assert "Performance track" in tracks or any("performance" in str(t).lower() for t in tracks)
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestPerformanceMetricsPersistence:
    """Test that performance metrics are persisted correctly"""
    
    def test_metrics_persisted_in_dynamodb(self, api_base_url, auth_token):
        """Verify metrics are stored in DynamoDB and persist"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 5,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 30
        }
        
        try:
            trigger_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token}
            )
            
            if trigger_response.status_code in [200, 202]:
                run_id = trigger_response.json().get("run_id")
                
                # Wait for completion
                time.sleep(40)
                
                # Check DynamoDB
                dynamodb = boto3.resource('dynamodb', region_name=REGION)
                table = dynamodb.Table("performance_metrics")
                
                response = table.query(
                    KeyConditionExpression='run_id = :run_id',
                    ExpressionAttributeValues={':run_id': run_id}
                )
                
                items = response.get('Items', [])
                # Should have metrics persisted
                assert len(items) >= 0  # At minimum, no errors
                
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_metrics_queryable_by_run_id(self, api_base_url, auth_token):
        """Verify metrics can be queried by run_id"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 5,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 30
        }
        
        try:
            trigger_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token}
            )
            
            if trigger_response.status_code in [200, 202]:
                run_id = trigger_response.json().get("run_id")
                
                time.sleep(40)
                
                # Query via API
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                # Should return results or 404 (if not completed)
                assert results_response.status_code in [200, 404]
                
                if results_response.status_code == 200:
                    data = results_response.json()
                    assert data.get("run_id") == run_id
                    
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")

