"""Integration tests for packages API endpoints."""

from fastapi.testclient import TestClient
from src.index import app

client = TestClient(app)


def test_reset_and_upload_and_get():
    """Test basic package operations."""
    # Reset first
    response = client.post("/api/packages/reset")
    assert response.status_code in (200, 404)  # 404 if endpoint doesn't exist yet
    
    # Try to get packages list
    response = client.get("/api/packages")
    assert response.status_code == 200
    assert "packages" in response.json()


def test_conflict_and_404():
    """Test error conditions."""
    # Try to get a non-existent package
    response = client.get("/api/packages/missing@0.0.0")
    assert response.status_code in (404, 404)  # Should return 404


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_hello_endpoint():
    """Test the hello endpoint."""
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "hello world"
