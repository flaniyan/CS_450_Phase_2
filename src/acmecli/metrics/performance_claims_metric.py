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
        
        readme_text = meta.get('readme_text', '').lower()
        if readme_text:
            # Look for benchmark-related keywords
            benchmark_keywords = ['benchmark', 'evaluation', 'eval', 'performance', 'accuracy', 'f1', 'bleu', 'rouge']
            if any(keyword in readme_text for keyword in benchmark_keywords):
                score += 0.3
            
            # Look for specific metrics or numbers indicating performance
            if re.search(r'\d+\.?\d*%', readme_text) or re.search(r'score.*\d+', readme_text):
                score += 0.2
            
            # Look for comparison with other models
            comparison_keywords = ['compared to', 'vs', 'versus', 'outperform', 'better than', 'state-of-the-art', 'sota']
            if any(keyword in readme_text for keyword in comparison_keywords):
                score += 0.2
            
            # Look for evaluation datasets
            eval_datasets = ['glue', 'superglue', 'squad', 'coco', 'imagenet', 'wmt', 'bleu', 'rouge']
            if any(dataset in readme_text for dataset in eval_datasets):
                score += 0.2
            
            # Look for published papers or citations
            paper_keywords = ['paper', 'arxiv', 'citation', 'published', 'acl', 'nips', 'icml', 'iclr', 'emnlp']
            if any(keyword in readme_text for keyword in paper_keywords):
                score += 0.1
        
        # Check if repo has releases (indicates mature development)
        if meta.get('has_pages', False):  # Often used for documentation/results
            score += 0.1
        
        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(PerformanceClaimsMetric())