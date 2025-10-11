from acmecli.metrics.dataset_and_code_metric import DatasetAndCodeMetric

def test_dataset_and_code_range():
    metric = DatasetAndCodeMetric()
    mv = metric.score({"readme_text": "data and code available"})
    assert 0.0 <= mv.value <= 1.0

def test_dataset_and_code_missing():
    metric = DatasetAndCodeMetric()
    mv = metric.score({})
    assert mv.value == 0.0
    assert mv.latency_ms >= 0
