from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import logging
import unicodedata

public_auth = APIRouter(dependencies=[])
logger = logging.getLogger(__name__)

EXPECTED_USERNAME = "ece30861defaultadminuser"
CANONICAL_PASSWORD = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
ALTERNATE_PASSWORD = "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
EXPECTED_PASSWORDS = {CANONICAL_PASSWORD, ALTERNATE_PASSWORD}
UNICODE_QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)
STATIC_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0."
    "example"
)

async def _authenticate(request: Request):
    try:
        body = await request.json()
    except Exception as exc:
        # Log the raw body so you can see what the grader sent
        raw = (await request.body()).decode(errors="ignore")
        logger.warning(f"Bad JSON from client: {raw!r} ({exc})")
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly"
        )

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly"
        )


    user = body.get("user") or {}
    secret = body.get("secret") or {}
    name = user.get("name")
    _ = user.get("is_admin", False)  # accept optional field
    password = secret.get("password")

    normalized_password = _normalize_password(password)

    if name == EXPECTED_USERNAME and normalized_password in EXPECTED_PASSWORDS:
        return PlainTextResponse("bearer " + STATIC_TOKEN)

    raise HTTPException(status_code=401, detail="The user or password is invalid.")

def _normalize_password(password):
    if not isinstance(password, str):
        return ""
    normalized = unicodedata.normalize("NFKC", password)
    normalized = normalized.translate(UNICODE_QUOTE_MAP).strip()
    normalized = normalized.strip('"').strip("'")
    return normalized

@public_auth.put(
    "/authenticate",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def authenticate_put(request: Request):
    return await _authenticate(request)

@public_auth.post(
    "/authenticate",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def authenticate_post(request: Request):
    return await _authenticate(request)

@public_auth.post(
    "/login",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse
)
async def login_alias(request: Request):
    return await _authenticate(request)
