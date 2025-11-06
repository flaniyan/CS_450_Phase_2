# Testing Guide

This guide explains how to run tests for the CS 450 Phase 2 project.

## Quick Start

### Option 1: Using the `run` script (Recommended)
```bash
./run test
```

This script:
- Installs the package in development mode
- Runs pytest with coverage
- Shows test results and coverage percentage

### Option 2: Using Make
```bash
# Install dependencies first
make install

# Run tests
make test

# Run tests with coverage report
make cov
```

### Option 3: Direct pytest
```bash
# Install package first
pip install -e .

# Run all unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=acmecli --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_jwt_middleware.py -v

# Run specific test function
pytest tests/unit/test_jwt_middleware.py::test_exempt_paths -v
```

### Option 4: Python module
```bash
# Install package first
pip install -e .

# Run via Python
python -m pytest tests/unit -v

# With coverage
python -m coverage run --source=acmecli -m pytest tests/unit
python -m coverage report -m
```

---

## Test Structure

```
tests/
├── unit/           # Unit tests (fast, isolated)
│   ├── test_jwt_middleware.py
│   ├── test_bus_factor_metric.py
│   ├── test_code_quality_metric.py
│   └── ...
├── integration/    # Integration tests (slower, require AWS)
│   ├── test_aws_integration.py
│   ├── test_directory.py
│   └── ...
└── fixtures/       # Test fixtures/data
```

---

## Common Issues & Solutions

### Issue: `ModuleNotFoundError: No module named 'acmecli'`

**Solution:**
```bash
# Install package in development mode
pip install -e .

# Or use the run script which does this automatically
./run test
```

### Issue: `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or install the package
pip install -e .
```

### Issue: Tests pass but coverage is 0%

**Solution:**
```bash
# Make sure you're using the correct source path
pytest tests/unit --cov=acmecli --cov-report=term-missing

# Check pyproject.toml has correct source path:
# [tool.coverage.run]
# source = ["src/acmecli"]
```

---

## Running Specific Tests

### Run only unit tests:
```bash
pytest tests/unit -v
```

### Run only integration tests:
```bash
pytest tests/integration -v
```

### Run tests matching a pattern:
```bash
pytest tests/unit -k "jwt" -v
```

### Run tests with markers:
```bash
pytest -m unit -v
pytest -m integration -v
```

### Run a single test file:
```bash
pytest tests/unit/test_jwt_middleware.py -v
```

### Run a single test function:
```bash
pytest tests/unit/test_jwt_middleware.py::test_exempt_paths -v
```

---

## Coverage Reports

### Terminal output:
```bash
pytest tests/unit --cov=acmecli --cov-report=term-missing
```

### HTML report:
```bash
pytest tests/unit --cov=acmecli --cov-report=html
# Then open htmlcov/index.html in your browser
```

### Using the run script:
```bash
./run test
# Coverage percentage is shown at the end
```

---

## CI/CD Testing

The project uses GitHub Actions for CI. Tests run automatically on:
- Push to main/master
- Pull requests
- Manual workflow dispatch

Check `.github/workflows/ci.yml` for the exact test configuration.

---

## Integration Tests

Integration tests require AWS credentials and may take longer. They are typically disabled in CI.

To run integration tests:
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Run integration tests
pytest tests/integration -v
```

---

## Debugging Tests

### Verbose output:
```bash
pytest tests/unit -vv  # Very verbose
pytest tests/unit -s   # Show print statements
```

### Run with pdb debugger:
```bash
pytest tests/unit/test_jwt_middleware.py --pdb
```

### Show test names only:
```bash
pytest tests/unit --collect-only
```

---

## Example Test Run

```bash
$ ./run test
✅ Installation completed successfully!
[INFO] Installing package in development mode...
✅ Tests completed successfully!
42/42 test cases passed. 85% line coverage achieved.
```

---

## Troubleshooting

1. **No tests discovered:**
   - Check you're in the repo root directory
   - Verify `tests/unit/` contains test files
   - Ensure test files match pattern: `test_*.py` or `*_test.py`

2. **Import errors:**
   - Run `pip install -e .` to install the package
   - Check `PYTHONPATH` includes the repo root

3. **Coverage issues:**
   - Verify `pyproject.toml` has correct `source` path
   - Make sure you're using `--source=acmecli` (not `--source=src`)

---

For more information, see:
- `pytest.ini` - Pytest configuration
- `pyproject.toml` - Project and coverage configuration
- `tests/conftest.py` - Shared test fixtures

