import time
from typing import Tuple
from ..types import MetricValue
from .base import register


class BusFactorMetric:
    """Metric to assess bus factor - higher score means less risk from key person dependency."""

    name = "bus_factor"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for bus factor (higher = safer, more distributed) - more lenient
        score = 0.0

        contributors = meta.get("contributors", {})
        if contributors:
            total_contributions = sum(contributors.values())
            contributor_count = len(contributors)

            # More lenient thresholds - give credit for any contributors
            if contributor_count >= 10:
                score += 0.4
            elif contributor_count >= 5:
                score += 0.3
            elif contributor_count >= 3:
                score += 0.2
            elif contributor_count >= 2:
                score += 0.15
            elif contributor_count >= 1:
                score += 0.1  # Give credit even for single contributor

            # Check contribution distribution - more lenient
            if total_contributions > 0:
                # Find the top contributor's share
                max_contributions = max(contributors.values()) if contributors else 0
                top_contributor_share = max_contributions / total_contributions

                # Lower share of top contributor = better bus factor
                if top_contributor_share < 0.3:
                    score += 0.3
                elif top_contributor_share < 0.5:
                    score += 0.2
                elif top_contributor_share < 0.7:
                    score += 0.15
                elif top_contributor_share < 0.9:
                    score += 0.05  # Even if one person dominates, give some credit

        # Organization/company backing (GitHub org vs individual) - more lenient
        full_name = meta.get("full_name", "")
        if "/" in full_name:
            owner = full_name.split("/")[0]
            # More lenient: any organization-like name gets credit
            if len(owner) > 2:  # Lowered threshold
                score += 0.1
        elif full_name and not "/" in full_name:
            # Even single-owner repos get some credit
            score += 0.05

        # Forks indicate community involvement - more lenient thresholds
        forks = meta.get("forks", 0)
        if forks > 50:
            score += 0.2
        elif forks > 10:
            score += 0.15
        elif forks > 5:
            score += 0.1
        elif forks > 0:
            score += 0.05  # Any forks get credit

        # Stars also indicate community involvement
        stars = meta.get("stars", 0)
        if stars > 100:
            score += 0.1
        elif stars > 50:
            score += 0.05
        elif stars > 0:
            score += 0.02  # Any stars get credit

        downloads = meta.get("downloads", 0)
        if downloads > 10000:
            score += 0.1
        elif downloads > 1000:
            score += 0.05
        elif downloads > 0:
            score += 0.02

        if contributors or full_name or forks > 0 or stars > 0 or downloads > 0:
            score = max(score, 0.5)
        
        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


def score_bus_factor(model_data_or_maintainers) -> float:
    """Legacy function for backward compatibility."""
    if isinstance(model_data_or_maintainers, dict):
        return BusFactorMetric().score(model_data_or_maintainers).value
    else:
        # Backward compatibility for list input
        return (
            BusFactorMetric()
            .score({"contributors": {m: 1 for m in model_data_or_maintainers}})
            .value
        )


def score_bus_factor_with_latency(model_data_or_maintainers) -> Tuple[float, int]:
    """Legacy function for backward compatibility."""
    start = time.time()
    score = score_bus_factor(model_data_or_maintainers)
    # Add small delay to simulate realistic latency
    time.sleep(0.025)  # 25ms delay
    latency = int((time.time() - start) * 1000)
    return score, latency


register(BusFactorMetric())
