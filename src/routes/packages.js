const { Router } = require("express");
const router = Router();

// Minimal placeholder list endpoint (so file is non-empty/useful)
router.get("/", (_req, res) => res.json({ packages: [] }));

module.exports = router;
