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

## IAM (Group_106)
- Attach the Terraform output policy `group106_project_policy` to your `Group_106`.
- Permissions:
  - S3: Put/Get/List/Multipart only within `packages/*` and `validators/*` in the artifacts bucket.
  - DynamoDB: Put/Get/Update/Query on project tables (`users`, `tokens`, `packages`, `uploads`, `downloads`).

## Team login and setup
- Console access (no root):
  - Visit https://<ACCOUNT_ID>.signin.aws.amazon.com/console and sign in with your IAM username/password.
  - On first login, change your password and set up MFA (IAM > Users > Security credentials > Assign MFA). Use a virtual MFA app.
- Programmatic (CLI) access:
  - Install AWS CLI: `sudo apt update && sudo apt install -y awscli`
  - Ask the account admin to create an Access key for your IAM user (one active key max). Store it in a password manager.
  - Configure: `aws configure` (Access key, Secret key, Default region, Default output). Or use a named profile: `aws configure --profile team`
  - Verify: `aws sts get-caller-identity` (should show your user, not root)
- Using the app locally:
  - Export env: `export AWS_REGION=us-east-1` and `export ARTIFACTS_BUCKET=pkg-artifacts`
  - Start API: `npm start` → Health: `curl localhost:3000/health`
- Using Terraform (dev env):
  - `cd infra/envs/dev && terraform init`
  - `terraform apply -var 'aws_region=us-east-1' -var 'artifacts_bucket=pkg-artifacts'` (uses your current AWS credentials/profile)
  - Outputs include the artifacts bucket name to set in your `.env`/environment.

Notes:
- Never share or commit access keys. Rotate keys if leaked.
- Prefer group-based permissions via `Group_106`; avoid attaching AdminAccess to users.
