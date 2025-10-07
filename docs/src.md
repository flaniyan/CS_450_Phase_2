# Source (API & Services)

## App

- `src/index.py` creates the FastAPI app, mounts API routers under `/api`, and serves Jinja templates and static assets.
- Health: `GET /health`

## Routers

- `src/routes/index.py`
  - `GET /api/hello` -> `{ "message": "hello world" }`
  - mounts `/api/packages`
  - mounts scoring endpoints
- `src/routes/packages.py`
  - `GET /api/packages` -> `{ packages: [] }` (placeholder)

## Scoring

- `src/services/rating.py` exposes `POST /api/registry/models/{modelId}/rate`.
- It shells out to `run.py score <urls_file>` and aliases result keys to a stable shape.

## Error Handling

- `src/middleware/errorHandler.py` provides a JSON error response helper if needed in custom handlers.
