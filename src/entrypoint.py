from __future__ import annotations

import os

from src.index import app as _app
from src.middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT

# Wrap the original app without modifying existing files
app = _app
app.add_middleware(JWTAuthMiddleware, exempt_paths=exempt)


