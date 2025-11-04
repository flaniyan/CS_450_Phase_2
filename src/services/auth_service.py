from fastapi import FastAPI, HTTPException, Depends, status
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

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "10"))
JWT_MAX_USES = int(os.getenv("JWT_MAX_USES", "1000"))

USERS_TABLE = os.getenv("DDB_TABLE_USERS", "users")
TOKENS_TABLE = os.getenv("DDB_TABLE_TOKENS", "tokens")

app = FastAPI(title="Authentication Service", version="1.0.0")
security = HTTPBearer()


# Pydantic models
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


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """Create JWT token"""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "roles": user_data["roles"],
        "groups": user_data["groups"],
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),  # JWT ID for tracking
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logging.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logging.warning("Invalid JWT token")
        return None


def store_token(token_id: str, user_data: Dict[str, Any], token: str) -> None:
    """Store token in DynamoDB with TTL"""
    try:
        table = dynamodb.Table(TOKENS_TABLE)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=JWT_EXPIRATION_HOURS)

        item = {
            "token_id": token_id,
            "user_id": user_data["user_id"],
            "username": user_data["username"],
            "roles": user_data["roles"],
            "groups": user_data["groups"],
            "token": token,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "remaining_uses": JWT_MAX_USES,
            "exp_ts": int(expires_at.timestamp()),  # TTL attribute
        }

        table.put_item(Item=item)
    except Exception as e:
        logging.error(f"Error storing token: {e}")
        raise HTTPException(status_code=500, detail="Error storing token")


def consume_token_use(token_id: str) -> Optional[Dict[str, Any]]:
    """Consume one token use and return updated token info"""
    try:
        table = dynamodb.Table(TOKENS_TABLE)

        # Get current token info
        response = table.get_item(Key={"token_id": token_id})
        if "Item" not in response:
            return None

        token_info = response["Item"]

        # Check if token has uses remaining
        remaining_uses = token_info.get("remaining_uses", 0)
        if remaining_uses <= 0:
            return None

        # Decrement uses
        new_uses = remaining_uses - 1
        if new_uses <= 0:
            # Delete token when uses exhausted
            table.delete_item(Key={"token_id": token_id})
        else:
            # Update remaining uses
            table.update_item(
                Key={"token_id": token_id},
                UpdateExpression="SET remaining_uses = :uses",
                ExpressionAttributeValues={":uses": new_uses},
            )
            token_info["remaining_uses"] = new_uses

        return token_info

    except Exception as e:
        logging.error(f"Error consuming token use: {e}")
        return None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    try:
        table = dynamodb.Table(USERS_TABLE)

        # Query by username (assuming username is a GSI)
        response = table.query(
            IndexName="username-index",
            KeyConditionExpression="username = :username",
            ExpressionAttributeValues={":username": username},
        )

        items = response.get("Items", [])
        return items[0] if items else None

    except Exception as e:
        logging.error(f"Error getting user: {e}")
        return None


def create_user(user_data: UserRegistration) -> Dict[str, Any]:
    """Create new user"""
    try:
        table = dynamodb.Table(USERS_TABLE)
        user_id = secrets.token_urlsafe(16)

        # Check if user already exists
        existing_user = get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(status_code=409, detail="Username already exists")

        # Create user
        user_item = {
            "user_id": user_id,
            "username": user_data.username,
            "password_hash": hash_password(user_data.password),
            "roles": user_data.roles,
            "groups": user_data.groups,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        table.put_item(Item=user_item)
        return user_item

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Error creating user")


@app.post("/register", response_model=UserInfo)
async def register_user(user_data: UserRegistration):
    """Register a new user (admin only)"""
    # In a real implementation, you'd check if the current user has admin role
    # For now, we'll allow registration

    user = create_user(user_data)
    return UserInfo(
        user_id=user["user_id"],
        username=user["username"],
        roles=user["roles"],
        groups=user["groups"],
    )


@app.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    """Login user and return JWT token"""
    # Get user
    user = get_user_by_username(login_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create token
    token = create_jwt_token(user)
    token_id = secrets.token_urlsafe(16)

    # Store token
    store_token(token_id, user, token)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)

    return TokenResponse(
        token=token, expires_at=expires_at.isoformat(), remaining_uses=JWT_MAX_USES
    )


@app.get("/me", response_model=TokenInfo)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get current user info and consume token use"""
    token = credentials.credentials

    # Verify token
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Consume token use
    token_info = consume_token_use(payload["jti"])
    if not token_info:
        raise HTTPException(status_code=401, detail="Token expired or exhausted")

    return TokenInfo(
        token_id=token_info["token_id"],
        user_id=token_info["user_id"],
        username=token_info["username"],
        roles=token_info["roles"],
        groups=token_info["groups"],
        expires_at=token_info["expires_at"],
        remaining_uses=token_info["remaining_uses"],
    )


@app.post("/logout")
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user by revoking token"""
    token = credentials.credentials

    # Verify token
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Delete token
    try:
        table = dynamodb.Table(TOKENS_TABLE)
        table.delete_item(Key={"token_id": payload["jti"]})
        return {"message": "Logged out successfully"}
    except Exception as e:
        logging.error(f"Error logging out: {e}")
        raise HTTPException(status_code=500, detail="Error logging out")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "3002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
