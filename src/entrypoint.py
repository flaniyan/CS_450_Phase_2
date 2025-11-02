from __future__ import annotations

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT

# Wrap the original app without modifying existing files
app = _app
app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)


