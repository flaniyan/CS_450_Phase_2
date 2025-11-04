import time
from typing import Tuple

"""
Pull Requests metric (0..1):

Heuristic (offline-friendly):
- Favors repos with *some* PR activity but penalizes excessive backlog of open PRs.
- Uses context fields many Phase-1 toolchains already collect (e.g., context.github):
  - open_prs, merged_prs, total_prs (fallbacks if missing).
If none present, return a neutral 0.5.

Scoring idea:
- activity = min(1.0, merged_prs / 50)   # normalize “healthy contribution” up to ~50 merges
- backlog  = 1.0 - min(1.0, open_prs / 50)
- score = 0.6 * activity + 0.4 * backlog
"""


def _extract_github(context):
    # Try object attribute then dict
    gh = getattr(context, "github", None)
    if gh is None and isinstance(context, dict):
        gh = context.get("github")
    return gh or {}


def score_pull_requests(context) -> float:
    gh = _extract_github(context)

    open_prs = gh.get("open_prs")
    merged_prs = gh.get("merged_prs")
    total_prs = gh.get("total_prs")

    if open_prs is None and merged_prs is None and total_prs is None:
        # No data → neutral
        return 0.5

    try:
        open_prs = int(open_prs or 0)
        merged_prs = int(merged_prs or 0)
        total_prs = int(total_prs or (open_prs + merged_prs))
    except Exception:
        return 0.5

    activity = min(1.0, merged_prs / 50.0)
    backlog = 1.0 - min(1.0, open_prs / 50.0)
    score = 0.6 * activity + 0.4 * backlog
    # Clamp
    return max(0.0, min(1.0, score))


def score_pull_requests_with_latency(context) -> Tuple[float, float]:
    t0 = time.perf_counter()
    s = score_pull_requests(context)
    latency = time.perf_counter() - t0
    return s, latency
