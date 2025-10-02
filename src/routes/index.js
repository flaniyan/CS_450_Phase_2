// src/routes/index.js
const { Router } = require("express");
const router = Router();

router.get("/hello", (_req, res) => {
  res.json({ message: "hello world" });
});

module.exports = router; // <-- IMPORTANT: CommonJS export
