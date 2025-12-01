# Performance Track: Remaining Tasks

## Overview

This document tracks remaining tasks for the Performance Track requirements. The baseline performance measurement and bottleneck optimization work has been completed. See `PERFORMANCE_BOTTLENECKS.md` for detailed documentation of completed work.

## Completed Work ✅

### Baseline Requirements
- ✅ Registry populated with 500 distinct models (Tiny-LLM + 499 additional models)
- ✅ Performance workload trigger endpoint (`POST /health/performance/workload`) accessible from health dashboard
- ✅ Load generator implemented (100 concurrent clients)
- ✅ Performance measurements collected:
  - Throughput: 37.48 MB/sec
  - Mean latency: 51.26 seconds
  - Median latency: 52.93 seconds
  - P99 latency: 63.17 seconds

### Bottleneck Identification & Optimization
- ✅ Identified 3 performance bottlenecks:
  1. Synchronous endpoint blocking event loop
  2. Insufficient thread pool capacity
  3. S3 connection pool size limitation
- ✅ Implemented optimizations for all 3 bottlenecks
- ✅ Measured and documented effects (100% success rate, 83% latency reduction)
- ✅ Complete documentation in `PERFORMANCE_BOTTLENECKS.md`

---

## Remaining Tasks

### 1. Component Comparison: Lambda vs EC2/ECS

**Requirement**: Experiment with the effect of different AWS compute components on performance (e.g., Lambdas vs. EC2/ECS).

**Tasks**:
- [x] Create Lambda-based download handler function
  - [x] Implement Lambda function that handles model downloads
  - [x] Store Lambda function code in `src/lambda/download_handler.py` or similar
  - [x] Configure Lambda IAM permissions for S3 access
- [ ] Make compute backend configurable
  - [ ] Add environment variable `COMPUTE_BACKEND=ecs|lambda`
  - [ ] Modify routing logic to select compute backend
  - [ ] Ensure same endpoint works with both backends
- [ ] Deploy Lambda function via Terraform
  - [ ] Create Lambda module in `infra/modules/lambda/`
  - [ ] Configure Lambda integration with API Gateway
  - [ ] Add feature flag/configuration to switch between ECS and Lambda
- [ ] Run performance tests with Lambda backend
  - [ ] Run same workload (100 concurrent clients, Tiny-LLM download)
  - [ ] Measure latency (mean, median, P99)
  - [ ] Measure throughput
  - [ ] Compare to ECS baseline measurements
- [ ] Document Lambda vs ECS comparison
  - [ ] Document latency differences
  - [ ] Document throughput differences
  - [ ] Document cold start impact (if any)
  - [ ] Document cost trade-offs
  - [ ] Create comparison table/section

**Estimated Effort**: 2-3 days

**Files to Create/Modify**:
- `src/lambda/download_handler.py` (new)
- `infra/modules/lambda/main.tf` (new)
- `src/routes/packages.py` (modify - add backend selection logic)
- `infra/envs/dev/main.tf` (modify - add Lambda resource)

---

### 2. Component Comparison: Object Store (S3) vs Relational Database (RDS)

**Requirement**: Experiment with the effect of different storage backends on performance (object store vs. relational database).

**Tasks**:
- [ ] Create RDS PostgreSQL instance
  - [ ] Create RDS module in `infra/modules/rds/`
  - [ ] Configure RDS instance for model storage
  - [ ] Consider storage method: BYTEA or large object storage
- [ ] Implement RDS storage backend
  - [ ] Create storage abstraction layer
  - [ ] Implement RDS backend for model storage
  - [ ] Store model files in RDS (as BYTEA or use RDS large object features)
  - [ ] Implement RDS backend for model retrieval
- [ ] Make storage backend configurable
  - [ ] Add environment variable `STORAGE_BACKEND=s3|rds`
  - [ ] Modify `s3_service.py` or create storage abstraction
  - [ ] Route storage operations based on configuration
- [ ] Populate RDS with test data
  - [ ] Upload Tiny-LLM model to RDS
  - [ ] Ensure 500 models metadata in database
  - [ ] Verify model can be retrieved from RDS
- [ ] Run performance tests with RDS backend
  - [ ] Run same workload (100 concurrent clients, Tiny-LLM download)
  - [ ] Measure latency (mean, median, P99)
  - [ ] Measure throughput
  - [ ] Compare to S3 baseline measurements
- [ ] Document S3 vs RDS comparison
  - [ ] Document latency differences
  - [ ] Document throughput differences
  - [ ] Document scalability characteristics
  - [ ] Document cost trade-offs
  - [ ] Document use case recommendations

**Estimated Effort**: 3-4 days

**Files to Create/Modify**:
- `src/services/storage_service.py` (new - abstraction layer)
- `src/services/rds_storage.py` (new - RDS implementation)
- `src/services/s3_service.py` (modify - add storage backend selection)
- `infra/modules/rds/main.tf` (new)
- `infra/envs/dev/main.tf` (modify - add RDS resource)

**Note**: RDS is not ideal for large binary files (24.8 MB), but this comparison demonstrates the performance trade-offs between object storage and relational databases for this use case.

---

### 3. Configuration Management

**Requirement**: Modify system so that it is possible to select underlying components as part of the configuration.

**Tasks**:
- [ ] Create performance configuration file
  - [ ] Create `config/performance_config.json` or use environment variables
  - [ ] Define configuration schema:
    ```json
    {
      "compute_backend": "ecs|lambda",
      "storage_backend": "s3|rds",
      "enable_caching": true/false,
      "thread_pool_size": 100,
      "s3_connection_pool_size": 150
    }
    ```
- [ ] Implement configuration loader
  - [ ] Load configuration at service startup
  - [ ] Validate configuration values
  - [ ] Provide defaults for missing values
- [ ] Integrate configuration into routing/storage logic
  - [ ] Use configuration to select compute backend
  - [ ] Use configuration to select storage backend
  - [ ] Ensure endpoints work with different configurations
- [ ] Document configuration options
  - [ ] Document all configuration parameters
  - [ ] Document how to switch between backends
  - [ ] Provide example configurations

**Estimated Effort**: 1 day

**Files to Create/Modify**:
- `config/performance_config.json` (new - optional, prefer env vars)
- `src/config/performance_config.py` (new - config loader)
- `src/routes/packages.py` (modify - use config)
- `src/services/s3_service.py` (modify - use config)

---

### 4. Final Performance Report

**Requirement**: Provide comprehensive documentation of all findings.

**Tasks**:
- [ ] Create performance report document
  - [ ] Include experimental design (already in `PERFORMANCE_BOTTLENECKS.md`)
  - [ ] Include baseline measurements (already documented)
  - [ ] Include bottleneck analysis (already documented)
  - [ ] Include optimization results (already documented)
  - [ ] Add Lambda vs ECS comparison section
  - [ ] Add S3 vs RDS comparison section
  - [ ] Add conclusions and recommendations
- [ ] Ensure all measurements are documented
  - [ ] Verify throughput measurements are included
  - [ ] Verify mean/median/P99 latency measurements are included
  - [ ] Include before/after comparisons
  - [ ] Include component comparison tables
- [ ] Create summary section
  - [ ] Key findings summary
  - [ ] Performance improvements summary
  - [ ] Recommendations for production deployment

**Estimated Effort**: 0.5-1 day (mostly writing, data already collected)

**Files to Create/Modify**:
- `PERFORMANCE_BOTTLENECKS.md` (modify - add component comparisons)
- `PERFORMANCE_REPORT.md` (new - optional comprehensive report)

---

## Implementation Priority

1. **Component Comparisons** (Required by assignment)
   - Lambda vs ECS: Start here (more straightforward)
   - S3 vs RDS: More complex, but valuable comparison

2. **Configuration Management** (Required for component selection)
   - Can be done in parallel with component implementations
   - Needed to actually switch between backends

3. **Final Documentation** (Completion)
   - Final report integrating all findings
   - Can be done after component comparisons are complete

---

## Notes

- **Current Status**: Baseline performance measurement and bottleneck optimization are complete. All 100 concurrent requests succeed with measured throughput and latency metrics.
- **Next Milestone**: Complete component comparison experiments (Lambda vs ECS, S3 vs RDS).
- **Blockers**: None - can proceed with component comparison work immediately.
- **Dependencies**: Component comparisons require infrastructure changes (Lambda deployment, RDS setup), which should be done via Terraform modules.

---

## Quick Reference

**Completed Documentation**:
- `PERFORMANCE_BOTTLENECKS.md` - Complete bottleneck analysis and optimization results

**Key Endpoints**:
- `POST /health/performance/workload` - Trigger performance workload
- `GET /health/performance/results/{run_id}` - Get workload results
- `GET /performance/{model_id}/{version}/model.zip` - Download endpoint

**Key Scripts**:
- `scripts/populate_registry.py --performance` - Populate 500 models for testing
- `scripts/test_load_generator.py` - Direct load generator testing

**Performance Results** (Final):
- Success Rate: 100/100 (100%)
- Throughput: 37.48 MB/sec
- Mean Latency: 51.26 seconds
- Median Latency: 52.93 seconds
- P99 Latency: 63.17 seconds
