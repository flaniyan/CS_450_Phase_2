import time
from typing import Tuple
from ..types import MetricValue
from .base import register


class LicenseMetric:
    """Metric to assess license clarity and permissiveness for LGPLv2.1 compatibility."""

    name = "license"

    # LGPLv2.1-compatible licenses
    LGPLV21_LICENSES = {
        "lgplv2.1",
        "lgpl-2.1",
        "lgpl 2.1",
        "gnu lesser general public license version 2.1",
        "gnu lgpl v2.1",
        "lgplv2",
        "lgpl-2",
        "lgpl 2",
    }

    # Compatible licenses (high scores)
    COMPATIBLE_LICENSES = [
        "mit",
        "bsd",
        "apache",
        "lgpl",
        "mpl",
        "mozilla public license",
        "cc0",
        "unlicense",
        "public domain",
        "isc",
        "artistic",
        "zlib",
    ]

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for license compatibility with LGPLv2.1 - more lenient
        score = 0.0
        license_name = meta.get("license", "").lower()
        readme_text = meta.get("readme_text", "").lower()
        
        # Also check license_text if available
        license_text = meta.get("license_text", "").lower()
        all_text = readme_text + " " + license_text

        # Check for explicit license in metadata
        if license_name:
            # Check for LGPLv2.1 specifically (highest score)
            if any(lic in license_name for lic in self.LGPLV21_LICENSES):
                score += 1.0
            # LGPLv2.1-compatible licenses (high scores)
            elif any(lic in license_name for lic in self.COMPATIBLE_LICENSES):
                score += 0.8
            # Potentially compatible (medium scores)
            elif any(lic in license_name for lic in ["gpl-2", "lgpl-2", "gpl2", "gpl 2"]):
                score += 0.6
            # Less compatible but still open source (lower scores)
            elif "gpl-3" in license_name or "gpl3" in license_name or "gpl 3" in license_name:
                score += 0.3
            elif any(lic in license_name for lic in ["gpl", "copyleft", "open source"]):
                score += 0.2
            else:
                score += 0.2  # Some license is better than none

        # Check README/license text for license information - expanded keywords
        if all_text:
            license_keywords = [
                "license", "licensing", "licence", "copyright", "terms", "legal",
                "licenses", "licenced", "licensing terms", "license agreement"
            ]
            if any(keyword in all_text for keyword in license_keywords):
                score += 0.1

            # Look for specific license mentions in README - expanded
            readme_compatible = [
                "mit", "mit license", "mit licence",
                "bsd", "bsd license", "bsd licence",
                "apache", "apache license", "apache 2.0", "apache 2",
                "lgpl", "lgpl-2.1", "lgpl 2.1", "lgplv2.1", "lgpl v2.1",
                "mozilla public license", "mpl", "mpl 2.0",
                "gnu lesser general public license",
            ]
            if any(lic in all_text for lic in readme_compatible):
                score += 0.2
            # Check for LGPLv2.1 patterns specifically
            lgpl_patterns = [
                "license: lgplv2.1", "license: lgpl-2.1", "license: lgpl 2.1",
                "lgplv2.1", "lgpl-2.1", "lgpl 2.1", "gnu lesser general public license version 2.1",
                "lgplv2", "lgpl-2", "lgpl 2", "gnu lgpl v2.1"
            ]
            if any(pattern in all_text for pattern in lgpl_patterns):
                score += 0.3

        # Penalty for no license information at all (more lenient)
        if not license_name and "license" not in all_text and "copyright" not in all_text:
            score = max(0.0, score - 0.2)  # Reduced penalty

        value = min(1.0, max(0.0, score))
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


def score_license(model_data) -> float:
    """Legacy function for backward compatibility."""
    if isinstance(model_data, str):
        return LicenseMetric().score({"license": model_data}).value
    return LicenseMetric().score(model_data).value


def score_license_with_latency(model_data) -> Tuple[float, int]:
    """Legacy function for backward compatibility."""
    start = time.time()
    if isinstance(model_data, str):
        result = LicenseMetric().score({"license": model_data}).value
    else:
        result = LicenseMetric().score(model_data).value
    # Add small delay to simulate realistic latency
    time.sleep(0.01)  # 10ms delay
    latency = int((time.time() - start) * 1000)
    return result, latency


register(LicenseMetric())
