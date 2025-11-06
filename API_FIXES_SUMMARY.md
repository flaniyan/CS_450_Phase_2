# API Fixes Summary

## All Changes Applied Successfully ✅

### A) App Entry + Middleware Wiring ✅

**File:** `src/middleware/jwt_auth.py`

- ✅ Added prefix-safe path normalization at the top of `dispatch()` method
- ✅ Handles `/prod/...` base paths via `root_path` scope and `X-Forwarded-Prefix` header
- ✅ Updated `DEFAULT_EXEMPT` to include: `/health`, `/reset`, `/tracks`, `/authenticate`

**File:** `src/entrypoint.py`

- ✅ Already correctly wraps `src.index:app` and adds `JWTAuthMiddleware`

### B) Public Routes ✅

**File:** `src/routes/system.py` (NEW)

- ✅ `GET /health` → Returns `{"status":"ok"}`
- ✅ `POST /reset` → Returns `{"status":"ok"}` and clears `_INMEM_DB["artifacts"]`
- ✅ `GET /tracks` → Returns `{"tracks": ["access-control", "reproducibility", "reviewedness", "security"]}`

**File:** `src/routes/auth.py` (NEW)

- ✅ `PUT /authenticate` → Returns **plain string** `"bearer <token>"` (not JSON)
- ✅ Uses HS256 algorithm with `exp` claim
- ✅ Reads `JWT_SECRET` from environment

**File:** `src/index.py`

- ✅ Removed old `/health` endpoint (now in `system.py`)
- ✅ Removed old `/authenticate` endpoint (now in `auth.py`)
- ✅ Removed old `/reset` endpoint (now in `system.py`)

### C) Artifact API Shapes ✅

**File:** `src/routes/artifacts.py` (NEW)

- ✅ Defined `Artifact` Pydantic model with: `id`, `name`, `type`, `version`, `description`, `created_at`
- ✅ `PUT /api/ingest` accepts single `Artifact` or list, stores as dicts (not strings)
- ✅ `GET /api/artifacts` returns `[]` if empty (never `None`)
- ✅ `GET /api/artifacts/by-name/{name}` returns 404 if not found
- ✅ `GET /api/artifacts/{artifact_id}` returns 404 if not found
- ✅ Uses shared `_INMEM_DB` from `system.py`

### D) Root Path Handling ✅

**Middleware Fix:**

- ✅ Prefix-safe path normalization handles any base path (e.g., `/prod`)
- ✅ Checks `request.scope.get("root_path")` and `X-Forwarded-Prefix` header

**Infrastructure:**

- ✅ API Gateway stage is `prod` (confirmed in `infra/modules/api-gateway/main.tf`)
- ✅ No `--root-path` flag needed in Dockerfile (code handles it)

### E) Router Inclusion ✅

**File:** `src/index.py`

- ✅ Added imports: `from .routes import system, auth, artifacts`
- ✅ Wired up routers:
  ```python
  app.include_router(system.router)
  app.include_router(auth.router)
  app.include_router(artifacts.router)
  ```

### F) JWT Secret and Algorithm ✅

**File:** `src/routes/auth.py`

- ✅ Uses `jwt.encode()` with `algorithm="HS256"`
- ✅ Includes `exp` claim: `int(time.time()) + 3600`
- ✅ Reads `JWT_SECRET` from environment (defaults to `"dev-secret"` for local dev)
- ✅ Returns plain string: `f"bearer {token}"`

**File:** `src/middleware/jwt_auth.py`

- ✅ Already configured for HS256
- ✅ Requires `exp` claim: `options = {"require": ["exp"], "verify_exp": True}`
- ✅ Reads `JWT_SECRET` from environment

### G) Middleware Whitelist ✅

**File:** `src/middleware/jwt_auth.py`

- ✅ `DEFAULT_EXEMPT` includes all required paths:
  - `/health`
  - `/reset`
  - `/tracks`
  - `/authenticate`
  - `/docs`, `/redoc`, `/openapi.json`
  - `/static/`, `/favicon.ico`
  - `/api/hello`, `/api/packages/reset`
- ✅ Prefix-safe matcher handles `/prod/health`, `/prod/tracks`, etc.

---

## Testing Checklist

### Sanity Tests (Run these after deployment):

```bash
# Health check
curl -sS "$BASE/health"
# Expected: {"status":"ok"}

# Reset
curl -sS -X POST "$BASE/reset"
# Expected: {"status":"ok"}

# Tracks
curl -sS "$BASE/tracks"
# Expected: {"tracks": ["access-control", "reproducibility", "reviewedness", "security"]}

# Authenticate (should return plain string)
curl -sS -X PUT "$BASE/authenticate" \
  -H "Content-Type: application/json" \
  -d '{"username":"ece30861defaultadminuser","password":"x"}'
# Expected: "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Artifacts list (should return [] not null)
curl -sS "$BASE/api/artifacts"
# Expected: []

# Ingest
curl -sS -X PUT "$BASE/api/ingest" \
  -H "Content-Type: application/json" \
  -d '{"id":"test-1","name":"test","type":"model","version":"1.0.0"}'
# Expected: {"ingested": 1}
```

---

## Files Created/Modified

### Created:

- `src/routes/system.py` - System routes (health, reset, tracks)
- `src/routes/auth.py` - Authentication endpoint
- `src/routes/artifacts.py` - Artifact API with Pydantic models

### Modified:

- `src/middleware/jwt_auth.py` - Added prefix-safe path normalization, updated DEFAULT_EXEMPT
- `src/index.py` - Wired up new routers, removed duplicate endpoints

---

## Next Steps

1. **Deploy** the updated code to ECS
2. **Verify** `JWT_SECRET` is set in ECS task environment (from Secrets Manager)
3. **Test** all endpoints using the sanity test commands above
4. **Monitor** for any 401 errors (should be resolved with prefix-safe normalization)

---

**Status:** ✅ All fixes applied and ready for deployment
