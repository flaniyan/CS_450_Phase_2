from acmecli.metrics.performance_claims_metric import PerformanceClaimsMetric

def test_performance_metric_range():
    metric = PerformanceClaimsMetric()
    mv = metric.score({"readme_text": "benchmark performance 99%"})
    assert 0.0 <= mv.value <= 1.0

def test_performance_metric_missing():
    metric = PerformanceClaimsMetric()
    mv = metric.score({})
    assert mv.value == 0.0
    assert mv.latency_ms >= 0