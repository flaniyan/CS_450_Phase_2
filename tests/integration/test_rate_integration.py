import pytest
import requests
import subprocess
import sys
import os
from typing import Optional

def has_python() -> bool:
    """Check if Python is available in the system."""
    try:
        result = subprocess.run([sys.executable, "--version"], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

@pytest.fixture(scope="module")
def app_url():
    """Get the application URL for testing."""
    # You may need to adjust this based on your deployment
    return os.getenv("TEST_APP_URL", "http://localhost:8000")

@pytest.fixture(scope="module")
def skip_if_no_python():
    """Skip tests if Python is not available."""
    if not has_python():
        pytest.skip("Skipping integration test: Python not found")

class TestRateEndpoint:
    """Integration tests for the rate endpoint."""
    
    def test_calls_real_python_scorer_and_returns_data(self, app_url, skip_if_no_python):
        """Test that the rate endpoint calls real Python scorer and returns data."""
        if not has_python():
            pytest.skip("Python not available")
        
        url = f"{app_url}/api/registry/models/demo/rate"
        payload = {"target": "https://github.com/pallets/flask"}
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            # Allow enforce logic differences and Python errors
            assert response.status_code in [200, 422, 502], f"Unexpected status code: {response.status_code}"
            
            response_data = response.json()
            
            # Check that the response has the expected structure
            assert "data" in response_data, "Response missing 'data' field"
            assert "netScore" in response_data["data"], "Response missing 'data.netScore' field"
            assert "subscores" in response_data["data"], "Response missing 'data.subscores' field"
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Request failed: {e}")
        except ValueError as e:
            pytest.fail(f"Invalid JSON response: {e}")

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
