const request = require("supertest");
const EventEmitter = require("events");

jest.mock("child_process", () => {
  return {
    spawn: jest.fn(() => {
      const { EventEmitter } = require("events");
      const proc = new EventEmitter();
      proc.stdout = new EventEmitter();
      proc.stderr = new EventEmitter();
      // default success payload; tests can override by emitting again before 'close'
      const line = JSON.stringify({
        net_score: 0.72,
        license: 0.9,
        ramp_up: 0.8,
        bus_factor: 0.7,
        performance_claims: 0.7,
        size: 0.6,
        dataset_code: 0.8,
        dataset_quality: 0.85,
        code_quality: 0.8,
        dependencies: 0.9,
        pull_requests: 0.7,
        aggregation_latency: 123,
      });
      // delay a tick to mimic async process output
      process.nextTick(() => {
        proc.stdout.emit("data", line + "\n");
        proc.emit("close", 0);
      });
      return proc;
    }),
  };
});

const app = require("../../src/index");

describe("rate API (scoring via Python)", () => {
  const base = (modelId) => `/api/registry/models/${modelId}`;

  it("returns scoring results (200)", async () => {
    const modelId = "m-score-ok";
    const res = await request(app)
      .post(`${base(modelId)}/rate`)
      .send({ target: "https://github.com/org/repo" })
      .expect(200);
    expect(res.body.data).toHaveProperty("netScore");
    expect(res.body.data).toHaveProperty("subscores");
    expect(res.body.data).toMatchObject({
      modelId,
      target: expect.any(String),
    });
  });

  it("enforces ingestibility (422 when a subscore <= 0.5)", async () => {
    // Reconfigure mock to emit a failing dependencies score once
    const { spawn } = require("child_process");
    spawn.mockImplementationOnce(() => {
      const { EventEmitter } = require("events");
      const proc = new EventEmitter();
      proc.stdout = new EventEmitter();
      proc.stderr = new EventEmitter();
      const line = JSON.stringify({
        net_score: 0.55,
        license: 0.9,
        ramp_up: 0.8,
        bus_factor: 0.7,
        performance_claims: 0.7,
        size: 0.6,
        dataset_code: 0.8,
        dataset_quality: 0.85,
        code_quality: 0.8,
        dependencies: 0.4, // failing
        pull_requests: 0.7,
        aggregation_latency: 111,
      });
      process.nextTick(() => {
        proc.stdout.emit("data", line + "\n");
        proc.emit("close", 0);
      });
      return proc;
    });

    const modelId = "m-enforce";
    const res = await request(app)
      .post(`${base(modelId)}/rate?enforce=true`)
      .send({ target: "https://github.com/org/repo" })
      .expect(422);
    expect(res.body).toHaveProperty("error", "INGESTIBILITY_FAILURE");
    expect(res.body.data).toHaveProperty("subscores");
  });
});
