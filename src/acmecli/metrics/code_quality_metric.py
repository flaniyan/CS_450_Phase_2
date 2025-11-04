import time
from ..types import MetricValue
from .base import register


class CodeQualityMetric:
    """Metric to assess code style, maintainability, and engineering practices."""

    name = "code_quality"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for code quality assessment
        score = 0.0

        readme_text = meta.get("readme_text")
        if readme_text is not None:
            readme_text = str(readme_text).lower()
        else:
            readme_text = ""

        if readme_text:
            # Look for testing mentions
            testing_keywords = [
                "test",
                "testing",
                "pytest",
                "unittest",
                "coverage",
                "ci",
                "continuous integration",
            ]
            if any(keyword in readme_text for keyword in testing_keywords):
                score += 0.3

            # Look for documentation practices
            doc_keywords = [
                "documentation",
                "docs",
                "api",
                "docstring",
                "readme",
                "wiki",
            ]
            if any(keyword in readme_text for keyword in doc_keywords):
                score += 0.2

            # Look for code style and linting
            style_keywords = [
                "lint",
                "flake8",
                "pylint",
                "black",
                "isort",
                "pre-commit",
                "style guide",
            ]
            if any(keyword in readme_text for keyword in style_keywords):
                score += 0.2

            # Look for dependency management
            dep_keywords = [
                "requirements.txt",
                "setup.py",
                "pyproject.toml",
                "pipfile",
                "conda",
                "environment",
            ]
            if any(keyword in readme_text for keyword in dep_keywords):
                score += 0.1

            # Look for version control best practices
            vc_keywords = [
                "tag",
                "release",
                "version",
                "changelog",
                "semantic versioning",
            ]
            if any(keyword in readme_text for keyword in vc_keywords):
                score += 0.1

        # Check for popular programming language (better tooling/community)
        language = meta.get("language")
        if language is not None:
            language = str(language).lower()
        else:
            language = ""

        popular_languages = [
            "python",
            "javascript",
            "java",
            "c++",
            "typescript",
            "go",
            "rust",
        ]
        if language in popular_languages:
            score += 0.1

        # Check for recent activity (maintained code is generally better)
        if meta.get("pushed_at"):
            from datetime import datetime, timezone

            try:
                pushed_date = datetime.fromisoformat(
                    meta["pushed_at"].replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                days_since_push = (now - pushed_date).days
                if days_since_push < 30:
                    score += 0.2
                elif days_since_push < 90:
                    score += 0.1
            except:
                pass

        # Check open issues ratio (fewer issues relative to activity often indicates quality)
        open_issues = meta.get("open_issues_count", 0)
        stars = meta.get("stars", 0)
        if stars > 0:
            issue_ratio = open_issues / max(stars, 1)
            if issue_ratio < 0.1:
                score += 0.1
            elif issue_ratio < 0.2:
                score += 0.05

        value = min(1.0, score)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(CodeQualityMetric())
