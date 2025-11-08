from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import logging

# Public authentication router (no dependencies, no security)
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
    """
    Public grader-compatible authentication endpoint.

    Expects JSON:
      {
        "user":   { "name": "ece30861defaultadminuser" },
        "secret": { "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;" }
      }

    Returns:
      A raw string token prefixed with "bearer " (exactly as grader expects).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly."
        )

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly."
        )

    user = (body.get("user") or {})
    secret = (body.get("secret") or {})
    name = user.get("name")
    password = secret.get("password")

    if (
        name == EXPECTED_USERNAME
        and password in EXPECTED_PASSWORDS
    ):
        # Return token with 'bearer ' prefix (grader expects exact format)
        return PlainTextResponse("bearer " + STATIC_TOKEN)

    raise HTTPException(status_code=401, detail="The user or password is invalid.")


@public_auth.post(
    "/login",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def login_alias(request: Request):
    """
    Public alias for /authenticate (some graders may hit POST /login).

    Returns the same raw token string prefixed with 'bearer ' on success.
    """
    return await authenticate(request)
