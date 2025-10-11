from acmecli.metrics.ramp_up_metric import RampUpMetric

def test_rampup_metric_range():
    metric = RampUpMetric()
    mv = metric.score({"readme_text": "Install and usage quickstart", "pushed_at": "2025-09-01T00:00:00Z"})
    assert 0.0 <= mv.value <= 1.0

def test_rampup_metric_missing():
    metric = RampUpMetric()
    mv = metric.score({})
    assert mv.value == 0.0
    assert mv.latency_ms >= 0