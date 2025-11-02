from __future__ import annotations

import os
from typing import Iterable

import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


def _is_exempt(path: str, exempt_paths: Iterable[str]) -> bool:
    # allow exact match or prefix (e.g., /health, /healthz, /health/live)
    return any(path == p or path.startswith(p.rstrip("/")) for p in exempt_paths)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, exempt_paths: Iterable[str] = ()):
        super().__init__(app)
        self.exempt_paths = tuple(exempt_paths)
        self.secret = os.getenv("JWT_SECRET", "")
        # strict by default; tests set JWT_LEEWAY_SEC=0 explicitly
        try:
            self.leeway = int(os.getenv("JWT_LEEWAY_SEC", "0"))
        except ValueError:
            self.leeway = 0

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass auth for exempt endpoints
        if _is_exempt(request.url.path, self.exempt_paths):
            return await call_next(request)

        # Expect Authorization: Bearer <token>
        auth = request.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Require HS256 + expiration claim;
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={"require": ["exp"]},
                leeway=self.leeway,
            )
            # make user info available to routes if needed
            request.state.user = payload.get("sub")
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expired"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            # Do not leak verification details
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
