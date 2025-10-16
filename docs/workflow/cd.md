## 🚀 Continuous Deployment (CD)

The **Continuous Deployment (CD)** workflow automatically **provisions and updates** the cloud infrastructure after changes are merged to `main` (or when run manually).
It uses **Terraform** and **AWS** to deploy the registry stack reliably and repeatably.

### 🎯 Purpose

Deploy stable code and infrastructure **without manual steps** — ensuring every change to `main` is reflected in the **dev environment** under `infra/envs/dev`.

### ⚙️ How It Works

1. **Trigger:** Runs on every **push to `main`** or via **Run workflow** (manual `workflow_dispatch`).
2. **Checkout:** Pulls the repository so Terraform can read code under `infra/envs/dev`.
3. **AWS Credentials:** Configures access using repository secrets:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (and optional `AWS_SESSION_TOKEN`).

4. **Terraform Setup:** Installs Terraform and disables the wrapper for clean logs.
5. **Init:**

   ```bash
   terraform init -input=false
   ```

   (Working directory: `infra/envs/dev`)

6. **Workspace:** Selects (or creates) the `dev` workspace:

   ```bash
   terraform workspace select dev || terraform workspace new dev
   ```

7. **Plan:** Previews changes and stores them in a plan file:

   ```bash
   terraform plan -out=tfplan -input=false
   ```

8. **Apply:** Applies the plan non-interactively:

   ```bash
   terraform apply -auto-approve tfplan
   ```

9. **Outputs:** Reads the validator service URL from Terraform outputs:

   ```bash
   terraform output -raw validator_service_url
   ```

10. **Health Check:** Polls `GET /health` until the service responds OK. If it never becomes healthy, the job **fails** to prevent a bad deploy.

### ✅ Result

- Successful runs **update AWS resources** (Lambdas, ECS/Fargate validator, S3, DynamoDB) and confirm the service is healthy.
- Failed health checks **stop the release**, signaling the team to investigate or roll back.
