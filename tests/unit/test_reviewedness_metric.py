import math

from acmecli.metrics.reviewedness_metric import ReviewednessMetric


def test_no_github_url_returns_minus1():
    m = ReviewednessMetric()
    assert m.score({}) == -1.0


def test_no_activity_returns_minus1():
    m = ReviewednessMetric()
    meta = {"github_url": "https://github.com/u/r", "github": {}}
    assert m.score(meta) == -1.0


def test_only_non_code_files_returns_one():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "prs": [
                {
                    "merged": True,
                    "approved": True,
                    "files": [
                        {"filename": "weights/model.safetensors", "additions": 100}
                    ],
                }
            ]
        },
    }
    assert m.score(meta) == 1.0


def test_reviewed_and_unreviewed_ratio():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "prs": [
                {
                    "merged": True,
                    "approved": True,
                    "files": [{"filename": "src/a.py", "additions": 100}],
                },
                {
                    "merged": True,
                    "approved": False,
                    "files": [{"filename": "src/b.py", "additions": 50}],
                },
            ]
        },
    }
    score = m.score(meta)
    assert math.isclose(score, 100 / 150, rel_tol=1e-6)


def test_direct_commits_unreviewed():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "direct_commits": [{"files": [{"filename": "src/c.py", "additions": 30}]}]
        },
    }
    assert m.score(meta) == 0.0
