# CURL Commands for All Endpoints

Base URL: `https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod`

API Reference: [https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/](https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/)

## ⚠️ Important: PowerShell vs Bash

**If you're using PowerShell (Windows), use the PowerShell commands below.**
**If you're using Bash/Linux/Mac, use the Bash commands.**

PowerShell uses different syntax:
- Variables: `$TOKEN = ...` (not `TOKEN=$(...)`)
- String replacement: `.Replace('"', '')` (not `tr -d '"'`)
- No `tr` command available

## Authentication Token
Most endpoints require authentication. First, get a token:

### Bash/Linux/Mac
```bash
# Get authentication token (autograder-compatible) using auth.json
TOKEN=$(curl.exe -s -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate" -H "Content-Type: application/json" -d @auth.json | tr -d '"')

# Or use POST /login (same as above)
TOKEN=$(curl.exe -s -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/login" -H "Content-Type: application/json" -d @auth.json | tr -d '"')
```

### PowerShell/Windows
```powershell
# Get authentication token (autograder-compatible) using auth.json
$TOKEN = (curl.exe -s -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate" -H "Content-Type: application/json" -d "@auth.json").Replace('"', '')

# Or use POST /login (same as above)
$TOKEN = (curl.exe -s -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/login" -H "Content-Type: application/json" -d "@auth.json").Replace('"', '')
```

---

## Health Endpoints

### GET /health
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/health"
```

### GET /health/components
```bash
# Basic request
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/health/components"

# With query parameters
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/health/components?windowMinutes=60&includeTimeline=true"
```

---

## Authentication Endpoints (Public - No Auth Required)

### PUT /authenticate

```bash
curl.exe -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate" -H "Content-Type: application/json" -d @auth.json
```

### POST /login (alias for /authenticate)

```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/login" -H "Content-Type: application/json" -d @auth.json
```

### POST /auth/register
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/register" -H "Content-Type: application/json" -d "{\"username\": \"newuser\", \"password\": \"securepassword123\", \"roles\": [\"user\"], \"groups\": []}"
```

### POST /auth/login
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/login" -H "Content-Type: application/json" -d "{\"username\": \"newuser\", \"password\": \"securepassword123\"}"
```

### GET /auth/me (Requires Bearer Token)

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/me" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/me" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### POST /auth/logout (Requires Bearer Token)

**Bash:**
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/logout" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/auth/logout" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

---

## Artifact Management Endpoints (Require Auth)

### POST /artifacts

**Bash:**
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "[{\"name\": \"example-model\", \"types\": [\"model\"]}, {\"name\": \"*\", \"types\": [\"model\", \"dataset\"]}]"
```

**PowerShell:**
```powershell
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "[{`"name`": `"example-model`", `"types`": [`"model`"]}, {`"name`": `"*`", `"types`": [`"model`", `"dataset`"]}]"
```

### DELETE /reset

**Bash:**
```bash
curl.exe -X DELETE "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/reset" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X DELETE "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/reset" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### GET /artifact/byName/{name}

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byName/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byName/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### POST /artifact/byRegEx

**Bash:**
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byRegEx" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{\"regex\": \".*example.*\"}"
```

**PowerShell:**
```powershell
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byRegEx" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{`"regex`": `".*example.*`"}"
```

### GET /artifacts/{artifact_type}/{id}

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### POST /artifact/ingest

**Bash:**
```bash
# Ingest a model from HuggingFace (using form data with model name)
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -F "name=maya-research/maya1" -F "version=main"

# Ingest a model from HuggingFace (using JSON with model name)
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{\"name\": \"maya-research/maya1\", \"version\": \"main\"}"

# Alternative: Use /artifacts endpoint with full HuggingFace URL
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{\"metadata\": {\"name\": \"maya-research/maya1\", \"type\": \"model\"}, \"data\": {\"url\": \"https://huggingface.co/maya-research/maya1\"}}"
```

**PowerShell:**
```powershell
# Ingest a model from HuggingFace (using form data with model name)
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -F "name=maya-research/maya1" -F "version=main"

# Ingest a model from HuggingFace (using JSON with model name)
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{`"name`": `"maya-research/maya1`", `"version`": `"main`"}"

# Alternative: Use /artifacts endpoint with full HuggingFace URL
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{`"metadata`": {`"name`": `"maya-research/maya1`", `"type`": `"model`"}, `"data`": {`"url`": `"https://huggingface.co/maya-research/maya1`"}}"
```

### PUT /artifacts/{artifact_type}/{id}

**Bash:**
```bash
curl.exe -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{\"metadata\": {\"name\": \"example-model\", \"id\": \"example-model\", \"type\": \"model\"}, \"data\": {\"url\": \"https://huggingface.co/example-model\"}}"
```

**PowerShell:**
```powershell
curl.exe -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{`"metadata`": {`"name`": `"example-model`", `"id`": `"example-model`", `"type`": `"model`"}, `"data`": {`"url`": `"https://huggingface.co/example-model`"}}"
```

### DELETE /artifacts/{artifact_type}/{id}

**Bash:**
```bash
curl.exe -X DELETE "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X DELETE "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/example-model" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### GET /artifact/{artifact_type}/{id}/cost

**Bash:**
```bash
# Without dependency calculation
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/cost" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

# With dependency calculation
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/cost?dependency=true" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
# Without dependency calculation
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/cost" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

# With dependency calculation
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/cost?dependency=true" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### GET /artifact/{artifact_type}/{id}/audit

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/audit" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/audit" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

---

## Model-Specific Endpoints (Require Auth)

### GET /artifact/model/{id}/rate

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/rate" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/rate" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### GET /artifact/model/{id}/lineage

**Bash:**
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/lineage" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/lineage" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

### POST /artifact/model/{id}/license-check

**Bash:**
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/license-check" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{\"github_url\": \"https://github.com/example/repo\", \"use_case\": \"fine-tune+inference\"}"
```

**PowerShell:**
```powershell
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/example-model/license-check" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" -H "Content-Type: application/json" -d "{`"github_url`": `"https://github.com/example/repo`", `"use_case`": `"fine-tune+inference`"}"
```

---

## Other Endpoints

### GET /tracks
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/tracks"
```

### GET /artifact/ingest
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest?name=maya-research/maya1&version=main" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

**PowerShell:**
```powershell
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/ingest?name=maya-research/maya1&version=main" -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
```

---

## API Router Endpoints (prefix: /api)

### GET /api/hello
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/hello"
```

### PUT /api/ingest
```bash
curl.exe -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/ingest" -H "Content-Type: application/json" -d "{\"id\": \"artifact-123\", \"name\": \"example-artifact\", \"type\": \"model\", \"version\": \"1.0.0\", \"description\": \"Example artifact\"}"

# Or with array
curl.exe -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/ingest" -H "Content-Type: application/json" -d "[{\"id\": \"artifact-123\", \"name\": \"example-artifact\", \"type\": \"model\", \"version\": \"1.0.0\"}]"
```

### GET /api/artifacts
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/artifacts"
```

### GET /api/artifacts/by-name/{name}
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/artifacts/by-name/example-artifact"
```

### GET /api/artifacts/{artifact_id}
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/artifacts/artifact-123"
```

---

## Packages Router Endpoints (prefix: /api/packages)

### GET /api/packages
```bash
# List all packages
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages"

# With query parameters
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages?limit=50&name_regex=.*example.*&version_range=1.0.0-2.0.0"
```

### GET /api/packages/rate/{name}
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/rate/example-model"
```

### GET /api/packages/search
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/search?q=example"
```

### GET /api/packages/search/model-cards
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/search/model-cards?q=transformer"
```

### GET /api/packages/search/advanced
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/search/advanced?name_regex=.*example.*&model_regex=.*transformer.*&version_range=1.0.0-2.0.0&limit=100"
```

### POST /api/packages/upload
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/upload" -F "file=@model.zip" -F "debloat=false"
```

### POST /api/packages/reset
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/reset"
```

### POST /api/packages/sync-neptune
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/sync-neptune"
```

### POST /api/packages/models/{model_id}/{version}/model.zip
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/example-model/1.0.0/model.zip" -F "file=@model.zip"
```

### GET /api/packages/models/{model_id}/{version}/model.zip
```bash
# Download full model
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/example-model/1.0.0/model.zip" -o model.zip

# Download specific component
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/example-model/1.0.0/model.zip?component=weights" -o weights.zip
```

### GET /api/packages/models/{model_id}/{version}/lineage
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/example-model/1.0.0/lineage"
```

### GET /api/packages/models/{model_id}/{version}/size
```bash
curl.exe -X GET "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/example-model/1.0.0/size"
```

### POST /api/packages/models/ingest
```bash
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/packages/models/ingest?model_id=example-model&version=main"
```

---

## Rating Router Endpoints (prefix: /api)

### POST /api/registry/models/{modelId}/rate
```bash
# Basic rating request
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/registry/models/example-model/rate" -H "Content-Type: application/json" -d "{\"target\": \"https://huggingface.co/example-model\"}"

# With enforce flag (will fail if scores <= 0.5)
curl.exe -X POST "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/api/registry/models/example-model/rate?enforce=true" -H "Content-Type: application/json" -d "{\"target\": \"https://huggingface.co/example-model\"}"
```

---

## Notes

1. **Authentication**: Most endpoints require the `X-Authorization` header with a bearer token. You can get a token using `/authenticate` or `/login`.

2. **Base URL**: All commands use the production API URL: `https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod`

3. **Token Variable**: 
   - **Bash/Linux/Mac**: Store the token using `$(...)` syntax:
     ```bash
     TOKEN=$(curl.exe -s -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate" -H "Content-Type: application/json" -d @auth.json | tr -d '"')
     ```
   - **PowerShell/Windows**: Store the token using `$variable = ...` syntax:
     ```powershell
     $TOKEN = (curl.exe -s -X PUT "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate" -H "Content-Type: application/json" -d "@auth.json").Replace('"', '')
     ```

4. **Using auth.json**: All authentication endpoints use the `auth.json` file for credentials. Make sure the file exists in your current directory.

5. **Using curl.exe**: All commands use `curl.exe` for Windows/PowerShell compatibility. This ensures the actual curl executable is used instead of PowerShell aliases.

6. **PowerShell Notes**: 
   - All commands are single-line (no line continuation needed)
   - Use `.Replace('"', '')` instead of `tr -d '"'`
   - Use `$VARIABLE` syntax for variables (not `$VARIABLE=$(...)`)

7. **File Uploads**: For file upload endpoints, use `-F` flag with `@filename` syntax.

8. **Query Parameters**: Some endpoints accept query parameters. Use `?param=value&param2=value2` syntax.

9. **JSON Payloads**: For JSON requests, always include `Content-Type: application/json` header.

