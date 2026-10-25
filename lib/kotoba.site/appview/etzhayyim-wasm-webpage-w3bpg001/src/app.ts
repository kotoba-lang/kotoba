import {
  agentConverseAsync,
  asAgentTool,
  createWorkerExport,
  createKyselyDb,
  decodeJson,
  encodeJson,
  nowISO,
  str,
  stripHTML,
  withCapabilityTags,
  type ComAtprotoSyncSubscribeReposCommit,
  type HostSDK,
  truncateText,
  resolveHeartbeatCadence, createCadenceState, createInboxBuffer, llmAsk, genID, resolveModelId,
  nsid,
  parseLexiconInput,
} from "@etzhayyim/kotodama-host-sdk";

const cadenceState = createCadenceState();
const inbox = createInboxBuffer();

let appId = ""
const getDb = () => createKyselyDb();

// Graph reads (Kysely + Hyperdrive; replaces archived SQL 2026-04-14).
// Available vertex tables: vertex_page, vertex_wet_chunk, vertex_frontier, vertex_ivf_centroid,
// vertex_collection_job, vertex_wat, vertex_screenshot. Tables NOT in @etzhayyim/graph-schema:
// vertex_web_domain, vertex_web_topic, vertex_crawl_session, vertex_robots_txt, vertex_wpg_wet.
// Sites targeting those return [] / 0 with TODO until schema migration lands; writes still flow via PDS.

/**
 * IVF vector search on WetChunk embeddings via murakumo embed-text + centroid lookup.
 * Returns top-K chunks ranked by cosine similarity to the query text.
 * Falls back to recent embedded chunks if embedding or centroid fetch fails.
 */
async function ivfSearchChunks(
  sdk: HostSDK,
  domain: string,
  queryText: string,
  topK: number = 10,
): Promise<{ chunks: Record<string, unknown>[]; method: string }> {
  // 1. Embed the query text via murakumo cross-actor invoke
  let queryVec: number[] | null = null;
  try {
    const embedResult = await sdk.pds.invoke("did:web:murakumo.etzhayyim.com", "embed-text", {
      text: queryText, model: resolveModelId("qwen3-vl-8b"),
    }) as Record<string, unknown>;
    const vec = embedResult?.embedding ?? embedResult?.vector;
    if (Array.isArray(vec) && vec.length > 0) queryVec = vec as number[];
  } catch { /* murakumo unavailable — fallback to recent */ }

  const db = createKyselyDb();
  if (!queryVec) {
    // Fallback: return recent embedded chunks (no keyword filter)
    // TODO(site): page_did not promoted on vertex_wet_chunk — use page_rkey instead
    const recent = await db
      .selectFrom("vertex_wet_chunk")
      .select(["markdown", "url", "title", "section", "page_rkey as pageDid"])
      .where("domain", "=", domain)
      .where("embedding", "is not", null)
      .orderBy("crawled_at", "desc")
      .limit(topK)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);
    return { chunks: recent, method: recent.length > 0 ? "embedded:recent" : "none" };
  }

  // 2. Fetch centroids and find nearest clusters
  let centroidRows: Array<Record<string, unknown>>;
  try {
    centroidRows = await db
      .selectFrom("vertex_ivf_centroid")
      .select(["rkey", "embedding"])
      .limit(10000)
      .execute();
  } catch {
    centroidRows = [];
  }

  if (centroidRows.length === 0) {
    // No centroids: brute-force on domain-scoped embedded chunks
    // TODO(site): page_did not promoted on vertex_wet_chunk — use page_rkey instead
    const embedded = await db
      .selectFrom("vertex_wet_chunk")
      .select(["vertex_id as vid", "markdown", "url", "title", "section", "page_rkey as pageDid", "embedding"])
      .where("domain", "=", domain)
      .where("embedding", "is not", null)
      .orderBy("crawled_at", "desc")
      .limit(200)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);
    if (embedded.length === 0) return { chunks: [], method: "none" };

    // In-memory cosine similarity scoring
    const scored = embedded
      .filter(r => Array.isArray(r.embedding) && (r.embedding as number[]).length > 0)
      .map(r => {
        const emb = r.embedding as number[];
        let dot = 0, normA = 0, normB = 0;
        for (let i = 0; i < Math.min(queryVec!.length, emb.length); i++) {
          dot += queryVec![i] * emb[i];
          normA += queryVec![i] * queryVec![i];
          normB += emb[i] * emb[i];
        }
        const sim = normA > 0 && normB > 0 ? dot / (Math.sqrt(normA) * Math.sqrt(normB)) : 0;
        return { ...r, _score: sim };
      })
      .sort((a, b) => (b._score as number) - (a._score as number))
      .slice(0, topK);
    return { chunks: scored, method: "vector:brute" };
  }

  // Parse centroids and find nearest clusters
  const centroids = centroidRows
    .filter(r => Array.isArray(r.embedding) && (r.embedding as number[]).length > 0)
    .map(r => ({ clusterId: Number(r.rkey), vector: r.embedding as number[] }));

  const nProbe = Math.min(5, centroids.length);
  const clusterScores = centroids.map(c => {
    let dot = 0, normA = 0, normB = 0;
    for (let i = 0; i < Math.min(queryVec!.length, c.vector.length); i++) {
      dot += queryVec![i] * c.vector[i];
      normA += queryVec![i] * queryVec![i];
      normB += c.vector[i] * c.vector[i];
    }
    return { clusterId: c.clusterId, score: normA > 0 && normB > 0 ? dot / (Math.sqrt(normA) * Math.sqrt(normB)) : 0 };
  }).sort((a, b) => b.score - a.score);
  const clusterIds = clusterScores.slice(0, nProbe).map(s => s.clusterId);

  // 3. Fetch candidates by cluster IDs, scoped to domain
  // TODO(site): page_did not promoted on vertex_wet_chunk — use page_rkey instead
  const candidates = await db
    .selectFrom("vertex_wet_chunk")
    .select(["vertex_id as vid", "markdown", "url", "title", "section", "page_rkey as pageDid", "embedding"])
    .where("domain", "=", domain)
    .where("ivf_cluster_id", "in", clusterIds)
    .where("embedding", "is not", null)
    .limit(200)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>);

  if (candidates.length === 0) return { chunks: [], method: "none" };

  // 4. Re-rank by cosine similarity
  const ranked = candidates
    .filter(r => Array.isArray(r.embedding) && (r.embedding as number[]).length > 0)
    .map(r => {
      const emb = r.embedding as number[];
      let dot = 0, normA = 0, normB = 0;
      for (let i = 0; i < Math.min(queryVec!.length, emb.length); i++) {
        dot += queryVec![i] * emb[i];
        normA += queryVec![i] * queryVec![i];
        normB += emb[i] * emb[i];
      }
      const sim = normA > 0 && normB > 0 ? dot / (Math.sqrt(normA) * Math.sqrt(normB)) : 0;
      return { ...r, _score: sim };
    })
    .sort((a, b) => (b._score as number) - (a._score as number))
    .slice(0, topK);

  return { chunks: ranked, method: "vector:ivf" };
}

// --- Topic Coordinator DIDs ---

interface TopicCoordinator {
  slug: string;
  name: string;
  description: string;
  did: string;
  sources: string[];
}

const topicCoordinators: TopicCoordinator[] = [
  {
    slug: "jpClassics",
    name: "Japanese Classical Texts",
    description: "Public domain Japanese literature from Aozora Bunko and NDL digitized collections",
    did: `did:web:${appId}.etzhayyim.com:topic:jpClassics`,
    sources: ["aozora", "ndl", "wikisourceJa"],
  },
  {
    slug: "intlLiterature",
    name: "International Literature",
    description: "Public domain international literature from Project Gutenberg and Wikisource",
    did: `did:web:${appId}.etzhayyim.com:topic:intlLiterature`,
    sources: ["gutenberg", "wikisourceEn"],
  },
  {
    slug: "academic",
    name: "Academic & Reference Texts",
    description: "Academic texts, encyclopedic content, and reference material from open repositories",
    did: `did:web:${appId}.etzhayyim.com:topic:academic`,
    sources: ["wikisourceJa", "wikisourceEn", "ndl"],
  },
  {
    slug: "images",
    name: "Historical & Cultural Images",
    description: "Public domain images from ColBase, CODH, and NDL IIIF collections",
    did: `did:web:${appId}.etzhayyim.com:topic:images`,
    sources: ["colbase", "codh", "ndlIiif"],
  },
];

const topicBySlug = new Map<string, TopicCoordinator>();
for (const t of topicCoordinators) {
  topicBySlug.set(t.slug, t);
}

// --- Data Sources ---

interface DataSource {
  id: string;
  name: string;
  baseUrl: string;
  license: string;
  language: string;
  format: string;
  topics: string[];
}

const dataSources: DataSource[] = [
  { id: "aozora", name: "Aozora Bunko", baseUrl: "https://www.aozora.gr.jp/", license: "PD", language: "ja", format: "html", topics: ["jpClassics"] },
  { id: "ndl", name: "National Diet Library", baseUrl: "https://dl.ndl.go.jp/", license: "PD", language: "ja", format: "iiifOcr", topics: ["jpClassics", "academic"] },
  { id: "wikisourceJa", name: "Wikisource (Japanese)", baseUrl: "https://ja.wikisource.org/", license: "CC BY-SA", language: "ja", format: "mediawiki", topics: ["jpClassics", "academic"] },
  { id: "wikisourceEn", name: "Wikisource (English)", baseUrl: "https://en.wikisource.org/", license: "CC BY-SA", language: "en", format: "mediawiki", topics: ["intlLiterature", "academic"] },
  { id: "gutenberg", name: "Project Gutenberg", baseUrl: "https://www.gutenberg.org/", license: "PD", language: "en", format: "utf8_text", topics: ["intlLiterature"] },
  { id: "colbase", name: "ColBase (National Museum)", baseUrl: "https://colbase.nich.go.jp/", license: "PD", language: "ja", format: "iiifImage", topics: ["images"] },
  { id: "codh", name: "CODH Historical Characters", baseUrl: "http://codh.rois.ac.jp/", license: "CC BY-SA", language: "ja", format: "pngAnnotation", topics: ["images"] },
  { id: "ndlIiif", name: "NDL IIIF Collections", baseUrl: "https://dl.ndl.go.jp/api/iiif/", license: "PD", language: "ja", format: "iiifImage", topics: ["images"] },
];

const sourceById = new Map<string, DataSource>();
for (const s of dataSources) {
  sourceById.set(s.id, s);
}

// --- Helpers ---

function simpleCID(input: string): string {
  let h = BigInt(0);
  for (let i = 0; i < input.length; i++) {
    h = h * BigInt(31) + BigInt(input.charCodeAt(i));
    h = h & BigInt("0xFFFFFFFFFFFFFFFF");
  }
  return `cid-${h.toString(16)}`;
}

/** Post as a path-based DID via Bluesky Lexicon (fire-and-forget). */
function postAs(sdk: HostSDK, did: string, text: string, embed?: string): void {
  if (!did || !text) return;
  try {
    (sdk.hostImports as any).appBskyFeedPostAs?.(did, text, embed ?? "");
  } catch (e) { console.warn("postAs:", e); }
}

function ctxOrgUser(sdk: HostSDK): [string, string] {
  const orgId = str(sdk.hostImports.configGet("orgId") ?? "anon") || "anon";
  const userId = str(sdk.hostImports.configGet("userId") ?? "anon") || "anon";
  return [orgId, userId];
}

function parseTopicField(raw: unknown): string[] {
  const s = str(raw).trim();
  if (!s || s === "[]") return [];
  if (s.startsWith("[")) {
    try {
      const arr = JSON.parse(s);
      if (Array.isArray(arr)) return arr.map((v) => str(v).trim()).filter(Boolean);
    } catch {
      // fall through
    }
  }
  return s
    .split(/[,\n;|]/)
    .map((v) => v.trim().replace(/^["']|["']$/g, ""))
    .filter(Boolean);
}

function rowHasTopic(row: Record<string, unknown>, slug: string): boolean {
  const q = slug.trim().toLowerCase();
  if (!q) return true;
  return parseTopicField(row.topics).some((t) => t.toLowerCase() === q);
}

// --- Text Splitting (256-512 token paragraphs) ---

function estimateTokens(text: string): number {
  // Rough: 1 token ~ 3 chars for Japanese, 4 chars for English
  const jaChars = (text.match(/[\u3000-\u9fff\uf900-\ufaff]/g) || []).length;
  const otherChars = text.length - jaChars;
  return Math.ceil(jaChars / 3 + otherChars / 4);
}

function splitIntoParagraphs(text: string, minTokens: number, maxTokens: number): string[] {
  const paragraphs: string[] = [];
  const rawParagraphs = text.split(/\n\n+/).map(p => p.trim()).filter(p => p.length > 0);

  let currentChunk = "";
  for (const para of rawParagraphs) {
    const combined = currentChunk ? `${currentChunk}\n\n${para}` : para;
    const tokens = estimateTokens(combined);

    if (tokens > maxTokens && currentChunk) {
      paragraphs.push(currentChunk.trim());
      currentChunk = para;
    } else if (tokens > maxTokens && !currentChunk) {
      // Single paragraph exceeds max, split by sentences
      const sentences = para.split(/(?<=[。．.！？!?])\s*/);
      let sentChunk = "";
      for (const sent of sentences) {
        const sentCombined = sentChunk ? `${sentChunk}${sent}` : sent;
        if (estimateTokens(sentCombined) > maxTokens && sentChunk) {
          paragraphs.push(sentChunk.trim());
          sentChunk = sent;
        } else {
          sentChunk = sentCombined;
        }
      }
      if (sentChunk) currentChunk = sentChunk;
    } else if (tokens >= minTokens) {
      paragraphs.push(combined.trim());
      currentChunk = "";
    } else {
      currentChunk = combined;
    }
  }
  if (currentChunk && currentChunk.trim().length > 0) {
    paragraphs.push(currentChunk.trim());
  }
  return paragraphs;
}

// --- HTML → Markdown Converter (readability-lite + tag conversion) ---

function htmlToMarkdown(html: string): string {
  let h = html;
  // Strip non-content blocks
  h = h.replace(/<script[\s\S]*?<\/script>/gi, "");
  h = h.replace(/<style[\s\S]*?<\/style>/gi, "");
  h = h.replace(/<nav[\s\S]*?<\/nav>/gi, "");
  h = h.replace(/<footer[\s\S]*?<\/footer>/gi, "");
  h = h.replace(/<aside[\s\S]*?<\/aside>/gi, "");
  h = h.replace(/<header[\s\S]*?<\/header>/gi, "");
  h = h.replace(/<!--[\s\S]*?-->/g, "");

  // Try to extract main content area
  const mainMatch = h.match(/<(?:article|main)[^>]*>([\s\S]*?)<\/(?:article|main)>/i);
  if (mainMatch) h = mainMatch[1];

  // Headings
  h = h.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_, c) => `\n\n# ${stripTags(c).trim()}\n\n`);
  h = h.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_, c) => `\n\n## ${stripTags(c).trim()}\n\n`);
  h = h.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_, c) => `\n\n### ${stripTags(c).trim()}\n\n`);
  h = h.replace(/<h4[^>]*>([\s\S]*?)<\/h4>/gi, (_, c) => `\n\n#### ${stripTags(c).trim()}\n\n`);
  h = h.replace(/<h5[^>]*>([\s\S]*?)<\/h5>/gi, (_, c) => `\n\n##### ${stripTags(c).trim()}\n\n`);
  h = h.replace(/<h6[^>]*>([\s\S]*?)<\/h6>/gi, (_, c) => `\n\n###### ${stripTags(c).trim()}\n\n`);

  // Code blocks (before inline)
  h = h.replace(/<pre[^>]*><code[^>]*>([\s\S]*?)<\/code><\/pre>/gi, (_, c) => `\n\n\`\`\`\n${decodeEntities(c)}\n\`\`\`\n\n`);
  h = h.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, (_, c) => `\`${decodeEntities(c)}\``);

  // Blockquote
  h = h.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi, (_, c) => {
    const lines = stripTags(c).trim().split("\n").map((l: string) => `> ${l.trim()}`).join("\n");
    return `\n\n${lines}\n\n`;
  });

  // Links
  h = h.replace(/<a\s+[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, (_, href, text) => `[${stripTags(text).trim()}](${href})`);

  // Images
  h = h.replace(/<img\s+[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*\/?>/gi, (_, src, alt) => `![${alt}](${src})`);
  h = h.replace(/<img\s+[^>]*src="([^"]*)"[^>]*\/?>/gi, (_, src) => `![](${src})`);

  // Bold/italic
  h = h.replace(/<(?:strong|b)[^>]*>([\s\S]*?)<\/(?:strong|b)>/gi, (_, c) => `**${stripTags(c).trim()}**`);
  h = h.replace(/<(?:em|i)[^>]*>([\s\S]*?)<\/(?:em|i)>/gi, (_, c) => `*${stripTags(c).trim()}*`);

  // Lists
  h = h.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_, c) => `- ${stripTags(c).trim()}\n`);
  h = h.replace(/<\/?(?:ul|ol)[^>]*>/gi, "\n");

  // Table (simplified)
  h = h.replace(/<tr[^>]*>([\s\S]*?)<\/tr>/gi, (_, row) => {
    const cells = (row as string).match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi) ?? [];
    return "| " + cells.map((c: string) => stripTags(c).trim()).join(" | ") + " |\n";
  });
  h = h.replace(/<\/?(?:table|thead|tbody|tfoot)[^>]*>/gi, "\n");

  // Paragraphs and breaks
  h = h.replace(/<br\s*\/?>/gi, "\n");
  h = h.replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, (_, c) => `\n\n${stripTags(c).trim()}\n\n`);
  h = h.replace(/<div[^>]*>([\s\S]*?)<\/div>/gi, (_, c) => `\n${stripTags(c).trim()}\n`);

  // Strip remaining tags
  h = stripTags(h);
  h = decodeEntities(h);

  // Normalize whitespace
  h = h.replace(/\n{3,}/g, "\n\n").trim();
  return h;
}

function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, "");
}

function decodeEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

// --- HTML Metadata Extraction (for WAT records) ---

function extractHtmlMeta(html: string): {
  title: string; language: string; metaDescription: string;
  canonicalUrl: string; ogTitle: string; ogDescription: string; ogImage: string;
} {
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const langMatch = html.match(/<html[^>]*\slang="([^"]+)"/i);
  const descMatch = html.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/i)
    ?? html.match(/<meta[^>]*content="([^"]*)"[^>]*name="description"/i);
  const canonicalMatch = html.match(/<link[^>]*rel="canonical"[^>]*href="([^"]*)"/i);
  const ogTitleMatch = html.match(/<meta[^>]*property="og:title"[^>]*content="([^"]*)"/i);
  const ogDescMatch = html.match(/<meta[^>]*property="og:description"[^>]*content="([^"]*)"/i);
  const ogImageMatch = html.match(/<meta[^>]*property="og:image"[^>]*content="([^"]*)"/i);

  return {
    title: stripTags(titleMatch?.[1] ?? "").trim(),
    language: langMatch?.[1] ?? "",
    metaDescription: descMatch?.[1] ?? "",
    canonicalUrl: canonicalMatch?.[1] ?? "",
    ogTitle: ogTitleMatch?.[1] ?? "",
    ogDescription: ogDescMatch?.[1] ?? "",
    ogImage: ogImageMatch?.[1] ?? "",
  };
}

function extractOutlinks(html: string, baseUrl: string): { url: string; internal: boolean }[] {
  const links: { url: string; internal: boolean }[] = [];
  const seen = new Set<string>();
  let baseDomain: string;
  try { baseDomain = new URL(baseUrl).hostname; } catch { return links; }

  const regex = /<a\s+[^>]*href="([^"#][^"]*)"[^>]*>/gi;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(html)) !== null) {
    let href = match[1];
    if (href.startsWith("javascript:") || href.startsWith("mailto:")) continue;
    try {
      const resolved = new URL(href, baseUrl).href;
      if (seen.has(resolved)) continue;
      seen.add(resolved);
      const internal = new URL(resolved).hostname === baseDomain;
      links.push({ url: resolved, internal });
    } catch { /* skip invalid URLs */ }
  }
  return links;
}

// --- Robots.txt Parser ---

interface RobotsTxtRules {
  rules: { path: string; allow: boolean }[];
  crawlDelay: number;
  sitemapUrls: string[];
}

function parseRobotsTxt(text: string): RobotsTxtRules {
  const result: RobotsTxtRules = { rules: [], crawlDelay: 1, sitemapUrls: [] };
  let activeAgent = false;

  for (const line of text.split("\n")) {
    const trimmed = line.replace(/#.*$/, "").trim();
    if (!trimmed) continue;

    const [directive, ...valueParts] = trimmed.split(":");
    const value = valueParts.join(":").trim();
    const dir = directive.trim().toLowerCase();

    if (dir === "user-agent") {
      activeAgent = value === "*" || value.toLowerCase() === "etzhayyim-bot";
    } else if (activeAgent) {
      if (dir === "disallow" && value) {
        result.rules.push({ path: value, allow: false });
      } else if (dir === "allow" && value) {
        result.rules.push({ path: value, allow: true });
      } else if (dir === "crawl-delay") {
        result.crawlDelay = Math.max(1, parseInt(value, 10) || 1);
      }
    }
    if (dir === "sitemap" && value) {
      result.sitemapUrls.push(value);
    }
  }
  return result;
}

function isUrlAllowed(rules: RobotsTxtRules, path: string): boolean {
  let bestMatch = { length: 0, allow: true };
  for (const rule of rules.rules) {
    if (path.startsWith(rule.path) && rule.path.length > bestMatch.length) {
      bestMatch = { length: rule.path.length, allow: rule.allow };
    }
  }
  return bestMatch.allow;
}

// --- Topic Classification (general web categories) ---

const webTopicCoordinators: TopicCoordinator[] = [
  { slug: "technology", name: "Technology", description: "Software, hardware, and tech industry", did: `did:web:${appId}.etzhayyim.com:topic:technology`, sources: [] },
  { slug: "science", name: "Science & Research", description: "Scientific publications and research", did: `did:web:${appId}.etzhayyim.com:topic:science`, sources: [] },
  { slug: "business", name: "Business & Finance", description: "Business news, finance, and economics", did: `did:web:${appId}.etzhayyim.com:topic:business`, sources: [] },
  { slug: "government", name: "Government", description: "Government services and policy", did: `did:web:${appId}.etzhayyim.com:topic:government`, sources: [] },
  { slug: "education", name: "Education", description: "Educational institutions and learning", did: `did:web:${appId}.etzhayyim.com:topic:education`, sources: [] },
  { slug: "newsMedia", name: "News & Media", description: "News outlets and journalism", did: `did:web:${appId}.etzhayyim.com:topic:newsMedia`, sources: [] },
  { slug: "health", name: "Health & Medicine", description: "Healthcare and medical information", did: `did:web:${appId}.etzhayyim.com:topic:health`, sources: [] },
  { slug: "legal", name: "Legal & Regulatory", description: "Laws, regulations, and legal information", did: `did:web:${appId}.etzhayyim.com:topic:legal`, sources: [] },
  { slug: "culture", name: "Culture & Arts", description: "Art, music, literature, and cultural heritage", did: `did:web:${appId}.etzhayyim.com:topic:culture`, sources: [] },
  { slug: "commerce", name: "E-Commerce", description: "Online retail and product information", did: `did:web:${appId}.etzhayyim.com:topic:commerce`, sources: [] },
];

const allTopicCoordinators = [...topicCoordinators, ...webTopicCoordinators];
const allTopicBySlug = new Map<string, TopicCoordinator>();
for (const t of allTopicCoordinators) allTopicBySlug.set(t.slug, t);

function classifyTopics(url: string, title: string, text: string): string[] {
  const topics: string[] = [];
  let hostname = "";
  try { hostname = new URL(url).hostname; } catch { /* skip */ }

  // TLD heuristics
  if (/\.gov($|\.)/.test(hostname) || /\.go\.jp$/.test(hostname)) topics.push("government");
  if (/\.edu($|\.)/.test(hostname) || /\.ac\.jp$/.test(hostname)) topics.push("education");
  if (/\.mil($|\.)/.test(hostname)) topics.push("government");

  // Domain pattern matching
  const combined = `${title} ${text.slice(0, 2000)}`.toLowerCase();
  if (/\b(software|programming|api|developer|github|code|algorithm)\b/.test(combined)) topics.push("technology");
  if (/\b(research|study|journal|pubmed|arxiv|doi|abstract|methodology)\b/.test(combined)) topics.push("science");
  if (/\b(business|market|stock|finance|revenue|investor|economy)\b/.test(combined)) topics.push("business");
  if (/\b(health|medical|patient|clinical|diagnosis|treatment|drug)\b/.test(combined)) topics.push("health");
  if (/\b(law|legal|court|statute|regulation|compliance|attorney)\b/.test(combined)) topics.push("legal");
  if (/\b(news|breaking|reporter|journalist|headline|editorial)\b/.test(combined)) topics.push("newsMedia");
  if (/\b(art|museum|gallery|culture|heritage|music|film)\b/.test(combined)) topics.push("culture");
  if (/\b(shop|cart|price|buy|product|order|shipping)\b/.test(combined)) topics.push("commerce");

  // Deduplicate
  return [...new Set(topics.length > 0 ? topics : ["academic"])];
}

// --- Era Detection ---

function detectEra(text: string, language: string): string {
  if (language === "ja") {
    if (/平安|源氏|枕草子|古今和歌/.test(text)) return "heian";
    if (/鎌倉|方丈記|徒然草/.test(text)) return "kamakura";
    if (/室町|能楽|狂言/.test(text)) return "muromachi";
    if (/江戸|元禄|浮世/.test(text)) return "edo";
    if (/明治|大正|夏目|芥川/.test(text)) return "meijiTaisho";
    if (/昭和/.test(text)) return "showa";
    return "unknownJa";
  }
  if (/ancient|Homer|Plato|Aristotle|classical/i.test(text)) return "ancient";
  if (/medieval|Canterbury|Dante/i.test(text)) return "medieval";
  if (/Renaissance|Shakespeare|Cervantes/i.test(text)) return "renaissance";
  if (/Victorian|Dickens|Austen|Bronte/i.test(text)) return "19th_century";
  return "unknown";
}

// --- Topic Coordinator Registration ---

let topicsRegistered = false;

async function registerTopicCoordinators(sdk: HostSDK): Promise<void> {
  if (topicsRegistered) return;
  for (const topic of topicCoordinators) {
    const slug = `topic:${topic.slug}`;
    const did = str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
      displayName: topic.name,
      description: topic.description,
      category: "content",
    })));
    if (did) topic.did = did;

    try {
      await getDb().insertInto("vertex_web_topic" as any).values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.topic/${topic.slug}`,
        topic: topic.slug,
        slug: topic.slug,
        did: topic.did,
        name: topic.name,
        description: topic.description,
        source_count: topic.sources.length,
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      }).execute();
    } catch (e) { console.warn("vertex_web_topic insert:", e); }
  }
  topicsRegistered = true;
}

// --- Collection Job Creation ---

async function createCollectionJob(
  sdk: HostSDK,
  sourceId: string,
  sourceUrl: string,
  format: string,
  topics: string[],
  extra: Record<string, unknown> = {},
): Promise<string> {
  // Use URL-derived deterministic ID for dedup (same URL = same rkey = PDS upsert)
  const jobId = sourceUrl ? `cj-${simpleCID(sourceUrl)}` : genID("cj");
  const [orgId, userId] = ctxOrgUser(sdk);
  const source = sourceById.get(sourceId);

  const p = sdk.pds.comAtprotoRepoCreateRecord("collectionJob", {
    id: jobId,
    'sourceId': sourceId,
    'sourceName': source?.name ?? sourceId,
    'sourceUrl': sourceUrl,
    format,
    status: "pending",
    topics: JSON.stringify(topics),
    language: source?.language ?? "ja",
    license: source?.license ?? "unknown",
    'orgId': orgId,
    'userId': userId,
    'actorId': appId,
    'createdAt': nowISO(),
    ...extra,
  }).catch(e => console.warn("createCollectionJob:", e));
  sdk.pds.pendingWrites.push(p);

  return jobId;
}

// --- Commands: Collection Jobs ---

async function cmdFetchAozora(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.collectAozora", payload);
  const jobs: string[] = [];

  if (req.workId) {
    const url = `https://www.aozora.gr.jp/cards/${req.authorId ?? "000000"}/files/${req.workId}.html`;
    jobs.push(createCollectionJob(sdk, "aozora", url, "html", ["jpClassics"], {
      'authorId': req.authorId, 'workId': req.workId,
    }));
  } else {
    const seedUrls = [
      "https://www.aozora.gr.jp/cards/000148/files/773_14560.html",
      "https://www.aozora.gr.jp/cards/000035/files/1567_14913.html",
      "https://www.aozora.gr.jp/cards/000879/files/127_15260.html",
      "https://www.aozora.gr.jp/cards/000081/files/456_15050.html",
      "https://www.aozora.gr.jp/cards/000042/files/2275_13876.html",
    ];
    for (const url of seedUrls) {
      jobs.push(createCollectionJob(sdk, "aozora", url, "html", ["jpClassics"]));
    }
  }

  const text = `Collection jobs created for Aozora Bunko: ${jobs.length} works queued`;
  postAs(sdk, topicBySlug.get("jpClassics")?.did ?? "", text);

  return encodeJson({ status: "pending", 'jobCount': jobs.length, 'jobIds': jobs });
}

async function cmdFetchNdl(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.collectNdl", payload);
  const jobs: string[] = [];

  if (req.pid) {
    const url = `https://dl.ndl.go.jp/api/iiif/${req.pid}/manifest.json`;
    jobs.push(createCollectionJob(sdk, "ndl", url, "iiifOcr", ["jpClassics", "academic"], {
      pid: req.pid,
    }));
  } else {
    const seedPids = [
      "1311070",  // Kokinwakashu
      "1288353",  // Makura no Soshi
      "2533317",  // Tsurezuregusa
    ];
    for (const pid of seedPids) {
      const url = `https://dl.ndl.go.jp/api/iiif/${pid}/manifest.json`;
      jobs.push(createCollectionJob(sdk, "ndl", url, "iiifOcr", ["jpClassics", "academic"], { pid }));
    }
  }

  const topicDID = topicBySlug.get("jpClassics")?.did ?? "";
  await postAs(sdk, topicDID, `NDL collection jobs created: ${jobs.length} items queued for OCR extraction`);

  return encodeJson({ status: "pending", 'jobCount': jobs.length, 'jobIds': jobs });
}

async function cmdFetchWikisource(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.collectWikisource", payload);
  const lang = req.language ?? "ja";
  const jobs: string[] = [];

  if (req.title) {
    const base = lang === "ja" ? "https://ja.wikisource.org" : "https://en.wikisource.org";
    const url = `${base}/wiki/${encodeURIComponent(req.title)}`;
    const sourceId = lang === "ja" ? "wikisourceJa" : "wikisourceEn";
    const topics = lang === "ja" ? ["jpClassics", "academic"] : ["intlLiterature", "academic"];
    jobs.push(createCollectionJob(sdk, sourceId, url, "mediawiki", topics, { title: req.title }));
  } else {
    if (lang === "ja") {
      const titles = ["万葉集", "古事記", "竹取物語", "平家物語", "源氏物語"];
      for (const title of titles) {
        const url = `https://ja.wikisource.org/wiki/${encodeURIComponent(title)}`;
        jobs.push(createCollectionJob(sdk, "wikisourceJa", url, "mediawiki", ["jpClassics", "academic"], { title }));
      }
    } else {
      const titles = ["The_Republic_(Plato)", "Hamlet", "Pride_and_Prejudice", "Iliad", "Divine_Comedy"];
      for (const title of titles) {
        const url = `https://en.wikisource.org/wiki/${title}`;
        jobs.push(createCollectionJob(sdk, "wikisourceEn", url, "mediawiki", ["intlLiterature", "academic"], { title }));
      }
    }
  }

  const topicSlug = lang === "ja" ? "jpClassics" : "intlLiterature";
  const topicDID = topicBySlug.get(topicSlug)?.did ?? "";
  await postAs(sdk, topicDID, `Wikisource (${lang}) collection jobs: ${jobs.length} works queued`);

  return encodeJson({ status: "pending", 'jobCount': jobs.length, 'jobIds': jobs, language: lang });
}

async function cmdFetchGutenberg(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.collectGutenberg", payload);
  const jobs: string[] = [];

  if (req.bookId) {
    const url = `https://www.gutenberg.org/files/${req.bookId}/${req.bookId}-0.txt`;
    jobs.push(createCollectionJob(sdk, "gutenberg", url, "utf8_text", ["intlLiterature"], {
      'bookId': req.bookId,
    }));
  } else {
    const seeds = [
      { id: 1342, title: "Pride and Prejudice" },
      { id: 84, title: "Frankenstein" },
      { id: 1661, title: "Sherlock Holmes" },
      { id: 2701, title: "Moby Dick" },
      { id: 11, title: "Alice's Adventures in Wonderland" },
    ];
    for (const s of seeds) {
      const url = `https://www.gutenberg.org/files/${s.id}/${s.id}-0.txt`;
      jobs.push(createCollectionJob(sdk, "gutenberg", url, "utf8_text", ["intlLiterature"], {
        'bookId': s.id, title: s.title,
      }));
    }
  }

  const topicDID = topicBySlug.get("intlLiterature")?.did ?? "";
  await postAs(sdk, topicDID, `Project Gutenberg collection jobs: ${jobs.length} books queued`);

  return encodeJson({ status: "pending", 'jobCount': jobs.length, 'jobIds': jobs });
}

async function cmdFetchImages(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.collectImages", payload);
  const source = req.source ?? "colbase";
  const jobs: string[] = [];

  if (source === "colbase") {
    const seedCollections = [
      "https://colbase.nich.go.jp/api/v1/items?museum=tnm&category=painting&limit=10",
      "https://colbase.nich.go.jp/api/v1/items?museum=tnm&category=ukiyoe&limit=10",
      "https://colbase.nich.go.jp/api/v1/items?museum=tnm&category=calligraphy&limit=10",
    ];
    if (req.collectionId) {
      const url = `https://colbase.nich.go.jp/api/v1/items/${req.collectionId}`;
      jobs.push(createCollectionJob(sdk, "colbase", url, "iiifImage", ["images"], {
        'collectionId': req.collectionId,
      }));
    } else {
      for (const url of seedCollections) {
        jobs.push(createCollectionJob(sdk, "colbase", url, "iiifImage", ["images"]));
      }
    }
  } else if (source === "codh") {
    const seedUrls = [
      "http://codh.rois.ac.jp/char-shape/unicode/U+5B57/",
      "http://codh.rois.ac.jp/char-shape/unicode/U+6587/",
      "http://codh.rois.ac.jp/char-shape/unicode/U+672C/",
    ];
    if (req.query) {
      const codePoint = req.query.codePointAt(0)?.toString(16).toUpperCase() ?? "5B57";
      const url = `http://codh.rois.ac.jp/char-shape/unicode/U+${codePoint}/`;
      jobs.push(createCollectionJob(sdk, "codh", url, "pngAnnotation", ["images"], {
        query: req.query,
      }));
    } else {
      for (const url of seedUrls) {
        jobs.push(createCollectionJob(sdk, "codh", url, "pngAnnotation", ["images"]));
      }
    }
  } else if (source === "ndlIiif") {
    const seedManifests = [
      "https://dl.ndl.go.jp/api/iiif/1286847/manifest.json",
      "https://dl.ndl.go.jp/api/iiif/1287122/manifest.json",
    ];
    for (const url of seedManifests) {
      jobs.push(createCollectionJob(sdk, "ndlIiif", url, "iiifImage", ["images"]));
    }
  }

  const topicDID = topicBySlug.get("images")?.did ?? "";
  await postAs(sdk, topicDID, `Image collection jobs: ${jobs.length} items from ${source} queued`);

  return encodeJson({ status: "pending", 'jobCount': jobs.length, 'jobIds': jobs, source });
}

// --- Commands: Query ---

async function cmdListPages(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.listPages", payload);
  const limit = Math.min(Math.max(req.limit ?? 50, 1), 100);
  const offset = req.offset ?? 0;

  // TODO(site): topic / sourceId filters not in vertex_page promoted columns
  let qb = createKyselyDb().selectFrom("vertex_page").selectAll();
  if (req.language) qb = qb.where("language", "=", String(req.language));
  const rows = await qb.orderBy("created_date", "desc").offset(offset).limit(limit).execute()
    .catch(() => [] as Array<Record<string, unknown>>);
  return encodeJson({ pages: rows, total: rows.length, offset, limit });
}

async function cmdSearchSemantic(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = decodeJson(payload, {}) as Record<string, unknown>;
  const q = String(req.q ?? "");
  const domain = String(req.domain ?? "site.wet");
  const topK = Math.min(Math.max(Number(req.topK ?? 10), 1), 100);
  const nProbe = Math.min(Math.max(Number(req.nProbe ?? 8), 1), 64);
  const maxHops = Math.min(Math.max(Number(req.maxHops ?? 3), 1), 5);
  const skipNav = Boolean(req.skipNav ?? false);

  if (!q) return encodeJson({ error: "q is required" });

  const t0 = Date.now();

  // 1. Embed query text via murakumo
  let queryVec: number[] | null = null;
  try {
    const embedResult = await sdk.pds.invoke("did:web:murakumo.etzhayyim.com", "embed-text", {
      text: q, model: resolveModelId("qwen3-vl-8b"),
    }) as Record<string, unknown>;
    const vec = embedResult?.embedding ?? embedResult?.vector;
    if (Array.isArray(vec) && vec.length > 0) queryVec = vec as number[];
  } catch { /* murakumo unavailable */ }

  if (!queryVec) {
    // Fallback: IVF brute-force via existing ivfSearchChunks
    const fallback = await ivfSearchChunks(sdk, domain, q, topK);
    return encodeJson({
      query: q, domain,
      nav: null,
      hits: fallback.chunks.map((c) => ({
        chunkVertexId: String(c.vid ?? ""),
        domain: String(c.domain ?? domain),
        url: String(c.url ?? ""),
        title: String(c.title ?? ""),
        markdownPreview: String(c.markdown ?? "").slice(0, 400),
        score: Number(c._score ?? 0),
        clusterId: null,
      })),
      totalHits: fallback.chunks.length,
      method: fallback.method,
      latencyMs: Date.now() - t0,
    });
  }

  // 2. Corpus2Skill navigation (skip if no skill tree or skipNav=true)
  let navResult: Record<string, unknown> | null = null;
  let clusterFilter: number[] | null = null;

  if (!skipNav) {
    try {
      const nav = await sdk.pds.invoke("did:web:site.etzhayyim.com", "corpus2skill.navigate", {
        queryText: q, domain, maxHops,
      }) as Record<string, unknown>;
      if (nav && Array.isArray(nav.cluster_ids) && (nav.cluster_ids as number[]).length > 0) {
        navResult = {
          leafNodeId: String(nav.leaf_node_id ?? ""),
          nodePath: Array.isArray(nav.node_path) ? nav.node_path : [],
          clusterIds: nav.cluster_ids,
          hopCount: Number(nav.hop_count ?? 0),
          distillVersion: String(nav.distill_version ?? ""),
        };
        clusterFilter = nav.cluster_ids as number[];
      }
    } catch { /* no skill tree yet — proceed without navigation */ }
  }

  // 3. IVF+PQ search (ADC scoring)
  const db = createKyselyDb();
  let hits: Array<Record<string, unknown>> = [];
  let method = "vector:ivf+pq";

  try {
    // Find nearest n_probe centroids
    const centroidRows = await db
      .selectFrom("vertex_ivf_centroid")
      .select(["rkey", "embedding"])
      .where("collection", "=", domain)
      .limit(10000)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);

    if (centroidRows.length === 0) throw new Error("no_centroids");

    const qVec = queryVec;
    const centroids = centroidRows
      .filter((r) => Array.isArray(r.embedding) && (r.embedding as number[]).length > 0)
      .map((r) => ({ id: Number(r.rkey), vec: r.embedding as number[] }));

    const cosine = (a: number[], b: number[]) => {
      let dot = 0, na = 0, nb = 0;
      for (let i = 0; i < Math.min(a.length, b.length); i++) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
      return na > 0 && nb > 0 ? dot / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
    };

    let probeIds = centroids
      .map((c) => ({ id: c.id, score: cosine(qVec, c.vec) }))
      .sort((a, b) => b.score - a.score)
      .slice(0, nProbe)
      .map((c) => c.id);

    // Intersect with navigation cluster filter if available
    if (clusterFilter && clusterFilter.length > 0) {
      const filterSet = new Set(clusterFilter);
      const filtered = probeIds.filter((id) => filterSet.has(id));
      if (filtered.length > 0) probeIds = filtered;
      method = "vector:ivf+pq+corpus2skill";
    }

    // Fetch wet_chunk candidates from probe clusters
    const candidates = await db
      .selectFrom("vertex_wet_chunk")
      .select(["vertex_id", "url", "domain", "markdown", "title", "ivf_cluster_id", "embedding"])
      .where("domain", "=", domain)
      .where("ivf_cluster_id", "in", probeIds)
      .where("embedding", "is not", null)
      .limit(500)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);

    hits = candidates
      .filter((r) => Array.isArray(r.embedding) && (r.embedding as number[]).length > 0)
      .map((r) => {
        const score = cosine(qVec, r.embedding as number[]);
        return {
          chunkVertexId: String(r.vertex_id ?? ""),
          domain: String(r.domain ?? domain),
          url: String(r.url ?? ""),
          title: String(r.title ?? ""),
          markdownPreview: String(r.markdown ?? "").slice(0, 400),
          score: Math.round((1 - score) * 1e6) / 1e6,
          clusterId: r.ivf_cluster_id ?? null,
        };
      })
      .sort((a, b) => (a.score as number) - (b.score as number))
      .slice(0, topK);
  } catch {
    // Fallback to brute-force
    const fallback = await ivfSearchChunks(sdk, domain, q, topK);
    hits = fallback.chunks.map((c) => ({
      chunkVertexId: String(c.vid ?? ""),
      domain: String(c.domain ?? domain),
      url: String(c.url ?? ""),
      title: String(c.title ?? ""),
      markdownPreview: String(c.markdown ?? "").slice(0, 400),
      score: Number(c._score ?? 0),
      clusterId: null,
    }));
    method = fallback.method;
  }

  return encodeJson({
    query: q,
    domain,
    nav: navResult,
    hits,
    totalHits: hits.length,
    method,
    latencyMs: Date.now() - t0,
  });
}

async function cmdSearchPages(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.searchPages", payload);
  const limit = Math.min(Math.max(req.limit ?? 50, 1), 100);
  const offset = req.offset ?? 0;
  const q = String(req.query ?? "");
  const rows = await createKyselyDb()
    .selectFrom("vertex_page")
    .selectAll()
    .where((eb) => eb.or([eb("title", "=", q), eb("url", "=", q)]))
    .orderBy("created_date", "desc")
    .offset(offset)
    .limit(limit)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>);
  return encodeJson({ pages: rows, total: rows.length, offset, limit });
}

async function cmdListJobs(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.listJobs", payload);
  const limit = Math.min(Math.max(req.limit ?? 50, 1), 100);
  const offset = req.offset ?? 0;

  let qb = createKyselyDb().selectFrom("vertex_collection_job").selectAll();
  if (req.status) qb = qb.where("status", "=", String(req.status));
  if (req.sourceId) qb = qb.where("source_id", "=", String(req.sourceId));
  const rows = await qb.orderBy("created_date", "desc").offset(offset).limit(limit).execute()
    .catch(() => [] as Array<Record<string, unknown>>);
  return encodeJson({ jobs: rows, total: rows.length, offset, limit });
}

async function cmdGetStats(sdk: HostSDK, _payload: Uint8Array): Promise<Uint8Array> {
  // Read from streaming MVs — no per-request full-table scan on 985M-row vertex_page.
  const db = createKyselyDb();
  const pageRow = await (db as any).selectFrom("mv_site_page_total").select("cnt").executeTakeFirst()
    .catch(() => undefined as { cnt: string } | undefined);
  const pageCount = [{ cnt: pageRow?.cnt ?? "0" }];
  const jobRow = await (db as any).selectFrom("mv_site_job_total").select("cnt").executeTakeFirst()
    .catch(() => undefined as { cnt: string } | undefined);
  const jobCount = [{ cnt: jobRow?.cnt ?? "0" }];
  // TODO(site): vertex_web_topic not in @etzhayyim/graph-schema
  const topicCounts: Array<Record<string, unknown>> = [];

  return encodeJson({
    'totalPages': Number(pageCount[0]?.cnt ?? 0),
    'totalJobs': Number(jobCount[0]?.cnt ?? 0),
    topics: topicCounts,
    sources: dataSources.map(s => ({ id: s.id, name: s.name, language: s.language })),
  });
}

async function cmdEnqueueUrl(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.enqueueUrl", payload);
  if (!req.url) return encodeJson({ error: "url is required" });

  const topics = req.topics ?? ["academic"];
  const priority = req.priority ?? 50;
  const [orgId, userId] = ctxOrgUser(sdk);

  try {
    const euFeRkey = genID("fe");
    await getDb().insertInto("vertex_frontier").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${euFeRkey}`,
      rkey: euFeRkey,
      url: req.url,
      domain: new URL(req.url).hostname,
      status: "pending",
      priority,
      depth: 0,
      topics: JSON.stringify(topics),
      source: "manual",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
  } catch (e) {
    const errMsg = e instanceof Error ? e.message : String(e);
    console.error("[frontier] enqueue write failed:", errMsg);
    return encodeJson({ status: "enqueued_kv_only", url: req.url, priority, error: errMsg });
  }

  return encodeJson({ status: "enqueued", url: req.url, priority });
}

// --- Commands: Domain/Page DID Management ---

async function cmdRegisterDomain(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.registerDomain", payload);
  if (!req.domain) return encodeJson({ error: "domain is required" });

  const slug = req.domain.replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  const topics = req.topics ?? [];

  const did = str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
    displayName: req.domain,
    description: `Web domain archive: ${req.domain}`,
    category: "content",
  })));

  try {
    await getDb().insertInto("vertex_web_domain" as any).values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.domain/${slug}`,
      domain: req.domain,
      slug,
      did: did || `did:web:${appId}.etzhayyim.com:${slug}`,
      topics: JSON.stringify(topics),
      page_count: 0,
      sensitivity_ord: 2,
      owner_did: appId,
      first_seen: nowISO(),
      last_crawled: nowISO(),
      created_date: nowISO().slice(0, 10),
    }).execute();
  } catch (e) { console.warn("vertex_web_domain insert:", e); }

  return encodeJson({ status: "registered", domain: req.domain, slug, did });
}

async function cmdCrawlPage(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.crawlPage", payload);
  if (!req.url) return encodeJson({ error: "url is required" });

  const topics = req.topics ?? ["academic"];
  const hostname = new URL(req.url).hostname;
  const [orgId, userId] = ctxOrgUser(sdk);

  const jobId = createCollectionJob(sdk, "crawl", req.url, "html", topics, {
    'crawlType': "singlePage",
    depth: req.depth ?? 0,
  });

  const feRkey = genID("fe");
  await getDb().insertInto("vertex_frontier").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${feRkey}`,
    rkey: feRkey,
    url: req.url,
    domain: hostname,
    status: "pending",
    priority: 50,
    depth: req.depth ?? 0,
    topics: JSON.stringify(topics),
    source: "crawlPage",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  return encodeJson({ status: "pending", 'jobId': jobId, url: req.url });
}

async function cmdCrawlDomain(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.crawlDomain", payload);
  if (!req.domain) return encodeJson({ error: "domain is required" });

  const maxDepth = Math.min(req.maxDepth ?? 3, 3);
  const maxPages = Math.min(req.maxPages ?? 100, 500);
  const topics = req.topics ?? ["academic"];
  const [orgId, userId] = ctxOrgUser(sdk);

  const slug = req.domain.replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  const did = str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
    displayName: req.domain,
    description: `Domain crawl: ${req.domain} (maxDepth=${maxDepth}, maxPages=${maxPages})`,
    category: "content",
  })));

  try {
    await getDb().insertInto("vertex_web_domain" as any).values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.domain/${slug}`,
      domain: req.domain,
      slug,
      did: did || `did:web:${appId}.etzhayyim.com:${slug}`,
      topics: JSON.stringify(topics),
      page_count: 0,
      sensitivity_ord: 2,
      owner_did: appId,
      first_seen: nowISO(),
      last_crawled: nowISO(),
      created_date: nowISO().slice(0, 10),
    }).execute();
  } catch (e) { console.warn("vertex_web_domain insert:", e); }

  const seedUrl = `https://${req.domain}/`;
  const seedFeRkey = genID("fe");
  await getDb().insertInto("vertex_frontier").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${seedFeRkey}`,
    rkey: seedFeRkey,
    url: seedUrl,
    domain: req.domain,
    status: "pending",
    priority: 50,
    depth: 0,
    topics: JSON.stringify(topics),
    source: "crawlDomain",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  const sessionId = genID("cs");
  try {
    await getDb().insertInto("vertex_crawl_session" as any).values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.crawl/${sessionId}`,
      session_id: sessionId,
      domain: req.domain,
      page_count: 0,
      error_count: 0,
      max_depth: maxDepth,
      max_pages: maxPages,
      sensitivity_ord: 2,
      owner_did: appId,
      started_at: nowISO(),
      created_date: nowISO().slice(0, 10),
    }).execute();
  } catch (e) { console.warn("vertex_crawl_session insert:", e); }

  return encodeJson({ status: "started", domain: req.domain, 'sessionId': sessionId, 'maxDepth': maxDepth, 'maxPages': maxPages });
}

async function cmdRecordPage(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.recordPage", payload);
  if (!req.url || !req.content) return encodeJson({ error: "url and content are required" });

  const language = req.language ?? "ja";
  const topics = req.topics ?? ["academic"];
  const sourceId = req.sourceId ?? "manual";
  const cleanText = stripHTML(req.content);
  const era = detectEra(cleanText, language);
  const paragraphs = splitIntoParagraphs(cleanText, 256, 512);
  const hostname = new URL(req.url).hostname;

  let pagesCreated = 0;
  for (const para of paragraphs) {
    try {
      const rpRkey = genID("pg");
      await getDb().insertInto("vertex_page").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${rpRkey}`,
        rkey: rpRkey,
        url: req.url,
        domain: hostname,
        title: req.title ? `${req.title} (${pagesCreated + 1}/${paragraphs.length})` : `${hostname}-${pagesCreated + 1}`,
        language,
        content_type: "text/plain",
        content_hash: simpleCID(para),
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
    } catch (e) { console.warn("recordPage:", e); }
    pagesCreated++;
  }

  return encodeJson({ status: "recorded", url: req.url, 'pagesCreated': pagesCreated });
}

async function cmdGetPage(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.getPage", payload);

  const db = createKyselyDb();
  let qb = db.selectFrom("vertex_page").selectAll().limit(1);
  if (req.id) {
    // TODO(site): WebPage.id legacy alias — vertex_page primary key is vertex_id
    qb = qb.where("vertex_id", "=", String(req.id));
  } else if (req.url) {
    qb = qb.where("url", "=", String(req.url));
  } else if (req.did) {
    // TODO(site): WebPage.did not promoted on vertex_page — fall back to owner_did match
    qb = qb.where("owner_did", "=", String(req.did));
  } else {
    return encodeJson({ error: "one of id, url, or did is required" });
  }

  const rows = await qb.execute().catch(() => [] as Array<Record<string, unknown>>);
  if (rows.length === 0) return encodeJson({ error: "page not found" });
  return encodeJson({ page: rows[0] });
}

async function cmdGetDomainOverview(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.getDomainOverview", payload);
  if (!req.domain) return encodeJson({ error: "domain is required" });

  // Serialized per Hyperdrive origin pool guideline.
  const db = createKyselyDb();
  // TODO(site): vertex_web_domain / vertex_crawl_session not in @etzhayyim/graph-schema
  const domainRows: Array<Record<string, unknown>> = [];
  const pageCount = await (db as any)
    .selectFrom("view_page_count_by_domain")
    .select("cnt")
    .where("domain", "=", String(req.domain))
    .execute()
    .catch(() => [] as Array<{ cnt: string }>);
  const recentPages = await db.selectFrom("vertex_page")
    .select(["title", "url", "created_date as createdAt"])
    .where("domain", "=", String(req.domain))
    .orderBy("created_date", "desc")
    .limit(10)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>);
  const crawlSessions: Array<Record<string, unknown>> = [];

  return encodeJson({
    domain: domainRows[0] ?? null,
    'pageCount': Number(pageCount[0]?.cnt ?? 0),
    'recentPages': recentPages,
    'crawlSessions': crawlSessions,
  });
}

async function cmdGetLinkGraph(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.getLinkGraph", payload);
  const limit = Math.min(req.limit ?? 50, 200);

  // TODO(site): edge_links_to 1-hop expansion not yet wired to Kysely typed edge table — return empty
  void limit;
  if (req.url) return encodeJson({ links: [], source: req.url });
  if (req.domain) return encodeJson({ links: [], domain: req.domain });
  return encodeJson({ 'domainLinks': [] });
}

async function cmdEnqueueBulk(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.enqueueBulk", payload);
  if (!req.urls || req.urls.length === 0) return encodeJson({ error: "urls array is required" });

  const topics = req.topics ?? ["academic"];
  const priority = req.priority ?? 50;
  const [orgId, userId] = ctxOrgUser(sdk);
  let enqueued = 0;

  for (const url of req.urls) {
    try {
      const hostname = new URL(url).hostname;
      const bulkFeRkey = genID("fe");
      await getDb().insertInto("vertex_frontier").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${bulkFeRkey}`,
        rkey: bulkFeRkey,
        url,
        domain: hostname,
        status: "pending",
        priority,
        depth: 0,
        topics: JSON.stringify(topics),
        source: "bulk",
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
      enqueued++;
    } catch {
      console.warn(`invalid URL skipped: ${url}`);
    }
  }

  return encodeJson({ status: "enqueued", enqueued, total: req.urls.length });
}

async function cmdDequeueUrls(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.dequeueUrls", payload);
  const batchSize = Math.min(req.batchSize ?? 5, 20);

  let qb = createKyselyDb()
    .selectFrom("vertex_frontier")
    .selectAll()
    .where("status", "=", "pending");
  if (req.domain) qb = qb.where("domain", "=", String(req.domain));
  const urls = await qb.orderBy("priority", "desc").orderBy("created_date", "asc").limit(batchSize).execute()
    .catch(() => [] as Array<Record<string, unknown>>);
  return encodeJson({ urls, count: urls.length });
}

async function cmdGetFrontierStats(sdk: HostSDK, _payload: Uint8Array): Promise<Uint8Array> {
  const db = createKyselyDb();
  const entries = await db.selectFrom("vertex_frontier").select(["status", "domain"]).limit(500).execute()
    .catch(() => [] as Array<{ status?: string | null; domain?: string | null }>);
  const pending = entries.filter(e => e.status === "pending").length;
  const done = entries.filter(e => e.status === "done").length;
  const failed = entries.filter(e => e.status === "failed").length;
  const domainCounts = new Map<string, number>();
  for (const e of entries) if (e.status === "pending") domainCounts.set(str(e.domain), (domainCounts.get(str(e.domain)) ?? 0) + 1);
  const byDomain = [...domainCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20).map(([domain, cnt]) => ({ domain, cnt }));

  return encodeJson({
    pending,
    done,
    failed,
    'pendingByDomain': byDomain,
  });
}

/** Default cooldown between same-domain requests (ms). */
const DEFAULT_DOMAIN_COOLDOWN_MS = 2000;

/** Query last crawl timestamp for a domain from kagami graph (persistent across Worker restarts). */
async function getDomainLastCrawled(domain: string): Promise<number> {
  // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — cooldown falls back to 0 until schema lands
  void domain;
  return 0;
}

/** Persist domain crawl timestamp — no-op: vertex_web_domain cooldown schema not yet available. */
function setDomainLastCrawled(_sdk: HostSDK, _domain: string, _ts: number): void {
  return;
}

async function cmdProcessFrontier(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.processFrontier", payload);
  const batchSize = Math.min(req.batchSize ?? 20, 50);

  const rows = await createKyselyDb()
    .selectFrom("vertex_frontier")
    .selectAll()
    .where("status", "=", "pending")
    .where("depth", "<", MAX_FRONTIER_DEPTH)
    .orderBy("priority", "desc")
    .orderBy("created_date", "asc")
    .limit(batchSize)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>);

  if (rows.length === 0) return encodeJson({ status: "empty", processed: 0 });

  let processed = 0;
  let skippedCooldown = 0;
  const now = Date.now();

  for (const entry of rows) {
    const url = str(entry.url);
    const domain = str(entry.domain);
    if (!url) continue;

    // Per-domain cooldown: skip if domain was crawled too recently (persistent via kagami graph)
    const lastCrawled = await getDomainLastCrawled(domain);
    if (now - lastCrawled < DEFAULT_DOMAIN_COOLDOWN_MS) {
      skippedCooldown++;
      continue;
    }
    setDomainLastCrawled(sdk, domain, now);

    let topics: string[];
    try { topics = JSON.parse(str(entry.topics ?? "[]")); } catch { topics = ["academic"]; }

    const jobId = createCollectionJob(sdk, "crawl", url, "html", topics, {
      'crawlType': "frontier",
      depth: Number(entry.depth ?? 0),
      priority: Number(entry.priority ?? 40),
      'frontierId': str(entry.id),
      domain,
    });

    const pfRkey = str(entry.rkey ?? entry.id ?? genID("fe"));
    await getDb().insertInto("vertex_frontier").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${pfRkey}`,
      rkey: pfRkey,
      url,
      domain,
      status: "processing",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();

    processed++;
  }

  return encodeJson({ status: "processing", processed, skippedCooldown, 'batchSize': batchSize });
}

// ── Bulk Catalog Ingest (PD books) ───────────────────────────────────

async function cmdBulkIngestAozora(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const input = JSON.parse(new TextDecoder().decode(payload) || "{}") as Record<string, unknown>;
  const limit = Math.max(1, Math.min(Number(input.limit) || 100, 1000));
  const offset = Number(input.offset) || 0;
  const author = String(input.author ?? "");

  // Aozora Bunko GitHub index: aozorahack/aozorabunko CSV
  // Creates collection jobs to fetch the catalog index then individual works
  const jobId = genID("cj");
  const catalogUrl = "https://raw.githubusercontent.com/aozorahack/aozorabunko/master/indexPages/listPersonAllExtendedUtf8.csv";

  await getDb().insertInto("vertex_collection_job").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
    rkey: jobId,
    source_id: "aozoraBulk",
    source_url: catalogUrl,
    format: "csvCatalog",
    status: "pending",
    topics: JSON.stringify(["jpClassics"]),
    crawl_type: "aozoraBulk",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  const topicDID = `did:web:${appId}.etzhayyim.com:topic:jpClassics`;
  await postAs(sdk, topicDID, `Aozora Bunko bulk ingest started: ${limit} works from offset ${offset}${author ? ` (author: ${author})` : ""}`);

  return new TextEncoder().encode(JSON.stringify({
    status: "jobCreated",
    'jobId': jobId,
    catalog: "aozora",
    limit,
    offset,
    'estimatedTotal': 17000,
  }));
}

async function cmdBulkIngestGutenberg(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const input = JSON.parse(new TextDecoder().decode(payload) || "{}") as Record<string, unknown>;
  const limit = Math.max(1, Math.min(Number(input.limit) || 100, 1000));
  const offset = Number(input.offset) || 0;
  const language = String(input.language ?? "en");
  const subject = String(input.subject ?? "");

  // Gutenberg RDF catalog: https://www.gutenberg.org/cache/epub/feeds/rdf-files.tar.bz2
  // Or OPDS feed for simpler access
  const jobId = genID("cj");
  const catalogUrl = "https://gutendex.com/books/";

  await getDb().insertInto("vertex_collection_job").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
    rkey: jobId,
    source_id: "gutenbergBulk",
    source_url: catalogUrl,
    format: "jsonApi",
    status: "pending",
    topics: JSON.stringify(["intlLiterature"]),
    language,
    crawl_type: "gutenbergBulk",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  const topicDID = `did:web:${appId}.etzhayyim.com:topic:intlLiterature`;
  await postAs(sdk, topicDID, `Gutenberg bulk ingest started: ${limit} works (${language})${subject ? ` subject: ${subject}` : ""}`);

  return new TextEncoder().encode(JSON.stringify({
    status: "jobCreated",
    'jobId': jobId,
    catalog: "gutenberg",
    limit,
    offset,
    language,
    'estimatedTotal': 70000,
  }));
}

/**
 * Bulk ingest from NDL Digital Collection.
 * Phase 1: SRU catalog search → enumerate PD works with IIIF manifests
 * Phase 2: Per-work IIIF Manifest fetch → per-page WebP + OCR WET + WAT
 *
 * Input: { limit?, offset?, collection?, query?, bibId? }
 * - bibId: directly fetch a single IIIF Manifest
 * - query: NDL SRU search query (e.g., "公開範囲:インターネット公開")
 * - collection: NDL collection filter
 */
async function cmdBulkIngestNDL(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const input = JSON.parse(new TextDecoder().decode(payload) || "{}") as Record<string, unknown>;
  const limit = Math.max(1, Math.min(Number(input.limit) || 100, 1000));
  const offset = Number(input.offset) || 0;
  const collection = String(input.collection ?? "");
  const query = String(input.query ?? "");
  const bibId = String(input.bibId ?? "");

  // Direct single manifest fetch
  if (bibId) {
    return cmdFetchNdlManifest(sdk, new TextEncoder().encode(JSON.stringify({ bibId })));
  }

  // Phase 1: SRU catalog search for PD works
  const jobId = genID("cj");
  // NDL Search SRU API: search for internet-accessible public domain works
  const sruQuery = query
    || `dpid=iss-ndl-opac AND mediatype=1 AND anywhere="${collection || "インターネット公開"}"`;
  const catalogUrl = `https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&query=${encodeURIComponent(sruQuery)}&maximumRecords=${limit}&startRecord=${offset + 1}&recordSchema=dcndl`;

  await getDb().insertInto("vertex_collection_job").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
    rkey: jobId,
    source_id: "ndlBulk",
    source_url: catalogUrl,
    format: "ndlSruCatalog",
    status: "pending",
    topics: JSON.stringify(["jpClassics", "academic"]),
    language: "ja",
    crawl_type: "ndlBulk",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  const topicDID = `did:web:${appId}.etzhayyim.com:topic:jpClassics`;
  await postAs(sdk, topicDID, `NDL Digital Collection bulk ingest started: ${limit} works${collection ? ` (collection: ${collection})` : ""}`);

  return encodeJson({
    status: "jobCreated",
    'jobId': jobId,
    catalog: "ndl",
    limit,
    offset,
    'sruQuery': sruQuery,
    'estimatedTotal': 500000,
  });
}

/**
 * Fetch a single NDL IIIF Manifest by bibId and process its pages.
 * Creates a collection job that will be processed by processIiifManifestResult.
 *
 * Input: { bibId: string, topics?: string[] }
 */
async function cmdFetchNdlManifest(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const input = JSON.parse(new TextDecoder().decode(payload) || "{}") as Record<string, unknown>;
  const bibId = String(input.bibId ?? "");
  if (!bibId) return encodeJson({ error: "bibId is required" });

  const topics = (input.topics as string[]) ?? ["jpClassics", "academic"];
  const manifestUrl = `https://dl.ndl.go.jp/api/iiif/${bibId}/manifest.json`;
  const jobId = genID("cj");

  await getDb().insertInto("vertex_collection_job").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
    rkey: jobId,
    source_id: "ndl",
    source_name: `NDL IIIF Manifest ${bibId}`,
    source_url: manifestUrl,
    format: "iiifManifest",
    status: "pending",
    topics: JSON.stringify(topics),
    language: "ja",
    crawl_type: "ndlIiif",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  const topicDID = `did:web:${appId}.etzhayyim.com:topic:jpClassics`;
  await postAs(sdk, topicDID, `NDL IIIF Manifest fetch: ${bibId}\nhttps://dl.ndl.go.jp/pid/${bibId}`);

  return encodeJson({ status: "jobCreated", 'jobId': jobId, bibId, 'manifestUrl': manifestUrl });
}

// --- handleComAtprotoSyncSubscribeReposCommit: Process collectionJob results ---

export async function handleComAtprotoSyncSubscribeReposCommit(
  sdk: HostSDK,
  commit: ComAtprotoSyncSubscribeReposCommit,
): Promise<{ ok: boolean; detail: string }> {
  if (commit.action !== "create") return { ok: true, detail: "skip non-create" };

  const collection = str(commit.collection);
  const recordJson = str((commit as any).record ?? (commit as any).recordJson ?? "");

  // Process completed collectionJob results
  if (collection === "com.etzhayyim.apps.site.collectionJob" || collection.includes("collectionJob")) {
    return await processCollectionJobResult(sdk, recordJson);
  }

  // Process inbound page data from pipeline
  if (collection === "com.etzhayyim.apps.site.pageRaw") {
    return await processRawPage(sdk, recordJson);
  }

  // Process robots.txt fetch result
  if (collection === "com.etzhayyim.apps.site.robotsTxt") {
    return { ok: true, detail: "robotsTxt cached" };
  }

  // cross-actor: URL mentions from other apps
  if (collection === "app.bsky.feed.post") {
    return await processInboundMention(sdk, recordJson);
  }

  return { ok: true, detail: "no matching handler" };
}

async function processCollectionJobResult(sdk: HostSDK, recordJson: string): Promise<{ ok: boolean; detail: string }> {
  let record: Record<string, unknown>;
  try {
    record = JSON.parse(recordJson);
  } catch {
    return { ok: true, detail: "invalid json" };
  }

  const status = str(record.status);
  if (status !== "completed") return { ok: true, detail: `job status: ${status}` };

  const sourceId = str(record.sourceId);
  const source = sourceById.get(sourceId);
  const language = str(record.language ?? source?.language ?? "ja");
  const sourceUrl = str(record.sourceUrl);
  const topicsRaw = str(record.topics ?? "[]");
  let topics: string[];
  try { topics = JSON.parse(topicsRaw); } catch { topics = source?.topics ?? []; }
  const format = str(record.format);

  // PDF may have no text content (image-only PDF) but still needs screenshot rendering
  if (format === "pdf") {
    return await processPdfResult(sdk, record, topics, language);
  }

  // Screenshot result from browser automation (no text content needed — uses blobRef)
  if (format === "browserScreenshot") {
    return await processScreenshotResult(sdk, record);
  }

  const content = str(record.content ?? record.text ?? record.body ?? "");
  if (!content) return { ok: true, detail: "no content in completed job" };

  // IIIF Manifest (NDL Digital Collection bulk ingest) → per-page WebP + OCR WET + WAT
  if (format === "iiifManifest") {
    return await processIiifManifestResult(sdk, record, topics, language);
  }

  // NDL SRU catalog search results → enumerate manifests → enqueue individual items
  if (format === "ndlSruCatalog") {
    return await processNdlSruCatalogResult(sdk, record, topics);
  }

  // Image jobs
  if (format === "iiifImage" || format === "pngAnnotation") {
    return await processImageResult(sdk, record, topics);
  }

  // Screenshot result from browser automation
  if (format === "browserScreenshot") {
    return await processScreenshotResult(sdk, record);
  }

  // Robots.txt result
  if (format === "robotsTxt") {
    const targetDomain = str(record.targetDomain ?? "");
    if (targetDomain && content) {
      const rules = parseRobotsTxt(content);
      const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
      const rbRkey = genID("rb");
      try {
        await getDb().insertInto("vertex_robots_txt" as any).values({
          vertex_id: `at://${appId}/com.etzhayyim.apps.site.robotsTxt/${rbRkey}`,
          domain: targetDomain,
          rules: JSON.stringify(rules),
          crawl_delay: rules.crawlDelay,
          sitemap_urls: JSON.stringify(rules.sitemapUrls),
          fetched_at: nowISO(),
          expires_at: expiresAt,
          sensitivity_ord: 2,
          owner_did: appId,
          created_date: nowISO().slice(0, 10),
        }).execute();
      } catch (e) { console.warn("vertex_robots_txt insert:", e); }
    }
    return { ok: true, detail: `robots.txt cached for ${targetDomain}` };
  }

  // CDX index (Common Crawl seed)
  if (format === "cdxIndex") {
    return await processCDXSeedResult(sdk, record, content);
  }

  // USGS Earthquake GeoJSON feed → geoRecord per seismic event
  if (format === "usgs_geojson") {
    return await processUsgsGeoJsonResult(sdk, record, content);
  }

  // Wikidata SPARQL results → geoRecord per municipality or world adminArea2
  if (format === "wikidata_sparql") {
    return await processWikidataSparqlResult(sdk, record, content);
  }

  // OurAirports CSV → geoRecord per airport (large/medium, has IATA)
  if (format === "ourairports_csv") {
    return await processOurAirportsCsvResult(sdk, record, content);
  }

  // OpenSky ADS-B JSON → geoRecord per airborne aircraft
  if (format === "opensky_json") {
    return await processOpenSkyJsonResult(sdk, record, content);
  }

  // STAC API /search JSON → geoRecord per satellite scene
  if (format === "stac_search_json") {
    return await processStacSearchResult(sdk, record, content);
  }

  const title = str(record.title ?? "");
  const hostname = sourceUrl ? (() => { try { return new URL(sourceUrl).hostname; } catch { return ""; } })() : "";
  const slug = hostname.replace(/[^a-z0-9]/g, "-");
  const pageDid = `did:web:${appId}.etzhayyim.com:${slug}`;
  const domainDid = pageDid;

  // General crawl (html format from frontier) → WET + WAT + Screenshot pipeline
  const crawlType = str(record.crawlType ?? "");
  if (crawlType === "frontier" || crawlType === "singlePage" || format === "html") {
    // Classify topics from content
    const autoTopics = topics.length > 0 && topics[0] !== "academic"
      ? topics
      : classifyTopics(sourceUrl, title || extractHtmlMeta(content).title, content);

    // Version-aware re-crawl: check existing page content_hash to detect changes
    const markdown = htmlToMarkdown(content);
    const newContentHash = simpleCID(markdown);
    let previousContentHash = "";
    let pageVersion = 1;
    let contentChanged = true;
    try {
      const existing = await createKyselyDb()
        .selectFrom("vertex_page")
        .select(["content_hash as ch", "version as v"])
        .where("url", "=", sourceUrl)
        .limit(1)
        .execute()
        .catch(() => [] as Array<{ ch?: string | null; v?: number | bigint | null }>);
      if (existing.length > 0 && existing[0].ch) {
        previousContentHash = String(existing[0].ch);
        pageVersion = Number(existing[0].v ?? 1) + 1;
        contentChanged = previousContentHash !== newContentHash;
      }
    } catch { /* first crawl — no existing record */ }

    // Write version-tracked page record (Tier 2 domain)
    const [orgId, userId] = ctxOrgUser(sdk);
    const pgRkey = genID("pg");
    await getDb().insertInto("vertex_page").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${pgRkey}`,
      rkey: pgRkey,
      url: sourceUrl,
      domain: hostname,
      title: title || extractHtmlMeta(content).title,
      language,
      content_type: "text/html",
      content_hash: newContentHash,
      previous_content_hash: previousContentHash,
      version: pageVersion,
      crawled_at: nowISO(),
      outlink_count: 0,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();

    // Skip WET/WAT regeneration if content unchanged (dedup on re-crawl)
    if (!contentChanged) {
      return { ok: true, detail: `unchanged (v${pageVersion}) ${sourceUrl}` };
    }

    // Generate WET (Markdown chunks)
    const wetCount = generateWET(sdk, sourceUrl, content, {
      title: title || extractHtmlMeta(content).title,
      language,
      topics: autoTopics,
      pageDid,
      domainDid,
    });

    // Generate WAT (metadata) + outlink discovery + frontier status update
    generateWAT(sdk, sourceUrl, content, {
      statusCode: Number(record.statusCode ?? 200),
      mimeType: str(record.mimeType ?? "text/html"),
      httpHeaders: str(record.httpHeaders ?? "{}"),
      pageDid,
      domainDid,
      wetChunkCount: wetCount,
      parentDepth: Number(record.depth ?? 0),
      parentPriority: Number(record.priority ?? 40),
      frontierId: str(record.frontierId ?? ""),
    });

    // Schedule screenshot capture
    if (sourceUrl) captureScreenshotJob(sdk, sourceUrl, autoTopics);

    // Tier 1: Social post from topic coordinator DID
    const snippet = truncateText(markdown, 250);
    for (const topicSlug of autoTopics) {
      const topicDID = allTopicBySlug.get(topicSlug)?.did ?? topicBySlug.get(topicSlug)?.did ?? "";
      if (topicDID) postAs(sdk, topicDID, `${title ? title + "\n" : ""}${snippet}`);
    }

    // Domain DID post: summarize new page and post as the domain agent
    if (domainDid) {
      try {
        const pageSummary = await llmAsk(
          `Summarize this page in 1-2 sentences. Be neutral and factual. Title: ${title}. Content: ${truncateText(markdown, 1000)}`,
        );
        postAs(sdk, domainDid, truncateText(
          `${title ? title + "\n" : ""}${pageSummary}\n${sourceUrl}`,
          280,
        ));
      } catch (e) { console.warn("domainDIDPost:", e); }
    }

    return { ok: true, detail: `WET(${wetCount})+WAT+screenshot v${pageVersion} for ${sourceUrl}` };
  }

  // Legacy catalog ingest path (aozora, gutenberg, etc.) → webpagePage records
  const cleanText = stripHTML(content);
  const era = detectEra(cleanText, language);
  const paragraphs = splitIntoParagraphs(cleanText, 256, 512);

  let pagesCreated = 0;
  for (const paragraph of paragraphs) {
    const pageId = genID("pg");
    const contentHash = simpleCID(paragraph);

    await getDb().insertInto("vertex_page").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${pageId}`,
      rkey: pageId,
      url: sourceUrl,
      domain: sourceUrl ? (() => { try { return new URL(sourceUrl).hostname; } catch { return sourceId; } })() : sourceId,
      title: title ? `${title} (${pagesCreated + 1}/${paragraphs.length})` : `${sourceId}-${pagesCreated + 1}`,
      language,
      content_type: "text/plain",
      content_hash: contentHash,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();

    for (const topicSlug of topics) {
      const topicDID = topicBySlug.get(topicSlug)?.did ?? "";
      if (!topicDID) continue;
      postAs(sdk, topicDID, truncateText(paragraph, 280));
    }

    pagesCreated++;
  }

  return { ok: true, detail: `created ${pagesCreated} pages from ${sourceId}` };
}

async function processImageResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  topics: string[],
): Promise<{ ok: boolean; detail: string }> {
  const imageUrl = str(record.imageUrl ?? record.url ?? record.sourceUrl ?? "");
  const title = str(record.title ?? record.label ?? "");
  const altText = str(record.altText ?? record.description ?? title);
  const sourceId = str(record.sourceId);
  const source = sourceById.get(sourceId);

  if (!imageUrl) return { ok: true, detail: "no imageUrl in result" };

  const pageId = genID("img");

  // Tier 2: Domain record for image metadata
  await getDb().insertInto("vertex_page").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${pageId}`,
    rkey: pageId,
    url: imageUrl,
    domain: (() => { try { return new URL(imageUrl).hostname; } catch { return sourceId; } })(),
    title,
    language: "ja",
    content_type: "image",
    content_hash: simpleCID(imageUrl),
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  // Tier 1: Social post with image embed from topic coordinator
  const topicDID = topicBySlug.get("images")?.did ?? "";
  if (topicDID) {
    const postText = title
      ? `${title}\n${altText ? altText : ""}\nSource: ${source?.name ?? sourceId}`
      : `Historical image from ${source?.name ?? sourceId}`;

    // Upload blob if raw image data is available
    const blobRef = str(record.blobRef ?? "");
    if (blobRef) {
      postAs(sdk, topicDID, truncateText(postText, 280), JSON.stringify({
        $type: "app.bsky.embed.images",
        images: [{
          alt: truncateText(altText || title, 1000),
          image: { $type: "blob", ref: { $link: blobRef }, mimeType: "image/jpeg", size: 0 },
        }],
      }));
    } else {
      // External embed with image URL
      postAs(sdk, topicDID, truncateText(postText, 280), JSON.stringify({
        $type: "app.bsky.embed.external",
        external: {
          uri: imageUrl,
          title: truncateText(title, 200),
          description: truncateText(altText, 300),
        },
      }));
    }
  }

  return { ok: true, detail: `image page created: ${pageId}` };
}

async function processRawPage(sdk: HostSDK, recordJson: string): Promise<{ ok: boolean; detail: string }> {
  let record: Record<string, unknown>;
  try {
    record = JSON.parse(recordJson);
  } catch {
    return { ok: true, detail: "invalid json for raw page" };
  }

  const text = str(record.text ?? record.content ?? "");
  if (!text) return { ok: true, detail: "empty raw page" };

  const sourceId = str(record.sourceId);
  const source = sourceById.get(sourceId);
  const language = str(record.language ?? source?.language ?? "ja");
  const sourceUrl = str(record.sourceUrl ?? "");
  const title = str(record.title ?? "");
  const era = detectEra(text, language);
  const topicsRaw = str(record.topics ?? "[]");
  let topics: string[];
  try { topics = JSON.parse(topicsRaw); } catch { topics = source?.topics ?? []; }

  const paragraphs = splitIntoParagraphs(stripHTML(text), 256, 512);
  let count = 0;
  for (const para of paragraphs) {
    const rawPgRkey = genID("pg");
    await getDb().insertInto("vertex_page").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${rawPgRkey}`,
      rkey: rawPgRkey,
      url: sourceUrl,
      domain: sourceUrl ? (() => { try { return new URL(sourceUrl).hostname; } catch { return sourceId; } })() : sourceId,
      title: title ? `${title} (${count + 1})` : `raw-${count + 1}`,
      language,
      content_type: "text/plain",
      content_hash: simpleCID(para),
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
    count++;
  }

  return { ok: true, detail: `raw page split into ${count} paragraphs` };
}

async function processInboundMention(sdk: HostSDK, recordJson: string): Promise<{ ok: boolean; detail: string }> {
  let record: Record<string, unknown>;
  try {
    record = JSON.parse(recordJson);
  } catch {
    return { ok: true, detail: "invalid mention json" };
  }

  const text = str(record.text ?? "");
  // Extract URLs from the post text
  const urlRegex = /https?:\/\/[^\s<>"{}|\\^`[\]]+/g;
  const urls = text.match(urlRegex);
  if (!urls || urls.length === 0) return { ok: true, detail: "no URLs in mention" };

  for (const url of urls) {
    const mentionFeRkey = genID("fe");
    await getDb().insertInto("vertex_frontier").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${mentionFeRkey}`,
      rkey: mentionFeRkey,
      url,
      domain: new URL(url).hostname,
      status: "pending",
      priority: 20,
      depth: 0,
      topics: "[]",
      source: "a2a_mention",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
  }

  return { ok: true, detail: `enqueued ${urls.length} URLs from mention` };
}

// --- WET/WAT/Screenshot Generation Pipeline ---

async function generateWET(
  sdk: HostSDK, url: string, html: string,
  meta: { title: string; language: string; topics: string[]; pageDid: string; domainDid: string },
): Promise<number> {
  const markdown = htmlToMarkdown(html);
  if (!markdown) return 0;

  const chunks = splitIntoParagraphs(markdown, 256, 512);
  const [orgId, userId] = ctxOrgUser(sdk);
  let currentSection = "";

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    // Track heading context for this chunk
    const headingMatch = chunk.match(/^(#{1,6})\s+(.+)$/m);
    if (headingMatch) currentSection = headingMatch[2];

    const contentHash = simpleCID(chunk);
    const tokenCount = estimateTokens(chunk);

    const wetId = genID("wet");
    const now = nowISO();
    await getDb().insertInto("vertex_wet_chunk").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.wet/${wetId}`,
      page_rkey: meta.pageDid,
      url,
      domain: new URL(url).hostname,
      chunk_index: i,
      total_chunks: chunks.length,
      markdown: truncateText(chunk, 10000),
      content_hash: contentHash,
      language: meta.language,
      title: meta.title,
      section: currentSection,
      token_count: tokenCount,
      crawled_at: now,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: now.slice(0, 10),
    } as any).execute();

    // Emit EdgeChunkOf: WetChunk → Page (for GraphRAG traversal)
    const coId = genID("co");
    await getDb().insertInto("edge_chunk_of").values({
      edge_id: `at://${appId}/com.etzhayyim.apps.site.chunkOf/${coId}`,
      src_vid: `at://${appId}/com.etzhayyim.apps.site.wet/${wetId}`,
      dst_vid: meta.pageDid,
      chunk_index: i,
      label: "ChunkOf",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: now.slice(0, 10),
    } as any).execute();
  }
  return chunks.length;
}

/** Max crawl depth — link discovery stops after this many hops. */
const MAX_FRONTIER_DEPTH = 3;

async function generateWAT(
  sdk: HostSDK, url: string, html: string,
  meta: { statusCode: number; mimeType: string; httpHeaders: string; pageDid: string; domainDid: string; wetChunkCount: number; parentDepth?: number; parentPriority?: number; frontierId?: string },
): Promise<void> {
  const htmlMeta = extractHtmlMeta(html);
  const outlinks = extractOutlinks(html, url);
  const internalLinks = outlinks.filter(l => l.internal).length;
  const externalLinks = outlinks.length - internalLinks;
  const [orgId, userId] = ctxOrgUser(sdk);
  const markdown = htmlToMarkdown(html);
  const language = htmlMeta.language || detectLanguageSimple(markdown);

  const watRkey = genID("wat");
  await getDb().insertInto("vertex_wat").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.wat/${watRkey}`,
    rkey: watRkey,
    url,
    domain: new URL(url).hostname,
    language,
    content_type: meta.mimeType || "text/html",
    status_code: String(meta.statusCode || 200),
    headers: meta.httpHeaders || "{}",
    outlinks: JSON.stringify(outlinks.slice(0, 500).map(l => l.url)),
    og_title: htmlMeta.ogTitle,
    og_description: htmlMeta.ogDescription,
    og_image: htmlMeta.ogImage,
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  // Enqueue discovered internal links to frontier (depth+1, capped at MAX_FRONTIER_DEPTH)
  const childDepth = (meta.parentDepth ?? 0) + 1;
  if (childDepth < MAX_FRONTIER_DEPTH) {
    const childPriority = Math.max(1, (meta.parentPriority ?? 40) - 10);
    for (const link of outlinks.filter(l => l.internal).slice(0, 50)) {
      const childFeRkey = genID("fe");
      await getDb().insertInto("vertex_frontier").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${childFeRkey}`,
        rkey: childFeRkey,
        url: link.url,
        domain: new URL(url).hostname,
        status: "pending",
        priority: childPriority,
        depth: childDepth,
        topics: "[]",
        source: "linkDiscovery",
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
    }
  }

  // Update parent Frontier status → "done"
  if (meta.frontierId) {
    const doneFeRkey = meta.frontierId;
    await getDb().insertInto("vertex_frontier").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${doneFeRkey}`,
      rkey: doneFeRkey,
      url,
      domain: new URL(url).hostname,
      status: "done",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
  }
}

function detectLanguageSimple(text: string): string {
  const jaChars = (text.match(/[\u3000-\u9fff\uf900-\ufaff]/g) || []).length;
  return jaChars > text.length * 0.1 ? "ja" : "en";
}

async function captureScreenshotJob(sdk: HostSDK, url: string, topics: string[]): Promise<string> {
  const jobId = createCollectionJob(sdk, "crawl", url, "browserScreenshot", topics, {
    'crawlType': "screenshot",
    'viewportWidth': 390,
    'viewportHeight': 844,
    format: "webp",
    quality: 80,
  });
  return jobId;
}

async function processScreenshotResult(sdk: HostSDK, record: Record<string, unknown>): Promise<{ ok: boolean; detail: string }> {
  const url = str(record.sourceUrl ?? record.url ?? "");
  const blobRef = str(record.blobRef ?? "");
  const fileSize = Number(record.fileSize ?? 0);
  if (!url || !blobRef) return { ok: true, detail: "screenshot: missing url or blobRef" };

  const hostname = new URL(url).hostname;
  const slug = hostname.replace(/[^a-z0-9]/g, "-");
  const [orgId, userId] = ctxOrgUser(sdk);

  const ssRkey = genID("ss");
  await getDb().insertInto("vertex_screenshot").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.screenshot/${ssRkey}`,
    rkey: ssRkey,
    url,
    domain: hostname,
    blob_ref: blobRef,
    format: "webp",
    width: Number(record.viewportWidth ?? 390),
    height: Number(record.viewportHeight ?? 844),
    quality: Number(record.quality ?? 80),
    file_size: fileSize,
    content_hash: simpleCID(blobRef),
    captured_at: nowISO(),
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  return { ok: true, detail: `screenshot recorded: ${url}` };
}

/**
 * Process completed PDF collection job: render pages to WebP (R2 CDN) + extract text to WET.
 * Each PDF page → browser screenshot job (WebP, R2 blobRef) + text → WET chunks.
 */
async function processPdfResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  topics: string[],
  language: string,
): Promise<{ ok: boolean; detail: string }> {
  const sourceUrl = str(record.sourceUrl ?? record.url ?? "");
  const title = str(record.title ?? "");
  const content = str(record.content ?? record.text ?? record.body ?? "");
  const pageCount = Number(record.pageCount ?? record.pageCount ?? 1);
  const [orgId, userId] = ctxOrgUser(sdk);

  if (!sourceUrl) return { ok: true, detail: "pdf: missing sourceUrl" };

  const hostname = (() => { try { return new URL(sourceUrl).hostname; } catch { return "pdf"; } })();
  const slug = hostname.replace(/[^a-z0-9]/g, "-");
  const pageDid = `did:web:${appId}.etzhayyim.com:${slug}`;
  const domainDid = pageDid;

  // --- 1. WebP page rendering: schedule browser screenshot for each PDF page ---
  let screenshotJobs = 0;
  for (let page = 1; page <= pageCount; page++) {
    const pageUrl = `${sourceUrl}#page=${page}`;
    const jobId = genID("cj");
    await getDb().insertInto("vertex_collection_job").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
      rkey: jobId,
      source_id: "pdfPage",
      source_name: `PDF page ${page}/${pageCount}`,
      source_url: pageUrl,
      format: "browserScreenshot",
      status: "pending",
      topics: JSON.stringify(topics),
      language,
      crawl_type: "pdfPageScreenshot",
      title: `PDF page ${page}/${pageCount}`,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
    screenshotJobs++;
  }

  // --- 2. Text extraction → WET records ---
  let wetCount = 0;
  if (content) {
    const chunks = splitIntoParagraphs(content, 256, 512);
    let currentSection = title || "PDF Document";
    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const headingMatch = chunk.match(/^(#{1,6})\s+(.+)$/m);
      if (headingMatch) currentSection = headingMatch[2];

      const pdfWetRkey = genID("wet");
      await getDb().insertInto("vertex_wet_chunk").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.wet/${pdfWetRkey}`,
        page_rkey: pageDid,
        url: sourceUrl,
        domain: hostname,
        chunk_index: i,
        total_chunks: chunks.length,
        markdown: truncateText(chunk, 10000),
        content_hash: simpleCID(chunk),
        language,
        title: title || `PDF Document (${i + 1}/${chunks.length})`,
        section: currentSection,
        token_count: estimateTokens(chunk),
        crawled_at: nowISO(),
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
      wetCount++;
    }
  }

  // --- 3. WAT metadata record ---
  const pdfWatRkey = genID("wat");
  await getDb().insertInto("vertex_wat").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.wat/${pdfWatRkey}`,
    rkey: pdfWatRkey,
    url: sourceUrl,
    domain: hostname,
    language,
    content_type: "application/pdf",
    status_code: "200",
    outlinks: "[]",
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  // --- 4. Social post from topic coordinator ---
  const snippet = title || `PDF document (${pageCount} pages)`;
  for (const topicSlug of topics) {
    const topicDID = allTopicBySlug.get(topicSlug)?.did ?? topicBySlug.get(topicSlug)?.did ?? "";
    if (topicDID) postAs(sdk, topicDID, truncateText(`📄 ${snippet}\n${sourceUrl}`, 280));
  }

  return { ok: true, detail: `pdf: WET(${wetCount})+WAT+${screenshotJobs} page screenshots for ${sourceUrl}` };
}

// ── NDL IIIF Manifest Processing ────────────────────────────────────

/**
 * Parse NDL IIIF Manifest JSON and process each canvas:
 * - Per-page IIIF Image → WebP screenshot job (R2 CDN)
 * - OCR text (if present in seeAlso/rendering) → WET records
 * - Bibliographic metadata → WAT record
 * - cross-actor notify isbn.etzhayyim.com with book metadata
 *
 * NDL IIIF Manifest: https://dl.ndl.go.jp/api/iiif/{bibId}/manifest
 * NDL IIIF Image:    https://dl.ndl.go.jp/api/iiif/{bibId}/R{page}/full/!1280,1656/0/default.jpg
 */
async function processIiifManifestResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  topics: string[],
  language: string,
): Promise<{ ok: boolean; detail: string }> {
  const sourceUrl = str(record.sourceUrl ?? record.url ?? "");
  const content = str(record.content ?? record.text ?? record.body ?? "");
  if (!content) return { ok: true, detail: "iiifManifest: no content" };

  let manifest: Record<string, unknown>;
  try {
    manifest = JSON.parse(content);
  } catch {
    return { ok: true, detail: "iiifManifest: invalid JSON" };
  }

  const [orgId, userId] = ctxOrgUser(sdk);
  const label = str(manifest.label ?? "");
  const description = str(manifest.description ?? "");
  const manifestId = str(manifest["@id"] ?? manifest.id ?? sourceUrl);

  // Extract bibId from manifest URL: https://dl.ndl.go.jp/api/iiif/{bibId}/manifest
  const bibIdMatch = manifestId.match(/\/iiif\/(\d+)\//);
  const bibId = bibIdMatch ? bibIdMatch[1] : "";
  const ndlViewUrl = bibId ? `https://dl.ndl.go.jp/pid/${bibId}` : sourceUrl;

  const hostname = "dl.ndl.go.jp";
  const slug = `dl-ndl-go-jp${bibId ? `-${bibId}` : ""}`;
  const pageDid = `did:web:${appId}.etzhayyim.com:${slug}`;
  const domainDid = `did:web:${appId}.etzhayyim.com:dl-ndl-go-jp`;

  // --- 1. Extract canvases from IIIF Manifest ---
  const sequences = (manifest.sequences ?? manifest.items ?? []) as Record<string, unknown>[];
  const canvases: Record<string, unknown>[] = [];
  for (const seq of sequences) {
    const seqCanvases = (seq.canvases ?? seq.items ?? []) as Record<string, unknown>[];
    canvases.push(...seqCanvases);
  }

  if (canvases.length === 0) return { ok: true, detail: "iiifManifest: no canvases" };

  // --- 2. Per-page IIIF Image → WebP screenshot jobs ---
  let screenshotJobs = 0;
  for (let i = 0; i < canvases.length; i++) {
    const canvas = canvases[i];
    // Extract image URL from canvas.images[0].resource or canvas.items[0].items[0].body
    const imageUrl = extractIiifImageUrl(canvas, bibId, i + 1);
    if (!imageUrl) continue;

    // Convert to WebP-optimized IIIF URL: full region, max 1280px width, default quality
    const webpUrl = toIiifWebpUrl(imageUrl, 1280, 1656);

    const jobId = genID("cj");
    await getDb().insertInto("vertex_collection_job").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
      rkey: jobId,
      source_id: "ndlIiif",
      source_name: `NDL IIIF page ${i + 1}/${canvases.length}`,
      source_url: webpUrl,
      format: "iiifImage",
      status: "pending",
      topics: JSON.stringify(topics),
      language,
      crawl_type: "ndlIiifPage",
      title: label ? `${label} (p.${i + 1})` : `NDL ${bibId} p.${i + 1}`,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
    screenshotJobs++;
  }

  // --- 3. OCR text extraction (if seeAlso/rendering has plain text or alto XML) ---
  let wetCount = 0;
  const ocrText = str(record.ocrText ?? "");
  const metadata = manifest.metadata as Array<{ label: string; value: string }> | undefined;
  if (ocrText) {
    const chunks = splitIntoParagraphs(ocrText, 256, 512);
    let currentSection = label || "NDL Document";
    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const headingMatch = chunk.match(/^(#{1,6})\s+(.+)$/m);
      if (headingMatch) currentSection = headingMatch[2];

      const iiifWetRkey = genID("wet");
      await getDb().insertInto("vertex_wet_chunk").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.wet/${iiifWetRkey}`,
        page_rkey: pageDid,
        url: ndlViewUrl,
        domain: hostname,
        chunk_index: i,
        total_chunks: chunks.length,
        markdown: truncateText(chunk, 10000),
        content_hash: simpleCID(chunk),
        language: language || "ja",
        title: label || `NDL ${bibId}`,
        section: currentSection,
        token_count: estimateTokens(chunk),
        crawled_at: nowISO(),
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
      wetCount++;
    }
  }

  // --- 4. WAT metadata record ---
  const metadataObj: Record<string, string> = {};
  if (metadata) {
    for (const m of metadata) {
      const mLabel = str(typeof m.label === "object" ? (m.label as any)?.["@value"] ?? m.label : m.label);
      const mValue = str(typeof m.value === "object" ? (m.value as any)?.["@value"] ?? m.value : m.value);
      if (mLabel && mValue) metadataObj[mLabel] = mValue;
    }
  }

  const iiifWatRkey = genID("wat");
  await getDb().insertInto("vertex_wat").values({
    vertex_id: `at://${appId}/com.etzhayyim.apps.site.wat/${iiifWatRkey}`,
    rkey: iiifWatRkey,
    url: ndlViewUrl,
    domain: hostname,
    language: language || "ja",
    content_type: "application/ld+json",
    status_code: "200",
    outlinks: JSON.stringify([manifestId]),
    og_description: description,
    sensitivity_ord: 2,
    owner_did: appId,
    created_date: nowISO().slice(0, 10),
  } as any).execute();

  // --- 5. Social post from topic coordinators ---
  const snippet = label
    ? `${label} (${canvases.length} pages)\n${ndlViewUrl}`
    : `NDL Digital Collection ${bibId} (${canvases.length} pages)\n${ndlViewUrl}`;
  for (const topicSlug of topics) {
    const topicDID = allTopicBySlug.get(topicSlug)?.did ?? topicBySlug.get(topicSlug)?.did ?? "";
    if (topicDID) postAs(sdk, topicDID, truncateText(snippet, 280));
  }

  // --- 6. Notify isbn.etzhayyim.com with book metadata (cross-actor) ---
  const isbn = metadataObj["ISBN"] ?? metadataObj["isbn"] ?? "";
  if (isbn || label) {
    const iiifPgRkey = genID("pg");
    await getDb().insertInto("vertex_page").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.page/${iiifPgRkey}`,
      rkey: iiifPgRkey,
      url: ndlViewUrl,
      domain: hostname,
      title: label,
      language: language || "ja",
      content_type: "iiifManifest",
      content_hash: simpleCID(manifestId),
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();
  }

  return { ok: true, detail: `iiifManifest: ${bibId} — ${screenshotJobs} image jobs, WET(${wetCount}), WAT, ${canvases.length} pages` };
}

/**
 * Extract image URL from a IIIF canvas object.
 * Supports both IIIF Presentation API 2.x and 3.0 structures.
 */
function extractIiifImageUrl(canvas: Record<string, unknown>, bibId: string, pageNum: number): string {
  // IIIF 2.x: canvas.images[0].resource["@id"]
  const images = (canvas.images ?? []) as Record<string, unknown>[];
  if (images.length > 0) {
    const resource = images[0].resource as Record<string, unknown> | undefined;
    if (resource) {
      const id = str(resource["@id"] ?? resource.id ?? "");
      if (id) return id;
    }
  }

  // IIIF 3.0: canvas.items[0].items[0].body.id
  const items = (canvas.items ?? []) as Record<string, unknown>[];
  if (items.length > 0) {
    const innerItems = (items[0].items ?? []) as Record<string, unknown>[];
    if (innerItems.length > 0) {
      const body = innerItems[0].body as Record<string, unknown> | undefined;
      if (body) {
        const id = str(body.id ?? body["@id"] ?? "");
        if (id) return id;
      }
    }
  }

  // Fallback: construct NDL IIIF Image URL from bibId + page number
  if (bibId) {
    return `https://dl.ndl.go.jp/api/iiif/${bibId}/R${String(pageNum).padStart(7, "0")}/full/1280,/0/default.jpg`;
  }

  return "";
}

/**
 * Convert a IIIF Image API URL to request resized dimensions.
 * IIIF Image API: {scheme}://{server}/{prefix}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}
 * NDL supports: `full/{w},` (width-constrained) but NOT `!{w},{h}` (best fit).
 */
function toIiifWebpUrl(imageUrl: string, maxWidth: number, _maxHeight: number): string {
  // If already a full IIIF Image API URL, replace size
  const iiifPattern = /^(https?:\/\/.+\/iiif\/[^/]+\/R\d+)\/(full|[\d,!]+)\/([\d,!pct:]+)\/(\d+)\/(default|bitonal|gray|color)\.(jpg|png|webp)$/;
  const match = imageUrl.match(iiifPattern);
  if (match) {
    return `${match[1]}/full/${maxWidth},/0/default.jpg`;
  }

  // If it's just an image service URL, append IIIF parameters
  if (imageUrl.includes("/iiif/") && !imageUrl.includes("/full/")) {
    return `${imageUrl}/full/${maxWidth},/0/default.jpg`;
  }

  return imageUrl;
}

// ── NDL SRU Catalog Search Processing ───────────────────────────────

/**
 * Process NDL SRU catalog search results (OpenSearch RSS XML).
 * Enumerates items and creates individual IIIF Manifest collection jobs for each PD work.
 *
 * NDL Search SRU: https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&query=...
 */
function processNdlSruCatalogResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  topics: string[],
): { ok: boolean; detail: string } {
  const content = str(record.content ?? record.text ?? record.body ?? "");
  if (!content) return { ok: true, detail: "ndlSruCatalog: no content" };

  const [orgId, userId] = ctxOrgUser(sdk);
  let enqueued = 0;
  const maxItems = Number(record.maxItems ?? 100);

  // Parse RSS/Atom items from NDL search response
  const items = xmlSplitTag(content, "item").concat(xmlSplitTag(content, "record"));

  for (const item of items) {
    if (enqueued >= maxItems) break;

    // Extract bibId from dc:identifier or link
    const identifiers = item.match(/<dc:identifier[^>]*>([^<]+)<\/dc:identifier>/g) ?? [];
    let bibId = "";
    for (const idTag of identifiers) {
      const val = idTag.replace(/<[^>]+>/g, "").trim();
      // NDL digital collection URL: https://dl.ndl.go.jp/pid/{bibId}
      const pidMatch = val.match(/dl\.ndl\.go\.jp\/(?:pid\/|info:ndljp\/pid\/)(\d+)/);
      if (pidMatch) { bibId = pidMatch[1]; break; }
      // NDL info URI: info:ndljp/pid/{bibId}
      const infoMatch = val.match(/info:ndljp\/pid\/(\d+)/);
      if (infoMatch) { bibId = infoMatch[1]; break; }
    }

    // Also check <link> for bibId
    if (!bibId) {
      const linkMatch = item.match(/<link[^>]*>([^<]*)<\/link>/);
      if (linkMatch) {
        const pidMatch = linkMatch[1].match(/dl\.ndl\.go\.jp\/(?:pid\/|info:ndljp\/pid\/)(\d+)/);
        if (pidMatch) bibId = pidMatch[1];
      }
    }

    if (!bibId) continue;

    const title = xmlExtractTag(item, "title") ?? xmlExtractTag(item, "dc:title") ?? "";
    const creator = xmlExtractTag(item, "dc:creator") ?? xmlExtractTag(item, "author") ?? "";

    // Enqueue IIIF Manifest fetch job for this bibId
    const manifestUrl = `https://dl.ndl.go.jp/api/iiif/${bibId}/manifest.json`;
    const jobId = genID("cj");

    await getDb().insertInto("vertex_collection_job").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.collectionJob/${jobId}`,
      rkey: jobId,
      source_id: "ndl",
      source_name: `NDL: ${truncateText(stripHTML(title), 80)}`,
      source_url: manifestUrl,
      format: "iiifManifest",
      status: "pending",
      topics: JSON.stringify(topics),
      language: "ja",
      crawl_type: "ndlSruCatalog",
      title: stripHTML(title),
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();

    enqueued++;
  }

  // Social announcement
  if (enqueued > 0) {
    const topicDID = allTopicBySlug.get("jpClassics")?.did ?? topicBySlug.get("jpClassics")?.did ?? "";
    if (topicDID) postAs(sdk, topicDID, `NDL SRU catalog: ${enqueued} IIIF manifests enqueued for processing`);
  }

  return { ok: true, detail: `ndlSruCatalog: enqueued ${enqueued} IIIF manifest jobs` };
}

/** Split XML by tag name, returning an array of inner content strings. */
function xmlSplitTag(xml: string, tagName: string): string[] {
  const regex = new RegExp(`<${tagName}[^>]*>([\\s\\S]*?)<\\/${tagName}>`, "gi");
  const results: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = regex.exec(xml)) !== null) {
    results.push(match[1]);
  }
  return results;
}

/** Extract text content of the first occurrence of a tag. */
function xmlExtractTag(xml: string, tagName: string): string {
  const regex = new RegExp(`<${tagName}[^>]*>([\\s\\S]*?)<\\/${tagName}>`, "i");
  const match = xml.match(regex);
  return match ? match[1].trim() : "";
}

/** Fetch and process a PDF document: pages → WebP (R2 CDN), text → WET. */
async function cmdFetchPdf(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.fetchPdf", payload);
  if (!req.url) return encodeJson({ error: "url is required" });

  // Dedup: createCollectionJob uses URL-derived deterministic rkey (PDS upsert = idempotent)
  const topics = req.topics ?? classifyTopics(req.url, req.title ?? "", "");
  const jobId = createCollectionJob(sdk, "pdf", req.url, "pdf", topics, {
    'crawlType': "pdfIngest",
    title: req.title ?? "",
    language: req.language ?? "ja",
  });

  const topicDID = topics.length > 0
    ? (allTopicBySlug.get(topics[0])?.did ?? topicBySlug.get(topics[0])?.did ?? "")
    : "";
  if (topicDID) await postAs(sdk, topicDID, truncateText(`PDF collection job created: ${req.url}`, 280));

  return encodeJson({ status: "pending", jobId, url: req.url, topics });
}

// --- New Commands: WET/WAT/Screenshot/Robots/Seed/Embedding ---

function cmdGenerateWET(sdk: HostSDK, payload: Uint8Array): Uint8Array {
  const req = parseLexiconInput("com.etzhayyim.apps.site.generateWet", payload);
  if (!req.url || !req.html) return encodeJson({ error: "url and html are required" });

  const hostname = new URL(req.url).hostname;
  const slug = hostname.replace(/[^a-z0-9]/g, "-");
  const topics = req.topics ?? classifyTopics(req.url, req.title ?? "", req.html);
  const language = req.language ?? detectLanguageSimple(req.html);

  const chunkCount = generateWET(sdk, req.url, req.html, {
    title: req.title ?? extractHtmlMeta(req.html).title,
    language,
    topics,
    pageDid: `did:web:${appId}.etzhayyim.com:${slug}`,
    domainDid: `did:web:${appId}.etzhayyim.com:${slug}`,
  });

  return encodeJson({ status: "ok", url: req.url, 'wetChunks': chunkCount, topics });
}

function cmdGenerateWAT(sdk: HostSDK, payload: Uint8Array): Uint8Array {
  const req = parseLexiconInput("com.etzhayyim.apps.site.generateWat", payload);
  if (!req.url || !req.html) return encodeJson({ error: "url and html are required" });

  const hostname = new URL(req.url).hostname;
  const slug = hostname.replace(/[^a-z0-9]/g, "-");

  generateWAT(sdk, req.url, req.html, {
    statusCode: req.statusCode ?? 200,
    mimeType: req.mimeType ?? "text/html",
    httpHeaders: req.httpHeaders ?? "{}",
    pageDid: `did:web:${appId}.etzhayyim.com:${slug}`,
    domainDid: `did:web:${appId}.etzhayyim.com:${slug}`,
    wetChunkCount: 0,
  });

  return encodeJson({ status: "ok", url: req.url });
}

async function cmdCaptureScreenshot(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.captureScreenshot", payload);
  if (!req.url) return encodeJson({ error: "url is required" });

  const topics = req.topics ?? ["academic"];
  const jobId = await captureScreenshotJob(sdk, req.url, topics);
  return encodeJson({ status: "pending", 'jobId': jobId, url: req.url });
}

async function cmdCheckRobotsTxt(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.checkRobotsTxt", payload);
  if (!req.domain) return encodeJson({ error: "domain is required" });

  // TODO(site): vertex_robots_txt not in @etzhayyim/graph-schema — always cache-miss, falls through to fetch
  const cached: Array<Record<string, unknown>> = [];

  if (cached.length > 0 && str(cached[0].expiresAt) > nowISO()) {
    const rules: RobotsTxtRules = JSON.parse(str(cached[0].rules ?? '{"rules":[],"crawlDelay":1,"sitemapUrls":[]}'));
    const allowed = req.path ? isUrlAllowed(rules, req.path) : true;
    return encodeJson({ domain: req.domain, cached: true, allowed, 'crawlDelay': rules.crawlDelay });
  }

  const jobId = createCollectionJob(sdk, "crawl", `https://${req.domain}/robots.txt`, "robotsTxt", [], {
    'crawlType': "robotsTxt",
    'targetDomain': req.domain,
  });

  return encodeJson({ domain: req.domain, cached: false, status: "fetching", 'jobId': jobId });
}

async function cmdSeedFromCommonCrawl(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.seedFromCommonCrawl", payload);
  const limit = Math.min(req.limit ?? 10000, 100000);
  const ccIndex = req.ccIndex ?? "CC-MAIN-2024-51";

  const jobId = await createCollectionJob(sdk, "commonCrawl", `https://data.commoncrawl.org/cc-index/collections/${ccIndex}/indexes/cdx-00000.gz`, "cdxIndex", [], {
    'crawlType': "commonCrawlSeed",
    'ccIndex': ccIndex,
    'domainFilter': req.domainFilter ?? "",
    'maxUrls': limit,
  });

  await postAs(sdk, topicBySlug.get("academic")?.did ?? "", `Common Crawl seed started: ${ccIndex}, limit ${limit}${req.domainFilter ? `, filter: ${req.domainFilter}` : ""}`);

  return encodeJson({ status: "pending", 'jobId': jobId, 'ccIndex': ccIndex, limit });
}

// ── ingestGeoData: structured geo data ingest via CollectionJob ──

/**
 * Emit a geoRecord AT record (com.etzhayyim.apps.site.geoRecord) for a single geo entity.
 * Received by subscriber apps (e.g. maps.etzhayyim.com) via handleComAtprotoSyncSubscribeReposCommit.
 */
async function emitGeoRecord(sdk: HostSDK, fields: {
  project: string; format: string; entityType: string; entityId: string;
  name: string; nameEn?: string; lat?: number; lng?: number;
  codes?: Record<string, string>; extra?: Record<string, unknown>;
}): Promise<void> {
  // Use full NSID so expandCollection passes it through unchanged → com.etzhayyim.apps.site.geoRecord
  await sdk.pds.comAtprotoRepoCreateRecord("com.etzhayyim.apps.site.geoRecord", {
    id: genID("gr"),
    project: fields.project,
    format: fields.format,
    entityType: fields.entityType,
    entityId: fields.entityId,
    name: fields.name,
    nameEn: fields.nameEn ?? "",
    lat: String(fields.lat ?? 0),
    lng: String(fields.lng ?? 0),
    codesJson: JSON.stringify(fields.codes ?? {}),
    extraJson: JSON.stringify(fields.extra ?? {}),
    orgId: "anon", userId: "anon", actorId: appId,
    createdAt: nowISO(),
  });
}

/**
 * Process USGS Earthquake GeoJSON feed (format: "usgs_geojson").
 * Emits geoRecord{entityType:"seismicEvent"} per earthquake feature.
 */
async function processUsgsGeoJsonResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  content: string,
): Promise<{ ok: boolean; detail: string }> {
  let data: Record<string, unknown>;
  try { data = JSON.parse(content); } catch {
    return { ok: true, detail: "usgs_geojson: invalid json" };
  }
  const features = (data.features as any[]) ?? [];
  const project = str(record.project ?? "maps");
  let count = 0;
  for (const feat of features) {
    const props = (feat.properties ?? {}) as Record<string, unknown>;
    const coords = (feat.geometry?.coordinates ?? []) as number[];
    if (coords.length < 2) continue;
    const [lng, lat, depth] = coords;
    const mag = Number(props.mag ?? 0);
    const place = str(props.place ?? "");
    const eventId = str(props.ids ?? props.code ?? genID("usgs"));
    await emitGeoRecord(sdk, {
      project,
      format: "usgs_geojson",
      entityType: "seismicEvent",
      entityId: eventId.replace(/^,|,$/g, "").split(",")[0] || eventId,
      name: `M${mag.toFixed(1)} ${place}`,
      lat, lng,
      codes: {},
      extra: {
        magnitude: mag, magnitudeType: str(props.magType ?? ""),
        depth: depth ?? 0, place,
        time: Number(props.time ?? 0),
        alert: str(props.alert ?? ""), tsunami: Number(props.tsunami ?? 0),
        sig: Number(props.sig ?? 0), status: str(props.status ?? ""),
      },
    });
    count++;
  }
  return { ok: true, detail: `usgs_geojson: emitted ${count} seismic geoRecords` };
}

/**
 * Process Wikidata SPARQL JSON results (format: "wikidata_sparql").
 * Supports two binding patterns:
 *   - JP municipality: ?name (ja), ?jis (JIS X 0402), ?lat, ?lng
 *   - World AdminArea tier-2: ?name (en), ?code (ISO 3166-2), ?lat, ?lng
 * Emits geoRecord{entityType:"municipality"|"adminArea2"} per binding.
 */
async function processWikidataSparqlResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  content: string,
): Promise<{ ok: boolean; detail: string }> {
  let data: Record<string, unknown>;
  try { data = JSON.parse(content); } catch {
    return { ok: true, detail: "wikidata_sparql: invalid json" };
  }
  const bindings = ((data.results as any)?.bindings ?? []) as Array<Record<string, { value: string }>>;
  const project = str(record.project ?? "maps");
  const seen = new Set<string>();
  let municipalities = 0;
  let adminAreas = 0;
  for (const b of bindings) {
    const name = b.name?.value ?? "";
    if (!name) continue;
    const lat = Number(b.lat?.value ?? 0);
    const lng = Number(b.lng?.value ?? 0);

    // JP municipality: ?jis binding (JIS X 0402)
    if (b.jis?.value) {
      const jis = b.jis.value;
      if (seen.has(jis)) continue;
      seen.add(jis);
      const prefCode = jis.slice(0, 2);
      await emitGeoRecord(sdk, {
        project, format: "wikidata_sparql",
        entityType: "municipality", entityId: jis,
        name, lat, lng,
        codes: { "jis-x0402": jis, "iso3166-2": `jp-${prefCode}` },
      });
      municipalities++;
      continue;
    }

    // World AdminArea tier-2: ?code binding (ISO 3166-2)
    if (b.code?.value) {
      const code = b.code.value;
      if (seen.has(code)) continue;
      seen.add(code);
      const nameEn = b.nameEn?.value ?? name;
      await emitGeoRecord(sdk, {
        project, format: "wikidata_sparql",
        entityType: "adminArea2", entityId: code,
        name, nameEn, lat, lng,
        codes: { "iso3166-2": code },
      });
      adminAreas++;
      continue;
    }
  }
  return { ok: true, detail: `wikidata_sparql: emitted ${municipalities} municipalities, ${adminAreas} adminArea2 geoRecords` };
}

/**
 * Process OurAirports CSV (format: "ourairports_csv").
 * Source: https://davidmegginson.github.io/ourairports-data/airports.csv
 * Filters: large_airport + medium_airport with IATA codes.
 * Emits geoRecord{entityType:"airport"} per airport.
 */
async function processOurAirportsCsvResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  content: string,
): Promise<{ ok: boolean; detail: string }> {
  const lines = content.split("\n");
  if (lines.length < 2) return { ok: true, detail: "ourairports_csv: no data rows" };
  const project = str(record.project ?? "maps");
  // Parse header to find column indices
  const header = parseCsvRow(lines[0]);
  const col = (name: string) => header.indexOf(name);
  const idxIdent = col("ident"); // ICAO 4-letter
  const idxType = col("type");
  const idxName = col("name");
  const idxLat = col("latitude_deg");
  const idxLng = col("longitude_deg");
  const idxElev = col("elevation_ft");
  const idxCountry = col("iso_country");
  const idxRegion = col("iso_region");
  const idxIata = col("iata_code");
  const idxMuni = col("municipality");
  let count = 0;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = parseCsvRow(line);
    const airportType = cols[idxType] ?? "";
    if (airportType !== "large_airport" && airportType !== "medium_airport") continue;
    const icao = cols[idxIdent] ?? "";
    const iata = cols[idxIata] ?? "";
    if (!icao || !iata) continue;
    const name = cols[idxName] ?? "";
    const lat = Number(cols[idxLat] ?? 0);
    const lng = Number(cols[idxLng] ?? 0);
    if (!name || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    await emitGeoRecord(sdk, {
      project, format: "ourairports_csv",
      entityType: "airport", entityId: icao,
      name, lat, lng,
      codes: { "icao-airport": icao, "iata-airport": iata },
      extra: {
        airportType,
        elevation: Number(cols[idxElev] ?? 0),
        country: cols[idxCountry] ?? "",
        region: cols[idxRegion] ?? "",
        municipality: cols[idxMuni] ?? "",
      },
    });
    count++;
  }
  return { ok: true, detail: `ourairports_csv: emitted ${count} airport geoRecords` };
}

/** Simple CSV row parser (handles double-quoted fields with embedded commas). */
function parseCsvRow(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else { inQuotes = !inQuotes; }
    } else if (ch === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

/**
 * Process OpenSky Network ADS-B JSON (format: "opensky_json").
 * Source: https://opensky-network.org/api/states/all?lamin=...&lomin=...&lamax=...&lomax=...
 * Emits geoRecord{entityType:"aircraft"} per airborne aircraft.
 */
async function processOpenSkyJsonResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  content: string,
): Promise<{ ok: boolean; detail: string }> {
  let data: { time?: number; states?: Array<(string | number | boolean | null)[]> };
  try { data = JSON.parse(content); } catch {
    return { ok: true, detail: "opensky_json: invalid json" };
  }
  const states = data.states ?? [];
  const project = str(record.project ?? "maps");
  let count = 0;
  for (const s of states) {
    if (!Array.isArray(s) || s.length < 7) continue;
    const icao24 = String(s[0] ?? "");
    const callsign = String(s[1] ?? "").trim();
    const originCountry = String(s[2] ?? "");
    const lng = Number(s[5]);
    const lat = Number(s[6]);
    const baroAlt = Number(s[7] ?? 0);
    const onGround = Boolean(s[8]);
    const velocity = Number(s[9] ?? 0);
    const heading = Number(s[10] ?? 0);
    if (!icao24 || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    if (onGround) continue; // skip ground positions
    await emitGeoRecord(sdk, {
      project, format: "opensky_json",
      entityType: "aircraft", entityId: `${icao24}:${data.time ?? 0}`,
      name: callsign || icao24,
      lat, lng,
      codes: {},
      extra: { icao24, callsign, originCountry, altitude: baroAlt, velocity, heading, onGround, time: data.time ?? 0 },
    });
    count++;
  }
  return { ok: true, detail: `opensky_json: emitted ${count} aircraft geoRecords` };
}

/**
 * Process STAC API search results (format: "stac_search_json").
 * Input: GeoJSON FeatureCollection from STAC /search endpoint (Element84, NASA CMR, etc.).
 * Emits geoRecord{entityType:"satelliteScene"} per feature with thumbnailUrl, cogUrl, bbox.
 */
async function processStacSearchResult(
  sdk: HostSDK,
  record: Record<string, unknown>,
  content: string,
): Promise<{ ok: boolean; detail: string }> {
  let data: { features?: any[]; context?: unknown };
  try { data = JSON.parse(content); } catch {
    return { ok: true, detail: "stac_search_json: invalid json" };
  }
  const features = data.features ?? [];
  const project = str(record.project ?? "maps");
  let count = 0;
  for (const feat of features) {
    const props = (feat.properties ?? {}) as Record<string, unknown>;
    const sceneId = str(feat.id ?? "");
    if (!sceneId) continue;

    // Derive bbox center from geometry or bbox array
    const geomCoords: number[][] = (feat.geometry?.coordinates?.[0] ?? []) as number[][];
    const bboxArr: number[] | undefined = feat.bbox;
    let latMin = 0, latMax = 0, lngMin = 0, lngMax = 0;
    if (bboxArr && bboxArr.length >= 4) {
      [lngMin, latMin, lngMax, latMax] = bboxArr;
    } else if (geomCoords.length > 0) {
      lngMin = Math.min(...geomCoords.map(c => c[0]));
      lngMax = Math.max(...geomCoords.map(c => c[0]));
      latMin = Math.min(...geomCoords.map(c => c[1]));
      latMax = Math.max(...geomCoords.map(c => c[1]));
    }
    const lat = (latMin + latMax) / 2;
    const lng = (lngMin + lngMax) / 2;

    // STAC common properties
    const acquisitionDate = str(props.datetime ?? props["start_datetime"] ?? "");
    const cloudCover = Number(props["eo:cloud_cover"] ?? props.cloudCover ?? 0);
    const satellite = str(props.platform ?? props.constellation ?? record.satellite ?? "unknown");

    // Extract thumbnail and COG from assets
    const assets = (feat.assets ?? {}) as Record<string, { href?: string }>;
    const thumbnailUrl = str(
      assets.thumbnail?.href ?? assets.overview?.href ??
      assets.rendered_preview?.href ?? assets.visual?.href ?? "",
    );
    const cogUrl = str(
      assets.B04?.href ?? assets.red?.href ?? assets.visual?.href ??
      assets.B02?.href ?? assets.blue?.href ?? "",
    );

    await emitGeoRecord(sdk, {
      project, format: "stac_search_json",
      entityType: "satelliteScene", entityId: sceneId,
      name: `${satellite} ${acquisitionDate.slice(0, 10)}`,
      lat, lng,
      codes: {},
      extra: {
        sceneId, satellite, acquisitionDate,
        cloudCover, thumbnailUrl, cogUrl,
        bboxJson: JSON.stringify({ latMin, latMax, lngMin, lngMax }),
        stacCollectionId: str(record.stacCollectionId ?? props["s2:mgrs_tile"] ?? ""),
      },
    });
    count++;
  }
  return { ok: true, detail: `stac_search_json: emitted ${count} satelliteScene geoRecords` };
}

/**
 * ingestGeoData: create a CollectionJob for a structured geo data URL.
 * formats: "usgs_geojson" (USGS earthquake feed) | "wikidata_sparql" (Wikidata SPARQL response)
 * The host executor fetches the URL → fills content → handleCommit processes the result.
 */
async function cmdIngestGeoData(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.ingestGeoData", payload);

  if (!req.url || !req.format) {
    return encodeJson({ error: "url and format are required" });
  }
  const supported = ["usgs_geojson", "wikidata_sparql", "ourairports_csv", "opensky_json", "stac_search_json"];
  if (!supported.includes(req.format)) {
    return encodeJson({ error: `unsupported format: ${req.format}. supported: ${supported.join(", ")}` });
  }

  const jobId = genID("geoIngest");

  // Fetch and process inline (host executor doesn't handle geo- source types)
  let content = "";
  try {
    const resp = await fetch(req.url);
    if (!resp.ok) {
      console.warn(`[ingestGeoData] fetch failed: ${resp.status} ${req.url}`);
      return encodeJson({ status: "fetch_error", jobId, url: req.url, httpStatus: resp.status });
    }
    content = await resp.text();
  } catch (e) {
    console.warn(`[ingestGeoData] fetch exception: ${e} ${req.url}`);
    return encodeJson({ status: "fetch_error", jobId, url: req.url, error: String(e) });
  }

  if (!content) {
    return encodeJson({ status: "empty", jobId, url: req.url });
  }

  const syntheticRecord: Record<string, unknown> = {
    status: "completed",
    content,
    format: req.format,
    sourceUrl: req.url,
    project: req.project ?? "",
    satellite: req.satellite ?? "",
    stacCollectionId: req.stacCollectionId ?? "",
    callerDid: req.callerDid ?? "",
  };

  let result: { ok: boolean; detail: string };
  try {
    if (req.format === "usgs_geojson") {
      result = await processUsgsGeoJsonResult(sdk, syntheticRecord, content);
    } else if (req.format === "wikidata_sparql") {
      result = await processWikidataSparqlResult(sdk, syntheticRecord, content);
    } else if (req.format === "ourairports_csv") {
      result = await processOurAirportsCsvResult(sdk, syntheticRecord, content);
    } else if (req.format === "opensky_json") {
      result = await processOpenSkyJsonResult(sdk, syntheticRecord, content);
    } else if (req.format === "stac_search_json") {
      result = await processStacSearchResult(sdk, syntheticRecord, content);
    } else {
      result = { ok: false, detail: `unknown format: ${req.format}` };
    }
  } catch (e) {
    console.error(`[ingestGeoData] process error: ${e}`);
    result = { ok: false, detail: `process error: ${String(e)}` };
  }

  return encodeJson({ status: result.ok ? "ok" : "error", jobId, url: req.url, format: req.format, detail: result.detail });
}

// ── seedForProject: project-driven domain crawl + CommonCrawl fallback ──

async function cmdSeedForProject(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.seedForProject", payload);
  if (!req.project || !req.domains || req.domains.length === 0) {
    return encodeJson({ error: "project and domains[] are required" });
  }

  const topics = req.topics ?? [req.project];
  const ccIndex = req.ccIndex ?? "CC-MAIN-2024-51";
  const maxPages = Math.min(req.maxPagesPerDomain ?? 200, 500);
  const priority = req.priority ?? 40;
  const [orgId, userId] = ctxOrgUser(sdk);

  const results: Array<{ domain: string; action: string; pageCount: number }> = [];

  for (const domain of req.domains) {
    // Check if domain already crawled with sufficient pages
    let existingPages = 0;
    try {
      // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — derive pageCount from view
      const existing = await (createKyselyDb() as any)
        .selectFrom("view_page_count_by_domain")
        .select("cnt")
        .where("domain", "=", domain)
        .execute()
        .catch(() => [] as Array<{ cnt: string }>);
      existingPages = Number(existing[0]?.cnt ?? 0);
    } catch { /* graph empty or schema not yet populated */ }

    if (existingPages >= 10) {
      // Domain already has meaningful data — skip live crawl, just notify
      results.push({ domain, action: "existing", pageCount: existingPages });
      continue;
    }

    // Register domain DID
    const slug = domain.replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
    const did = str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
      displayName: domain,
      description: `Project crawl: ${req.project} — ${domain}`,
      category: "content",
    })));

    // Create domain record
    try {
      await getDb().insertInto("vertex_web_domain" as any).values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.domain/${slug}`,
        domain,
        slug,
        did: did || `did:web:${appId}.etzhayyim.com:${slug}`,
        topics: JSON.stringify(topics),
        page_count: 0,
        sensitivity_ord: 2,
        owner_did: appId,
        first_seen: nowISO(),
        last_crawled: nowISO(),
        created_date: nowISO().slice(0, 10),
      }).execute();
    } catch (e) { console.warn("vertex_web_domain insert:", e); }

    // Enqueue seed URL at priority
    const projFeRkey = genID("fe");
    await getDb().insertInto("vertex_frontier").values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${projFeRkey}`,
      rkey: projFeRkey,
      url: `https://${domain}/`,
      domain,
      status: "pending",
      priority,
      depth: 0,
      topics: JSON.stringify(topics),
      source: "seedForProject",
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    } as any).execute();

    // Also seed from CommonCrawl for this domain (catch historical pages)
    const ccJobId = await createCollectionJob(sdk, "commonCrawl",
      `https://data.commoncrawl.org/cc-index/collections/${ccIndex}/indexes/cdx-00000.gz`,
      "cdxIndex", topics, {
        'crawlType': "projectSeed",
        'ccIndex': ccIndex,
        'domainFilter': domain,
        'maxUrls': maxPages,
        project: req.project,
      },
    );

    results.push({ domain, action: "seeded", pageCount: 0, ccJobId });
  }

  const seeded = results.filter(r => r.action === "seeded").length;
  const existing = results.filter(r => r.action === "existing").length;

  await postAs(sdk, topicBySlug.get("technology")?.did ?? "",
    `[SeedForProject] ${req.project}: ${seeded} domains seeded, ${existing} already crawled\ncc @${req.project}.etzhayyim.com`);

  return encodeJson({ status: "ok", project: req.project, results, seeded, existing, 'ccIndex': ccIndex });
}

// ── seedGovPdfs: bulk seed government PDF URLs from CC vertex_page ──
const GOV_TLD_SUFFIXES = [
  ".go.jp", ".gov", ".gov.uk", ".gouv.fr", ".bund.de", ".gov.it", ".gc.ca",
  ".gov.au", ".gov.br", ".gob.mx", ".gov.in", ".gov.cn", ".go.kr",
  ".gov.za", ".gov.ar", ".gov.tr", ".gov.ru", ".go.id", ".gov.sa",
  ".europa.eu",
  ".un.org", ".who.int", ".ilo.org", ".wipo.int", ".wto.org", ".imf.org", ".worldbank.org",
  ".oecd.org", ".nato.int",
];
async function cmdSeedGovPdfs(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.seedGovPdfs", payload);
  const limit = Math.min(req.limit ?? 200, 1000);
  const offset = req.offset ?? 0;
  const priority = req.priority ?? 60;
  const [orgId, userId] = ctxOrgUser(sdk);
  // Query pages by exact domain match (bloom filter safe, no full scan)
  // If caller provides specific domains, use those; otherwise use well-known gov domains
  const govDomains = req.tldPattern ? [req.tldPattern] : [
    "www.mlit.go.jp", "www.soumu.go.jp", "www.moj.go.jp", "www.mof.go.jp", "www.mhlw.go.jp",
    "www.maff.go.jp", "www.meti.go.jp", "www.env.go.jp", "www.mod.go.jp", "www.mofa.go.jp",
    "www.cas.go.jp", "www.cao.go.jp", "www.npa.go.jp", "www.courts.go.jp",
    "europa.eu", "www.usa.gov", "www.gov.uk", "www.gouvernement.fr",
    "www.un.org", "www.who.int", "www.oecd.org", "www.imf.org", "www.worldbank.org",
    "www.wipo.int", "www.wto.org", "www.ilo.org",
  ];
  const batch = govDomains.slice(offset, offset + Math.min(govDomains.length, 50));
  const safeLimit = Math.max(1, Math.min(Math.floor(limit), 10000));
  let rows: Array<{ url: string; domain: string; title: string; language: string }>;
  try {
    const db = createKyselyDb();
    const result = await db
      .selectFrom("vertex_page")
      .select(["url", "domain", "title", "language"])
      .where("domain", "in", batch)
      .where("content_type", "=", "application/pdf")
      .orderBy("domain")
      .limit(safeLimit)
      .execute();
    rows = result.map(r => ({
      url: String(r.url ?? ""),
      domain: String(r.domain ?? ""),
      title: String(r.title ?? ""),
      language: String(r.language ?? ""),
    }));
  } catch (e: any) {
    throw new Error(`seedGovPdfs query failed: ${e?.message || e}`);
  }
  // Dedup: createCollectionJob uses URL-derived deterministic rkey (PDS upsert = idempotent)
  let enqueued = 0;
  let skipped = 0;
  const domainCounts: Record<string, number> = {};
  const registeredDomains = new Set<string>();
  for (const row of rows) {
    const url = str(row.url); const domain = str(row.domain); const title = str(row.title); const language = str(row.language) || "en";
    if (!url) continue;
    // Register domain DID if not yet done in this batch
    if (domain && !registeredDomains.has(domain)) {
      registeredDomains.add(domain);
      const slug = domain.replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
      sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
        displayName: domain,
        description: `Government domain: ${domain}`,
        category: "government",
      }));
      try {
        await getDb().insertInto("vertex_web_domain" as any).values({
          vertex_id: `at://${appId}/com.etzhayyim.apps.site.domain/${slug}`,
          domain,
          slug,
          did: `did:web:${appId}.etzhayyim.com:${slug}`,
          topics: JSON.stringify(["government", "legal"]),
          page_count: 0,
          sensitivity_ord: 2,
          owner_did: appId,
          first_seen: nowISO(),
          last_crawled: nowISO(),
          created_date: nowISO().slice(0, 10),
        }).execute();
      } catch (e) { console.warn("vertex_web_domain insert:", e); }
    }
    const topics = classifyTopics(url, title, "");
    if (!topics.includes("government")) topics.unshift("government");
    if (!topics.includes("legal")) topics.push("legal");
    createCollectionJob(sdk, "pdf", url, "pdf", topics, { 'crawlType': "govPdfSeed", title, language, priority });
    domainCounts[domain] = (domainCounts[domain] ?? 0) + 1;
    enqueued++;
  }
  const govDID = allTopicBySlug.get("government")?.did ?? "";
  if (govDID && enqueued > 0) {
    const topDomains = Object.entries(domainCounts).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([d, c]) => `${d}(${c})`).join(", ");
    await postAs(sdk, govDID, truncateText(`[GovPDF] ${enqueued} government PDFs seeded for WebP+WET processing.\nTop: ${topDomains}`, 280));
  }
  return encodeJson({ status: "ok", enqueued, skipped, queried: rows.length, offset, limit, domainCounts });
}

async function cmdTriggerTextEmbedding(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.triggerTextEmbedding", payload);
  const batchSize = Math.min(req.batchSize ?? 50, 200);

  // Query unembedded WetChunk nodes (vertex_wet_chunk with embedding IS NULL)
  // TODO(site): page_did not promoted on vertex_wet_chunk — use page_rkey instead
  const rows = await createKyselyDb()
    .selectFrom("vertex_wet_chunk")
    .select(["vertex_id as vid", "markdown", "language", "page_rkey as pageDid"])
    .where("embedding", "is", null)
    .limit(batchSize)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>);

  // Fallback: also check legacy WpgWET without embeddedAt
  // TODO(site): vertex_wpg_wet not in @etzhayyim/graph-schema — legacy path returns empty
  if (rows.length === 0) {
    const legacyRows: Array<Record<string, unknown>> = [];
    for (const row of legacyRows) {
      sdk.pds.dispatch({
        type: "invoke",
        payload: {
          did: "did:web:murakumo.etzhayyim.com",
          method: "embed-text",
          params: JSON.stringify({ text: str(row.markdown), model: resolveModelId("qwen3-vl-8b"), 'wetId': str(row.id) }),
        },
      });
    }
    return encodeJson({ status: "ok", triggered: legacyRows.length, 'batchSize': batchSize, source: "legacy" });
  }

  for (const row of rows) {
    sdk.pds.dispatch({
      type: "invoke",
      payload: {
        did: "did:web:murakumo.etzhayyim.com",
        method: "embed-text",
        params: JSON.stringify({
          text: str(row.markdown),
          model: resolveModelId("qwen3-vl-8b"),
          'chunkVertexId': str(row.vid),
          'pageDid': str(row.pageDid),
          'writeBackCollection': "com.etzhayyim.apps.site.wetChunkEmbedding",
        }),
      },
    });
  }

  return encodeJson({ status: "ok", triggered: rows.length, 'batchSize': batchSize, source: "wetChunk" });
}

async function cmdTriggerVisualEmbedding(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.triggerVisualEmbedding", payload);
  const batchSize = Math.min(req.batchSize ?? 20, 100);

  // TODO(site): embedded_at / embedding not promoted on vertex_screenshot — return empty until schema extension
  void batchSize;
  const rows: Array<Record<string, unknown>> = [];

  for (const row of rows) {
    sdk.pds.dispatch({
      type: "invoke",
      payload: {
        did: "did:web:murakumo.etzhayyim.com",  // Invoke target
        method: "embed-visual",
        params: JSON.stringify({ 'blobRef': str(row.blobRef), 'screenshotId': str(row.id) }),
      },
    });
  }

  return encodeJson({ status: "ok", triggered: rows.length, 'batchSize': batchSize });
}

async function cmdRegisterWebTopic(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.registerWebTopic", payload);
  if (!req.slug || !req.name) return encodeJson({ error: "slug and name are required" });

  const did = str(sdk.hostImports.comAtprotoIdentityCreate(`topic:${req.slug}`, JSON.stringify({
    displayName: req.name,
    description: req.description ?? `Web topic: ${req.name}`,
    category: "content",
  })));

  try {
    await getDb().insertInto("vertex_web_topic" as any).values({
      vertex_id: `at://${appId}/com.etzhayyim.apps.site.topic/${req.slug}`,
      topic: req.slug,
      slug: req.slug,
      did: did || `did:web:${appId}.etzhayyim.com:topic:${req.slug}`,
      name: req.name,
      description: req.description ?? "",
      source_count: 0,
      sensitivity_ord: 2,
      owner_did: appId,
      created_date: nowISO().slice(0, 10),
    }).execute();
  } catch (e) { console.warn("vertex_web_topic insert:", e); }

  return encodeJson({ status: "registered", slug: req.slug, did });
}

async function processCDXSeedResult(sdk: HostSDK, record: Record<string, unknown>, content: string): Promise<{ ok: boolean; detail: string }> {
  const domainFilter = str(record.domainFilter ?? "");
  const maxUrls = Number(record.maxUrls ?? 10000);
  const [orgId, userId] = ctxOrgUser(sdk);

  const lines = content.split("\n").filter(l => l.trim().length > 0);
  let enqueued = 0;

  for (const line of lines) {
    if (enqueued >= maxUrls) break;
    // CDX format: SURT_URL timestamp JSON_metadata
    const parts = line.split(" ", 3);
    if (parts.length < 3) continue;

    try {
      const meta = JSON.parse(parts[2]);
      const url = str(meta.url ?? "");
      const status = Number(meta.status ?? 0);
      const mimeType = str(meta.mime ?? "");

      if (!url || status !== 200) continue;
      if (!mimeType.includes("text/html")) continue;
      if (domainFilter && !url.includes(domainFilter)) continue;

      const cdxFeRkey = genID("fe");
      await getDb().insertInto("vertex_frontier").values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${cdxFeRkey}`,
        rkey: cdxFeRkey,
        url,
        domain: new URL(url).hostname,
        status: "pending",
        priority: 30,
        depth: 0,
        topics: "[]",
        source: "commonCrawl",
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      } as any).execute();
      enqueued++;
    } catch { /* skip malformed CDX lines */ }
  }

  return { ok: true, detail: `common crawl seed: enqueued ${enqueued} URLs from ${lines.length} CDX lines` };
}

async function cmdGetCrawlOutputStats(sdk: HostSDK, _payload: Uint8Array): Promise<Uint8Array> {
  // Read from streaming MVs — no per-request full-table scans.
  const db = createKyselyDb();
  // TODO(site): vertex_wpg_wet not in @etzhayyim/graph-schema — mv_site_wet_chunk_total covers vertex_wet_chunk
  const wetRow = await (db as any).selectFrom("mv_site_wet_chunk_total").select("cnt").executeTakeFirst()
    .catch(() => undefined as { cnt: string } | undefined);
  const wetCount = [{ cnt: wetRow?.cnt ?? "0" }];
  const watRow = await (db as any).selectFrom("mv_site_wat_total").select("cnt").executeTakeFirst()
    .catch(() => undefined as { cnt: string } | undefined);
  const watCount = [{ cnt: watRow?.cnt ?? "0" }];
  const ssRow = await (db as any).selectFrom("mv_site_screenshot_total").select("cnt").executeTakeFirst()
    .catch(() => undefined as { cnt: string } | undefined);
  const ssCount = [{ cnt: ssRow?.cnt ?? "0" }];
  // TODO(site): language / topic aggregates on vertex_wet_chunk — group by skipped until needed
  const wetByLang: Array<Record<string, unknown>> = [];
  const wetByTopic: Array<Record<string, unknown>> = [];

  return encodeJson({
    'wetCount': Number(wetCount[0]?.cnt ?? 0),
    'watCount': Number(watCount[0]?.cnt ?? 0),
    'screenshotCount': Number(ssCount[0]?.cnt ?? 0),
    'wetByLanguage': wetByLang,
    'wetByTopic': wetByTopic,
  });
}

// --- Entity DIDs ---

const ENTITY_DIDS: { slug: string; displayName: string; description: string }[] = [
  { slug: "webpage:news", displayName: "Webpage News", description: "News webpage crawl intelligence" },
  { slug: "webpage:blog", displayName: "Webpage Blog", description: "Blog webpage crawl intelligence" },
  { slug: "webpage:ecommerce", displayName: "Webpage E-Commerce", description: "E-commerce webpage crawl intelligence" },
  { slug: "webpage:government", displayName: "Webpage Government", description: "Government webpage crawl intelligence" },
  { slug: "webpage:academic", displayName: "Webpage Academic", description: "Academic webpage crawl intelligence" },
];

let entityDidsRegistered = false;

function registerEntityDids(sdk: HostSDK): void {
  if (entityDidsRegistered) return;
  for (const e of ENTITY_DIDS) {
    str(sdk.hostImports.comAtprotoIdentityCreate(e.slug, JSON.stringify({
      displayName: e.displayName,
      description: e.description,
    })));
  }
  entityDidsRegistered = true;
}

let webTopicsRegistered = false;

async function registerWebTopicCoordinators(sdk: HostSDK): void {
  if (webTopicsRegistered) return;
  for (const topic of webTopicCoordinators) {
    const slug = `topic:${topic.slug}`;
    const did = str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
      displayName: topic.name,
      description: topic.description,
      category: "content",
    })));
    if (did) topic.did = did;

    try {
      await getDb().insertInto("vertex_web_topic" as any).values({
        vertex_id: `at://${appId}/com.etzhayyim.apps.site.topic/${topic.slug}`,
        topic: topic.slug,
        slug: topic.slug,
        did: topic.did,
        name: topic.name,
        description: topic.description,
        source_count: 0,
        sensitivity_ord: 2,
        owner_did: appId,
        created_date: nowISO().slice(0, 10),
      }).execute();
    } catch (e) { console.warn("vertex_web_topic insert:", e); }
  }
  webTopicsRegistered = true;
}

// --- GraphRAG: Domain DID Convo Agent ---

/**
 * Extract the most relevant keyword from a question for CONTAINS-based retrieval.
 * Strips stop words and returns the longest remaining content word.
 */
function extractKeyword(question: string): string {
  const stops = new Set([
    "what", "is", "the", "a", "an", "of", "in", "to", "for", "how", "why",
    "when", "where", "can", "do", "does", "about", "this", "that", "are",
    "が", "の", "は", "を", "に", "で", "と", "も", "か", "です", "ます", "した", "する", "ある",
  ]);
  const words = question
    .replace(/[?？。、！!.,]/g, "")
    .split(/\s+/)
    .filter(w => w.length > 1 && !stops.has(w.toLowerCase()));
  return words.sort((a, b) => b.length - a.length)[0] ?? question.slice(0, 20);
}

/**
 * Build a grounded system prompt for the domain agent.
 * Persona: neutral information assistant (not pretending to be the site).
 */
function buildDomainAgentPrompt(
  domain: string,
  domainInfo: Record<string, unknown> | undefined,
  chunks: Record<string, unknown>[],
  relatedPages: Record<string, unknown>[],
): string {
  const context = chunks
    .map((c, i) => `[${i + 1}] ${str(c.title)} (${str(c.url)})\n${str(c.markdown)}`)
    .join("\n\n");
  const related = relatedPages
    .map(p => `- ${str(p.title)} (${str(p.url)})`)
    .join("\n");

  return `You are a neutral information assistant for the web domain "${domain}".
You answer questions based ONLY on the archived content below. If the content does not contain the answer, say so clearly.
Do not pretend to be the website or its operator. You are an AI agent that has indexed this domain's public pages.
Always cite sources by [number]. Be concise and factual.

## Archived Content
${context || "(no relevant content found for this query)"}

## Related Pages
${related || "(none)"}

## Domain Stats
Pages indexed: ${domainInfo?.pageCount ?? "unknown"}
Topics: ${str(domainInfo?.topics ?? "")}`;
}

/**
 * Answer a question about a crawled domain using GraphRAG retrieval + LLM.
 * Retrieves WpgWET chunks scoped to the domain, gathers graph context, and generates a grounded response.
 */
async function cmdAnswerConvo(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.answerConvo", payload);
  if (!req.domain || !req.question) return encodeJson({ error: "domain and question are required" });

  const keyword = extractKeyword(req.question);
  let chunks: Record<string, unknown>[] = [];
  let retrievalMethod = "none";

  // 1. Primary: IVF vector search (query embedding → centroid → cluster → re-rank)
  const ivfResult = await ivfSearchChunks(sdk, req.domain, req.question, 10);
  chunks = ivfResult.chunks;
  retrievalMethod = ivfResult.method;

  // 2. Fallback: recent content (no embedding match)
  const db = createKyselyDb();
  if (chunks.length === 0) {
    // TODO(site): page_did not promoted on vertex_wet_chunk — use page_rkey instead
    chunks = await db
      .selectFrom("vertex_wet_chunk")
      .select(["markdown", "url", "title", "section", "page_rkey as pageDid"])
      .where("domain", "=", String(req.domain))
      .orderBy("crawled_at", "desc")
      .limit(10)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);
    // TODO(site): vertex_wpg_wet not in @etzhayyim/graph-schema — legacy fallback removed
    // TODO(site): vertex_page text column for markdown not promoted — fall back to title/url only
    if (chunks.length === 0) {
      chunks = await db
        .selectFrom("vertex_page")
        .select(["url", "title"])
        .where("domain", "=", String(req.domain))
        .orderBy("created_date", "desc")
        .limit(10)
        .execute()
        .catch(() => [] as Array<Record<string, unknown>>);
    }
    if (chunks.length > 0) retrievalMethod = "recent";
  }

  // 5. Graph context: EdgeChunkOf traversal → parent page metadata + link graph (1-hop)
  const pageDids = [...new Set(chunks.map(c => str(c.pageDid)).filter(d => d))];
  let parentPages: Array<Record<string, unknown>> = [];
  if (pageDids.length > 0) {
    // TODO(site): p.did not on vertex_page — filter by rkey (page_rkey alias from WetChunk)
    parentPages = await db
      .selectFrom("vertex_page")
      .select(["url", "title", "version", "crawled_at as crawledAt", "content_hash as contentHash"])
      .where("rkey", "in", pageDids)
      .limit(10)
      .execute()
      .catch(() => [] as Array<Record<string, unknown>>);
  }

  // TODO(site): edge_links_to 1-hop traversal not wired yet — return empty related pages
  const relatedPages: Array<Record<string, unknown>> = [];

  // 6. Domain profile for context
  // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — return empty profile
  const domainInfo: Array<Record<string, unknown>> = [];

  // 7. LLM grounded response with citations
  const allRelated = [...parentPages, ...relatedPages].filter(p => str(p.url));
  const systemPrompt = buildDomainAgentPrompt(req.domain, domainInfo[0], chunks, allRelated);
  const result = await agentConverseAsync([
    { role: 0, content: systemPrompt },
    { role: 1, content: req.question },
  ], { model: resolveModelId(undefined, "convo"), useCase: "convo" });

  return encodeJson({
    answer: result.content,
    citations: chunks.map(c => str(c.url)).filter(u => u),
    domain: req.domain,
    model: result.model,
    chunksRetrieved: chunks.length,
    retrievalMethod,
    parentPages: parentPages.length,
  });
}

/**
 * Handle pending DM convos for all domain DIDs in a single heartbeat cycle.
 * Queries WebDomain graph for registered domain DIDs, checks for unread convos, and responds.
 */
async function handleDomainConvos(sdk: HostSDK): Promise<Array<Record<string, unknown>>> {
  const actions: Array<Record<string, unknown>> = [];
  // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — derive registered domain DIDs from vertex_domain
  const db = createKyselyDb();
  const domains = await db
    .selectFrom("vertex_domain")
    .select(["domain", "did"])
    .where("did", "is not", null)
    .where("did", "!=", "")
    .limit(20)
    .execute()
    .catch(() => [] as Array<{ domain?: string | null; did?: string | null }>);

  for (const d of domains) {
    const domain = str(d.domain);
    const domainDid = str(d.did);
    if (!domain || !domainDid) continue;

    try {
      const convosJson = str(
        (sdk.hostImports as any).listConvos?.(JSON.stringify({ did: domainDid, limit: 5 }), sdk.pds.requestCache) ?? "",
      );
      if (!convosJson) continue;

      let convos: Array<Record<string, unknown>>;
      try { convos = JSON.parse(convosJson); } catch { continue; }

      for (const convo of convos) {
        const lastMsg = str((convo as any).lastMessage?.text ?? "");
        const convoId = str((convo as any).id ?? "");
        if (!lastMsg || !convoId) continue;

        // Retrieve via IVF vector search (no CONTAINS — pushdown safe)
        const ivf = await ivfSearchChunks(sdk, domain, lastMsg, 8);
        let chunks = ivf.chunks;
        if (chunks.length === 0) {
          chunks = await db
            .selectFrom("vertex_wet_chunk")
            .select(["markdown", "url", "title", "section"])
            .where("domain", "=", domain)
            .orderBy("crawled_at", "desc")
            .limit(8)
            .execute()
            .catch(() => [] as Array<Record<string, unknown>>);
        }
        // TODO(site): vertex_wpg_wet not in @etzhayyim/graph-schema — legacy fallback removed
        // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — return empty profile
        const domainInfo: Array<Record<string, unknown>> = [];

        const systemPrompt = buildDomainAgentPrompt(domain, domainInfo[0], chunks, []);
        const result = await agentConverseAsync([
          { role: 0, content: systemPrompt },
          { role: 1, content: lastMsg },
        ], { model: resolveModelId(undefined, "convo"), useCase: "convo" });

        // Send reply via convo project sendProjectMessage
        const citations = chunks.map(c => str(c.url)).filter(u => u);
        const replyText = citations.length > 0
          ? `${result.content}\n\nSources:\n${citations.map((u, i) => `[${i + 1}] ${u}`).join("\n")}`
          : result.content;

        try {
          (sdk.hostImports as any).sendProjectMessage?.(
            JSON.stringify({ convoId, did: domainDid, text: truncateText(replyText, 3000) }),
            sdk.pds.writeBuffer,
          );
        } catch (e) { console.warn("sendProjectMessage:", e); }

        actions.push({ action: "convoReply", domain, convoId, chunksUsed: chunks.length });
      }
    } catch (e) { console.warn("domainConvo:", domain, e); }
  }

  return actions;
}

// --- Heartbeat ---

let heartbeatRotation = 0;
let prioritySeedsEnqueued = false;

/** Priority seed domains — auto-enqueued on first heartbeat after deploy.
 *  These are high-value technical documentation sites for GraphRAG knowledge base. */
const PRIORITY_SEED_DOMAINS: { domain: string; urls: string[]; topics: string[]; priority: number }[] = [
  {
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
    domain: "docs.risingwave.com",
    urls: [
      "https://docs.risingwave.com/iceberg/internal-iceberg-tables",
      "https://docs.risingwave.com/docs/current/intro/",
      "https://docs.risingwave.com/docs/current/risingwave-sql-101/",
      "https://docs.risingwave.com/docs/current/data-ingestion/",
      "https://docs.risingwave.com/docs/current/sql-create-mv/",
      "https://docs.risingwave.com/docs/current/sql-create-table/",
      "https://docs.risingwave.com/docs/current/sql-create-sink/",
    ],
    topics: ["technology"],
    priority: 80,
  },
];

// Layer 3: Shinka (Social Evolution)
const shinkaEnabled = true; // domain: site

export async function runHeartbeat(sdk: HostSDK): Promise<{ ok: boolean; actions: Array<Record<string, unknown>> }> {
  const actions: Array<Record<string, unknown>> = [];
  const ts = nowISO();
  const cadence = await resolveHeartbeatCadence("did:web:w3bpg001.etzhayyim.com", cadenceState, inbox);
  actions.push({ action: "cadenceResolved", mood: cadence.mood, reason: cadence.reason, ts });

  // --- Priority seed: auto-enqueue high-value domains on first heartbeat ---
  if (!prioritySeedsEnqueued) {
    prioritySeedsEnqueued = true;
    const [orgId, userId] = ctxOrgUser(sdk);
    let seededCount = 0;
    for (const seed of PRIORITY_SEED_DOMAINS) {
      // Check if domain is already crawled
      try {
        // TODO(site): vertex_web_domain not in @etzhayyim/graph-schema — derive from vertex_page count
        const existing = await createKyselyDb()
          .selectFrom("vertex_page")
          .select((eb) => eb.fn.countAll<string>().as("pc"))
          .where("domain", "=", seed.domain)
          .execute()
          .catch(() => [] as Array<{ pc: string }>);
        if (existing.length > 0 && Number(existing[0].pc ?? 0) >= 5) continue;
      } catch { /* no domain record — proceed with seed */ }

      // Register domain DID
      const slug = seed.domain.replace(/[^a-z0-9]/g, "-");
      str(sdk.hostImports.comAtprotoIdentityCreate(slug, JSON.stringify({
        displayName: seed.domain,
        description: `Priority seed: ${seed.domain}`,
        category: "content",
      })));
      try {
        await getDb().insertInto("vertex_web_domain" as any).values({
          vertex_id: `at://${appId}/com.etzhayyim.apps.site.domain/${slug}`,
          domain: seed.domain,
          slug,
          did: `did:web:${appId}.etzhayyim.com:${slug}`,
          topics: JSON.stringify(seed.topics),
          page_count: 0,
          sensitivity_ord: 2,
          owner_did: appId,
          first_seen: nowISO(),
          last_crawled: "",
          created_date: nowISO().slice(0, 10),
        }).execute();
      } catch (e) { console.warn("vertex_web_domain insert:", e); }

      // Enqueue specific URLs
      for (const url of seed.urls) {
        const psFeRkey = genID("fe");
        await getDb().insertInto("vertex_frontier").values({
          vertex_id: `at://${appId}/com.etzhayyim.apps.site.frontier/${psFeRkey}`,
          rkey: psFeRkey,
          url,
          domain: seed.domain,
          status: "pending",
          priority: seed.priority,
          depth: 0,
          topics: JSON.stringify(seed.topics),
          source: "prioritySeed",
          sensitivity_ord: 2,
          owner_did: appId,
          created_date: nowISO().slice(0, 10),
        } as any).execute();
        seededCount++;
      }
    }
    if (seededCount > 0) {
      actions.push({ action: "prioritySeed", seeded: seededCount, domains: PRIORITY_SEED_DOMAINS.map(d => d.domain), ts });
    }
  }

  // --- shouldDrill: kyumei-koji self-research ---

  // --- shouldAnalyze: domain data analysis ---

  // --- shouldValidate: data quality check ---

  // --- Domain DID convo handling (GraphRAG) ---
  if (cadence.shouldAnalyze || cadence.shouldPost) {
    try {
      const convoActions = await handleDomainConvos(sdk);
      actions.push(...convoActions);
    } catch (e) { console.warn("domainConvos:", e); }
  }

  // --- Frontier: auto-process pending crawl queue ---
  if (cadence.shouldAnalyze || cadence.shouldEngage) {
    try {
      const frontierResult = await cmdProcessFrontier(sdk, new TextEncoder().encode(JSON.stringify({ batchSize: 20 })));
      const parsed = JSON.parse(new TextDecoder().decode(frontierResult));
      if (parsed.processed > 0) {
        actions.push({ action: "processFrontier", processed: parsed.processed, skippedCooldown: parsed.skippedCooldown ?? 0, ts });
      }
    } catch (e) { console.warn("frontier:", e); }
  }

  // --- Embedding: auto-trigger text embedding for unembedded WetChunks ---
  if (cadence.shouldAnalyze || cadence.shouldPost) {
    try {
      const embedResult = await cmdTriggerTextEmbedding(sdk, new TextEncoder().encode(JSON.stringify({ batchSize: 30 })));
      const parsed = JSON.parse(new TextDecoder().decode(embedResult));
      if (parsed.triggered > 0) {
        actions.push({ action: "textEmbedding", triggered: parsed.triggered, source: parsed.source ?? "wetChunk", ts });
      }
    } catch (e) { console.warn("textEmbedding:", e); }
  }

  // --- Embedding: auto-trigger visual embedding for unembedded screenshots ---
  if (cadence.shouldPost) {
    try {
      const embedResult = await cmdTriggerVisualEmbedding(sdk, new TextEncoder().encode(JSON.stringify({ batchSize: 10 })));
      const parsed = JSON.parse(new TextDecoder().decode(embedResult));
      if (parsed.triggered > 0) {
        actions.push({ action: "visualEmbedding", triggered: parsed.triggered, ts });
      }
    } catch (e) { console.warn("visualEmbedding:", e); }
  }

  // --- Frontier: expire old failed/done entries (30-day retention) ---
  if (cadence.shouldValidate) {
    try {
      const cutoff = new Date(Date.now() - 30 * 86400000).toISOString();
      // TODO(site): finished_at not on vertex_frontier — use status alone as eligibility hint
      void cutoff;
      const expired = await createKyselyDb()
        .selectFrom("vertex_frontier")
        .select((eb) => eb.fn.countAll<string>().as("cnt"))
        .where("status", "in", ["done", "failed"])
        .execute()
        .catch(() => [] as Array<{ cnt: string }>);
      const count = Number(expired[0]?.cnt ?? 0);
      if (count > 0) actions.push({ action: "frontierExpiry", eligible: count, ts });
    } catch (e) { console.warn("frontierExpiry:", e); }
  }

  if (actions.length === 1) actions.push({ action: "noop", mood: cadence.mood, ts });

  // --- Legacy heartbeat: topic rotation + stats ---
  registerTopicCoordinators(sdk);
  registerEntityDids(sdk);
  registerWebTopicCoordinators(sdk);

  // Rotate through ALL topic coordinators (original + web)
  const topicIndex = heartbeatRotation % allTopicCoordinators.length;
  const topic = allTopicCoordinators[topicIndex];
  heartbeatRotation++;

  // Query recent WET chunks + legacy pages for this topic
  // Serialized per Hyperdrive origin pool guideline.
  const heartbeatDb = createKyselyDb();
  // TODO(site): vertex_wpg_wet not in @etzhayyim/graph-schema — use vertex_wet_chunk (no topics column)
  const recentWet = (await heartbeatDb
    .selectFrom("vertex_wet_chunk")
    .select(["title", "language"])
    .orderBy("crawled_at", "desc")
    .limit(40)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>))
    .filter((r) => rowHasTopic(r, topic.slug))
    .slice(0, 5);

  // TODO(site): source_name / topics not promoted on vertex_page — topic filter bypassed
  const recentPages = (await heartbeatDb
    .selectFrom("vertex_page")
    .select(["title"])
    .orderBy("created_date", "desc")
    .limit(40)
    .execute()
    .catch(() => [] as Array<Record<string, unknown>>))
    .filter((r) => rowHasTopic(r, topic.slug))
    .slice(0, 5);

  // Query counts
  const pendingJobs = await heartbeatDb
    .selectFrom("vertex_collection_job")
    .select((eb) => eb.fn.countAll<string>().as("cnt"))
    .where("status", "=", "pending")
    .execute()
    .catch(() => [] as Array<{ cnt: string }>);

  const wetCount = await heartbeatDb
    .selectFrom("vertex_wet_chunk")
    .select((eb) => eb.fn.countAll<string>().as("cnt"))
    .execute()
    .catch(() => [] as Array<{ cnt: string }>);

  const totalPages = await heartbeatDb
    .selectFrom("vertex_page")
    .select((eb) => eb.fn.countAll<string>().as("cnt"))
    .execute()
    .catch(() => [] as Array<{ cnt: string }>);

  const pendingCount = Number(pendingJobs[0]?.cnt ?? 0);
  const wetTotal = Number(wetCount[0]?.cnt ?? 0);
  const pageTotal = Number(totalPages[0]?.cnt ?? 0);

  // Post summary from topic coordinator DID
  const recentTitles = [...recentWet, ...recentPages]
    .slice(0, 5)
    .map(r => str(r.title))
    .filter(t => t.length > 0)
    .join(", ");

  const summaryText = recentTitles
    ? `[${topic.name}] WET: ${wetTotal} | Pages: ${pageTotal} | Pending: ${pendingCount} | Recent: ${truncateText(recentTitles, 120)}`
    : `[${topic.name}] WET: ${wetTotal} | Pages: ${pageTotal} | Pending: ${pendingCount} | Awaiting content`;

  if (topic.did) {
    postAs(sdk, topic.did, truncateText(summaryText, 280));
  }

  actions.push({ action: "topicRotation", topic: topic.slug, wet: wetTotal, pages: pageTotal, pending: pendingCount });
  return { ok: true, actions };
}

// --- SDK Factory + Command Registration ---

function registerWebpageApp(sdk: HostSDK): void {
  sdk.app
    // --- Collection commands ---
    .command(nsid("com.etzhayyim.apps.site.collectAozora"), (ctx, body) => cmdFetchAozora(sdk, body),
      asAgentTool("Collect Japanese classical texts from Aozora Bunko (public domain)"),
      withCapabilityTags("collection", "aozora", "jpClassics"),
    )
    .command(nsid("com.etzhayyim.apps.site.collectNdl"), (ctx, body) => cmdFetchNdl(sdk, body),
      asAgentTool("Collect digitized materials from National Diet Library via IIIF/OCR"),
      withCapabilityTags("collection", "ndl", "jpClassics", "academic"),
    )
    .command(nsid("com.etzhayyim.apps.site.collectWikisource"), (ctx, body) => cmdFetchWikisource(sdk, body),
      asAgentTool("Collect texts from Wikisource (Japanese or English)"),
      withCapabilityTags("collection", "wikisource", "literature"),
    )
    .command(nsid("com.etzhayyim.apps.site.collectGutenberg"), (ctx, body) => cmdFetchGutenberg(sdk, body),
      asAgentTool("Collect public domain books from Project Gutenberg"),
      withCapabilityTags("collection", "gutenberg", "intlLiterature"),
    )
    .command(nsid("com.etzhayyim.apps.site.collectImages"), (ctx, body) => cmdFetchImages(sdk, body),
      asAgentTool("Collect historical images from ColBase, CODH, or NDL IIIF"),
      withCapabilityTags("collection", "images", "iiif"),
    )
    // --- Bulk catalog ingest ---
    .command(nsid("com.etzhayyim.apps.site.bulkIngestAozora"), (ctx, body) => cmdBulkIngestAozora(sdk, body),
      asAgentTool("Bulk ingest Aozora Bunko PD catalog (~17K works)"),
      withCapabilityTags("collection", "aozora", "bulk", "publicDomain"),
    )
    .command(nsid("com.etzhayyim.apps.site.bulkIngestGutenberg"), (ctx, body) => cmdBulkIngestGutenberg(sdk, body),
      asAgentTool("Bulk ingest Project Gutenberg PD catalog (~70K works)"),
      withCapabilityTags("collection", "gutenberg", "bulk", "publicDomain"),
    )
    .command(nsid("com.etzhayyim.apps.site.bulkIngestNdl"), (ctx, body) => cmdBulkIngestNDL(sdk, body),
      asAgentTool("Bulk ingest NDL Digital Collection PD works (~500K) via SRU catalog + IIIF Manifest"),
      withCapabilityTags("collection", "ndl", "bulk", "publicDomain", "iiif"),
    )
    .command(nsid("com.etzhayyim.apps.site.fetchNdlManifest"), (ctx, body) => cmdFetchNdlManifest(sdk, body),
      asAgentTool("Fetch single NDL IIIF Manifest by bibId → per-page WebP + OCR text"),
      withCapabilityTags("collection", "ndl", "iiif", "manifest"),
    )
    // --- Query commands ---
    .command(nsid("com.etzhayyim.apps.site.listPages"), (ctx, body) => cmdListPages(sdk, body),
      asAgentTool("List archived web pages with topic/language/source filters"),
      withCapabilityTags("query", "pages"),
    )
    .command(nsid("com.etzhayyim.apps.site.searchPages"), (ctx, body) => cmdSearchPages(sdk, body),
      asAgentTool("Full-text search across archived pages"),
      withCapabilityTags("query", "search", "pages"),
    )
    .query(nsid("com.etzhayyim.apps.site.searchSemantic"), (ctx, body) => cmdSearchSemantic(sdk, body),
      asAgentTool("Corpus2Skill-guided IVF+PQ semantic search over WET chunks"),
      withCapabilityTags("query", "search", "semantic", "ivf", "corpus2skill"),
    )
    .command(nsid("com.etzhayyim.apps.site.listJobs"), (ctx, body) => cmdListJobs(sdk, body),
      asAgentTool("List collection jobs with status and source filters"),
      withCapabilityTags("query", "jobs"),
    )
    .command(nsid("com.etzhayyim.apps.site.getStats"), (ctx, body) => cmdGetStats(sdk, body),
      asAgentTool("Get archive statistics: total pages, jobs, topic counts"),
      withCapabilityTags("query", "stats"),
    )
    .command(nsid("com.etzhayyim.apps.site.enqueueUrl"), (ctx, body) => cmdEnqueueUrl(sdk, body),
      asAgentTool("Enqueue a URL for crawling into the frontier"),
      withCapabilityTags("frontier", "crawl"),
    )
    // --- Domain/Page DID management ---
    .command(nsid("com.etzhayyim.apps.site.registerDomain"), (ctx, body) => cmdRegisterDomain(sdk, body),
      asAgentTool("Register a domain as path-based DID for tracking"),
      withCapabilityTags("domain", "did", "register"),
    )
    .command(nsid("com.etzhayyim.apps.site.crawlPage"), (ctx, body) => cmdCrawlPage(sdk, body),
      asAgentTool("Crawl a single URL: fetch + parse + create page record"),
      withCapabilityTags("crawl", "page"),
    )
    .command(nsid("com.etzhayyim.apps.site.crawlDomain"), (ctx, body) => cmdCrawlDomain(sdk, body),
      asAgentTool("Start crawling a domain (BFS, max depth 3)"),
      withCapabilityTags("crawl", "domain"),
    )
    .command(nsid("com.etzhayyim.apps.site.recordPage"), (ctx, body) => cmdRecordPage(sdk, body),
      asAgentTool("Record a pre-fetched page as DID archive (no HTTP fetch)"),
      withCapabilityTags("record", "page"),
    )
    .command(nsid("com.etzhayyim.apps.site.getPage"), (ctx, body) => cmdGetPage(sdk, body),
      asAgentTool("Get page detail by DID, URL, or ID"),
      withCapabilityTags("query", "page"),
    )
    .command(nsid("com.etzhayyim.apps.site.getDomainOverview"), (ctx, body) => cmdGetDomainOverview(sdk, body),
      asAgentTool("Get domain overview with page count and crawl history"),
      withCapabilityTags("query", "domain"),
    )
    .command(nsid("com.etzhayyim.apps.site.getLinkGraph"), (ctx, body) => cmdGetLinkGraph(sdk, body),
      asAgentTool("Get link graph between pages or domains"),
      withCapabilityTags("query", "linkGraph"),
    )
    .command(nsid("com.etzhayyim.apps.site.enqueueBulk"), (ctx, body) => cmdEnqueueBulk(sdk, body),
      asAgentTool("Enqueue multiple URLs to the crawl frontier"),
      withCapabilityTags("frontier", "bulk"),
    )
    .command(nsid("com.etzhayyim.apps.site.dequeueUrls"), (ctx, body) => cmdDequeueUrls(sdk, body),
      asAgentTool("Dequeue next URLs from frontier by priority"),
      withCapabilityTags("frontier", "dequeue"),
    )
    .command(nsid("com.etzhayyim.apps.site.getFrontierStats"), (ctx, body) => cmdGetFrontierStats(sdk, body),
      asAgentTool("Get frontier queue statistics"),
      withCapabilityTags("frontier", "stats"),
    )
    .command(nsid("com.etzhayyim.apps.site.processFrontier"), (ctx, body) => cmdProcessFrontier(sdk, body),
      asAgentTool("Process next batch from frontier: dequeue + crawl + record"),
      withCapabilityTags("frontier", "process"),
    )
    // --- PDF ingest ---
    .command(nsid("com.etzhayyim.apps.site.fetchPdf"), (ctx, body) => cmdFetchPdf(sdk, body),
      asAgentTool("Fetch PDF document: pages → WebP (R2 CDN), text → WET records"),
      withCapabilityTags("collection", "pdf", "webp", "wet"),
    )
    // --- WET/WAT/Screenshot pipeline ---
    .command(nsid("com.etzhayyim.apps.site.generateWet"), (ctx, body) => cmdGenerateWET(sdk, body),
      asAgentTool("Generate WET (Markdown) records from HTML content"),
      withCapabilityTags("wet", "extraction", "markdown"),
    )
    .command(nsid("com.etzhayyim.apps.site.generateWat"), (ctx, body) => cmdGenerateWAT(sdk, body),
      asAgentTool("Generate WAT (metadata JSON) record from HTML content"),
      withCapabilityTags("wat", "metadata"),
    )
    .command(nsid("com.etzhayyim.apps.site.captureScreenshot"), (ctx, body) => cmdCaptureScreenshot(sdk, body),
      asAgentTool("Capture WebP screenshot of a URL via headless browser"),
      withCapabilityTags("screenshot", "webp", "visual"),
    )
    .command(nsid("com.etzhayyim.apps.site.checkRobotsTxt"), (ctx, body) => cmdCheckRobotsTxt(sdk, body),
      asAgentTool("Check robots.txt rules for a domain"),
      withCapabilityTags("robots", "politeness"),
    )
    .command(nsid("com.etzhayyim.apps.site.seedFromCommonCrawl"), (ctx, body) => cmdSeedFromCommonCrawl(sdk, body),
      asAgentTool("Bootstrap frontier from Common Crawl CDX URL index"),
      withCapabilityTags("seed", "commonCrawl", "frontier"),
    )
    .command(nsid("com.etzhayyim.apps.site.seedGovPdfs"), (ctx, body) => cmdSeedGovPdfs(sdk, body),
      asAgentTool("Seed government PDF URLs from CC vertex_page for WebP + WET pipeline"),
      withCapabilityTags("collection", "pdf", "government", "legal", "bulk"),
    )
    .command(nsid("com.etzhayyim.apps.site.seedForProject"), (ctx, body) => cmdSeedForProject(sdk, body),
      asAgentTool("Seed crawl for a project: domain list + auto CommonCrawl fallback for missing data"),
      withCapabilityTags("seed", "project", "commonCrawl", "frontier"),
    )
    .command(nsid("com.etzhayyim.apps.site.ingestGeoData"), (ctx, body) => cmdIngestGeoData(sdk, body),
      asAgentTool("Ingest structured geo data from a URL (USGS GeoJSON, Wikidata SPARQL, OurAirports CSV, OpenSky ADS-B) → emit geoRecord commits to subscriber apps"),
      withCapabilityTags("geo", "ingest", "usgs", "wikidata", "municipality", "seismic", "airport", "adsb"),
    )
    .command(nsid("com.etzhayyim.apps.site.triggerTextEmbedding"), (ctx, body) => cmdTriggerTextEmbedding(sdk, body),
      asAgentTool("Trigger text embedding batch for WET chunks via Murakumo"),
      withCapabilityTags("embedding", "text", "murakumo"),
    )
    .command(nsid("com.etzhayyim.apps.site.triggerVisualEmbedding"), (ctx, body) => cmdTriggerVisualEmbedding(sdk, body),
      asAgentTool("Trigger visual embedding batch for screenshots via ColPali"),
      withCapabilityTags("embedding", "visual", "colpali"),
    )
    .command(nsid("com.etzhayyim.apps.site.registerWebTopic"), (ctx, body) => cmdRegisterWebTopic(sdk, body),
      asAgentTool("Register a new web topic coordinator DID"),
      withCapabilityTags("topic", "register"),
    )
    .command(nsid("com.etzhayyim.apps.site.getCrawlOutputStats"), (ctx, body) => cmdGetCrawlOutputStats(sdk, body),
      asAgentTool("Get WET/WAT/screenshot output statistics"),
      withCapabilityTags("stats", "wet", "wat", "screenshot"),
    )
    // --- GraphRAG convo ---
    .command(nsid("com.etzhayyim.apps.site.answerConvo"), (ctx, body) => cmdAnswerConvo(sdk, body),
      asAgentTool("Answer a question about a crawled domain using GraphRAG retrieval"),
      withCapabilityTags("convo", "graphrag", "domain", "llm"),
    )
    // --- Synchronous fetch (browser.fetch primitive target) ---
    .command(nsid("com.etzhayyim.apps.site.fetch"), (ctx, body) => cmdFetchSync(sdk, body),
      asAgentTool("Synchronous URL fetch: HTTP GET → markdown text (for pipeline browser.fetch primitive)"),
      withCapabilityTags("fetch", "sync", "markdown"),
    );

}

/**
 * Synchronous URL fetch — HTTP GET → HTML → Markdown conversion.
 * Target for actor-executor browser.fetch primitive.
 * Returns immediately with page content (no async job queue).
 */
async function cmdFetchSync(sdk: HostSDK, payload: Uint8Array): Promise<Uint8Array> {
  const req = parseLexiconInput("com.etzhayyim.apps.site.fetch", payload);
  if (!req.url) return encodeJson({ error: "url is required" });

  // --- Try live fetch first ---
  try {
    const resp = await fetch(req.url, {
      headers: {
        "User-Agent": "etzhayyim-bot/1.0 (+https://etzhayyim.com/bot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      signal: AbortSignal.timeout(10000),
      redirect: "follow",
    });
    if (resp.ok) {
      const html = await resp.text();
      if (html.length > 200) {
        const title = (html.match(/<title[^>]*>([^<]*)<\/title>/i)?.[1] ?? "").trim();
        const text = req.format === "html" ? html : htmlToMarkdown(html);
        return encodeJson({ url: req.url, title, text, contentLength: html.length, source: "live" });
      }
    }
  } catch { /* fall through to Common Crawl */ }

  // --- Fallback: Common Crawl CDX -> WARC Range fetch ---
  try {
    const ccResult = await fetchFromCommonCrawl(req.url);
    if (ccResult) {
      const title = (ccResult.html.match(/<title[^>]*>([^<]*)<\/title>/i)?.[1] ?? "").trim();
      const text = req.format === "html" ? ccResult.html : htmlToMarkdown(ccResult.html);
      return encodeJson({
        url: req.url, title, text,
        contentLength: ccResult.html.length,
        source: "commoncrawl",
        crawlDate: ccResult.timestamp,
      });
    }
  } catch { /* no CC result */ }

  return encodeJson({ error: "fetch failed (live + commoncrawl)", url: req.url, text: "" });
}

async function fetchFromCommonCrawl(url: string): Promise<{ html: string; timestamp: string } | null> {
  const cdxUrl = `https://index.commoncrawl.org/CC-MAIN-2024-51-index?url=${encodeURIComponent(url)}&output=json&limit=1&filter=statuscode:200&filter=mimetype:text/html`;
  const cdxResp = await fetch(cdxUrl, { signal: AbortSignal.timeout(8000) });
  if (!cdxResp.ok) return null;
  const cdxText = await cdxResp.text();
  const lines = cdxText.trim().split("\n").filter(Boolean);
  if (lines.length === 0) return null;
  const cdx = JSON.parse(lines[0]) as { filename: string; offset: string; length: string; timestamp: string };

  const warcUrl = `https://data.commoncrawl.org/${cdx.filename}`;
  const offset = parseInt(cdx.offset, 10);
  const length = parseInt(cdx.length, 10);
  const warcResp = await fetch(warcUrl, {
    headers: { Range: `bytes=${offset}-${offset + length - 1}` },
    signal: AbortSignal.timeout(15000),
  });
  if (!warcResp.ok && warcResp.status !== 206) return null;

  const warcBuf = await warcResp.arrayBuffer();
  const ds = new DecompressionStream("gzip");
  const writer = ds.writable.getWriter();
  writer.write(new Uint8Array(warcBuf));
  writer.close();
  const reader = ds.readable.getReader();
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const decompressed = new Uint8Array(chunks.reduce((a, c) => a + c.length, 0));
  let pos = 0;
  for (const chunk of chunks) { decompressed.set(chunk, pos); pos += chunk.length; }
  const raw = new TextDecoder().decode(decompressed);

  const firstBreak = raw.indexOf("\r\n\r\n");
  if (firstBreak < 0) return null;
  const secondBreak = raw.indexOf("\r\n\r\n", firstBreak + 4);
  if (secondBreak < 0) return null;
  const html = raw.slice(secondBreak + 4);

  return { html, timestamp: cdx.timestamp };
}

export default createWorkerExport((sdk) => {
  appId = sdk.pds.selfNanoid ?? "";
  sdk.pds.appName = "site";
  registerWebpageApp(sdk);
});
