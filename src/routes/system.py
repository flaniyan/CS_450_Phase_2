from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# In-memory database shared with artifacts routes
_INMEM_DB = {"artifacts": []}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/tracks")
def tracks():
    return {"tracks": ["access-control", "reproducibility", "reviewedness", "security"]}


@router.post("/reset")
def reset():
    _INMEM_DB["artifacts"].clear()
    return {"status": "ok"}

