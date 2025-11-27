import time
from typing import Dict
from ..types import MetricValue
from .base import register


class SizeMetric:
    """Metric to assess model size compatibility with different hardware platforms."""

    name = "size_score"

    # check for CD
    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Get repository size in KB
        repo_size_kb = meta.get("size", 0)

        # Heuristic size thresholds for different hardware (in KB)
        # Based on typical model sizes and hardware constraints
        thresholds = {
            "raspberry_pi": 100_000,  # ~100MB - very constrained
            "jetson_nano": 1_000_000,  # ~1GB - moderate constraints
            "desktop_pc": 10_000_000,  # ~10GB - good resources
            "aws_server": 50_000_000,  # ~50GB - high resources
        }

        scores = {}
        for platform, threshold in thresholds.items():
            if repo_size_kb == 0:
                scores[platform] = 0.5
            elif repo_size_kb <= threshold * 0.1:
                scores[platform] = 1.0
            elif repo_size_kb <= threshold * 0.5:
                scores[platform] = 0.8
            elif repo_size_kb <= threshold:
                scores[platform] = 0.6
            elif repo_size_kb <= threshold * 2:
                scores[platform] = max(0.5, 0.3)
            else:
                scores[platform] = max(0.5, 0.1)

        # Check README for size-related information
        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            # Look for explicit size mentions
            if any(
                keyword in readme_text
                for keyword in ["lightweight", "small", "compact", "efficient"]
            ):
                # Boost all scores slightly for models claiming to be lightweight
                for platform in scores:
                    scores[platform] = min(1.0, scores[platform] + 0.1)
            elif any(
                keyword in readme_text
                for keyword in ["large", "heavy", "resource-intensive"]
            ):
                # Reduce scores for models explicitly stating they are large
                for platform in scores:
                    scores[platform] = max(0.0, scores[platform] - 0.1)

        # Round all scores to 2 decimal places
        scores = {
            platform: round(float(score), 2) for platform, score in scores.items()
        }

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, scores, latency_ms)


register(SizeMetric())
