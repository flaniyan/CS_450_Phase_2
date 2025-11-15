## Test Autograder Locally

1. **Start the API**
   ```powershell
   cd CS_450_Phase_2
   uvicorn src.entrypoint:app --host 127.0.0.1 --port 8086
   ```

2. **Authenticate (static grader credentials)**
   
   **Local testing:**
   ```powershell
   $authUri = "http://127.0.0.1:8086/authenticate"
   $tokenResponse = Invoke-RestMethod `
       -Uri $authUri `
       -Method Put `
       -ContentType "application/json" `
       -InFile ".\auth.json"

   # Token is returned as plain text with "bearer " prefix
   $token = $tokenResponse.Trim().Trim('"')
   if ($token -like "bearer *") {
       $token = $token.Substring(7)
   }
   ```

   **Backend API Gateway:**
   ```powershell
   $authUri = "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate"
   $tokenResponse = Invoke-RestMethod `
       -Uri $authUri `
       -Method Put `
       -ContentType "application/json" `
       -InFile ".\auth.json"

   # Token is returned as plain text with "bearer " prefix
   $token = $tokenResponse.Trim().Trim('"')
   if ($token -like "bearer *") {
       $token = $token.Substring(7)
   }
   ```

3. **Set common headers**
   ```powershell
   $headers = @{
     "Content-Type"    = "application/json"
     "X-Authorization" = "bearer $token"
   }
   ```

4. **Ingest a model**
   
   **Local testing:**
   ```powershell
   $body = '{"url":"https://huggingface.co/google-bert/bert-base-uncased"}'
   $ingestResponse = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/model" `
       -Method Post `
       -Headers $headers `
       -Body $body

   $id = $ingestResponse.metadata.id
   Write-Host "Ingested model with ID: $id"
   ```

   **Backend API Gateway:**
   ```powershell
   $body = '{"url":"https://huggingface.co/google-bert/bert-base-uncased"}'
   $ingestResponse = Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model" `
       -Method Post `
       -Headers $headers `
       -Body $body

   $id = $ingestResponse.metadata.id
   Write-Host "Ingested model with ID: $id"
   ```

5. **Verify reads**
   
   **Local testing:**
   ```powershell
   # Get artifact by ID
   $artifact = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifacts/model/$id" `
       -Headers $headers
   Write-Host "Artifact retrieved: $($artifact.metadata.name)"

   # Get artifact by name (use sanitized name with underscores)
   $modelName = "google-bert_bert-base-uncased"  # Slashes replaced with underscores
   $byName = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/byName/$modelName" `
       -Headers $headers
   Write-Host "Found $($byName.Count) artifact(s) by name"
   ```

   **Backend API Gateway:**
   ```powershell
   # Get artifact by ID
   $artifact = Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifacts/model/$id" `
       -Headers $headers
   Write-Host "Artifact retrieved: $($artifact.metadata.name)"

   # Get artifact by name (use sanitized name with underscores)
   $modelName = "google-bert_bert-base-uncased"  # Slashes replaced with underscores
   $byName = Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byName/$modelName" `
       -Headers $headers
   Write-Host "Found $($byName.Count) artifact(s) by name"
   ```

6. **Get model rating**
   ```powershell
   # Get rating for the ingested model
   $rating = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/model/$id/rate" `
       -Headers $headers
   Write-Host "Model rating - Net Score: $($rating.net_score)"
   ```

7. **Query artifacts**
   ```powershell
   # Query all models
   $queryBody = '[{"name": "*", "types": ["model"]}]'
   $artifacts = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifacts" `
       -Method Post `
       -Headers $headers `
       -Body $queryBody
   Write-Host "Found $($artifacts.Count) model artifact(s)"
   ```

