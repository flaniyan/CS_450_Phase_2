# API Error Codes Reference

This document lists all HTTP status codes and their descriptions as defined in the ECE 461 Fall 2025 OpenAPI Specification (Version 3.4.6).

## Success Codes

### 200 OK
- **Service reachable** - `/health` endpoint
- **List of artifacts** - `/artifacts` POST endpoint
- **Return the artifact** - `/artifacts/{artifact_type}/{id}` GET endpoint
- **Artifact is updated** - `/artifacts/{artifact_type}/{id}` PUT endpoint
- **Artifact is deleted** - `/artifacts/{artifact_type}/{id}` DELETE endpoint
- **Return the rating** - `/artifact/model/{id}/rate` GET endpoint (only if each metric was computed successfully)
- **Return the total cost of the artifact, and its dependencies** - `/artifact/{artifact_type}/{id}/cost` GET endpoint
- **Return an AuthenticationToken** - `/authenticate` PUT endpoint
- **Return artifact metadata entries that match the provided name** - `/artifact/byName/{name}` GET endpoint
- **Return the audit trail for this artifact** - `/artifact/{artifact_type}/{id}/audit` GET endpoint
- **Lineage graph extracted from structured metadata** - `/artifact/model/{id}/lineage` GET endpoint
- **License compatibility analysis produced successfully** - `/artifact/model/{id}/license-check` POST endpoint
- **Return a list of artifacts** - `/artifact/byRegEx` POST endpoint
- **Return the list of tracks the student plans to implement** - `/tracks` GET endpoint
- **Component-level health detail** - `/health/components` GET endpoint

### 201 Created
- **Success. Check the id in the returned metadata for the official ID** - `/artifact/{artifact_type}` POST endpoint

### 202 Accepted
- **Artifact ingest accepted but the rating pipeline deferred the evaluation** - `/artifact/{artifact_type}` POST endpoint
  - Use this when the package is stored but rating is performed asynchronously and the artifact is dropped silently if the rating later fails. Subsequent requests to `/rate` or any other endpoint with this artifact id should return 404 until a rating result exists.

---

## Client Error Codes (4xx)

### 400 Bad Request
- **There is missing field(s) in the artifact_query or it is formed improperly, or is invalid** - `/artifacts` POST endpoint
- **There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid** - `/artifacts/{artifact_type}/{id}` GET/PUT endpoints
- **There is missing field(s) in the artifact_type or artifact_id or invalid** - `/artifacts/{artifact_type}/{id}` DELETE endpoint
- **There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)** - `/artifact/{artifact_type}` POST endpoint
- **There is missing field(s) in the artifact_id or it is formed improperly, or is invalid** - `/artifact/model/{id}/rate` GET endpoint
- **There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid** - `/artifact/{artifact_type}/{id}/cost` GET endpoint
- **There is missing field(s) in the AuthenticationRequest or it is formed improperly** - `/authenticate` PUT endpoint
- **There is missing field(s) in the artifact_name or it is formed improperly, or is invalid** - `/artifact/byName/{name}` GET endpoint
- **There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid** - `/artifact/{artifact_type}/{id}/audit` GET endpoint
- **The lineage graph cannot be computed because the artifact metadata is missing or malformed** - `/artifact/model/{id}/lineage` GET endpoint
- **The license check request is malformed or references an unsupported usage context** - `/artifact/model/{id}/license-check` POST endpoint
- **There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid** - `/artifact/byRegEx` POST endpoint

### 401 Unauthorized
- **You do not have permission to reset the registry** - `/reset` DELETE endpoint

### 403 Forbidden
- **Authentication failed due to invalid or missing AuthenticationToken** - All authenticated endpoints:
  - `/artifacts` POST
  - `/reset` DELETE
  - `/artifacts/{artifact_type}/{id}` GET/PUT/DELETE
  - `/artifact/{artifact_type}` POST
  - `/artifact/model/{id}/rate` GET
  - `/artifact/{artifact_type}/{id}/cost` GET
  - `/artifact/byName/{name}` GET
  - `/artifact/{artifact_type}/{id}/audit` GET
  - `/artifact/model/{id}/lineage` GET
  - `/artifact/model/{id}/license-check` POST
  - `/artifact/byRegEx` POST

### 404 Not Found
- **Artifact does not exist** - Multiple endpoints:
  - `/artifacts/{artifact_type}/{id}` GET/PUT/DELETE
  - `/artifact/model/{id}/rate` GET
  - `/artifact/{artifact_type}/{id}/cost` GET
  - `/artifact/{artifact_type}/{id}/audit` GET
  - `/artifact/model/{id}/lineage` GET
- **No such artifact** - `/artifact/byName/{name}` GET endpoint
- **The artifact or GitHub project could not be found** - `/artifact/model/{id}/license-check` POST endpoint
- **No artifact found under this regex** - `/artifact/byRegEx` POST endpoint

### 409 Conflict
- **Artifact exists already** - `/artifact/{artifact_type}` POST endpoint

### 413 Payload Too Large
- **Too many artifacts returned** - `/artifacts` POST endpoint

### 424 Failed Dependency
- **Artifact is not registered due to the disqualified rating** - `/artifact/{artifact_type}` POST endpoint

---

## Server Error Codes (5xx)

### 500 Internal Server Error
- **The artifact rating system encountered an error while computing at least one metric** - `/artifact/model/{id}/rate` GET endpoint
- **The artifact cost calculator encountered an error** - `/artifact/{artifact_type}/{id}/cost` GET endpoint
- **The system encountered an error while retrieving the student's track information** - `/tracks` GET endpoint

### 501 Not Implemented
- **This system does not support authentication** - `/authenticate` PUT endpoint

### 502 Bad Gateway
- **External license information could not be retrieved** - `/artifact/model/{id}/license-check` POST endpoint

---

## Error Code Summary by Endpoint

### `/health` GET
- **200**: Service reachable

### `/health/components` GET
- **200**: Component-level health detail

### `/artifacts` POST
- **200**: List of artifacts
- **400**: There is missing field(s) in the artifact_query or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **413**: Too many artifacts returned

### `/reset` DELETE
- **200**: Registry is reset
- **401**: You do not have permission to reset the registry
- **403**: Authentication failed due to invalid or missing AuthenticationToken

### `/artifacts/{artifact_type}/{id}` GET
- **200**: Return the artifact. url is required
- **400**: There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist

### `/artifacts/{artifact_type}/{id}` PUT
- **200**: Artifact is updated
- **400**: There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist

### `/artifacts/{artifact_type}/{id}` DELETE
- **200**: Artifact is deleted
- **400**: There is missing field(s) in the artifact_type or artifact_id or invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist

### `/artifact/{artifact_type}` POST
- **201**: Success. Check the id in the returned metadata for the official ID
- **202**: Artifact ingest accepted but the rating pipeline deferred the evaluation
- **400**: There is missing field(s) in the artifact_data or it is formed improperly (must include a single url)
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **409**: Artifact exists already
- **424**: Artifact is not registered due to the disqualified rating

### `/artifact/model/{id}/rate` GET
- **200**: Return the rating. Only use this if each metric was computed successfully
- **400**: There is missing field(s) in the artifact_id or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist
- **500**: The artifact rating system encountered an error while computing at least one metric

### `/artifact/{artifact_type}/{id}/cost` GET
- **200**: Return the total cost of the artifact, and its dependencies
- **400**: There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist
- **500**: The artifact cost calculator encountered an error

### `/authenticate` PUT
- **200**: Return an AuthenticationToken
- **400**: There is missing field(s) in the AuthenticationRequest or it is formed improperly
- **401**: The user or password is invalid
- **501**: This system does not support authentication

### `/artifact/byName/{name}` GET
- **200**: Return artifact metadata entries that match the provided name
- **400**: There is missing field(s) in the artifact_name or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: No such artifact

### `/artifact/{artifact_type}/{id}/audit` GET
- **200**: Return the audit trail for this artifact
- **400**: There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist

### `/artifact/model/{id}/lineage` GET
- **200**: Lineage graph extracted from structured metadata
- **400**: The lineage graph cannot be computed because the artifact metadata is missing or malformed
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: Artifact does not exist

### `/artifact/model/{id}/license-check` POST
- **200**: License compatibility analysis produced successfully
- **400**: The license check request is malformed or references an unsupported usage context
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: The artifact or GitHub project could not be found
- **502**: External license information could not be retrieved

### `/artifact/byRegEx` POST
- **200**: Return a list of artifacts
- **400**: There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid
- **403**: Authentication failed due to invalid or missing AuthenticationToken
- **404**: No artifact found under this regex

### `/tracks` GET
- **200**: Return the list of tracks the student plans to implement
- **500**: The system encountered an error while retrieving the student's track information

---

## Common Error Patterns

### Authentication Errors (403)
Most endpoints require authentication via the `X-Authorization` header. If authentication fails, all endpoints return:
- **403**: Authentication failed due to invalid or missing AuthenticationToken

### Validation Errors (400)
Most endpoints validate input parameters and return:
- **400**: There is missing field(s) in [field_name] or it is formed improperly, or is invalid

### Not Found Errors (404)
When an artifact is requested but doesn't exist:
- **404**: Artifact does not exist
- **404**: No such artifact (for name-based queries)
- **404**: No artifact found under this regex (for regex searches)

### Server Errors (500)
Internal server errors occur when:
- Rating system encounters errors computing metrics
- Cost calculator encounters errors
- System errors retrieving track information

---

## Notes

- All error responses should include appropriate error details in the response body
- Authentication is required for most endpoints except `/health` and `/health/components`
- The `/authenticate` endpoint may return **501 Not Implemented** if the system doesn't support authentication
- The **202 Accepted** response for artifact creation indicates async processing - subsequent requests may return **404** until processing completes

