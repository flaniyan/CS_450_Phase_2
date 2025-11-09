import time
from ..types import MetricValue
from .base import register


class HFDownloadsMetric:
    name = "hf_downloads"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        downloads = meta.get("downloads", 0)
        if downloads > 0:
            value = min(1.0, max(0.5, downloads / 10000))
        else:
            value = 0.5
        value = round(float(value), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(HFDownloadsMetric())
