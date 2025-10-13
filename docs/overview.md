# Overview

This project provides a unified Python service that:
- Scores repositories from GitHub and Hugging Face using modular metrics (`src/acmecli/*`).
- Exposes an HTTP API using FastAPI (`src/index.py`, `src/routes/*`).
- Serves a minimal frontend via Jinja templates on the same server and port (`frontend/*`).

## Architecture

- `src/acmecli/`: domain logic for scoring, metrics, and reporting.
- `src/index.py`: FastAPI app; mounts API routes and serves frontend templates/static.
- `src/routes/`: API routers (`/api/hello`, `/api/packages`, and scoring route).
- `src/services/rating.py`: integrates with `run.py` to execute the scoring pipeline.
- `frontend/`: Jinja templates and static assets.
- `tests/`: pytest-based unit tests for metrics and helpers.

## Runtime

- Single process on port 3000 using Uvicorn.
- Frontend routes: `/`, `/directory`, `/rate`, `/upload`, `/admin`.
- API routes under `/api/*`.
