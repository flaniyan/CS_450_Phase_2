module.exports = (err, _req, res, _next) => {
  const status = err.status || 500;
  res.status(status).json({
    error: err.name || "Error",
    message: err.message || "Something went wrong",
  });
};
