import os
import time
import jwt
import contextlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.middleware.jwt_auth import JWTAuthMiddleware


JWT_SECRET = "devsecret"


@contextlib.contextmanager
def app_with_middleware():
    os.environ["JWT_SECRET"] = JWT_SECRET
    os.environ["JWT_LEEWAY_SEC"] = "0"  # <-- ensure strict exp rejection in tests
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware, exempt_paths=("/health",))
    
    @app.get("/health")
    def health():
        return {"status": "ok"}
    
    @app.get("/protected")
    def protected():
        return {"ok": True}
    
    yield TestClient(app)


def make_token(exp_offset_sec: int, secret: str = JWT_SECRET):
    """Generate a JWT token with specified expiration offset"""
    payload = {"sub": "demo", "exp": int(time.time()) + exp_offset_sec}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_no_token_returns_401_with_www_authenticate():
    """Test that missing Authorization header returns 401 with WWW-Authenticate"""
    with app_with_middleware() as client:
        r = client.get("/protected")
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "Bearer"
        assert "detail" in r.json()


def test_expired_token_returns_401():
    """Test that expired tokens are rejected"""
    with app_with_middleware() as client:
        tok = make_token(-5)  # expired 5 seconds ago
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "Bearer"
        # Should indicate expired token
        detail = r.json()["detail"].lower()
        assert "token expired" in detail or "invalid token" in detail


def test_bad_signature_returns_401_without_leak():
    """Test that tokens with bad signatures are rejected without leaking details"""
    with app_with_middleware() as client:
        tok = make_token(3600, secret="wrongsecret")
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "Bearer"
        # Should not leak internal details about signature verification
        detail = r.json()["detail"]
        assert detail in {"Invalid token", "Unauthorized"}


def test_valid_token_allows_200():
    """Test that valid tokens allow access to protected routes"""
    with app_with_middleware() as client:
        tok = make_token(3600)  # valid for 1 hour
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}


def test_exempt_paths_bypass_auth():
    """Test that exempt paths don't require authentication"""
    with app_with_middleware() as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

