from acmecli.scoring import compute_netscore, compute_net_score
from acmecli.types import MetricValue


def test_compute_netscore_typical():
    scores = [0.9, 0.8, 0.7]
    weights = [0.5, 0.3, 0.2]
    net = compute_netscore(scores, weights)
    assert 0.0 <= net <= 1.0


def test_compute_netscore_zero():
    scores = [0, 0, 0]
    weights = [0.5, 0.3, 0.2]
    net = compute_netscore(scores, weights)
    assert net == 0.0


def test_compute_net_score():
    results = {
        'license': MetricValue(name='license', value=0.8, latency_ms=10),
        'ramp_up_time': MetricValue(name='ramp_up_time', value=0.7, latency_ms=20),
        'bus_factor': MetricValue(name='bus_factor', value=0.6, latency_ms=15)
    }
    net_score, latency = compute_net_score(results)
    assert 0.0 <= net_score <= 1.0
    assert latency >= 0


def test_compute_net_score_with_all_metrics():
    """Test compute_net_score with all metrics including size_score dict."""
    results = {
        'license': MetricValue(name='license', value=0.8, latency_ms=10),
        'ramp_up_time': MetricValue(name='ramp_up_time', value=0.7, latency_ms=20),
        'bus_factor': MetricValue(name='bus_factor', value=0.6, latency_ms=15),
        'size_score': MetricValue(name='size_score', value={'desktop_pc': 0.5, 'raspberry_pi': 0.3}, latency_ms=25),
        'reproducibility': MetricValue(name='reproducibility', value=0.9, latency_ms=30),
        'reviewedness': MetricValue(name='reviewedness', value=0.8, latency_ms=35),
        'treescore': MetricValue(name='treescore', value=0.7, latency_ms=40)
    }
    net_score, latency = compute_net_score(results)
    assert 0.0 <= net_score <= 1.0
    assert latency >= 0
