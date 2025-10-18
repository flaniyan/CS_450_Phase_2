import json
import sys
import os
import signal
import resource
import importlib.machinery
import importlib.util

# Environment variable parsing with validation
try:
    TIMEOUT_SEC = max(1, min(int(os.getenv("VALIDATOR_TIMEOUT_SEC", "5")), 300))
except (ValueError, TypeError):
    TIMEOUT_SEC = 5

try:
    MEM_LIMIT_MB = max(16, min(int(os.getenv("VALIDATOR_MEMORY_MB", "128")), 2048))
except (ValueError, TypeError):
    MEM_LIMIT_MB = 128

try:
    NOFILE_SOFT = max(32, int(os.getenv("VALIDATOR_NOFILE_SOFT", "64")))
except (ValueError, TypeError):
    NOFILE_SOFT = 64

try:
    NPROC_SOFT = max(8, int(os.getenv("VALIDATOR_NPROC_SOFT", "64")))
except (ValueError, TypeError):
    NPROC_SOFT = 64


def _timeout_handler(signum, frame):
    """Signal handler for timeout - raises TimeoutError with proper signal info."""
    raise TimeoutError(f"Validator timeout after {TIMEOUT_SEC} seconds")


def set_limits():
    """Set resource limits and timeouts for validator execution."""
    errors = []

    # Set CPU time limit
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SEC, TIMEOUT_SEC))
    except (ValueError, OSError) as e:
        errors.append(f"Failed to set CPU limit: {e}")

    # Set memory limit
    try:
        memory_limit_bytes = MEM_LIMIT_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    except (ValueError, OSError) as e:
        errors.append(f"Failed to set memory limit: {e}")

    # Set file descriptor limit
    try:
        current_soft, current_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if NOFILE_SOFT <= current_hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (NOFILE_SOFT, current_hard))
    except (ValueError, OSError) as e:
        errors.append(f"Failed to set file descriptor limit: {e}")

    # Set process limit
    try:
        current_soft, current_hard = resource.getrlimit(resource.RLIMIT_NPROC)
        if NPROC_SOFT <= current_hard:
            resource.setrlimit(resource.RLIMIT_NPROC, (NPROC_SOFT, current_hard))
    except (ValueError, OSError) as e:
        errors.append(f"Failed to set process limit: {e}")

    # Disable core dumps
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        pass  # Core dumps are not critical

    # Set wall-clock timeout
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TIMEOUT_SEC)
    except (ValueError, OSError) as e:
        errors.append(f"Failed to set alarm signal: {e}")

    # Log any errors but don't fail - this is best effort
    if errors:
        error_msg = '; '.join(errors)
        sys.stderr.write(f"Warning: Resource limit warnings: {error_msg}\n")


def main():
    """Main validator execution function."""
    if len(sys.argv) != 3:
        error_msg = "Expected 2 arguments: validator_path payload_json"
        print(json.dumps({"ok": False, "error": "bad_args", "detail": error_msg}))
        sys.exit(2)

    validator_path, payload_json = sys.argv[1], sys.argv[2]

    # Validate file exists
    if not os.path.isfile(validator_path):
        error_msg = f"Validator file not found: {validator_path}"
        print(json.dumps({"ok": False, "error": "file_not_found", "detail": error_msg}))
        sys.exit(2)

    # Parse payload with error handling
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": "invalid_json", "detail": str(e)}))
        sys.exit(2)

    # Set resource limits
    set_limits()

    # Load and validate the validator module
    try:
        spec = importlib.util.spec_from_file_location("validator_mod", validator_path)
        if spec is None or spec.loader is None:
            error_msg = "Could not create module spec"
            result = {"ok": False, "error": "load_failed", "detail": error_msg}
            print(json.dumps(result))
            sys.exit(1)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "load_failed", "detail": str(e)}))
        sys.exit(1)

    # Check for validate function
    if not hasattr(mod, "validate"):
        error_msg = "Module must define a validate function"
        result = {"ok": False, "error": "missing_validate", "detail": error_msg}
        print(json.dumps(result))
        sys.exit(1)

    if not callable(getattr(mod, "validate")):
        error_msg = "validate must be callable"
        result = {"ok": False, "error": "invalid_validate", "detail": error_msg}
        print(json.dumps(result))
        sys.exit(1)

    # Execute validator with error handling
    try:
        result = mod.validate(payload)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "validation_failed", "detail": str(e)}))
        sys.exit(1)

    # Validate result format
    if not isinstance(result, dict):
        error_msg = "validate function must return a dict"
        print(json.dumps({"ok": False, "error": "bad_return", "detail": error_msg}))
        sys.exit(1)

    allow = bool(result.get("allow"))
    reason = str(result.get("reason", ""))

    # Return result
    print(json.dumps({"allow": allow, "reason": reason}))
    sys.exit(0 if allow else 3)


if __name__ == "__main__":
    try:
        main()
    except TimeoutError as e:
        print(json.dumps({"ok": False, "error": "timeout", "detail": str(e)}))
        sys.exit(124)
    except MemoryError as e:
        print(json.dumps({"ok": False, "error": "oom", "detail": str(e)}))
        sys.exit(137)
    except KeyboardInterrupt:
        error_msg = "Process interrupted"
        print(json.dumps({"ok": False, "error": "interrupted", "detail": error_msg}))
        sys.exit(130)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "exception", "detail": str(e)}))
        sys.exit(1)
