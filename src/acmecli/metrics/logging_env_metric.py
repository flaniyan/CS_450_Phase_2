import time
from ..types import MetricValue
from .base import register


class LoggingEnvMetric:
    """Metric to assess logging configuration via environment variables."""

    name = "logging_env"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        score = 0.0
        env_vars = meta.get("env_vars", {})
        readme_text = meta.get("readme_text", "").lower()
        if "log_file" in env_vars or "log_level" in env_vars:
            score += 0.5
        if "debug" in readme_text or "logging" in readme_text:
            score += 0.3

        if readme_text or env_vars:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(LoggingEnvMetric())
