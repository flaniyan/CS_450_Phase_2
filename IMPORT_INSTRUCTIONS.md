# Import API Gateway GET Method - One-Time Fix

## Problem
The GET method for `/artifact/{artifact_type}` already exists in AWS but not in Terraform state.

## Optimal Solution: Import Once

**Step 1: Get the resource ID**
```powershell
$API_ID = "1q1x0d7k93"
$ARTIFACT_ID = aws apigateway get-resources --rest-api-id $API_ID --query "items[?pathPart=='artifact'].id" --output text
$RESOURCE_ID = aws apigateway get-resources --rest-api-id $API_ID --query "items[?pathPart=='{artifact_type}' && parentId=='$ARTIFACT_ID'].id" --output text
Write-Host "Resource ID: $RESOURCE_ID"
```

**Step 2: Import the method**
```powershell
cd infra\envs\dev
terraform import "module.api_gateway.aws_api_gateway_method.artifact_type_get" "$API_ID/$RESOURCE_ID/GET"
```

**Step 3: Verify**
```powershell
terraform plan
# Should show no changes needed (or only desired changes)
```

**Step 4: Commit the updated state**
The Terraform state will now include the imported method. The CI/CD import step can be removed.

