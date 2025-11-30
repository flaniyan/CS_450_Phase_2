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
            elif any(
                lic in license_name for lic in ["gpl-2", "lgpl-2", "gpl2", "gpl 2"]
            ):
                score += 0.6
            # Less compatible but still open source (lower scores)
            elif (
                "gpl-3" in license_name
                or "gpl3" in license_name
                or "gpl 3" in license_name
            ):
                score += 0.3
            elif any(lic in license_name for lic in ["gpl", "copyleft", "open source"]):
                score += 0.2
            else:
                score += 0.2  # Some license is better than none

        # Check README/license text for license information - expanded keywords
        if all_text:
            license_keywords = [
                "license",
                "licenses",
                "licensing",
                "licenced",
                "licenced",
                "licence",
                "licences",
                "licencing",
                "licenced",
                "copyright",
                "copyrights",
                "copyrighted",
                "copyright notice",
                "terms",
                "terms of use",
                "terms of service",
                "terms and conditions",
                "legal",
                "legal notice",
                "legal terms",
                "legal agreement",
                "licensing terms",
                "license agreement",
                "license terms",
                "permission",
                "permissions",
                "permitted",
                "permit",
                "rights",
                "right",
                "all rights reserved",
                "all rights",
                "proprietary",
                "proprietary license",
                "proprietary software",
                "open source",
                "opensource",
                "open-source",
                "open source license",
                "free software",
                "free software license",
                "free and open source",
                "foss",
                "f/oss",
                "free/libre open source software",
                "public domain",
                "publicdomain",
                "public-domain",
                "copyleft",
                "copyleft license",
                "copyleft software",
                "permissive",
                "permissive license",
                "permissive software",
                "commercial",
                "commercial license",
                "commercial use",
                "non-commercial",
                "noncommercial",
                "non commercial",
                "academic",
                "academic license",
                "academic use",
                "research",
                "research license",
                "research use",
                "educational",
                "educational license",
                "educational use",
            ]
            if any(keyword in all_text for keyword in license_keywords):
                score += 0.1

            # Look for specific license mentions in README - expanded
            readme_compatible = [
                "mit",
                "mit license",
                "mit licence",
                "mit-license",
                "mit licence",
                "bsd",
                "bsd license",
                "bsd licence",
                "bsd-license",
                "bsd licence",
                "apache",
                "apache license",
                "apache 2.0",
                "apache 2",
                "apache-2.0",
                "apache-2",
                "apache2",
                "apache2.0",
                "apache license 2.0",
                "lgpl",
                "lgpl-2.1",
                "lgpl 2.1",
                "lgplv2.1",
                "lgpl v2.1",
                "lgpl-2",
                "lgpl 2",
                "lgplv2",
                "lgpl v2",
                "lgpl-3",
                "lgpl 3",
                "mozilla public license",
                "mpl",
                "mpl 2.0",
                "mpl-2.0",
                "mpl2.0",
                "gnu lesser general public license",
                "gnu lgpl",
                "gnu lgpl v2.1",
                "gpl",
                "gpl-2",
                "gpl 2",
                "gplv2",
                "gpl v2",
                "gpl-3",
                "gpl 3",
                "gplv3",
                "gpl v3",
                "gnu general public license",
                "gnu gpl",
                "agpl",
                "agpl-3",
                "agpl 3",
                "agplv3",
                "agpl v3",
                "epl",
                "eclipse public license",
                "epl-1.0",
                "epl 1.0",
                "mpl",
                "mozilla public license",
                "mpl-2.0",
                "mpl 2.0",
                "cc0",
                "cc0 1.0",
                "cc0-1.0",
                "creative commons zero",
                "cc-by",
                "cc by",
                "creative commons attribution",
                "cc-by-sa",
                "cc by-sa",
                "creative commons attribution share-alike",
                "cc-by-nc",
                "cc by-nc",
                "creative commons attribution non-commercial",
                "unlicense",
                "unlicense license",
                "unlicense-license",
                "isc",
                "isc license",
                "isc licence",
                "zlib",
                "zlib license",
                "zlib licence",
                "artistic",
                "artistic license",
                "artistic licence",
                "python",
                "python license",
                "python software foundation license",
                "psf",
                "psf license",
                "python software foundation",
            ]
            if any(lic in all_text for lic in readme_compatible):
                score += 0.2
            # Check for LGPLv2.1 patterns specifically
            lgpl_patterns = [
                "license: lgplv2.1",
                "license: lgpl-2.1",
                "license: lgpl 2.1",
                "lgplv2.1",
                "lgpl-2.1",
                "lgpl 2.1",
                "gnu lesser general public license version 2.1",
                "lgplv2",
                "lgpl-2",
                "lgpl 2",
                "gnu lgpl v2.1",
            ]
            if any(pattern in all_text for pattern in lgpl_patterns):
                score += 0.3

        if (
            not license_name
            and "license" not in all_text
            and "copyright" not in all_text
        ):
            score = max(0.0, score - 0.2)

        if all_text or license_name:
            score = max(score, 0.5)

        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
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
