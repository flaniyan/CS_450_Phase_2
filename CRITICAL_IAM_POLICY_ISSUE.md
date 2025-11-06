# 🚨 CRITICAL IAM Policy Issue Found

## Issue: Missing Multipart Upload Actions in Lambda Policy

### Problem

The Lambda execution role is **missing critical S3 multipart upload permissions** that are required by the package upload functionality.

### What the Code Uses

In `src/services/package_service.py`, the `commit_upload` function uses:

1. **Line 218**: `s3.create_multipart_upload()` ❌ Missing permission
2. **Line 233**: `s3.upload_part_copy()` ❌ Missing permission  
3. **Line 249**: `s3.complete_multipart_upload()` ❌ Missing permission

### Current Lambda S3 Policy (DEPLOYED)

**Has:**
- ✅ s3:GetObject
- ✅ s3:PutObject
- ✅ s3:DeleteObject
- ✅ s3:AbortMultipartUpload
- ✅ s3:ListMultipartUploadParts

**Missing (REQUIRED):**
- ❌ **s3:CreateMultipartUpload** - NEEDED by line 218
- ❌ **s3:CompleteMultipartUpload** - NEEDED by line 249
- ❌ **s3:UploadPartCopy** - NEEDED by line 233
- ❌ s3:UploadPart (might be needed)

### Impact

**CRITICAL**: Package upload functionality will **FAIL** because:
- Lambda cannot create multipart uploads
- Lambda cannot complete multipart uploads
- Lambda cannot copy upload parts

This means:
- ❌ Users cannot upload packages
- ❌ Package commit will fail
- ❌ Multipart upload workflow is broken

### Code Evidence

```python
# Line 217-220: Creates multipart upload
multipart_response = s3.create_multipart_upload(
    Bucket=ARTIFACTS_BUCKET, Key=s3_key, ContentType="application/zip"
)

# Line 233-239: Uses upload_part_copy
copy_response = s3.upload_part_copy(
    Bucket=ARTIFACTS_BUCKET,
    Key=s3_key,
    PartNumber=part_number,
    UploadId=upload_id_s3,
    CopySource={"Bucket": ARTIFACTS_BUCKET, "Key": source_key},
)

# Line 248-254: Completes multipart upload
s3.complete_multipart_upload(
    Bucket=ARTIFACTS_BUCKET,
    Key=s3_key,
    UploadId=upload_id_s3,
    MultipartUpload={"Parts": parts},
)
```

### Fix Required

Add these actions to `lambda_s3_policy` in `infra/modules/api-gateway/main.tf`:

```hcl
Action = [
  "s3:GetObject",
  "s3:GetObjectTagging",
  "s3:PutObject",
  "s3:PutObjectTagging",
  "s3:DeleteObject",
  "s3:AbortMultipartUpload",
  "s3:ListMultipartUploadParts",
  "s3:CreateMultipartUpload",      # ADD THIS
  "s3:CompleteMultipartUpload",    # ADD THIS
  "s3:UploadPartCopy"              # ADD THIS
]
```

### Additional Issue: KMS Condition on GetObject

**Problem**: The KMS encryption condition might prevent reading existing objects:

```json
"Condition": {
  "StringEquals": {
    "s3:x-amz-server-side-encryption": "aws:kms"
  }
}
```

**Impact**: 
- If existing objects don't have KMS encryption headers, GetObject will fail
- The condition applies to ALL actions including GetObject

**Potential Fix**: 
- Separate the condition - only require KMS for PutObject, not GetObject
- Or make KMS condition optional for GetObject operations

### Summary

**Status**: 🚨 **CRITICAL ISSUE**

1. ❌ Missing multipart upload actions (will break package uploads)
2. ⚠️ KMS condition might break reading existing objects
3. ✅ Other restrictions are good (prefix-based, split permissions)

**Priority**: **HIGH** - Fix immediately to restore package upload functionality.
