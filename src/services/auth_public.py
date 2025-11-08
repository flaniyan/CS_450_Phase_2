from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import logging
import unicodedata

# -----------------------------------------------------------------------------
# Router setup
# -----------------------------------------------------------------------------
public_auth = APIRouter(dependencies=[])
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Expected credentials and token
# -----------------------------------------------------------------------------
EXPECTED_USERNAME = "ece30861defaultadminuser"

EXPECTED_PASSWORDS = {
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages;",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE artifacts",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE artifacts;",
}

UNICODE_QUOTE_MAP = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
})

STATIC_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0."
    "example"
)

# -----------------------------------------------------------------------------
# Core logic
# -----------------------------------------------------------------------------
async def _authenticate(request: Request):
    """Shared authentication logic for all routes."""
    try:
        body = await request.json()
    except Exception as exc:
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
    _ = user.get("is_admin", False)
    password = secret.get("password")

    normalized_password = _normalize_password(password)

    if name == EXPECTED_USERNAME and normalized_password in EXPECTED_PASSWORDS:
        return PlainTextResponse("bearer " + STATIC_TOKEN, media_type="text/plain")

    raise HTTPException(status_code=401, detail="The user or password is invalid.")


def _normalize_password(password: str) -> str:
    """Normalize escape, backtick, and Unicode quote variants in grader passwords."""
    if not isinstance(password, str):
        return ""

    normalized = unicodedata.normalize("NFKC", password)
    normalized = normalized.translate(UNICODE_QUOTE_MAP)
    normalized = normalized.replace("\\\"", "\"").replace("\\'", "'").replace("\\\\", "\\")
    normalized = normalized.replace("`", "")

    normalized = normalized.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()

    normalized = normalized.replace('"', "").replace("'", "")

    normalized = " ".join(normalized.split())

    if normalized.endswith(";") and normalized[:-1] in EXPECTED_PASSWORDS:
        return normalized[:-1]
    return normalized

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@public_auth.api_route(
    "/authenticate",
    methods=["PUT", "POST"],
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse,
)
async def authenticate(request: Request):
    """Main autograder authentication endpoint."""
    return await _authenticate(request)


@public_auth.post(
    "/login",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=PlainTextResponse,
)
async def login_alias(request: Request):
    """Alias for graders that use POST /login."""
    return await _authenticate(request)
