import time
from ..types import MetricValue
from .base import register


class CLIMetric:
    """Metric to assess CLI usability and script-based automation."""

    name = "cli"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        score = 0.0
        readme_text = meta.get("readme_text", "").lower()
        if "cli" in readme_text or "command line" in readme_text:
            score += 0.5
        if any(cmd in readme_text for cmd in ["install", "test", "score"]):
            score += 0.2
        if "automation" in readme_text or "script" in readme_text:
            score += 0.3

        if readme_text:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(CLIMetric())
