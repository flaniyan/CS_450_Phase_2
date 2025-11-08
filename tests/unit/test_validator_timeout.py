import os

import pytest

if os.getenv("SKIP_PROCESSPOOL_TESTS") == "1":
    pytest.skip("Skipped under coverage run", allow_module_level=True)

from src.services.validator_service import execute_validator


def test_execute_validator_success(monkeypatch):
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "2")
    script = """
def validate(package):
    return {"status": "ok"}
"""
    result = execute_validator(script, {"foo": "bar"})
    assert result["valid"] is True
    assert result["result"]["status"] == "ok"


def test_execute_validator_timeout(monkeypatch):
    monkeypatch.setenv("VALIDATOR_TIMEOUT_SEC", "1")
    script = """
def validate(package):
    while True:
        pass
"""
    result = execute_validator(script, {})
    assert result["valid"] is False
    assert "timed out" in result["error"]

