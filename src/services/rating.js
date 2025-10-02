const { Router } = require("express");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const router = Router();

/* ----------------------------- helpers ----------------------------- */

const PY_TIMEOUT_MS = 20000; // kill Python if it hangs (>20s)

/** choose python executable per platform */
function pythonCmd() {
  return process.platform === "win32" ? "python" : "python3";
}

/** return the first defined value among aliases */
function alias(obj, ...keys) {
  for (const k of keys) {
    if (obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
}

/** write a temp urls file containing one target URL, return its absolute path */
function writeTempUrlsFile(target) {
  const file = `.tmp_urls_${Date.now()}_${Math.random().toString(36).slice(2)}.txt`;
  const full = path.join(process.cwd(), file);
  fs.writeFileSync(full, `${target}\n`, "utf8");
  return full;
}

/** robustly parse first non-empty line of NDJSON, throwing 502 on issues */
function parseFirstNdjsonLine(stdoutStr) {
  const line = stdoutStr
    .split("\n")
    .map((s) => s.trim())
    .find((s) => s.length > 0);

  if (!line) {
    const e = new Error("No scoring output received from Python tool.");
    e.status = 502;
    throw e;
  }
  try {
    return JSON.parse(line);
  } catch {
    const e = new Error("Invalid JSON from scorer.");
    e.status = 502;
    throw e;
  }
}

/**
 * Run the Phase-1 scorer: `python run.py score <urlsFile>`
 * Resolves with the parsed first NDJSON row.
 */
function runScorer(target) {
  return new Promise((resolve, reject) => {
    const urlsPath = writeTempUrlsFile(target);
    const child = spawn(pythonCmd(), ["run.py", "score", urlsPath], {
      cwd: process.cwd(),
    });

    let out = "";
    let errOut = "";

    const cleanup = () => {
      try {
        fs.unlinkSync(urlsPath);
      } catch {}
    };

    const timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {}
    }, PY_TIMEOUT_MS);

    child.stdout.on("data", (d) => (out += d.toString()));
    child.stderr.on("data", (d) => (errOut += d.toString()));

    child.on("close", (code) => {
      clearTimeout(timer);
      cleanup();
      if (code !== 0) {
        const e = new Error(
          `scoring failed (${code}). stderr: ${errOut.slice(0, 500)}`
        );
        e.status = 502;
        return reject(e);
      }
      try {
        const row = parseFirstNdjsonLine(out);
        resolve(row);
      } catch (e) {
        reject(e);
      }
    });

    child.on("error", (err) => {
      clearTimeout(timer);
      cleanup();
      err.status = 502;
      reject(err);
    });
  });
}

/* ------------------------------ route ------------------------------ */

/**
 * POST /api/registry/models/:modelId/rate
 * Body: { target: string }  // e.g., GitHub/HF URL to score
 * Query: ?enforce=true      // 422 if any subscore <= 0.5 (non-latency)
 *
 * Response 200:
 * { data: { modelId, target, netScore, subscores, latency } }
 *
 * Response 422 (when enforce=true and a metric fails threshold):
 * { error:"INGESTIBILITY_FAILURE", message, data:{...} }
 */
router.post("/registry/models/:modelId/rate", async (req, res, next) => {
  try {
    const { modelId } = req.params;
    const { target } = req.body || {};

    if (!target || typeof target !== "string") {
      const err = new Error("target is required (GitHub/HF URL string).");
      err.status = 400;
      throw err;
    }

    const row = await runScorer(target);

    // Flexible mapping for keys that may differ in Phase-1 output
    const subscores = {
      license: alias(row, "license", "License", "score_license"),
      ramp_up: alias(row, "ramp_up", "RampUp", "score_ramp_up", "rampUp"),
      bus_factor: alias(
        row,
        "bus_factor",
        "BusFactor",
        "score_bus_factor",
        "busFactor"
      ),
      performance_claims: alias(
        row,
        "performance_claims",
        "PerformanceClaims",
        "score_performance_claims",
        "performanceClaims"
      ),
      size: alias(row, "size", "Size", "score_size"),
      dataset_code: alias(
        row,
        "dataset_code",
        "DatasetCode",
        "score_available_dataset_and_code",
        "available_dataset_and_code"
      ),
      dataset_quality: alias(
        row,
        "dataset_quality",
        "DatasetQuality",
        "score_dataset_quality"
      ),
      code_quality: alias(
        row,
        "code_quality",
        "CodeQuality",
        "score_code_quality"
      ),

      // Phase-2 additions
      dependencies: alias(
        row,
        "dependencies",
        "Dependencies",
        "score_dependencies"
      ),
      pull_requests: alias(
        row,
        "pull_requests",
        "PullRequests",
        "score_pull_requests"
      ),
    };

    const netScore = alias(row, "net_score", "NetScore", "netScore");
    const latency = alias(
      row,
      "aggregation_latency",
      "AggregationLatency",
      "latency",
      "total_latency"
    );

    // optional enforcement
    const enforce = String(req.query.enforce || "").toLowerCase() === "true";
    if (enforce) {
      const failures = Object.entries(subscores)
        .filter(([, v]) => v !== undefined && v !== null)
        .filter(([, v]) => Number(v) <= 0.5);

      if (failures.length) {
        return res.status(422).json({
          error: "INGESTIBILITY_FAILURE",
          message: `Failed ingestibility: ${failures
            .map(([k, v]) => `${k}=${v}`)
            .join(", ")}`,
          data: { modelId, target, netScore, subscores, latency },
        });
      }
    }

    return res
      .status(200)
      .json({ data: { modelId, target, netScore, subscores, latency } });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
