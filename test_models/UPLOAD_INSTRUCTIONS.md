# Manual Upload Test Package

## Package Details
- **File**: `manual-upload-model.zip`
- **Size**: 2,844 bytes
- **Location**: `CS_450_Phase_2/test_models/manual-upload-model.zip`

## Package Contents
- `config.json` - GPT-2 model configuration
- `README.md` - Documentation
- `pytorch_model.bin` - Model weights (simulated)
- `tokenizer.json` - Tokenizer configuration
- `tokenizer_config.json` - Tokenizer settings
- `vocab.json` - Vocabulary file

## Upload Instructions

### Method 1: Website Upload
1. **Open your browser** and go to:
   - Local: `http://localhost:3000/upload`
   - AWS: `https://d6zjk2j65mgd4.cloudfront.net/upload`

2. **Select the ZIP file**:
   - Navigate to: `CS_450_Phase_2/test_models/manual-upload-model.zip`
   - Click "Choose File" and select the ZIP file

3. **Enter package details**:
   - **Model Name**: `manual-test-gpt2`
   - **Version**: `2.0.0`
   - **Description**: `GPT-2 test model for manual upload`

4. **Click Upload**

### Method 2: API Upload (Alternative)
If the website upload doesn't work, you can use the API:

```bash
curl -X POST "http://localhost:3000/api/packages/models/manual-test-gpt2/versions/2.0.0/upload" \
  -F "file=@manual-upload-model.zip"
```

## Expected Results
After successful upload:
- Package will appear in the directory: `/directory`
- API will list the package: `/api/packages`
- Package can be downloaded: `/api/packages/models/manual-test-gpt2/versions/2.0.0/download`

## Verification
Check that the package appears in:
- Local directory: `http://localhost:3000/directory`
- AWS directory: `https://d6zjk2j65mgd4.cloudfront.net/directory`
- API response: `http://localhost:3000/api/packages`
