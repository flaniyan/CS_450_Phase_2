"""Test reproducibility metric."""

from acmecli.metrics.reproducibility_metric import ReproducibilityMetric


def test_no_readme_returns_zero():
    """Test with no readme text."""
    m = ReproducibilityMetric()
    assert m.score({}) == 0.0


def test_basic_demo_returns_score():
    """Test basic demo functionality."""
    m = ReproducibilityMetric()
    meta = {
        "readme_text": "Here's how to run the demo...",
        "repo_files": {"demo.py", "examples/"}
    }
    result = m.score(meta)
    assert isinstance(result, (int, float))
    assert 0.0 <= result <= 1.0


def test_no_demo_returns_zero():
    """Test without demo section."""
    m = ReproducibilityMetric()
    meta = {
        "readme_text": "This is just documentation",  # No demo keywords
        "repo_files": set()
    }
    result = m.score(meta)
    assert result == 0.0
