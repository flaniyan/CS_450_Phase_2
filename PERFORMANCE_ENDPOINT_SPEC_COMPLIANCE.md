# Performance Endpoint OpenAPI Spec Compliance

This document verifies that our performance-related endpoints match the OpenAPI specification requirements.

## OpenAPI Spec Requirements

### 1. `/tracks` Endpoint

**Spec Requirement** (line 779-803):
- **Path**: `GET /tracks`
- **Returns**: Object with `plannedTracks` array
- **Format**: `{"plannedTracks": ["Performance track", ...]}`
- **Enum Values**: "Performance track", "Access control track", "High assurance track", "Other Security track"

**Our Implementation**: ✅ COMPLIANT
- Located in: `src/index.py` lines 5121-5139
- Returns: `{"plannedTracks": ["Performance track", "Access control track"]}`
- Matches spec format exactly

### 2. `/health/components` Endpoint

**Spec Requirement** (line 42-72):
- **Path**: `GET /health/components`
- **Query Parameters**: 
  - `windowMinutes` (5-1440, default: 60)
  - `includeTimeline` (boolean, default: false)
- **Returns**: `HealthComponentCollection` schema
- **Purpose**: "Return per-component health diagnostics, including status, active issues, and log references. Use this endpoint to power deeper observability dashboards"

**Our Implementation**: ✅ COMPLIANT
- Located in: `src/index.py` lines 838-920
- Accepts `windowMinutes` and `includeTimeline` parameters
- Returns array of components including:
  - `validator-service` component
  - `performance` component (added per assignment requirements)
- Format matches `HealthComponentCollection` schema
- Performance component includes metrics and can be accessed from health dashboard

**Performance Component Details**:
- **id**: "performance"
- **display_name**: "Performance Testing"
- **status**: "ok" | "unknown" | "degraded" | "critical"
- **description**: Explains performance testing functionality
- **metrics**: Latest performance run metrics (if available)
- **Endpoints referenced**: 
  - `POST /health/performance/workload` - Trigger workload
  - `GET /health/performance/results/{run_id}` - Get results

### 3. Performance Workload Endpoints

**Note**: The OpenAPI spec does not explicitly define performance workload endpoints. These are implementation details for the Performance Track assignment requirement that the "workload should be triggerable from your team's system health dashboard."

**Our Implementation**: ✅ COMPLIES WITH ASSIGNMENT REQUIREMENT
- **Trigger Endpoint**: `POST /health/performance/workload`
  - Located in: `src/index.py` lines 737-795
  - Accepts workload configuration (num_clients, model_id, duration_seconds)
  - Returns `run_id` and status
  - Returns 202 (Accepted) status code
  - Executes workload asynchronously

- **Results Endpoint**: `GET /health/performance/results/{run_id}`
  - Located in: `src/index.py` lines 798-835
  - Returns aggregated performance metrics for a run
  - Returns 404 if run not found
  - Returns 200 with metrics if available

**Integration with Health Dashboard**:
- Performance component in `/health/components` references these endpoints
- Dashboard can display performance status and trigger workloads
- Meets assignment requirement: "This workload should be triggerable from your team's system health dashboard"

## Endpoint Summary

| Endpoint | Method | Spec Status | Purpose |
|----------|--------|-------------|---------|
| `/tracks` | GET | ✅ In Spec | Returns planned tracks including "Performance track" |
| `/health/components` | GET | ✅ In Spec | Returns component health including performance component |
| `/health/performance/workload` | POST | 📝 Assignment Req | Trigger performance workload (accessible from health dashboard) |
| `/health/performance/results/{run_id}` | GET | 📝 Assignment Req | Get performance workload results |

## Verification Checklist

- [x] `/tracks` endpoint exists and returns `plannedTracks` array
- [x] `/tracks` includes "Performance track" in the array
- [x] `/health/components` endpoint exists and matches spec format
- [x] `/health/components` includes performance component
- [x] Performance component describes workload trigger endpoints
- [x] Performance workload is triggerable from health dashboard (via component description and metrics)
- [x] All endpoints follow OpenAPI spec response formats
- [x] Error handling matches spec requirements

## Testing

All endpoints have been tested and verified:
- See `tests/integration/test_performance_workload_setup.py`
- See `tests/integration/test_performance_end_to_end.py`
- See `tests/integration/test_performance_workload_setup.py::TestTracksEndpoint`

