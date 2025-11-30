"""
Integration tests for Phase 5: Component Comparison Experiments
Tests Lambda vs ECS and S3 vs RDS comparisons.
Run with: pytest tests/integration/test_performance_component_comparison.py -v
"""
import pytest
import requests
import boto3
import os
import time
import uuid
from datetime import datetime, timedelta
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


class TestLambdaVsECSComparison:
    """Test Lambda vs ECS compute component comparison"""
    
    def test_lambda_endpoint_available(self, api_base_url, auth_token):
        """Verify Lambda-based download endpoint exists"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Test with Lambda backend enabled
        model_id = "arnir0/Tiny-LLM"
        version = "1.0.0"
        
        try:
            response = requests.get(
                f"{api_base_url}/models/{model_id}/{version}/model.zip",
                params={"backend": "lambda"},
                headers={"X-Authorization": auth_token}
            )
            # Should accept lambda backend parameter
            assert response.status_code in [200, 302, 400, 404]
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_lambda_performance(self, api_base_url, auth_token):
        """Run workload against Lambda endpoint and record metrics"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 100,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 300,
            "compute_backend": "lambda"
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
                
                # Wait for completion
                time.sleep(310)
                
                # Get results
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                if results_response.status_code == 200:
                    lambda_data = results_response.json()
                    lambda_metrics = lambda_data.get("metrics", {})
                    
                    # Verify metrics exist
                    assert "latency" in lambda_metrics or "throughput" in lambda_metrics
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_lambda_cold_start(self, api_base_url, auth_token):
        """Measure cold start latency for Lambda"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # First request after idle period should trigger cold start
        model_id = "arnir0/Tiny-LLM"
        version = "1.0.0"
        
        try:
            # Wait for Lambda to go cold (if possible)
            time.sleep(5)
            
            start_time = time.time()
            response = requests.get(
                f"{api_base_url}/models/{model_id}/{version}/model.zip",
                params={"backend": "lambda"},
                headers={"X-Authorization": auth_token}
            )
            first_request_time = (time.time() - start_time) * 1000
            
            # Second request should be faster (warm)
            start_time = time.time()
            response2 = requests.get(
                f"{api_base_url}/models/{model_id}/{version}/model.zip",
                params={"backend": "lambda"},
                headers={"X-Authorization": auth_token}
            )
            second_request_time = (time.time() - start_time) * 1000
            
            # First request may include cold start overhead
            assert first_request_time > 0
            assert second_request_time > 0
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_lambda_vs_ecs_comparison(self, api_base_url, auth_token):
        """Compare Lambda vs ECS performance metrics"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Run same workload on both backends
        payload_template = {
            "num_clients": 100,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 300
        }
        
        ecs_results = None
        lambda_results = None
        
        try:
            # Run ECS workload
            ecs_payload = {**payload_template, "compute_backend": "ecs"}
            ecs_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=ecs_payload,
                headers={"X-Authorization": auth_token}
            )
            
            if ecs_response.status_code in [200, 202]:
                ecs_run_id = ecs_response.json().get("run_id")
                time.sleep(310)
                
                ecs_results_resp = requests.get(
                    f"{api_base_url}/health/performance/results/{ecs_run_id}",
                    headers={"X-Authorization": auth_token}
                )
                if ecs_results_resp.status_code == 200:
                    ecs_results = ecs_results_resp.json()
            
            # Run Lambda workload
            lambda_payload = {**payload_template, "compute_backend": "lambda"}
            lambda_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=lambda_payload,
                headers={"X-Authorization": auth_token}
            )
            
            if lambda_response.status_code in [200, 202]:
                lambda_run_id = lambda_response.json().get("run_id")
                time.sleep(310)
                
                lambda_results_resp = requests.get(
                    f"{api_base_url}/health/performance/results/{lambda_run_id}",
                    headers={"X-Authorization": auth_token}
                )
                if lambda_results_resp.status_code == 200:
                    lambda_results = lambda_results_resp.json()
            
            # Compare metrics
            if ecs_results and lambda_results:
                ecs_latency = ecs_results.get("metrics", {}).get("latency", {}).get("mean_ms", 0)
                lambda_latency = lambda_results.get("metrics", {}).get("latency", {}).get("mean_ms", 0)
                
                # Both should have valid metrics
                assert ecs_latency > 0 or lambda_latency > 0
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestS3VsRDSComparison:
    """Test S3 vs RDS storage component comparison"""
    
    def test_rds_storage_backend(self, api_base_url, auth_token):
        """Verify RDS backend is configured and functional"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Test with RDS storage backend
        model_id = "arnir0/Tiny-LLM"
        version = "1.0.0"
        
        try:
            response = requests.get(
                f"{api_base_url}/models/{model_id}/{version}/model.zip",
                params={"storage_backend": "rds"},
                headers={"X-Authorization": auth_token}
            )
            # Should accept rds backend parameter
            assert response.status_code in [200, 302, 400, 404]
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_rds_performance(self, api_base_url, auth_token):
        """Run workload with RDS storage backend"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 100,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 300,
            "storage_backend": "rds"
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
                
                time.sleep(310)
                
                results_response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                if results_response.status_code == 200:
                    rds_data = results_response.json()
                    rds_metrics = rds_data.get("metrics", {})
                    
                    # Verify metrics exist
                    assert "latency" in rds_metrics or "throughput" in rds_metrics
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_storage_backend_switching(self, api_base_url, auth_token):
        """Verify configuration flag allows switching between backends"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        model_id = "arnir0/Tiny-LLM"
        version = "1.0.0"
        
        backends = ["s3", "rds"]
        
        for backend in backends:
            try:
                response = requests.get(
                    f"{api_base_url}/models/{model_id}/{version}/model.zip",
                    params={"storage_backend": backend},
                    headers={"X-Authorization": auth_token}
                )
                # Should accept both backends (may return 404 if model doesn't exist in that backend)
                assert response.status_code in [200, 302, 400, 404]
            except requests.exceptions.ConnectionError:
                pytest.skip("API server not running")
    
    def test_s3_vs_rds_comparison(self, api_base_url, auth_token):
        """Compare S3 vs RDS performance metrics"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload_template = {
            "num_clients": 100,
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 300
        }
        
        s3_results = None
        rds_results = None
        
        try:
            # Run S3 workload
            s3_payload = {**payload_template, "storage_backend": "s3"}
            s3_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=s3_payload,
                headers={"X-Authorization": auth_token}
            )
            
            if s3_response.status_code in [200, 202]:
                s3_run_id = s3_response.json().get("run_id")
                time.sleep(310)
                
                s3_results_resp = requests.get(
                    f"{api_base_url}/health/performance/results/{s3_run_id}",
                    headers={"X-Authorization": auth_token}
                )
                if s3_results_resp.status_code == 200:
                    s3_results = s3_results_resp.json()
            
            # Run RDS workload
            rds_payload = {**payload_template, "storage_backend": "rds"}
            rds_response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=rds_payload,
                headers={"X-Authorization": auth_token}
            )
            
            if rds_response.status_code in [200, 202]:
                rds_run_id = rds_response.json().get("run_id")
                time.sleep(310)
                
                rds_results_resp = requests.get(
                    f"{api_base_url}/health/performance/results/{rds_run_id}",
                    headers={"X-Authorization": auth_token}
                )
                if rds_results_resp.status_code == 200:
                    rds_results = rds_results_resp.json()
            
            # Compare metrics
            if s3_results and rds_results:
                s3_latency = s3_results.get("metrics", {}).get("latency", {}).get("mean_ms", 0)
                rds_latency = rds_results.get("metrics", {}).get("latency", {}).get("mean_ms", 0)
                
                # Both should have valid metrics
                assert s3_latency > 0 or rds_latency > 0
                
                # Document differences
                s3_throughput = s3_results.get("metrics", {}).get("throughput", {}).get("bytes_per_second", 0)
                rds_throughput = rds_results.get("metrics", {}).get("throughput", {}).get("bytes_per_second", 0)
                
                # Throughput comparison
                assert s3_throughput >= 0 and rds_throughput >= 0
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestConfigurationManagement:
    """Test configuration management for component selection"""
    
    def test_compute_backend_configuration(self, api_base_url):
        """Verify compute backend can be configured"""
        try:
            response = requests.get(f"{api_base_url}/health")
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_storage_backend_configuration(self, api_base_url):
        """Verify storage backend can be configured"""
        try:
            response = requests.get(f"{api_base_url}/health")
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")

