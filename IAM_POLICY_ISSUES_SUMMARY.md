# IAM Policy Issues Summary

## 🚨 CRITICAL ISSUES FOUND

### Issue #1: Missing Multipart Upload Actions ⚠️ CRITICAL

**Location**: `infra/modules/api-gateway/main.tf` - `lambda_s3_policy`

**Problem**: Lambda functions require multipart upload permissions but policy is missing them.

**Code Requirements** (`src/services/package_service.py`):
- Line 218: `s3.create_multipart_upload()` - **Missing permission**
- Line 233: `s3.upload_part_copy()` - **Missing permission**
- Line 249: `s3.complete_multipart_upload()` - **Missing permission**

**Current Policy Has:**
- ✅ s3:GetObject
- ✅ s3:PutObject
- ✅ s3:DeleteObject
- ✅ s3:AbortMultipartUpload
- ✅ s3:ListMultipartUploadParts

**Missing:**
- ❌ s3:CreateMultipartUpload
- ❌ s3:CompleteMultipartUpload
- ❌ s3:UploadPartCopy
- ❌ s3:UploadPart (may be needed)

**Impact**: Package upload functionality will **FAIL**. Users cannot upload packages.

**Fix**: Add missing actions to the S3 policy statement.

---

### Issue #2: KMS Condition Too Restrictive for GetObject ⚠️ HIGH

**Location**: `infra/modules/api-gateway/main.tf` - `lambda_s3_policy` line 1520-1522

**Problem**: KMS encryption condition applies to ALL actions including GetObject.

**Current Condition:**
```json
"Condition": {
  "StringEquals": {
    "s3:x-amz-server-side-encryption": "aws:kms"
  }
}
```

**Issue**: 
- Condition applies to ALL actions in the statement (GetObject, PutObject, DeleteObject, etc.)
- GetObject might fail if existing objects don't have KMS encryption headers
- S3 conditions for GetObject typically check object metadata, not request headers
- The `s3:x-amz-server-side-encryption` condition works for PutObject but may not work correctly for GetObject

**Impact**:
- Lambda might not be able to read existing objects without KMS headers
- Could break existing package downloads

**Fix Options**:
1. **Split statements**: Separate GetObject from PutObject operations
2. **Remove condition for GetObject**: Only require KMS for writes
3. **Make condition optional for reads**: Use conditional logic

---

### Issue #3: KMS Condition May Not Work for GetObject ⚠️ MEDIUM

**Technical Issue**: The `s3:x-amz-server-side-encryption` condition key:
- Works for PutObject (checks request header)
- May NOT work for GetObject (object metadata vs request header)
- S3 condition keys are action-specific

**Impact**: GetObject operations might fail even with the condition.

**Solution**: Split the policy into two statements:
1. Read operations (GetObject, GetObjectTagging) - no KMS condition
2. Write operations (PutObject, etc.) - with KMS condition

---

## ✅ What's Working Correctly

1. ✅ Prefix restriction (`packages/*`) - Good
2. ✅ DynamoDB split read/write - Good
3. ✅ KMS policy for encryption - Good
4. ✅ Policies deployed and attached - Good
5. ✅ Old broad policy removed - Good

---

## 📋 Required Fixes

### Fix 1: Add Missing Multipart Upload Actions

Update `lambda_s3_policy` to include:

```hcl
Action = [
  "s3:GetObject",
  "s3:GetObjectTagging",
  "s3:PutObject",
  "s3:PutObjectTagging",
  "s3:DeleteObject",
  "s3:AbortMultipartUpload",
  "s3:ListMultipartUploadParts",
  "s3:CreateMultipartUpload",      # ADD
  "s3:CompleteMultipartUpload",    # ADD
  "s3:UploadPartCopy"              # ADD
]
```

### Fix 2: Split S3 Policy Statements (Separate Read/Write)

Split the S3 policy into two statements:

**Statement 1: Read Operations (No KMS condition)**
```hcl
{
  Sid    = "ReadPackages"
  Effect = "Allow"
  Action = [
    "s3:GetObject",
    "s3:GetObjectTagging"
  ]
  Resource = ["arn:aws:s3:::${var.artifacts_bucket}/packages/*"]
  # NO KMS condition for reads
}
```

**Statement 2: Write Operations (With KMS condition)**
```hcl
{
  Sid    = "WritePackagesWithKMS"
  Effect = "Allow"
  Action = [
    "s3:PutObject",
    "s3:PutObjectTagging",
    "s3:DeleteObject",
    "s3:AbortMultipartUpload",
    "s3:ListMultipartUploadParts",
    "s3:CreateMultipartUpload",
    "s3:CompleteMultipartUpload",
    "s3:UploadPartCopy"
  ]
  Resource = ["arn:aws:s3:::${var.artifacts_bucket}/packages/*"]
  Condition = {
    StringEquals = {
      "s3:x-amz-server-side-encryption" = "aws:kms"
    }
  }
}
```

---

## 🎯 Priority

1. **CRITICAL**: Add multipart upload actions (breaks package uploads)
2. **HIGH**: Fix KMS condition for GetObject (might break downloads)
3. **MEDIUM**: Split read/write statements (best practice)

---

## 📝 Status

- ✅ Issue #30 (broad policy) - FIXED
- ❌ Missing multipart upload actions - NEEDS FIX
- ⚠️ KMS condition issue - NEEDS FIX
- ✅ Prefix restrictions - WORKING
- ✅ DynamoDB restrictions - WORKING
