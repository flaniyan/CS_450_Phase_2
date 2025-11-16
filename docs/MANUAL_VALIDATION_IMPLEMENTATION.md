# Implementing Schemas Without Pydantic - Manual Validation Guide

Yes, you can implement all schemas without Pydantic using your old code approach, but you'll need to add comprehensive manual validation functions. This guide shows what's required.

## Overview

**Current (Pydantic):** Automatic validation, ~50 lines of schema definitions
**Manual Approach:** Manual validation functions, ~500+ lines of validation code

## Required Validation Functions

### 1. Type Validation Functions

```python
# validation.py
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from enum import Enum

class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"

class HealthStatus(str, Enum):
    ok = "ok"
    degraded = "degraded"
    critical = "critical"
    unknown = "unknown"

class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DOWNLOAD = "DOWNLOAD"
    RATE = "RATE"
    AUDIT = "AUDIT"

class IssueSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"

def validate_artifact_id(artifact_id: str) -> str:
    """Validate ArtifactID pattern: ^[a-zA-Z0-9\-]+$"""
    if not isinstance(artifact_id, str):
        raise ValueError("artifact_id must be a string")
    pattern = r'^[a-zA-Z0-9\-]+$'
    if not re.match(pattern, artifact_id):
        raise ValueError(f"Invalid artifact_id format: {artifact_id}. Must match pattern: {pattern}")
    return artifact_id

def validate_url(url: str) -> str:
    """Validate URL format (HttpUrl equivalent)"""
    if not isinstance(url, str):
        raise ValueError("url must be a string")
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValueError(f"Invalid URL format: {url}")
        return url
    except Exception as e:
        raise ValueError(f"Invalid URL: {url} - {str(e)}")

def validate_artifact_type(artifact_type: str) -> ArtifactType:
    """Validate ArtifactType enum"""
    if not isinstance(artifact_type, str):
        raise ValueError("artifact_type must be a string")
    try:
        return ArtifactType(artifact_type)
    except ValueError:
        raise ValueError(f"Invalid artifact_type: {artifact_type}. Must be one of: model, dataset, code")

def validate_health_status(status: str) -> HealthStatus:
    """Validate HealthStatus enum"""
    if not isinstance(status, str):
        raise ValueError("status must be a string")
    try:
        return HealthStatus(status)
    except ValueError:
        raise ValueError(f"Invalid status: {status}. Must be one of: ok, degraded, critical, unknown")

def validate_boolean(value: Any, field_name: str) -> bool:
    """Validate boolean type"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
    raise ValueError(f"{field_name} must be a boolean, got: {type(value).__name__}")

def validate_string(value: Any, field_name: str, required: bool = True) -> str:
    """Validate string type"""
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got: {type(value).__name__}")
    return value

def validate_integer(value: Any, field_name: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """Validate integer type with optional min/max"""
    if not isinstance(value, int):
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        else:
            raise ValueError(f"{field_name} must be an integer, got: {type(value).__name__}")
    if min_val is not None and value < min_val:
        raise ValueError(f"{field_name} must be >= {min_val}, got: {value}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{field_name} must be <= {max_val}, got: {value}")
    return value

def validate_float(value: Any, field_name: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
    """Validate float type with optional min/max"""
    if not isinstance(value, (int, float)):
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise ValueError(f"{field_name} must be a number, got: {type(value).__name__}")
        else:
            raise ValueError(f"{field_name} must be a number, got: {type(value).__name__}")
    value = float(value)
    if min_val is not None and value < min_val:
        raise ValueError(f"{field_name} must be >= {min_val}, got: {value}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{field_name} must be <= {max_val}, got: {value}")
    return value

def validate_list(value: Any, field_name: str, item_validator=None) -> List:
    """Validate list type with optional item validation"""
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list, got: {type(value).__name__}")
    if item_validator:
        return [item_validator(item, f"{field_name}[{i}]") for i, item in enumerate(value)]
    return value

def validate_datetime(value: Any, field_name: str) -> str:
    """Validate ISO 8601 datetime string"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string (ISO 8601 datetime), got: {type(value).__name__}")
    try:
        from datetime import datetime
        # Try parsing ISO format
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        raise ValueError(f"{field_name} must be a valid ISO 8601 datetime string, got: {value}")
```

### 2. Schema Validation Functions

```python
# schema_validators.py
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from .validation import (
    validate_string, validate_boolean, validate_url, validate_artifact_id,
    validate_artifact_type, validate_list, validate_integer, validate_float,
    validate_datetime, ArtifactType, HealthStatus, AuditAction, IssueSeverity
)

def validate_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate User schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the User or it is formed improperly"
        )
    
    name = validate_string(data.get("name"), "name", required=True)
    is_admin = validate_boolean(data.get("is_admin"), "is_admin")
    
    return {"name": name, "is_admin": is_admin}

def validate_user_authentication_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate UserAuthenticationInfo schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the UserAuthenticationInfo or it is formed improperly"
        )
    
    password = validate_string(data.get("password"), "password", required=True)
    
    return {"password": password}

def validate_authentication_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate AuthenticationRequest schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly"
        )
    
    if "user" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly"
        )
    
    if "secret" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the AuthenticationRequest or it is formed improperly"
        )
    
    user = validate_user(data.get("user", {}))
    secret = validate_user_authentication_info(data.get("secret", {}))
    
    return {"user": user, "secret": secret}

def validate_artifact_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ArtifactMetadata schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactMetadata or it is formed improperly"
        )
    
    name = validate_string(data.get("name"), "name", required=True)
    artifact_id = validate_artifact_id(data.get("id"))
    artifact_type = validate_artifact_type(data.get("type"))
    
    return {
        "name": name,
        "id": artifact_id,
        "type": artifact_type.value
    }

def validate_artifact_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ArtifactData schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactData or it is formed improperly (must include a single url)"
        )
    
    if "url" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactData or it is formed improperly (must include a single url)"
        )
    
    url = validate_url(data.get("url"))
    download_url = None
    if "download_url" in data and data.get("download_url"):
        download_url = validate_url(data.get("download_url"))
    
    result = {"url": url}
    if download_url:
        result["download_url"] = download_url
    
    return result

def validate_artifact(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Artifact schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the Artifact or it is formed improperly"
        )
    
    if "metadata" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the Artifact or it is formed improperly"
        )
    
    if "data" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the Artifact or it is formed improperly"
        )
    
    metadata = validate_artifact_metadata(data.get("metadata", {}))
    artifact_data = validate_artifact_data(data.get("data", {}))
    
    return {"metadata": metadata, "data": artifact_data}

def validate_artifact_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ArtifactQuery schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactQuery or it is formed improperly"
        )
    
    if "name" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactQuery or it is formed improperly"
        )
    
    name = validate_string(data.get("name"), "name", required=True)
    
    types = None
    if "types" in data and data.get("types"):
        types_list = validate_list(data.get("types"), "types")
        types = [validate_artifact_type(t).value for t in types_list]
    
    result = {"name": name}
    if types:
        result["types"] = types
    
    return result

def validate_artifact_regex(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ArtifactRegEx schema"""
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactRegEx or it is formed improperly, or is invalid"
        )
    
    if "regex" not in data:
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the ArtifactRegEx or it is formed improperly, or is invalid"
        )
    
    regex = validate_string(data.get("regex"), "regex", required=True)
    
    # Validate regex pattern syntax
    try:
        import re
        re.compile(regex)
    except re.error as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the ArtifactRegEx or it is formed improperly, or is invalid: {str(e)}"
        )
    
    return {"regex": regex}

# ... (similar functions for all other schemas)
```

### 3. Updated Endpoint Example (Without Pydantic)

```python
# index.py (old approach)
from fastapi import FastAPI, Request, HTTPException
from .schema_validators import (
    validate_authentication_request,
    validate_artifact_query,
    validate_artifact_data,
    validate_artifact_metadata,
    validate_artifact
)

@app.post("/artifacts")
async def list_artifacts(request: Request, offset: Optional[str] = None):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_query or it is formed improperly, or is invalid: {str(e)}"
        )
    
    if not isinstance(body, list):
        raise HTTPException(
            status_code=400,
            detail="There is missing field(s) in the artifact_query or it is formed improperly, or is invalid"
        )
    
    # Validate each query
    validated_queries = []
    for query_data in body:
        try:
            validated_query = validate_artifact_query(query_data)
            validated_queries.append(validated_query)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"There is missing field(s) in the artifact_query or it is formed improperly, or is invalid: {str(e)}"
            )
    
    # Process queries (same logic as before)
    results = []
    for query in validated_queries:
        name = query["name"]
        types_filter = query.get("types")  # List of strings like ["model", "dataset"]
        
        # ... rest of query logic ...
    
    # Return results as dictionaries (not Pydantic models)
    return results

@app.post("/artifact/{artifact_type}")
async def create_artifact_by_type(artifact_type: str, request: Request):
    if not verify_auth_token(request):
        raise HTTPException(
            status_code=403,
            detail="Authentication failed due to invalid or missing AuthenticationToken",
        )
    
    # Validate artifact_type enum
    try:
        artifact_type_enum = validate_artifact_type(artifact_type)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid: {str(e)}"
        )
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_data or it is formed improperly (must include a single url): {str(e)}"
        )
    
    # Validate ArtifactData
    try:
        validated_data = validate_artifact_data(body)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"There is missing field(s) in the artifact_data or it is formed improperly (must include a single url): {str(e)}"
        )
    
    url = validated_data["url"]
    
    # ... rest of ingestion logic ...
    
    # Return response as dictionary
    return {
        "metadata": {
            "name": model_id,
            "id": artifact_id,
            "type": artifact_type_enum.value
        },
        "data": {
            "url": url
        }
    }
```

## Comparison: Pydantic vs Manual

| Aspect | Pydantic | Manual Validation |
|--------|----------|-------------------|
| **Code Lines** | ~50 (schema definitions) | ~500+ (validation functions) |
| **Type Safety** | ✅ Automatic | ⚠️ Manual checks needed |
| **Pattern Validation** | ✅ Automatic | ⚠️ Manual regex checks |
| **URL Validation** | ✅ Automatic | ⚠️ Manual URL parsing |
| **Nested Validation** | ✅ Automatic | ⚠️ Manual recursive validation |
| **Error Messages** | ✅ Detailed | ⚠️ Must write custom messages |
| **OpenAPI Generation** | ✅ Automatic | ❌ Must write manually |
| **Maintenance** | ✅ Low | ⚠️ High (must update validators) |
| **Testing** | ✅ Less needed | ⚠️ Must test all validators |

## What You Need to Add

### 1. Validation Module (~300 lines)
- Type validation functions
- Pattern validation functions
- Enum validation functions
- URL validation functions

### 2. Schema Validators (~200 lines)
- One function per schema
- Nested object validation
- Required field checking
- Type coercion where needed

### 3. Endpoint Updates (~100+ lines)
- Replace Pydantic models with `Request` + manual parsing
- Add validation calls in each endpoint
- Convert validated dicts back to response format
- Handle validation errors

### 4. OpenAPI Schema Generation (~200+ lines)
- Manually define OpenAPI schemas
- Keep in sync with validation logic
- Update when schemas change

## Recommendation

**Keep Pydantic** because:
1. ✅ **Less code** - 50 lines vs 500+ lines
2. ✅ **Automatic OpenAPI** - Always in sync
3. ✅ **Type safety** - Catches errors at development time
4. ✅ **Maintainability** - Changes to schemas automatically propagate
5. ✅ **Community standard** - Well-tested and documented

**Use Manual Validation** only if:
- You cannot use Pydantic (dependency restrictions)
- You need very custom validation logic
- You want complete control over validation flow

## Hybrid Approach (Best of Both)

You can keep Pydantic but add manual validation where needed:

```python
@app.post("/artifacts")
async def list_artifacts(queries: List[ArtifactQuery], request: Request):
    # Pydantic handles validation automatically
    # But you can add custom validation if needed
    for query in queries:
        if query.name == "*" and not query.types:
            # Custom business logic validation
            pass
    # ... rest of logic
```

This gives you:
- ✅ Automatic validation from Pydantic
- ✅ Custom validation where needed
- ✅ Best of both worlds

## Conclusion

Yes, you can implement all schemas without Pydantic, but it requires:
- **~500+ lines** of validation code
- **Manual OpenAPI** schema definitions
- **More testing** and maintenance
- **Higher risk** of bugs

The current Pydantic approach is more maintainable and less error-prone.

