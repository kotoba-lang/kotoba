import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  createProcessRun,
  updateProcessRun,
  listProcessRuns,
  getProcessRun,
  createAutomation,
  updateAutomation,
  listAutomations,
  getAutomation,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:ops.etzhayyim.com";

describe("ops kotoba (kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("processRun (PLAINTEXT public operational telemetry)", () => {
    it("creates, dedups, validates, updates, lists/filters, gets", async () => {
      expect((await createProcessRun(e, { runId: "r1", processName: "billing-close", status: "running", stepCount: 5, completionPct: 40, durationMs: 1200 })).status).toBe("created");
      expect((await createProcessRun(e, { runId: "r1", processName: "billing-close" })).status).toBe("alreadyExists");
      // float-free invariants
      expect((await createProcessRun(e, { runId: "rX", processName: "p", completionPct: 200 })).status).toBe("rejected");
      expect((await createProcessRun(e, { runId: "rY", processName: "p", stepCount: -1 })).status).toBe("rejected");
      expect((await createProcessRun(e, { runId: "rZ", processName: "p", status: "bogus" as any })).status).toBe("rejected");

      await createProcessRun(e, { runId: "r2", processName: "campaign-roi", status: "succeeded", completionPct: 100 });
      expect((await listProcessRuns(e)).total).toBe(2);
      expect((await listProcessRuns(e, { processName: "billing-close" })).total).toBe(1);
      expect((await listProcessRuns(e, { status: "succeeded" })).total).toBe(1);

      const upd = await updateProcessRun(e, { runId: "r1", status: "succeeded", completionPct: 100, durationMs: 4200 });
      expect(upd.status).toBe("updated");
      expect((await updateProcessRun(e, { runId: "missing", status: "failed" })).status).toBe("notFound");

      const got = await getProcessRun(e, { runId: "r1" });
      expect(got.run?.status).toBe("succeeded");
      expect(got.run?.completionPct).toBe(100);
      expect(got.run?.durationMs).toBe(4200);
      expect((await getProcessRun(e, { runId: "nope" })).error).toBe("notFound");
    });
  });

  describe("automation (E2E-ENCRYPTED confidential business config)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates decimals", async () => {
      const ok = await createAutomation(e, {
        automationId: "a1",
        name: "Daily revenue sweep",
        schedule: "0 6 * * *",
        dispatchTarget: "com.etzhayyim.apps.ops.createProcessRun",
        revenueTargetUsd: "12500.00",
        creditsBudget: "5000.000",
      });
      expect(ok.status).toBe("created");
      expect(ok.keyId).toBeTruthy();

      // money must be a decimal STRING (no float).
      expect((await createAutomation(e, { automationId: "aX", name: "n", schedule: "* * * * *", dispatchTarget: "t", revenueTargetUsd: "12.5.6" })).status).toBe("rejected");
      expect((await createAutomation(e, { automationId: "aY", name: "n", schedule: "* * * * *", dispatchTarget: "t", status: "bogus" as any })).status).toBe("rejected");
      expect((await createAutomation(e, { automationId: "", name: "n", schedule: "s", dispatchTarget: "t" })).status).toBe("rejected");

      const got = await getAutomation(e, { automationId: "a1" });
      expect(got.automation?.revenueTargetUsd).toBe("12500.00");
      expect(got.automation?.dispatchTarget).toBe("com.etzhayyim.apps.ops.createProcessRun");

      await createAutomation(e, { automationId: "a2", name: "Pause me", schedule: "0 0 * * *", dispatchTarget: "t2", status: "paused" });
      expect((await listAutomations(e)).total).toBe(2);
      expect((await listAutomations(e, { status: "paused" })).total).toBe(1);

      const upd = await updateAutomation(e, { automationId: "a1", status: "archived", creditsBudget: "9999.000" });
      expect(upd.status).toBe("updated");
      const re = await getAutomation(e, { automationId: "a1" });
      expect(re.automation?.status).toBe("archived");
      expect(re.automation?.creditsBudget).toBe("9999.000");
      // re-seal at same rkey: still exactly 2 automations
      expect((await listAutomations(e)).total).toBe(2);
      expect((await updateAutomation(e, { automationId: "missing", status: "active" })).status).toBe("notFound");
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the automation", async () => {
      await createAutomation(e, { automationId: "a1", name: "secret", schedule: "s", dispatchTarget: "t" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listAutomations(outsider)).total).toBe(0);
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await createAutomation(e, { automationId: "a1", name: "shared", schedule: "s", dispatchTarget: "t", recipients: [partner] });
      expect(r.status).toBe("created");
      expect((await listAutomations(e)).total).toBe(1);
    });
  });

  describe("FK: processRun.automationId references an E2E automation", () => {
    it("rejects unknown automationId, accepts an existing one", async () => {
      expect((await createProcessRun(e, { runId: "r1", processName: "p", automationId: "ghost" })).status).toBe("rejected");
      await createAutomation(e, { automationId: "a1", name: "n", schedule: "s", dispatchTarget: "t" });
      expect((await createProcessRun(e, { runId: "r1", processName: "p", automationId: "a1" })).status).toBe("created");
      expect((await getProcessRun(e, { runId: "r1" })).run?.automationId).toBe("a1");
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext runs (by status) + E2E automations", async () => {
      await createProcessRun(e, { runId: "r1", processName: "p", status: "running" });
      await createProcessRun(e, { runId: "r2", processName: "p", status: "succeeded" });
      await createProcessRun(e, { runId: "r3", processName: "p", status: "succeeded" });
      await createAutomation(e, { automationId: "a1", name: "n", schedule: "s", dispatchTarget: "t" });
      const cov = await coverage(e);
      expect(cov.processRunCount).toBe(3);
      expect(cov.automationCount).toBe(1);
      expect(cov.runsByStatus?.succeeded).toBe(2);
      expect(cov.runsByStatus?.running).toBe(1);
      expect(cov.truncated).toBe(false);
    });
  });
});
