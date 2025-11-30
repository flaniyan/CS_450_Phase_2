import time
import re
from ..types import MetricValue
from .base import register


class PerformanceClaimsMetric:
    """Metric to assess evidence of performance claims through benchmarks and evaluations."""

    name = "performance_claims"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for performance claims evidence
        score = 0.0

        readme_text = meta.get("readme_text", "").lower()
        # Give baseline score if there's any documentation
        if readme_text:
            score += 0.1  # Baseline score for having documentation
            # Look for benchmark-related keywords - expanded
            benchmark_keywords = [
                "benchmark",
                "benchmarks",
                "benchmarking",
                "bench",
                "evaluation",
                "evaluations",
                "eval",
                "evaluate",
                "evaluated",
                "evaluating",
                "assessment",
                "assess",
                "performance",
                "performances",
                "performs",
                "performed",
                "performing",
                "accuracy",
                "accuracies",
                "accurate",
                "precise",
                "precision",
                "f1",
                "f1-score",
                "f1 score",
                "f-score",
                "f measure",
                "bleu",
                "bleu score",
                "rouge",
                "rouge score",
                "rouge-l",
                "rouge-n",
                "metric",
                "metrics",
                "measure",
                "measures",
                "measurement",
                "measurements",
                "score",
                "scores",
                "scoring",
                "scored",
                "result",
                "results",
                "test",
                "tests",
                "testing",
                "tested",
                "test set",
                "test dataset",
                "validation",
                "validate",
                "validated",
                "validating",
                "val set",
                "val dataset",
                "quality",
                "qualities",
                "capability",
                "capabilities",
                "ability",
                "abilities",
            ]
            if any(keyword in readme_text for keyword in benchmark_keywords):
                score += 0.3

            # Look for specific metrics or numbers indicating performance
            if (
                re.search(r"\d+\.?\d*%", readme_text)
                or re.search(r"score.*\d+", readme_text)
                or re.search(
                    r"\d+\.?\d*\s*(accuracy|f1|bleu|rouge|precision|recall)",
                    readme_text,
                )
            ):
                score += 0.2

            # Look for comparison with other models - expanded
            comparison_keywords = [
                "compared to",
                "compared with",
                "compared against",
                "comparison",
                "compare",
                "vs",
                "vs.",
                "versus",
                "v.s.",
                "vs ",
                "comparison to",
                "outperform",
                "outperforms",
                "outperformed",
                "outperforming",
                "outperformance",
                "better than",
                "better performance",
                "improved",
                "improvement",
                "improves",
                "state-of-the-art",
                "sota",
                "state of the art",
                "state-of-art",
                "superior",
                "superior to",
                "superior performance",
                "exceeds",
                "exceed",
                "beats",
                "beat",
                "beating",
                "surpasses",
                "surpass",
                "surpassing",
                "top",
                "leading",
                "best",
                "strongest",
                "highest",
                "competitive",
            ]
            if any(keyword in readme_text for keyword in comparison_keywords):
                score += 0.2

            # Look for evaluation datasets - expanded
            eval_datasets = [
                "glue",
                "superglue",
                "glue benchmark",
                "superglue benchmark",
                "squad",
                "squad1",
                "squad2",
                "squad 1.1",
                "squad 2.0",
                "squad dataset",
                "coco",
                "ms coco",
                "coco dataset",
                "coco 2017",
                "coco 2014",
                "imagenet",
                "imagenet-1k",
                "imagenet-21k",
                "wmt",
                "wmt14",
                "wmt16",
                "wmt17",
                "wmt18",
                "wmt19",
                "wmt20",
                "wmt21",
                "bleu",
                "rouge",
                "rouge-l",
                "rouge-n",
                "rouge-w",
                "rouge score",
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
                "github",
                "wikipedia",
            ]
            if any(dataset in readme_text for dataset in eval_datasets):
                score += 0.2

            # Look for published papers or citations - expanded
            paper_keywords = [
                "paper",
                "papers",
                "publication",
                "publications",
                "published",
                "publish",
                "arxiv",
                "arxiv.org",
                "arxiv:",
                "arxiv id",
                "arxiv paper",
                "citation",
                "citations",
                "cite",
                "cited",
                "citing",
                "cites",
                "acl",
                "nips",
                "neurips",
                "icml",
                "iclr",
                "emnlp",
                "naacl",
                "aaai",
                "ijcai",
                "eacl",
                "coling",
                "acl anthology",
                "conference",
                "conferences",
                "workshop",
                "workshops",
                "proceedings",
                "journal",
                "journals",
                "research",
                "researcher",
                "researchers",
            ]
            if any(keyword in readme_text for keyword in paper_keywords):
                score += 0.1

        if meta.get("has_pages", False):
            score += 0.1

        if readme_text:
            score = max(score, 0.5)

        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(PerformanceClaimsMetric())
