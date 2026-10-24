import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  createTransferRequest,
  getTransferRequest,
  transferFromSquarespace,
  putTransferStep,
  listTransferSteps,
  putTransferOutcome,
} from "../src/index.js";

describe("dns kotoba", () => {
  let e: any;

  beforeEach(() => {
    e = new MockEtzhayyim({ did: "did:web:dns.etzhayyim.com" });
  });

  describe("3-signer approval invariant", () => {
    it("transferFromSquarespace rejects with needsApprovals if < 3 approvals", async () => {
      const result = await transferFromSquarespace(e, {
        transferId: "transfer-1",
        domain: "example.com",
        requesterDid: "did:plc:requester",
        projectConvoId: "convo-1",
        approvals: ["did:plc:signer1", "did:plc:signer2"],
      });

      expect(result.status).toBe("needsApprovals");
      expect(result.error).toContain("requires 3 approvals");
    });

    it("transferFromSquarespace succeeds with 3 approvals", async () => {
      const result = await transferFromSquarespace(e, {
        transferId: "transfer-2",
        domain: "example.com",
        requesterDid: "did:plc:requester",
        projectConvoId: "convo-2",
        approvals: [
          "did:plc:signer1",
          "did:plc:signer2",
          "did:plc:signer3",
        ],
      });

      expect(result.status).toMatch(/started|alreadyExists/);
      expect(result.transferRequestUri).toBeDefined();
    });
  });

  describe("createTransferRequest + getTransferRequest", () => {
    it("creates transfer request with required fields", async () => {
      const result = await createTransferRequest(e, {
        transferId: "transfer-3",
        domain: "test.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-3",
      });

      expect(result.status).toBe("registered");
      expect(result.transferRequestUri).toBeDefined();
      expect(result.did).toBeDefined();
    });

    it("is idempotent on transferId", async () => {
      const input = {
        transferId: "transfer-4",
        domain: "idempotent.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-4",
      };

      const first = await createTransferRequest(e, input);
      expect(first.status).toBe("registered");

      const second = await createTransferRequest(e, input);
      expect(second.status).toBe("alreadyExists");
      expect(second.did).toBe(first.did);
    });

    it("getTransferRequest retrieves created request", async () => {
      const created = await createTransferRequest(e, {
        transferId: "transfer-5",
        domain: "fetch.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-5",
      });

      const result = await getTransferRequest(e, {
        transferId: "transfer-5",
      });

      expect(result.transferRequest).toBeDefined();
      expect(result.transferRequest?.transferId).toBe("transfer-5");
      expect(result.transferRequest?.domain).toBe("fetch.com");
    });
  });

  describe("putTransferStep authCode encryption invariant", () => {
    beforeEach(async () => {
      await createTransferRequest(e, {
        transferId: "transfer-6",
        domain: "auth.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-6",
      });
    });

    it("rejects authCode step without signal:v1: prefix", async () => {
      const result = await putTransferStep(e, {
        transferId: "transfer-6",
        step: "authCode",
        status: "pending",
        authCodeEncrypted: "unencrypted-code-123",
      });

      expect(result.status).toBe("rejected");
      expect(result.error).toBe("authCodeNotEncrypted");
    });

    it("accepts authCode step with signal:v1: prefix", async () => {
      const result = await putTransferStep(e, {
        transferId: "transfer-6",
        step: "authCode",
        status: "pending",
        authCodeEncrypted: "signal:v1:encrypted-payload-abc123",
      });

      expect(result.status).toBe("registered");
      expect(result.transferStepUri).toBeDefined();
    });

    it("allows non-authCode steps without encryption check", async () => {
      const result = await putTransferStep(e, {
        transferId: "transfer-6",
        step: "locking",
        status: "completed",
      });

      expect(result.status).toBe("registered");
    });
  });

  describe("listTransferSteps filter by transferId", () => {
    beforeEach(async () => {
      await createTransferRequest(e, {
        transferId: "transfer-7",
        domain: "steps.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-7",
      });
      await putTransferStep(e, {
        transferId: "transfer-7",
        step: "initiate",
        status: "completed",
      });
      await putTransferStep(e, {
        transferId: "transfer-7",
        step: "authCode",
        status: "pending",
        authCodeEncrypted: "signal:v1:code",
      });
    });

    it("lists steps for transferId", async () => {
      const result = await listTransferSteps(e, {
        transferId: "transfer-7",
      });

      expect(result.items.length).toBe(2);
      expect(result.items.every((s) => s.transferId === "transfer-7")).toBe(
        true
      );
    });

    it("returns empty for non-existent transferId", async () => {
      const result = await listTransferSteps(e, {
        transferId: "nonexistent",
      });

      expect(result.items.length).toBe(0);
    });
  });

  describe("putTransferOutcome derives zoneDid on success", () => {
    beforeEach(async () => {
      await createTransferRequest(e, {
        transferId: "transfer-8",
        domain: "outcome.com",
        requesterDid: "did:plc:req",
        projectConvoId: "conv-8",
      });
    });

    it("putTransferOutcome success sets zoneDid", async () => {
      const result = await putTransferOutcome(e, {
        transferId: "transfer-8",
        result: "success",
        cloudflareZoneId: "zone-123",
      });

      expect(result.status).toBe("registered");
      expect(result.zoneDid).toBeDefined();
    });

    it("putTransferOutcome failure has no zoneDid", async () => {
      const result = await putTransferOutcome(e, {
        transferId: "transfer-8",
        result: "failure",
        failureReason: "Invalid auth code",
      });

      expect(result.status).toBe("registered");
      expect(result.zoneDid).toBeUndefined();
    });
  });
});
