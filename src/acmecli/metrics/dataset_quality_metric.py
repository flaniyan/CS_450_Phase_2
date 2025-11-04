import time
from ..types import MetricValue
from .base import register


class DatasetQualityMetric:
    """Metric to assess the quality of training/evaluation datasets used."""

    name = "dataset_quality"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for dataset quality assessment
        score = 0.0

        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            # Look for high-quality, well-known datasets
            premium_datasets = [
                "imagenet",
                "coco",
                "openimages",
                "wmt",
                "squad",
                "glue",
                "superglue",
            ]
            if any(dataset in readme_text for dataset in premium_datasets):
                score += 0.4

            # Look for dataset size indicators (larger often means better)
            size_indicators = [
                "million",
                "billion",
                "large-scale",
                "comprehensive",
                "extensive",
            ]
            if any(indicator in readme_text for indicator in size_indicators):
                score += 0.2

            # Look for data curation and cleaning mentions
            quality_keywords = [
                "curated",
                "cleaned",
                "filtered",
                "validated",
                "annotated",
                "labeled",
            ]
            if any(keyword in readme_text for keyword in quality_keywords):
                score += 0.2

            # Look for diversity and bias considerations
            diversity_keywords = [
                "diverse",
                "balanced",
                "bias",
                "fairness",
                "representative",
            ]
            if any(keyword in readme_text for keyword in diversity_keywords):
                score += 0.1

            # Look for evaluation methodology
            eval_keywords = [
                "evaluation",
                "benchmark",
                "metric",
                "validation",
                "test set",
            ]
            if any(keyword in readme_text for keyword in eval_keywords):
                score += 0.1

        # Check for academic/research backing (often indicates quality)
        if readme_text and any(
            keyword in readme_text
            for keyword in ["paper", "research", "university", "arxiv"]
        ):
            score += 0.1

        # Check repository maturity (stars, forks indicate community validation)
        stars = meta.get("stars", 0)
        if stars > 500:
            score += 0.1
        elif stars > 100:
            score += 0.05

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(DatasetQualityMetric())
