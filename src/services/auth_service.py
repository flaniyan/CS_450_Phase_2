# src/services/auth_service.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import boto3
import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import os
import logging

logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "10"))
JWT_MAX_USES = int(os.getenv("JWT_MAX_USES", "1000"))

USERS_TABLE = os.getenv("DDB_TABLE_USERS", "users")
TOKENS_TABLE = os.getenv("DDB_TABLE_TOKENS", "tokens")

DEFAULT_ADMIN_USERNAME = "ece30861defaultadminuser"
DEFAULT_ADMIN_PASSWORD_PRIMARY = (
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
)
DEFAULT_ADMIN_PASSWORD_ALTERNATE = (
    "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
)
DEFAULT_ADMIN_PASSWORDS = {
    DEFAULT_ADMIN_PASSWORD_PRIMARY,
    DEFAULT_ADMIN_PASSWORD_ALTERNATE,
}

security = HTTPBearer()


# --------- Models ----------
class UserRegistration(BaseModel):
    username: str
    password: str
    roles: List[str] = []
    groups: List[str] = []


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    expires_at: str
    remaining_uses: int


class UserInfo(BaseModel):
    user_id: str
    username: str
    roles: List[str]
    groups: List[str]


class TokenInfo(BaseModel):
    token_id: str
    user_id: str
    username: str
    roles: List[str]
    groups: List[str]
    expires_at: str
    remaining_uses: int


# --------- Helpers ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_jwt_token(user_data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    jti = secrets.token_urlsafe(16)
    payload = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "roles": user_data.get("roles", []),
        "groups": user_data.get("groups", []),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token, "jti": jti, "expires_at": expires_at}


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT")
        return None


def store_token(
    token_id: str, user_data: Dict[str, Any], token: str, expires_at: datetime
) -> None:
    # token_id MUST equal JWT jti so /auth/me can consume it
    table = dynamodb.Table(TOKENS_TABLE)
    item = {
        "token_id": token_id,
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "roles": user_data.get("roles", []),
        "groups": user_data.get("groups", []),
        "token": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "remaining_uses": JWT_MAX_USES,
        "exp_ts": int(expires_at.timestamp()),  # for DynamoDB TTL
    }
    table.put_item(Item=item)


def consume_token_use(token_id: str) -> Optional[Dict[str, Any]]:
    table = dynamodb.Table(TOKENS_TABLE)
    resp = table.get_item(Key={"token_id": token_id})
    if "Item" not in resp:
        return None
    item = resp["Item"]
    remaining = int(item.get("remaining_uses", 0))
    if remaining <= 0:
        table.delete_item(Key={"token_id": token_id})
        return None
    remaining -= 1
    if remaining <= 0:
        table.delete_item(Key={"token_id": token_id})
        item["remaining_uses"] = 0
    else:
        table.update_item(
            Key={"token_id": token_id},
            UpdateExpression="SET remaining_uses = :r",
            ExpressionAttributeValues={":r": remaining},
        )
        item["remaining_uses"] = remaining
    return item


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    try:
        table = dynamodb.Table(USERS_TABLE)
        # Try to query using username-index if it exists
        try:
            resp = table.query(
                IndexName="username-index",
                KeyConditionExpression="username = :u",
                ExpressionAttributeValues={":u": username},
            )
            items = resp.get("Items", [])
            if items:
                return items[0]
        except Exception as index_error:
            # If index doesn't exist, fall back to scan (less efficient but works)
            logger.debug(f"username-index not available, using scan: {index_error}")
            resp = table.scan(
                FilterExpression="username = :u",
                ExpressionAttributeValues={":u": username},
            )
            items = resp.get("Items", [])
            if items:
                return items[0]
        return None
    except Exception as e:
        logger.error(f"get_user_by_username error: {e}")
        return None


def create_user(user_data: UserRegistration) -> Dict[str, Any]:
    existing = get_user_by_username(user_data.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    user_id = secrets.token_urlsafe(16)
    item = {
        "user_id": user_id,
        "username": user_data.username,
        "password_hash": hash_password(user_data.password),
        "roles": user_data.roles,
        "groups": user_data.groups,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    dynamodb.Table(USERS_TABLE).put_item(Item=item)
    return item


def ensure_default_admin() -> bool:
    """
    Ensure the default admin account exists with the expected credentials.
    Returns True if the account exists or was created/updated, False otherwise.
    """
    try:
        admin = get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if admin:
            roles = set(admin.get("roles", []))
            needs_update = False
            update_parts = []
            expr_attr_vals = {}
            expr_attr_names = {}

            if "admin" not in roles:
                roles.add("admin")
                needs_update = True
                update_parts.append("#roles = :roles")
                expr_attr_vals[":roles"] = list(roles)
                expr_attr_names["#roles"] = "roles"

            if not admin.get("password_hash"):
                needs_update = True
                update_parts.append("#password_hash = :password_hash")
                expr_attr_vals[":password_hash"] = hash_password(
                    DEFAULT_ADMIN_PASSWORD_PRIMARY
                )
                expr_attr_names["#password_hash"] = "password_hash"

            update_parts.append("#updated_at = :updated_at")
            expr_attr_vals[":updated_at"] = datetime.now(timezone.utc).isoformat()
            expr_attr_names["#updated_at"] = "updated_at"

            if needs_update:
                table = dynamodb.Table(USERS_TABLE)
                kwargs = {
                    "Key": {"user_id": admin["user_id"]},
                    "UpdateExpression": "SET " + ", ".join(update_parts),
                    "ExpressionAttributeValues": expr_attr_vals,
                    "ExpressionAttributeNames": expr_attr_names,
                }
                table.update_item(**kwargs)
                logger.info("Default admin account refreshed.")
            return True

        # Create the account if it does not exist
        create_user(
            UserRegistration(
                username=DEFAULT_ADMIN_USERNAME,
                password=DEFAULT_ADMIN_PASSWORD_PRIMARY,
                roles=["admin"],
            )
        )
        logger.info("Default admin account created.")
        return True
    except HTTPException as http_exc:
        if http_exc.status_code == 409:
            logger.info("Default admin already exists.")
            return True
        logger.warning("Failed to ensure default admin: %s", http_exc.detail)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to ensure default admin: %s", exc, exc_info=True)
    return False


def purge_tokens() -> bool:
    """
    Remove all issued tokens. Used during system reset to invalidate sessions.
    """
    try:
        table = dynamodb.Table(TOKENS_TABLE)
        scan_kwargs = {"ProjectionExpression": "token_id"}
        response = table.scan(**scan_kwargs)
        while True:
            for item in response.get("Items", []):
                table.delete_item(Key={"token_id": item["token_id"]})
            if "LastEvaluatedKey" not in response:
                break
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], **scan_kwargs
            )
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to purge tokens: %s", exc, exc_info=True)
        return False


# --------- Routers ----------
auth_public = APIRouter(prefix="/auth")  # public namespaced routes
auth_private = APIRouter(prefix="/auth", dependencies=[Depends(security)])  # private


@auth_public.post("/register", response_model=UserInfo)
async def register_user(user_data: UserRegistration):
    user = create_user(user_data)
    return UserInfo(
        user_id=user["user_id"],
        username=user["username"],
        roles=user.get("roles", []),
        groups=user.get("groups", []),
    )


@auth_public.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    user = get_user_by_username(login_data.username)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token_obj = create_jwt_token(user)  # {token, jti, expires_at}
    store_token(token_obj["jti"], user, token_obj["token"], token_obj["expires_at"])
    return TokenResponse(
        token=token_obj["token"],
        expires_at=token_obj["expires_at"].isoformat(),
        remaining_uses=JWT_MAX_USES,
    )


@auth_private.get("/me", response_model=TokenInfo)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = verify_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    item = consume_token_use(payload["jti"])
    if not item:
        raise HTTPException(status_code=401, detail="Token expired or exhausted")
    return TokenInfo(
        token_id=payload["jti"],
        user_id=item["user_id"],
        username=item["username"],
        roles=item.get("roles", []),
        groups=item.get("groups", []),
        expires_at=item["expires_at"],
        remaining_uses=item.get("remaining_uses", 0),
    )


@auth_private.post("/logout")
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    dynamodb.Table(TOKENS_TABLE).delete_item(Key={"token_id": payload["jti"]})
    return {"message": "Logged out successfully"}
