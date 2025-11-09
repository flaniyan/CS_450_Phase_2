# POST /artifact/model - Curl Commands for Multiple Models

Base URL: `http://localhost:8000`

## First, Get Authentication Token

```powershell
$TOKEN = (curl.exe -s -X PUT "http://localhost:8000/authenticate" -H "Content-Type: application/json" -d "@auth.json").Replace('"', '')
```

---

## POST /artifact/model Commands

**⚠️ Important:** Use the here-string method below. `ConvertTo-Json` can sometimes have issues with curl.exe in PowerShell.

### 1. google-bert/bert-base-uncased

```powershell
# Method 1: Using --data-raw (recommended)
$json = '{"url": "https://huggingface.co/google-bert/bert-base-uncased"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json

# Method 2: Using a temporary file
$json = '{"url": "https://huggingface.co/google-bert/bert-base-uncased"}'
$json | Out-File -FilePath "temp.json" -Encoding utf8 -NoNewline
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" -d "@temp.json"
Remove-Item "temp.json"
```

### 2. parvk11/audience_classifier_model

```powershell
$json = '{"url": "https://huggingface.co/parvk11/audience_classifier_model"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 3. distilbert/distilbert-base-uncased-distilled-squad

```powershell
$json = '{"url": "https://huggingface.co/distilbert/distilbert-base-uncased-distilled-squad"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 4. caidas/swin2SR-lightweight-x2-64

```powershell
$json = '{"url": "https://huggingface.co/caidas/swin2SR-lightweight-x2-64"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 5. vikhyatk/moondream2

```powershell
$json = '{"url": "https://huggingface.co/vikhyatk/moondream2"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 6. microsoft/git-base

```powershell
$json = '{"url": "https://huggingface.co/microsoft/git-base"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 7. WinKawaks/vit-tiny-patch16-224

```powershell
$json = '{"url": "https://huggingface.co/WinKawaks/vit-tiny-patch16-224"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 8. patrickjohncyh/fashion-clip

```powershell
$json = '{"url": "https://huggingface.co/patrickjohncyh/fashion-clip"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

### 9. lerobot/diffusion_pusht

```powershell
$json = '{"url": "https://huggingface.co/lerobot/diffusion_pusht"}'
curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
```

---

## Batch Script - Run All Models

```powershell
# Get token first
$TOKEN = (curl.exe -s -X PUT "http://localhost:8000/authenticate" -H "Content-Type: application/json" -d "@auth.json").Replace('"', '')

# Array of model URLs
$models = @(
    "https://huggingface.co/google-bert/bert-base-uncased",
    "https://huggingface.co/parvk11/audience_classifier_model",
    "https://huggingface.co/distilbert/distilbert-base-uncased-distilled-squad",
    "https://huggingface.co/caidas/swin2SR-lightweight-x2-64",
    "https://huggingface.co/vikhyatk/moondream2",
    "https://huggingface.co/microsoft/git-base",
    "https://huggingface.co/WinKawaks/vit-tiny-patch16-224",
    "https://huggingface.co/patrickjohncyh/fashion-clip",
    "https://huggingface.co/lerobot/diffusion_pusht"
)

# Post each model
foreach ($modelUrl in $models) {
    Write-Host "Posting: $modelUrl"
    $json = "{`"url`": `"$modelUrl`"}"
    curl.exe -X POST "http://localhost:8000/artifact/model" -H "X-Authorization: bearer $TOKEN" -H "Content-Type: application/json" --data-raw $json
    Write-Host ""
}
```

---

## Notes

- The endpoint requires authentication via `X-Authorization: bearer <token>` header
- The JSON body must include a `url` field
- **Use `--data-raw` instead of `-d`** - This ensures PowerShell passes the JSON correctly to curl.exe
- **Use single quotes with plain JSON strings** - This prevents PowerShell from interpreting special characters
- If `--data-raw` doesn't work, use the temporary file method shown in example 1
- Optional: You can add a `version` field to the JSON body if needed: `$json = '{"url": "https://...", "version": "main"}'`
