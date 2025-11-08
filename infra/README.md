# Infrastructure Overview

This directory contains the Terraform definition for the Phase-2 deployment. It is split into
environment-specific stacks under `envs/` and reusable modules under `modules/`.

```
infra/
├── envs/
│   └── dev/                # Environment entrypoint (providers, variables, IAM bindings)
│       ├── main.tf         # Calls each module with dev-specific wiring
│       ├── iam_api.tf      # API task IAM policies (least-privilege)
│       ├── iam_validator.tf# Validator task IAM policies (least-privilege)
│       ├── iam_role.tf     # Execution-task roles and trust relationships
│       └── variables.tf    # Environment inputs (region, bucket, image tag, etc.)
└── modules/
    ├── api-gateway/        # API Gateway + Lambda glue
    ├── dynamodb/           # Registry tables
    ├── ecs/                # API & validator services (Fargate)
    ├── iam/                # Legacy shared IAM policy (kept for docs/tests)
    ├── monitoring/         # CloudWatch, KMS, Secrets Manager
    └── s3/                 # Artifact bucket
```

## IAM Policy Structure

All task roles are defined in `envs/dev/iam_role.tf` and receive narrowly scoped policies from the
following files:

- `envs/dev/iam_api.tf`
  - `api_ddb_rw_managed` – read/write only to the `packages` table + indexes.
  - `api_s3_packages_rw_managed` – list/put/get/delete under `pkg-artifacts/packages/*` with SSE-KMS enforced.
  - `api_kms_s3_managed` – grants the S3 KMS key permissions via `kms:ViaService = s3.us-east-1.amazonaws.com`.
- `envs/dev/iam_validator.tf`
  - `validator_ddb_min_rw_managed` – read + update specific fields in the `packages` table.
  - `validator_s3_inputs_ro_managed` – list/get limited to `pkg-artifacts/validator/inputs/*`.
  - `validator_kms_s3_ro_managed` – decrypt via the same S3 KMS key.
  - `validator_secrets_jwt_ro_managed` – retrieve the JWT secret from Secrets Manager, decrypting only through that service.

These policies replaced the original broad `*` grants and are now validated automatically.

## IAM Compliance Test

We ship a Terratest guard that fails the build if any Terraform-managed IAM policy includes
`Action="*"` or `Resource="*"`.

```
cd tests/terraform
go test ./...
```

The test consumes the Terraform plan for `envs/dev` and walks every `aws_iam_policy` resource to
ensure only explicit actions and resources are present. Update or extend it whenever new policies
are added.
