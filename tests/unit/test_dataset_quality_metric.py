from acmecli.metrics.dataset_quality_metric import DatasetQualityMetric


def test_dataset_quality_range():
    metric = DatasetQualityMetric()
    mv = metric.score({"readme_text": "imagenet large-scale curated"})
    assert 0.0 <= mv.value <= 1.0
    assert mv.latency_ms >= 0
