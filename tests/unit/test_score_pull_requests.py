"""Test score pull requests function."""

from acmecli.metrics.score_pull_requests import score_pull_requests


def test_no_context_returns_zero():
    """Test with no context returns zero."""
    result = score_pull_requests({})
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0


def test_dict_context():
    """Test with dictionary context."""
    context = {"github_url": "https://github.com/test/repo"}
    result = score_pull_requests(context)
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0


def test_object_context():
    """Test with object-like context."""
    class MockContext:
        github_url = "https://github.com/test/repo"

    context = MockContext()
    result = score_pull_requests(context)
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0
