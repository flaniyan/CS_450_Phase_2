const { runWithTimeout } = require("../../../validator/src/timeout");

test("times out slow validator", async () => {
  await expect(
    runWithTimeout(async () => {
      // pretend the validator hangs
      await new Promise((r) => setTimeout(r, 6000));
    }, 1000) // 1 second budget
  ).rejects.toThrow(/TIMEOUT/);
});

test("completes fast validator successfully", async () => {
  const result = await runWithTimeout(async () => {
    await new Promise((r) => setTimeout(r, 100));
    return "success";
  }, 1000);

  expect(result).toBe("success");
});

test("handles promise rejection within timeout", async () => {
  await expect(
    runWithTimeout(async () => {
      await new Promise((r) => setTimeout(r, 100));
      throw new Error("VALIDATION_ERROR");
    }, 1000)
  ).rejects.toThrow("VALIDATION_ERROR");
});
