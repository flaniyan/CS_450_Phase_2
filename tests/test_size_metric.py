from acmecli.metrics.size_metric import SizeMetric

def test_size_metric_range():
    metric = SizeMetric()
    mv = metric.score({"size": 1000})
    assert all(0.0 <= v <= 1.0 for v in mv.value.values())

def test_size_metric_zero():
    metric = SizeMetric()
    mv = metric.score({"size": 0})
    assert all(v == 0.5 for v in mv.value.values())
    assert isinstance(mv.latency_ms, int)
    assert mv.latency_ms >= 0

def test_size_metric_with_readme():
    metric = SizeMetric()
    mv = metric.score({"size": 1000, "readme_text": "lightweight small efficient"})
    # Should have bonus from readme keywords
    assert all(v > 0.5 for v in mv.value.values())

def test_size_metric_large_readme():
    metric = SizeMetric()
    mv = metric.score({"size": 10000, "readme_text": "large heavy resource-intensive model"})
    # Should have penalty from readme keywords
    base_score = SizeMetric().score({"size": 10000})
    assert all(mv.value[k] < base_score.value[k] for k in mv.value.keys())