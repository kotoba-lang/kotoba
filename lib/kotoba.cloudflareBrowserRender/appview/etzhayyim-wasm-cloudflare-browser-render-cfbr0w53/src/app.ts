import {
  asAgentTool, createKyselyDb, createWorkerExport, withCapabilityTags,
  type HostSDK, nowISO, str, genID, nsid,
} from "@etzhayyim/kotodama-host-sdk";
import puppeteer, { type Browser, type Page } from "@cloudflare/puppeteer";

const ACTOR_NAME = "cloudflare-browser-render";
const ACTOR_NSID_NS = "cloudflareBrowserRender";
const ACTOR_DID = `did:web:${ACTOR_NAME}.etzhayyim.com`;

function camelToSnake(s: string): string {
  return s.replace(/[A-Z]/g, m => "_" + m.toLowerCase()).replace(/^_/, "");
}

function decodeParams(payload: any): Record<string, any> {
  if (!payload) return {};
  if (typeof payload === "object" && !(payload instanceof Uint8Array)) return payload as any;
  try {
    const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
    if (bytes.length === 0) return {};
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch { return {}; }
}

/**
 * com.etzhayyim.apps.cloudflareBrowserRender — CF Browser Rendering wrapper.
 *
 * Phase 2 (2026-04-20): DO-held chromium via `@cloudflare/puppeteer`.
 * `dispatchOp` forwards ops to the BrowserSessionDO which keeps a single
 * browser/page alive across calls. Alarm sweeps idle sessions at TTL.
 *
 * Called by com.etzhayyim.apps.playwright as a service binding (CF_BROWSER_RENDER).
 */

const SESSION_TTL_SEC = 5 * 60;
const SESSION_IDLE_SWEEP_MS = 60_000;

type GraphDb = ReturnType<typeof createKyselyDb>;

async function writeRecord(db: GraphDb, collection: string, rkey: string, value: Record<string, unknown>): Promise<void> {
  const table = `vertex_${camelToSnake(ACTOR_NSID_NS)}_${camelToSnake(collection)}`;
  const now = new Date();
  const row: Record<string, unknown> = {
    vertex_id: `at://${ACTOR_DID}/com.etzhayyim.apps.${ACTOR_NSID_NS}.${collection}/${rkey}`,
    _seq: null,
    created_date: now.toISOString().slice(0, 10),
    sensitivity_ord: 100,
    owner_did: ACTOR_DID,
    rkey,
    repo: ACTOR_DID,
    created_at: now.toISOString(),
    org_id: "etzhayyim",
    user_id: "system",
    actor_id: `sys.${ACTOR_NAME}`,
  };
  for (const [k, v] of Object.entries(value)) {
    const sc = camelToSnake(k);
    if (sc in row) continue;
    row[sc] = (v !== null && typeof v === "object") ? JSON.stringify(v) : v;
  }
  try {
    await db.insertInto(table as any).values(row as any).execute();
  } catch (e: any) {
    const msg = String(e?.message ?? e);
    if (!/duplicate|already exists|pk violation/i.test(msg)) {
      console.error(`[writeRecord] ${table} failed: ${msg.slice(0, 300)}`);
    }
  }
}

// ── R2 helpers ─────────────────────────────────────────────────────────────
async function sha256Hex(bytes: Uint8Array | string): Promise<string> {
  const data = typeof bytes === "string" ? new TextEncoder().encode(bytes) : bytes;
  const h = await crypto.subtle.digest("SHA-256", data as unknown as BufferSource);
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join("");
}
async function putR2(env: any, key: string, body: Uint8Array | string, contentType: string): Promise<string> {
  const bucket = env.ARTIFACT_R2 ?? env.CACHE_R2;
  if (!bucket) throw new Error("ARTIFACT_R2 / CACHE_R2 binding not configured");
  await bucket.put(key, body, { httpMetadata: { contentType } });
  return key;
}

// ── PII redaction ──────────────────────────────────────────────────────────
function redactHtml(html: string): string {
  // Password inputs → value=""
  let out = html.replace(/<input([^>]*?)type=["']password["']([^>]*?)value=["'][^"']*["']([^>]*?)>/gi,
    "<input$1type=\"password\"$2value=\"\"$3>");
  // Luhn-formatted card numbers → REDACTED
  out = out.replace(/\b(?:\d[ -]?){13,19}\b/g, (m) => {
    const digits = m.replace(/[^\d]/g, "");
    if (digits.length < 13) return m;
    let s = 0, alt = false;
    for (let i = digits.length - 1; i >= 0; i--) {
      let n = parseInt(digits[i], 10);
      if (alt) { n *= 2; if (n > 9) n -= 9; }
      s += n; alt = !alt;
    }
    return s % 10 === 0 ? "[REDACTED_CARD]" : m;
  });
  return out;
}

// ───────────────────────────────────────────────────────────────────────────
// Durable Object: holds a chromium session for ≤5 min.
// ───────────────────────────────────────────────────────────────────────────
export class BrowserSessionDO {
  state: DurableObjectState;
  env: any;
  browser: Browser | null = null;
  page: Page | null = null;
  lastUsedAt: number = Date.now();
  sessionId: string = "";

  constructor(state: DurableObjectState, env: any) {
    this.state = state;
    this.env = env;
  }

  private async ensureBrowser(): Promise<{ browser: Browser; page: Page }> {
    if (this.browser && this.page) {
      this.lastUsedAt = Date.now();
      return { browser: this.browser, page: this.page };
    }
    if (!this.env.HEADLESS_BROWSER) throw new Error("BROWSER binding not configured");
    this.browser = await puppeteer.launch(this.env.HEADLESS_BROWSER);
    this.page = await this.browser.newPage();
    await this.state.storage.setAlarm(Date.now() + SESSION_IDLE_SWEEP_MS);
    this.lastUsedAt = Date.now();
    return { browser: this.browser, page: this.page };
  }

  private async closeBrowser(): Promise<void> {
    try { await this.page?.close(); } catch {}
    try { await this.browser?.close(); } catch {}
    this.page = null;
    this.browser = null;
  }

  async alarm(): Promise<void> {
    const idleMs = Date.now() - this.lastUsedAt;
    if (idleMs >= SESSION_TTL_SEC * 1000) {
      await this.closeBrowser();
      return;
    }
    await this.state.storage.setAlarm(Date.now() + SESSION_IDLE_SWEEP_MS);
  }

  async fetch(request: Request): Promise<Response> {
    const body = await request.json().catch(() => ({})) as any;
    const op = String(body?.op ?? "");
    const args = (body?.args ?? {}) as Record<string, any>;
    try {
      const result = await this.dispatch(op, args);
      return new Response(JSON.stringify(result), { headers: { "content-type": "application/json" } });
    } catch (e: any) {
      const msg = String(e?.message ?? e).slice(0, 800);
      return new Response(JSON.stringify({ error: msg, op }), {
        status: 500, headers: { "content-type": "application/json" }
      });
    }
  }

  private async dispatch(op: string, args: Record<string, any>): Promise<unknown> {
    if (op === "sessionClose") {
      await this.closeBrowser();
      return { closed: true };
    }
    const { page } = await this.ensureBrowser();
    const timeoutMs = Math.min(Number(args.timeout ?? 30_000), 120_000);
    switch (op) {
      case "goto": {
        if (!args.url) return { error: "url required" };
        const resp = await page.goto(String(args.url), {
          waitUntil: (args.waitUntil ?? "load") as any,
          timeout: timeoutMs,
        });
        return { status: resp?.status() ?? null, url: page.url() };
      }
      case "getUrl": {
        return { url: page.url() };
      }
      case "fill": {
        if (!args.selector) return { error: "selector required" };
        const value = String(args.value ?? "");
        await page.waitForSelector(String(args.selector), { timeout: timeoutMs });
        await page.click(String(args.selector), { clickCount: 3 }).catch(() => {});
        await page.keyboard.type(value);
        return { filled: true };
      }
      case "click": {
        if (!args.selector) return { error: "selector required" };
        await page.waitForSelector(String(args.selector), { timeout: timeoutMs });
        await page.click(String(args.selector));
        return { clicked: true };
      }
      case "waitFor": {
        if (args.selector) {
          await page.waitForSelector(String(args.selector), { timeout: timeoutMs });
          return { waited: "selector" };
        }
        if (args.state === "networkidle") {
          await page.waitForNetworkIdle({ timeout: timeoutMs }).catch(() => {});
          return { waited: "networkidle" };
        }
        return { waited: "noop" };
      }
      case "scrape": {
        if (!args.selector) return { error: "selector required" };
        const parse = String(args.parse ?? "text");
        await page.waitForSelector(String(args.selector), { timeout: timeoutMs }).catch(() => {});
        if (parse === "text") {
          const values = await page.$$eval(String(args.selector), els => els.map(e => (e as HTMLElement).innerText ?? ""));
          return { values };
        }
        if (parse.startsWith("attr:")) {
          const attr = parse.slice(5);
          const values = await page.$$eval(String(args.selector), (els, a) =>
            els.map(e => (e as Element).getAttribute(a) ?? ""), attr);
          return { values };
        }
        if (parse === "number" || parse === "jpy") {
          const values = await page.$$eval(String(args.selector), els => els.map(e => (e as HTMLElement).innerText ?? ""));
          const nums = values.map((t: string) => {
            const cleaned = t.replace(/[^0-9.-]/g, "");
            const n = Number(cleaned);
            return Number.isFinite(n) ? n : null;
          });
          return { values: nums };
        }
        return { error: `unknown parse: ${parse}` };
      }
      case "snapshot": {
        const html = redactHtml(await page.content());
        const cid = await sha256Hex(html);
        const key = `cfbr-render/snapshot/${cid}.html`;
        await putR2(this.env, key, html, "text/html; charset=utf-8");
        return { cid, key, byteSize: html.length };
      }
      case "screenshot": {
        const png = await page.screenshot({ fullPage: Boolean(args.fullPage), type: "png" });
        const bytes = png instanceof Uint8Array ? png : new Uint8Array(png as unknown as ArrayBuffer);
        const cid = await sha256Hex(bytes);
        const key = `cfbr-render/screenshot/${cid}.png`;
        await putR2(this.env, key, bytes, "image/png");
        return { cid, key, byteSize: bytes.byteLength };
      }
      case "evaluate": {
        // Allowlist enforcement: only querySelector / textContent / location.* expressions.
        const js = String(args.jsCode ?? "");
        if (!/^[\s;]*(?:document\.querySelector(All)?\([^)]+\)(?:\.textContent|\.innerText|\.getAttribute\([^)]+\))?|window\.location\.(?:href|hostname|pathname|search))[\s;]*$/.test(js)) {
          return { error: "evaluate: expression not on allowlist" };
        }
        const value = await page.evaluate(js);
        return { value };
      }
      default:
        return { error: `unknown op: ${op}` };
    }
  }
}

export default createWorkerExport((sdk: HostSDK) => {
  const env = sdk.env as any;
  const db = createKyselyDb(env.HYPERDRIVE);

    sdk.app.command(nsid("com.etzhayyim.apps.cloudflareBrowserRender.createSession"),
      async (_ctx, _p: any) => {
        const params = decodeParams(_p);
        const sessionId = `cf-${genID("cf")}`;
        const durableObjectId = env.HEADLESS_BROWSER_SESSION?.idFromName(sessionId).toString() ?? "stub";
        const expiresAt = new Date(Date.now() + SESSION_TTL_SEC * 1000).toISOString();
        await writeRecord(db, "session", sessionId, {
          sessionId, durableObjectId, options: params ?? {},
          openedAt: nowISO(), expiresAt,
        });
        return { sessionId, durableObjectId, expiresAt };
      },
      asAgentTool("Create a CF Browser Rendering session (Durable Object)."),
      withCapabilityTags("cf-browser", "session"),
    );

    sdk.app.command(nsid("com.etzhayyim.apps.cloudflareBrowserRender.closeSession"),
      async (_ctx, _p: any) => {
        const params = decodeParams(_p);
        const sessionId = str(params?.sessionId ?? "");
        if (!sessionId) return { error: "sessionId required" };
        if (!env.HEADLESS_BROWSER_SESSION) return { error: "BROWSER_SESSION DO not configured" };
        const doId = env.HEADLESS_BROWSER_SESSION.idFromName(sessionId);
        const stub = env.HEADLESS_BROWSER_SESSION.get(doId);
        await stub.fetch(new Request("https://do/op", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ op: "sessionClose", args: {} }),
        }));
        return { sessionId, closed: true };
      },
      asAgentTool("Close a session."),
      withCapabilityTags("cf-browser", "session"),
    );

    sdk.app.command(nsid("com.etzhayyim.apps.cloudflareBrowserRender.renderPage"),
      async (_ctx, _p: any) => {
        const params = decodeParams(_p);
        const url = str(params?.url ?? "");
        const output = str(params?.output ?? "html");
        if (!url) return { error: "url required" };
        if (!env.HEADLESS_BROWSER) return { error: "BROWSER binding not configured" };
        // 1-shot: launch → goto → extract → close
        const browser = await puppeteer.launch(env.HEADLESS_BROWSER);
        try {
          const page = await browser.newPage();
          await page.goto(url, { waitUntil: "load", timeout: 30_000 });
          const artifactId = `art-${genID("art")}`;
          let cid = "";
          let key = "";
          let byteSize = 0;
          let contentType = "";
          if (output === "html") {
            const html = redactHtml(await page.content());
            cid = await sha256Hex(html);
            key = `cfbr-render/renderPage/${cid}.html`;
            contentType = "text/html; charset=utf-8";
            byteSize = html.length;
            await putR2(env, key, html, contentType);
          } else if (output === "png") {
            const png = await page.screenshot({ fullPage: true, type: "png" });
            const bytes = png instanceof Uint8Array ? png : new Uint8Array(png as unknown as ArrayBuffer);
            cid = await sha256Hex(bytes);
            key = `cfbr-render/renderPage/${cid}.png`;
            contentType = "image/png";
            byteSize = bytes.byteLength;
            await putR2(env, key, bytes, contentType);
          } else if (output === "pdf") {
            const pdf = await page.pdf({ format: "A4" });
            const bytes = pdf instanceof Uint8Array ? pdf : new Uint8Array(pdf as unknown as ArrayBuffer);
            cid = await sha256Hex(bytes);
            key = `cfbr-render/renderPage/${cid}.pdf`;
            contentType = "application/pdf";
            byteSize = bytes.byteLength;
            await putR2(env, key, bytes, contentType);
          } else {
            return { error: `unknown output: ${output}` };
          }
          await writeRecord(db, "artifact", artifactId, {
            artifactId, url, output, cid, byteSize, r2Key: key, contentType,
          });
          return { artifactCid: cid, artifactId, r2Key: key, byteSize, contentType };
        } finally {
          await browser.close().catch(() => {});
        }
      },
      asAgentTool("One-shot render a URL to HTML/PNG/PDF; returns artifact CID."),
      withCapabilityTags("cf-browser", "render"),
    );

    sdk.app.command(nsid("com.etzhayyim.apps.cloudflareBrowserRender.dispatchOp"),
      async (_ctx, _p: any) => {
        const params = decodeParams(_p);
        const sessionId = str(params?.sessionId ?? "");
        const op = str(params?.op ?? "");
        if (!sessionId || !op) return { error: "sessionId and op required" };
        if (!env.HEADLESS_BROWSER_SESSION) return { error: "BROWSER_SESSION DO not configured" };
        const doId = env.HEADLESS_BROWSER_SESSION.idFromName(sessionId);
        const stub = env.HEADLESS_BROWSER_SESSION.get(doId);
        const res = await stub.fetch(new Request("https://do/op", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ op, args: params?.args ?? {} }),
        }));
        return await res.json();
      },
      asAgentTool("Dispatch a Playwright-style op to a DO-held session."),
      withCapabilityTags("cf-browser", "dispatch"),
    );
});
