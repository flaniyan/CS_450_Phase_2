from __future__ import annotations

import os

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT

# Wrap the original app without modifying existing files
app = _app

# Only add JWT middleware if auth is explicitly enabled
# Auth is enabled if ENABLE_AUTH=true OR if JWT_SECRET is set
enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
jwt_secret = os.getenv("JWT_SECRET")
if enable_auth or jwt_secret:
    app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)
