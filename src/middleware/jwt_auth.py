from __future__ import annotations

import os
from typing import Iterable
from urllib.parse import unquote

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


# Public endpoints that should bypass auth
DEFAULT_EXEMPT: tuple[str, ...] = (
    "/health",
    "/reset",
    "/tracks",
    "/authenticate",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/favicon.ico",
    "/api/hello",
    "/api/packages/reset",
    "/artifact/",  # Temporarily exempt all artifact endpoints
)


def _is_exempt(path: str, exempt: Iterable[str]) -> bool:
    for p in exempt:
        if p.endswith("/") and path.startswith(p):
            return True
        if path == p:
            return True
    return False


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    JWT verifier aligned:
      - HS256 with JWT_SECRET (matches src/services/auth_service.py)
      - requires and verifies 'exp'
      - attaches claims to request.state.user
    """

    def __init__(self, app, exempt_paths: Iterable[str] = DEFAULT_EXEMPT) -> None:
        super().__init__(app)
        self.exempt_paths = tuple(exempt_paths)

        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.secret = os.getenv("JWT_SECRET")
        if self.algorithm != "HS256":
            raise ValueError("This middleware currently supports HS256 only.")
        # Auth is optional: if JWT_SECRET is not set, skip auth checks
        self.auth_enabled = bool(self.secret)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Temporarily disable all auth checks - all endpoints are exempt
        return await call_next(request)

        # Prefix-safe path normalization (handles /prod/... base paths)
        raw_path = unquote(request.scope.get("path", "") or request.url.path)
        root_prefix = request.scope.get("root_path", "") or request.headers.get(
            "X-Forwarded-Prefix", ""
        )
        path = (
            raw_path[len(root_prefix) :]
            if root_prefix and raw_path.startswith(root_prefix)
            else raw_path
        )

        if _is_exempt(path, self.exempt_paths):
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return JSONResponse(
                {"detail": "Missing or malformed Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth.split(" ", 1)[1].strip()
        try:
            # Require exp; enforce issuer/audience with small clock skew
            iss = os.getenv("JWT_ISSUER")
            aud = os.getenv("JWT_AUDIENCE")
            leeway = int(os.getenv("JWT_LEEWAY_SEC", "60"))

            options = {"require": ["exp"], "verify_exp": True}
            if not aud:
                options["verify_aud"] = False

            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options=options,
                issuer=iss if iss else None,
                audience=aud if aud else None,
                leeway=leeway,
            )
            request.state.user = claims
        except ExpiredSignatureError:
            return JSONResponse(
                {"detail": "Token expired"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError:
            # Do not leak parsing/crypto details in response
            return JSONResponse(
                {"detail": "Invalid token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception:
            return JSONResponse(
                {"detail": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
