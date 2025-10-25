from acmecli.metrics.reproducibility_metric import ReproducibilityMetric

m = ReproducibilityMetric()


def test_full_score():
    meta = {
        "readme_text": "## Example\npip install pkg\npython demo.py",
        "repo_files": {"demo.py"},
    }
    assert m.score(meta) == 1.0


def test_half_score():
    meta = {"readme_text": "## Example\nRun the model after setup", "repo_files": set()}
    assert m.score(meta) == 0.5


def test_zero_score():
    meta = {"readme_text": "no demo here", "repo_files": set()}
    assert m.score(meta) == 0.0
