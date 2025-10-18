from __future__ import annotations

from fastapi import APIRouter

from .packages import router as packages_router
from ..services.rating import router as rating_router

router = APIRouter()


@router.get("/hello")
def hello():
    return {"message": "hello world"}


router.include_router(packages_router, prefix="/packages")
router.include_router(rating_router)
