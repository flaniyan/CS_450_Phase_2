# Schema Implementation Alternatives to Pydantic

This document outlines various approaches to implement API schemas without using Pydantic, along with their pros, cons, and example implementations.

## 1. TypedDict (Python Standard Library)

**Best for:** Type hints and IDE support without runtime validation overhead.

### Example Implementation

```python
from typing import TypedDict, List, Optional
from enum import Enum

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

class User(TypedDict):
    name: str
    is_admin: bool

class UserAuthenticationInfo(TypedDict):
    password: str

class AuthenticationRequest(TypedDict):
    user: User
    secret: UserAuthenticationInfo

class ArtifactMetadata(TypedDict):
    name: str
    id: str
    type: ArtifactType
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI()

def validate_user(data: Dict[str, Any]) -> User:
    """Manual validation for TypedDict."""
    if not isinstance(data.get("name"), str):
        raise HTTPException(status_code=400, detail="name must be a string")
    if not isinstance(data.get("is_admin"), bool):
        raise HTTPException(status_code=400, detail="is_admin must be a boolean")
    return User(name=data["name"], is_admin=data["is_admin"])

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    user_data = validate_user(body.get("user", {}))
    # ... rest of logic
    return {"token": "bearer ..."}
```

### Pros
- ✅ No external dependencies
- ✅ Type hints for IDE support
- ✅ Works with FastAPI (but no automatic validation)
- ✅ Lightweight

### Cons
- ❌ No runtime validation (must write manual validators)
- ❌ No automatic serialization
- ❌ No OpenAPI schema generation (must write manually)
- ❌ No field-level validation (patterns, min/max, etc.)

---

## 2. @dataclass (Python Standard Library)

**Best for:** Simple data structures with basic validation needs.

### Example Implementation

```python
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

@dataclass
class User:
    name: str
    is_admin: bool

@dataclass
class UserAuthenticationInfo:
    password: str

@dataclass
class AuthenticationRequest:
    user: User
    secret: UserAuthenticationInfo

@dataclass
class ArtifactMetadata:
    name: str
    id: str
    type: ArtifactType
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException
import json

app = FastAPI()

def validate_and_create_user(data: dict) -> User:
    """Manual validation and creation."""
    if not isinstance(data.get("name"), str):
        raise HTTPException(status_code=400, detail="name must be a string")
    if not isinstance(data.get("is_admin"), bool):
        raise HTTPException(status_code=400, detail="is_admin must be a boolean")
    return User(name=data["name"], is_admin=data["is_admin"])

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    user = validate_and_create_user(body.get("user", {}))
    secret = UserAuthenticationInfo(password=body.get("secret", {}).get("password", ""))
    auth_request = AuthenticationRequest(user=user, secret=secret)
    # ... rest of logic
    return {"token": "bearer ..."}

# Manual serialization
def to_dict(obj):
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, '__dict__'):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    return obj
```

### Pros
- ✅ No external dependencies
- ✅ Clean syntax with `@dataclass`
- ✅ Can add `__post_init__` for validation
- ✅ Immutable option with `frozen=True`

### Cons
- ❌ No automatic validation
- ❌ No automatic serialization (must write custom `to_dict()`)
- ❌ No OpenAPI schema generation
- ❌ Limited field-level validation

---

## 3. JSON Schema Validation (jsonschema library)

**Best for:** Strict schema validation matching OpenAPI spec exactly.

### Example Implementation

```python
from typing import Dict, Any
import jsonschema

# Define JSON Schema (matches OpenAPI spec)
USER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "is_admin": {"type": "boolean"}
    },
    "required": ["name", "is_admin"]
}

AUTHENTICATION_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "user": USER_SCHEMA,
        "secret": {
            "type": "object",
            "properties": {
                "password": {"type": "string"}
            },
            "required": ["password"]
        }
    },
    "required": ["user", "secret"]
}
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException
import jsonschema

app = FastAPI()

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data against JSON Schema."""
    try:
        jsonschema.validate(instance=data, schema=schema)
        return data
    except jsonschema.ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {e.message}"
        )

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    validated = validate_json_schema(body, AUTHENTICATION_REQUEST_SCHEMA)
    # ... rest of logic
    return {"token": "bearer ..."}
```

### Pros
- ✅ Matches OpenAPI/JSON Schema spec exactly
- ✅ Powerful validation rules
- ✅ Can generate schemas from OpenAPI spec
- ✅ Industry standard

### Cons
- ❌ Requires external dependency (`jsonschema`)
- ❌ No type hints/IDE support
- ❌ No automatic serialization
- ❌ Verbose schema definitions
- ❌ No Python object model (just dicts)

---

## 4. Marshmallow

**Best for:** Validation and serialization with more control than Pydantic.

### Example Implementation

```python
from marshmallow import Schema, fields, validate, ValidationError

class UserSchema(Schema):
    name = fields.Str(required=True)
    is_admin = fields.Bool(required=True)

class UserAuthenticationInfoSchema(Schema):
    password = fields.Str(required=True, validate=validate.Length(min=1))

class AuthenticationRequestSchema(Schema):
    user = fields.Nested(UserSchema, required=True)
    secret = fields.Nested(UserAuthenticationInfoSchema, required=True)
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException
from marshmallow import ValidationError

app = FastAPI()

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    schema = AuthenticationRequestSchema()
    try:
        validated = schema.load(body)
    except ValidationError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {err.messages}"
        )
    # validated is a dict
    # ... rest of logic
    return {"token": "bearer ..."}

# Serialization
result = {"user": {"name": "admin", "is_admin": True}}
serialized = UserSchema().dump(result)
```

### Pros
- ✅ Powerful validation
- ✅ Good serialization/deserialization
- ✅ Can generate OpenAPI schemas (with plugins)
- ✅ More control than Pydantic

### Cons
- ❌ Requires external dependency
- ❌ No type hints/IDE support
- ❌ Less integrated with FastAPI than Pydantic
- ❌ More verbose than Pydantic
- ❌ Returns dicts, not objects

---

## 5. attrs Library

**Best for:** Similar to dataclasses but with validation capabilities.

### Example Implementation

```python
import attrs
from typing import Optional
from enum import Enum

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

@attrs.define
class User:
    name: str = attrs.field(validator=attrs.validators.instance_of(str))
    is_admin: bool = attrs.field(validator=attrs.validators.instance_of(bool))

@attrs.define
class UserAuthenticationInfo:
    password: str = attrs.field(validator=attrs.validators.instance_of(str))

@attrs.define
class AuthenticationRequest:
    user: User = attrs.field()
    secret: UserAuthenticationInfo = attrs.field()
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException
import attrs

app = FastAPI()

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    try:
        user = User(
            name=body["user"]["name"],
            is_admin=body["user"]["is_admin"]
        )
        secret = UserAuthenticationInfo(password=body["secret"]["password"])
        auth_request = AuthenticationRequest(user=user, secret=secret)
    except (KeyError, TypeError, attrs.exceptions.FrozenInstanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    # ... rest of logic
    return {"token": "bearer ..."}

# Serialization
result_dict = attrs.asdict(auth_request)
```

### Pros
- ✅ Type hints support
- ✅ Validation capabilities
- ✅ Immutable option with `frozen=True`
- ✅ Clean syntax

### Cons
- ❌ Requires external dependency
- ❌ No automatic FastAPI integration
- ❌ No OpenAPI schema generation
- ❌ Manual serialization needed

---

## 6. Manual Validation with Type Hints

**Best for:** Maximum control, minimal dependencies.

### Example Implementation

```python
from typing import Dict, Any, Optional
from enum import Enum
import re

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

def validate_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Manual validation function."""
    if not isinstance(data.get("name"), str):
        raise ValueError("name must be a string")
    if not isinstance(data.get("is_admin"), bool):
        raise ValueError("is_admin must be a boolean")
    return {"name": data["name"], "is_admin": data["is_admin"]}

def validate_artifact_id(artifact_id: str) -> str:
    """Validate artifact ID pattern."""
    pattern = r'^[a-zA-Z0-9\-]+$'
    if not re.match(pattern, artifact_id):
        raise ValueError(f"Invalid artifact_id format: {artifact_id}")
    return artifact_id
```

### Usage in FastAPI

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post("/authenticate")
async def authenticate(request: Request):
    body = await request.json()
    try:
        user = validate_user(body.get("user", {}))
        secret = {"password": body.get("secret", {}).get("password", "")}
        if not secret["password"]:
            raise ValueError("password is required")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # ... rest of logic
    return {"token": "bearer ..."}
```

### Pros
- ✅ No external dependencies
- ✅ Complete control
- ✅ Can be very lightweight

### Cons
- ❌ Lots of boilerplate code
- ❌ No automatic OpenAPI generation
- ❌ Easy to miss validation cases
- ❌ No type safety at runtime

---

## 7. Hybrid Approach: TypedDict + Manual Validation

**Best for:** Balance between type safety and control.

### Example Implementation

```python
from typing import TypedDict, Dict, Any
from enum import Enum
import re

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

class User(TypedDict):
    name: str
    is_admin: bool

class ArtifactMetadata(TypedDict):
    name: str
    id: str
    type: ArtifactType

# Validation functions
def validate_user(data: Dict[str, Any]) -> User:
    """Validate and return User TypedDict."""
    if not isinstance(data.get("name"), str):
        raise ValueError("name must be a string")
    if not isinstance(data.get("is_admin"), bool):
        raise ValueError("is_admin must be a boolean")
    return User(name=data["name"], is_admin=data["is_admin"])

def validate_artifact_metadata(data: Dict[str, Any]) -> ArtifactMetadata:
    """Validate and return ArtifactMetadata TypedDict."""
    artifact_id = data.get("id", "")
    if not re.match(r'^[a-zA-Z0-9\-]+$', artifact_id):
        raise ValueError("Invalid artifact_id format")
    artifact_type = ArtifactType(data.get("type", ""))
    return ArtifactMetadata(
        name=data.get("name", ""),
        id=artifact_id,
        type=artifact_type
    )
```

---

## Comparison Table

| Approach | Dependencies | Runtime Validation | OpenAPI Gen | Type Hints | FastAPI Integration | Complexity |
|----------|-------------|-------------------|------------|------------|---------------------|------------|
| **Pydantic** | ✅ pydantic | ✅ Automatic | ✅ Automatic | ✅ Yes | ✅ Excellent | Low |
| **TypedDict** | ❌ None | ❌ Manual | ❌ Manual | ✅ Yes | ⚠️ Partial | Low |
| **@dataclass** | ❌ None | ❌ Manual | ❌ Manual | ✅ Yes | ⚠️ Partial | Low |
| **JSON Schema** | ✅ jsonschema | ✅ Automatic | ✅ Possible | ❌ No | ⚠️ Manual | Medium |
| **Marshmallow** | ✅ marshmallow | ✅ Automatic | ⚠️ With plugins | ❌ No | ⚠️ Manual | Medium |
| **attrs** | ✅ attrs | ⚠️ Basic | ❌ Manual | ✅ Yes | ⚠️ Manual | Medium |
| **Manual** | ❌ None | ❌ Manual | ❌ Manual | ⚠️ Partial | ⚠️ Manual | High |

---

## Recommendation for Your Codebase

Given that you're using **FastAPI**, here's the recommended approach:

### Option 1: Stay with Pydantic (Recommended)
- ✅ Best FastAPI integration
- ✅ Automatic OpenAPI generation
- ✅ Type safety + runtime validation
- ✅ Minimal code changes needed

### Option 2: TypedDict + Manual Validation (If removing Pydantic)
- Use TypedDict for type hints
- Write validation functions
- Manually generate OpenAPI schemas
- More code but no external dependency

### Option 3: JSON Schema (If strict spec compliance needed)
- Use `jsonschema` for validation
- Generate schemas from OpenAPI YAML
- More verbose but matches spec exactly

---

## Migration Example: Pydantic → TypedDict

Here's how you could convert a Pydantic model to TypedDict:

### Before (Pydantic)
```python
from pydantic import BaseModel, Field

class ArtifactMetadata(BaseModel):
    name: str
    id: str = Field(..., pattern=r'^[a-zA-Z0-9\-]+$')
    type: ArtifactType
```

### After (TypedDict + Manual Validation)
```python
from typing import TypedDict
import re

class ArtifactMetadata(TypedDict):
    name: str
    id: str
    type: ArtifactType

def validate_artifact_metadata(data: dict) -> ArtifactMetadata:
    """Validate and return ArtifactMetadata."""
    artifact_id = data.get("id", "")
    if not re.match(r'^[a-zA-Z0-9\-]+$', artifact_id):
        raise ValueError("Invalid artifact_id format")
    if data.get("type") not in ["model", "dataset", "code"]:
        raise ValueError("Invalid artifact type")
    return ArtifactMetadata(
        name=data["name"],
        id=artifact_id,
        type=ArtifactType(data["type"])
    )
```

---

## Conclusion

While Pydantic is the most convenient choice for FastAPI, the alternatives above provide different trade-offs:
- **TypedDict**: Best for minimal dependencies
- **@dataclass**: Best for simple structures
- **JSON Schema**: Best for strict spec compliance
- **Marshmallow**: Best for complex validation needs
- **attrs**: Best for validation with type hints
- **Manual**: Best for maximum control

Choose based on your priorities: dependencies, validation needs, OpenAPI generation, and FastAPI integration.

