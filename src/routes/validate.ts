import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";

async function runPythonValidator(
  code: Buffer,
  input: object,
  timeoutMs = 5000
) {
  const path = join(tmpdir(), `validator_${Date.now()}.py`);
  await fs.writeFile(path, code);

  return new Promise<{ ok: boolean; allow?: boolean; reason?: string }>(
    (resolve, reject) => {
      const args = [
        "-I",
        "-S",
        "src/validator/py/driver.py",
        path,
        JSON.stringify(input),
      ];
      const child = spawn("python3", args, {
        env: {
          ...process.env,
          VALIDATOR_TIMEOUT_SEC: String(Math.ceil(timeoutMs / 1000)),
          VALIDATOR_MEMORY_MB: "128",
        },
      });

      let out = "",
        err = "";
      const killTimer = setTimeout(
        () => child.kill("SIGKILL"),
        timeoutMs + 500
      );

      child.stdout.on("data", (d) => (out += d));
      child.stderr.on("data", (d) => (err += d));
      child.on("exit", (code) => {
        clearTimeout(killTimer);
        try {
          const parsed = JSON.parse(out || "{}");
          if (code === 0)
            return resolve({ ok: true, allow: true, reason: parsed.reason });
          if (code === 3)
            return resolve({ ok: true, allow: false, reason: parsed.reason });
          return resolve({ ok: false, reason: parsed.error || `exit_${code}` });
        } catch {
          return reject(
            new Error(err || `validator_bad_output (code ${code})`)
          );
        }
      });
    }
  );
}
