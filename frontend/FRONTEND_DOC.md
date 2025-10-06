Dev-ACME/
├─ frontend/
│ ├─ src/
│ │ ├─ pages/
│ │ │ ├─ Home.tsx
│ │ │ ├─ Directory.tsx
│ │ │ ├─ Upload.tsx
│ │ │ ├─ Rate.tsx
│ │ │ └─ Admin.tsx
│ │ ├─ components/
│ │ │ ├─ NavBar.tsx
│ │ │ ├─ PackageCard.tsx
│ │ │ ├─ SearchBar.tsx
│ │ │ └─ MetricChart.tsx
│ │ ├─ services/
│ │ │ └─ api.ts
│ │ ├─ App.tsx
│ │ └─ main.tsx
│ ├─ tests/
│ │ └─ selenium/
│ │ ├─ upload_test.js
│ │ ├─ search_test.js
│ │ └─ rate_test.js
│ ├─ vite.config.ts
│ └─ package.json

## 🎯 Purpose
Create a **browser-accessible, ADA-compliant UI** that connects to your backend REST API and AWS-hosted services.  
Users should be able to:
- Upload & update package `.zip` files  
- Check ratings (Net Score + subscores)  
- Search & download packages  
- Reset registry (admin only)

## 🧱 Tech Stack

| Category | Tool | Purpose |
|-----------|------|----------|
| Framework | React + Vite (TypeScript) | Fast modular SPA build |
| UI Lib | Chakra UI / Material UI | Accessibility & responsiveness |
| Routing | React Router v6 | Navigation |
| HTTP Client | Axios | REST API calls |
| Forms | React Hook Form | Validation & upload handling |
| Accessibility Testing | axe-core + Lighthouse | WCAG 2.1 AA compliance |
| Testing | Jest + Selenium WebDriverJS | Unit + E2E automation |
| Deployment | AWS S3 + CloudFront | Static hosting + CDN |
| CI/CD | GitHub Actions | Automated build / test / deploy |

---

## 🔑 Core Features

| Feature | Description | REST Endpoint |
|----------|--------------|---------------|
| **Home** | Overview, navigation | — |
| **Directory View** | Lists all packages | `/packages/` |
| **Search** | Regex search | `/packages/search?q=` |
| **Upload** | Upload `.zip` (+ debloat flag) | `/packages/upload` |
| **Rate** | Show metrics & NetScore | `/packages/rate/{name}` |
| **Download** | Download selected version | `/packages/{name}/{ver}` |
| **Reset** | Reset system state | `/reset` |

---

## ♿ ADA Compliance Checklist
- Semantic HTML (`<header>`, `<main>`, `<nav>` etc.)  
- ARIA labels for buttons and inputs  
- Full keyboard navigation  
- Contrast ratio ≥ 4.5 : 1  
- Tested via axe-core browser plugin and Lighthouse  

---

## 🧩 Integration Points
- **Backend / REST Team:** Provide OpenAPI schema and base URL  
- **AWS Team:** Expose public endpoint + bucket for frontend deploy  
- **Cybersecurity:** Verify secure token handling / CORS policies  
- **Testing Lead:** Add UI tests to global CI pipeline  

---

## ⚙️ CI/CD Pipeline
**GitHub Actions** (`.github/workflows/frontend-deploy.yml`)
```yaml
on:
  push:
    branches: [main]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci --prefix frontend
      - run: npm test --prefix frontend
      - run: npm run build --prefix frontend
      - uses: aws-actions/configure-aws-credentials@v3
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - run: aws s3 sync frontend/dist s3://trustworthy-registry-frontend --delete
      - run: aws cloudfront create-invalidation --distribution-id ${{ secrets.CLOUDFRONT_ID }} --paths "/*"
🧪 Testing Plan
Test	Tool	Goal
Upload Flow	Selenium	Verify file upload success
Search Results	Selenium	Regex filter accuracy
Rating Display	Jest + DOM testing	Proper subscore rendering
Accessibility	axe-core	Ensure WCAG AA compliance

🧭 Implementation Timeline
Week	Tasks	Owner
1	Setup Vite + React scaffold + CI pipeline	Ethan
2	Home + Directory + Navbar components	Ethan
3	REST API integration (Axios services)	Ethan
4	Upload / Rate / Download pages	Ethan
5	Accessibility + Selenium tests	Ethan
6	AWS S3 + CloudFront deployment setup	AWS teammate + Ethan
7	Polish + Docs + bug fixes	Team

🔒 Security and Best Practices
Use HTTPS requests only

Sanitize user inputs on upload forms

Never store API keys client-side; use AWS IAM roles or GitHub Secrets

Apply CORS policy to restrict origins

Log errors without leaking sensitive data

🧾 References
OpenAPI Spec

WCAG 2.1 AA Guidelines

AWS S3 Hosting Guide

React Testing with Jest

Selenium Docs

✅ Expected Deliverables
Functional React frontend in /frontend

Connected to backend REST API

Accessible (ADA AA compliance)

Selenium + unit tests ≥ 60% coverage

Automated deployment to AWS S3 + CloudFront

Documented architecture and testing results