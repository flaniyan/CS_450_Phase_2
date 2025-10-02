const express = require("express");
const routes = require("./routes");
const errorHandler = require("./middleware/errorHandler");

const app = express();
app.use("/api", routes);

// simple health check
app.get("/health", (_req, res) => res.status(200).json({ ok: true }));

// mount API routes
app.use("/api", routes);

// central error handler
app.use(errorHandler);

// start only when run directly (not during tests)
const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
}

module.exports = app;
