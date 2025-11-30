# Testing Performance Workload (Phase 1.3)

This guide explains how to test the load generation client functionality.

## Prerequisites

1. **Server must be running**
   ```bash
   python run_server.py
   # or
   uvicorn src.entrypoint:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **At least one model must be ingested** (e.g., Tiny-LLM)
   ```bash
   # Make sure Tiny-LLM is ingested first
   python scripts/populate_registry.py --local
   # Or manually ingest via API
   ```

## Testing Methods

### Method 1: Via API Endpoint (Recommended)

This is the easiest way - triggers the workload via the API endpoint.

```bash
# Using curl
curl -X POST http://localhost:8000/health/performance/workload \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 10,
    "model_id": "arnir0/Tiny-LLM",
    "duration_seconds": 60
  }'

# Using PowerShell
$body = @{
    num_clients = 10
    model_id = "arnir0/Tiny-LLM"
    duration_seconds = 60
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/health/performance/workload" \
  -Method Post \
  -ContentType "application/json" \
  -Body $body
```

**Response:**
```json
{
  "run_id": "uuid-here",
  "status": "started",
  "estimated_completion": "2024-01-01T12:00:00Z"
}
```

**Check results:**
```bash
# Replace {run_id} with the returned run_id
curl http://localhost:8000/health/performance/results/{run_id}
```

### Method 2: Direct Python Script

Run the test script directly (good for debugging):

```bash
python test_load_generator.py
```

This will:
- Create 10 concurrent clients
- Download Tiny-LLM from your local server
- Display latency statistics
- Show sample metrics

### Method 3: Run Integration Tests

Run the existing test suite:

```bash
# Run all Phase 1 tests
pytest tests/integration/test_performance_workload_setup.py -v

# Run specific test class
pytest tests/integration/test_performance_workload_setup.py::TestLoadGenerator -v

# Run specific test
pytest tests/integration/test_performance_workload_setup.py::TestLoadGenerator::test_load_generator_creates_clients -v
```

### Method 4: Manual Testing with Python

You can also test interactively in Python:

```python
import asyncio
import uuid
from src.services.performance.load_generator import LoadGenerator

async def test():
    generator = LoadGenerator(
        run_id=str(uuid.uuid4()),
        base_url="http://localhost:8000",
        num_clients=5,  # Start small
        model_id="arnir0/Tiny-LLM"
    )
    await generator.run()
    print(generator.get_summary())

asyncio.run(test())
```

## Expected Behavior

When the load generator runs successfully, you should see:

1. **Concurrent requests**: Multiple download requests happening simultaneously
2. **Metrics collection**: Each request records:
   - Client ID (1-100)
   - Request timestamp
   - Response latency (ms)
   - Status code
   - Bytes transferred
3. **Statistics**: Summary with:
   - Total requests
   - Success/failure counts
   - Mean/median/P99 latency
   - Throughput (bytes/sec)

## Troubleshooting

### "Connection refused" error
- Make sure the server is running on the correct port
- Check the base_url in your test

### "404 Not Found" for model
- Ensure the model is ingested first
- Check model_id matches exactly (use sanitized version: `arnir0_Tiny-LLM`)

### "Timeout" errors
- Model might be too large
- Try with fewer clients first
- Check server logs for errors

### No metrics stored
- Check if DynamoDB table exists (for AWS)
- For local testing, metrics might just be in-memory
- Check server logs for storage errors

## Full Workload Test (100 clients)

Once basic testing works, try the full workload:

```bash
curl -X POST http://localhost:8000/health/performance/workload \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 100,
    "model_id": "arnir0/Tiny-LLM",
    "duration_seconds": 300
  }'
```

This will take longer but tests the full concurrent load scenario.

