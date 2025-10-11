from acmecli.metrics.logging_env_metric import LoggingEnvMetric

def test_logging_env_metric_env_vars():
    metric = LoggingEnvMetric()
    mv = metric.score({"env_vars": {"LOG_FILE": "log.txt", "LOG_LEVEL": "DEBUG"}})
    assert 0.0 <= mv.value <= 1.0
    assert mv.latency_ms >= 0