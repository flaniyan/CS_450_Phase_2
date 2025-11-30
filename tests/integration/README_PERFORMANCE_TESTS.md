# Performance Track Test Suite

This directory contains comprehensive test suites for the Performance Track implementation, organized by phase.

## Test Organization

Tests are organized into phases corresponding to the development phases:

- **Phase 1**: `test_performance_workload_setup.py` - Workload setup and trigger
- **Phase 2**: `test_performance_metrics.py` - Metrics collection infrastructure
- **Phase 3**: `test_performance_bottlenecks.py` - Bottleneck identification
- **Phase 4**: `test_performance_optimizations.py` - Optimization implementation
- **Phase 5**: `test_performance_component_comparison.py` - Component comparisons
- **End-to-End**: `test_performance_end_to_end.py` - Complete workflow tests

### Overall Test Orchestrator

- **Master Test**: `test_overall_performance_track.py` - Runs all phases and generates comprehensive summary

## Running Tests by Phase

### Phase 1: Workload Setup
```bash
pytest tests/integration/test_performance_workload_setup.py -v
pytest tests/unit/test_performance_load_generator.py -v
```

### Phase 2: Measurement Infrastructure
```bash
pytest tests/integration/test_performance_metrics.py -v
pytest tests/unit/test_performance_statistics.py -v
```

### Phase 3: Bottleneck Identification
```bash
pytest tests/integration/test_performance_bottlenecks.py -v
```

### Phase 4: Optimizations
```bash
pytest tests/integration/test_performance_optimizations.py -v
```

### Phase 5: Component Comparison
```bash
pytest tests/integration/test_performance_component_comparison.py -v
```

### All Performance Tests (Individual)
```bash
pytest tests/integration/test_performance_*.py -v
pytest tests/unit/test_performance_*.py -v
```

### Overall Performance Track Summary
```bash
# Run all phases and get comprehensive summary
pytest tests/integration/test_overall_performance_track.py -v -s

# The summary test will:
# 1. Run each phase's tests sequentially
# 2. Collect results for each phase
# 3. Generate a comprehensive summary report
# 4. Save results to performance_track_summary.json
```

## Test-Driven Development (TDD) Approach

These tests are written following TDD principles:

1. **Red Phase**: Tests will initially fail because implementations don't exist yet
2. **Green Phase**: Implement features to make tests pass
3. **Refactor Phase**: Improve implementation while keeping tests green

### Expected Initial State

When first running these tests, you should expect:
- Import errors (modules don't exist yet)
- Attribute errors (classes/functions not implemented)
- Connection errors (if API server not running)
- Assertion failures (expected behavior not implemented)

This is **normal and expected** for TDD!

## Prerequisites

### Environment Variables
```bash
export API_BASE_URL="https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod"
export AWS_REGION="us-east-1"
export ARTIFACTS_BUCKET="pkg-artifacts"
export SKIP_AWS_TESTS="false"  # Set to "true" to skip AWS-dependent tests
```

### Required Services
- FastAPI server running
- AWS credentials configured
- DynamoDB tables created
- S3 bucket accessible

### Required Python Packages
```bash
pytest
pytest-asyncio
requests
boto3
```

## Test Fixtures

Common fixtures available:
- `api_base_url`: API endpoint URL
- `auth_token`: Authentication token for API requests
- `baseline_workload_run_id`: Run ID for baseline workload
- `performance_workload_run_id`: Run ID for performance workload

## Running Specific Test Cases

```bash
# Run a specific test class
pytest tests/integration/test_performance_workload_setup.py::TestPerformanceWorkloadEndpoint -v

# Run a specific test method
pytest tests/integration/test_performance_workload_setup.py::TestPerformanceWorkloadEndpoint::test_performance_workload_endpoint_exists -v

# Run tests matching a pattern
pytest tests/integration/test_performance_*.py -k "endpoint" -v
```

## Handling Test Failures

### Expected Failures (TDD Red Phase)
- `ModuleNotFoundError`: Module doesn't exist yet
- `AttributeError`: Class/function not implemented
- `AssertionError`: Feature not working yet

### Unexpected Failures
- `ConnectionError`: API server not running
- `AWS credentials error`: AWS not configured
- `TimeoutError`: Workload taking too long

## Test Coverage Goals

- **Unit Tests**: > 90% coverage for utility functions
- **Integration Tests**: Cover all critical paths
- **End-to-End Tests**: Validate complete workflows

## Notes

- Some tests require actual AWS resources and may incur costs
- Long-running tests (workloads) may take 5+ minutes
- Tests are designed to be idempotent where possible
- Some tests may need to be run in sequence (dependencies)

## Troubleshooting

### Tests failing with import errors
- Expected in TDD red phase
- Create stub modules to allow imports
- Implement modules incrementally

### Tests timing out
- Increase timeout values in test fixtures
- Check API server is responsive
- Verify network connectivity

### AWS permission errors
- Check IAM permissions
- Verify AWS credentials are configured
- Review CloudWatch/DynamoDB access

