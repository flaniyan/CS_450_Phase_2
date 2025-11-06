# IAM Policy Issues Analysis

## ✅ Lambda Execution Role - Status Check

### Current Deployed Policies

1. **AWSLambdaBasicExecutionRole** ✅
   - AWS managed policy
   - Purpose: CloudWatch logs

2. **lambda-s3-packages-policy** ✅
   - Status: Deployed
   - Restrictions: ✅ Prefix-based (`packages/*`)
   - KMS Requirement: ✅ Required

3. **lambda-ddb-policy** ✅
   - Status: Deployed
   - Split read/write: ✅ Yes

4. **lambda-kms-s3-policy** ✅
   - Status: Deployed
   - Service restriction: ✅ S3 only

## ⚠️ Potential Issues Found

### Issue 1: Missing Multipart Upload Actions in S3 Policy

**Problem**: The deployed S3 policy is missing multipart upload actions that Lambda might need.

**Current Deployed Policy Has:**
- ✅ s3:GetObject
- ✅ s3:PutObject
- ✅ s3:DeleteObject
- ✅ s3:AbortMultipartUpload
- ✅ s3:ListMultipartUploadParts
- ❌ **MISSING**: s3:CreateMultipartUpload
- ❌ **MISSING**: s3:CompleteMultipartUpload
- ❌ **MISSING**: s3:UploadPart
- ❌ **MISSING**: s3:UploadPartCopy

**Code Has:**
Looking at the code (lines 1509-1517), it also doesn't include these actions!

**Impact**: If Lambda functions need to upload large files using multipart upload, they will fail.

### Issue 2: S3 Policy Condition May Be Too Restrictive

**Current Condition:**
```json
"Condition": {
  "StringEquals": {
    "s3:x-amz-server-side-encryption": "aws:kms"
  }
}
```

**Problem**: This requires KMS encryption for ALL operations. However:
- Some existing objects might not have KMS encryption
- Reading existing objects (GetObject) might fail if they don't have this header
- This condition applies to ALL actions including GetObject

**Potential Impact**: 
- Lambda might not be able to read existing objects that don't have KMS encryption headers
- This could break existing functionality

### Issue 3: KMS Policy Service Condition

**Current:**
```json
"kms:ViaService": "s3.us-east-1.amazonaws.com"
```

**Code:**
```hcl
"kms:ViaService" = "s3.${var.aws_region}.amazonaws.com"
```

✅ This matches (us-east-1), but should be verified.

### Issue 4: DynamoDB Policy - Missing Index Permissions Verification

**Current Policy**: Allows access to all indexes (`/*index/*`)

**Potential Issue**: If any table has an index, Lambda can access it. This might be intended, but should be verified.

## 🔍 Detailed Comparison

### S3 Policy - Code vs Deployed

**Code (lines 1509-1517):**
- Missing: CreateMultipartUpload, CompleteMultipartUpload, UploadPart, UploadPartCopy

**Deployed:**
- Same as code - missing multipart upload actions

**Old Broad Policy Had:**
- ✅ CreateMultipartUpload
- ✅ CompleteMultipartUpload
- ✅ UploadPart
- ✅ UploadPartCopy

### Recommendations

1. **Add Missing Multipart Upload Actions** (if Lambda needs large file uploads)
2. **Review KMS Condition** - Consider if GetObject should require KMS header
3. **Test Existing Functionality** - Ensure Lambda can read existing objects
4. **Verify Multipart Upload Requirements** - Check if Lambda functions actually use multipart upload

## ✅ What's Working

1. ✅ Policies are deployed
2. ✅ Old broad policy removed
3. ✅ Prefix restrictions in place
4. ✅ KMS policy attached
5. ✅ DynamoDB split read/write working

## ⚠️ Potential Problems

1. ⚠️ Missing multipart upload actions
2. ⚠️ KMS condition might break reading existing objects
3. ⚠️ Need to verify Lambda function requirements
