# HTTP Status Codes Reference

This document lists all HTTP status codes used in the ACME API, organized by status code and endpoint.

## Status Code Summary

| Code | Meaning | Count | Endpoints |
|------|---------|-------|-----------|
| 200 | OK - Success | Multiple | All GET endpoints, successful operations |
| 201 | Created | 1 | POST /artifact/{artifact_type} |
| 202 | Accepted | 1 | POST /artifact/{artifact_type} (async rating) |
| 400 | Bad Request | Multiple | Invalid input, missing fields, malformed requests |
| 401 | Unauthorized | 2 | Authentication failures, permission denied |
| 403 | Forbidden | Multiple | Authentication token invalid/missing |
| 404 | Not Found | Multiple | Artifact does not exist |
| 409 | Conflict | 2 | Artifact exists already |
| 413 | Payload Too Large | 1 | Too many artifacts returned |
| 424 | Failed Dependency | 1 | Artifact disqualified by rating |
| 500 | Internal Server Error | Multiple | Server-side errors, rating failures |
| 502 | Bad Gateway | 1 | License check service unavailable |
| 501 | Not Implemented | 1 | Authentication not supported |

---

## Status Code Details

### 200 OK
**Description:** Request succeeded.

**Endpoints:**
- `GET /health` - Service reachable
- `GET /health/components` - Component health details returned
- `GET /artifacts/{artifact_type}/{id}` - Artifact retrieved successfully
- `PUT /artifacts/{artifact_type}/{id}` - Artifact updated successfully
- `DELETE /artifacts/{artifact_type}/{id}` - Artifact deleted successfully
- `DELETE /reset` - Registry reset successfully
- `POST /artifacts` - Artifacts list returned
- `GET /artifact/{artifact_type}/{id}/cost` - Cost calculation successful
- `GET /artifact/{artifact_type}/{id}/audit` - Audit trail returned
- `GET /artifact/model/{id}/rate` - Rating returned
- `GET /artifact/model/{id}/lineage` - Lineage returned
- `POST /artifact/model/{id}/license-check` - License check completed
- `GET /artifact/byName/{name}` - Artifacts found by name
- `POST /artifact/byRegEx` - Artifacts found by regex
- `GET /tracks` - Tracks returned
- `PUT /authenticate` - Authentication token returned

---

### 201 Created
**Description:** Resource created successfully.

**Endpoints:**
- `POST /artifact/{artifact_type}` - Artifact successfully created and registered

**Response Body:**
```json
{
  "metadata": {
    "name": "artifact-name",
    "id": "1234567890",
    "type": "model"
  },
  "data": {
    "url": "https://...",
    "download_url": "https://..."
  }
}
```

---

### 202 Accepted
**Description:** Request accepted for processing, but processing is deferred.

**Endpoints:**
- `POST /artifact/{artifact_type}` - Artifact ingest accepted but rating pipeline deferred

**Details:**
- Artifact is stored but rating is performed asynchronously
- Artifact may be dropped silently if rating later fails
- Subsequent requests to `/rate` or other endpoints with this artifact id should return 404 until a rating result exists

---

### 400 Bad Request
**Description:** The request is invalid, malformed, or missing required fields.

**Endpoints and Error Messages:**

1. **POST /artifacts**
   - "Request body must be an array of ArtifactQuery objects"
   - "Each query must be an object"
   - "Missing required field 'name' in artifact_query"
   - "There is missing field(s) in the artifact_query or it is formed improperly, or is invalid."

2. **GET /health/components**
   - "windowMinutes must be between 5 and 1440"

3. **GET /artifacts/{artifact_type}/{id}**
   - "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."

4. **PUT /artifacts/{artifact_type}/{id}**
   - "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
   - "Name and id in metadata must match the path parameters"
   - "Missing required field 'url' in artifact data"

5. **DELETE /artifacts/{artifact_type}/{id}**
   - "There is missing field(s) in the artifact_type or artifact_id or invalid"

6. **POST /artifact/{artifact_type}**
   - "There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)."
   - "Invalid artifact_type: {type}. Must be one of: model, dataset, code"
   - "Missing required field 'url' in request body"

7. **GET /artifact/{artifact_type}/{id}/cost**
   - "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."

8. **GET /artifact/{artifact_type}/{id}/audit**
   - "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."

9. **GET /artifact/model/{id}/rate**
   - "There is missing field(s) in the artifact_id or it is formed improperly, or is invalid."

10. **GET /artifact/model/{id}/lineage**
    - "There is missing field(s) in the artifact_id or it is formed improperly, or is invalid."

11. **POST /artifact/model/{id}/license-check**
    - "There is missing field(s) in the artifact_id or it is formed improperly, or is invalid."
    - "Missing required field 'github_url' in request body"

12. **GET /artifact/byName/{name}**
    - "There is missing field(s) in the artifact_name or it is formed improperly, or is invalid."
    - "Name parameter is empty or invalid"

13. **POST /artifact/byRegEx**
    - "There is missing field(s) in the regex or it is formed improperly, or is invalid."
    - "Missing required field 'regex' in request body"

14. **PUT /authenticate**
    - "There is missing field(s) in the AuthenticationRequest or it is formed improperly."

15. **DELETE /reset**
    - Various validation errors during reset operation

---

### 401 Unauthorized
**Description:** Authentication failed or user lacks permission.

**Endpoints:**

1. **DELETE /reset**
   - "You do not have permission to reset the registry."
   - Only admin users can reset the registry

2. **PUT /authenticate**
   - "The user or password is invalid."

---

### 403 Forbidden
**Description:** Authentication failed due to invalid or missing AuthenticationToken.

**Endpoints:**
- All authenticated endpoints return 403 when:
  - `X-Authorization` header is missing
  - `X-Authorization` header contains an invalid token
  - Token is expired
  - Token format is incorrect

**Affected Endpoints:**
- `POST /artifacts`
- `GET /artifacts/{artifact_type}/{id}`
- `PUT /artifacts/{artifact_type}/{id}`
- `DELETE /artifacts/{artifact_type}/{id}`
- `DELETE /reset`
- `POST /artifact/{artifact_type}`
- `GET /artifact/{artifact_type}/{id}/cost`
- `GET /artifact/{artifact_type}/{id}/audit`
- `GET /artifact/model/{id}/rate`
- `GET /artifact/model/{id}/lineage`
- `POST /artifact/model/{id}/license-check`
- `GET /artifact/byName/{name}`
- `POST /artifact/byRegEx`

**Error Message:**
- "Authentication failed due to invalid or missing AuthenticationToken"

---

### 404 Not Found
**Description:** The requested resource does not exist.

**Endpoints and Error Messages:**

1. **GET /artifacts/{artifact_type}/{id}**
   - "Artifact does not exist."

2. **PUT /artifacts/{artifact_type}/{id}**
   - "Artifact does not exist."

3. **DELETE /artifacts/{artifact_type}/{id}**
   - "Artifact does not exist."

4. **GET /artifact/{artifact_type}/{id}/cost**
   - "Artifact does not exist."
   - Error message from cost calculation service

5. **GET /artifact/{artifact_type}/{id}/audit**
   - "Artifact does not exist."

6. **GET /artifact/model/{id}/rate**
   - "Artifact does not exist."
   - Returned when artifact hasn't been rated yet (for 202 Accepted artifacts)

7. **GET /artifact/model/{id}/lineage**
   - "Artifact does not exist."

8. **POST /artifact/model/{id}/license-check**
   - "Artifact does not exist."

9. **GET /artifact/byName/{name}**
   - "No such artifact."

10. **POST /artifact/byRegEx**
    - "No artifact found under this regex."

---

### 409 Conflict
**Description:** The resource already exists and cannot be created again.

**Endpoints:**

1. **POST /artifact/{artifact_type}**
   - "Artifact exists already."
   - Returned when attempting to create an artifact that already exists (same URL or name)

2. **POST /artifact/ingest**
   - "Artifact exists already."
   - Returned when attempting to ingest an artifact that is already registered

---

### 413 Payload Too Large
**Description:** The response would be too large to return.

**Endpoints:**

1. **POST /artifacts**
   - "Too many artifacts returned."
   - Returned when query results exceed 10,000 artifacts

---

### 424 Failed Dependency
**Description:** The operation failed because a dependency failed.

**Endpoints:**

1. **POST /artifact/{artifact_type}**
   - "Artifact is not registered due to the disqualified rating."
   - Returned when artifact ingestion is rejected because the rating system disqualified the artifact

---

### 500 Internal Server Error
**Description:** An unexpected error occurred on the server.

**Endpoints and Error Messages:**

1. **GET /artifact/{artifact_type}/{id}/cost**
   - "The artifact cost calculator encountered an error."
   - Generic error message when cost calculation fails

2. **GET /artifact/model/{id}/rate**
   - "The artifact rating system encountered an error while computing at least one metric."
   - Returned when rating computation fails

3. **GET /artifact/model/{id}/lineage**
   - Various internal errors during lineage retrieval
   - "Failed to get model lineage: {error}"

4. **POST /artifact/{artifact_type}**
   - "Failed to ingest model: {error}"
   - "Ingest failed: {error}"

5. **DELETE /reset**
   - "Reset failed: {error}"

6. **GET /tracks**
   - Generic server error

7. **POST /artifact/model/{id}/license-check**
   - Various internal errors during license checking

---

### 502 Bad Gateway
**Description:** The server, while acting as a gateway or proxy, received an invalid response from an upstream server.

**Endpoints:**

1. **POST /artifact/model/{id}/license-check**
   - Returned when the license check service (external dependency) is unavailable or returns an error

---

### 501 Not Implemented
**Description:** The requested functionality is not implemented.

**Endpoints:**

1. **PUT /authenticate**
   - "This system does not support authentication."
   - Returned when authentication is not implemented in the system

---

## Status Code Usage by Endpoint

### GET /health
- **200**: Service reachable

### GET /health/components
- **200**: Component health details returned
- **400**: windowMinutes out of range (5-1440)

### POST /artifacts
- **200**: Artifacts list returned
- **400**: Missing/invalid fields in artifact_query
- **403**: Authentication failed
- **413**: Too many artifacts returned (>10,000)

### DELETE /reset
- **200**: Registry reset successfully
- **401**: User lacks permission to reset
- **403**: Authentication failed
- **500**: Reset operation failed

### GET /artifacts/{artifact_type}/{id}
- **200**: Artifact retrieved successfully
- **400**: Invalid artifact_type or artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist

### PUT /artifacts/{artifact_type}/{id}
- **200**: Artifact updated successfully
- **400**: Invalid fields or missing required data
- **403**: Authentication failed
- **404**: Artifact does not exist

### DELETE /artifacts/{artifact_type}/{id}
- **200**: Artifact deleted successfully
- **400**: Invalid artifact_type or artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist

### POST /artifact/{artifact_type}
- **201**: Artifact created successfully
- **202**: Artifact ingest accepted, rating deferred
- **400**: Missing/invalid fields in artifact_data
- **403**: Authentication failed
- **409**: Artifact exists already
- **424**: Artifact disqualified by rating
- **500**: Ingest operation failed

### GET /artifact/{artifact_type}/{id}/cost
- **200**: Cost calculation successful
- **400**: Invalid artifact_type or artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist
- **500**: Cost calculator error

### GET /artifact/{artifact_type}/{id}/audit
- **200**: Audit trail returned
- **400**: Invalid artifact_type or artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist

### GET /artifact/model/{id}/rate
- **200**: Rating returned successfully
- **400**: Invalid artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist or not rated yet
- **500**: Rating system error

### GET /artifact/model/{id}/lineage
- **200**: Lineage returned successfully
- **400**: Invalid artifact_id
- **403**: Authentication failed
- **404**: Artifact does not exist
- **500**: Lineage retrieval error

### POST /artifact/model/{id}/license-check
- **200**: License check completed
- **400**: Invalid artifact_id or missing github_url
- **403**: Authentication failed
- **404**: Artifact does not exist
- **502**: License check service unavailable

### GET /artifact/byName/{name}
- **200**: Artifacts found by name
- **400**: Invalid or missing artifact_name
- **403**: Authentication failed
- **404**: No such artifact

### POST /artifact/byRegEx
- **200**: Artifacts found by regex
- **400**: Invalid or missing regex
- **403**: Authentication failed
- **404**: No artifact found under this regex

### PUT /authenticate
- **200**: Authentication token returned
- **400**: Missing/invalid fields in AuthenticationRequest
- **401**: Invalid user or password
- **501**: Authentication not supported

### GET /tracks
- **200**: Tracks returned
- **500**: Server error

---

## Common Error Patterns

### Authentication Errors (403)
All authenticated endpoints return 403 when:
- `X-Authorization` header is missing
- Token is invalid, expired, or malformed
- Token verification fails

### Not Found Errors (404)
Most endpoints return 404 when:
- Artifact ID doesn't exist in database
- Artifact doesn't exist in S3
- Artifact was deleted
- Artifact rating is still pending (for rate endpoint)

### Validation Errors (400)
Common causes:
- Missing required fields in request body
- Invalid data types or formats
- Parameter values out of allowed range
- Malformed JSON in request body

### Server Errors (500)
Common causes:
- Database connection failures
- S3 access errors
- External service failures
- Unexpected exceptions in business logic

---

## Notes

- All status codes follow HTTP/1.1 standard definitions
- Error responses typically include a `detail` field with a descriptive error message
- Authentication is required for most endpoints except `/health`, `/health/components`, `/authenticate`, and `/tracks`
- The API Gateway integration responses are configured in `infra/modules/api-gateway/main.tf` to handle all these status codes

