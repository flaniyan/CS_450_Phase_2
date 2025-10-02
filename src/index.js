const express = require("express");
const routes = require("./routes");
const errorHandler = require("./middleware/errorHandler");

const app = express();
app.use(express.json());

// health check
app.get("/health", (_req, res) => res.status(200).json({ ok: true }));

// mount your API routes (once)
app.use("/api", routes);

// central error handler (keep last)
app.use(errorHandler);

// start only when run directly (not during tests)
const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
}

module.exports = app;
