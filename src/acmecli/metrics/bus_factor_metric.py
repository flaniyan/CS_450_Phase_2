import time
from ..types import MetricValue
from .base import register


class BusFactorMetric:
    """Metric to assess bus factor - higher score means less risk from key person dependency."""

    name = "bus_factor"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for bus factor (higher = safer, more distributed)
        score = 0.0

        contributors = meta.get("contributors", {})
        if contributors:
            total_contributions = sum(contributors.values())
            contributor_count = len(contributors)

            if contributor_count >= 10:
                score += 0.4
            elif contributor_count >= 5:
                score += 0.3
            elif contributor_count >= 3:
                score += 0.2
            elif contributor_count >= 2:
                score += 0.1

            # Check contribution distribution
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
                    score += 0.1

        # Organization/company backing (GitHub org vs individual)
        full_name = meta.get("full_name", "")
        if "/" in full_name:
            owner = full_name.split("/")[0]
            # Heuristic: longer names often indicate organizations
            if len(owner) > 3 and not owner.islower():
                score += 0.1

        # Forks indicate community involvement
        forks = meta.get("forks", 0)
        if forks > 50:
            score += 0.2
        elif forks > 10:
            score += 0.1

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(BusFactorMetric())
