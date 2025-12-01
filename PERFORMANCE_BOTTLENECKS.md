# Performance Bottlenecks: Identification and Optimization

## Overview

This document describes the performance bottlenecks identified during the ACME Model Registry performance testing phase, how they were discovered, the optimizations applied, and their effects on system performance.

## Test Scenario

- **Workload**: 100 concurrent clients downloading Tiny-LLM model (24.8 MB)
- **Registry Size**: 500 distinct models
- **Endpoint**: `/performance/{model_id}/{version}/model.zip`
- **Goal**: Measure throughput, mean/median/P99 latency

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

## Combined Effect

### Before All Optimizations
- **Successful Requests**: 0/100 (all timed out)
- **Throughput**: 0 bytes/sec
- **Latency**: ~300 seconds (timeout)

### After All Optimizations
- **Successful Requests**: 100/100 (all complete - verified from server logs)
- **Throughput**: Significant improvement (limited by network/S3 bandwidth, not application bottlenecks)
- **Latency**: ~30-40 seconds per request (actual download time, no artificial queuing)
- **Concurrent Processing**: All 100 requests processing simultaneously

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

