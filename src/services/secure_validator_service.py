import os, json, asyncio, subprocess, sys, time, uuid, contextlib, logging
from asyncio import Semaphore
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

# envs
VALIDATOR_TIMEOUT_MS  = int(os.getenv("VALIDATOR_TIMEOUT_MS",  "4000"))
VALIDATOR_HEAP_MB     = int(os.getenv("VALIDATOR_HEAP_MB",     "128"))
VALIDATOR_MAX_WORKERS = int(os.getenv("VALIDATOR_MAX_WORKERS", "2"))
MAX_SCRIPT_SIZE       = int(os.getenv("VALIDATOR_MAX_SCRIPT_SIZE", "200000"))
MAX_FILE_COUNT        = int(os.getenv("VALIDATOR_MAX_FILE_COUNT",  "10"))
MAX_PAYLOAD_BYTES     = int(os.getenv("VALIDATOR_MAX_PAYLOAD_BYTES","2097152"))  # 2MB

_SEM = Semaphore(VALIDATOR_MAX_WORKERS)
logger = logging.getLogger(__name__)

# Pydantic models
class ValidationRequest(BaseModel):
    pkg_name: str
    version: str
    user_id: str
    user_groups: list[str]
    script: Optional[str] = None

class ValidationResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    validation_result: Optional[Dict[str, Any]] = None

app = FastAPI(title="Secure Package Validator Service", version="1.0.0")

async def execute_validator(script_content: str, package_data: dict) -> dict:
    # fast fail / size guards
    if not isinstance(script_content, str) or len(script_content) > MAX_SCRIPT_SIZE:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "script too large"}}
    if len(json.dumps(package_data)) > MAX_PAYLOAD_BYTES:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "payload too large"}}
    if isinstance(package_data.get("files"), list) and len(package_data["files"]) > MAX_FILE_COUNT:
        return {"ok": False, "error": {"code": "BAD_INPUT", "message": "too many files"}}

    req = {
        "script": script_content,
        "payload": package_data,
        "heap_mb": VALIDATOR_HEAP_MB,
        "cpu_s": max(1, VALIDATOR_TIMEOUT_MS // 1000 - 1)  # leave headroom
    }
    cmd = [sys.executable, "-u", "-m", "src.validator.secure_sandbox"]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, lambda: proc.communicate(input=json.dumps(req).encode("utf-8"))
            ),
            timeout=VALIDATOR_TIMEOUT_MS / 1000
        )
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return {"ok": False, "error": {"code": "TIMEOUT", "message": f"exceeded {VALIDATOR_TIMEOUT_MS}ms"}}

    if proc.returncode != 0:
        return {"ok": False, "error": {"code": "INTERNAL", "message": (err or b'').decode(errors='ignore')[:300]}}

    result = json.loads(out.decode("utf-8"))
    return {"ok": bool(result.get("ok", True)), **{k: v for k, v in result.items() if k != "ok"}}


@app.post("/validate", response_model=ValidationResponse)
async def validate_package(req: ValidationRequest):
    async with _SEM:
        t0 = time.perf_counter()
        job_id = str(uuid.uuid4())
        
        # Basic validation logic
        if not req.script:
            return ValidationResponse(allowed=True, reason="No validator script required")
        
        result = await execute_validator(req.script, req.model_dump(exclude={"script"}))
        result.setdefault("issues", [])
        result.setdefault("score", 0.0)
        result["duration_ms_total"] = int((time.perf_counter() - t0) * 1000)
        
        logger.info(f"job_id={job_id} ok={result.get('ok')} dur_ms={result['duration_ms_total']}")
        
        if not result.get("ok"):
            code = result.get("error", {}).get("code")
            raise HTTPException(
                status_code=408 if code == "TIMEOUT" else 422,
                detail=result.get("error", {}).get("message", "Validation failed")
            )
        
        return ValidationResponse(
            allowed=result.get("ok", False),
            reason="Validation passed" if result.get("ok") else "Validation failed",
            validation_result=result
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
