from __future__ import annotations

import os
import time

import jwt
from fastapi import APIRouter, Body
from pydantic import BaseModel

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")


class LoginIn(BaseModel):
    username: str
    password: str


@router.put("/authenticate")
def authenticate(data: LoginIn = Body(...)):
    payload = {"sub": data.username, "is_admin": True, "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return f"bearer {token}"

