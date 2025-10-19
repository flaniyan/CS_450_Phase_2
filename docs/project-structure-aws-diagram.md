# ACME Model Registry - Project Structure & AWS Components Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ACME Model Registry Project Structure                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    src/                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   index.py      │  │   routes/       │  │   services/      │                │
│  │                 │  │                 │  │                 │                │
│  │ Main FastAPI    │  │ packages.py     │  │ s3_service.py   │                │
│  │ application     │  │ handles API     │  │ manages AWS S3  │                │
│  │ entry point     │  │ routing and     │  │ model storage   │                │
│  │ with frontend   │  │ request         │  │ operations      │                │
│  │ templates       │  │ processing      │  │                 │                │
│  │                 │  │                 │  │ rating.py       │                │
│  │                 │  │                 │  │ calculates      │                │
│  │                 │  │                 │  │ model metrics   │                │
│  │                 │  │                 │  │                 │                │
│  │                 │  │                 │  │ auth_service.py │                │
│  │                 │  │                 │  │ handles user    │                │
│  │                 │  │                 │  │ authentication │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   AWS S3        │ │   AWS DynamoDB  │ │   AWS ECS       │
│                 │ │                 │ │                 │
│ Stores model    │ │ Stores model    │ │ Hosts FastAPI  │
│ ZIP files and   │ │ metadata and    │ │ application in  │
│ handles upload/ │ │ search indices  │ │ containerized   │
│ download        │ │ for queries     │ │ environment     │
│ operations      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AWS Infrastructure Layer                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   AWS API       │  │   AWS           │  │   AWS           │                │
│  │   Gateway        │  │   CloudWatch    │  │   IAM           │                │
│  │                 │  │                 │  │                 │                │
│  │ Provides        │  │ Monitors        │  │ Manages         │                │
│  │ external API    │  │ system          │  │ access control  │                │
│  │ endpoint with   │  │ performance     │  │ and permissions│                │
│  │ rate limiting   │  │ and logs        │  │ for AWS         │                │
│  │                 │  │                 │  │ services        │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           External Integrations                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   GitHub API    │  │   HuggingFace   │  │   acmecli/      │                │
│  │   Integration   │  │   Model Hub     │  │   metrics/       │                │
│  │                 │  │                 │  │                 │                │
│  │ Analyzes        │  │ Ingests models  │  │ Contains        │                │
│  │ repository      │  │ from HuggingFace│  │ metric          │                │
│  │ code quality    │  │ hub for scoring │  │ calculation     │                │
│  │ and pull        │  │ and validation  │  │ modules for     │                │
│  │ requests        │  │                 │  │ model analysis  │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Development Tools                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   GitHub        │  │   LLM Tools      │  │   Testing       │                │
│  │   Ecosystem     │  │                 │  │   Framework     │                │
│  │                 │  │                 │  │                 │                │
│  │ GitHub Actions  │  │ GitHub Copilot  │  │ pytest         │                │
│  │ for CI/CD       │  │ Auto-Review     │  │ for unit tests  │                │
│  │ pipeline        │  │ for code review │  │                 │                │
│  │                 │  │                 │  │ Selenium        │                │
│  │ Dependabot      │  │ ChatGPT for     │  │ for GUI tests   │                │
│  │ for dependency  │  │ engineering     │  │                 │                │
│  │ management      │  │ assistance      │  │                 │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Frontend Layer                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   Jinja2        │  │   Static        │  │   Templates     │                │
│  │   Templates     │  │   Assets        │  │                 │                │
│  │                 │  │                 │  │ home.html       │                │
│  │ Renders dynamic │  │ styles.css      │  │ directory.html  │                │
│  │ web pages with  │  │ provides CSS    │  │ upload.html     │                │
│  │ user interface  │  │ styling for     │  │ rate.html       │                │
│  │ components      │  │ frontend        │  │ admin.html      │                │
│  │                 │  │                 │  │ base.html       │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Testing & Validation                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   Unit Tests    │  │   Integration   │  │   End-to-End    │                │
│  │                 │  │   Tests         │  │   Tests         │                │
│  │ tests/unit/     │  │ tests/integration│  │ test_aws_       │                │
│  │ contains        │  │ contains API    │  │ integration.py  │                │
│  │ individual      │  │ endpoint        │  │ tests complete  │                │
│  │ metric tests    │  │ testing         │  │ system          │                │
│  │                 │  │                 │  │ functionality  │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Infrastructure as Code                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   Terraform     │  │   Docker        │  │   CI/CD         │                │
│  │   Modules       │  │   Containers    │  │   Pipeline      │                │
│  │                 │  │                 │  │                 │                │
│  │ infra/modules/  │  │ Dockerfile      │  │ GitHub Actions │                │
│  │ defines AWS     │  │ containerizes   │  │ automates       │                │
│  │ infrastructure  │  │ application     │  │ testing and     │                │
│  │ resources       │  │ deployment      │  │ deployment      │                │
│  │                 │  │                 │  │                 │                │
│  │                 │  │                 │  │ OpenAPI spec    │                │
│  │                 │  │                 │  │ compliance      │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Key AWS Components Integration:

### **Core AWS Services Used:**

1. **AWS S3 (Simple Storage Service)**
   - **File**: `src/services/s3_service.py`
   - **Infrastructure**: `infra/modules/s3/main.tf`
   - **Purpose**: Model file storage and operations

2. **AWS DynamoDB**
   - **Infrastructure**: `infra/modules/dynamodb/main.tf`
   - **Purpose**: Metadata storage and search indices

3. **AWS ECS (Elastic Container Service)**
   - **Infrastructure**: `infra/modules/ecs/main.tf`
   - **Purpose**: FastAPI application hosting

4. **AWS API Gateway**
   - **Infrastructure**: `infra/modules/api-gateway/main.tf`
   - **Purpose**: External API endpoint

5. **AWS CloudWatch**
   - **Infrastructure**: `infra/modules/monitoring/main.tf`
   - **Purpose**: Monitoring and logging

6. **AWS IAM (Identity and Access Management)**
   - **Infrastructure**: `infra/modules/iam/main.tf`
   - **Purpose**: Access control and permissions


### **Data Flow with AWS Components:**

1. **User Request** → **API Gateway** → **ECS (FastAPI)** → **S3/DynamoDB**
2. **Model Upload** → **S3 Service** → **AWS S3 Bucket** → **CloudWatch Logs**
3. **Model Download** → **S3 Service** → **AWS S3 Bucket** → **CloudWatch Metrics**
4. **Search Query** → **DynamoDB Service** → **AWS DynamoDB** → **Results**
5. **Monitoring** → **CloudWatch Service** → **AWS CloudWatch** → **Alerts**

### **Development Tools Integration:**

1. **GitHub Ecosystem**
   - **GitHub Actions**: CI/CD pipeline for automated testing and deployment
   - **Dependabot**: Automated dependency management and security updates
   - **GitHub Copilot Auto-Review**: Automated code review assistance

2. **LLM Tools**
   - **GitHub Copilot**: Code generation and assistance
   - **ChatGPT**: Engineering process assistance and problem-solving

3. **Testing Framework**
   - **pytest**: Unit and integration testing framework
   - **Selenium**: GUI testing for frontend interface
   - **Coverage**: Line coverage measurement (60%+ baseline requirement)

4. **API Standards**
   - **OpenAPI Specification**: REST API compliance and documentation
   - **REST Architecture**: Fielding's REST principles implementation

5. **Security Tools**
   - **ThreatModeler**: Security design platform
   - **STRIDE Analysis**: Security threat modeling approach
   - **OWASP Top 10**: Security vulnerability assessment

6. **Accessibility Standards**
   - **WCAG 2.1 AA**: Web Content Accessibility Guidelines compliance
   - **ADA Compliance**: Americans with Disabilities Act requirements
   - **Microsoft Accessibility Tools**: Free tools for accessibility testing

### **Performance Track Implementation:**

Since your team is implementing the Performance Track, the diagram includes:

1. **Performance Measurement Tools**
   - **Load Testing**: 100 clients downloading Tiny-LLM from 500-model registry
   - **Latency Metrics**: Mean, median, and 99th percentile measurements
   - **Throughput Analysis**: System capacity under load

2. **AWS Component Comparison**
   - **Lambda vs EC2**: Performance comparison for different compute options
   - **S3 vs RDS**: Object storage vs relational database performance
   - **Configurable Components**: Ability to switch between AWS services

3. **Performance Monitoring**
   - **CloudWatch Metrics**: Real-time performance data collection
   - **System Health Dashboard**: Performance visualization and monitoring
   - **Bottleneck Identification**: Automated detection of performance issues

### **File-to-AWS Mapping:**
Each Python file is clearly connected to its corresponding AWS service:
- `src/services/s3_service.py` → **AWS S3**
- `src/services/auth_service.py` → **AWS IAM**
- `src/services/rating.py` → **Model Analysis**
- `src/acmecli/metrics/` → **Metric Calculations**
- `infra/modules/s3/main.tf` → **AWS S3 Infrastructure**
- `infra/modules/ecs/main.tf` → **AWS ECS Infrastructure**

This diagram provides a complete visual representation of your project's architecture, making it easy to understand how all components work together and which AWS services are being utilized in each part of the system.
