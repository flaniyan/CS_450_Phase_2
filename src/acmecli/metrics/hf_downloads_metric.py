import time
from ..types import MetricValue
from .base import register


class HFDownloadsMetric:
    name = "hf_downloads"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        downloads = meta.get("downloads", 0)
        # Heuristic: normalize to [0,1] (e.g. >10000 is 1.0, <100 is 0.1)
        value = min(1.0, downloads / 10000) if downloads else 0.0
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(HFDownloadsMetric())