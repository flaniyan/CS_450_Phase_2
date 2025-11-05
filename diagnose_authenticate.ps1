# Diagnostic Script for /authenticate Endpoint
# Run this to check if requests are reaching FastAPI

$API_ID = "1q1x0d7k93"
$REGION = "us-east-1"
$CLUSTER = "validator-cluster"
$SERVICE = "validator-service"

Write-Host "=== DIAGNOSTIC: /authenticate Endpoint ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check API Gateway Method Configuration
Write-Host "1. Checking API Gateway Method Configuration..." -ForegroundColor Yellow
try {
    $resources = aws apigateway get-resources --rest-api-id $API_ID --region $REGION --output json | ConvertFrom-Json
    $authenticateResource = $resources.items | Where-Object { $_.path -eq "/authenticate" }
    
    if ($authenticateResource) {
        Write-Host "   ✅ /authenticate resource found (ID: $($authenticateResource.id))" -ForegroundColor Green
        
        $method = aws apigateway get-method `
            --rest-api-id $API_ID `
            --resource-id $authenticateResource.id `
            --http-method PUT `
            --region $REGION `
            --output json | ConvertFrom-Json
        
        Write-Host "   Authorization: $($method.authorization)" -ForegroundColor $(if ($method.authorization -eq "NONE") { "Green" } else { "Red" })
        Write-Host "   API Key Required: $($method.apiKeyRequired)" -ForegroundColor $(if (-not $method.apiKeyRequired) { "Green" } else { "Red" })
    } else {
        Write-Host "   ❌ /authenticate resource NOT found!" -ForegroundColor Red
    }
} catch {
    Write-Host "   ⚠️  Could not check API Gateway: $_" -ForegroundColor Yellow
}

Write-Host ""

# 2. Check API Gateway Integration
Write-Host "2. Checking API Gateway Integration..." -ForegroundColor Yellow
try {
    if ($authenticateResource) {
        $integration = aws apigateway get-integration `
            --rest-api-id $API_ID `
            --resource-id $authenticateResource.id `
            --http-method PUT `
            --region $REGION `
            --output json | ConvertFrom-Json
        
        Write-Host "   Integration Type: $($integration.type)" -ForegroundColor $(if ($integration.type -eq "HTTP_PROXY") { "Green" } else { "Yellow" })
        Write-Host "   Integration URI: $($integration.uri)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "   ⚠️  Could not check integration: $_" -ForegroundColor Yellow
}

Write-Host ""

# 3. Check ECS Service Status
Write-Host "3. Checking ECS Service Status..." -ForegroundColor Yellow
try {
    $ecsService = aws ecs describe-services `
        --cluster $CLUSTER `
        --services $SERVICE `
        --region $REGION `
        --output json | ConvertFrom-Json
    
    if ($ecsService.services) {
        $service = $ecsService.services[0]
        Write-Host "   Service Status: $($service.status)" -ForegroundColor Green
        Write-Host "   Running Count: $($service.runningCount)" -ForegroundColor Cyan
        Write-Host "   Desired Count: $($service.desiredCount)" -ForegroundColor Cyan
        
        if ($service.runningCount -eq 0) {
            Write-Host "   ⚠️  WARNING: No tasks running!" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "   ⚠️  Could not check ECS service: $_" -ForegroundColor Yellow
}

Write-Host ""

# 4. Check ALB Target Health
Write-Host "4. Checking ALB Target Health..." -ForegroundColor Yellow
try {
    $targetGroups = aws elbv2 describe-target-groups --region $REGION --output json | ConvertFrom-Json
    $validatorTargetGroup = $targetGroups.TargetGroups | Where-Object { $_.TargetGroupName -like "*validator*" }
    
    if ($validatorTargetGroup) {
        $health = aws elbv2 describe-target-health `
            --target-group-arn $validatorTargetGroup.TargetGroupArn `
            --region $REGION `
            --output json | ConvertFrom-Json
        
        $healthyCount = ($health.TargetHealthDescriptions | Where-Object { $_.TargetHealth.State -eq "healthy" }).Count
        Write-Host "   Healthy Targets: $healthyCount / $($health.TargetHealthDescriptions.Count)" -ForegroundColor $(if ($healthyCount -gt 0) { "Green" } else { "Red" })
        
        foreach ($target in $health.TargetHealthDescriptions) {
            $status = $target.TargetHealth.State
            $color = if ($status -eq "healthy") { "Green" } else { "Red" }
            Write-Host "   Target $($target.Target.Id): $status" -ForegroundColor $color
        }
    }
} catch {
    Write-Host "   ⚠️  Could not check ALB targets: $_" -ForegroundColor Yellow
}

Write-Host ""

# 5. Check Recent CloudWatch Logs
Write-Host "5. Checking Recent CloudWatch Logs..." -ForegroundColor Yellow
Write-Host "   Looking for middleware and endpoint logs..." -ForegroundColor Cyan

try {
    $startTime = (Get-Date).AddMinutes(-10).ToUniversalTime()
    $startTimeUnix = [int64]((Get-Date $startTime -UFormat %s))
    $startTimeMs = $startTimeUnix * 1000
    
    $logs = aws logs filter-log-events `
        --log-group-name "/ecs/validator-service" `
        --start-time $startTimeMs `
        --filter-pattern "authenticate" `
        --region $REGION `
        --output json | ConvertFrom-Json
    
    $middlewareLogs = $logs.events | Where-Object { $_.message -like "*MIDDLEWARE START*authenticate*" }
    $endpointLogs = $logs.events | Where-Object { $_.message -like "*AUTHENTICATE ENDPOINT REACHED*" }
    $errorLogs = $logs.events | Where-Object { $_.message -like "*401*" -or $_.message -like "*Unauthorized*" }
    
    if ($middlewareLogs) {
        Write-Host "   ✅ Found $($middlewareLogs.Count) middleware logs" -ForegroundColor Green
    } else {
        Write-Host "   ❌ No middleware logs found - request may not be reaching FastAPI" -ForegroundColor Red
    }
    
    if ($endpointLogs) {
        Write-Host "   ✅ Found $($endpointLogs.Count) endpoint logs" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  No endpoint logs found" -ForegroundColor Yellow
    }
    
    if ($errorLogs) {
        Write-Host "   ⚠️  Found $($errorLogs.Count) error logs" -ForegroundColor Yellow
        Write-Host "   Recent errors:" -ForegroundColor Yellow
        $errorLogs | Select-Object -Last 3 | ForEach-Object {
            Write-Host "     $($_.message)" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "   ⚠️  Could not check logs: $_" -ForegroundColor Yellow
}

Write-Host ""

# 6. Test Direct ALB Access (if ALB DNS available)
Write-Host "6. Testing Direct ALB Access..." -ForegroundColor Yellow
Write-Host "   (This bypasses API Gateway to test if FastAPI code works)" -ForegroundColor Cyan

try {
    $loadBalancers = aws elbv2 describe-load-balancers --region $REGION --output json | ConvertFrom-Json
    $validatorLB = $loadBalancers.LoadBalancers | Where-Object { $_.LoadBalancerName -like "*validator*" }
    
    if ($validatorLB) {
        $albDNS = $validatorLB.DNSName
        Write-Host "   ALB DNS: $albDNS" -ForegroundColor Cyan
        Write-Host "   Test with: curl -X PUT http://$albDNS/authenticate -H 'Content-Type: application/json' -d @auth.json" -ForegroundColor Yellow
    } else {
        Write-Host "   ⚠️  Could not find ALB" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️  Could not check ALB: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== DIAGNOSTIC COMPLETE ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. If middleware logs are missing → Check ALB and security groups" -ForegroundColor White
Write-Host "2. If endpoint logs are missing → Check FastAPI route registration" -ForegroundColor White
Write-Host "3. If 401 errors persist → Check FastAPI security configuration" -ForegroundColor White
Write-Host "4. Test direct ALB access to isolate API Gateway issues" -ForegroundColor White

