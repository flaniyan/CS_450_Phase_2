# Quick Test Commands

## ✅ Setup (One-time)

You already have a virtual environment set up! Just activate it:

```bash
source venv/bin/activate
```

## Run Tests

### All unit tests:
```bash
source venv/bin/activate
pytest tests/unit -v
```

### With coverage:
```bash
source venv/bin/activate
pytest tests/unit --cov=acmecli --cov-report=term-missing
```

### Using the run script:
```bash
source venv/bin/activate
./run test
```

### Using Make:
```bash
source venv/bin/activate
make test
```

### Specific test file:
```bash
source venv/bin/activate
pytest tests/unit/test_jwt_middleware.py -v
```

## Quick Reference

**Activate venv:**
```bash
source venv/bin/activate
```

**Deactivate venv:**
```bash
deactivate
```

**Install dependencies (if needed):**
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

**Run a single test:**
```bash
source venv/bin/activate
pytest tests/unit/test_jwt_middleware.py::test_exempt_paths -v
```

---

**Note:** Always activate the virtual environment first with `source venv/bin/activate` before running any Python commands!

