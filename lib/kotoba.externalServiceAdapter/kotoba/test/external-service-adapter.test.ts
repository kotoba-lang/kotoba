import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerConnector,
  getConnector,
  listConnectors,
  recordSync,
  listSyncs,
  getSync,
  recordGrant,
  listGrants,
  getGrant,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:external-service-adapter.etzhayyim.com";

describe("external-service-adapter kotoba (kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("providerConnector (PLAINTEXT public catalog)", () => {
    it("registers, dedups, validates, gets, lists/filters", async () => {
      expect(
        (await registerConnector(e, { provider: "outlook", displayName: "Outlook Mail", category: "mail", apiBase: "https://graph.microsoft.com/v1.0", scopes: ["Mail.Read"] })).status,
      ).toBe("registered");
      expect(
        (await registerConnector(e, { provider: "outlook", displayName: "Outlook Mail", category: "mail", apiBase: "https://graph.microsoft.com/v1.0" })).status,
      ).toBe("alreadyExists");
      expect((await registerConnector(e, { provider: "", displayName: "x", category: "mail", apiBase: "y" })).status).toBe("rejected");
      await registerConnector(e, { provider: "gmail", displayName: "Gmail", category: "mail", apiBase: "https://gmail.googleapis.com" });
      await registerConnector(e, { provider: "gcal", displayName: "Google Calendar", category: "calendar", apiBase: "https://www.googleapis.com/calendar/v3" });

      const got = await getConnector(e, { provider: "outlook" });
      expect(got.connector?.displayName).toBe("Outlook Mail");
      expect(got.connector?.scopes).toEqual(["Mail.Read"]);
      expect((await getConnector(e, { provider: "nope" })).error).toBe("notFound");

      expect((await listConnectors(e)).total).toBe(3);
      expect((await listConnectors(e, { category: "mail" })).total).toBe(2);
    });
  });

  describe("mailboxSync (E2E-ENCRYPTED per-person)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await recordSync(e, { syncId: "s1", userDid: "did:web:alice.example", provider: "outlook", folder: "INBOX", messagesIngested: 42, watermark: "wm-9", oauthStatus: "connected" });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      expect((await recordSync(e, { syncId: "sX", userDid: "d", provider: "p", messagesIngested: -1 })).status).toBe("rejected");
      expect((await recordSync(e, { syncId: "sY", userDid: "d", provider: "p", messagesIngested: 1, oauthStatus: "bogus" as any })).status).toBe("rejected");

      const got = await getSync(e, { syncId: "s1" });
      expect(got.sync?.userDid).toBe("did:web:alice.example");
      expect(got.sync?.messagesIngested).toBe(42);
      expect(got.sync?.oauthStatus).toBe("connected");

      await recordSync(e, { syncId: "s2", userDid: "did:web:bob.example", provider: "gmail", messagesIngested: 7 });
      expect((await listSyncs(e)).total).toBe(2);
      expect((await listSyncs(e, { provider: "outlook" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the sync", async () => {
      await recordSync(e, { syncId: "s1", userDid: "did:web:alice.example", provider: "outlook", messagesIngested: 5 });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listSyncs(outsider)).total).toBe(0);
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await recordSync(e, { syncId: "s1", userDid: "did:web:alice.example", provider: "outlook", messagesIngested: 5, recipients: [partner] });
      expect(r.status).toBe("recorded");
      expect((await listSyncs(e)).total).toBe(1);
    });
  });

  describe("oauthGrant (E2E-ENCRYPTED binding metadata only)", () => {
    it("seals scopes/status (no tokens), round-trips, validates", async () => {
      const ok = await recordGrant(e, { grantId: "g1", userDid: "did:web:alice.example", provider: "outlook", scopes: ["Mail.Read", "Calendars.ReadWrite"], status: "connected", expiresAt: "2026-07-01T00:00:00.000Z" });
      expect(ok.status).toBe("recorded");
      expect((await recordGrant(e, { grantId: "", userDid: "d", provider: "p" })).status).toBe("rejected");
      expect((await recordGrant(e, { grantId: "gX", userDid: "d", provider: "p", status: "bogus" as any })).status).toBe("rejected");

      const got = await getGrant(e, { grantId: "g1" });
      expect(got.grant?.scopes).toEqual(["Mail.Read", "Calendars.ReadWrite"]);
      expect(got.grant?.status).toBe("connected");
      // Binding metadata only — body never carries raw tokens/secrets.
      expect(Object.keys(got.grant ?? {})).not.toContain("accessToken");
      expect(Object.keys(got.grant ?? {})).not.toContain("refreshToken");

      await recordGrant(e, { grantId: "g2", userDid: "did:web:bob.example", provider: "gmail", status: "expired" });
      expect((await listGrants(e)).total).toBe(2);
      expect((await listGrants(e, { provider: "gmail" })).total).toBe(1);
    });

    it("isolates grants by owner DID", async () => {
      await recordGrant(e, { grantId: "g1", userDid: "did:web:alice.example", provider: "outlook" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listGrants(outsider)).total).toBe(0);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext connectors + E2E syncs + E2E grants", async () => {
      await registerConnector(e, { provider: "outlook", displayName: "Outlook", category: "mail", apiBase: "x" });
      await registerConnector(e, { provider: "gmail", displayName: "Gmail", category: "mail", apiBase: "y" });
      await registerConnector(e, { provider: "gcal", displayName: "GCal", category: "calendar", apiBase: "z" });
      await recordSync(e, { syncId: "s1", userDid: "did:web:a", provider: "outlook", messagesIngested: 3 });
      await recordGrant(e, { grantId: "g1", userDid: "did:web:a", provider: "outlook" });

      const cov = await coverage(e);
      expect(cov.providerConnectorCount).toBe(3);
      expect(cov.mailboxSyncCount).toBe(1);
      expect(cov.oauthGrantCount).toBe(1);
      expect(cov.connectorsByCategory?.mail).toBe(2);
      expect(cov.connectorsByCategory?.calendar).toBe(1);
      expect(cov.truncated).toBe(false);
    });
  });
});
