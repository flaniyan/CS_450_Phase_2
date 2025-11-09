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
            # Look for testing mentions - expanded
            testing_keywords = [
                "test",
                "tests",
                "testing",
                "tested",
                "test suite",
                "test cases",
                "pytest",
                "unittest",
                "nose",
                "nose2",
                "doctest",
                "doctests",
                "coverage",
                "code coverage",
                "test coverage",
                "coverage.py",
                "ci",
                "cd",
                "continuous integration",
                "continuous deployment",
                "github actions",
                "gitlab ci",
                "jenkins",
                "travis",
                "circleci",
                "unit test",
                "unit tests",
                "integration test",
                "integration tests",
                "test framework",
                "test runner",
                "test automation",
                "qa",
                "quality assurance",
            ]
            if any(keyword in readme_text for keyword in testing_keywords):
                score += 0.3

            # Look for documentation practices - expanded
            doc_keywords = [
                "documentation",
                "docs",
                "doc",
                "documented",
                "documents",
                "api",
                "api docs",
                "api documentation",
                "api reference",
                "docstring",
                "docstrings",
                "sphinx",
                "mkdocs",
                "doxygen",
                "readme",
                "read me",
                "readme.md",
                "readme file",
                "wiki",
                "wikis",
                "documentation site",
                "docs site",
                "guide",
                "guides",
                "tutorial",
                "tutorials",
                "manual",
                "manuals",
            ]
            if any(keyword in readme_text for keyword in doc_keywords):
                score += 0.2

            # Look for code style and linting - expanded
            style_keywords = [
                "lint", "linter", "linting", "linter config", "linter configs",
                "flake8", "pylint", "pylance", "pycodestyle", "pyflakes",
                "black", "black formatter", "code formatter", "formatting",
                "isort", "yapf", "autopep8", "autopep", "code formatter",
                "pre-commit", "pre commit", "precommit", "git hooks", "git hook",
                "style guide", "code style", "coding style", "code standards",
                "pep 8", "pep8", "pep 257", "pep257", "pep 484", "pep484",
                "mypy", "type checking", "type checker", "type hints", "type hinting",
                "ruff", "ruff linter", "ruff formatter", "ruff config",
                "eslint", "jshint", "jslint", "prettier", "prettier formatter",
                "gofmt", "gofmt formatter", "go fmt", "go format",
                "clang-format", "clang format", "clangformatter",
                "rustfmt", "rust fmt", "rust format", "rust formatter",
                "code formatting", "auto format", "auto formatting", "autoformatter",
                "code style guide", "style guide", "coding standards", "code standards",
                "code quality", "code quality tools", "code quality check",
                "static analysis", "static analyzer", "static code analysis",
                "sonarqube", "sonar", "sonarcloud", "code quality analysis",
                "code review", "code reviews", "code reviewing", "peer review",
                "pull request", "pull requests", "pr review", "pr reviews",
                "merge request", "merge requests", "mr review", "mr reviews",
            ]
            if any(keyword in readme_text for keyword in style_keywords):
                score += 0.2

            # Look for dependency management - expanded
            dep_keywords = [
                "requirements.txt",
                "requirements",
                "requirements-dev.txt",
                "setup.py",
                "setup.cfg",
                "setuptools",
                "distutils",
                "pyproject.toml",
                "pyproject.toml",
                "poetry.toml",
                "pipfile",
                "pipfile.lock",
                "pipenv",
                "poetry",
                "conda",
                "conda.yml",
                "environment.yml",
                "environment.yaml",
                "environment",
                "environments",
                "virtualenv",
                "venv",
                "package manager",
                "dependency management",
                "dependencies",
                "install dependencies",
                "package dependencies",
            ]
            if any(keyword in readme_text for keyword in dep_keywords):
                score += 0.1

            # Look for version control best practices - expanded
            vc_keywords = [
                "tag",
                "tags",
                "git tag",
                "version tag",
                "release tag",
                "release",
                "releases",
                "github release",
                "git release",
                "version",
                "versions",
                "versioning",
                "version number",
                "changelog",
                "change log",
                "changelogs",
                "release notes",
                "semantic versioning",
                "semver",
                "version control",
                "git",
                "gitflow",
                "git workflow",
                "branch",
                "branches",
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

        open_issues = meta.get("open_issues_count", 0)
        stars = meta.get("stars", 0)
        if stars > 0:
            issue_ratio = open_issues / max(stars, 1)
            if issue_ratio < 0.1:
                score += 0.1
            elif issue_ratio < 0.2:
                score += 0.05

        if readme_text or language or meta.get("pushed_at"):
            score = max(score, 0.5)
        
        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(CodeQualityMetric())
