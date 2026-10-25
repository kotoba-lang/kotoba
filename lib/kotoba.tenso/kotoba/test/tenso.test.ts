import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  recordStat,
  listStats,
  recordTransfer,
  listTransfers,
  getTransfer,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:tenso.etzhayyim.com";
const MANIFEST = "signal:v1:ZmFrZS1tYW5pZmVzdA==";

describe("tenso kotoba (kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("transferStat (PLAINTEXT public aggregate)", () => {
    it("records, dedups, validates, lists/filters", async () => {
      expect((await recordStat(e, { statId: "s1", bucket: "pending", transferCount: 12, totalBytes: 4096 })).status).toBe("recorded");
      expect((await recordStat(e, { statId: "s1", bucket: "pending", transferCount: 12, totalBytes: 4096 })).status).toBe("alreadyExists");
      expect((await recordStat(e, { statId: "sX", bucket: "pending", transferCount: -1, totalBytes: 0 })).status).toBe("rejected");
      expect((await recordStat(e, { statId: "sY", bucket: "pending", transferCount: 1, totalBytes: -5 })).status).toBe("rejected");
      await recordStat(e, { statId: "s2", bucket: "accepted", transferCount: 5, totalBytes: 1000 });
      expect((await listStats(e)).total).toBe(2);
      expect((await listStats(e, { bucket: "pending" })).total).toBe(1);
    });
  });

  describe("transferEnvelope (E2E-ENCRYPTED CUI)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await recordTransfer(e, { transferId: "t1", recipientDid: "did:web:bob.example", filename: "report.pdf", sizeBytes: 8192, chunkCount: 1, encryptedManifest: MANIFEST });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      // read-cap granted to BOTH owner (sender) and recipient
      expect(ok.grantedTo).toContain(OWNER);
      expect(ok.grantedTo).toContain("did:web:bob.example");

      expect((await recordTransfer(e, { transferId: "tX", recipientDid: "d", filename: "f", sizeBytes: 1, chunkCount: 0, encryptedManifest: MANIFEST })).status).toBe("rejected"); // chunkCount 0
      expect((await recordTransfer(e, { transferId: "tY", recipientDid: "d", filename: "f", sizeBytes: -1, chunkCount: 1, encryptedManifest: MANIFEST })).status).toBe("rejected"); // negative bytes
      expect((await recordTransfer(e, { transferId: "tZ", recipientDid: "d", filename: "f", sizeBytes: 1, chunkCount: 1, encryptedManifest: "" })).status).toBe("rejected"); // no manifest

      const got = await getTransfer(e, { transferId: "t1" });
      expect(got.transfer?.filename).toBe("report.pdf");
      expect(got.transfer?.recipientDid).toBe("did:web:bob.example");
      expect(got.transfer?.encryptedManifest).toBe(MANIFEST);
      expect(got.transfer?.sender).toBe(OWNER); // sender carried by envelope, not body
      expect(got.transfer?.mimeType).toBe("application/octet-stream"); // default applied

      await recordTransfer(e, { transferId: "t2", recipientDid: "did:web:carol.example", filename: "img.png", mimeType: "image/png", sizeBytes: 200, chunkCount: 1, encryptedManifest: MANIFEST });
      expect((await listTransfers(e)).total).toBe(2);
      expect((await listTransfers(e, { recipientDid: "did:web:bob.example" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the envelope", async () => {
      await recordTransfer(e, { transferId: "t1", recipientDid: "did:web:bob.example", filename: "secret.bin", sizeBytes: 64, chunkCount: 1, encryptedManifest: MANIFEST });
      // A distinct PDS view (no read-cap, separate envelope store) sees zero.
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listTransfers(outsider)).total).toBe(0);
      expect((await getTransfer(outsider, { transferId: "t1" })).error).toBe("notFound");
    });

    it("grants read-cap to an explicit extra recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await recordTransfer(e, { transferId: "t1", recipientDid: "did:web:bob.example", filename: "f.bin", sizeBytes: 10, chunkCount: 1, encryptedManifest: MANIFEST, recipients: [partner] });
      expect(r.status).toBe("recorded");
      expect(r.grantedTo).toContain(partner);
      expect(r.grantedTo).toContain("did:web:bob.example");
      expect(r.grantedTo).toContain(OWNER);
      // owner can still read back
      expect((await listTransfers(e)).total).toBe(1);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext stats + E2E envelopes by bucket", async () => {
      await recordStat(e, { statId: "s1", bucket: "pending", transferCount: 1, totalBytes: 10 });
      await recordStat(e, { statId: "s2", bucket: "pending", transferCount: 2, totalBytes: 20 });
      await recordTransfer(e, { transferId: "t1", recipientDid: "did:web:bob.example", filename: "f", sizeBytes: 5, chunkCount: 1, encryptedManifest: MANIFEST });
      const cov = await coverage(e);
      expect(cov.transferStatCount).toBe(2);
      expect(cov.transferEnvelopeCount).toBe(1);
      expect(cov.statsByBucket?.pending).toBe(2);
    });
  });
});
