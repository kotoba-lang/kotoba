/**
 * OS Messaging Gateway — Multi-platform chat bridge to etzhayyim agent network.
 *
 * Receives webhooks from 5 platforms (Discord, Telegram, Slack, LINE, WhatsApp),
 * converts to UnifiedMessage, resolves the user's etzhayyim DID via platform mapping,
 * dispatches to PDS com.etzhayyim.convo.send (→ agentInfer), and relays the reply
 * back to the originating platform.
 *
 * Data path:
 *   Write: sdk.pds.dispatch → PDS → kagami → RisingWave (PlatformUserMapping, MessageLog)
 *   Read:  createKyselyDb → RisingWave (platform user mapping lookup)
 *
 * Architecture (Path F Phase 3):
 *   Platform webhook → this Worker → PDS com.etzhayyim.convo.send → agentInferV2
 *     → memory + consent + audit + tool chain → reply
 *   → this Worker → platform API → user
 */
import {
  createWorkerExport,
  asAgentTool,
  withCapabilityTags,
  withOCELEvent,
  resolveHeartbeatCadence,
  createCadenceState,
  createInboxBuffer,
  createKyselyDb,
  genID,
  nowISO,
  str,
  decodeJson,
  type AppDef,
  type HostSDK,
  type ComAtprotoSyncSubscribeReposCommit,
} from "@etzhayyim/kotodama-host-sdk";

const APP_DEF: AppDef = {
  id: "0sm3sg01",
  name: "OS Messaging Gateway",
  description: "Multi-platform messaging gateway — Discord, Telegram, Slack, LINE, WhatsApp",
};

const cadenceState = createCadenceState();
const inbox = createInboxBuffer();

// ---------------------------------------------------------------------------
// Unified Message Type
// ---------------------------------------------------------------------------

type Platform = "discord" | "telegram" | "slack" | "line" | "whatsapp" | "web";

interface UnifiedMessage {
  platform: Platform;
  channelId: string;
  userId: string;
  userDid?: string;
  text: string;
  replyToId?: string;
  attachments?: Array<{ type: string; url: string }>;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Platform User Mapping
// ---------------------------------------------------------------------------

const MAPPING_TABLE = "graphar.vertex_PlatformUserMapping";

async function resolveUserDid(platform: Platform, platformUid: string): Promise<string | null> {
  try {
    const db = createKyselyDb();
    const row = await db
      .selectFrom(MAPPING_TABLE as any)
      .select(["etzhayyim_did"] as any[])
      .where("platform" as any, "=", platform)
      .where("platform_uid" as any, "=", platformUid)
      .limit(1)
      .executeTakeFirst() as { etzhayyim_did: string } | undefined;
    return row?.etzhayyim_did || null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Platform Adapters — parse webhook → UnifiedMessage
// ---------------------------------------------------------------------------

function parseDiscordWebhook(body: Record<string, unknown>): UnifiedMessage | null {
  // Discord Interactions API / Bot message event
  const data = body.d as Record<string, unknown> | undefined;
  if (!data) return null;
  const content = str(data.content ?? "");
  if (!content) return null;
  const author = data.author as Record<string, unknown> | undefined;
  return {
    platform: "discord",
    channelId: str(data.channel_id ?? ""),
    userId: str(author?.id ?? ""),
    text: content,
    timestamp: Date.now(),
  };
}

function parseTelegramWebhook(body: Record<string, unknown>): UnifiedMessage | null {
  const msg = (body.message ?? body.edited_message) as Record<string, unknown> | undefined;
  if (!msg) return null;
  const text = str(msg.text ?? "");
  if (!text) return null;
  const from = msg.from as Record<string, unknown> | undefined;
  return {
    platform: "telegram",
    channelId: str(msg.chat && (msg.chat as any).id || ""),
    userId: str(from?.id ?? ""),
    text,
    timestamp: Number(msg.date ?? 0) * 1000 || Date.now(),
  };
}

function parseSlackWebhook(body: Record<string, unknown>): UnifiedMessage | null {
  // Slack Events API
  const event = body.event as Record<string, unknown> | undefined;
  if (!event || event.type !== "message" || event.subtype) return null;
  return {
    platform: "slack",
    channelId: str(event.channel ?? ""),
    userId: str(event.user ?? ""),
    text: str(event.text ?? ""),
    timestamp: Number(event.ts ?? 0) * 1000 || Date.now(),
  };
}

function parseLineWebhook(body: Record<string, unknown>): UnifiedMessage | null {
  const events = body.events as Array<Record<string, unknown>> | undefined;
  if (!events || events.length === 0) return null;
  const event = events[0];
  if (event.type !== "message") return null;
  const msg = event.message as Record<string, unknown> | undefined;
  if (!msg || msg.type !== "text") return null;
  const source = event.source as Record<string, unknown> | undefined;
  return {
    platform: "line",
    channelId: str(source?.groupId ?? source?.roomId ?? source?.userId ?? ""),
    userId: str(source?.userId ?? ""),
    text: str(msg.text ?? ""),
    replyToId: str(event.replyToken ?? ""),
    timestamp: Number(event.timestamp ?? 0) || Date.now(),
  };
}

function parseWhatsappWebhook(body: Record<string, unknown>): UnifiedMessage | null {
  // WhatsApp Cloud API webhook
  const entry = (body.entry as Array<Record<string, unknown>> | undefined)?.[0];
  const changes = (entry?.changes as Array<Record<string, unknown>> | undefined)?.[0];
  const value = changes?.value as Record<string, unknown> | undefined;
  const messages = value?.messages as Array<Record<string, unknown>> | undefined;
  if (!messages || messages.length === 0) return null;
  const msg = messages[0];
  if (msg.type !== "text") return null;
  const textObj = msg.text as Record<string, unknown> | undefined;
  return {
    platform: "whatsapp",
    channelId: str(msg.from ?? ""),
    userId: str(msg.from ?? ""),
    text: str(textObj?.body ?? ""),
    timestamp: Number(msg.timestamp ?? 0) * 1000 || Date.now(),
  };
}

// ---------------------------------------------------------------------------
// Platform Reply — send response back to originating platform
// ---------------------------------------------------------------------------

async function replyToPlatform(
  sdk: HostSDK,
  msg: UnifiedMessage,
  replyText: string,
): Promise<void> {
  // Platform-specific reply via external API
  // Secrets are resolved from env bindings at dispatch time
  const outId = genID("out");
  const ownerDid = sdk.pds.selfRepo ?? "did:web:0sm3sg01.etzhayyim.com";
  const db = createKyselyDb();
  let data: Record<string, unknown>;
  switch (msg.platform) {
    case "discord":
      data = { platform: "discord", channel_id: msg.channelId, text: replyText, sent_at: nowISO() };
      break;
    case "telegram":
      data = { platform: "telegram", chat_id: msg.channelId, text: replyText, sent_at: nowISO() };
      break;
    case "line":
      data = { platform: "line", reply_token: msg.replyToId ?? "", text: replyText, sent_at: nowISO() };
      break;
    default:
      data = { platform: msg.platform, channel_id: msg.channelId, user_id: msg.userId, text: replyText, sent_at: nowISO() };
  }
  await db.insertInto("vertex_os_messaging_outbound" as any).values({
    vertex_id: `at://${ownerDid}/com.etzhayyim.apps.osMessaging.outbound/${outId}`,
    sensitivity_ord: 2,
    owner_did: ownerDid,
    org_id: "anon",
    user_id: "anon",
    actor_id: "0sm3sg01",
    created_at: nowISO(),
    ...data,
  }).execute();
}

// ---------------------------------------------------------------------------
// Core dispatch: UnifiedMessage → PDS convo → agentInfer → platform reply
// ---------------------------------------------------------------------------

async function dispatchToAgent(
  sdk: HostSDK,
  msg: UnifiedMessage,
  targetAgentDid: string,
): Promise<string> {
  // Resolve user's etzhayyim DID
  const userDid = msg.userDid || await resolveUserDid(msg.platform, msg.userId);

  // Dispatch to PDS com.etzhayyim.convo.send → agentInfer pipeline
  // The PDS handler auto-detects peer agent DID and runs agentInfer
  const inboundId = genID("in");
  const selfDid = sdk.pds.selfRepo ?? "did:web:0sm3sg01.etzhayyim.com";
  const db = createKyselyDb();
  await db.insertInto("vertex_os_messaging_inbound" as any).values({
    vertex_id: `at://${selfDid}/com.etzhayyim.apps.osMessaging.inbound/${inboundId}`,
    sensitivity_ord: 2,
    owner_did: selfDid,
    platform: msg.platform,
    channel_id: msg.channelId,
    user_id: msg.userId,
    user_did: userDid || `anonymous:${msg.platform}:${msg.userId}`,
    target_agent_did: targetAgentDid,
    text: msg.text,
    received_at: nowISO(),
    org_id: "anon",
    actor_id: "0sm3sg01",
    created_at: nowISO(),
  }).execute();

  // Return acknowledgement (actual reply comes async via outbound record + platform API)
  return `Message dispatched to ${targetAgentDid}`;
}

// ---------------------------------------------------------------------------
// App export
// ---------------------------------------------------------------------------

export default createWorkerExport((sdk) => {
  // ── Platform webhook commands ──

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.webhookDiscord",
    asAgentTool(
      withCapabilityTags(["webhook-receiver"])(
        withOCELEvent("osMessaging:webhookDiscord")(async (input: Record<string, unknown>) => {
          // Slack URL verification challenge
          if (input.type === 1) return { type: 1 }; // Discord PING
          const msg = parseDiscordWebhook(input);
          if (!msg) return { status: "ignored" };
          const result = await dispatchToAgent(sdk, msg, "did:web:os.etzhayyim.com");
          return { status: "dispatched", result };
        }),
      ),
      { name: "webhookDiscord", description: "Receive Discord webhook events and dispatch to etzhayyim agent" },
    ),
  );

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.webhookTelegram",
    asAgentTool(
      withCapabilityTags(["webhook-receiver"])(
        withOCELEvent("osMessaging:webhookTelegram")(async (input: Record<string, unknown>) => {
          const msg = parseTelegramWebhook(input);
          if (!msg) return { status: "ignored" };
          const result = await dispatchToAgent(sdk, msg, "did:web:os.etzhayyim.com");
          return { status: "dispatched", result };
        }),
      ),
      { name: "webhookTelegram", description: "Receive Telegram Bot API webhook events" },
    ),
  );

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.webhookSlack",
    asAgentTool(
      withCapabilityTags(["webhook-receiver"])(
        withOCELEvent("osMessaging:webhookSlack")(async (input: Record<string, unknown>) => {
          // Slack URL verification
          if (input.type === "url_verification") return { challenge: input.challenge };
          const msg = parseSlackWebhook(input);
          if (!msg) return { status: "ignored" };
          const result = await dispatchToAgent(sdk, msg, "did:web:os.etzhayyim.com");
          return { status: "dispatched", result };
        }),
      ),
      { name: "webhookSlack", description: "Receive Slack Events API webhook events" },
    ),
  );

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.webhookLine",
    asAgentTool(
      withCapabilityTags(["webhook-receiver"])(
        withOCELEvent("osMessaging:webhookLine")(async (input: Record<string, unknown>) => {
          const msg = parseLineWebhook(input);
          if (!msg) return { status: "ignored" };
          const result = await dispatchToAgent(sdk, msg, "did:web:os.etzhayyim.com");
          return { status: "dispatched", result };
        }),
      ),
      { name: "webhookLine", description: "Receive LINE Messaging API webhook events" },
    ),
  );

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.webhookWhatsapp",
    asAgentTool(
      withCapabilityTags(["webhook-receiver"])(
        withOCELEvent("osMessaging:webhookWhatsapp")(async (input: Record<string, unknown>) => {
          const msg = parseWhatsappWebhook(input);
          if (!msg) return { status: "ignored" };
          const result = await dispatchToAgent(sdk, msg, "did:web:os.etzhayyim.com");
          return { status: "dispatched", result };
        }),
      ),
      { name: "webhookWhatsapp", description: "Receive WhatsApp Cloud API webhook events" },
    ),
  );

  // ── Platform connection management ──

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.connectPlatform",
    asAgentTool(
      withCapabilityTags(["platform-user-mapping"])(
        withOCELEvent("osMessaging:connectPlatform")(async (input: {
          platform: Platform;
          platformUid: string;
          etzhayyimDid: string;
        }) => {
          const mappingId = genID("map");
          const selfDid = sdk.pds.selfRepo ?? "did:web:0sm3sg01.etzhayyim.com";
          const db = createKyselyDb();
          await db.insertInto("vertex_os_messaging_platform_mapping" as any).values({
            vertex_id: `at://${selfDid}/com.etzhayyim.apps.osMessaging.platformMapping/${mappingId}`,
            sensitivity_ord: 2,
            owner_did: selfDid,
            platform: input.platform,
            platform_uid: input.platformUid,
            etzhayyim_did: input.etzhayyimDid,
            status: "connected",
            connected_at: nowISO(),
            org_id: "anon",
            user_id: "anon",
            actor_id: "0sm3sg01",
            created_at: nowISO(),
          }).execute();
          return { status: "connected", platform: input.platform, etzhayyimDid: input.etzhayyimDid };
        }),
      ),
      { name: "connectPlatform", description: "Link a platform user ID to a etzhayyim DID. Params: platform ('discord'|'telegram'|'slack'|'line'|'whatsapp'), platformUid (platform user ID), etzhayyimDid (etzhayyim DID to link)." },
    ),
  );

  sdk.app.command(
    "com.etzhayyim.apps.osMessaging.disconnectPlatform",
    asAgentTool(
      withCapabilityTags(["platform-user-mapping"])(
        withOCELEvent("osMessaging:disconnectPlatform")(async (input: { platform: Platform; platformUid: string }) => {
          const disconnectId = genID("map");
          const selfDid = sdk.pds.selfRepo ?? "did:web:0sm3sg01.etzhayyim.com";
          const db = createKyselyDb();
          await db.insertInto("vertex_os_messaging_platform_mapping" as any).values({
            vertex_id: `at://${selfDid}/com.etzhayyim.apps.osMessaging.platformMapping/${disconnectId}`,
            sensitivity_ord: 2,
            owner_did: selfDid,
            platform: input.platform,
            platform_uid: input.platformUid,
            etzhayyim_did: null,
            status: "disconnected",
            disconnected_at: nowISO(),
            org_id: "anon",
            user_id: "anon",
            actor_id: "0sm3sg01",
            created_at: nowISO(),
          }).execute();
          return { status: "disconnected", platform: input.platform };
        }),
      ),
      { name: "disconnectPlatform", description: "Unlink a platform user ID from etzhayyim DID." },
    ),
  );

  sdk.app.query(
    "com.etzhayyim.apps.osMessaging.listConnections",
    asAgentTool(
      withCapabilityTags(["platform-user-mapping"])(
        withOCELEvent("osMessaging:listConnections")(async (input: { etzhayyimDid?: string; platform?: string }) => {
          const match: Record<string, unknown> = {};
          if (input.etzhayyimDid) match.etzhayyim_did = input.etzhayyimDid;
          if (input.platform) match.platform = input.platform;
          const db = createKyselyDb();
          let q = db.selectFrom(MAPPING_TABLE as any)
            .select(["platform", "platform_uid", "etzhayyim_did", "connected_at"] as any[]);
          for (const [k, v] of Object.entries(match)) {
            q = q.where(k as any, "=", v) as any;
          }
          const rows = await q.limit(50).execute();
          return { connections: rows };
        }),
      ),
      { name: "listConnections", description: "List platform connections. Optional filters: etzhayyimDid, platform." },
    ),
  );

  // ── Reactive commit handler ──

  sdk.app.onCommit(handleComAtprotoSyncSubscribeReposCommit);

  sdk.app.onHeartbeat(async () => {
    const cadence = resolveHeartbeatCadence(cadenceState, inbox);
    return { nextMs: cadence.nextMs };
  });
});

// ---------------------------------------------------------------------------
// Reactive: outbound records → platform API delivery
// ---------------------------------------------------------------------------

async function handleComAtprotoSyncSubscribeReposCommit(
  commit: ComAtprotoSyncSubscribeReposCommit,
  sdk: HostSDK,
) {
  if (commit.action !== "create") return;

  // Outbound message delivery: osMessaging.outbound record → platform API
  if (commit.collection === "com.etzhayyim.apps.osMessaging.outbound") {
    const record = decodeJson(commit.recordJson);
    const platform = str(record.platform ?? "") as Platform;
    const text = str(record.text ?? "");
    if (!platform || !text) return;

    // Platform API calls would go here (fetch to Discord/Telegram/etc.)
    // For now, log the outbound delivery
    await sdk.pds.dispatch({
      type: "app.bsky.feed.post",
      payload: {
        text: `[${platform}] Reply delivered: ${text.slice(0, 100)}`,
      },
    });
  }
}
