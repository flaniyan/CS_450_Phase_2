# 🚀 ACME Registry - Team Setup Guide

This guide will help team members set up and run the ACME Registry API from scratch, both locally and on AWS CloudFront.

## 📋 Prerequisites

Before starting, ensure you have:

- **Python 3.8+** installed
- **Git** installed
- **AWS CLI** configured (for AWS deployment)
- **Docker** installed (optional, for containerized deployment)

## 🏗️ Project Overview

The ACME Registry is a FastAPI-based application that provides:
- **Package Management**: Upload, download, and list AI/ML models
- **Model Rating**: Score models based on various metrics
- **Web Interface**: User-friendly frontend for package management
- **REST API**: Programmatic access to all functionality

## 🚀 Quick Start Options

### Option 1: Local Development (Recommended for Development)

#### Step 1: Clone and Setup
```bash
# Clone the repository
git clone https://github.com/emsilver987/CS_450_Phase_2.git
cd CS_450_Phase_2

# Switch to AWS branch (contains production-ready code)
git checkout AWS

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Run Locally
```bash
# Start the development server
python -m src.index

# Or use the run script
./run install
python -m src.index
```

#### Step 3: Access the Application
- **Main Website**: http://localhost:3000/
- **Package Directory**: http://localhost:3000/directory
- **Upload Page**: http://localhost:3000/upload
- **API Health Check**: http://localhost:3000/health
- **API Packages List**: http://localhost:3000/api/packages

### Option 2: AWS CloudFront (Production Environment)

The application is already deployed and accessible at:
- **Main Website**: https://d6zjk2j65mgd4.cloudfront.net/
- **Package Directory**: https://d6zjk2j65mgd4.cloudfront.net/directory
- **Upload Page**: https://d6zjk2j65mgd4.cloudfront.net/upload
- **API Health Check**: https://d6zjk2j65mgd4.cloudfront.net/health
- **API Packages List**: https://d6zjk2j65mgd4.cloudfront.net/api/packages

### Option 3: Docker Development

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
docker build -t acme-registry .
docker run -p 3000:3000 acme-registry
```

## 🔧 Development Workflow

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and test locally:
   ```bash
   python -m src.index
   ```

3. **Test your changes**:
   - Visit http://localhost:3000/health
   - Test relevant API endpoints
   - Check frontend functionality

4. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request** to merge into the AWS branch

### Testing

```bash
# Run all tests
./run test

# Run specific test files
python -m pytest tests/unit/test_specific.py

# Run scoring tests
./run score urls.txt
```

## 🌐 API Endpoints Reference

### Core API Endpoints

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/health` | GET | Health check | `{"ok": true}` |
| `/api/hello` | GET | Hello world | `{"message": "Hello World"}` |
| `/api/packages` | GET | List all packages | `{"packages": [...]}` |
| `/api/packages/upload` | POST | Upload a package | Multipart form data |
| `/api/packages/{name}/download` | GET | Download package | Binary file |
| `/api/registry/models/{model_id}/{version}/model.zip` | GET | Download model | ZIP file |
| `/api/registry/models/{model_id}/rate` | POST | Rate a model | `{"target": "model_name"}` |

### Frontend Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Homepage |
| `/directory` | Package directory with search |
| `/upload` | Package upload form |
| `/rate` | Model rating interface |

## 📦 Package Management

### Uploading Packages

#### Via Web Interface
1. Go to http://localhost:3000/upload (or CloudFront URL)
2. Select a ZIP file containing your model
3. Optionally enable "debloat" for optimization
4. Click "Upload Package"

#### Via API
```bash
curl -X POST "http://localhost:3000/api/packages/upload" \
  -F "file=@your-model.zip" \
  -F "model_id=your-model-name" \
  -F "version=1.0.0" \
  -F "debloat=false"
```

### Package Structure

Your ZIP file should contain:
```
your-model.zip
├── config.json          # Model configuration
├── pytorch_model.bin     # Model weights
├── tokenizer.json        # Tokenizer (if applicable)
└── other model files...
```

### Downloading Packages

```bash
# Download via API
curl -O "http://localhost:3000/api/packages/your-model/download"

# Or visit the directory page and click download links
```

## 🔍 Model Rating System

### Rating a Model

```bash
# Rate a model via API
curl -X POST "http://localhost:3000/api/registry/models/gpt2/rate" \
  -H "Content-Type: application/json" \
  -d '{"target": "gpt2"}'
```

### Rating Metrics

The system evaluates models based on:
- **License**: Open source compatibility
- **Ramp-up Time**: Ease of getting started
- **Bus Factor**: Code maintainability
- **Performance Claims**: Accuracy of performance metrics
- **Size**: Model efficiency
- **Dataset Quality**: Training data quality
- **Code Quality**: Implementation quality

## 🛠️ Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find and kill the process using port 3000
netstat -ano | findstr :3000
taskkill /PID <PID_NUMBER> /F
```

#### 2. Missing Dependencies
```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

#### 3. AWS S3 Access Issues
- Ensure AWS credentials are configured: `aws configure`
- Check S3 bucket permissions
- Verify the S3 access point is accessible

#### 4. Database Connection Issues
- Check DynamoDB table permissions
- Verify AWS region configuration
- Ensure IAM roles have proper permissions

### Debug Mode

```bash
# Run with debug logging
python -m src.index --log-level debug

# Check application logs
tail -f logs/app.log
```

## 🔐 AWS Configuration

### Required AWS Resources

The application uses these AWS services:
- **S3**: Package storage (`pkg-artifacts` bucket)
- **DynamoDB**: Metadata storage (5 tables)
- **ECS**: Application hosting
- **CloudFront**: CDN and HTTPS
- **IAM**: Permissions and roles

### Environment Variables

```bash
# Required for AWS deployment
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export ARTIFACTS_BUCKET=pkg-artifacts
export PYTHON_ENV=production
```

## 📚 Additional Resources

### Documentation Files
- `README.md` - Main project documentation
- `AWS_SETUP_GUIDE.md` - AWS infrastructure setup
- `CD_SETUP_GUIDE.md` - Continuous deployment setup
- `CD_TESTING_GUIDE.md` - CD pipeline testing

### Useful Commands

```bash
# Check application status
curl http://localhost:3000/health

# List all packages
curl http://localhost:3000/api/packages

# Test model rating
curl -X POST http://localhost:3000/api/registry/models/gpt2/rate \
  -H "Content-Type: application/json" \
  -d '{"target": "gpt2"}'

# Check AWS infrastructure
aws ecs describe-services --cluster validator-cluster --services validator-service
```

## 🤝 Contributing

### Code Style
- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to functions and classes
- Write tests for new functionality

### Pull Request Process
1. Create a feature branch from `AWS`
2. Make your changes with tests
3. Ensure all tests pass
4. Create a PR with a clear description
5. Request review from team members

## 📞 Support

If you encounter issues:
1. Check this guide first
2. Look at existing issues in the repository
3. Ask team members for help
4. Create a new issue with detailed information

---

**Happy coding! 🚀**

*Last updated: October 2025*



