import time

from ..types import MetricValue
from .base import register


class LicenseMetric:
    """Metric to assess license clarity and permissiveness for LGPLv2.1 compatibility."""

    name = "license"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for license compatibility with LGPLv2.1
        score = 0.0
        license_name = meta.get("license", "").lower()
        readme_text = meta.get("readme_text", "").lower()

        # Check for explicit license in metadata
        if license_name:
            # LGPLv2.1-compatible licenses (high scores)
            compatible_licenses = [
                "mit",
                "bsd",
                "apache",
                "lgpl",
                "mpl",
                "cc0",
                "unlicense",
                "public domain",
            ]
            if any(lic in license_name for lic in compatible_licenses):
                score += 0.8
            # Potentially compatible (medium scores)
            elif any(lic in license_name for lic in ["gpl-2", "lgpl-2"]):
                score += 0.6
            # Less compatible (lower scores)
            elif "gpl-3" in license_name:
                score += 0.3
            else:
                score += 0.2  # Some license is better than none

        # Check README for license information
        if readme_text:
            license_keywords = ["license", "licensing", "copyright", "terms", "legal"]
            if any(keyword in readme_text for keyword in license_keywords):
                score += 0.1

            # Look for specific license mentions in README
            readme_compatible = [
                "mit",
                "bsd",
                "apache",
                "lgpl",
                "mozilla public license",
            ]
            if any(lic in readme_text for lic in readme_compatible):
                score += 0.1

        # Penalty for no license information at all
        if not license_name and "license" not in readme_text:
            score = max(0.0, score - 0.3)

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(LicenseMetric())
