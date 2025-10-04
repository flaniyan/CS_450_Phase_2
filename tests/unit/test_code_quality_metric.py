from acmecli.metrics.code_quality_metric import CodeQualityMetric

def test_code_quality_range():
    metric = CodeQualityMetric()
    mv = metric.score({"readme_text": "testing with pytest", "language": "python", "pushed_at": "2025-09-01T00:00:00Z"})
    assert 0.0 <= mv.value <= 1.0

def test_code_quality_missing():
    metric = CodeQualityMetric()
    mv = metric.score({})
    assert mv.value == 0.0
    assert mv.latency_ms >= 0

def test_code_quality_comprehensive():
    metric = CodeQualityMetric()
    mv = metric.score({
        "readme_text": "testing pytest coverage lint flake8 requirements.txt release version",
        "language": "python",
        "pushed_at": "2025-09-01T00:00:00Z",
        "open_issues_count": 2,
        "stars": 100
    })
    # Should have high score due to many quality indicators
    assert mv.value > 0.5