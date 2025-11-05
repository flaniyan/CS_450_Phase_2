# Debugging: Request Not Reaching FastAPI

If the `/authenticate` endpoint returns 401 but the request isn't reaching FastAPI (no logs from middleware or endpoint), check these layers:

## 1. API Gateway Configuration

### Check API Gateway Integration
```bash
# Get the API Gateway ID
aws apigateway get-rest-apis --query "items[?name=='acme-api'].id" --output text

# Check the /authenticate resource configuration
aws apigateway get-resource --rest-api-id <API_ID> --resource-id <RESOURCE_ID>

# Check the PUT method configuration
aws apigateway get-method --rest-api-id <API_ID> --resource-id <RESOURCE_ID> --http-method PUT
```

**Verify:**
- ✅ `authorization = "NONE"` (no authorizer)
- ✅ `apiKeyRequired = false` (no API key required)
- ✅ Integration type is `HTTP_PROXY`
- ✅ Integration URI points to correct ALB URL

### Check API Gateway Stage/Deployment
```bash
# List deployments
aws apigateway get-deployments --rest-api-id <API_ID>

# Check stage configuration
aws apigateway get-stage --rest-api-id <API_ID> --stage-name prod
```

**Verify:**
- ✅ Latest deployment is active
- ✅ No stage variables interfering
- ✅ No throttling/quotas blocking

## 2. ALB (Application Load Balancer) Configuration

### Check ALB Target Health
```bash
# Get ALB ARN
aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'validator')]"

# Check target group health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>
```

**Verify:**
- ✅ Targets (ECS tasks) are healthy
- ✅ Health checks passing
- ✅ No security group rules blocking

### Check ALB Listener Rules
```bash
# Get listener rules
aws elbv2 describe-rules --listener-arn <LISTENER_ARN>
```

**Verify:**
- ✅ No authentication rules on ALB
- ✅ No WAF rules blocking
- ✅ Rules allow traffic to ECS

## 3. Security Groups

### Check API Gateway → ALB Security Group
```bash
# Check ALB security group inbound rules
aws ec2 describe-security-groups --group-ids <ALB_SG_ID>
```

**Verify:**
- ✅ Allows inbound from API Gateway (0.0.0.0/0 or VPC ranges)
- ✅ Allows HTTPS (443) or HTTP (80)

### Check ALB → ECS Security Group
```bash
# Check ECS task security group
aws ec2 describe-security-groups --group-ids <ECS_SG_ID>
```

**Verify:**
- ✅ Allows inbound from ALB security group
- ✅ Allows port 3000 (FastAPI port)

## 4. Network ACLs

### Check VPC Network ACLs
```bash
# Get network ACLs for the subnets
aws ec2 describe-network-acls --filters "Name=vpc-id,Values=<VPC_ID>"
```

**Verify:**
- ✅ No rules blocking API Gateway → ALB traffic
- ✅ No rules blocking ALB → ECS traffic

## 5. CloudWatch Logs - API Gateway

### Check API Gateway Execution Logs
```bash
# Check if API Gateway has execution logging enabled
aws apigateway get-stage --rest-api-id <API_ID> --stage-name prod

# Query CloudWatch Logs for API Gateway execution
aws logs filter-log-events \
  --log-group-name "API-Gateway-Execution-Logs_<API_ID>/prod" \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  --filter-pattern "authenticate"
```

**Look for:**
- Request reaching API Gateway
- Integration request/response
- Any errors in integration

## 6. CloudWatch Logs - ECS Backend

### Check ECS Backend Logs
```bash
# Check if middleware is running
aws logs filter-log-events \
  --log-group-name "/ecs/validator-service" \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  --filter-pattern "MIDDLEWARE START.*authenticate"
```

**Look for:**
- `=== MIDDLEWARE START: PUT /authenticate ===`
- `=== AUTHENTICATE ENDPOINT REACHED ===`
- If these don't appear, request isn't reaching FastAPI

## 7. Test Direct ALB Access

### Bypass API Gateway and test ALB directly
```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'validator')].DNSName" --output text

# Test directly
curl -X PUT "http://<ALB_DNS>/authenticate" \
  -H "Content-Type: application/json" \
  -d @auth.json
```

**If this works:**
- ✅ FastAPI code is correct
- ✅ Problem is in API Gateway → ALB path

**If this fails:**
- ❌ Problem is in ALB → ECS or FastAPI code

## 8. Check API Gateway Method Response

### Verify method response configuration
```bash
# Check method response
aws apigateway get-method-response \
  --rest-api-id <API_ID> \
  --resource-id <RESOURCE_ID> \
  --http-method PUT \
  --status-code 200
```

**Verify:**
- ✅ No required response headers blocking
- ✅ Response models configured correctly

## 9. Check API Gateway Resource Policy

### Verify no resource policy blocking
```bash
# Check REST API policy
aws apigateway get-rest-api --rest-api-id <API_ID> --query "policy"
```

**Verify:**
- ✅ No IP restrictions
- ✅ No source IP blocking
- ✅ No time-based restrictions

## 10. Force API Gateway Deployment

### Sometimes deployments don't propagate
```bash
# Create new deployment
aws apigateway create-deployment \
  --rest-api-id <API_ID> \
  --stage-name prod \
  --description "Force redeploy for /authenticate fix"
```

## Quick Diagnostic Commands

```bash
# 1. Check API Gateway method config
API_ID="1q1x0d7k93"
aws apigateway get-method --rest-api-id $API_ID --resource-id <RESOURCE_ID> --http-method PUT

# 2. Check integration config
aws apigateway get-integration --rest-api-id $API_ID --resource-id <RESOURCE_ID> --http-method PUT

# 3. Check ECS service status
aws ecs describe-services --cluster validator-cluster --services validator-service

# 4. Check ALB target health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>

# 5. Check recent API Gateway logs
aws logs tail "API-Gateway-Execution-Logs_${API_ID}/prod" --since 10m --format short
```

## Expected Flow

```
Client Request
    ↓
API Gateway (1q1x0d7k93)
    ↓ (HTTP_PROXY integration)
ALB (Application Load Balancer)
    ↓ (Target Group)
ECS Task (FastAPI on port 3000)
    ↓
FastAPI Middleware
    ↓
FastAPI Endpoint (/authenticate)
```

**If logs show request at API Gateway but not at ECS:**
- Check ALB target health
- Check security groups
- Check network ACLs

**If logs show request at ECS middleware but not endpoint:**
- Check FastAPI route registration
- Check middleware order
- Check exception handlers

