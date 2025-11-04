import time
import json
import os
from typing import Tuple

"""
Dependencies metric (0..1):

Heuristic:
- If a manifest exists (package.json or requirements.txt), we score inversely to the number of declared deps.
- 0 deps → 1.0,   20+ deps → ~0.0,   smooth clamp in between.

Safe & offline: only reads local files already cloned by fetch step.
"""

MAX_DEP_COUNT = 20  # after this many, score tends toward 0


def _count_deps(repo_path: str) -> int:
    # package.json (JS)
    pkg = os.path.join(repo_path, "package.json")
    if os.path.exists(pkg):
        try:
            data = json.load(open(pkg, "r", encoding="utf-8"))
            deps = 0
            for key in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            ):
                d = data.get(key) or {}
                if isinstance(d, dict):
                    deps += len(d)
            return deps
        except Exception:
            pass

    # requirements.txt (Python)
    req = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(req):
        try:
            lines = [
                ln.strip()
                for ln in open(req, "r", encoding="utf-8").read().splitlines()
            ]
            # Ignore comments and empty lines
            pkgs = [ln for ln in lines if ln and not ln.startswith("#")]
            return len(pkgs)
        except Exception:
            pass

    # Pipfile / pyproject.toml could be added similarly if needed.
    return 0


def score_dependencies(context) -> float:
    """
    context: object with repo_path or similar attribute (aligns with your existing metrics).
    We try context.repo_path first, then context.get('repo_path').
    """
    repo_path = getattr(context, "repo_path", None) or getattr(
        context, "local_path", None
    )
    if repo_path is None and isinstance(context, dict):
        repo_path = context.get("repo_path") or context.get("local_path")

    if not repo_path or not os.path.exists(repo_path):
        # No repo on disk? Be conservative but not fatal.
        return 0.5

    deps = _count_deps(repo_path)
    # Map to 0..1: more deps → lower score; clamp at [0,1]
    raw = max(0.0, 1.0 - (deps / float(MAX_DEP_COUNT)))
    return min(1.0, raw)


def score_dependencies_with_latency(context) -> Tuple[float, float]:
    t0 = time.perf_counter()
    score = score_dependencies(context)
    latency = time.perf_counter() - t0
    return score, latency
