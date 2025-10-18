# 🔐 Security Policy – ACME Trustworthy Module Registry

## 📣 Reporting Vulnerabilities

If you discover a security issue or vulnerability in this project, **report it privately** to the maintainers:

- **Email:** team106@purdue.edu
- **Maintainers:** Security Lead
- **GitHub:** Do _not_ open public issues for vulnerabilities.
- Response target: **within 5 business days**.
  We follow responsible-disclosure practices and will credit reporters after resolution.

---

## 🧩 Supported Versions

| Branch                    | Supported | Notes                               |
| ------------------------- | --------- | ----------------------------------- |
| `main`                    | ✅        | Production / deployment branch      |
| `security`                | 🧪        | Security analysis & STRIDE tracking |
| feature / legacy branches | ❌        | Unsupported                         |

---

## ☁️ System Overview

**Platform:** AWS ECS Fargate + Lambda + API Gateway + S3 + DynamoDB + KMS + Secrets Manager + CloudWatch + CloudTrail

**Purpose:** Internal package and model registry ensuring secure upload, validation, and controlled download of software artifacts.

**High-level flow:**
User → API Gateway → Lambda → ECS Validator → S3 / DynamoDB ↔ KMS / Secrets Manager ↔ CloudWatch + CloudTrail.

---

## 🧱 Security Measures

### 🔑 Authentication & Authorization

- All requests require **JWT authentication** (10 h / 1,000 use limit) signed via **AWS KMS**.
- **Auth Lambda** validates tokens on every call; expired or forged tokens rejected.
- **Group_106 IAM policy** grants least-privilege access; admins use MFA.
- Token consumption tracked in **DynamoDB (tokens table)** to prevent replay.

### 🗄️ Data Storage & Integrity

- **S3 (pkg-artifacts)** – private, SSE-KMS encrypted, versioned.
  - Objects: `packages/{pkg}/{ver}/package.zip`, `validators/{pkg}/{ver}/validator.js`
  - Upload/download only via **presigned URLs (≤ 300 s TTL)**.
- **DynamoDB tables** – `users`, `tokens`, `packages`, `uploads`, `downloads`.
  - Conditional writes & TTL enforce consistency and token expiry.
- Every package stored with a **SHA-256 hash**, verified by the Validator Service.

### 🧠 Validator Service (Sandbox)

- Runs in **ECS Fargate (Node 22)** behind an **Application Load Balancer**.
- Executes uploaded validator scripts in an **isolated sandbox** with CPU + memory quotas.
- **Timeout ≤ 5 s** enforced to prevent DoS.
- Environment secrets read-only and KMS-encrypted.
- Logs all outcomes to **DynamoDB (downloads)** + **CloudWatch**.

### 🔒 Encryption & Secrets

- **KMS CMKs** encrypt S3 objects, DynamoDB data, and application secrets.
- **Secrets Manager** stores admin bootstrap secrets.
- No plaintext credentials committed or baked into images.

### ☁️ Infrastructure & Monitoring

- **Terraform + GitHub OIDC** handle infrastructure as code; no long-lived keys.
- **CloudWatch** collects metrics and alarms (p95 latency, 5xx rate).
- **CloudTrail** logs all AWS API calls for non-repudiation.
- **AWS Config** monitors for policy drift.
- **WAF + API Gateway throttling** mitigate DoS.
- **Autoscaling groups / Lambda concurrency limits** ensure availability.

### 🧰 Developer Practices

- All PRs require **code review + CI tests**.
- **Flake8 (88 char limit)** and **pytest coverage ≥ 60 %** enforced in CI.
- Secrets never committed; local dev uses sandbox IAM or LocalStack.
- Infra changes through Terraform with `terraform plan + apply` review.

---

## 🧠 Threat Model and Analyses

- **STRIDE Threat Model:** [`docs/security/stride-threat-model.md`](docs/security/stride-threat-model.md)
  – Details system-level threats, trust boundaries, and mitigations.
- **Validator Architecture:** [`docs/security/validator-architecture.md`](docs/security/validator-architecture.md)
  – Describes ECS validator data flow and security controls.
- **Five Whys Root-Cause Analysis:** [`docs/security/five-whys.md`](docs/security/five-whys.md)
  – Documents root causes for JWT, IAM, temp-file, and timeout issues + fixes.
- All artifacts link to [GitHub Issue #9 (Security Epic)](../../issues/9) and sub-issues #29 – #32 for traceability.

---

## 🧱 Ongoing Security Tracking

| Area                 | Mechanism                              |
| -------------------- | -------------------------------------- |
| Threat Model updates | STRIDE docs and ThreatModeler exports  |
| Root-cause lessons   | Five Whys log                          |
| Issue tracking       | GitHub Security Epic #9                |
| Infra audits         | CloudTrail + AWS Config                |
| Policy review        | Quarterly IAM audit via Terraform plan |

---

## 🧭 Disclosure Policy

- We follow **Purdue responsible-disclosure** guidelines.
- Vulnerabilities remain confidential until patched and verified.
- Reporters may request public credit post-remediation.

_Last updated: October 2025_
