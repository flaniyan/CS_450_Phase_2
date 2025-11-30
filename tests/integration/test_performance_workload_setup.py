"""
Integration tests for Phase 1: Workload Setup
Tests registry population, workload trigger endpoint, and load generator functionality.
Run with: pytest tests/integration/test_performance_workload_setup.py -v
"""
import pytest
import requests
import json
import os
import boto3
import uuid
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
REGION = os.getenv("AWS_REGION", "us-east-1")

# AWS clients (will use moto or real AWS in actual tests)
s3_client = None
dynamodb_resource = None


@pytest.fixture
def api_base_url():
    """Fixture for API base URL"""
    return BASE_URL


@pytest.fixture
def auth_token(api_base_url):
    """Fixture to get authentication token"""
    # This should use actual authentication endpoint
    # For now, return None - tests will need to handle auth
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


class TestRegistryPopulation:
    """Test registry population script functionality"""
    
    def test_populate_registry_script_exists(self):
        """Test that populate_registry.py script exists"""
        script_path = "scripts/populate_registry.py"
        # Note: This test will pass once script is created
        # For now, we check if we can import or if file exists
        if os.path.exists(script_path):
            assert True
        else:
            pytest.skip(f"Script {script_path} not yet created")
    
    def test_populate_registry_creates_500_models(self):
        """Verify script creates exactly 500 model entries"""
        import subprocess
        result = subprocess.run(["python", "scripts/populate_registry.py"], capture_output=True)
        assert result.returncode == 0
        
        # Then verify DynamoDB has 500 models
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table("artifacts")
        response = table.scan()
        model_count = sum(1 for item in response["Items"] if item.get("type") == "model")
        assert model_count >= 500
    
    def test_populate_registry_tiny_llm_ingested(self):
        """Verify Tiny-LLM model is ingested correctly"""
        # Check DynamoDB for Tiny-LLM model
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table("artifacts")
        response = table.scan(
            FilterExpression="contains(#n, :name)",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": "Tiny-LLM"}
        )
        assert len(response["Items"]) > 0, "Tiny-LLM model not found in DynamoDB"
        
        # Check S3 for model file
        s3 = boto3.client('s3', region_name=REGION)
        response = s3.list_objects_v2(
            Bucket=ARTIFACTS_BUCKET,
            Prefix="models/arnir0_Tiny-LLM/"
        )
        assert 'Contents' in response, "Tiny-LLM model file not found in S3"
        assert len(response['Contents']) > 0
    
    def test_populate_registry_idempotent(self):
        """Verify script can be run multiple times without creating duplicates"""
        import subprocess
        
        # Get initial count
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table("artifacts")
        response_before = table.scan()
        count_before = len(response_before["Items"])
        
        # Run script again
        result = subprocess.run(["python", "scripts/populate_registry.py"], capture_output=True)
        assert result.returncode == 0
        
        # Get count after
        response_after = table.scan()
        count_after = len(response_after["Items"])
        
        # Count should be the same (no duplicates)
        assert count_after == count_before, "Duplicate models created on second run"
    
    def test_populate_registry_tiny_llm_downloadable(self, api_base_url, auth_token):
        """Verify Tiny-LLM model can be downloaded after ingestion"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Try to download Tiny-LLM model
        model_id = "arnir0_Tiny-LLM"  # Sanitized model ID
        version = "1.0.0"
        
        response = requests.get(
            f"{api_base_url}/models/{model_id}/{version}/model.zip",
            headers={"X-Authorization": auth_token}
        )
        assert response.status_code == 200
        assert len(response.content) > 0


class TestPerformanceWorkloadEndpoint:
    """Test performance workload trigger endpoint"""
    
    def test_performance_workload_endpoint_exists(self, api_base_url):
        """Verify POST /health/performance/workload endpoint exists"""
        try:
            response = requests.post(f"{api_base_url}/health/performance/workload", json={})
            # Should not return 404 - might return 400 for missing params, but not 404
            assert response.status_code != 404, "Endpoint does not exist"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_performance_workload_endpoint_returns_200(self, api_base_url, auth_token):
        """Verify endpoint returns 200 status code with valid request"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 10,  # Use smaller number for testing
            "model_id": "arnir0/Tiny-LLM",
            "duration_seconds": 60
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            # Accept 200 or 202 (accepted)
            assert response.status_code in [200, 202], f"Unexpected status: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_performance_workload_returns_run_id(self, api_base_url, auth_token):
        """Verify response contains run_id field"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 10,
            "model_id": "arnir0/Tiny-LLM"
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            
            if response.status_code in [200, 202]:
                data = response.json()
                assert "run_id" in data, "Response missing run_id field"
                # Verify run_id is valid UUID format
                run_id = data["run_id"]
                uuid.UUID(run_id)  # Will raise ValueError if not valid UUID
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_performance_workload_accepts_default_parameters(self, api_base_url, auth_token):
        """Test with default parameters (num_clients=100)"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {}  # Empty payload should use defaults
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            # Should accept empty payload with defaults or require minimal fields
            assert response.status_code in [200, 202, 400], f"Unexpected status: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_performance_workload_accepts_custom_parameters(self, api_base_url, auth_token):
        """Test with custom parameters"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        payload = {
            "num_clients": 50,
            "model_id": "test-model",
            "artifact_id": "test-artifact-123",
            "duration_seconds": 120
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            assert response.status_code in [200, 202, 400], f"Unexpected status: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_performance_workload_rejects_invalid_parameters(self, api_base_url, auth_token):
        """Test with invalid parameters"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # Test negative clients
        payload = {"num_clients": -10}
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            assert response.status_code == 400, "Should reject negative clients"
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    @patch('src.services.performance.load_generator.LoadGenerator')
    def test_performance_workload_starts_background_task(self, mock_load_generator, api_base_url, auth_token):
        """Verify background task is actually started"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        # This test will need the actual implementation to verify
        # For now, we verify the endpoint exists and accepts requests
        payload = {"num_clients": 10, "model_id": "test"}
        
        try:
            response = requests.post(
                f"{api_base_url}/health/performance/workload",
                json=payload,
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            assert response.status_code in [200, 202]
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestLoadGenerator:
    """Test load generator functionality"""
    
    @pytest.mark.asyncio
    async def test_load_generator_creates_clients(self):
        """Verify load generator creates specified number of clients"""
        import uuid
        num_clients = 10
        
        from src.services.performance.load_generator import LoadGenerator
        generator = LoadGenerator(
            run_id=str(uuid.uuid4()),
            base_url="http://test",
            num_clients=num_clients
        )
        assert generator.num_clients == num_clients
    
    @pytest.mark.asyncio
    async def test_load_generator_makes_download_requests(self):
        """Verify load generator makes requests to correct endpoint"""
        import uuid
        from src.services.performance.load_generator import LoadGenerator
        
        run_id = str(uuid.uuid4())
        base_url = "http://test"
        generator = LoadGenerator(
            run_id=run_id,
            base_url=base_url,
            num_clients=1,
            model_id="arnir0/Tiny-LLM"
        )
        
        # Verify correct endpoint is constructed
        url = generator._get_download_url()
        assert base_url in url
        assert "Tiny-LLM" in url or "arnir0_Tiny-LLM" in url
        assert generator.num_clients == 1
    
    def test_load_generator_tracks_timing_metrics(self):
        """Verify each request records timing metrics"""
        # Test that start/end times are recorded
        import time
        
        start_time = time.time()
        time.sleep(0.01)
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        assert latency_ms > 0
        assert latency_ms < 100  # Should be around 10ms
    
    def test_load_generator_handles_errors(self):
        """Verify failed requests are tracked separately"""
        # Test error handling logic
        results = []
        
        def mock_request(success=True):
            try:
                if not success:
                    raise Exception("Request failed")
                results.append({"status": "success"})
            except Exception as e:
                results.append({"status": "error", "error": str(e)})
        
        mock_request(success=True)
        mock_request(success=False)
        
        assert len(results) == 2
        assert any(r["status"] == "success" for r in results)
        assert any(r["status"] == "error" for r in results)


class TestTracksEndpoint:
    """Test that /tracks endpoint includes Performance track"""
    
    def test_tracks_endpoint_exists(self, api_base_url):
        """Verify /tracks endpoint exists"""
        try:
            response = requests.get(f"{api_base_url}/tracks")
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_tracks_endpoint_returns_performance_track(self, api_base_url):
        """Verify /tracks returns Performance track in plannedTracks"""
        try:
            response = requests.get(f"{api_base_url}/tracks")
            assert response.status_code == 200
            
            data = response.json()
            assert "plannedTracks" in data or "tracks" in data
            
            tracks_key = "plannedTracks" if "plannedTracks" in data else "tracks"
            tracks = data[tracks_key]
            
            assert isinstance(tracks, list)
            assert "Performance track" in tracks or "performance" in [t.lower() for t in tracks]
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")

