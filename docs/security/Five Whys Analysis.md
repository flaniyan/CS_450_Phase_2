<<<<<<< HEAD
<<<<<<< HEAD
# 🧩 Five Whys Analysis — Trustworthy Module Registry
=======
# 🧩 Five Whys Analysis
>>>>>>> 3e5b6f144d5ac92802d2ae2a7086fdbe1a4bc7a5
=======
# 🧩 Five Whys Analysis — Trustworthy Module Registry
>>>>>>> eda6b84d50b63949d957cac35c29c2f1018e278d

This document applies the **Five Whys** root-cause method to four potential security issues discovered during STRIDE analysis.  
Each issue traces its failure chain to an underlying cause and proposes an actionable mitigation.

---

## ⚠️ Issue 1 – Expired or Forged JWT Tokens Accepted

**Symptom:**  
A user could still access package endpoints with an expired or tampered JWT.

| Why?                                     | Explanation                                                                               |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| **1. Why did this happen?**              | The API did not re-verify JWT signatures or expiration on every request.                  |
| **2. Why wasn’t verification enforced?** | Token validation logic existed only in the `/auth` Lambda, not reused in other functions. |
| **3. Why wasn’t it reused?**             | Each Lambda had its own handler and lacked a shared middleware layer.                     |
| **4. Why was middleware missing?**       | The team prioritized functionality over modular auth early in development.                |
| **5. Why was that choice made?**         | Limited familiarity with API Gateway authorizers and reuse patterns.                      |

**Root Cause:** Authentication not centralized across all endpoints.  
**Fix:** Implement a **shared JWT-verification middleware** or API Gateway **Lambda Authorizer**; enforce token expiry and signature validation on every call.

---

## ⚠️ Issue 2 – Overly Broad IAM Policy for Lambda Execution Role

**Symptom:**  
Lambda functions could access all S3 objects or DynamoDB tables rather than least-privilege subsets.

| Why?                                         | Explanation                                                        |
| -------------------------------------------- | ------------------------------------------------------------------ |
| **1. Why?**                                  | The default AWS managed `AmazonS3FullAccess` policy was attached.  |
| **2. Why was it attached?**                  | It simplified early testing of uploads and downloads.              |
| **3. Why did testing use production roles?** | Separate dev/test IAM roles weren’t created.                       |
| **4. Why weren’t they created?**             | Terraform templates lacked fine-grained IAM modules.               |
| **5. Why was that omitted?**                 | Team unfamiliar with Terraform’s `aws_iam_policy_document` blocks. |

**Root Cause:** Over-permissive IAM role design.  
**Fix:** Replace broad policies with **resource-scoped IAM roles** (S3 prefix restrictions and DynamoDB table-specific actions).  
Run `terraform plan` + `terraform validate` to confirm least privilege.

---

## ⚠️ Issue 3 – Unencrypted Temporary Files in Validator Service

**Symptom:**  
Validator Service stores a temp `.zip` for analysis before deletion; file may remain unencrypted on ECS disk.

| Why?                                | Explanation                                                       |
| ----------------------------------- | ----------------------------------------------------------------- |
| **1. Why is it unencrypted?**       | Node.js writes temp files to container `/tmp` without encryption. |
| **2. Why isn’t `/tmp` ephemeral?**  | Fargate task volume persists briefly after task stops.            |
| **3. Why no cleanup hook?**         | Container lacked a `postValidate` cleanup routine.                |
| **4. Why was cleanup missed?**      | Focus was on validator correctness, not temp hygiene.             |
| **5. Why was that de-prioritized?** | Misjudged risk assuming AWS ECS automatically wiped disks.        |

**Root Cause:** Assumed ephemeral storage instead of enforcing cleanup.  
**Fix:** Encrypt temp files with `crypto.subtle` or Node `fs` streams using **KMS data keys**, and **delete temp files** in a finally block or ECS task epilogue.

---

## ⚠️ Issue 4 – Validator Timeout Allows Resource Exhaustion (DoS)

**Symptom:**  
A malicious validator script could loop indefinitely, consuming CPU and blocking ECS tasks.

| Why?                                 | Explanation                                                          |
| ------------------------------------ | -------------------------------------------------------------------- |
| **1. Why?**                          | The Node.js validator lacked execution time limits.                  |
| **2. Why were no limits applied?**   | No sandbox or worker-thread timeout wrapper implemented.             |
| **3. Why wasn’t that built?**        | Team assumed ECS Fargate would kill hung containers automatically.   |
| **4. Why is that assumption wrong?** | Fargate kills only when CPU/memory quotas are hit, not by wall time. |
| **5. Why was this misunderstood?**   | Lack of detailed reading of ECS task-definition runtime limits.      |

**Root Cause:** Missing per-validator timeout enforcement.  
**Fix:** Run validators inside **isolated Node.js worker threads** with a `setTimeout` kill (≤ 5 s) or configure **ECS task `stopTimeout`** to 5 seconds max.

---

## ✅ Lessons Learned

- Centralize authentication/authorization logic to prevent replay or misuse.
- Apply **least-privilege IAM** and verify policies during code reviews.
- Treat **temporary and intermediate data** as sensitive—encrypt and clean up.
- Sandbox and **time-limit untrusted code** execution to protect system availability.

Together, these mitigations close high-impact gaps identified in the STRIDE analysis and strengthen the registry’s overall cloud-security posture.
