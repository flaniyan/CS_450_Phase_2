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
    os.environ["JWT_LEEWAY_SEC"] = "0"
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
    payload = {"sub": "demo", "exp": int(time.time()) + exp_offset_sec}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_no_token_returns_401_with_www_authenticate():
    with app_with_middleware() as client:
        r = client.get("/protected")
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_expired_token_returns_401():
    with app_with_middleware() as client:
        tok = make_token(-5)
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401
        assert r.json()["detail"].lower().startswith("token expired") or r.json()[
            "detail"
        ].lower() == "invalid token"


def test_bad_signature_returns_401_without_leak():
    with app_with_middleware() as client:
        tok = make_token(3600, secret="wrongsecret")
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401
        assert r.json()["detail"] in {"Invalid token", "Unauthorized"}
        assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_valid_token_allows_200():
    with app_with_middleware() as client:
        tok = make_token(3600)
        r = client.get("/protected", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
