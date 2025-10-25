import time

from ..types import MetricValue
from .base import register


class DatasetAndCodeMetric:
    """Metric to assess availability of training dataset and code documentation."""

    name = "dataset_and_code_score"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for dataset and code availability
        score = 0.0

        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            # Look for dataset-related information
            dataset_keywords = [
                "dataset",
                "data",
                "training data",
                "corpus",
                "benchmark",
            ]
            if any(keyword in readme_text for keyword in dataset_keywords):
                score += 0.3

            # Look for specific well-known datasets
            known_datasets = [
                "imagenet",
                "coco",
                "openimages",
                "wikipedia",
                "common crawl",
                "glue",
                "squad",
                "wmt",
                "pile",
                "c4",
                "openwebtext",
            ]
            if any(dataset in readme_text for dataset in known_datasets):
                score += 0.2

            # Look for code availability indicators
            code_keywords = [
                "code",
                "implementation",
                "source",
                "repository",
                "github",
                "script",
            ]
            if any(keyword in readme_text for keyword in code_keywords):
                score += 0.2

            # Look for example usage or demo code
            example_keywords = [
                "example",
                "demo",
                "tutorial",
                "usage",
                "quickstart",
                "getting started",
            ]
            if any(keyword in readme_text for keyword in example_keywords):
                score += 0.2

            # Look for links to external resources
            if "http" in readme_text or "www" in readme_text:
                score += 0.1

        # Check if repository has multiple programming languages (indicates comprehensive codebase)
        language = meta.get("language", "")
        if language:
            score += 0.1

        # Check repository size - larger repos often have more comprehensive code/data
        size_kb = meta.get("size", 0)
        if size_kb > 10000:  # > 10MB suggests substantial content
            score += 0.1

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(DatasetAndCodeMetric())
