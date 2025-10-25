from acmecli.metrics.license_metric import LicenseMetric


def test_license_metric_high_score():
    metric = LicenseMetric()
    mv = metric.score({"license": "MIT", "readme_text": "MIT license"})
    assert 0.8 <= mv.value <= 1.0


def test_license_metric_no_license():
    metric = LicenseMetric()
    mv = metric.score({"license": "", "readme_text": ""})
    assert mv.value == 0.0 or mv.value < 0.2
    assert mv.latency_ms >= 0


def test_license_metric_readme_license_only():
    metric = LicenseMetric()
    mv = metric.score(
        {"license": "", "readme_text": "licensed under the Apache license"}
    )
    assert mv.value > 0.0


def test_license_metric_gpl3():
    metric = LicenseMetric()
    mv = metric.score({"license": "GPL-3.0"})
    assert 0.3 <= mv.value < 0.6
