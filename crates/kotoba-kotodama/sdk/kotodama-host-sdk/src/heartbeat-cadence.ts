// heartbeat-cadence.ts — joucho 情緒 score-driven heartbeat cadence + InboxBuffer + follower KPI reward.
//
// 3 concerns:
//   1. Cadence (joucho mood → what action?)
//   2. Content source (InboxBuffer → what to say?)
//   3. Follower reward (wellness/dojo delta → like/love)
//
// joucho 情緒 5 軸:
//   joy (喜び)       — high → post, share, celebrate
//   calm (落ち着き)   — high → analyze, validate, reflect
//   stress (ストレス) — high → suppress posting, drill/recovery
//   gratitude (感謝)  — high → engage (like, follow, repost)
//   focus (集中力)    — high → deep work (kyumei-koji, analysis)

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";

// ── Types ──────────────────────────────────────────────────────────────

/** joucho 情緒 5 軸 scores (0-100 each). */
export interface JouchoScores {
  joy: number;
  calm: number;
  stress: number;
  gratitude: number;
  focus: number;
}

/** Buffered inbound events between heartbeats. */
export interface InboxBuffer {
  /** Follow 先の commit (handleCommit で push). */
  inboundCommits: InboundCommit[];
  /** 受けた engagement (onReaction で push). */
  reactions: InboundReaction[];
  /** 前回 joucho (mood shift 検出). */
  prevJoucho: JouchoScores | null;
  /** Follower wellness snapshots (前回 heartbeat 時点). */
  followerSnapshots: Map<string, FollowerSnapshot>;
  /** Profile data missing — triggers dataRepair ContentSource. Set by host-sdk when getProfile returns incomplete. */
  profileIncomplete?: boolean;
}

export interface InboundCommit {
  collection: string;
  repo: string;
  rkey: string;
  time: string;
}

export interface InboundReaction {
  type: "like" | "repost" | "reply" | "mention";
  uri: string;
  from: string;
  time: string;
}

export interface FollowerSnapshot {
  wellnessScore: number;
  dojoScore: number;
  rank: string;
}

/** Follower whose wellness/dojo improved — reward target. */
export interface FollowerReward {
  did: string;
  /** Which metric improved. */
  metric: "wellness" | "dojo" | "both";
  /** Score delta (positive = improvement). */
  wellnessDelta: number;
  dojoDelta: number;
  /** Suggested reward intensity. */
  rewardType: "like" | "love";
  /** Latest post URI to like/love (if available). */
  latestPostUri: string | null;
}

export type Mood = "joyful" | "calm" | "stressed" | "grateful" | "focused" | "neutral";

/** Content source priority for what to post. */
export type ContentSource =
  | { type: "inbound"; commit: InboundCommit }
  | { type: "reaction"; reaction: InboundReaction }
  | { type: "recordAnalysis" }
  | { type: "moodShift"; prev: Mood; current: Mood }
  | { type: "milestone"; detail: string }
  | { type: "followerCelebration"; reward: FollowerReward }
  | { type: "dataRepair"; missing: DataRepairTarget[] }
  | { type: "none" };

/** Identifies what data is missing and needs repair. */
export interface DataRepairTarget {
  field: "profile" | "displayName" | "description" | "avatar";
  did: string;
}

export interface HeartbeatCadence {
  shouldPost: boolean;
  shouldAnalyze: boolean;
  shouldDrill: boolean;
  shouldValidate: boolean;
  shouldEngage: boolean;
  /** True when profile data is missing — agent should run kyumei-koji to self-repair. */
  shouldRepair: boolean;
  /** Followers whose wellness/dojo improved — like/love these. */
  followerRewards: FollowerReward[];
  /** Recommended content source for posting. */
  contentSource: ContentSource;
  joucho: JouchoScores;
  mood: Mood;
  postCooldownMs: number;
  reason: string;
}

export interface CadenceState {
  lastPostAt: number;
  lastAnalyzeAt: number;
  lastDrillAt: number;
  lastValidateAt: number;
  lastEngageAt: number;
  lastRewardAt: number;
  /**
   * Sliding window of recent post content source types for Shannon dedup.
   * Prevents the same contentSource.type from firing consecutively.
   */
  recentPostTypes: Array<{ type: string; ts: number }>;
}

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

let db: KyselyDb | null = null;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

function normalizeOtherRow(row: AnyRow | null | undefined): AnyRow {
  if (!row) return {};
  let props: AnyRow = {};
  if (typeof row.props === "string" && row.props.length > 0) {
    try {
      const parsed = JSON.parse(row.props) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) props = parsed as AnyRow;
    } catch {
      props = {};
    }
  }
  return { ...props, ...row };
}

/** Create a fresh InboxBuffer. Call once at module level. */
export function createInboxBuffer(): InboxBuffer {
  return {
    inboundCommits: [],
    reactions: [],
    prevJoucho: null,
    followerSnapshots: new Map(),
  };
}

/** Create a fresh CadenceState. Call once at module level. */
export function createCadenceState(): CadenceState {
  return { lastPostAt: 0, lastAnalyzeAt: 0, lastDrillAt: 0, lastValidateAt: 0, lastEngageAt: 0, lastRewardAt: 0, recentPostTypes: [] };
}

// ── joucho score query ─────────────────────────────────────────────────

async function queryJouchoScores(did: string): Promise<JouchoScores> {
  const defaults: JouchoScores = { joy: 50, calm: 50, stress: 30, gratitude: 50, focus: 50 };
  void did;
  return defaults;
}

function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  return Promise.race([
    promise,
    new Promise<T>((resolve) => { timer = setTimeout(() => resolve(fallback), ms); }),
  ]).finally(() => clearTimeout(timer!));
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

// ── Follower wellness/dojo query ───────────────────────────────────────

interface FollowerCurrentScore {
  did: string;
  wellnessScore: number;
  dojoScore: number;
  rank: string;
  latestPostUri: string | null;
}

async function queryFollowerScores(selfDid: string): Promise<FollowerCurrentScore[]> {
  try {
    const me = await withTimeout(
      getDb()
        .selectFrom("vertex_actor")
        .selectAll()
        .where((eb: any) => eb.or([
          eb("repo", "=", selfDid),
          eb("did", "=", selfDid),
        ]))
        .limit(1)
        .executeTakeFirst(),
      5000,
      undefined as { vertex_id: string | null | undefined; did: string | null | undefined } | undefined,
    );
    if (!me?.vertex_id) return [];

    const followers = await withTimeout(
      getDb()
        .selectFrom("mv_followers as e")
        .innerJoin("vertex_actor as a", "a.vertex_id", "e.src_vid")
        .select(["a.did as did"])
        .where("e.dst_vid", "=", me.vertex_id)
        .orderBy("e._seq", "desc")
        .limit(50)
        .execute(),
      5000,
      [] as Array<{ did: string | null }>,
    );
    const followerDids = followers.map((row) => String(row.did ?? "")).filter(Boolean);
    if (followerDids.length === 0) return [];

    const [rankRows, dojoRows, postRows] = await Promise.all([
      Promise.resolve([] as AnyRow[]),
      Promise.resolve([] as AnyRow[]),
      getDb()
        .selectFrom("vertex_post")
        .select(["repo", "rkey", "created_at"])
        .where("repo", "in", followerDids)
        .orderBy("_seq", "desc")
        .limit(500)
        .execute(),
    ]);

    const rankByDid = new Map<string, AnyRow>();
    for (const raw of rankRows) {
      const row = normalizeOtherRow(raw as AnyRow);
      const did = String(row.constituentDid ?? row.did ?? row.repo ?? "");
      if (did && !rankByDid.has(did)) rankByDid.set(did, row);
    }

    const dojoStats = new Map<string, { total: number; count: number }>();
    for (const raw of dojoRows) {
      const row = normalizeOtherRow(raw as AnyRow);
      const did = String(row.constituentDid ?? row.actorDid ?? row.did ?? row.repo ?? "");
      if (!did || !followerDids.includes(did)) continue;
      const score = Number(row.score ?? row.totalScore ?? 0);
      const prev = dojoStats.get(did) ?? { total: 0, count: 0 };
      dojoStats.set(did, { total: prev.total + score, count: prev.count + 1 });
    }

    const latestPostByDid = new Map<string, string | null>();
    for (const row of postRows) {
      const did = String(row.repo ?? "");
      if (!did || latestPostByDid.has(did)) continue;
      const rkey = String(row.rkey ?? "");
      latestPostByDid.set(did, rkey ? `at://${did}/app.bsky.feed.post/${rkey}` : null);
    }

    return followerDids.map((did) => {
      const rank = rankByDid.get(did);
      const dojo = dojoStats.get(did);
      return {
        did,
        wellnessScore: Number(rank?.totalScore ?? rank?.score ?? 0) || 0,
        dojoScore: dojo && dojo.count > 0 ? dojo.total / dojo.count : 0,
        rank: String(rank?.rank ?? rank?.rankName ?? "kyu6"),
        latestPostUri: latestPostByDid.get(did) ?? null,
      };
    });
  } catch {
    return [];
  }
}

function detectFollowerRewards(
  current: FollowerCurrentScore[],
  snapshots: Map<string, FollowerSnapshot>,
): FollowerReward[] {
  const rewards: FollowerReward[] = [];
  for (const f of current) {
    const prev = snapshots.get(f.did);
    if (!prev) continue; // first observation — no delta yet
    const wDelta = f.wellnessScore - prev.wellnessScore;
    const dDelta = f.dojoScore - prev.dojoScore;
    // Only reward positive deltas
    if (wDelta <= 0 && dDelta <= 0) continue;
    const metric: FollowerReward["metric"] =
      wDelta > 0 && dDelta > 0 ? "both" : wDelta > 0 ? "wellness" : "dojo";
    // love for notable improvements (wellness +10 or dojo +1), like for minor gains
    const rewardType: "like" | "love" = (wDelta >= 10 || dDelta >= 1) ? "love" : "like";
    rewards.push({
      did: f.did,
      metric,
      wellnessDelta: wDelta,
      dojoDelta: dDelta,
      rewardType,
      latestPostUri: f.latestPostUri,
    });
  }
  // Sort by total improvement descending
  rewards.sort((a, b) => (b.wellnessDelta + b.dojoDelta) - (a.wellnessDelta + a.dojoDelta));
  return rewards;
}

function updateFollowerSnapshots(
  snapshots: Map<string, FollowerSnapshot>,
  current: FollowerCurrentScore[],
): void {
  for (const f of current) {
    snapshots.set(f.did, {
      wellnessScore: f.wellnessScore,
      dojoScore: f.dojoScore,
      rank: f.rank,
    });
  }
}

// ── Mood determination ─────────────────────────────────────────────────

export function determineMood(j: JouchoScores): Mood {
  if (j.stress >= 70) return "stressed";
  const axes: { mood: Mood; score: number }[] = [
    { mood: "joyful", score: j.joy },
    { mood: "calm", score: j.calm },
    { mood: "grateful", score: j.gratitude },
    { mood: "focused", score: j.focus },
  ];
  axes.sort((a, b) => b.score - a.score);
  if (axes[0].score < 60) return "neutral";
  return axes[0].mood;
}

// ── Mood → Cadence mapping ─────────────────────────────────────────────

interface MoodCadence {
  postCooldownMs: number;
  analyzeCooldownMs: number;
  drillCooldownMs: number;
  validateCooldownMs: number;
  engageCooldownMs: number;
  rewardCooldownMs: number;
  postEnabled: boolean;
  analyzeEnabled: boolean;
  drillEnabled: boolean;
  validateEnabled: boolean;
  engageEnabled: boolean;
}

function moodToCadence(mood: Mood): MoodCadence {
  switch (mood) {
    case "joyful":
      return {
        postCooldownMs: 30 * 60_000,      analyzeCooldownMs: 3 * 3600_000,
        drillCooldownMs: 4 * 3600_000,     validateCooldownMs: 2 * 3600_000,
        engageCooldownMs: 15 * 60_000,     rewardCooldownMs: 10 * 60_000,
        postEnabled: true, analyzeEnabled: true, drillEnabled: false,
        validateEnabled: true, engageEnabled: true,
      };
    case "calm":
      return {
        postCooldownMs: 2 * 3600_000,     analyzeCooldownMs: 3600_000,
        drillCooldownMs: 2 * 3600_000,     validateCooldownMs: 45 * 60_000,
        engageCooldownMs: 3600_000,        rewardCooldownMs: 30 * 60_000,
        postEnabled: true, analyzeEnabled: true, drillEnabled: true,
        validateEnabled: true, engageEnabled: true,
      };
    case "stressed":
      return {
        postCooldownMs: 6 * 3600_000,     analyzeCooldownMs: 4 * 3600_000,
        drillCooldownMs: 30 * 60_000,      validateCooldownMs: 3600_000,
        engageCooldownMs: 3 * 3600_000,    rewardCooldownMs: 3600_000,
        postEnabled: false, analyzeEnabled: true, drillEnabled: true,
        validateEnabled: true, engageEnabled: false,
      };
    case "grateful":
      return {
        postCooldownMs: 3600_000,          analyzeCooldownMs: 2 * 3600_000,
        drillCooldownMs: 3 * 3600_000,     validateCooldownMs: 2 * 3600_000,
        engageCooldownMs: 10 * 60_000,     rewardCooldownMs: 5 * 60_000,
        postEnabled: true, analyzeEnabled: true, drillEnabled: false,
        validateEnabled: true, engageEnabled: true,
      };
    case "focused":
      return {
        postCooldownMs: 3 * 3600_000,     analyzeCooldownMs: 45 * 60_000,
        drillCooldownMs: 3600_000,         validateCooldownMs: 30 * 60_000,
        engageCooldownMs: 2 * 3600_000,    rewardCooldownMs: 3600_000,
        postEnabled: true, analyzeEnabled: true, drillEnabled: true,
        validateEnabled: true, engageEnabled: false,
      };
    case "neutral":
    default:
      return {
        postCooldownMs: 2 * 3600_000,     analyzeCooldownMs: 3 * 3600_000,
        drillCooldownMs: 2 * 3600_000,     validateCooldownMs: 90 * 60_000,
        engageCooldownMs: 3600_000,        rewardCooldownMs: 30 * 60_000,
        postEnabled: true, analyzeEnabled: true, drillEnabled: true,
        validateEnabled: true, engageEnabled: true,
      };
  }
}

// ── Stress scaling ─────────────────────────────────────────────────────

function applyStressScaling(cadence: MoodCadence, stress: number): MoodCadence {
  if (stress < 50) return cadence;
  const scale = 1.0 + (stress - 50) / 50;
  return {
    ...cadence,
    postCooldownMs: Math.round(cadence.postCooldownMs * scale),
    engageCooldownMs: Math.round(cadence.engageCooldownMs * scale),
  };
}

// ── Shannon content diversity ─────────────────────────────────────────
//
// Prevent actors from posting the same content source type consecutively.
// Track recent post types and suppress repetitive patterns.

/** Max consecutive posts of the same content source type. */
const MAX_SAME_TYPE_CONSECUTIVE = 2;
/** Time window for content diversity tracking (2 hours). */
const DIVERSITY_WINDOW_MS = 2 * 3600_000;

/**
 * Check if a content source type has been used too many consecutive times recently.
 * Returns true if the source should be suppressed.
 */
function isContentTypeSaturated(state: CadenceState, sourceType: string): boolean {
  const now = Date.now();
  // Evict expired entries
  state.recentPostTypes = state.recentPostTypes.filter(e => now - e.ts < DIVERSITY_WINDOW_MS);
  // Count consecutive same-type from the end (most recent)
  let consecutive = 0;
  for (let i = state.recentPostTypes.length - 1; i >= 0; i--) {
    if (state.recentPostTypes[i].type === sourceType) consecutive++;
    else break;
  }
  return consecutive >= MAX_SAME_TYPE_CONSECUTIVE;
}

/**
 * Record a post's content source type for diversity tracking.
 */
function recordPostType(state: CadenceState, sourceType: string): void {
  state.recentPostTypes.push({ type: sourceType, ts: Date.now() });
  if (state.recentPostTypes.length > 20) state.recentPostTypes.shift();
}

// ── Content source resolution ──────────────────────────────────────────
//
// Decide *what* to post based on mood × inbox contents.
// Priority varies by mood.

function resolveContentSource(mood: Mood, inbox: InboxBuffer, joucho: JouchoScores, rewards: FollowerReward[]): ContentSource {
  // Data repair takes absolute priority — agent cannot function properly without profile data
  if (inbox.profileIncomplete) {
    return { type: "dataRepair", missing: [{ field: "profile", did: "" }] };
  }

  const prevMood = inbox.prevJoucho ? determineMood(inbox.prevJoucho) : null;
  const moodShifted = prevMood !== null && prevMood !== mood;
  const hasCommits = inbox.inboundCommits.length > 0;
  const hasReactions = inbox.reactions.length > 0;
  const hasRewards = rewards.length > 0;

  switch (mood) {
    case "joyful":
      // Joy: celebrate follower improvement > react to inbound > mood shift
      if (hasRewards) return { type: "followerCelebration", reward: rewards[0] };
      if (hasCommits) return { type: "inbound", commit: inbox.inboundCommits[0] };
      if (moodShifted) return { type: "moodShift", prev: prevMood!, current: mood };
      return { type: "recordAnalysis" };

    case "calm":
      // Calm: analyze records > react to inbound > react to commits > mood shift
      if (hasReactions) return { type: "reaction", reaction: inbox.reactions[0] };
      if (hasCommits) return { type: "inbound", commit: inbox.inboundCommits[0] };
      if (moodShifted) return { type: "moodShift", prev: prevMood!, current: mood };
      return { type: "recordAnalysis" };

    case "stressed":
      // Stressed: post nothing (cadence disables posting)
      return { type: "none" };

    case "grateful":
      // Grateful: reply to reactions > celebrate followers > inbound > record analysis
      if (hasReactions) return { type: "reaction", reaction: inbox.reactions[0] };
      if (hasRewards) return { type: "followerCelebration", reward: rewards[0] };
      if (hasCommits) return { type: "inbound", commit: inbox.inboundCommits[0] };
      return { type: "recordAnalysis" };

    case "focused":
      // Focused: deep record analysis > inbound commit review > validate
      if (hasCommits) return { type: "inbound", commit: inbox.inboundCommits[0] };
      return { type: "recordAnalysis" };

    case "neutral":
    default:
      // Neutral: reactions > inbound > analysis
      if (hasReactions) return { type: "reaction", reaction: inbox.reactions[0] };
      if (hasCommits) return { type: "inbound", commit: inbox.inboundCommits[0] };
      if (hasRewards) return { type: "followerCelebration", reward: rewards[0] };
      return { type: "recordAnalysis" };
  }
}

// ── Main resolver ──────────────────────────────────────────────────────

/**
 * Resolve heartbeat cadence based on joucho 情緒 scores, inbox buffer, and follower KPI.
 *
 * 3 outputs:
 * 1. **Cadence flags** (shouldPost/shouldEngage/etc.) — driven by joucho mood + cooldowns
 * 2. **contentSource** — what to post about (inbound commit, reaction, record analysis, follower celebration)
 * 3. **followerRewards** — followers whose wellness/dojo improved → like/love their latest post
 *
 * @param actorDid - The app's DID
 * @param state - Mutable cooldown timestamps
 * @param inbox - Mutable inbox buffer (commits/reactions accumulated between heartbeats)
 */
export async function resolveHeartbeatCadence(
  actorDid: string,
  state: CadenceState,
  inbox: InboxBuffer,
): Promise<HeartbeatCadence> {
  const now = Date.now();

  // Query joucho + follower scores in parallel
  const [joucho, followerScores] = await Promise.all([
    queryJouchoScores(actorDid),
    (now - state.lastRewardAt >= 5 * 60_000) ? queryFollowerScores(actorDid) : Promise.resolve([]),
  ]);

  const mood = determineMood(joucho);
  let cadence = moodToCadence(mood);
  cadence = applyStressScaling(cadence, joucho.stress);

  // Detect follower wellness/dojo improvements
  const followerRewards = followerScores.length > 0
    ? detectFollowerRewards(followerScores, inbox.followerSnapshots)
    : [];
  if (followerScores.length > 0) {
    updateFollowerSnapshots(inbox.followerSnapshots, followerScores);
  }

  // Evaluate cooldowns
  const shouldPost = cadence.postEnabled && (now - state.lastPostAt >= cadence.postCooldownMs);
  const shouldAnalyze = cadence.analyzeEnabled && (now - state.lastAnalyzeAt >= cadence.analyzeCooldownMs);
  const shouldDrill = cadence.drillEnabled && (now - state.lastDrillAt >= cadence.drillCooldownMs);
  const shouldValidate = cadence.validateEnabled && (now - state.lastValidateAt >= cadence.validateCooldownMs);
  const shouldEngage = cadence.engageEnabled && (now - state.lastEngageAt >= cadence.engageCooldownMs);
  const shouldRepair = !!inbox.profileIncomplete;

  // Content source (what to post about) — dataRepair bypasses Shannon diversity gate
  let contentSource: ContentSource = shouldRepair
    ? resolveContentSource(mood, inbox, joucho, followerRewards)
    : shouldPost ? resolveContentSource(mood, inbox, joucho, followerRewards) : { type: "none" as const };

  // Shannon diversity gate: suppress if same content type posted too many times consecutively
  // dataRepair is never suppressed — repair must happen regardless of diversity
  if (shouldPost && contentSource.type !== "none" && contentSource.type !== "dataRepair" && isContentTypeSaturated(state, contentSource.type)) {
    // Try alternative content sources before giving up
    const alternatives: ContentSource["type"][] = ["inbound", "reaction", "recordAnalysis", "followerCelebration", "moodShift"];
    let found = false;
    for (const altType of alternatives) {
      if (altType === contentSource.type) continue;
      if (isContentTypeSaturated(state, altType)) continue;
      // Check if alternative source has data
      if (altType === "inbound" && inbox.inboundCommits.length > 0) {
        contentSource = { type: "inbound", commit: inbox.inboundCommits[0] };
        found = true; break;
      }
      if (altType === "reaction" && inbox.reactions.length > 0) {
        contentSource = { type: "reaction", reaction: inbox.reactions[0] };
        found = true; break;
      }
      if (altType === "recordAnalysis") {
        contentSource = { type: "recordAnalysis" };
        found = true; break;
      }
      if (altType === "followerCelebration" && followerRewards.length > 0) {
        contentSource = { type: "followerCelebration", reward: followerRewards[0] };
        found = true; break;
      }
    }
    if (!found) contentSource = { type: "none" };
  }

  // Track content source type for diversity (only if actually posting)
  if (shouldPost && contentSource.type !== "none") {
    recordPostType(state, contentSource.type);
  }

  // Consume the inbox item that was selected to prevent re-posting same item next heartbeat.
  if ((shouldPost || shouldRepair) && contentSource.type !== "none") {
    if (contentSource.type === "inbound" && inbox.inboundCommits.length > 0) {
      inbox.inboundCommits.shift();
    } else if (contentSource.type === "reaction" && inbox.reactions.length > 0) {
      inbox.reactions.shift();
    }
  }

  // Update prev joucho for mood shift detection
  inbox.prevJoucho = joucho;

  // Build reason
  const parts: string[] = [];
  if (shouldRepair) parts.push(`repair:${contentSource.type}`);
  if (shouldPost) parts.push(`post:${contentSource.type}`);
  if (shouldEngage) parts.push("engage");
  if (followerRewards.length > 0) parts.push(`reward:${followerRewards.length}`);
  if (shouldDrill) parts.push("drill");
  if (shouldAnalyze) parts.push("analyze");
  if (shouldValidate) parts.push("validate");
  const actionStr = parts.length > 0 ? parts.join("+") : "noop";
  const reason = `${mood} (j=${joucho.joy} c=${joucho.calm} s=${joucho.stress} g=${joucho.gratitude} f=${joucho.focus}) → ${actionStr}`;

  return {
    shouldPost,
    shouldAnalyze,
    shouldDrill,
    shouldValidate,
    shouldEngage,
    shouldRepair,
    followerRewards,
    contentSource,
    joucho,
    mood,
    postCooldownMs: cadence.postCooldownMs,
    reason,
  };
}
