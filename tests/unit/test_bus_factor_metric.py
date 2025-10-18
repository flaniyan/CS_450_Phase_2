from acmecli.metrics.bus_factor_metric import BusFactorMetric


def test_bus_factor_many_contributors_even():
    metric = BusFactorMetric()
    # Test exactly 10 contributors to hit the >= 10 branch
    contributors = {f"user{i}": 5 for i in range(10)}
    mv = metric.score({"contributors": contributors})
    assert mv.value > 0.5


def test_bus_factor_one_contributor():
    metric = BusFactorMetric()
    mv = metric.score({"contributors": {"alice": 50}})
    assert mv.value < 0.5


def test_bus_factor_empty_input():
    metric = BusFactorMetric()
    mv = metric.score({})
    assert mv.value == 0.0
    assert mv.latency_ms >= 0


def test_bus_factor_three_contributors():
    metric = BusFactorMetric()
    # Test exactly 3 contributors to hit the >= 3 branch
    mv = metric.score({"contributors": {"a": 10, "b": 10, "c": 10}})
    assert mv.value > 0.1
