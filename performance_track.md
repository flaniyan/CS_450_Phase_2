# Performance Track Implementation Plan

## Overview

This document outlines the plan for implementing performance measurement capabilities for the ACME Model Registry. The goal is to measure system performance under load (100 concurrent clients downloading Tiny-LLM from a registry with 500 models) and experiment with different AWS component configurations.

## Architecture Context

**Current System:**
- **Compute**: ECS Fargate (FastAPI service)
- **Storage**: S3 (model files) + DynamoDB (metadata)
- **API**: API Gateway → ECS Service
- **Monitoring**: CloudWatch (metrics, logs, dashboards)
- **Download Endpoint**: `/models/{model_id}/{version}/model.zip`

## Experimental Design

### Phase 1: Workload Setup

#### 1.1 Model Registry Population
- **Goal**: Ensure 500 distinct models exist in the registry
- **Implementation**: 
  - Create a script `scripts/populate_registry.py` that:
    - Ingest Tiny-LLM model (`arnir0/Tiny-LLM`) from HuggingFace
    - Create 499 additional dummy model entries (metadata-only) in DynamoDB
    - Store Tiny-LLM model file in S3 at `models/arnir0_Tiny-LLM/{version}/model.zip`
- **Minimal Code Change**: Script only, no service changes

#### 1.2 Performance Workload Trigger
- **Goal**: Add endpoint to system health dashboard to trigger workload (aligned with OpenAPI spec)
- **Implementation**:
  - Add endpoint `POST /health/performance/workload` to `src/routes/system.py` (or integrate into health routes)
  - Accept parameters in request body:
    ```json
    {
      "num_clients": 100,
      "model_id": "arnir0/Tiny-LLM",
      "artifact_id": "optional-artifact-id",
      "duration_seconds": 300
    }
    ```
  - Use background task (FastAPI BackgroundTasks) to coordinate load generation
  - Return job ID and status for tracking progress:
    ```json
    {
      "run_id": "uuid",
      "status": "started",
      "estimated_completion": "iso8601-timestamp"
    }
    ```
  - **CRITICAL**: Update `/tracks` endpoint in `src/routes/system.py` to return:
    ```json
    {
      "plannedTracks": ["Performance track", "access-control", "reproducibility", "reviewedness", "security"]
    }
    ```
    This ensures compliance with OpenAPI spec requirement that `/tracks` returns planned tracks including "Performance track"
- **Minimal Code Change**: Single route addition (~50 lines) + tracks endpoint update (~5 lines)
- **Testing**: See Phase 1 Testing section

#### 1.3 Load Generation Client
- **Goal**: Generate 100 concurrent download requests
- **Implementation**:
  - Create `src/services/performance/load_generator.py`:
    - Use `asyncio` and `aiohttp` for concurrent requests
    - Track timing metrics per request (start, end, latency)
    - Store raw metrics in temporary storage (local file or DynamoDB table)
  - Metrics collected per request:
    - Request timestamp
    - Response time (latency)
    - Response status code
    - Bytes transferred (from Content-Length header)
    - Client ID (1-100)
- **Minimal Code Change**: New service module (~150 lines)

### Phase 2: Measurement Infrastructure

#### 2.1 Black-Box Metrics Collection
- **Goal**: Measure throughput and latency from external perspective
- **Implementation**:
  - In load generator, collect:
    - **Throughput**: Total bytes transferred / total time window
    - **Latency**: Time from request start to response complete
    - Calculate: mean, median, 99th percentile
  - Export metrics to CloudWatch custom metrics namespace: `ACME/Performance`
  - Also store raw metrics in DynamoDB table `performance_metrics` for analysis
- **Metrics Schema**:
  ```json
  {
    "run_id": "uuid",
    "timestamp": "iso8601",
    "client_id": 1-100,
    "request_latency_ms": float,
    "bytes_transferred": int,
    "status_code": int
  }
  ```
- **Minimal Code Change**: Metrics storage logic in load generator (~100 lines)

#### 2.2 White-Box Metrics Collection
- **Goal**: Instrument system components to understand bottlenecks
- **Implementation**:
  - Add CloudWatch custom metrics to existing services:
    - **S3 Service** (`src/services/s3_service.py`):
      - `ACME/Performance/S3DownloadLatency` (time to get_object)
      - `ACME/Performance/S3DownloadBytes`
    - **API Gateway**:
      - Use existing CloudWatch API Gateway metrics
      - Latency, integration latency, response time
    - **DynamoDB**:
      - Use existing CloudWatch DynamoDB metrics
      - Read/Write capacity consumption
    - **ECS Service**:
      - Add custom metrics via CloudWatch SDK:
        - `ACME/Performance/RequestProcessingTime` (time in FastAPI handler)
        - `ACME/Performance/ConcurrentRequests` (gauge)
  - Add logging with correlation IDs for request tracing
- **Minimal Code Change**: 
  - Add timing decorators/wrappers (~50 lines)
  - Instrument download_model function (~20 lines)

#### 2.3 Results Reporting
- **Goal**: Aggregate and display performance results
- **Implementation**:
  - Add endpoint `GET /health/performance/results/{run_id}` to `src/routes/system.py`
  - Query DynamoDB `performance_metrics` table
  - Calculate statistics:
    - Throughput (requests/sec, bytes/sec)
    - Mean latency (milliseconds)
    - Median latency (milliseconds)
    - 99th percentile latency (milliseconds)
    - Min/Max latency (milliseconds)
    - Error rate (percentage)
    - Total requests processed
    - Total bytes transferred
  - Return JSON response with all metrics:
    ```json
    {
      "run_id": "uuid",
      "status": "completed",
      "started_at": "iso8601",
      "completed_at": "iso8601",
      "metrics": {
        "throughput": {
          "requests_per_second": float,
          "bytes_per_second": float
        },
        "latency": {
          "mean_ms": float,
          "median_ms": float,
          "p99_ms": float,
          "min_ms": float,
          "max_ms": float
        },
        "error_rate": float,
        "total_requests": int,
        "total_bytes": int
      }
    }
    ```
  - Optionally create CloudWatch dashboard widget for visualization
- **Minimal Code Change**: Single route with statistics calculation (~80 lines)
- **Testing**: See Phase 2 Testing section

### Phase 3: Bottleneck Identification

#### 3.1 Performance Profiling Strategy
- **Goal**: Identify at least 2 performance bottlenecks
- **Methodology**:
  1. **Baseline Measurement**: Run workload, collect all metrics
  2. **Component-Level Analysis**: 
     - Compare time spent in each component (API Gateway → ECS → S3)
     - Check CloudWatch metrics for each service
     - Analyze DynamoDB read/write patterns
  3. **Statistical Analysis**:
     - Identify component with highest latency variance
     - Identify component with highest time contribution
     - Check for correlation between errors and component
  4. **Resource Utilization**:
     - ECS CPU/Memory utilization
     - S3 request rate limits
     - DynamoDB throttling
     - Network throughput

#### 3.2 Expected Bottlenecks (Hypotheses)
1. **S3 Download Bottleneck**:
   - Large file download through ECS service (streaming vs direct)
   - S3 request rate limits
   - Network bandwidth
   - **Detection**: High `ACME/Performance/S3DownloadLatency`, low throughput
   
2. **ECS Concurrency Bottleneck**:
   - Fargate task limited to single container instance
   - Thread/async concurrency limits
   - Memory constraints for concurrent downloads
   - **Detection**: High `ACME/Performance/RequestProcessingTime`, CPU saturation

3. **DynamoDB Metadata Lookup**:
   - Cold start / caching issues
   - Read capacity throttling
   - **Detection**: High DynamoDB latency in CloudWatch

### Phase 4: Optimization Implementation

#### 4.1 Optimization Strategy
- **Goal**: Implement optimizations for identified bottlenecks
- **Process**:
  1. Document baseline metrics
  2. Implement optimization
  3. Re-run workload with same parameters
  4. Compare metrics (before/after)
  5. Document effect

#### 4.2 Optimization Options (Examples)

**Optimization 1: S3 Presigned URLs (Direct Download)**
- **Problem**: Models streamed through ECS service add latency
- **Solution**: 
  - Modify `/models/{model_id}/{version}/model.zip` to return presigned S3 URL
  - Clients download directly from S3 (bypass ECS)
  - Keep ECS only for authorization/validation
- **Expected Effect**: 
  - Reduced ECS CPU/memory usage
  - Lower latency (direct S3 connection)
  - Higher throughput (S3 scales better)
- **Code Change**: Modify download endpoint (~30 lines)

**Optimization 2: ECS Auto-Scaling**
- **Problem**: Single Fargate task cannot handle 100 concurrent requests
- **Solution**:
  - Add ECS auto-scaling based on CPU/Memory metrics
  - Configure target tracking scaling policy
  - Minimum: 2 tasks, Maximum: 10 tasks
- **Expected Effect**:
  - Better request distribution
  - Lower latency under load
  - Higher throughput
- **Code Change**: Terraform update to ECS module (~20 lines)

**Optimization 3: DynamoDB Caching**
- **Problem**: Repeated metadata lookups for same model
- **Solution**:
  - Add in-memory cache (TTL-based) for model metadata
  - Use `functools.lru_cache` or Redis (if available)
- **Expected Effect**:
  - Reduced DynamoDB read costs
  - Lower latency for cached lookups
- **Code Change**: Add caching decorator (~30 lines)

**Optimization 4: Connection Pooling**
- **Problem**: New S3/boto3 connections for each request
- **Solution**:
  - Reuse boto3 client (already done, but verify)
  - Use connection pooling for HTTP requests
- **Expected Effect**:
  - Reduced connection overhead
  - Slightly lower latency
- **Code Change**: Verify/optimize boto3 client usage (~10 lines)

### Phase 5: Component Comparison Experiments

#### 5.1 Compute Component Comparison (Lambda vs EC2/ECS)
- **Goal**: Measure performance difference between Lambda and ECS Fargate
- **Implementation**:
  - Create alternative Lambda-based download handler
  - Deploy both architectures in parallel
  - Add configuration flag to route requests to Lambda or ECS
  - Run same workload against both
  - Compare: latency, throughput, cost, cold start times
- **Configuration**:
  - Add environment variable `USE_LAMBDA_DOWNLOADS=true/false`
  - If true, API Gateway routes to Lambda instead of ECS
- **Minimal Code Change**:
  - Create Lambda function (new file: `lambda/download_handler.py`)
  - Modify API Gateway Terraform to include Lambda integration
  - Add feature flag in routing logic (~50 lines total)

#### 5.2 Storage Component Comparison (S3 vs Relational Database)
- **Goal**: Compare S3 (object store) vs RDS (relational DB) for model storage
- **Implementation**:
  - Create RDS PostgreSQL instance for model storage
  - Store model files as BYTEA or use RDS large object storage
  - Add configuration flag to select storage backend
  - Run same workload against both
  - Compare: latency, throughput, scalability, cost
- **Note**: This is somewhat artificial since RDS is not ideal for large binary files, but useful for comparison
- **Configuration**:
  - Add environment variable `STORAGE_BACKEND=s3|rds`
  - Modify `s3_service.py` to support both backends
- **Minimal Code Change**:
  - Add RDS module to Terraform
  - Create storage abstraction layer (~100 lines)
  - Add RDS backend implementation (~150 lines)

#### 5.3 Configuration Management
- **Goal**: Make component selection configurable
- **Implementation**:
  - Add configuration file `config/performance_config.json`:
    ```json
    {
      "compute_backend": "ecs|lambda",
      "storage_backend": "s3|rds",
      "enable_caching": true,
      "enable_presigned_urls": true
    }
    ```
  - Load configuration at service startup
  - Route requests based on configuration
- **Minimal Code Change**: Configuration loader (~30 lines)

### Phase 6: Testing Requirements

##
THERE NEEDS TO BE A NUKING OF ALL DATA CREATED DURING RESET ENDPOINT
##

#### 6.1 Phase 1: Workload Setup Testing

**Test Suite**: `tests/integration/test_performance_workload_setup.py`

**Test Cases**:
1. **Test Registry Population Script**
   - `test_populate_registry_creates_500_models()`:
     - Verify script creates exactly 500 model entries
     - Verify Tiny-LLM model is ingested correctly
     - Verify 499 dummy models have metadata in DynamoDB
     - Verify Tiny-LLM model file exists in S3
   - `test_populate_registry_idempotent()`:
     - Verify script can be run multiple times without errors
     - Verify no duplicate models are created
   - `test_populate_registry_tiny_llm_downloadable()`:
     - Verify Tiny-LLM model can be downloaded after ingestion
     - Verify download returns valid ZIP file

2. **Test Performance Workload Trigger Endpoint**
   - `test_performance_workload_endpoint_exists()`:
     - Verify `POST /health/performance/workload` endpoint exists
     - Verify endpoint returns 200 status code
     - Verify response contains `run_id` field
   - `test_performance_workload_accepts_parameters()`:
     - Test with default parameters (num_clients=100)
     - Test with custom num_clients parameter
     - Test with custom model_id parameter
     - Test with invalid parameters (negative clients, missing model)
   - `test_performance_workload_returns_job_id()`:
     - Verify returned run_id is valid UUID
     - Verify status field is present
   - `test_performance_workload_starts_background_task()`:
     - Verify background task is actually started
     - Verify load generator begins making requests
     - Use mocking to verify load generator is called

3. **Test Load Generator**
   - `test_load_generator_creates_100_clients()`:
     - Verify load generator creates exactly 100 concurrent clients
     - Verify each client has unique ID (1-100)
   - `test_load_generator_makes_download_requests()`:
     - Verify load generator makes requests to correct download endpoint
     - Verify requests use proper authentication headers
     - Mock HTTP requests to avoid actual downloads
   - `test_load_generator_tracks_timing_metrics()`:
     - Verify each request records start timestamp
     - Verify each request records end timestamp
     - Verify latency is calculated correctly
   - `test_load_generator_handles_errors()`:
     - Verify failed requests are tracked separately
     - Verify error status codes are recorded
     - Verify load generator continues after individual failures

**Unit Tests**: `tests/unit/test_performance_load_generator.py`
- Test metrics collection functions
- Test concurrent request handling
- Test statistics calculations

#### 6.2 Phase 2: Measurement Infrastructure Testing

**Test Suite**: `tests/integration/test_performance_metrics.py`

**Test Cases**:
1. **Test Black-Box Metrics Collection**
   - `test_metrics_stored_in_dynamodb()`:
     - Run workload, verify metrics written to `performance_metrics` table
     - Verify all required fields are present (run_id, timestamp, client_id, latency, etc.)
     - Verify 100 metrics entries exist (one per client)
   - `test_metrics_sent_to_cloudwatch()`:
     - Verify custom metrics appear in CloudWatch namespace `ACME/Performance`
     - Verify metrics have correct dimensions
     - Use CloudWatch client to query metrics
   - `test_throughput_calculation()`:
     - Calculate throughput from stored metrics
     - Verify throughput formula: total_bytes / total_time
     - Test with known sample data
   - `test_latency_percentiles()`:
     - Calculate mean, median, 99th percentile from sample data
     - Verify calculations match expected values
     - Test edge cases (single request, all same latency, etc.)

2. **Test White-Box Metrics Collection**
   - `test_s3_download_instrumentation()`:
     - Verify S3 download operations emit `ACME/Performance/S3DownloadLatency` metrics
     - Verify timing is captured correctly
     - Mock S3 calls to verify instrumentation
   - `test_ecs_request_instrumentation()`:
     - Verify FastAPI handlers emit `ACME/Performance/RequestProcessingTime` metrics
     - Verify concurrent request count is tracked
     - Use middleware/interceptor to verify metrics
   - `test_dynamodb_metrics_available()`:
     - Verify DynamoDB metrics are accessible in CloudWatch
     - Query for read/write capacity metrics
     - Verify no throttling occurs during workload

3. **Test Results Reporting Endpoint**
   - `test_results_endpoint_returns_metrics()`:
     - Run workload, wait for completion
     - Call `GET /health/performance/results/{run_id}`
     - Verify all metric fields are present
   - `test_results_calculations_accurate()`:
     - Compare endpoint results with manual calculations
     - Verify throughput matches expected value
     - Verify latency percentiles match manual calculation
   - `test_results_endpoint_handles_missing_run()`:
     - Request results for non-existent run_id
     - Verify 404 status code returned
   - `test_results_endpoint_handles_in_progress()`:
     - Request results while workload is still running
     - Verify status indicates "in_progress"
     - Verify partial metrics are returned if available

**Unit Tests**: `tests/unit/test_performance_statistics.py`
- Test percentile calculation functions
- Test throughput calculation
- Test metric aggregation functions

#### 6.3 Phase 3: Bottleneck Identification Testing

**Test Suite**: `tests/integration/test_performance_bottlenecks.py`

**Test Cases**:
1. **Test Baseline Measurement**
   - `test_baseline_workload_completes()`:
     - Run full 100-client workload
     - Verify all requests complete (success or error)
     - Verify baseline metrics are captured
   - `test_baseline_metrics_recorded()`:
     - Verify all component metrics are collected
     - Verify CloudWatch metrics are available
     - Verify no missing data points

2. **Test Bottleneck Detection**
   - `test_component_latency_analysis()`:
     - Compare latencies across components (API Gateway, ECS, S3, DynamoDB)
     - Verify highest latency component is identified
     - Test with mock data showing clear bottleneck
   - `test_resource_utilization_tracking()`:
     - Verify CPU utilization is tracked for ECS
     - Verify memory utilization is tracked
     - Verify S3 request rates are tracked
     - Verify DynamoDB capacity consumption is tracked
   - `test_statistical_analysis()`:
     - Test variance calculation across components
     - Test correlation analysis between errors and components
     - Verify bottleneck hypotheses can be validated

**Validation Tests**:
- Manual validation: Run workload and manually inspect CloudWatch dashboards
- Verify identified bottlenecks match expected components
- Document evidence for each identified bottleneck

#### 6.4 Phase 4: Optimization Testing

**Test Suite**: `tests/integration/test_performance_optimizations.py`

**Test Cases**:
1. **Test Optimization 1: S3 Presigned URLs**
   - `test_presigned_url_endpoint_exists()`:
     - Verify download endpoint can return presigned URL
     - Verify URL is valid and accessible
   - `test_presigned_url_performance()`:
     - Run workload with presigned URLs enabled
     - Compare metrics to baseline
     - Verify latency improvement
     - Verify throughput improvement
   - `test_presigned_url_functionality()`:
     - Verify presigned URLs actually work
     - Verify download completes successfully
     - Verify authentication is still enforced

2. **Test Optimization 2: ECS Auto-Scaling**
   - `test_auto_scaling_configuration()`:
     - Verify auto-scaling policy is configured
     - Verify min/max task counts are set correctly
   - `test_auto_scaling_triggers()`:
     - Run workload, verify additional tasks are launched
     - Verify tasks scale back down after workload completes
   - `test_auto_scaling_performance()`:
     - Compare metrics before/after auto-scaling
     - Verify latency improves with more tasks
     - Verify no performance degradation during scaling

3. **Test Optimization 3: DynamoDB Caching**
   - `test_cache_functionality()`:
     - Verify cache returns cached data on second request
     - Verify cache TTL works correctly
     - Verify cache invalidation works
   - `test_cache_performance()`:
     - Compare DynamoDB read latency with/without cache
     - Verify cache reduces DynamoDB read capacity consumption
   - `test_cache_consistency()`:
     - Verify cached data is consistent
     - Verify cache doesn't serve stale data incorrectly

4. **Test Overall Optimization Effect**
   - `test_optimized_workload_improvements()`:
     - Run workload with all optimizations enabled
     - Compare to baseline metrics
     - Verify at least 20% improvement in key metrics
     - Document specific improvements per optimization

#### 6.5 Phase 5: Component Comparison Testing

**Test Suite**: `tests/integration/test_performance_component_comparison.py`

**Test Cases**:
1. **Test Lambda vs ECS Comparison**
   - `test_lambda_endpoint_available()`:
     - Verify Lambda-based download endpoint exists
     - Verify configuration flag works (USE_LAMBDA_DOWNLOADS)
   - `test_lambda_performance()`:
     - Run workload against Lambda endpoint
     - Record all performance metrics
     - Compare to ECS baseline
   - `test_lambda_cold_start()`:
     - Measure cold start latency for Lambda
     - Verify cold start impact on first request
   - `test_lambda_vs_ecs_comparison()`:
     - Run same workload on both
     - Compare latency, throughput, cost
     - Document trade-offs

2. **Test S3 vs RDS Comparison**
   - `test_rds_storage_backend()`:
     - Verify RDS backend is configured
     - Verify models can be stored in RDS
     - Verify models can be retrieved from RDS
   - `test_rds_performance()`:
     - Run workload with RDS storage backend
     - Record all performance metrics
     - Compare to S3 baseline
   - `test_storage_backend_switching()`:
     - Verify configuration flag works (STORAGE_BACKEND)
     - Verify both backends work independently
   - `test_s3_vs_rds_comparison()`:
     - Run same workload on both storage backends
     - Compare latency, throughput, scalability
     - Document trade-offs and use cases

**Comparison Report Tests**:
- Generate automated comparison reports
- Verify all metrics are included in comparison
- Verify differences are statistically significant

#### 6.6 Integration Testing

**Test Suite**: `tests/integration/test_performance_end_to_end.py`

**Test Cases**:
1. **End-to-End Performance Workflow**
   - `test_full_performance_workflow()`:
     - Trigger workload via endpoint
     - Wait for completion
     - Retrieve results
     - Verify all metrics are present
     - Verify results are consistent with expectations

2. **Multiple Workload Runs**
   - `test_multiple_concurrent_workloads()`:
     - Trigger multiple workloads simultaneously
     - Verify each has unique run_id
     - Verify results don't interfere with each other

3. **Error Handling**
   - `test_workload_error_handling()`:
     - Test with invalid model_id
     - Test with service unavailable
     - Verify errors are caught and reported
     - Verify partial results are still available

**Test Coverage Requirements**:
- All endpoints must have at least 80% code coverage
- All critical paths must have tests
- Integration tests must run against staging environment
- Unit tests must run in CI/CD pipeline

**Performance Test Benchmarks**:
- Workload trigger endpoint should respond in < 1 second
- Results endpoint should respond in < 2 seconds (even with 100 requests)
- Load generator should complete 100 requests in < 5 minutes
- Metrics collection should not add > 10% overhead

### Phase 7: Documentation and Reporting

#### 7.1 Performance Report Template
- Create report structure:
  1. **Experimental Setup**
     - Workload description
     - Infrastructure configuration
     - Measurement methodology
  2. **Baseline Metrics**
     - Throughput, latency (mean/median/99th percentile)
     - Resource utilization
     - Error rates
  3. **Bottleneck Analysis**
     - Identification method
     - Bottleneck #1: Description, evidence, impact
     - Bottleneck #2: Description, evidence, impact
  4. **Optimizations**
     - Optimization #1: Changes, effect, metrics
     - Optimization #2: Changes, effect, metrics
  5. **Component Comparisons**
     - Lambda vs ECS: Metrics, trade-offs
     - S3 vs RDS: Metrics, trade-offs
  6. **Conclusions**
     - Key findings
     - Recommendations

#### 7.2 Dashboard Integration
- **Goal**: Display performance results in system health dashboard
- **Implementation**:
  - Integrate performance metrics into `/health/components` endpoint
  - Add performance component to health component collection:
    ```json
    {
      "id": "performance",
      "display_name": "Performance Testing",
      "status": "ok|degraded|critical",
      "metrics": {
        "latest_run_id": "uuid",
        "latest_throughput": float,
        "latest_p99_latency": float,
        "total_runs": int
      }
    }
    ```
  - Add performance section to frontend dashboard
  - Show latest run results
  - Visualize latency distribution (histogram)
  - Show throughput over time
  - Compare component configurations side-by-side
- **Minimal Code Change**: Frontend template update (~100 lines)
- **Testing**: 
  - Test `/health/components` includes performance component
  - Test frontend displays performance metrics correctly
  - Test dashboard updates when new workload completes

## Implementation Timeline

### Week 1: Setup & Baseline
- Day 1-2: Workload trigger endpoint (`POST /health/performance/workload`) + load generator
- Day 2-3: Write Phase 1 tests (registry population, workload trigger, load generator)
- Day 3-4: Metrics collection (black-box + white-box)
- Day 4-5: Write Phase 2 tests (metrics collection, results endpoint)
- Day 5: Baseline measurement run + test execution

### Week 2: Analysis & Optimization
- Day 1: Write Phase 3 tests (bottleneck identification)
- Day 1-2: Bottleneck identification + validation
- Day 2-3: Write Phase 4 tests (optimization testing)
- Day 3-4: Implement 2+ optimizations
- Day 4-5: Re-measure, document effects, run optimization tests

### Week 3: Component Comparison
- Day 1: Write Phase 5 tests (component comparison)
- Day 1-2: Lambda vs ECS setup
- Day 2-3: Run Lambda vs ECS comparisons + tests
- Day 3-5: S3 vs RDS setup, comparison, and testing

### Week 4: Documentation & Dashboard
- Day 1: Write integration tests (end-to-end workflow)
- Day 1-2: Performance report
- Day 2-3: Dashboard integration (`/health/components` update)
- Day 3-4: Final testing and validation (all test suites)
- Day 5: Documentation review and test coverage verification

## File Structure

```
Dev-ACME/
├── scripts/
│   └── populate_registry.py          # NEW: Populate 500 models
├── tests/
│   ├── integration/
│   │   ├── test_performance_workload_setup.py      # NEW: Phase 1 tests
│   │   ├── test_performance_metrics.py             # NEW: Phase 2 tests
│   │   ├── test_performance_bottlenecks.py         # NEW: Phase 3 tests
│   │   ├── test_performance_optimizations.py       # NEW: Phase 4 tests
│   │   ├── test_performance_component_comparison.py # NEW: Phase 5 tests
│   │   └── test_performance_end_to_end.py          # NEW: Integration tests
│   └── unit/
│       ├── test_performance_load_generator.py      # NEW: Unit tests
│       └── test_performance_statistics.py          # NEW: Statistics tests
├── src/
│   ├── routes/
│   │   └── system.py                 # MODIFY: Add performance endpoints
│   ├── services/
│   │   ├── s3_service.py             # MODIFY: Add instrumentation
│   │   └── performance/              # NEW: Performance module
│   │       ├── __init__.py
│   │       ├── load_generator.py     # Load generation client
│   │       ├── metrics_collector.py  # Metrics aggregation
│   │       └── statistics.py         # Statistical calculations
│   └── lambda/                       # NEW: Lambda functions
│       └── download_handler.py       # Lambda download handler
├── infra/
│   ├── modules/
│   │   ├── ecs/
│   │   │   └── main.tf               # MODIFY: Add auto-scaling
│   │   ├── lambda/                   # NEW: Lambda module
│   │   │   └── main.tf
│   │   └── rds/                      # NEW: RDS module
│   │       └── main.tf
│   └── envs/
│       └── dev/
│           └── main.tf               # MODIFY: Add Lambda/RDS resources
└── config/
    └── performance_config.json       # NEW: Performance configuration
```

## Key Principles

1. **Minimal Code Changes**: Reuse existing infrastructure, add new modules instead of modifying core logic extensively
2. **Configuration-Driven**: Use environment variables and config files to switch between components
3. **Instrumentation First**: Add metrics collection before optimization to establish baseline
4. **Incremental**: Implement one optimization at a time to measure individual effects
5. **Reproducible**: Ensure all experiments can be re-run with same parameters
6. **Documented**: Maintain clear documentation of changes and results

## Success Criteria

✅ **Endpoints match OpenAPI spec:**
- `POST /health/performance/workload` - trigger workload
- `GET /health/performance/results/{run_id}` - get results
- `GET /tracks` returns `["Performance track"]` in `plannedTracks`
- Performance metrics integrated into `/health/components`

✅ **Workload execution:**
- 100 concurrent clients downloading Tiny-LLM from 500-model registry
- Workload triggerable from system health dashboard

✅ **Metrics collection:**
- Measurements: throughput, mean/median/99th percentile latency
- Black-box metrics (external perspective)
- White-box metrics (internal component instrumentation)

✅ **Bottleneck analysis:**
- At least 2 bottlenecks identified with evidence
- Evidence includes statistical analysis and component-level metrics

✅ **Optimizations:**
- At least 2 optimizations implemented
- Measured effects documented (before/after metrics)
- Optimizations validated through testing

✅ **Component comparisons:**
- Lambda vs ECS comparison with measurements
- S3 vs RDS comparison with measurements
- Trade-offs documented

✅ **Testing:**
- All phases have comprehensive test suites
- Test coverage ≥ 80% for all performance code
- All tests pass in CI/CD pipeline
- Integration tests validate end-to-end workflow

✅ **Documentation:**
- Performance report documenting all findings
- Test documentation included
- API endpoint documentation matches OpenAPI spec

