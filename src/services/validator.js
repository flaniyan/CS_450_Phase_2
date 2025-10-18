const express = require("express");
const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  QueryCommand,
} = require("@aws-sdk/lib-dynamodb");
const { S3Client, GetObjectCommand } = require("@aws-sdk/client-s3");
const { exec, spawn } = require("child_process");
const { promisify } = require("util");
const fs = require("fs").promises;
const path = require("path");
const os = require("os");
const {
  Worker,
  isMainThread,
  parentPort,
  workerData,
} = require("worker_threads");

const execAsync = promisify(exec);

const app = express();

// Security middleware: limit body size to prevent DoS
app.use(express.json({ limit: "32kb" }));

// Simple rate limiting (requests per minute per IP)
const rateLimitMap = new Map();
const RATE_LIMIT_WINDOW_MS = 10 * 1000; // 10 seconds
const RATE_LIMIT_MAX_REQUESTS = 20;

app.use("/validate", (req, res, next) => {
  const clientIP = req.ip || req.connection.remoteAddress || "unknown";
  const now = Date.now();

  // Clean old entries
  for (const [ip, data] of rateLimitMap.entries()) {
    if (now - data.firstRequest > RATE_LIMIT_WINDOW_MS) {
      rateLimitMap.delete(ip);
    }
  }

  const clientData = rateLimitMap.get(clientIP);
  if (!clientData) {
    rateLimitMap.set(clientIP, { firstRequest: now, count: 1 });
    return next();
  }

  if (now - clientData.firstRequest > RATE_LIMIT_WINDOW_MS) {
    // Reset window
    rateLimitMap.set(clientIP, { firstRequest: now, count: 1 });
    return next();
  }

  clientData.count++;
  if (clientData.count > RATE_LIMIT_MAX_REQUESTS) {
    return res.status(429).json({
      error: "Rate limit exceeded",
      message: "Too many requests",
    });
  }

  next();
});

// AWS Configuration
const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const ARTIFACTS_BUCKET = process.env.ARTIFACTS_BUCKET || "pkg-artifacts";
const DDB_TABLE_PACKAGES = process.env.DDB_TABLE_PACKAGES || "packages";
const DDB_TABLE_DOWNLOADS = process.env.DDB_TABLE_DOWNLOADS || "downloads";

// AWS Clients
const ddbClient = new DynamoDBClient({ region: AWS_REGION });
const docClient = DynamoDBDocumentClient.from(ddbClient);
const s3Client = new S3Client({ region: AWS_REGION });

// Concurrency control for validator execution
const MAX_CONCURRENT_VALIDATORS = 4;
let activeValidators = 0;
const validatorQueue = [];

function executeValidator() {
  if (
    activeValidators >= MAX_CONCURRENT_VALIDATORS ||
    validatorQueue.length === 0
  ) {
    return;
  }

  const { resolve, reject, fn, args } = validatorQueue.shift();
  activeValidators++;

  Promise.resolve(fn(...args))
    .then(resolve)
    .catch(reject)
    .finally(() => {
      activeValidators--;
      if (validatorQueue.length > 0) {
        setImmediate(executeValidator);
      }
    });
}

function queueValidator(fn, ...args) {
  return new Promise((resolve, reject) => {
    validatorQueue.push({ resolve, reject, fn, args });
    executeValidator();
  });
}

// Python validator runner with timeout and resource limits
async function runPythonValidator(codeBuf, payload, timeoutMs = 5000) {
  const validatorPath = path.join(os.tmpdir(), `validator_${Date.now()}.py`);
  await fs.writeFile(validatorPath, codeBuf);

  return new Promise((resolve, reject) => {
    // Determine the correct path for driver.py (in Docker container vs local)
    const driverPath =
      process.env.NODE_ENV === "production"
        ? path.join(__dirname, "driver.py")
        : path.join(__dirname, "../../validator/driver.py");

    const args = [
      "-I",
      "-S",
      driverPath,
      validatorPath,
      JSON.stringify(payload),
    ];
    const child = spawn("python3", args, {
      env: {
        ...process.env,
        VALIDATOR_TIMEOUT_SEC: String(Math.ceil(timeoutMs / 1000)),
        VALIDATOR_MEMORY_MB: process.env.VALIDATOR_MEMORY_MB || "128",
        VALIDATOR_NOFILE_SOFT: "64",
        VALIDATOR_NPROC_SOFT: "64",
      },
    });

    let out = "";
    let err = "";

    const kill = setTimeout(() => child.kill("SIGKILL"), timeoutMs + 500);

    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));

    child.on("exit", (code) => {
      clearTimeout(kill);

      // Clean up temp file
      fs.unlink(validatorPath).catch(() => {});

      try {
        const parsed = JSON.parse(out || "{}");
        if (code === 0)
          return resolve({ ok: true, allow: true, reason: parsed.reason });
        if (code === 3)
          return resolve({ ok: true, allow: false, reason: parsed.reason });
        return resolve({ ok: false, reason: parsed.error || `exit_${code}` });
      } catch {
        return reject(new Error(err || `validator_bad_output (code ${code})`));
      }
    });

    child.on("error", (err) => {
      clearTimeout(kill);
      fs.unlink(validatorPath).catch(() => {});
      reject(err);
    });
  });
}

// JavaScript validator runner using worker threads with timeout protection
async function runJavaScriptValidator(code, payload, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    // Create a temporary file for the worker to execute
    const tempFile = path.join(os.tmpdir(), `validator_js_${Date.now()}.js`);

    // Write the validator code to a file for the worker to execute
    fs.writeFile(tempFile, code)
      .then(() => {
        // Create worker thread with timeout
        const worker = new Worker(__filename, {
          workerData: { tempFile, payload, timeoutMs },
        });

        // Set timeout to kill worker thread
        const killTimer = setTimeout(() => {
          worker.terminate();
          fs.unlink(tempFile).catch(() => {});
          reject(
            new Error(`JavaScript validator timeout after ${timeoutMs}ms`)
          );
        }, timeoutMs);

        worker.on("message", (result) => {
          clearTimeout(killTimer);
          worker.terminate();
          fs.unlink(tempFile).catch(() => {});
          resolve(result);
        });

        worker.on("error", (error) => {
          clearTimeout(killTimer);
          worker.terminate();
          fs.unlink(tempFile).catch(() => {});
          reject(error);
        });

        worker.on("exit", (code) => {
          clearTimeout(killTimer);
          fs.unlink(tempFile).catch(() => {});
          if (code !== 0) {
            reject(new Error(`Worker stopped with exit code ${code}`));
          }
        });
      })
      .catch(reject);
  });
}

// Worker thread code (executed when this file is run as a worker)
if (!isMainThread) {
  const { tempFile, payload, timeoutMs } = workerData;

  try {
    // Load and execute the validator script
    delete require.cache[require.resolve(tempFile)];
    const validatorModule = require(tempFile);

    // Check if the validator has the expected interface
    if (typeof validatorModule.validate !== "function") {
      parentPort.postMessage({
        valid: false,
        error: "Missing validate function",
      });
      process.exit(1);
    }

    // Set up timeout for the validator execution
    const timeout = setTimeout(() => {
      parentPort.postMessage({
        valid: false,
        error: "Validator execution timeout",
      });
      process.exit(1);
    }, timeoutMs);

    // Execute the validator
    const result = validatorModule.validate(payload);

    clearTimeout(timeout);

    // Ensure result is properly formatted
    if (typeof result === "object" && result !== null) {
      parentPort.postMessage(result);
    } else {
      parentPort.postMessage({
        valid: false,
        error: "Invalid validator response format",
      });
    }

    process.exit(0);
  } catch (error) {
    parentPort.postMessage({
      valid: false,
      error: error.message,
    });
    process.exit(1);
  }
}

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "validator",
    timestamp: new Date().toISOString(),
  });
});

// Validate package endpoint
app.post("/validate", async (req, res) => {
  try {
    const { pkgName, version, userId, groups = [] } = req.body;

    if (!pkgName || !version || !userId) {
      return res.status(400).json({
        error: "Missing required fields: pkgName, version, userId",
      });
    }

    console.log(
      `Validating package: ${pkgName}@${version} for user: ${userId}`
    );

    // 1. Check if package exists in DynamoDB
    const packageKey = `${pkgName}@${version}`;
    const packageResult = await docClient.send(
      new GetCommand({
        TableName: DDB_TABLE_PACKAGES,
        Key: { pkg_key: packageKey },
      })
    );

    if (!packageResult.Item) {
      return res.status(404).json({
        error: "Package not found",
        pkgName,
        version,
      });
    }

    const packageData = packageResult.Item;

    // 2. Check if package is sensitive and user has access
    if (packageData.is_sensitive) {
      const userGroups = groups || [];
      const packageGroups = packageData.allowed_groups || [];

      const hasAccess = packageGroups.some((group) =>
        userGroups.includes(group)
      );

      if (!hasAccess) {
        // Log unauthorized access attempt
        await docClient.send(
          new PutCommand({
            TableName: DDB_TABLE_DOWNLOADS,
            Item: {
              event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              pkg_name: pkgName,
              version: version,
              user_id: userId,
              timestamp: new Date().toISOString(),
              status: "blocked",
              reason: "insufficient_group_access",
              user_groups: userGroups,
              required_groups: packageGroups,
            },
          })
        );

        return res.status(403).json({
          error: "Access denied",
          reason: "Package is sensitive and requires group access",
          required_groups: packageGroups,
          user_groups: userGroups,
        });
      }
    }

    // 3. Check if validator script exists - try Python first, then JavaScript
    let validatorKey = `validators/${pkgName}/${version}/validator.py`;
    let validatorType = "python";

    try {
      // Try to get Python validator first
      let validatorResult;
      try {
        validatorResult = await s3Client.send(
          new GetObjectCommand({
            Bucket: ARTIFACTS_BUCKET,
            Key: validatorKey,
          })
        );
      } catch (s3Error) {
        if (s3Error.name === "NoSuchKey") {
          // Try JavaScript validator
          validatorKey = `validators/${pkgName}/${version}/validator.js`;
          validatorType = "javascript";
          try {
            validatorResult = await s3Client.send(
              new GetObjectCommand({
                Bucket: ARTIFACTS_BUCKET,
                Key: validatorKey,
              })
            );
          } catch (jsError) {
            if (jsError.name === "NoSuchKey") {
              throw s3Error; // Will be handled in outer catch
            }
            throw jsError;
          }
        } else {
          throw s3Error;
        }
      }

      // 4. Download and run validator script
      const validatorScript = await validatorResult.Body.transformToString();

      // Prepare validator payload
      const validatorPayload = {
        pkgName,
        version,
        packageData,
        userId,
        groups,
      };

      try {
        if (validatorType === "python") {
          // Run Python validator with timeout protection and concurrency control
          const result = await queueValidator(
            runPythonValidator,
            Buffer.from(validatorScript),
            validatorPayload,
            5000
          );

          if (!result.ok) {
            throw new Error(`Python validator error: ${result.reason}`);
          }

          validationResult = {
            valid: result.allow,
            error: result.allow ? null : result.reason,
            reason: result.reason,
          };
        } else {
          // Run JavaScript validator using worker threads with timeout protection and concurrency control
          validationResult = await queueValidator(
            runJavaScriptValidator,
            validatorScript,
            validatorPayload,
            5000
          );
        }

        if (!validationResult.valid) {
          // Log failed validation
          await docClient.send(
            new PutCommand({
              TableName: DDB_TABLE_DOWNLOADS,
              Item: {
                event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                pkg_name: pkgName,
                version: version,
                user_id: userId,
                timestamp: new Date().toISOString(),
                status: "blocked",
                reason: "validation_failed",
                validation_error:
                  validationResult.error || "Unknown validation error",
              },
            })
          );

          return res.status(403).json({
            error: "Validation failed",
            reason: validationResult.error || "Package validation failed",
            details: validationResult.details,
          });
        }
      } catch (validatorError) {
        console.error(
          `Validator execution error for ${pkgName}@${version}:`,
          validatorError
        );

        // Log validator execution error
        await docClient.send(
          new PutCommand({
            TableName: DDB_TABLE_DOWNLOADS,
            Item: {
              event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              pkg_name: pkgName,
              version: version,
              user_id: userId,
              timestamp: new Date().toISOString(),
              status: "blocked",
              reason: "validator_execution_error",
              validation_error: validatorError.message,
            },
          })
        );

        return res.status(500).json({
          error: "Validator execution failed",
          reason: validatorError.message,
        });
      }

      // 5. Log successful validation
      await docClient.send(
        new PutCommand({
          TableName: DDB_TABLE_DOWNLOADS,
          Item: {
            event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            pkg_name: pkgName,
            version: version,
            user_id: userId,
            timestamp: new Date().toISOString(),
            status: "validated",
            validation_result: validationResult,
          },
        })
      );

      res.json({
        valid: true,
        pkgName,
        version,
        validation_result: validationResult,
        message: "Package validation successful",
      });
    } catch (s3Error) {
      if (s3Error.name === "NoSuchKey") {
        // No validator script - allow download
        console.log(
          `No validator script for ${pkgName}@${version}, allowing download`
        );

        await docClient.send(
          new PutCommand({
            TableName: DDB_TABLE_DOWNLOADS,
            Item: {
              event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              pkg_name: pkgName,
              version: version,
              user_id: userId,
              timestamp: new Date().toISOString(),
              status: "validated",
              reason: "no_validator_script",
            },
          })
        );

        res.json({
          valid: true,
          pkgName,
          version,
          message: "No validator script found, download allowed",
        });
      } else {
        throw s3Error;
      }
    }
  } catch (error) {
    console.error("Validation error:", error);
    res.status(500).json({
      error: "Internal server error",
      message: error.message,
    });
  }
});

// Get validation history for a user
app.get("/history/:userId", async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 50 } = req.query;

    const result = await docClient.send(
      new QueryCommand({
        TableName: DDB_TABLE_DOWNLOADS,
        IndexName: "user-timestamp-index", // We'll need to create this GSI
        KeyConditionExpression: "user_id = :userId",
        ExpressionAttributeValues: { ":userId": userId },
        ScanIndexForward: false, // Most recent first
        Limit: parseInt(limit),
      })
    );

    res.json({
      userId,
      history: result.Items || [],
      count: result.Items?.length || 0,
    });
  } catch (error) {
    console.error("History error:", error);
    res.status(500).json({
      error: "Internal server error",
      message: error.message,
    });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Validator service running on port ${PORT}`);
  console.log(`AWS Region: ${AWS_REGION}`);
  console.log(`Artifacts Bucket: ${ARTIFACTS_BUCKET}`);
});
