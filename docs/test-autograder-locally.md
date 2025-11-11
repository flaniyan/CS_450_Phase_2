## Test Autograder Locally

1. **Start the API**
   ```powershell
   uvicorn src.entrypoint:app --host 127.0.0.1 --port 8086
   ```

2. **Authenticate (static grader credentials)**
   ```powershell
   $authUri = "http://127.0.0.1:8086/authenticate"
   $tokenResponse = Invoke-RestMethod `
       -Uri $authUri `
       -Method Post `
       -ContentType "application/json" `
       -InFile ".\auth.json"

   $token = $tokenResponse
   ```

   **Authenticate on backend link (static grader credentials)**
   ```powershell
   $authUri = "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/authenticate"
   $tokenResponse = Invoke-RestMethod `
       -Uri $authUri `
       -Method Post `
       -ContentType "application/json" `
       -InFile ".\auth.json"

   $token = $tokenResponse
   ```

3. **Set common headers**
   ```powershell
   $headers = @{
     "Content-Type"    = "application/json"
     "X-Authorization" = $token
   }
   ```

4. **Ingest a model**
   ```powershell
   $body = '{"url":"https://huggingface.co/google-bert/bert-base-uncased"}'
   $ingestResponse = Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/model" `
       -Method Post `
       -Headers $headers `
       -Body $body

   $id = $ingestResponse.metadata.id
  ```

   $body = '{"url":"https://huggingface.co/google-bert/bert-base-uncased"}'
   $ingestResponse = Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model" `
       -Method Post `
       -Headers $headers `
       -Body $body

   $id = $ingestResponse.metadata.id

5. **Verify reads**
   ```powershell
   Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/model/$id" `
       -Headers $headers

   Invoke-RestMethod `
       -Uri "http://127.0.0.1:8086/artifact/byName/google-bert/bert-base-uncased" `
       -Headers $headers
   ```

   Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/model/$id" `
       -Headers $headers

   Invoke-RestMethod `
       -Uri "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/artifact/byName/google-bert/bert-base-uncased" `
       -Headers $headers

