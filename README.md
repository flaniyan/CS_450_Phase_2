# ACME CLI Scoring Toolkit

ACME CLI ingests lists of model repository URLs, pulls rich metadata from GitHub and Hugging Face, evaluates programmable quality metrics, and emits newline-delimited JSON (NDJSON) summaries. The project ships with a thin runner (`run.py`/`run`) for local workflows, a library surface under `acmecli`, and a pytest suite that locks down the heuristics used to score repositories.

## Table of Contents
- [Quick Start](#quick-start)
- [Project Layout](#project-layout)
- [CLI Entry Points](#cli-entry-points)
- [Runtime Data Flow](#runtime-data-flow)
- [Source Modules](#source-modules)
  - [Top-Level Runner](#top-level-runner)
  - [Handlers and Utilities](#handlers-and-utilities)
  - [Scoring and Reporting](#scoring-and-reporting)
  - [Metrics Registry](#metrics-registry)
- [Metric Reference](#metric-reference)
- [Testing and Tooling](#testing-and-tooling)
- [Continuous Integration](#continuous-integration)
- [Sample Inputs and Docs](#sample-inputs-and-docs)
- [Extending the System](#extending-the-system)
- [Operational Notes and Limitations](#operational-notes-and-limitations)

## Quick Start

### Option 1: AWS Cloud Deployment (Production Ready)

The application is deployed on AWS with the following URLs:

**🌐 Production URLs:**
- **Main Website**: `https://d6zjk2j65mgd4.cloudfront.net/`
- **Package Directory**: `https://d6zjk2j65mgd4.cloudfront.net/directory`
- **Upload Packages**: `https://d6zjk2j65mgd4.cloudfront.net/upload` *(Note: CloudFront POST requests need configuration fix)*
- **Rate Packages**: `https://d6zjk2j65mgd4.cloudfront.net/rate`
- **Admin Panel**: `https://d6zjk2j65mgd4.cloudfront.net/admin`

**🔧 Direct AWS URLs (Bypass CloudFront):**
- **Direct Upload**: `http://validator-lb-727503296.us-east-1.elb.amazonaws.com/upload`
- **Direct Directory**: `http://validator-lb-727503296.us-east-1.elb.amazonaws.com/directory`

**📡 API Endpoints:**
- **Health Check**: `https://d6zjk2j65mgd4.cloudfront.net/health`
- **API Hello**: `https://d6zjk2j65mgd4.cloudfront.net/api/hello`
- **List Packages**: `GET https://d6zjk2j65mgd4.cloudfront.net/api/packages`
- **Upload Package**: `POST https://d6zjk2j65mgd4.cloudfront.net/api/packages/models/{model_id}/versions/{version}/upload`
- **Download Package**: `GET https://d6zjk2j65mgd4.cloudfront.net/api/packages/models/{model_id}/versions/{version}/download`
- **Reset Registry**: `POST https://d6zjk2j65mgd4.cloudfront.net/api/packages/reset`

### Option 2: Local Development

1. **Environment Setup**
   ```bash
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install --upgrade pip
   ```
   
2. **Install dependencies and project**
   ```bash
   ./run install
   ```
   
3. **Run the application locally**
   ```bash
   python -m src.index
   ```
   
   **Or using the Unix runner:**
   ```bash
   ./run install  # Install dependencies
   python -m src.index  # Run the application
   ```

4. **Access the local application**
   - Frontend home: `http://localhost:3000/`
   - Package Directory: `http://localhost:3000/directory`
   - Upload Packages: `http://localhost:3000/upload`
   - Rate Packages: `http://localhost:3000/rate`
   - Admin Panel: `http://localhost:3000/admin`
   - API health: `http://localhost:3000/health`
   - API hello: `http://localhost:3000/api/hello`

### Option 3: Docker (Development)

1. **Ensure Docker Desktop is running**
   
2. **Build and run with Docker Compose**
   ```bash
   docker-compose up
   ```
   
3. **Or build and run manually**
   ```bash
   docker build -t validator-api .
   docker run -p 3000:3000 validator-api
   ```

4. **Stop the container**
   ```bash
   docker-compose down
   ```

**Note:** When Uvicorn starts, it displays `http://0.0.0.0:3000` (listening on all interfaces). Access it at `http://localhost:3000` in your browser.

## Package Management API

The application provides a comprehensive package management system with the following capabilities:

### 📦 Package Operations

**Upload Packages:**
- **Frontend**: Use the web interface at `/upload` to upload ZIP files containing HuggingFace models
- **API**: `POST /api/packages/models/{model_id}/versions/{version}/upload`
- **Supported formats**: ZIP files containing HuggingFace model structure (config.json, pytorch_model.bin, tokenizer files, etc.)
- **Features**: Automatic model validation, S3 storage, version management

**List Packages:**
- **Frontend**: Browse packages at `/directory` with search functionality
- **API**: `GET /api/packages?limit=100&name_regex=pattern&version_range=1.0.0-2.0.0`
- **Features**: Pagination, regex filtering, version range filtering

**Download Packages:**
- **API**: `GET /api/packages/models/{model_id}/versions/{version}/download?component=full`
- **Components**: `full` (complete model), `weights` (model weights only), `datasets` (datasets only)
- **Features**: Streaming download, component extraction

**Reset Registry:**
- **API**: `POST /api/packages/reset`
- **Purpose**: Clear all packages from the registry (admin function)

### 🔧 Testing and Development

**Run the test suite:**
```bash
./run test
```
Prints a coverage summary along with the pass count extracted from pytest output.

**Score repositories:**
```bash
./run score urls.txt
```
- Passing no arguments defaults to `urls.txt`.
- NDJSON is written to stdout; redirect to a file to persist results: `./run score urls.txt > reports.ndjson`.

## AWS Infrastructure

The application is deployed on AWS using the following services:

### 🏗️ Architecture Components

- **ECS Fargate**: Containerized FastAPI application running on AWS managed containers
- **Application Load Balancer (ALB)**: Routes traffic to ECS tasks with health checks
- **CloudFront CDN**: Global content delivery with HTTPS and caching
- **S3 Bucket**: Package storage with Access Point for secure access
- **DynamoDB**: Metadata storage for packages and user data
- **ECR**: Container registry for Docker images
- **IAM**: Role-based access control for AWS services

### 📊 Current Deployment Status

**✅ Working Features:**
- Package upload via localhost and direct AWS URLs
- Package listing and directory browsing
- Package download and streaming
- Health checks and API endpoints
- Frontend web interface

**⚠️ Known Issues:**
- CloudFront POST requests blocked (403 error) - needs AllowedMethods configuration update
- Use direct AWS URLs for uploads until CloudFront is fixed

**🔧 Infrastructure Files:**
- `AWS_SETUP_GUIDE.md`: Complete AWS infrastructure documentation
- `AWS_IMPLEMENTATION_SUMMARY.md`: Current deployment status and issues
- `docker-compose.yml`: Local development with Docker
- `Dockerfile`: Container configuration for AWS deployment

## Project Layout

| Path | Description |
| --- | --- |
| `run.py` | CLI orchestrator for install, test, and score flows. |
| `run` | Thin executable shim that re-invokes `run.py` with the active interpreter. |
| `src/acmecli/` | Library package containing handlers, metrics, scoring, and types. |
| `tests/` | Pytest suite that exercises metrics, scoring logic, and reporters. |
| `frontend/templates/` | Jinja templates served by FastAPI for the UI. |
| `frontend/static/` | Static assets (CSS, images) served at `/static`. |
| `docs/` | High-level documentation: overview, frontend, API/src, tests. |
| `.github/workflows/ci.yml` | GitHub Actions workflow mirroring the local run commands. |
| `urls.txt` | Default set of GitHub and Hugging Face URLs used for smoke scoring. |
| `.coveragerc`, `pytest.ini`, `mypy.ini` | Tooling configuration for coverage, pytest defaults, and type checking. |
| `autograder_docs/` | OpenAPI spec and sample payloads for the external autograder service. |

## CLI Entry Points

- `python run.py install` -> installs requirements (user site outside a venv) and the project in editable mode.
- `python run.py test` -> runs pytest with coverage, summarizes pass count, and echoes logs on failure.
- `python run.py score <URL_FILE>` -> executes the scoring pipeline for comma-separated URLs per line.
- `python run.py` (no args) -> shorthand for `python run.py score urls.txt`.
- `run` script -> Unix-friendly wrapper that preserves the active interpreter when executed.

**Logging controls** (implemented in `acmecli/cli.py`):
- `LOG_FILE=/path/to/log.txt` redirects logs to disk and creates directories as needed.
- `LOG_LEVEL` accepts `0` (silent), `1` (info), or `2` (debug). The default is silent mode.

## Runtime Data Flow

1. **Entrypoint resolution** - `run.py:main` parses the command and dispatches to `do_install`, `do_test`, or `do_score`.
2. **URL ingestion** - `acmecli.cli.extract_urls` expands comma-separated URLs per line, while `classify` tags each as GitHub or Hugging Face.
3. **Metadata fetch** - `GitHubHandler.fetch_meta` and `HFHandler.fetch_meta` call the respective public APIs, normalizing selected fields and README text.
4. **Metric evaluation** - `acmecli.metrics.base.REGISTRY` holds metric instances registered via module side effects; `cli.process_url` submits each metric `score` call to a `ThreadPoolExecutor` for parallel evaluation.
5. **Aggregation** - `acmecli.scoring.compute_net_score` combines metric values with predefined weights and reports both the score and aggregation latency.
6. **Emission** - `acmecli.reporter.write_ndjson` serializes a `ReportRow` dataclass to NDJSON for downstream consumption.

## Source Modules

### Top-Level Runner
- `parse_args` (`run.py`) - builds the argparse CLI with `install`, `test`, and `score` subcommands.
- `do_install` (`run.py`) - installs `requirements.txt` (when present) followed by the package itself in editable mode.
- `do_test` (`run.py`) - runs pytest with coverage, scrapes stdout/stderr for counts, and prints a compact summary line.
- `do_score` (`run.py`) - validates the URL file and forwards execution to `acmecli.cli.main`.
- `main` (`run.py`) - wires the subcommands, logging, and the default fallback to scoring URLs.

### Handlers and Utilities
- `setup_logging` (`src/acmecli/cli.py`) - configures root logging according to `LOG_FILE` and `LOG_LEVEL` environment variables.
- `classify`, `extract_urls` (`cli.py`) - map raw URLs to internal categories and expand comma-separated URL lists.
- `GitHubHandler` (`src/acmecli/github_handler.py`) - fetches repository metadata, top contributors, and README content using the GitHub REST API.
- `HFHandler` (`src/acmecli/hf_handler.py`) - resolves Hugging Face model identifiers and retrieves model cards via the public API.
- `InMemoryCache` (`src/acmecli/cache.py`) - simple key and etag in-memory cache that can be swapped for persistent stores.
- `TargetSpec`, `MetricValue`, `ReportRow` (`src/acmecli/types.py`) - dataclasses and protocols describing targets, metric outputs, and the NDJSON schema.

### Scoring and Reporting
- `process_url` (`cli.py`) - orchestrates metadata retrieval, parallel metric execution, net score aggregation, and `ReportRow` construction.
- `compute_net_score` (`src/acmecli/scoring.py`) - multiplies metric values by weights (license 20%, ramp-up 15%, bus factor 12%, performance claims 12%, size 10%, dataset/code 10%, dataset quality 11%, code quality 10%) and averages dict-valued size scores across hardware tiers.
- `compute_netscore` (`scoring.py`) - lightweight helper used in tests to verify weighted sums.
- `write_ndjson`, `Reporter.format` (`src/acmecli/reporter.py`) - emit NDJSON rows and format arbitrary dicts as JSON strings.

### Metrics Registry
- `REGISTRY` (`src/acmecli/metrics/base.py`) - global list populated through the `register` helper.
- `acmecli/metrics/__init__.py` - imports each metric module so their `register(...)` side effects run. Import this package before using `REGISTRY` in custom integrations.

## Metric Reference

Each metric exposes `name` and `score(meta: dict) -> MetricValue`. Implementations live under `src/acmecli/metrics/` and are unit-tested in `tests/`.

| Metric | Module | Purpose and Heuristics |
| --- | --- | --- |
| `LicenseMetric` | `license_metric.py` | Scores LGPLv2.1 compatibility based on SPDX identifiers and README cues; penalizes missing license data. |
| `RampUpMetric` | `ramp_up_metric.py` | Rewards thorough READMEs, quickstart sections, recent commits, project wikis, and star counts to reflect onboarding ease. |
| `BusFactorMetric` | `bus_factor_metric.py` | Estimates sustainability using contributor counts, contribution distribution, organization ownership hints, and fork counts. |
| `PerformanceClaimsMetric` | `performance_claims_metric.py` | Searches README text for benchmarks, metrics, comparisons, and academic references signaling evidence-backed claims. |
| `SizeMetric` | `size_metric.py` | Produces per-platform deployability scores (Raspberry Pi to AWS Server) derived from repository size and README descriptors. |
| `DatasetAndCodeMetric` | `dataset_and_code_metric.py` | Checks for dataset disclosure, code pointers, examples, and project size to gauge resource availability. |
| `DatasetQualityMetric` | `dataset_quality_metric.py` | Looks for high-quality datasets, curation notes, bias considerations, and usage metrics to assess data rigor. |
| `CodeQualityMetric` | `code_quality_metric.py` | Detects testing, documentation, style, dependency management, release cadence, and issue ratios as proxies for engineering health. |
| `HFDownloadsMetric` | `hf_downloads_metric.py` | Normalizes Hugging Face download counts into a 0-1 score; currently excluded from `ReportRow` aggregation but available to consumers. |
| `CLIMetric` | `cli_metric.py` | Rewards repositories that document CLI usage, automation scripts, or install and test instructions. |
| `LoggingEnvMetric` | `logging_env_metric.py` | Measures logging ergonomics via environment-variable support and README mentions. |

## Testing and Tooling

- `python run.py test` executes the full pytest suite.
- Coverage configuration (`.coveragerc`) excludes network-heavy modules from coverage expectations.
- `tests/` contains focused unit tests per metric (for example `tests/test_bus_factor_metric.py`) plus checks for `Reporter` and `scoring` helpers.
- `pytest.ini` pins `tests/` as the discovery root and enforces coverage reports.
- `mypy.ini` opts into Python 3.12 typing, ignoring missing imports for third-party APIs.

## Continuous Integration

`.github/workflows/ci.yml` mirrors local workflows on a self-hosted Windows runner:
1. Checkout repository.
2. Install Python 3.12.
3. Install dependencies via `pip`.
4. Run `python3 run.py install`, `python3 run.py test`, and `python3 run.py` (smoke scoring with `urls.txt`).

## Sample Inputs and Docs

- `urls.txt` demonstrates the comma-separated URL format consumed by the scorer (GitHub repo, placeholder, Hugging Face model).
- `autograder_docs/autograder_openapi_spec.yaml` describes the external autograder API, accompanied by `sample_input.txt` and `sample_output.txt` for reference payloads.

## Extending the System

1. **Add a metric**
   - Create `src/acmecli/metrics/<new_metric>.py` with a `score` method returning `MetricValue`.
   - Call `register(NewMetric())` at module scope.
   - Import the module inside `src/acmecli/metrics/__init__.py` so it auto-registers.
   - Update `acmecli/scoring.py` weights and `ReportRow` if the metric should affect NDJSON output.
   - Add a dedicated test in `tests/`.
2. **Support another source**
   - Implement a handler following the `SourceHandler` protocol in `types.py`.
   - Update `cli.classify` and `process_url` to invoke the handler and pass its metadata to metrics.
3. **Swap caching**
   - Replace `InMemoryCache` with a persistent cache by implementing the `Cache` protocol and wiring it into `process_url`.
4. **Integrate into other programs**
   - Import `acmecli.cli`, ensure `import acmecli.metrics` runs to populate `REGISTRY`, and call `process_url` directly with custom handlers.

## Operational Notes and Limitations

- Network access is required for live GitHub and Hugging Face scoring; consider injecting cached metadata when offline.
- Metric evaluations rely on README heuristics and public metadata; they do not clone repositories or inspect files.
- `REGISTRY` depends on metric modules being imported; custom consumers must import `acmecli.metrics` before invoking `process_url`.
- NDJSON output currently omits `hf_downloads`, `cli`, and `logging_env` scores; extend `ReportRow` if these should be surfaced downstream.
- The cache is in-memory and per-process; restart the CLI or run in parallel to clear state.
