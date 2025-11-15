# PowerShell script to create or update the GitHub token secret in AWS Secrets Manager
# Usage: .\setup-github-token-secret.ps1 -GitHubToken "YOUR_GITHUB_TOKEN"

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken
)

$SecretName = "acme-github-token"
$Region = "us-east-1"

# Validate token format
if ($GitHubToken -notmatch "^(ghp_|github_pat_)") {
    Write-Warning "Token doesn't start with 'ghp_' or 'github_pat_'. Are you sure it's valid?"
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

# Create JSON secret string
$SecretJson = @{
    github_token = $GitHubToken
} | ConvertTo-Json -Compress

# Check if secret exists
try {
    $existing = aws secretsmanager describe-secret --secret-id $SecretName --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Secret '$SecretName' already exists. Updating..." -ForegroundColor Yellow
        aws secretsmanager update-secret `
            --secret-id $SecretName `
            --secret-string $SecretJson `
            --region $Region
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Secret updated successfully!" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to update secret" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "Creating new secret '$SecretName'..." -ForegroundColor Yellow
    aws secretsmanager create-secret `
        --name $SecretName `
        --description "GitHub personal access token for API rate limits (5000 req/hour)" `
        --secret-string $SecretJson `
        --region $Region
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Secret created successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create secret" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Redeploy the ECS service to pick up the new secret:"
Write-Host "   aws ecs update-service --cluster validator-cluster --service validator-service --force-new-deployment"
Write-Host ""
Write-Host "2. Verify the token is being used by checking logs:"
Write-Host "   aws logs tail /ecs/validator-service --follow | Select-String -Pattern 'github' -CaseSensitive"

