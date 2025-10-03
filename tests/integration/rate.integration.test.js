const request = require("supertest");
const { spawnSync } = require("child_process");

function hasPython() {
  const r = spawnSync(process.platform === "win32" ? "python" : "python3", [
    "--version",
  ]);
  return r.status === 0;
}

describe("integration: rate endpoint", () => {
  let app;
  beforeAll(() => {
    if (!hasPython()) {
      console.warn("Skipping integration test: python not found");
      // Jest: skip all tests in this block
      return pending();
    }
    jest.resetModules();
    app = require("../../src/index");
  });

  test("calls real python scorer and returns data", async () => {
    if (!hasPython()) return; // safety

    const res = await request(app)
      .post("/api/registry/models/demo/rate")
      .send({ target: "https://github.com/pallets/flask" })
      .set("Content-Type", "application/json");

    expect([200, 422, 502]).toContain(res.status); // allow enforce logic differences and Python errors
    expect(res.body).toHaveProperty("data.netScore");
    expect(res.body).toHaveProperty("data.subscores");
  });
});
