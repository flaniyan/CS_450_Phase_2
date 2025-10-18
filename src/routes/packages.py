from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_packages():
    # Minimal placeholder list endpoint (so file is non-empty/useful)
    return {"packages": []}