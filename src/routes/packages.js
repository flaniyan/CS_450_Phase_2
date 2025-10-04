const { Router } = require("express");
const router = Router();
const storage = require("../services/storage");

function required(value, name) {
  if (!value) {
    const err = new Error(`${name} is required`);
    err.status = 400;
    throw err;
  }
}

router.get("/", (_req, res) => res.json({ packages: [] }));

// Initialize multipart upload
router.post("/init", async (req, res, next) => {
  try {
    const { pkgName, version } = req.body || {};
    required(pkgName, "pkgName");
    required(version, "version");
    const result = await storage.uploadInit(pkgName, version, {});
    res.json(result);
  } catch (e) {
    next(e);
  }
});

// Upload a part (expects binary body; here we accept base64 for simplicity)
router.put("/:pkgName/:version/part", async (req, res, next) => {
  try {
    const { pkgName, version } = req.params;
    const { uploadId, partNumber, data } = req.body || {};
    required(uploadId, "uploadId");
    required(partNumber, "partNumber");
    required(data, "data(base64)");
    const buffer = Buffer.from(data, "base64");
    const out = await storage.uploadPart(pkgName, version, uploadId, Number(partNumber), buffer);
    res.json(out);
  } catch (e) {
    next(e);
  }
});

// Commit multipart upload
router.post("/:pkgName/:version/commit", async (req, res, next) => {
  try {
    const { pkgName, version } = req.params;
    const { uploadId, parts } = req.body || {};
    required(uploadId, "uploadId");
    required(parts, "parts");
    await storage.uploadCommit(pkgName, version, uploadId, parts);
    res.status(204).end();
  } catch (e) {
    next(e);
  }
});

// Abort multipart upload
router.post("/:pkgName/:version/abort", async (req, res, next) => {
  try {
    const { pkgName, version } = req.params;
    const { uploadId } = req.body || {};
    required(uploadId, "uploadId");
    await storage.uploadAbort(pkgName, version, uploadId);
    res.status(204).end();
  } catch (e) {
    next(e);
  }
});

// Get presigned download URL
router.get("/:pkgName/:version/download", async (req, res, next) => {
  try {
    const { pkgName, version } = req.params;
    const ttl = Number(req.query.ttl || 300);
    const out = await storage.getDownloadUrl(pkgName, version, ttl);
    res.json(out);
  } catch (e) {
    next(e);
  }
});

// Manage validator script
router.post("/:pkgName/:version/validator", async (req, res, next) => {
  try {
    const { pkgName, version } = req.params;
    const { scriptBase64 } = req.body || {};
    required(scriptBase64, "scriptBase64");
    const buf = Buffer.from(scriptBase64, "base64");
    await storage.putValidatorScript(pkgName, version, buf);
    res.status(204).end();
  } catch (e) {
    next(e);
  }
});

module.exports = router;
