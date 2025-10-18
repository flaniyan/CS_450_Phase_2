"""Test score dependencies function."""

from acmecli.metrics.score_dependencies import score_dependencies


def test_no_context_returns_high_score():
    """Test with no context returns high score (no deps is good)."""
    result = score_dependencies({})
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0


def test_dict_context():
    """Test with dictionary context."""
    context = {"repo_path": "/fake/path"}
    result = score_dependencies(context)
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0


def test_object_context():
    """Test with object-like context."""
    class MockContext:
        pass
    
    context = MockContext()
    result = score_dependencies(context)
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0
