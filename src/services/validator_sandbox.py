import json, sys, time
import time as time_module

def _limits(heap_mb: int, cpu_s: int):
    try:
        import resource
        b = heap_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        pass

def _safe_exec(script: str, payload: dict) -> dict:
    safe_builtins = {
        "len": len, "range": range, "min": min, "max": max, "sum": sum, "abs": abs,
        "float": float, "int": int, "str": str, "bool": bool, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter, "all": all, "any": any,
        "time": time_module,
    }
    g = {"__builtins__": safe_builtins, "__name__": "__validator__"}
    l = {"INPUT": payload, "RESULT": None}
    exec(script, g, l)  # contract: script must set RESULT = {...}
    if not isinstance(l.get("RESULT"), dict):
        raise ValueError("validator did not set RESULT dict")
    return l["RESULT"]

def main():
    req = json.loads(sys.stdin.read())
    _limits(int(req.get("heap_mb", 128)), int(req.get("cpu_s", 3)))
    t0 = time.perf_counter()
    out = _safe_exec(req["script"], req["payload"])
    out["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
