import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerDocument,
  getDocument,
  listDocuments,
  recordTransmission,
  listTransmissions,
  getTransmission,
  recordInbound,
  listInbound,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:fax.etzhayyim.com";

describe("fax kotoba (kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("renderedDocument (PLAINTEXT public artifact catalog)", () => {
    it("registers, dedups, validates, gets, lists/filters by format", async () => {
      expect((await registerDocument(e, { blobKey: "abcdef01", format: "markdown", pageCount: 2, byteSize: 4096 })).status).toBe("registered");
      expect((await registerDocument(e, { blobKey: "abcdef01", format: "markdown", pageCount: 2, byteSize: 4096 })).status).toBe("alreadyExists");
      expect((await registerDocument(e, { blobKey: "ZZZ", format: "text", pageCount: 1, byteSize: 1 })).status).toBe("rejected"); // bad blobKey
      expect((await registerDocument(e, { blobKey: "deadbeef", format: "text", pageCount: -1, byteSize: 1 })).status).toBe("rejected"); // bad pageCount
      await registerDocument(e, { blobKey: "deadbeef", format: "html", pageCount: 1, byteSize: 2048 });
      const got = await getDocument(e, { blobKey: "abcdef01" });
      expect(got.document?.pageSize).toBe("A4");
      expect(got.document?.pageCount).toBe(2);
      expect((await listDocuments(e)).total).toBe(2);
      expect((await listDocuments(e, { format: "html" })).total).toBe(1);
    });
  });

  describe("faxTransmission (E2E-ENCRYPTED message-metadata)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await recordTransmission(e, { txId: "fax-1", to: "+81338188411", caseId: "matsuoka-2504", subject: "通知書", status: "needs_human", pageCount: 3 });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      expect((await recordTransmission(e, { txId: "", to: "+8133" })).status).toBe("rejected"); // missing txId
      expect((await recordTransmission(e, { txId: "fax-x", to: "+8133", pageCount: -2 })).status).toBe("rejected"); // bad pageCount
      const got = await getTransmission(e, { txId: "fax-1" });
      expect(got.transmission?.to).toBe("+81338188411");
      expect(got.transmission?.caseId).toBe("matsuoka-2504");
      await recordTransmission(e, { txId: "fax-2", to: "+81312345678", caseId: "other-2505", status: "success" });
      expect((await listTransmissions(e)).total).toBe(2);
      expect((await listTransmissions(e, { caseId: "matsuoka-2504" })).total).toBe(1);
      expect((await listTransmissions(e, { status: "success" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt transmissions", async () => {
      await recordTransmission(e, { txId: "fax-1", to: "+81338188411", caseId: "matsuoka-2504" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listTransmissions(outsider)).total).toBe(0);
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await recordTransmission(e, { txId: "fax-1", to: "+81338188411", recipients: [partner] });
      expect(r.status).toBe("recorded");
      expect((await listTransmissions(e)).total).toBe(1);
    });
  });

  describe("inboundFax (E2E-ENCRYPTED message-metadata)", () => {
    it("seals, round-trips, validates, filters by sender", async () => {
      expect((await recordInbound(e, { rxId: "rx-1", from: "+81399998888", pageCount: 1, blobKey: "cafe1234" })).status).toBe("recorded");
      expect((await recordInbound(e, { rxId: "rx-x", from: "" })).status).toBe("rejected"); // missing from
      await recordInbound(e, { rxId: "rx-2", from: "+81311112222" });
      expect((await listInbound(e)).total).toBe(2);
      expect((await listInbound(e, { from: "+81399998888" })).total).toBe(1);
    });
  });

  describe("innerType partition (two E2E collections, one wrapper)", () => {
    it("keeps faxTransmission and inboundFax isolated in the shared wrapper", async () => {
      await recordTransmission(e, { txId: "fax-1", to: "+81338188411" });
      await recordTransmission(e, { txId: "fax-2", to: "+81312345678" });
      await recordInbound(e, { rxId: "rx-1", from: "+81399998888" });
      // Two encrypted collections share com.etzhayyim.encrypted.record; innerType
      // filtering MUST keep the counts from cross-contaminating.
      expect((await listTransmissions(e)).total).toBe(2);
      expect((await listInbound(e)).total).toBe(1);
      // getTransmission must not surface an inbound record and vice-versa.
      expect((await getTransmission(e, { txId: "rx-1" })).error).toBe("notFound");
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext documents + both E2E collections", async () => {
      await registerDocument(e, { blobKey: "abcdef01", format: "markdown", pageCount: 2, byteSize: 4096 });
      await recordTransmission(e, { txId: "fax-1", to: "+81338188411", status: "success" });
      await recordTransmission(e, { txId: "fax-2", to: "+81312345678", status: "success" });
      await recordTransmission(e, { txId: "fax-3", to: "+81355556666", status: "needs_human" });
      await recordInbound(e, { rxId: "rx-1", from: "+81399998888" });
      const cov = await coverage(e);
      expect(cov.renderedDocumentCount).toBe(1);
      expect(cov.faxTransmissionCount).toBe(3);
      expect(cov.inboundFaxCount).toBe(1);
      expect(cov.transmissionsByStatus?.success).toBe(2);
      expect(cov.transmissionsByStatus?.needs_human).toBe(1);
    });
  });
});
