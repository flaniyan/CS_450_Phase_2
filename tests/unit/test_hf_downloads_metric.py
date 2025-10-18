from acmecli.metrics.hf_downloads_metric import HFDownloadsMetric


def test_downloads_high():
    metric = HFDownloadsMetric()
    mv = metric.score({"downloads": 20000})
    assert mv.value == 1.0
    assert mv.latency_ms >= 0
