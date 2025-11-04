# Real HuggingFace Models for Manual Upload

## 📦 **Downloaded Model Packages**

The following real HuggingFace models have been downloaded and packaged for manual upload:

### **1. DistilBERT Base Uncased** 
- **File**: `distilbert-base-uncased.zip` (247 MB)
- **Purpose**: Lightweight BERT model for text classification and understanding
- **Use Case**: General NLP tasks, sentiment analysis, question answering
- **Model ID**: `distilbert-base-uncased`

### **2. GPT-2**
- **File**: `gpt2.zip` (464 MB) 
- **Purpose**: Text generation model
- **Use Case**: Creative writing, text completion, dialogue generation
- **Model ID**: `gpt2`

### **3. Twitter RoBERTa Sentiment**
- **File**: `cardiffnlp-twitter-roberta-base-sentiment-latest.zip` (466 MB)
- **Purpose**: Sentiment analysis specifically trained on Twitter data
- **Use Case**: Social media sentiment analysis, emotion detection
- **Model ID**: `cardiffnlp-twitter-roberta-base-sentiment-latest`

### **4. DialoGPT Small**
- **File**: `microsoft-DialoGPT-small.zip` (302 MB)
- **Purpose**: Conversational AI model
- **Use Case**: Chatbots, dialogue systems, conversational AI
- **Model ID**: `microsoft-DialoGPT-small`

## 🚀 **How to Upload**

### **Method 1: Local Upload (Recommended)**
1. Go to: `http://localhost:3000/upload`
2. Select one of the ZIP files from `real_models/` folder
3. Click Upload
4. You'll be redirected to the directory page

### **Method 2: AWS Direct Upload**
1. Go to: `http://validator-lb-727503296.us-east-1.elb.amazonaws.com/upload`
2. Select one of the ZIP files
3. Click Upload

### **Method 3: API Upload**
```bash
curl -X POST "http://localhost:3000/api/packages/models/{model_id}/versions/1.0.0/upload" \
  -F "file=@real_models/distilbert-base-uncased.zip"
```

## 📋 **Model Details**

Each package contains:
- ✅ `config.json` - Model configuration
- ✅ `pytorch_model.bin` - Model weights
- ✅ `tokenizer.json` - Tokenizer configuration  
- ✅ `tokenizer_config.json` - Tokenizer settings
- ✅ `vocab.json` or `vocab.txt` - Vocabulary
- ✅ `README.md` - Model documentation
- ✅ Additional files (merges.txt, etc.)

## 🎯 **Testing Recommendations**

1. **Start with DistilBERT** - Smallest and fastest to upload
2. **Try GPT-2** - Popular model for text generation
3. **Test Sentiment Model** - Specialized for sentiment analysis
4. **Upload DialoGPT** - Conversational AI capabilities

## 📊 **Expected Results**

After upload, you should see:
- Models listed in the directory page
- Ability to download models via API
- Proper model metadata and documentation
- Integration with ACME CLI scoring system

**Ready to upload! Choose any model and test the upload functionality.** 🎉



