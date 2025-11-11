### Goal
- Persist ingested model metadata so the autograder can read artifacts by the IDs it receives.

### Minimal Plan
- [ ] In `src/index.py` update `POST /artifact/model/{id}` (the main ingest path) to save a record in `_artifact_storage` using the generated `artifact_id`, mirroring what we already do for dataset/code.
- [ ] Make sure every read endpoint (`GET /artifact/{artifact_type}/{id}`, `/artifact/byName/{name}`, regex search, cost/audit/rate/lineage) checks `_artifact_storage` first so the new records are returned before falling back to S3 lookups.
- [ ] (Optional but low effort) add a helper to serialize `_artifact_storage` to disk on shutdown and reload on startup if we ever need persistence between runs.

