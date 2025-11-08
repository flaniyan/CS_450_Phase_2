# Services Overview

This directory contains the main service modules that power the Phase‑2 backend. Highlights:

- `auth_service.py` – registration, login, JWT issuance.
- `package_service.py` / `s3_service.py` – artifact storage and listing.
- `rating.py`, `license_compatibility.py` – metrics and license checks.
- `validator_service.py` – per-model validation and download authorization.

## Validator Timeout Safeguard

The validator service executes customer-provided scripts stored in S3 under `validators/{pkg}/{version}/validator.py`. To prevent long‑running or malicious scripts from exhausting resources, the execution now happens inside a subprocess with a configurable timeout:

- Environment variable: `VALIDATOR_TIMEOUT_SEC` (defaults to `5` seconds).
- Implementation: `execute_validator` spawns a separate process, waits up to the timeout, and terminates the process if it is still alive.
- Failure mode: the API returns `{"valid": False, "error": "Validator execution timed out …"}` and the attempt is logged in DynamoDB. Each timeout also increments the CloudWatch metric `validator.timeout.count` (namespace configurable via `VALIDATOR_METRIC_NAMESPACE`) for alerting.

See `tests/unit/test_validator_timeout.py` for regression coverage of both success and timeout paths.
