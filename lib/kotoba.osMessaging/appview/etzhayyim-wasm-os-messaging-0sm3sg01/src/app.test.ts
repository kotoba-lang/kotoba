/**
 * OS Messaging Gateway — Integration Tests
 * Tests: webhook parsing, platform dispatch, connection management, Slack/Discord verification.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

let writtenRecords: Array<{ collection: string; record: Record<string, unknown> }> = [];
let postedTexts: string[] = [];

vi.mock("@etzhayyim/kotodama-host-sdk", () => ({
  createWorkerExport: (setup: (sdk: any) => void) => {
    const commands = new Map<string, (sdk: any, params: string) => Promise<string>>();
    const queries = new Map<string, (sdk: any, params: string) => Promise<string>>();
    let commitFn: any = null;
    const mockSdk = {
      app: {
        command: (nsid: string, handler: any) => { commands.set(nsid, handler); },
        query: (nsid: string, handler: any) => { queries.set(nsid, handler); },
        onHeartbeat: () => {},
        onCommit: (fn: any) => { commitFn = fn; },
      },
      pds: {
        dispatch: (action: any) => {
          if (action.type === "com.atproto.repo.createRecord") {
            const { collection, recordJson } = action.payload;
            writtenRecords.push({ collection, record: JSON.parse(recordJson) });
          } else if (action.type === "app.bsky.feed.post") {
            postedTexts.push(action.payload.text);
          }
        },
      },
    };
    setup(mockSdk);
    return { __commands: commands, __queries: queries, __mockSdk: mockSdk, __commit: commitFn };
  },
  asAgentTool: (fn: any, _meta: any) => async (sdk: any, paramsJson: string) => {
    const input = JSON.parse(paramsJson || "{}");
    const result = await fn(input);
    return JSON.stringify(result);
  },
  withCapabilityTags: (_tags: string[]) => (fn: any) => fn,
  withOCELEvent: (_tag: string) => (fn: any) => fn,
  resolveHeartbeatCadence: () => ({ nextMs: 60000 }),
  createCadenceState: () => ({}),
  createInboxBuffer: () => ({ inboundCommits: [], reactions: [] }),
  createKyselyDb: () => ({
    selectFrom() {
      const chain: any = {
        select() { return chain; },
        where() { return chain; },
        limit() { return chain; },
        execute() { return Promise.resolve([]); },
        executeTakeFirst() { return Promise.resolve(undefined); },
      };
      return chain;
    },
  }),
  nowISO: () => "2026-04-13T00:00:00.000Z",
  str: (v: any) => String(v ?? ""),
  decodeJson: (s: string) => { try { return JSON.parse(s || "{}"); } catch { return {}; } },
}));

import appExport from "./app.js";
const { __commands: commands, __queries: queries, __mockSdk: sdk, __commit: commitFn } = appExport as any;

async function invokeCommand(nsid: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
  const handler = commands.get(nsid);
  if (!handler) throw new Error(`Command not found: ${nsid}`);
  return JSON.parse(await handler(sdk, JSON.stringify(params)));
}

async function invokeQuery(nsid: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
  const handler = queries.get(nsid);
  if (!handler) throw new Error(`Query not found: ${nsid}`);
  return JSON.parse(await handler(sdk, JSON.stringify(params)));
}

describe("OS Messaging Gateway — Integration Tests", () => {
  beforeEach(() => { writtenRecords = []; postedTexts = []; });

  it("registers 7 commands and 1 query", () => {
    expect(commands.size).toBe(7);
    expect(queries.size).toBe(1);
  });

  // ── Discord ──

  describe("Discord webhook", () => {
    it("dispatches a Discord message", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookDiscord", {
        t: "MESSAGE_CREATE",
        d: { content: "新幹線を予約して", channel_id: "ch-123", author: { id: "user-456" } },
      });
      expect(result.status).toBe("dispatched");
      const inbound = writtenRecords.find(r => r.collection === "com.etzhayyim.apps.osMessaging.inbound");
      expect(inbound).toBeDefined();
      expect(inbound!.record.platform).toBe("discord");
      expect(inbound!.record.text).toBe("新幹線を予約して");
    });

    it("responds to Discord PING", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookDiscord", { type: 1 });
      expect(result.type).toBe(1);
    });

    it("ignores empty Discord messages", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookDiscord", { d: {} });
      expect(result.status).toBe("ignored");
    });
  });

  // ── Telegram ──

  describe("Telegram webhook", () => {
    it("dispatches a Telegram message", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookTelegram", {
        message: { text: "東京から新大阪", chat: { id: 12345 }, from: { id: 67890 }, date: 1718000000 },
      });
      expect(result.status).toBe("dispatched");
      const inbound = writtenRecords.find(r => r.collection === "com.etzhayyim.apps.osMessaging.inbound");
      expect(inbound!.record.platform).toBe("telegram");
    });

    it("ignores non-text Telegram updates", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookTelegram", { update_id: 1 });
      expect(result.status).toBe("ignored");
    });
  });

  // ── Slack ──

  describe("Slack webhook", () => {
    it("responds to Slack URL verification", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookSlack", {
        type: "url_verification",
        challenge: "test-challenge-token",
      });
      expect(result.challenge).toBe("test-challenge-token");
    });

    it("dispatches a Slack message", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookSlack", {
        event: { type: "message", text: "予約確認", channel: "C123", user: "U456", ts: "1718000000.000" },
      });
      expect(result.status).toBe("dispatched");
    });

    it("ignores Slack bot messages (subtype)", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookSlack", {
        event: { type: "message", subtype: "bot_message", text: "bot reply", channel: "C123" },
      });
      expect(result.status).toBe("ignored");
    });
  });

  // ── LINE ──

  describe("LINE webhook", () => {
    it("dispatches a LINE message", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookLine", {
        events: [{
          type: "message",
          message: { type: "text", text: "明日の新幹線" },
          source: { userId: "U-line-001" },
          replyToken: "rt-abc",
          timestamp: 1718000000000,
        }],
      });
      expect(result.status).toBe("dispatched");
      const inbound = writtenRecords.find(r => r.collection === "com.etzhayyim.apps.osMessaging.inbound");
      expect(inbound!.record.platform).toBe("line");
    });
  });

  // ── WhatsApp ──

  describe("WhatsApp webhook", () => {
    it("dispatches a WhatsApp message", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.webhookWhatsapp", {
        entry: [{
          changes: [{
            value: {
              messages: [{ type: "text", from: "81901234567", text: { body: "のぞみ予約" }, timestamp: "1718000000" }],
            },
          }],
        }],
      });
      expect(result.status).toBe("dispatched");
      const inbound = writtenRecords.find(r => r.collection === "com.etzhayyim.apps.osMessaging.inbound");
      expect(inbound!.record.platform).toBe("whatsapp");
      expect(inbound!.record.text).toBe("のぞみ予約");
    });
  });

  // ── Platform connection ──

  describe("Platform connections", () => {
    it("connectPlatform writes mapping record", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.connectPlatform", {
        platform: "discord",
        platformUid: "user-456",
        etzhayyimDid: "did:web:gkgua2o1.etzhayyim.com",
      });
      expect(result.status).toBe("connected");
      const mapping = writtenRecords.find(r => r.collection === "com.etzhayyim.apps.osMessaging.platformMapping");
      expect(mapping).toBeDefined();
      expect(mapping!.record.etzhayyimDid).toBe("did:web:gkgua2o1.etzhayyim.com");
    });

    it("disconnectPlatform writes disconnect record", async () => {
      const result = await invokeCommand("com.etzhayyim.apps.osMessaging.disconnectPlatform", {
        platform: "telegram",
        platformUid: "67890",
      });
      expect(result.status).toBe("disconnected");
    });

    it("listConnections returns empty array", async () => {
      const result = await invokeQuery("com.etzhayyim.apps.osMessaging.listConnections", {});
      expect(result.connections).toBeDefined();
    });
  });
});
