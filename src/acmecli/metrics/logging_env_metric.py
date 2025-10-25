import time

from ..types import MetricValue
from .base import register


class LoggingEnvMetric:
    """Metric to assess logging configuration via environment variables."""

    name = "logging_env"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        # Heuristic: score higher if LOG_FILE or LOG_LEVEL are mentioned/configured
        score = 0.0
        env_vars = meta.get("env_vars", {})
        readme_text = meta.get("readme_text", "").lower()
        if "log_file" in env_vars or "log_level" in env_vars:
            score += 0.5
        if "debug" in readme_text or "logging" in readme_text:
            score += 0.3
        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(LoggingEnvMetric())
