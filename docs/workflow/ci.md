## ⚙️ Continuous Integration (CI)

The **Continuous Integration (CI)** workflow ensures that every code change is automatically built, tested, and verified before it is merged into the `main` branch.  
This automation keeps the project stable, prevents broken code from being deployed, and ensures consistent behavior across environments.

### 🧩 Purpose

The goal of CI is to **catch issues early** before they reach production.  
Every time code is pushed or a pull request (PR) is opened, GitHub Actions runs the CI pipeline to make sure the project installs, passes tests, and follows coding standards.

### ⚙️ How It Works

1. **Trigger:** Runs automatically on every pull request or push to `main`.
2. **Setup:** Checks out the repository and sets up Python 3.12.
3. **Install:** Runs
   ```bash
   python -u run.py install
   ```
