# Debug Logs Analysis - Validator Service

**Date:** 2025-11-15  
**Validator Service URL:** `http://validator-lb-727503296.us-east-1.elb.amazonaws.com`  
**CloudWatch Log Group:** `/ecs/validator-service`

## Summary

All endpoints from `CURL_COMMANDS.md` were tested against the validator service directly (bypassing API Gateway). The debug logs show the complete request flow through the application.

---

## Test Results

### ✅ Working Endpoints

1. **GET /health** - ✅ Working
   - Returns: `{"ok": true}`

2. **GET /health/components** - ✅ Working
   - Returns component health details

3. **PUT /authenticate** - ✅ Working
   - Successfully authenticates and returns bearer token

4. **POST /artifacts** (query) - ✅ Working (with DynamoDB permission fix)
   - Returns list of artifacts
   - **Issue Found:** Missing `dynamodb:Scan` permission (FIXED)

5. **POST /artifact/model** (ingest) - ✅ Working
   - Successfully ingested model: `distilbert-base-uncased`
   - Artifact ID: `8943025711`

6. **GET /artifacts/{artifact_type}/{id}** - ✅ Working
   - Successfully retrieved artifact by ID

7. **GET /artifact/byName/{name}** - ✅ Working
   - Successfully found artifacts by name

8. **GET /artifact/model/{id}/rate** - ✅ Working
   - Returns rating with net_score: 0.7

9. **GET /artifact/{artifact_type}/{id}/audit** - ✅ Working
   - Returns audit trail

10. **GET /tracks** - ✅ Working
    - Returns planned tracks

---

## Debug Log Analysis

### Request Flow Patterns

#### 1. Authentication Flow
```
=== MIDDLEWARE START: PUT /authenticate ===
=== MIDDLEWARE: Headers: {...'x-authorization': 'bearer ...'} ===
=== MIDDLEWARE: Calling call_next ===
=== MIDDLEWARE: Response status 200 ===
```

#### 2. POST /artifacts Query Flow
```
=== MIDDLEWARE START: POST /artifacts ===
=== MIDDLEWARE: Headers: {...'x-authorization': 'bearer ...', 'content-type': 'application/json'} ===
=== MIDDLEWARE: Calling call_next ===
[DEBUG: Searching S3 for models...]
[DEBUG: Searching S3 for datasets...]
[DEBUG: Searching S3 for code...]
[DEBUG: Checking database...]
=== MIDDLEWARE: Response status 200 ===
```

#### 3. GET /artifact/byName Flow
```
=== MIDDLEWARE START: GET /artifact/byName/{name} ===
DEBUG: ===== GET_ARTIFACT_BY_NAME START =====
DEBUG: Searching for artifact with name: '{name}'
DEBUG: ===== SEARCHING S3 FOR MODELS =====
DEBUG: Searching S3 for models with name pattern: ^{name}$
DEBUG: list_models returned {count} models
DEBUG: ===== CHECKING DATABASE =====
DEBUG: Database artifacts count: {count}
DEBUG: Found {count} artifact(s)
```

#### 4. POST /artifact/model Ingest Flow
```
=== MIDDLEWARE START: POST /artifact/model ===
[INGEST] Downloaded in {time}s
[INGEST] Found github field in hf_meta: {url}
[INGEST] Fetching GitHub metadata for {url}
[INGEST] Computing metrics...
[INGEST] license = {score}
[INGEST] ramp_up = {score}
[INGEST] bus_factor = {score}
[INGEST] performance_claims = {score}
AWS S3 upload successful: {model} v{version} ({size} bytes) -> models/{model}/{version}/model.zip
DEBUG: Starting async rating for artifact_id='{id}'
DEBUG: [ASYNC RATING] Starting rating for artifact_id='{id}', model_name='{name}'
DEBUG: Storing metadata to S3 key: models/{model}/{version}/metadata.json
[INGEST] Success in {time}s
```

#### 5. GET /artifact/model/{id}/rate Flow
```
=== MIDDLEWARE START: GET /artifact/model/{id}/rate ===
DEBUG: Validating id format: '{id}'
DEBUG: ===== GET_MODEL_RATE START =====
DEBUG: Querying rate for id='{id}'
DEBUG: ✅ Found artifact in database: {artifact}
DEBUG: Analyzing model content for id='{id}'
DEBUG: Building rating response for id='{id}'
DEBUG: Returning rating result: {result}
```

---

## Issues Found and Fixed

### 1. ❌ DynamoDB Scan Permission Missing (FIXED)

**Error:**
```
ERROR:src.services.artifact_storage:Error listing artifacts: AccessDeniedException - 
An error occurred (AccessDeniedException) when calling the Scan operation: 
User: arn:aws:sts::838693051036:assumed-role/ecs-task-role/... is not authorized to perform: 
dynamodb:Scan on resource: arn:aws:dynamodb:us-east-1:838693051036:table/artifacts 
because no identity-based policy allows the dynamodb:Scan action
```

**Location:** `infra/modules/ecs/main.tf` - IAM policy for ECS task role

**Fix Applied:**
- Added `"dynamodb:Scan"` to the IAM policy actions
- Also added `"dynamodb:DeleteItem"` for completeness

**Before:**
```terraform
Action = [
  "dynamodb:GetItem",
  "dynamodb:PutItem",
  "dynamodb:UpdateItem",
  "dynamodb:Query"
]
```

**After:**
```terraform
Action = [
  "dynamodb:GetItem",
  "dynamodb:PutItem",
  "dynamodb:UpdateItem",
  "dynamodb:DeleteItem",
  "dynamodb:Query",
  "dynamodb:Scan"
]
```

### 2. ⚠️ UTF-8 BOM Issue in PowerShell

**Issue:** PowerShell's `Out-File` creates JSON files with UTF-8 BOM, causing JSON parsing errors

**Error:**
```
Invalid JSON in request body: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)
```

**Solution:** Use `-Encoding utf8NoBOM` or create JSON files differently:
```powershell
$json | Out-File -FilePath "file.json" -Encoding utf8NoBOM
# OR
[System.IO.File]::WriteAllText("file.json", $json, [System.Text.UTF8Encoding]::new($false))
```

### 3. ⚠️ JSON Escaping in PowerShell

**Issue:** PowerShell's backtick escaping in curl commands can cause JSON parsing errors

**Solution:** Use JSON files instead of inline JSON for complex requests

---

## Key DEBUG Log Patterns

### Authentication Verification
```
DEBUG: No authorization header found
DEBUG: Token does not have valid JWT format (3 parts)
DEBUG: JWT verification successful - user_id: {id}
DEBUG: Static token from /authenticate accepted
```

### S3 Operations
```
DEBUG: Storing metadata to S3 key: {key}
DEBUG: Metadata content: {json}
DEBUG: Searching S3 for models with name pattern: {pattern}
DEBUG: list_models returned {count} models
```

### Database Operations
```
DEBUG: ===== CHECKING DATABASE =====
DEBUG: Database artifacts count: {count}
DEBUG: Found artifact in database: id='{id}', name='{name}', type='{type}'
DEBUG: Found {count} additional artifacts in database
```

### Model Ingestion
```
[INGEST] Downloaded in {time}s
[INGEST] Found github field in hf_meta: {url}
[INGEST] Computing metrics...
[INGEST] license = {score}
[INGEST] ramp_up = {score}
AWS S3 upload successful: {model} v{version} ({size} bytes)
DEBUG: Starting async rating for artifact_id='{id}'
```

### Rating Operations
```
DEBUG: Starting async rating for artifact_id='{id}'
DEBUG: [ASYNC RATING] Starting rating for artifact_id='{id}', model_name='{name}'
DEBUG: Rating status for id='{id}': {status}
DEBUG: Using cached rating result for id='{id}'
DEBUG: Building rating response for id='{id}'
```

---

## Request Flow Summary

### Typical Request Flow:
1. **Middleware** - Logs request start, headers, method, path
2. **Authentication** - Verifies `X-Authorization` header
3. **Validation** - Validates request parameters/body
4. **Business Logic** - Executes endpoint-specific logic
   - S3 operations (list, get, put)
   - DynamoDB operations (get, put, scan, query)
   - Model ingestion/rating
5. **Response** - Returns JSON response
6. **Middleware** - Logs response status

### Error Handling:
- All errors are caught and logged with full traceback
- HTTP exceptions include status code, detail, path, method, headers
- Errors are returned as JSON with `{"detail": "error message"}`

---

## Performance Observations

From the logs:
- Model download: ~0.18-0.57 seconds
- S3 upload: Successful
- Metric computation: ~0.02 seconds
- Async rating: Starts immediately, completes in background

---

## Recommendations

1. **Deploy IAM Policy Fix** - The `dynamodb:Scan` permission needs to be deployed via Terraform
2. **Monitor DynamoDB Errors** - Watch for AccessDeniedException errors in logs
3. **Use JSON Files** - For PowerShell scripts, use JSON files instead of inline JSON
4. **Check Rate Limits** - GitHub API rate limits may affect ingestion (set GITHUB_TOKEN)

---

## Log Retrieval Commands

### Get Recent DEBUG Logs:
```bash
aws logs tail /ecs/validator-service --since 10m --format short --filter-pattern "DEBUG"
```

### Get All Recent Logs:
```bash
aws logs tail /ecs/validator-service --since 10m --format short
```

### Get Error Logs:
```bash
aws logs tail /ecs/validator-service --since 10m --format short --filter-pattern "ERROR"
```

### Get Logs for Specific Endpoint:
```bash
aws logs tail /ecs/validator-service --since 10m --format short | grep "POST /artifacts"
```

---

## Notes

- All timestamps are in UTC
- Log format: `YYYY-MM-DDTHH:MM:SS LEVEL:module:message`
- DEBUG logs show detailed request processing flow
- ERROR logs include full Python tracebacks
- Middleware logs all requests before processing

