import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerChannel,
  listChannels,
  getChannel,
  recordRun,
  listRuns,
  registerBridge,
  listBridges,
  getBridge,
  recordMessage,
  listMessages,
  getMessage,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:os-messaging.etzhayyim.com";

describe("os-messaging kotoba (E2E + plaintext split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("openChannel (PLAINTEXT public crawl catalog)", () => {
    it("records, dedups, validates, lists/filters, gets", async () => {
      expect((await registerChannel(e, { channelKey: "c1", platform: "telegram", channelId: "tg-100", title: "Open Telegram A", country: "JP" })).status).toBe("recorded");
      expect((await registerChannel(e, { channelKey: "c1", platform: "telegram", channelId: "tg-100", title: "Open Telegram A", country: "JP" })).status).toBe("alreadyExists");
      expect((await registerChannel(e, { channelKey: "cX", platform: "nope" as any, channelId: "x", title: "x" })).status).toBe("rejected");
      await registerChannel(e, { channelKey: "c2", platform: "line", channelId: "ln-9", title: "Open LINE B", country: "KR" });
      expect((await listChannels(e)).total).toBe(2);
      expect((await listChannels(e, { platform: "telegram" })).total).toBe(1);
      expect((await listChannels(e, { country: "KR" })).total).toBe(1);
      expect((await getChannel(e, { channelKey: "c1" })).channel?.title).toBe("Open Telegram A");
      expect((await getChannel(e, { channelKey: "missing" })).error).toBe("notFound");
    });
  });

  describe("scraperRun (PLAINTEXT operational aggregate)", () => {
    it("records counts, dedups, validates, lists/filters", async () => {
      expect((await recordRun(e, { runId: "r1", platform: "telegram", status: "ok", messagesSeen: 120, messagesNew: 30 })).status).toBe("recorded");
      expect((await recordRun(e, { runId: "r1", platform: "telegram", status: "ok", messagesSeen: 120, messagesNew: 30 })).status).toBe("alreadyExists");
      expect((await recordRun(e, { runId: "rX", platform: "telegram", status: "ok", messagesSeen: -1, messagesNew: 0 })).status).toBe("rejected");
      expect((await recordRun(e, { runId: "rY", platform: "telegram", status: "bogus" as any, messagesSeen: 0, messagesNew: 0 })).status).toBe("rejected");
      await recordRun(e, { runId: "r2", platform: "line", status: "error", messagesSeen: 0, messagesNew: 0, errorMessage: "timeout" });
      expect((await listRuns(e)).total).toBe(2);
      expect((await listRuns(e, { status: "error" })).total).toBe(1);
      expect((await listRuns(e, { platform: "telegram" })).total).toBe(1);
    });
  });

  describe("bridge (E2E control-plane: convoDid + owner)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await registerBridge(e, { bridgeId: "b1", platform: "discord", channelId: "dc-1", ownerDid: OWNER, bridgeMode: "fully-bridged", convoDid: "did:web:convo.example", e2eMode: "server-assisted" });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      expect((await registerBridge(e, { bridgeId: "bX", platform: "discord", channelId: "x", ownerDid: OWNER, bridgeMode: "bad" as any, e2eMode: "plaintext" })).status).toBe("rejected");
      expect((await registerBridge(e, { bridgeId: "bY", platform: "discord", channelId: "x", ownerDid: OWNER, bridgeMode: "read-only", e2eMode: "bad" as any })).status).toBe("rejected");
      const got = await getBridge(e, { bridgeId: "b1" });
      expect(got.bridge?.convoDid).toBe("did:web:convo.example");
      expect(got.bridge?.bridgeMode).toBe("fully-bridged");
      await registerBridge(e, { bridgeId: "b2", platform: "slack", channelId: "sl-2", ownerDid: OWNER, bridgeMode: "agent-only", e2eMode: "plaintext" });
      expect((await listBridges(e)).total).toBe(2);
      expect((await listBridges(e, { platform: "discord" })).total).toBe(1);
      expect((await listBridges(e, { bridgeMode: "agent-only" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the bridge", async () => {
      await registerBridge(e, { bridgeId: "b1", platform: "discord", channelId: "dc-1", ownerDid: OWNER, bridgeMode: "fully-bridged", e2eMode: "server-assisted" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listBridges(outsider)).total).toBe(0);
    });
  });

  describe("openMessage (E2E per-author scraped content)", () => {
    it("requires parent channel (cross-tier FK), seals, round-trips, validates", async () => {
      // FK: parent openChannel must exist (plaintext catalog).
      expect((await recordMessage(e, { messageId: "m1", channelKey: "c1", platform: "telegram", platformMessageId: "p1", authorLabel: "alice", messageText: "hi" })).status).toBe("rejected");
      await registerChannel(e, { channelKey: "c1", platform: "telegram", channelId: "tg-100", title: "Open Telegram A" });
      const ok = await recordMessage(e, { messageId: "m1", channelKey: "c1", platform: "telegram", platformMessageId: "p1", authorLabel: "alice", messageText: "hello world" });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      expect((await recordMessage(e, { messageId: "mX", channelKey: "c1", platform: "telegram", platformMessageId: "p2", authorLabel: "", messageText: "x" })).status).toBe("rejected");
      const got = await getMessage(e, { messageId: "m1" });
      expect(got.message?.messageText).toBe("hello world");
      expect(got.message?.authorLabel).toBe("alice");
      await recordMessage(e, { messageId: "m2", channelKey: "c1", platform: "telegram", platformMessageId: "p3", authorLabel: "bob", messageText: "second" });
      expect((await listMessages(e)).total).toBe(2);
      expect((await listMessages(e, { channelKey: "c1" })).total).toBe(2);
      expect((await listMessages(e, { platform: "line" })).total).toBe(0);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the message", async () => {
      await registerChannel(e, { channelKey: "c1", platform: "telegram", channelId: "tg-100", title: "Open Telegram A" });
      await recordMessage(e, { messageId: "m1", channelKey: "c1", platform: "telegram", platformMessageId: "p1", authorLabel: "alice", messageText: "secret" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listMessages(outsider)).total).toBe(0);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext catalog + E2E control-plane/content", async () => {
      await registerChannel(e, { channelKey: "c1", platform: "telegram", channelId: "tg-1", title: "A" });
      await registerChannel(e, { channelKey: "c2", platform: "telegram", channelId: "tg-2", title: "B" });
      await registerChannel(e, { channelKey: "c3", platform: "line", channelId: "ln-1", title: "C" });
      await recordRun(e, { runId: "r1", platform: "telegram", status: "ok", messagesSeen: 10, messagesNew: 2 });
      await registerBridge(e, { bridgeId: "b1", platform: "discord", channelId: "dc-1", ownerDid: OWNER, bridgeMode: "read-only", e2eMode: "plaintext" });
      await recordMessage(e, { messageId: "m1", channelKey: "c1", platform: "telegram", platformMessageId: "p1", authorLabel: "alice", messageText: "x" });
      const cov = await coverage(e);
      expect(cov.openChannelCount).toBe(3);
      expect(cov.scraperRunCount).toBe(1);
      expect(cov.bridgeCount).toBe(1);
      expect(cov.openMessageCount).toBe(1);
      expect(cov.channelsByPlatform?.telegram).toBe(2);
      expect(cov.channelsByPlatform?.line).toBe(1);
    });
  });
});
