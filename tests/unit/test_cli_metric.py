from acmecli.metrics.cli_metric import CLIMetric

def test_cli_metric_documentation():
    metric = CLIMetric()
    mv = metric.score({"readme_text": "Supports install, test, score via CLI"})
    assert 0.0 <= mv.value <= 1.0

def test_cli_metric_no_cli():
    metric = CLIMetric()
    mv = metric.score({"readme_text": "This project is for data analysis"})
    assert mv.value < 0.5
    assert mv.latency_ms >= 0