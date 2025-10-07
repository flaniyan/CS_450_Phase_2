# Tests

## Running the suite

```powershell
. .venv/Scripts/Activate.ps1
python run.py test
```

This runs pytest with coverage and prints a concise summary.

## Structure

- `tests/unit/*.py`: unit tests for metrics, scoring, reporter.
- `pytest.ini`: discovery root and coverage options.

## Tips

- Use `-k` to filter tests: `pytest -k bus_factor`.
- Use `-q` for quiet mode.
- View coverage details with `--cov-report=term-missing` (already enabled).
