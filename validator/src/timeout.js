// Simple wall-time guard for any async operation
async function runWithTimeout(promiseFactory, ms = 5000) {
  const timeout = new Promise((_, rej) =>
    setTimeout(() => rej(new Error("TIMEOUT")), ms)
  );
  // promiseFactory must be a function that returns a Promise when called
  return Promise.race([promiseFactory(), timeout]);
}

module.exports = { runWithTimeout };
