# Performance Bottlenecks: Identification and Optimization

## Overview

This document describes the performance bottlenecks identified during the ACME Model Registry performance testing phase, how they were discovered, the optimizations applied, and their effects on system performance. This work was conducted as part of the ACME Corporation performance requirements to measure throughput and latency (mean, median, and 99th percentile) when 100 concurrent clients download the Tiny-LLM model from a registry containing 500 distinct models.

## Experimental Design

### Workload Specification

**Objective**: Measure system performance when 100 concurrent clients simultaneously download a copy of the Tiny-LLM model from a registry containing 500 distinct models.

**Test Configuration**:
- **Number of Concurrent Clients**: 100
- **Target Model**: Tiny-LLM (ingested from https://huggingface.co/arnir0/Tiny-LLM)
- **Model Size**: 24.8 MB (24,834,009 bytes)
- **Registry Size**: 500 distinct models stored in S3
- **Download Endpoint**: `/performance/{model_id}/{version}/model.zip`
- **Model ID Format**: `arnir0_Tiny-LLM` (sanitized from HuggingFace format `arnir0/Tiny-LLM`)
- **Version**: `main`

### Infrastructure Setup

**System Components**:
- **Compute**: FastAPI application running on ECS Fargate
- **Storage**: Amazon S3 (model files stored at `performance/` prefix)
- **Metadata**: Amazon DynamoDB (model metadata)
- **API**: FastAPI service exposing download endpoints
- **Load Generation**: Custom async load generator using `aiohttp`

**Registry Population**:
- Used `scripts/populate_registry.py --performance` to populate registry
- Tiny-LLM model: Full download including model binary (required for performance testing)
- 499 additional models: Essential files only (config, README) for registry population
- All models stored in S3 under `performance/` prefix for performance testing isolation

### Measurement Methodology

**Black-Box Measurements** (External Perspective):
- Load generator makes HTTP GET requests to download endpoint
- Each request measured from client perspective:
  - Request start timestamp
  - Response completion timestamp
  - Latency = completion - start (milliseconds)
  - Bytes transferred (from response body length)
  - HTTP status code
- All 100 requests initiated simultaneously using `asyncio.gather()`
- Metrics collected per-request, then aggregated

**White-Box Measurements** (Internal Component Instrumentation):
- **S3 Download Latency**: Time spent in `s3.get_object()` operation
- **Request Processing Time**: Time spent in FastAPI endpoint handler
- **Connection Pool Metrics**: Monitor boto3 connection pool utilization
- **Thread Pool Metrics**: Monitor executor queue depth
- **Server Logs**: Detailed logging of request processing patterns

**Metrics Calculated**:
1. **Throughput**: Total bytes transferred / total duration (bytes/sec, MB/sec)
2. **Mean Latency**: Average request latency across all requests
3. **Median Latency**: 50th percentile latency
4. **99th Percentile (P99) Latency**: 99th percentile latency (tail latency)
5. **Min/Max Latency**: Fastest and slowest request latencies
6. **Success Rate**: Percentage of successful requests (status 200)

### Workload Trigger

**Trigger Endpoint**: `POST /health/performance/workload`

The workload is triggerable from the system health dashboard via the above endpoint, which accepts:
```json
{
  "num_clients": 100,
  "model_id": "arnir0/Tiny-LLM",
  "duration_seconds": 300
}
```

Returns immediately with `run_id` and status, then executes workload asynchronously. Results can be retrieved via `GET /health/performance/results/{run_id}`.

### Test Execution

**Execution Steps**:
1. Ensure registry is populated with 500 models (including Tiny-LLM) in `performance/` S3 path
2. Start FastAPI server
3. Trigger workload via `/health/performance/workload` endpoint or run load generator directly
4. Monitor server logs for request processing patterns
5. Collect metrics from load generator output
6. Retrieve results via `/health/performance/results/{run_id}` endpoint

**Baseline vs Optimized Runs**:
- **Baseline**: Initial system state before optimizations
- **Optimized**: After applying all three bottleneck fixes

---

## Bottleneck #1: Synchronous Endpoint Blocking Event Loop

### How It Was Found

**Detection Method**: Black-box + White-box analysis

1. **Initial Symptoms**:
   - All 100 requests timing out after 300 seconds
   - Zero successful requests
   - Server logs showed only one request being processed at a time
   - Status code 0 (timeout) for all requests

2. **White-box Analysis**:
   - Examined server logs: only one `[PERF] Received download request` message appeared
   - Checked endpoint implementation in `src/routes/packages.py`
   - Discovered endpoint was defined as `def download_performance_model_file()` (synchronous)
   - FastAPI/Uvicorn async event loop was being blocked by synchronous S3 download operations

3. **Root Cause**:
   - Synchronous endpoint blocked the entire event loop
   - Each request held a worker thread for ~30 seconds while downloading from S3
   - With limited worker threads, subsequent requests queued and eventually timed out
   - Event loop couldn't handle concurrent requests

### Evidence

**Before Fix**:
```
Server logs:
- Only 1 request showing "[PERF] Received download request"
- All 100 requests timing out
- Latency: ~300 seconds (timeout value)

Test results:
- Successful: 0/100
- Failed: 100/100
- Mean latency: 300819.27 ms
- Throughput: 0.00 bytes/sec
```

**Code Analysis**:
```python
# BEFORE (synchronous - blocks event loop)
@router.get("/performance/{model_id}/{version}/model.zip")
def download_performance_model_file(...):
    file_content = download_model(...)  # Blocking call
    return StreamingResponse(...)
```

### Optimization Applied

**Solution**: Convert endpoint to async and use thread pool for blocking I/O

1. **Changed endpoint signature**: `def` → `async def`
2. **Wrapped blocking S3 call**: Used `asyncio.to_thread()` to run blocking operation in thread pool

**Code Changes** (`src/routes/packages.py`):
```python
# AFTER (async - doesn't block event loop)
@router.get("/performance/{model_id}/{version}/model.zip")
async def download_performance_model_file(...):
    file_content = await asyncio.to_thread(
        download_model, model_id, version, component, True
    )
    return StreamingResponse(...)
```

### Effect

**After Fix**:
- Multiple concurrent requests processed simultaneously
- Server logs showed many `[PERF] Received download request` messages
- Requests began completing successfully
- Event loop no longer blocked

**Metrics Improvement**:
- Request processing: 0/100 successful → Multiple successful (limited by next bottleneck)
- Event loop utilization: Blocked → Concurrent
- Thread blocking: Yes → No

---

## Bottleneck #2: Insufficient Thread Pool Capacity

### How It Was Found

**Detection Method**: White-box analysis + Server logs

1. **Initial Symptoms**:
   - After making endpoint async, requests started processing
   - But still saw sequential processing patterns
   - Multiple requests received, but downloads happened sequentially

2. **White-box Analysis**:
   - Examined Python's default thread pool executor capacity
   - `asyncio.to_thread()` uses default executor with `max_workers = min(32, (os.cpu_count() or 1) + 4)`
   - With 100 concurrent requests and default ~32-36 workers, requests were queued
   - Thread pool became the bottleneck

3. **Root Cause**:
   - Default thread pool executor can only handle ~32-36 concurrent blocking operations
   - With 100 concurrent requests, 64-68 requests had to wait for thread pool slots
   - This created a queue, reducing parallelism

### Evidence

**Server Logs Analysis**:
```
- Multiple requests received: ✓
- But downloads happening in batches of ~30-35
- Not all 100 requests processing simultaneously
```

**Code Analysis**:
```python
# asyncio.to_thread() uses default executor
# Default max_workers = min(32, (os.cpu_count() or 1) + 4)
# Insufficient for 100 concurrent requests
```

### Optimization Applied

**Solution**: Create custom thread pool executor with capacity matching workload

1. **Created custom ThreadPoolExecutor**: 100 workers (matching load test requirements)
2. **Changed from `asyncio.to_thread()`** to `loop.run_in_executor()` with custom executor

**Code Changes** (`src/routes/packages.py`):
```python
# Added custom thread pool executor
from concurrent.futures import ThreadPoolExecutor

# Custom thread pool executor for S3 operations to handle high concurrency
# Use max_workers=100 to match our load test requirements
_s3_executor = ThreadPoolExecutor(max_workers=100, thread_name_prefix="s3_download")

# Changed execution method
async def download_performance_model_file(...):
    loop = asyncio.get_event_loop()
    file_content = await loop.run_in_executor(
        _s3_executor,
        download_model,
        model_id, version, component, True
    )
    return StreamingResponse(...)
```

### Effect

**After Fix**:
- All 100 requests could be processed concurrently
- Server logs showed all 100 requests being received and processed
- True parallelism achieved

**Metrics Improvement**:
- Concurrent processing: ~30-35 → 100
- Thread pool utilization: Saturated → Full capacity
- Queue depth: High → Minimal

---

## Bottleneck #3: S3 Connection Pool Size Limitation

### How It Was Found

**Detection Method**: White-box analysis + Warning logs

1. **Initial Symptoms**:
   - Requests were being processed, but taking very long
   - High latency (20-50 seconds per request)
   - Repeated warnings in server logs

2. **Warning Messages** (key evidence):
   ```
   WARNING:urllib3.connectionpool:Connection pool is full, discarding connection: 
   cs450-s3-838693051036.s3-accesspoint.us-east-1.amazonaws.com. 
   Connection pool size: 10
   ```

3. **White-box Analysis**:
   - Examined boto3 S3 client configuration in `src/services/s3_service.py`
   - Found S3 client created without custom configuration: `boto3.client("s3", region_name=region)`
   - boto3's default connection pool size is **10 connections**
   - With 100 concurrent requests, 90 requests were waiting for available connections

4. **Root Cause**:
   - boto3's default connection pool (10 connections) insufficient for 100 concurrent downloads
   - Requests queued waiting for connection pool slots
   - Added significant latency as requests waited in queue
   - Each S3 download takes ~30 seconds, so requests were serializing through the pool

### Evidence

**Warning Logs** (repeated many times):
```
WARNING:urllib3.connectionpool:Connection pool is full, discarding connection: 
cs450-s3-838693051036.s3-accesspoint.us-east-1.amazonaws.com. 
Connection pool size: 10
```

**Before Fix Metrics**:
- Connection pool size: 10
- Concurrent S3 operations: Limited to 10
- Effective throughput: ~10 requests per ~30 seconds = ~0.33 req/s
- Remaining 90 requests: Waiting in queue

**Code Analysis**:
```python
# BEFORE (default connection pool = 10)
s3 = boto3.client("s3", region_name=region)
```

### Optimization Applied

**Solution**: Configure boto3 S3 client with larger connection pool

1. **Added boto3 Config import**: `from botocore.config import Config`
2. **Created custom boto3 config**: Increased `max_pool_connections` from 10 to 150
3. **Applied config to S3 client**: Pass config to client initialization

**Code Changes** (`src/services/s3_service.py`):
```python
from botocore.config import Config

# Configure S3 client with larger connection pool for high concurrency
# Default is 10 connections, increase to 150+ to handle concurrent load testing
s3_config = Config(
    max_pool_connections=150,  # Allow up to 150 concurrent connections
    retries={'max_attempts': 3, 'mode': 'standard'}
)

s3 = boto3.client("s3", region_name=region, config=s3_config)
```

### Effect

**After Fix**:
- Connection pool warnings eliminated
- All 100 requests can download from S3 concurrently
- No more connection pool queuing
- True parallelism for S3 operations

**Actual Metrics Improvement**:
- Connection pool size: 10 → 150
- Concurrent S3 downloads: 10 → 100+
- Connection pool queue depth: High → None
- Connection pool warnings: Present → Eliminated
- Overall latency: Reduced (no queue waiting time)
- Throughput: Increased significantly

**Before vs After**:
- **Before**: 100 requests processed in ~10 batches × ~30 seconds = ~300 seconds total (many timing out)
- **After**: All 100 requests can proceed concurrently = ~30-40 seconds per request (limited by actual download speed, not connection pool)

**Verification from Server Logs**:
```
- Multiple concurrent requests received and processed simultaneously
- "AWS S3 download successful" messages appearing concurrently
- Status 200 responses for successful downloads
- No "Connection pool is full" warnings
- Request completion times: ~29-43 seconds per request
```

---

## Summary of Optimizations

| Bottleneck | Detection Method | Root Cause | Fix Applied | Effect |
|------------|-----------------|------------|-------------|--------|
| **#1: Synchronous Endpoint** | Logs showed only 1 request processing | Synchronous function blocked event loop | Converted to async endpoint | Enabled concurrent request processing |
| **#2: Thread Pool Capacity** | White-box code analysis | Default executor (~32 workers) insufficient for 100 requests | Custom executor with 100 workers | True parallelism for blocking I/O |
| **#3: S3 Connection Pool** | Warning logs: "Connection pool is full (size: 10)" | boto3 default pool (10) insufficient for 100 concurrent requests | Increased to 150 connections | Eliminated connection queue bottleneck |

---

## Black-Box Performance Measurements

### Baseline Measurements (Before Optimizations)

**Initial Test Results**:
- **Successful Requests**: 0/100 (all timed out)
- **Failed Requests**: 100/100
- **Total Duration**: 301.16 seconds (all requests timed out)
- **Throughput**: 0.00 bytes/sec
- **Mean Latency**: 300,932.18 ms (~301 seconds - timeout value)
- **Median Latency**: 300,925.39 ms
- **P99 Latency**: 301,075.44 ms
- **Min Latency**: 300,799.91 ms
- **Max Latency**: 301,078.06 ms

**Analysis**: All requests failed due to system-level bottlenecks preventing concurrent request processing. The timeout value (300 seconds) was hit before any request could complete.

### Final Measurements (After All Optimizations)

**Optimized Test Results**:
- **Successful Requests**: 100/100 (100% success rate)
- **Failed Requests**: 0/100
- **Total Duration**: 63.20 seconds
- **Throughput**: 37.48 MB/sec (39,296,264 bytes/sec)
- **Mean Latency**: 51,257.91 ms (51.26 seconds)
- **Median Latency**: 52,931.20 ms (52.93 seconds)
- **P99 Latency**: 63,174.26 ms (63.17 seconds)
- **Min Latency**: 12,706.16 ms (12.71 seconds)
- **Max Latency**: 63,189.94 ms (63.19 seconds)
- **Total Bytes Transferred**: 2,483,400,900 bytes (2,368.36 MB)
- **Requests per Second**: 1.58 req/s

**Performance Improvement Summary**:
- **Success Rate**: 0% → 100% (+100 percentage points)
- **Throughput**: 0 MB/sec → 37.48 MB/sec (infinite improvement)
- **Mean Latency**: 300.93 seconds → 51.26 seconds (83% reduction)
- **P99 Latency**: 301.08 seconds → 63.17 seconds (79% reduction)
- **Total Duration**: 301.16 seconds → 63.20 seconds (79% reduction)

## White-Box Performance Explanation

### Component-Level Analysis

**S3 Download Component**:
- **Operation**: `s3.get_object()` to retrieve 24.8 MB ZIP file from S3
- **Baseline Latency**: ~30-40 seconds per download (network bandwidth limited)
- **Optimization Impact**: Connection pool increase eliminated queuing delays
- **White-Box Evidence**: Server logs show concurrent "AWS S3 download successful" messages
- **Bottleneck**: Initially limited to 10 concurrent connections, causing serialization

**FastAPI Endpoint Handler**:
- **Operation**: `/performance/{model_id}/{version}/model.zip` endpoint processing
- **Baseline Latency**: Blocking entire event loop, preventing concurrency
- **Optimization Impact**: Async endpoint allows concurrent request handling
- **White-Box Evidence**: Server logs show multiple "[PERF] Received download request" messages simultaneously
- **Bottleneck**: Synchronous function blocking event loop

**Thread Pool Executor**:
- **Operation**: Offloading blocking S3 I/O operations from async event loop
- **Baseline Capacity**: ~32-36 workers (default Python executor)
- **Optimization Impact**: Increased to 100 workers matching concurrent request load
- **White-Box Evidence**: All 100 requests processed concurrently instead of in batches
- **Bottleneck**: Insufficient thread pool capacity for 100 concurrent operations

### Request Flow Analysis

**Optimized Request Flow** (After Fixes):
1. 100 concurrent HTTP requests arrive at FastAPI endpoint
2. FastAPI async event loop handles all requests concurrently (non-blocking)
3. Each request offloaded to custom thread pool executor (100 workers available)
4. Thread pool executes blocking S3 download operation using boto3 client
5. S3 client uses connection pool (150 connections) to download from S3
6. Responses streamed back to clients concurrently
7. All 100 requests complete within ~63 seconds (limited by network bandwidth)

**Bottleneck Identification Flow**:
1. **Initial Failure**: All requests timeout → Identified synchronous endpoint blocking event loop
2. **Partial Success**: Some requests succeed, but sequential processing → Identified thread pool capacity limit
3. **Connection Warnings**: "Connection pool is full" messages → Identified S3 connection pool bottleneck
4. **Final Success**: All requests succeed concurrently → All bottlenecks resolved

## Combined Effect

### After All Optimizations

**Final Performance Measurements** (from actual test run):

**Request Statistics**:
- **Total Requests**: 100
- **Successful**: 100
- **Failed**: 0
- **Success Rate**: 100.00%
- **Total Duration**: 63.20 seconds

**Latency Statistics** (Required Measurements):
- **Mean Latency**: 51,257.91 ms (51.26 seconds)
- **Median Latency**: 52,931.20 ms (52.93 seconds)
- **99th Percentile (P99) Latency**: 63,174.26 ms (63.17 seconds)
- **Min Latency**: 12,706.16 ms (12.71 seconds)
- **Max Latency**: 63,189.94 ms (63.19 seconds)

**Throughput Statistics** (Required Measurement):
- **Throughput**: 39,296,263.99 bytes/sec (37.48 MB/sec)
- **Total Bytes Transferred**: 2,483,400,900 bytes (2,368.36 MB)
- **Requests per Second**: 1.58 req/s

**Sample Request Metrics** (first 5 clients):
1. Client 2: ✓ Status 200, Latency 12,706.16 ms, Bytes 24,834,009
2. Client 4: ✓ Status 200, Latency 12,741.01 ms, Bytes 24,834,009
3. Client 10: ✓ Status 200, Latency 12,786.35 ms, Bytes 24,834,009
4. Client 16: ✓ Status 200, Latency 12,802.58 ms, Bytes 24,834,009
5. Client 12: ✓ Status 200, Latency 12,865.58 ms, Bytes 24,834,009

**Concurrent Processing**: All 100 requests processing simultaneously

### Key Improvements
1. **Concurrency**: Enabled true concurrent processing (100 requests in parallel)
2. **No Artificial Queuing**: Eliminated thread pool and connection pool queues
3. **Efficient Resource Utilization**: All available connections and threads utilized
4. **Bottleneck Shift**: Performance now limited by actual network/S3 bandwidth, not application-level bottlenecks

---

## Performance Testing Recommendations

### For Future Testing
1. **Monitor Connection Pool Metrics**: Watch for connection pool warnings
2. **Measure Thread Pool Utilization**: Track executor queue depth
3. **Profile Endpoint Execution**: Use async profiling tools to identify blocking operations
4. **Load Testing**: Gradually increase load to identify next bottlenecks

### Configuration Guidelines
- **Thread Pool Size**: Match to expected concurrent request load
- **Connection Pool Size**: Set to at least 2x expected concurrent connections
- **Async Operations**: Ensure all I/O operations are non-blocking

---

## References

- **Endpoint Implementation**: `src/routes/packages.py`
- **S3 Service Configuration**: `src/services/s3_service.py`
- **Load Generator**: `src/services/performance/load_generator.py`
- **Server Logs**: Check for connection pool warnings and request processing patterns

