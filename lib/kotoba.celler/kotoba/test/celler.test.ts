import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  provisionNumber,
  getNumber,
  resolveByE164,
  listNumbers,
  releaseNumber,
  coverage,
  isValidE164,
  numberDid,
} from "../src/index.js";

describe("celler kotoba", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: "did:web:celler.kotoba-lang.org" });
  });

  describe("helpers", () => {
    it("validates E.164", () => {
      expect(isValidE164("+14155550123")).toBe(true);
      expect(isValidE164("+81312345678")).toBe(true);
      expect(isValidE164("14155550123")).toBe(false);
      expect(isValidE164("+0123")).toBe(false);
    });
    it("derives number DID", () => {
      expect(numberDid("N-1")).toBe("did:web:celler.kotoba-lang.org:number:n-1");
    });
  });

  describe("provisioning", () => {
    const n = {
      numberId: "N-1",
      ownerDid: "did:web:alice.etzhayyim.com",
      e164: "+14155550123",
      country: "US",
    };
    it("provisions an active number", async () => {
      const r = await provisionNumber(e, n);
      expect(r.status).toBe("provisioned");
      const got = await getNumber(e, { numberId: "N-1" });
      expect(got.number?.status).toBe("active");
      expect(got.number?.provider).toBe("telnyx");
    });
    it("is idempotent on numberId", async () => {
      await provisionNumber(e, n);
      expect((await provisionNumber(e, n)).status).toBe("alreadyExists");
    });
    it("rejects invalid E.164 / country", async () => {
      expect((await provisionNumber(e, { ...n, e164: "415" })).status).toBe("rejected");
      expect((await provisionNumber(e, { ...n, country: "usa" })).status).toBe("rejected");
    });
    it("resolves by E.164", async () => {
      await provisionNumber(e, n);
      const r = await resolveByE164(e, { e164: "+14155550123" });
      expect(r.number?.numberId).toBe("N-1");
      expect((await resolveByE164(e, { e164: "+19999999999" })).error).toBe("notFound");
    });
  });

  describe("lifecycle + coverage", () => {
    beforeEach(async () => {
      await provisionNumber(e, { numberId: "N-1", ownerDid: "did:web:alice.etzhayyim.com", e164: "+14155550123", country: "US" });
      await provisionNumber(e, { numberId: "N-2", ownerDid: "did:web:alice.etzhayyim.com", e164: "+81312345678", country: "JP" });
    });
    it("lists by owner / country", async () => {
      expect((await listNumbers(e, { ownerDid: "did:web:alice.etzhayyim.com" })).total).toBe(2);
      expect((await listNumbers(e, { country: "JP" })).total).toBe(1);
    });
    it("releases a number (and resolve skips released)", async () => {
      expect((await releaseNumber(e, { numberId: "N-1" })).status).toBe("released");
      expect((await releaseNumber(e, { numberId: "N-1" })).status).toBe("alreadyReleased");
      expect((await resolveByE164(e, { e164: "+14155550123" })).error).toBe("notFound");
    });
    it("coverage aggregates by country/status", async () => {
      const cov = await coverage(e);
      expect(cov.total).toBe(2);
      expect(cov.byCountry?.US).toBe(1);
      expect(cov.byStatus?.active).toBe(2);
    });
  });
});
