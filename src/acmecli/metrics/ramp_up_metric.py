import time
from ..types import MetricValue
from .base import register


class RampUpMetric:
    """Metric to assess ease of ramp-up based on documentation and examples."""

    name = "ramp_up_time"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for ramp-up time (higher = easier to ramp up)
        score = 0.0

        # Check for README content
        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            score += 0.3
            # Look for common documentation sections
            if any(
                keyword in readme_text
                for keyword in [
                    "install",
                    "usage",
                    "example",
                    "quickstart",
                    "getting started",
                ]
            ):
                score += 0.2
            if any(
                keyword in readme_text for keyword in ["api", "documentation", "docs"]
            ):
                score += 0.1

        # Check for presence of wiki
        if meta.get("has_wiki", False):
            score += 0.1

        # Check for active maintenance (recent updates)
        if meta.get("pushed_at"):
            from datetime import datetime, timezone

            try:
                pushed_date = datetime.fromisoformat(
                    meta["pushed_at"].replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                days_since_push = (now - pushed_date).days
                if days_since_push < 30:
                    score += 0.2
                elif days_since_push < 90:
                    score += 0.1
            except:
                pass

        # Check for stars (indication of community adoption)
        stars = meta.get("stars", 0)
        if stars > 100:
            score += 0.1

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(RampUpMetric())
