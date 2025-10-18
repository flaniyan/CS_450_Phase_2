from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


async def error_handler(request: Request, exc: Exception):
    status = getattr(exc, "status_code", getattr(exc, "status", 500)) or 500
    return JSONResponse(
        status_code=int(status),
        content={
            "error": exc.__class__.__name__,
            "message": str(exc) or "Something went wrong",
        },
    )
