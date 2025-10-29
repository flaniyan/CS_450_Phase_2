# ECE 461 - Trustworthy Model Registry API Documentation

**Version:** 3.4.2  
**Base URL:** `https://{api-gateway-id}.execute-api.us-east-1.amazonaws.com/prod`

## Table of Contents

- [Authentication](#authentication)
- [Health Endpoints](#health-endpoints)
- [Artifact Management](#artifact-management)
- [Artifact Operations](#artifact-operations)
- [Search & Discovery](#search--discovery)
- [Error Codes](#error-codes)
- [Complete Examples](#complete-examples)

---

## Authentication

Most endpoints require authentication using the `X-Authorization` header.

### PUT /authenticate

Create an access token for authenticated requests.

**Request:**
```bash
curl -X PUT "https://your-api-url.com/prod/authenticate" \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "name": "ece30861defaultadminuser",
      "is_admin": true
    },
    "secret": {
      "password": "correcthorsebatterystaple123(!__+@**(A'\''\"`;DROP TABLE artifacts;"
    }
  }'
```

**Response (200):**
```json
"bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response Codes:**
- `200` - Token created successfully
- `400` - Missing or malformed fields
- `401` - Invalid credentials
- `501` - Authentication not implemented

**Usage:**
```bash
# Use the token in subsequent requests
curl -X GET "https://your-api-url.com/prod/artifacts" \
  -H "X-Authorization: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Health Endpoints

### GET /health

Lightweight heartbeat check to verify API is reachable.

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/health"
```

**Response (200):**
Service is reachable (may return empty or simple status message)

**Authentication:** Not required

---

### GET /health/components

Get detailed component health diagnostics.

**Query Parameters:**
- `windowMinutes` (optional): Observation window in minutes (5-1440, default: 60)
- `includeTimeline` (optional): Include activity timelines (boolean, default: false)

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/health/components?windowMinutes=60&includeTimeline=false"
```

**Response (200):**
```json
{
  "components": [
    {
      "id": "ingest-worker",
      "display_name": "Ingest Worker",
      "status": "ok",
      "observed_at": "2025-10-28T12:00:00Z",
      "metrics": {
        "requests_processed": 1234,
        "avg_response_time": 0.45
      }
    }
  ],
  "generated_at": "2025-10-28T12:00:00Z",
  "window_minutes": 60
}
```

**Authentication:** Not required

---

## Artifact Management

### POST /artifact/{artifact_type}

Register a new artifact by providing a downloadable URL.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)

**Request Body:**
```json
{
  "url": "https://huggingface.co/google-bert/bert-base-uncased"
}
```

**Request:**
```bash
curl -X POST "https://your-api-url.com/prod/artifact/model" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '{
    "url": "https://huggingface.co/google-bert/bert-base-uncased"
  }'
```

**Response (201):**
```json
{
  "metadata": {
    "name": "bert-base-uncased",
    "id": "9078563412",
    "type": "model"
  },
  "data": {
    "url": "https://huggingface.co/google-bert/bert-base-uncased"
  }
}
```

**Response Codes:**
- `201` - Artifact created successfully
- `400` - Missing or malformed fields
- `403` - Authentication failed
- `409` - Artifact already exists
- `424` - Artifact disqualified due to rating

**Authentication:** Required

---

### GET /artifacts/{artifact_type}/{id}

Retrieve details for a specific artifact.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)
- `id`: Unique artifact identifier

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/artifacts/model/9078563412" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
```json
{
  "metadata": {
    "name": "bert-base-uncased",
    "id": "9078563412",
    "type": "model"
  },
  "data": {
    "url": "https://huggingface.co/google-bert/bert-base-uncased"
  }
}
```

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found

**Authentication:** Required

---

### PUT /artifacts/{artifact_type}/{id}

Update an existing artifact's content.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)
- `id`: Unique artifact identifier

**Request Body:**
```json
{
  "metadata": {
    "name": "bert-base-uncased",
    "id": "9078563412",
    "type": "model"
  },
  "data": {
    "url": "https://huggingface.co/google-bert/bert-base-uncased-v2"
  }
}
```

**Request:**
```bash
curl -X PUT "https://your-api-url.com/prod/artifacts/model/9078563412" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '{
    "metadata": {
      "name": "bert-base-uncased",
      "id": "9078563412",
      "type": "model"
    },
    "data": {
      "url": "https://huggingface.co/google-bert/bert-base-uncased-v2"
    }
  }'
```

**Response (200):**
Artifact updated successfully

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found

**Authentication:** Required

---

### DELETE /artifacts/{artifact_type}/{id}

Delete a specific artifact.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)
- `id`: Unique artifact identifier

**Request:**
```bash
curl -X DELETE "https://your-api-url.com/prod/artifacts/model/9078563412" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
Artifact deleted successfully

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found

**Authentication:** Required

---

### POST /artifacts

List artifacts matching query criteria.

**Query Parameters:**
- `offset` (optional): Pagination offset

**Request Body:**
```json
[
  {
    "name": "*",
    "types": ["model"]
  }
]
```

To list **all** artifacts, use `name: "*"`:
```json
[
  {
    "name": "*"
  }
]
```

**Request:**
```bash
curl -X POST "https://your-api-url.com/prod/artifacts" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '[{"name": "*"}]'
```

**Response (200):**
```json
[
  {
    "name": "bert-base-uncased",
    "id": "9078563412",
    "type": "model"
  },
  {
    "name": "bookcorpus",
    "id": "5738291045",
    "type": "dataset"
  }
]
```

**Response Headers:**
- `offset`: Next pagination offset (e.g., "3")

**Response Codes:**
- `200` - Success
- `400` - Malformed query
- `403` - Authentication failed
- `413` - Too many results

**Authentication:** Required

---

## Artifact Operations

### GET /artifact/model/{id}/rate

Get quality ratings for a model artifact.

**Path Parameters:**
- `id`: Model artifact identifier

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/artifact/model/9078563412/rate" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
```json
{
  "name": "bert-base-uncased",
  "category": "NLP",
  "net_score": 0.85,
  "net_score_latency": 2.3,
  "ramp_up_time": 0.7,
  "ramp_up_time_latency": 1.2,
  "bus_factor": 0.9,
  "bus_factor_latency": 0.8,
  "performance_claims": 0.88,
  "performance_claims_latency": 3.5,
  "license": 0.95,
  "license_latency": 0.5,
  "dataset_and_code_score": 0.82,
  "dataset_and_code_score_latency": 2.1,
  "dataset_quality": 0.80,
  "dataset_quality_latency": 1.8,
  "code_quality": 0.85,
  "code_quality_latency": 1.5,
  "reproducibility": 0.78,
  "reproducibility_latency": 2.0,
  "reviewedness": 0.92,
  "reviewedness_latency": 1.1,
  "tree_score": 0.87,
  "tree_score_latency": 1.9,
  "size_score": {
    "raspberry_pi": 0.2,
    "jetson_nano": 0.5,
    "desktop_pc": 0.9,
    "aws_server": 1.0
  },
  "size_score_latency": 0.7
}
```

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found
- `500` - Rating system error

**Authentication:** Required

---

### GET /artifact/{artifact_type}/{id}/cost

Get the download cost of an artifact in MB.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)
- `id`: Artifact identifier

**Query Parameters:**
- `dependency` (optional): Include dependencies (boolean, default: false)

**Request:**
```bash
# Without dependencies
curl -X GET "https://your-api-url.com/prod/artifact/model/3847247294/cost?dependency=false" \
  -H "X-Authorization: bearer YOUR_TOKEN"

# With dependencies
curl -X GET "https://your-api-url.com/prod/artifact/model/3847247294/cost?dependency=true" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200) - Without Dependencies:**
```json
{
  "3847247294": {
    "total_cost": 412.5
  }
}
```

**Response (200) - With Dependencies:**
```json
{
  "3847247294": {
    "standalone_cost": 412.5,
    "total_cost": 1255.0
  },
  "4628173590": {
    "standalone_cost": 280.0,
    "total_cost": 280.0
  },
  "5738291045": {
    "standalone_cost": 562.5,
    "total_cost": 562.5
  }
}
```

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found
- `500` - Cost calculator error

**Authentication:** Required

---

### GET /artifact/model/{id}/lineage

Retrieve the lineage graph showing dependencies and relationships.

**Path Parameters:**
- `id`: Model artifact identifier

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/artifact/model/3847247294/lineage" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
```json
{
  "nodes": [
    {
      "artifact_id": "3847247294",
      "name": "audience-classifier",
      "source": "config_json"
    },
    {
      "artifact_id": "5738291045",
      "name": "bookcorpus",
      "source": "upstream_dataset"
    }
  ],
  "edges": [
    {
      "from_node_artifact_id": "5738291045",
      "to_node_artifact_id": "3847247294",
      "relationship": "fine_tuning_dataset"
    }
  ]
}
```

**Response Codes:**
- `200` - Success
- `400` - Malformed metadata
- `403` - Authentication failed
- `404` - Artifact not found

**Authentication:** Required

---

### POST /artifact/model/{id}/license-check

Check license compatibility for a model with a GitHub project.

**Path Parameters:**
- `id`: Model artifact identifier

**Request Body:**
```json
{
  "github_url": "https://github.com/google-research/bert"
}
```

**Request:**
```bash
curl -X POST "https://your-api-url.com/prod/artifact/model/9078563412/license-check" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '{
    "github_url": "https://github.com/google-research/bert"
  }'
```

**Response (200):**
```json
true
```

**Response Codes:**
- `200` - Success (returns boolean)
- `400` - Malformed request
- `403` - Authentication failed
- `404` - Artifact or GitHub project not found
- `502` - External license info unavailable

**Authentication:** Required

---

### GET /artifact/{artifact_type}/{id}/audit

Retrieve the audit trail for an artifact.

**Path Parameters:**
- `artifact_type`: Type of artifact (`model`, `dataset`, or `code`)
- `id`: Artifact identifier

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/artifact/model/3847247294/audit" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
```json
[
  {
    "user": {
      "name": "Lina Torres",
      "is_admin": true
    },
    "date": "2024-07-11T14:22:05Z",
    "artifact": {
      "name": "audience-classifier",
      "id": "3847247293",
      "type": "model"
    },
    "action": "CREATE"
  },
  {
    "user": {
      "name": "Casey Morgan",
      "is_admin": false
    },
    "date": "2024-09-02T01:12:30Z",
    "artifact": {
      "name": "audience-classifier",
      "id": "3847247294",
      "type": "model"
    },
    "action": "RATE"
  }
]
```

**Action Types:**
- `CREATE` - Artifact was created
- `UPDATE` - Artifact was updated
- `DOWNLOAD` - Artifact was downloaded
- `RATE` - Artifact was rated
- `AUDIT` - Audit trail was accessed

**Response Codes:**
- `200` - Success
- `400` - Invalid parameters
- `403` - Authentication failed
- `404` - Artifact not found

**Authentication:** Required

---

## Search & Discovery

### GET /artifact/byName/{name}

Search for artifacts by exact name.

**Path Parameters:**
- `name`: Artifact name to search for

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/artifact/byName/audience-classifier" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
```json
[
  {
    "name": "audience-classifier",
    "id": "3847247293",
    "type": "model"
  },
  {
    "name": "audience-classifier",
    "id": "3847247294",
    "type": "model"
  }
]
```

**Response Codes:**
- `200` - Success
- `400` - Invalid name
- `403` - Authentication failed
- `404` - No artifacts found

**Authentication:** Required

---

### POST /artifact/byRegEx

Search for artifacts using regular expressions over names and READMEs.

**Request Body:**
```json
{
  "regex": ".*?(audience|bert).*"
}
```

**Request:**
```bash
curl -X POST "https://your-api-url.com/prod/artifact/byRegEx" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: bearer YOUR_TOKEN" \
  -d '{
    "regex": ".*bert.*"
  }'
```

**Response (200):**
```json
[
  {
    "name": "bert-base-uncased",
    "id": "9078563412",
    "type": "model"
  },
  {
    "name": "audience-classifier",
    "id": "3847247294",
    "type": "model"
  }
]
```

**Response Codes:**
- `200` - Success
- `400` - Invalid regex
- `403` - Authentication failed
- `404` - No matches found

**Authentication:** Required

---

## Utility Endpoints

### DELETE /reset

Reset the entire registry to default state.

**Request:**
```bash
curl -X DELETE "https://your-api-url.com/prod/reset" \
  -H "X-Authorization: bearer YOUR_TOKEN"
```

**Response (200):**
Registry reset successfully

**Response Codes:**
- `200` - Success
- `401` - Insufficient permissions
- `403` - Authentication failed

**Authentication:** Required (Admin only)

**⚠️ WARNING:** This is a destructive operation that deletes all artifacts!

---

### GET /tracks

Get the list of tracks a student plans to implement.

**Request:**
```bash
curl -X GET "https://your-api-url.com/prod/tracks"
```

**Response (200):**
```json
{
  "plannedTracks": [
    "Performance track",
    "Access control track"
  ]
}
```

**Possible Tracks:**
- `"Performance track"`
- `"Access control track"`
- `"High assurance track"`
- `"Other Security track"`

**Response Codes:**
- `200` - Success
- `500` - System error

**Authentication:** Not required

---

## Error Codes

### Common HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `200` | OK | Request succeeded |
| `201` | Created | Resource created successfully |
| `400` | Bad Request | Missing or malformed request fields |
| `401` | Unauthorized | Invalid credentials or insufficient permissions |
| `403` | Forbidden | Authentication failed or missing token |
| `404` | Not Found | Resource does not exist |
| `409` | Conflict | Resource already exists |
| `413` | Payload Too Large | Too many results returned |
| `424` | Failed Dependency | Artifact disqualified (rating too low) |
| `500` | Internal Server Error | System encountered an error |
| `501` | Not Implemented | Feature not available |
| `502` | Bad Gateway | External service unavailable |

### Error Response Format

Most errors return a JSON response with details:

```json
{
  "error": "Artifact not found",
  "code": 404,
  "message": "No artifact exists with ID: 9078563412"
}
```

---

## Complete Examples

### Example 1: Create and Rate a Model

```bash
# 1. Authenticate
TOKEN=$(curl -s -X PUT "https://your-api-url.com/prod/authenticate" \
  -H "Content-Type: application/json" \
  -d '{
    "user": {"name": "ece30861defaultadminuser", "is_admin": true},
    "secret": {"password": "correcthorsebatterystaple123(!__+@**(A'\''\"`;DROP TABLE artifacts;"}
  }' | jq -r '.')

# 2. Create a model artifact
ARTIFACT=$(curl -s -X POST "https://your-api-url.com/prod/artifact/model" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: $TOKEN" \
  -d '{
    "url": "https://huggingface.co/google-bert/bert-base-uncased"
  }')

# 3. Extract artifact ID
ARTIFACT_ID=$(echo "$ARTIFACT" | jq -r '.metadata.id')
echo "Created artifact ID: $ARTIFACT_ID"

# 4. Rate the model
curl -X GET "https://your-api-url.com/prod/artifact/model/$ARTIFACT_ID/rate" \
  -H "X-Authorization: $TOKEN" | jq '.'
```

---

### Example 2: Search and Analyze Artifacts

```bash
# Authenticate
TOKEN="bearer YOUR_TOKEN_HERE"

# Search for BERT models using regex
MODELS=$(curl -s -X POST "https://your-api-url.com/prod/artifact/byRegEx" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: $TOKEN" \
  -d '{"regex": ".*bert.*"}')

echo "$MODELS" | jq '.'

# Get details for first model
FIRST_ID=$(echo "$MODELS" | jq -r '.[0].id')
FIRST_TYPE=$(echo "$MODELS" | jq -r '.[0].type')

# Get lineage (if it's a model)
if [ "$FIRST_TYPE" = "model" ]; then
  curl -s -X GET "https://your-api-url.com/prod/artifact/model/$FIRST_ID/lineage" \
    -H "X-Authorization: $TOKEN" | jq '.'
fi

# Get cost with dependencies
curl -s -X GET "https://your-api-url.com/prod/artifact/$FIRST_TYPE/$FIRST_ID/cost?dependency=true" \
  -H "X-Authorization: $TOKEN" | jq '.'
```

---

### Example 3: List All Artifacts with Pagination

```bash
TOKEN="bearer YOUR_TOKEN_HERE"

# Get first page
RESPONSE=$(curl -s -X POST "https://your-api-url.com/prod/artifacts" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: $TOKEN" \
  -d '[{"name": "*"}]' \
  -i)

# Extract offset from headers
OFFSET=$(echo "$RESPONSE" | grep -i "offset:" | awk '{print $2}' | tr -d '\r')

# Get next page if offset exists
if [ -n "$OFFSET" ]; then
  curl -s -X POST "https://your-api-url.com/prod/artifacts?offset=$OFFSET" \
    -H "Content-Type: application/json" \
    -H "X-Authorization: $TOKEN" \
    -d '[{"name": "*"}]' | jq '.'
fi
```

---

### Example 4: Check License Compatibility

```bash
TOKEN="bearer YOUR_TOKEN_HERE"
MODEL_ID="9078563412"

# Check if model license is compatible with a GitHub project
COMPATIBLE=$(curl -s -X POST "https://your-api-url.com/prod/artifact/model/$MODEL_ID/license-check" \
  -H "Content-Type: application/json" \
  -H "X-Authorization: $TOKEN" \
  -d '{
    "github_url": "https://github.com/google-research/bert"
  }')

if [ "$COMPATIBLE" = "true" ]; then
  echo "✅ License is compatible"
else
  echo "❌ License conflict detected"
fi
```

---

## Notes

### Artifact Types
- `model`: Machine learning models
- `dataset`: Training/evaluation datasets
- `code`: Source code repositories

### Artifact IDs
- IDs are unique across all artifact types
- Multiple artifacts can share the same name but will have different IDs
- Hugging Face models treat each ingest as standalone (no version tracking)

### Best Practices
1. Always check authentication token expiry
2. Handle pagination for large result sets
3. Use regex search for flexible queries
4. Check cost before downloading large artifacts
5. Review lineage graphs to understand dependencies
6. Verify license compatibility before using models in projects

---

## Support

For issues or questions:
- Email: davisjam@purdue.edu
- Documentation: http://davisjam.github.io
- License: Apache 2.0

---

**Last Updated:** October 28, 2025  
**API Version:** 3.4.2