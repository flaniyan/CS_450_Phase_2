"""Test treescore metric."""

from acmecli.metrics.treescore_metric import TreescoreMetric


def test_no_parents_returns_zero():
    """Test with no parents."""
    m = TreescoreMetric()
    assert m.score({}) == 0.0


def test_basic_parents_returns_score():
    """Test with basic parent data."""
    m = TreescoreMetric()
    meta = {
        "parents": [
            {"score": "0.8"},
            {"score": "0.6"}
        ]
    }
    result = m.score(meta)
    assert isinstance(result, (int, float))


def test_lineage_parents_format():
    """Test lineage parents format."""
    m = TreescoreMetric()
    meta = {
        "lineage": {
            "parents": [
                {"score": "0.5"}
            ]
        }
    }
    result = m.score(meta)
    assert isinstance(result, (int, float))
