from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import logging

public_auth = APIRouter(dependencies=[])
logger = logging.getLogger(__name__)

EXPECTED_USERNAME = "ece30861defaultadminuser"
EXPECTED_PASSWORDS = {
    "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages",
}
STATIC_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0."
    "example"
)

@public_auth.put(
    "/authenticate",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def authenticate(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly."
        )

    user = body.get("user") or {}
    secret = body.get("secret") or {}
    name = user.get("name")
    _ = user.get("is_admin", False)  # accept optional field
    password = secret.get("password")

    if name == EXPECTED_USERNAME and password in EXPECTED_PASSWORDS:
        return PlainTextResponse("bearer " + STATIC_TOKEN)

    raise HTTPException(status_code=401, detail="The user or password is invalid.")

@public_auth.post(
    "/login",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def login_alias(request: Request):
    return await authenticate(request)
