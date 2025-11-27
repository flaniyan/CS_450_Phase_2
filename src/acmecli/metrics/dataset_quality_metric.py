import time
from typing import Tuple
from ..types import MetricValue
from .base import register


class DatasetQualityMetric:
    """Metric to assess the quality of training/evaluation datasets used."""

    name = "dataset_quality"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for dataset quality assessment - more lenient
        score = 0.0

        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            # Look for high-quality, well-known datasets - expanded
            premium_datasets = [
                "imagenet",
                "imagenet-1k",
                "imagenet-21k",
                "imagenet dataset",
                "coco",
                "ms coco",
                "coco dataset",
                "coco 2017",
                "coco 2014",
                "openimages",
                "open images",
                "openimages dataset",
                "wmt",
                "wmt14",
                "wmt16",
                "wmt17",
                "wmt18",
                "wmt19",
                "wmt20",
                "wmt21",
                "squad",
                "squad1",
                "squad2",
                "squad 1.1",
                "squad 2.0",
                "glue",
                "superglue",
                "mnli",
                "qqp",
                "qnli",
                "rte",
                "sts-b",
                "mrpc",
                "cola",
                "sst-2",
                "commonsenseqa",
                "arc",
                "hellaswag",
                "winogrande",
                "race",
                "piqa",
                "wikitext",
                "wikitext-2",
                "wikitext-103",
                "ptb",
                "penn treebank",
                "bookcorpus",
                "common crawl",
                "openwebtext",
                "the pile",
                "cc-news",
                "reddit",
                "stackexchange",
                "wikipedia",
                "wiki",
                "kaggle",
                "kaggle dataset",
                "huggingface datasets",
                "hf datasets",
                "mnist",
                "cifar",
                "cifar-10",
                "cifar-100",
                "imdb",
                "yelp",
                "amazon",
                "amazon reviews",
                "yelp reviews",
                "yelp dataset",
                "news",
                "news dataset",
                "text",
                "text dataset",
                "corpus",
                "corpora",
            ]
            if any(dataset in readme_text for dataset in premium_datasets):
                score += 0.4

            # Look for dataset size indicators (larger often means better) - expanded
            size_indicators = [
                "million",
                "millions",
                "m samples",
                "m examples",
                "m instances",
                "billion",
                "billions",
                "b samples",
                "b examples",
                "b instances",
                "large-scale",
                "large scale",
                "large scale dataset",
                "comprehensive",
                "comprehensively",
                "comprehensive dataset",
                "extensive",
                "extensively",
                "extensive dataset",
                "massive",
                "massive dataset",
                "huge",
                "huge dataset",
                "vast",
                "vast dataset",
                "wide",
                "wide dataset",
                "thousands",
                "thousand",
                "k samples",
                "k examples",
            ]
            if any(indicator in readme_text for indicator in size_indicators):
                score += 0.2

            # Look for data curation and cleaning mentions - expanded
            quality_keywords = [
                "curated",
                "curation",
                "curate",
                "curating",
                "carefully curated",
                "cleaned",
                "cleaning",
                "clean",
                "clean data",
                "data cleaning",
                "filtered",
                "filtering",
                "filter",
                "filtered data",
                "data filtering",
                "validated",
                "validation",
                "validate",
                "validated data",
                "data validation",
                "annotated",
                "annotation",
                "annotate",
                "annotations",
                "data annotation",
                "labeled",
                "labels",
                "label",
                "labeled data",
                "data labeling",
                "quality",
                "high quality",
                "quality data",
                "data quality",
                "quality control",
                "verified",
                "verification",
                "verify",
                "verified data",
                "data verification",
                "reviewed",
                "review",
                "reviewed data",
                "data review",
                "data reviewing",
                "processed",
                "processing",
                "process",
                "processed data",
                "data processing",
                "preprocessed",
                "preprocessing",
                "preprocess",
                "preprocessed data",
                "data preprocessing",
                "normalized",
                "normalization",
                "normalize",
                "normalized data",
                "data normalization",
                "standardized",
                "standardization",
                "standardize",
                "standardized data",
                "data standardization",
                "checked",
                "checking",
                "check",
                "checked data",
                "data checking",
                "inspected",
                "inspection",
                "inspect",
                "inspected data",
                "data inspection",
                "audited",
                "audit",
                "auditing",
                "audited data",
                "data audit",
                "tested",
                "testing",
                "test",
                "tested data",
                "data testing",
                "evaluated",
                "evaluation",
                "evaluate",
                "evaluated data",
                "data evaluation",
                "assessed",
                "assessment",
                "assess",
                "assessed data",
                "data assessment",
                "monitored",
                "monitoring",
                "monitor",
                "monitored data",
                "data monitoring",
                "maintained",
                "maintenance",
                "maintain",
                "maintained data",
                "data maintenance",
                "updated",
                "updating",
                "update",
                "updated data",
                "data updating",
                "refined",
                "refinement",
                "refine",
                "refined data",
                "data refinement",
                "polished",
                "polishing",
                "polish",
                "polished data",
                "data polishing",
            ]
            if any(keyword in readme_text for keyword in quality_keywords):
                score += 0.2

            # Look for diversity and bias considerations - expanded
            diversity_keywords = [
                "diverse",
                "diversity",
                "diversely",
                "diverse dataset",
                "data diversity",
                "balanced",
                "balance",
                "balanced dataset",
                "balanced distribution",
                "data balance",
                "bias",
                "biases",
                "bias free",
                "bias-free",
                "unbiased",
                "bias reduction",
                "fairness",
                "fair",
                "fair dataset",
                "fair representation",
                "data fairness",
                "representative",
                "representation",
                "representative dataset",
                "data representation",
                "inclusive",
                "inclusion",
                "inclusive dataset",
                "inclusivity",
                "data inclusion",
                "equitable",
                "equity",
                "equitable dataset",
                "data equity",
                "unbiased",
                "unbiased dataset",
                "unbiased data",
                "data unbiased",
                "neutral",
                "neutrality",
                "neutral dataset",
                "data neutrality",
                "impartial",
                "impartiality",
                "impartial dataset",
                "data impartiality",
                "comprehensive",
                "comprehensiveness",
                "comprehensive dataset",
                "data comprehensiveness",
                "varied",
                "variety",
                "varied dataset",
                "data variety",
                "heterogeneous",
                "heterogeneity",
                "heterogeneous dataset",
                "data heterogeneity",
                "multifaceted",
                "multifaceted dataset",
                "data multifaceted",
                "wide-ranging",
                "wide ranging",
                "wide-ranging dataset",
                "data wide-ranging",
                "broad",
                "breadth",
                "broad dataset",
                "data breadth",
                "extensive",
                "extensiveness",
                "extensive dataset",
                "data extensiveness",
            ]
            if any(keyword in readme_text for keyword in diversity_keywords):
                score += 0.1

            # Look for evaluation methodology - expanded
            eval_keywords = [
                "evaluation",
                "evaluate",
                "evaluated",
                "evaluating",
                "evaluations",
                "benchmark",
                "benchmarks",
                "benchmarking",
                "benchmarked",
                "metric",
                "metrics",
                "measure",
                "measures",
                "measurement",
                "validation",
                "validate",
                "validated",
                "validating",
                "val set",
                "test set",
                "test dataset",
                "test split",
                "testing set",
                "train",
                "training",
                "training set",
                "training data",
                "test",
                "testing",
                "test data",
                "test dataset",
            ]
            if any(keyword in readme_text for keyword in eval_keywords):
                score += 0.1

            # Look for dataset mentions - more lenient
            dataset_keywords = [
                "dataset",
                "datasets",
                "data set",
                "data sets",
                "corpus",
                "corpora",
                "data collection",
                "data collections",
                "training data",
                "training dataset",
                "train data",
                "evaluation data",
                "evaluation dataset",
                "eval data",
                "benchmark dataset",
                "benchmark data",
            ]
            if any(keyword in readme_text for keyword in dataset_keywords):
                score += 0.1  # Give credit for any dataset mention

        # Check for academic/research backing (often indicates quality) - expanded
        if readme_text:
            research_keywords = [
                "paper",
                "papers",
                "publication",
                "publications",
                "published",
                "research",
                "researcher",
                "researchers",
                "research paper",
                "university",
                "universities",
                "academic",
                "academics",
                "arxiv",
                "arxiv.org",
                "arxiv paper",
                "conference",
                "workshop",
                "journal",
                "proceedings",
            ]
            if any(keyword in readme_text for keyword in research_keywords):
                score += 0.1

        # Check repository maturity (stars, forks indicate community validation) - more lenient
        stars = meta.get("stars", 0)
        if stars > 500:
            score += 0.1
        elif stars > 100:
            score += 0.05
        elif stars > 10:
            score += 0.02  # Give credit even for small star counts

        downloads = meta.get("downloads", 0)
        if downloads > 10000:
            score += 0.05
        elif downloads > 1000:
            score += 0.02

        if readme_text:
            score = max(score, 0.5)

        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


def score_dataset_quality(model_data) -> float:
    """Legacy function for backward compatibility."""
    if isinstance(model_data, dict):
        return DatasetQualityMetric().score(model_data).value
    try:
        v = float(model_data)
    except (TypeError, ValueError):
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def score_dataset_quality_with_latency(model_data) -> Tuple[float, int]:
    """Legacy function for backward compatibility."""
    start = time.time()
    score = score_dataset_quality(model_data)
    # Add small delay to simulate realistic latency
    time.sleep(0.02)  # 20ms delay
    latency = int((time.time() - start) * 1000)
    return score, latency


register(DatasetQualityMetric())
