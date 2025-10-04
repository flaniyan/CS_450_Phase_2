# AWS usage for CS_450_Phase_2

## Services and purpose
- S3 (bucket: pkg-artifacts): store npm package zip files; SSE-KMS; private access.
  - packages/${pkgName}/${version}/package.zip
  - validators/${pkgName}/${version}/validator.js
- DynamoDB: metadata tables (users, tokens, packages, uploads, downloads) with TTL for tokens.
- API Gateway + Lambda: REST API for upload/search/download; issues presigned S3 URLs; runs validator for sensitive packages.
- CloudWatch: logs, metrics, alarms; dashboards for p95 latency and 5xx rate.
- KMS + Secrets Manager: encryption keys and admin bootstrap secret.

## storage.js contract (Node.js)
Use this module from the REST API implementation.

Functions:
- async uploadInit(pkgName, version, options) -> { uploadId }
- async uploadPart(pkgName, version, uploadId, partNumber, streamOrBuffer) -> { etag }
- async uploadCommit(pkgName, version, uploadId, parts) -> void
- async uploadAbort(pkgName, version, uploadId) -> void
- async getDownloadUrl(pkgName, version, ttlSeconds=300) -> { url, expiresAt }
- async putValidatorScript(pkgName, version, scriptBuffer) -> void
- async deleteValidatorScript(pkgName, version) -> void

S3 layout:
- packages/${pkgName}/${version}/package.zip
- validators/${pkgName}/${version}/validator.js

Access patterns:
- Upload uses S3 multipart; state tracked in DDB table `uploads` with conditional writes.
- Download checks RBAC, runs validator if present, then returns presigned URL. Each download logged to `downloads` with user, pkg, version, timestamp.

Local development:
- Use sandbox AWS credentials or LocalStack.
- Env vars: AWS_REGION, ARTIFACTS_BUCKET, DDB_TABLE_USERS, DDB_TABLE_PACKAGES, DDB_TABLE_UPLOADS, DDB_TABLE_DOWNLOADS.

Security:
- Buckets are private; presigned URLs have short TTL. KMS on S3/DynamoDB. Validator Lambda runs with least-privilege role.

Team workflow:
- Infra via Terraform with GitHub OIDC. On merge to main: plan/apply, deploy Lambdas, run smoke tests.
