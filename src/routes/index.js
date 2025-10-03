const { Router } = require("express");
const router = Router();

router.get("/hello", (_req, res) => res.json({ message: "hello world" }));
router.use("/packages", require("./packages"));
// ratings routes under /api/registry/models/:modelId/ratings...
router.use("/", require("../services/rating"));

module.exports = router;
