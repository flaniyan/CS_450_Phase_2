# CloudWatch Log Search Guide for Dataset and Code Queries

This guide shows how to search CloudWatch logs to verify if dataset and code queries are working correctly.

## Prerequisites

1. **Log Group Name**: `/ecs/validator-service` (or your ECS service log group)
2. **AWS CLI configured** with appropriate permissions
3. **Region**: `us-east-1` (or your deployment region)

## Quick Search Commands

### 1. Search for POST /artifacts Requests (Query Endpoint)

```bash
# Search for all POST /artifacts requests
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "POST /artifacts" \
  --region us-east-1 \
  --max-items 100

# Search for successful queries (HTTP 200)
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "POST /artifacts" "200" \
  --region us-east-1 \
  --max-items 100
```

### 2. Search for Dataset-Related Logs

```bash
# Search for dataset mentions
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "dataset" \
  --region us-east-1 \
  --max-items 100

# Search for dataset queries in _artifact_storage
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Searching _artifact_storage for datasets" \
  --region us-east-1 \
  --max-items 100

# Search for dataset artifacts found
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "dataset" "artifact" \
  --region us-east-1 \
  --max-items 100
```

### 3. Search for Code-Related Logs

```bash
# Search for code mentions
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "code" \
  --region us-east-1 \
  --max-items 100

# Search for code queries in _artifact_storage
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Searching _artifact_storage for datasets and code" \
  --region us-east-1 \
  --max-items 100
```

### 4. Search for Query Processing

```bash
# Search for query processing (both dataset and code)
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Searching _artifact_storage for datasets and code" \
  --region us-east-1 \
  --max-items 100

# Search for artifact storage initialization
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Initialized _artifact_storage" \
  --region us-east-1 \
  --max-items 10
```

## CloudWatch Filter Patterns

### Using Filter Patterns in CloudWatch Console

1. Go to **CloudWatch Console** → **Logs** → **Log groups**
2. Select `/ecs/validator-service`
3. Click **Search log group**
4. Use the following filter patterns:

#### Pattern 1: Dataset Queries
```
"dataset" "artifact"
```
This matches log entries containing both "dataset" and "artifact".

#### Pattern 2: Code Queries
```
"code" "artifact"
```
This matches log entries containing both "code" and "artifact".

#### Pattern 3: Query Endpoint Activity
```
"POST" "/artifacts"
```
This matches POST requests to the /artifacts endpoint.

#### Pattern 4: Artifact Storage Searches
```
"Searching _artifact_storage for datasets and code"
```
This matches the specific log message when searching _artifact_storage.

#### Pattern 5: Successful Queries (HTTP 200)
```
"POST /artifacts" "200"
```
This matches successful POST /artifacts requests.

#### Pattern 6: Query Errors
```
"POST /artifacts" "error"
```
This matches errors related to POST /artifacts.

### Using Regex Filter Patterns

CloudWatch supports regex patterns when wrapped in `%...%`:

#### Pattern 7: Dataset or Code Queries (Regex)
```
%dataset|code%
```
This matches log entries containing either "dataset" or "code".

#### Pattern 8: Query with Specific Name (Regex)
```
%POST /artifacts.*name=.*%
```
This matches POST /artifacts requests with a name parameter.

#### Pattern 9: Artifact Storage Initialization (Regex)
```
%Initialized _artifact_storage with \d+%
```
This matches initialization messages with artifact counts.

## Advanced Search with Time Range

### Search Recent Logs (Last Hour)

```bash
# Get current timestamp
END_TIME=$(date +%s)000
START_TIME=$((END_TIME - 3600000))  # 1 hour ago

aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --filter-pattern "dataset" "code" \
  --region us-east-1 \
  --max-items 100
```

### Search Specific Time Range

```bash
# Search logs from a specific time (Unix timestamp in milliseconds)
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --start-time 1700000000000 \
  --end-time 1700003600000 \
  --filter-pattern "POST /artifacts" \
  --region us-east-1 \
  --max-items 100
```

## PowerShell Commands (Windows)

### Search for Dataset Queries

```powershell
# Search for dataset mentions
aws logs filter-log-events `
  --log-group-name /ecs/validator-service `
  --filter-pattern "dataset" `
  --region us-east-1 `
  --max-items 100

# Search for code mentions
aws logs filter-log-events `
  --log-group-name /ecs/validator-service `
  --filter-pattern "code" `
  --region us-east-1 `
  --max-items 100

# Search for query endpoint
aws logs filter-log-events `
  --log-group-name /ecs/validator-service `
  --filter-pattern "POST /artifacts" `
  --region us-east-1 `
  --max-items 100
```

### Search with Time Range (PowerShell)

```powershell
# Get timestamps (last hour)
$endTime = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$startTime = $endTime - 3600000

aws logs filter-log-events `
  --log-group-name /ecs/validator-service `
  --start-time $startTime `
  --end-time $endTime `
  --filter-pattern "dataset" "code" `
  --region us-east-1 `
  --max-items 100
```

## What to Look For

### Successful Dataset/Code Query Indicators

1. **Initialization Message**:
   ```
   Initialized _artifact_storage with X dataset/code artifacts
   ```
   Shows how many dataset/code artifacts are in memory.

2. **Search Activity**:
   ```
   Searching _artifact_storage for datasets and code with name='...'
   ```
   Shows active searching in _artifact_storage.

3. **Found Artifacts**:
   ```
   Found dataset/code in _artifact_storage: id='...', name='...'
   ```
   Shows successful finds.

4. **HTTP 200 Response**:
   ```
   POST /artifacts ... 200
   ```
   Shows successful query responses.

### Error Indicators

1. **No Results**:
   ```
   No artifacts found
   ```
   Indicates query returned empty results.

2. **HTTP 400/500 Errors**:
   ```
   POST /artifacts ... 400
   POST /artifacts ... 500
   ```
   Indicates query errors.

3. **Exception Messages**:
   ```
   Error searching datasets
   Error searching code
   ```
   Indicates processing errors.

## Example: Complete Query Verification

### Step 1: Check Initialization
```bash
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Initialized _artifact_storage" \
  --region us-east-1
```

**Expected Output:**
```
Initialized _artifact_storage with 5 dataset/code artifacts
```

### Step 2: Check Query Activity
```bash
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "Searching _artifact_storage for datasets and code" \
  --region us-east-1 \
  --max-items 50
```

**Expected Output:**
```
DEBUG: Searching _artifact_storage for datasets and code with name='my-dataset'
DEBUG: Found dataset in _artifact_storage: id='1234567890', name='my-dataset'
```

### Step 3: Check Query Endpoint Requests
```bash
aws logs filter-log-events \
  --log-group-name /ecs/validator-service \
  --filter-pattern "POST /artifacts" "200" \
  --region us-east-1 \
  --max-items 50
```

**Expected Output:**
```
INFO: POST /artifacts ... 200 OK
```

## Using CloudWatch Insights (Advanced)

For more complex queries, use CloudWatch Logs Insights:

### Query 1: Count Dataset/Code Queries
```
fields @timestamp, @message
| filter @message like /dataset|code/
| filter @message like /POST \/artifacts/
| stats count() by bin(5m)
```

### Query 2: Find Query Errors
```
fields @timestamp, @message
| filter @message like /POST \/artifacts/
| filter @message like /error|Error|ERROR|400|500/
| sort @timestamp desc
```

### Query 3: Track Query Performance
```
fields @timestamp, @message, @duration
| filter @message like /POST \/artifacts/
| stats avg(@duration), max(@duration), min(@duration) by bin(1m)
```

## Troubleshooting

### If No Logs Found

1. **Check Log Group Name**:
   ```bash
   aws logs describe-log-groups --region us-east-1 | grep validator
   ```

2. **Check Recent Log Streams**:
   ```bash
   aws logs describe-log-streams \
     --log-group-name /ecs/validator-service \
     --order-by LastEventTime \
     --descending \
     --max-items 5 \
     --region us-east-1
   ```

3. **Get Latest Log Stream**:
   ```bash
   # Get the most recent log stream
   LOG_STREAM=$(aws logs describe-log-streams \
     --log-group-name /ecs/validator-service \
     --order-by LastEventTime \
     --descending \
     --max-items 1 \
     --region us-east-1 \
     --query 'logStreams[0].logStreamName' \
     --output text)
   
   # Get events from that stream
   aws logs get-log-events \
     --log-group-name /ecs/validator-service \
     --log-stream-name $LOG_STREAM \
     --region us-east-1 \
     --limit 100
   ```

### If Queries Not Working

1. **Check for Errors**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/validator-service \
     --filter-pattern "error" "dataset" "code" \
     --region us-east-1
   ```

2. **Check Artifact Storage**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/validator-service \
     --filter-pattern "_artifact_storage" \
     --region us-east-1
   ```

3. **Check Type Filter Issues**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/validator-service \
     --filter-pattern "types_filter" \
     --region us-east-1
   ```

## Quick Reference

| What to Search | Filter Pattern | Command |
|---------------|----------------|---------|
| Dataset queries | `"dataset"` | `--filter-pattern "dataset"` |
| Code queries | `"code"` | `--filter-pattern "code"` |
| Query endpoint | `"POST /artifacts"` | `--filter-pattern "POST /artifacts"` |
| Successful queries | `"POST /artifacts" "200"` | `--filter-pattern "POST /artifacts" "200"` |
| Artifact storage | `"_artifact_storage"` | `--filter-pattern "_artifact_storage"` |
| Query errors | `"POST /artifacts" "error"` | `--filter-pattern "POST /artifacts" "error"` |

## Notes

- Filter patterns are case-sensitive
- Multiple terms in a filter pattern are ANDed together
- Use regex patterns (`%...%`) for OR conditions
- Time ranges use Unix timestamps in milliseconds
- The `--max-items` parameter limits results (default: 10,000)

