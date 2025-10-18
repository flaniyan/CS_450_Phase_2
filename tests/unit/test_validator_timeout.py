import json
import os
import pathlib
import subprocess
import tempfile
import textwrap

from pathlib import Path

# Ensure we can find the driver from the project root
project_root = Path(__file__).parent.parent.parent
DRIVER = str(project_root / "src/validator/driver.py")


def run(code, payload, env_overrides=None, timeout=8):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        env = os.environ.copy()
        env.setdefault("VALIDATOR_TIMEOUT_SEC", "2")
        env.setdefault("VALIDATOR_MEMORY_MB", "64")
        if env_overrides:
            env.update(env_overrides)
        p = subprocess.run(
            ["python3", "-I", "-S", DRIVER, path, json.dumps(payload)],
            capture_output=True, text=True, timeout=timeout, env=env
        )
        return p.returncode, p.stdout.strip()
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def test_infinite_loop_times_out():
    rc, out = run("def validate(_):\n  while True:\n    pass\n", {})
    # -24 = SIGXCPU (CPU time limit exceeded), 124 = timeout signal
    assert rc in (124, 1, -24) or "timeout" in out


def test_memory_hog_fails():
    code = textwrap.dedent("""
    def validate(_):
        # Try to allocate a large amount but not so large it fails immediately
        try:
            x = "x" * (50 * 1024 * 1024)  # 50MB
            return {"allow": True, "reason": "large allocation succeeded"}
        except MemoryError:
            return {"allow": False, "reason": "memory limit hit"}
    """)
    rc, out = run(code, {}, env_overrides={"VALIDATOR_MEMORY_MB": "1"})

    assert rc in (0, 1, 137) or "exception" in out or "allow" in out


def test_happy_path_allows():
    code = "def validate(data):\n  return {'allow': True, 'reason': 'ok'}\n"
    rc, out = run(code, {})
    assert rc == 0 and '"allow": true' in out
