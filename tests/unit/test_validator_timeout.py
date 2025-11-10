import importlib
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

validator_service = importlib.import_module("src.services.validator_service")
execute_validator = validator_service.execute_validator

if os.getenv("SKIP_PROCESSPOOL_TESTS") == "1":
    pytest.skip("Skipped under coverage run", allow_module_level=True)


@pytest.fixture(autouse=True)
def stub_cloudwatch(monkeypatch):
    class CloudWatchStub:
        def __init__(self):
            self.calls = []

        def put_metric_data(self, **kwargs):
            self.calls.append(kwargs)

    stub = CloudWatchStub()
    monkeypatch.setattr("src.services.validator_service.cloudwatch", stub)
    return stub


def test_execute_validator_success(monkeypatch, stub_cloudwatch):
    """Checker path: validator returns result and no metrics emitted."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = """
def validate(package):
    return {"status": "ok"}
"""
    result = execute_validator(script, {"foo": "bar"})
    assert result["valid"] is True
    assert result["result"]["status"] == "ok"
    assert stub_cloudwatch.calls == []


def test_execute_validator_timeout(monkeypatch, stub_cloudwatch):
    """Validator loops forever; ensure timeout triggers metric and failure."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "1")
    script = """
def validate(package):
    while True:
        pass
"""
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert "timed out" in result["error"]
    assert len(stub_cloudwatch.calls) == 1
    metric = stub_cloudwatch.calls[0]
    assert metric["Namespace"]
    assert metric["MetricData"][0]["MetricName"]


def test_execute_validator_missing_validate(monkeypatch, stub_cloudwatch):
    """Script lacks validate(); service should reject with clear message."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = """
def not_validate(package):
    return {"status": "ok"}
"""
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert "validate() function" in result["error"]
    assert stub_cloudwatch.calls == []


def test_execute_validator_syntax_error(monkeypatch, stub_cloudwatch):
    """Broken Python should surface syntax error without metrics."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = "def validate(:\n    pass"
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert "invalid syntax" in result["error"]
    assert stub_cloudwatch.calls == []


def test_execute_validator_exception(monkeypatch, stub_cloudwatch):
    """Validator raises runtime error; service must propagate message."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = """
def validate(package):
    raise RuntimeError("boom")
"""
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert "boom" in result["error"]
    assert stub_cloudwatch.calls == []


def test_execute_validator_no_result(monkeypatch, stub_cloudwatch):
    """validate() returning None should count as invalid and give error."""
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = """
def validate(package):
    return None
"""
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert result["error"] == "Validator returned no result"
    assert stub_cloudwatch.calls == []
