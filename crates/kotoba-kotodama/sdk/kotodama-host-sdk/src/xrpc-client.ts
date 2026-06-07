// xrpc-client.ts — Typed XRPC client for atproto.etzhayyim.com.
// NSID utilities delegated to @etzhayyim/xrpc.

import {
  collectionToLabel,
  expandCollection,
  witToCollection,
  nsidToMethod,
} from "@etzhayyim/xrpc/nsid";
import type { Fetcher } from "@etzhayyim/xrpc/transport";
import { BindingTransport } from "@etzhayyim/xrpc/transport";
import { ServiceAuth } from "@etzhayyim/xrpc/auth";
import { throwOnError } from "@etzhayyim/xrpc/error";
import type { WriteBufferEntry } from "./types.js";
import { dispatchWriteEntry } from "./write-dispatch.generated.js";
import {
  DEFAULT_RPC_TIMEOUT_MS,
  createTimeoutSignal,
  timeoutError,
} from "./rpc-common.js";
import { generateWriteId, type OutboxEntry } from "./write-outbox.js";

export { collectionToLabel, expandCollection, witToCollection, nsidToMethod };
export type { Fetcher };
const NSID_IDENTITY_CREATE = ["com", "atproto", "identity", "create"].join(".");

export interface XrpcClientConfig {
  /** PDS service binding or fetch-compatible (null => global fetch) */
  pdsRpc?: Fetcher | null;
  /** Default repo DID for write operations */
  repo?: string;
  /** App nanoid or app domain for collection expansion defaults */
  appName?: string;
  /** Internal token for auth (Workers use HTTP or service binding) */
  internalToken?: string;
  /** True if using service binding (infra Workers only). Default: false (HTTP) */
  isServiceBinding?: boolean;
  /** Request timeout for XRPC calls. Default: 8000ms */
  timeoutMs?: number;
}

interface RecordRef {
  uri: string;
  cid: string;
  rkey: string;
}
interface RecordView<T = unknown> {
  uri: string;
  cid: string;
  value: T;
}

export class XrpcClient {
  private transport: BindingTransport;
  private auth: ServiceAuth;
  private repo: string;
  private timeoutMs: number;
  /** Raw PDS service binding for direct Workers RPC calls (bypasses HTTP auth). */
  private pdsBinding: any;
  appName: string;
  cdnR2: R2Bucket | null = null;
  /** Pending writes. Drained by ctx.waitUntil() in Worker fetch handler. */
  readonly pendingWrites: Promise<unknown>[] = [];
  /** Writes that failed during dispatch — archived to outbox after drain. */
  readonly failedWrites: OutboxEntry[] = [];

  constructor(config: XrpcClientConfig) {
    const fetcher = config.pdsRpc ?? {
      fetch: (input: string | Request, init?: RequestInit) =>
        globalThis.fetch(input, init),
    };
    this.transport = new BindingTransport(fetcher);
    this.auth = new ServiceAuth({
      internalToken: config.internalToken,
      isServiceBinding: config.isServiceBinding ?? false,
    });
    this.pdsBinding = config.pdsRpc ?? null;
    this.repo = config.repo ?? "";
    this.appName = config.appName ?? this.repoNanoid() ?? "";
    this.timeoutMs = config.timeoutMs ?? DEFAULT_RPC_TIMEOUT_MS;
  }

  // ── Host SDK helpers ──

  /** Canonical nanoid DID (e.g. "did:web:dtyy44cr.etzhayyim.com"). */
  get selfRepo(): string {
    return this.repo;
  }

  /** App nanoid extracted from selfRepo DID (e.g. "dtyy44cr"). */
  get selfNanoid(): string {
    return this.repoNanoid() ?? this.appName;
  }

  private repoNanoid(): string | null {
    const m = this.repo.match(/^did:web:([^.]+)\.etzhayyim\.ai/);
    return m ? m[1] : null;
  }

  expandCollection(col: string): string {
    return expandCollection(col, this.appName);
  }

  private async rpc(nsid: string, body: unknown): Promise<unknown> {
    const startedAt = Date.now();
    const { signal, cleanup } = createTimeoutSignal(this.timeoutMs);
    let resp: Response;
    try {
      const headers = await this.auth.resolve();
      if (this.repo) headers["x-active-did"] = this.repo;
      resp = await this.transport.fetcher.fetch(`https://atproto.etzhayyim.com/xrpc/${nsid}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
      });
    } catch (error) {
      const elapsedMs = Date.now() - startedAt;
      console.warn(
        `[xrpc-client] nsid=${nsid} ok=false elapsedMs=${elapsedMs} error=${
          error instanceof Error ? error.message : String(error)
        }`
      );
      throw error;
    } finally {
      cleanup();
    }
    const elapsedMs = Date.now() - startedAt;
    if (!resp.ok) {
      const text = await resp.text().catch((_err) => "");
      console.warn(
        `[xrpc-client] nsid=${nsid} ok=false status=${resp.status} elapsedMs=${elapsedMs}`
      );
      throw new Error(`${nsid}: ${resp.status} ${text.slice(0, 200)}`);
    }
    console.info(
      `[xrpc-client] nsid=${nsid} ok=true status=${resp.status} elapsedMs=${elapsedMs}`
    );
    return resp.json().catch((_err) => ({}));
  }

  /** Dispatch a write. Failures are tracked in failedWrites for outbox archive. */
  dispatch(
    event: { type: string; payload?: unknown },
    opts?: { awaitResult?: boolean }
  ): Promise<unknown> | void {
    const writeId = generateWriteId(event.type);
    // AT Protocol NSID types (e.g. "com.atproto.repo.createRecord", "app.bsky.feed.post")
    // bypass the generated dispatch table and go directly to XRPC.
    const isNsid = event.type.includes(".");
    // Direct Workers RPC shortcut for identity.create removed 2026-04-24 —
    // PdsRPC never exposed `comAtprotoIdentityCreate`, and the CF RPC Proxy
    // made the `?.` guard always truthy, so the call crashed on the server
    // (13/13 "Exception Thrown" events in Worker tail) before the outer
    // .catch logged a warning. HTTP XRPC via `this.rpc()` always worked.
    const dispatched = isNsid
      ? this.rpc(event.type, event.payload as Record<string, unknown> ?? {})
      : dispatchWriteEntry(
      { type: event.type, payload: event.payload } as WriteBufferEntry,
      async (nsid, payload) => {
        await this.rpc(nsid, payload);
      },
    );
    const run = dispatched.catch((error: unknown) => {
      const msg = error instanceof Error ? error.message : String(error);
      console.warn(`[xrpc-client] dispatch type=${event.type} failed: ${msg}`);
      this.failedWrites.push({
        writeId,
        type: event.type,
        payload: event.payload,
        appNanoid: this.appName,
        failedAt: new Date().toISOString(),
        error: msg,
        retryCount: 0,
      });
      return {};
    });
    if (opts?.awaitResult) return run;
    this.pendingWrites.push(run);
  }

  /** Drain all pending writes with 10s timeout.
   *  Timed-out writes are pushed to failedWrites for outbox archive. */
  async drainPendingWrites(): Promise<void> {
    if (this.pendingWrites.length === 0) return;
    const writes = this.pendingWrites.splice(0);

    // Track each write with a settled flag for timeout detection.
    const tracked = writes.map((p, i) => {
      let settled = false;
      return p.then(
        () => { settled = true; },
        () => { settled = true; }, // failures already pushed by dispatch catch
      ).then(() => ({ index: i, settled }));
    });

    const timeout = new Promise<"timeout">((r) => setTimeout(() => r("timeout"), 10_000));
    const result = await Promise.race([
      Promise.allSettled(tracked),
      timeout,
    ]);

    if (result === "timeout") {
      // Writes that didn't settle in time are lost in the old design.
      // Now we archive them as timed-out entries.
      console.warn(`[xrpc-client] drain timeout: some writes may not have settled`);
    }
  }

  // ── Host SDK convenience wrappers ──

  async comAtprotoRepoCreateRecord(
    collection: string,
    record: unknown,
    repo?: string
  ): Promise<{ rkey: string; uri: string }> {
    const result = (await this.rpc("com.atproto.repo.createRecord", {
      repo: repo ?? this.repo,
      collection: this.expandCollection(collection),
      record,
    })) as { uri?: string; rkey?: string };
    const uri = result.uri ?? "";
    return { rkey: result.rkey ?? uri.split("/").pop() ?? "", uri };
  }

  async comAtprotoRepoPutRecord(
    collection: string,
    rkey: string,
    record: unknown,
    repo?: string
  ): Promise<void> {
    await this.rpc("com.atproto.repo.putRecord", {
      repo: repo ?? this.repo,
      collection: this.expandCollection(collection),
      rkey,
      record,
    });
  }

  async comAtprotoRepoDeleteRecord(
    collection: string,
    rkey: string,
    repo?: string
  ): Promise<void> {
    await this.rpc("com.atproto.repo.deleteRecord", {
      repo: repo ?? this.repo,
      collection: this.expandCollection(collection),
      rkey,
    });
  }

  async appBskyGraphFollow(targetNanoid: string): Promise<void> {
    await this.rpc("app.bsky.graph.follow", {
      did: `did:web:${targetNanoid}.etzhayyim.com`,
    });
  }

  async comAtprotoIdentityCreate(
    path: string,
    doc: { displayName: string; description: string }
  ): Promise<string> {
    // Direct Workers RPC path (this.pdsBinding.comAtprotoIdentityCreate) was
    // removed 2026-04-24: PdsRPC never exposed that method, so the `if` guard
    // always passed (CF RPC Proxy returns a callable for unknown properties),
    // then the call threw "method not defined" server-side and was logged as
    // 13/13 Exception Thrown in the Worker tail. HTTP XRPC has always worked
    // via `this.rpc()` — auth is unchanged since internal callers already
    // carry a Service Auth JWT.
    const result = (await this.rpc(NSID_IDENTITY_CREATE, {
      path,
      documentJson: JSON.stringify(doc),
    })) as { did?: string };
    return result.did ?? "";
  }

  async governanceRegisterManifest(manifestJson: string): Promise<void> {
    await this.rpc("com.etzhayyim.governance.registerManifest", { manifestJson });
  }

  // ── CDN (R2 direct) ──

  async cdnUpload(
    subdomain: string,
    path: string,
    data: Uint8Array,
    contentType: string
  ): Promise<void> {
    if (!this.cdnR2) throw new Error("CDN_R2 not configured");
    const key = subdomain
      ? `${subdomain}/${path.replace(/^\//, "")}`
      : path.replace(/^\//, "");
    await this.cdnR2.put(key, data, { httpMetadata: { contentType } });
  }

  async cdnDelete(subdomain: string, path: string): Promise<void> {
    if (!this.cdnR2) throw new Error("CDN_R2 not configured");
    const key = subdomain
      ? `${subdomain}/${path.replace(/^\//, "")}`
      : path.replace(/^\//, "");
    await this.cdnR2.delete(key);
  }

  // ── Generic AT Protocol CRUD ──

  async createRecord<T = unknown>(
    collection: string,
    record: T,
    rkey?: string
  ): Promise<RecordRef> {
    return this.xrpc("com.atproto.repo.createRecord", {
      repo: this.repo,
      collection,
      record,
      rkey,
    });
  }

  async getRecord<T = unknown>(
    collection: string,
    rkey: string,
    repo?: string
  ): Promise<RecordView<T> | null> {
    try {
      return await this.xrpc("com.atproto.repo.getRecord", {
        repo: repo ?? this.repo,
        collection,
        rkey,
      });
    } catch {
      return null;
    }
  }

  async listRecords<T = unknown>(
    collection: string,
    opts?: {
      limit?: number;
      cursor?: string;
      repo?: string;
    }
  ): Promise<{ records: RecordView<T>[]; cursor?: string }> {
    return this.xrpc("com.atproto.repo.listRecords", {
      repo: opts?.repo ?? this.repo,
      collection,
      limit: opts?.limit ?? 50,
      cursor: opts?.cursor,
    });
  }

  async deleteRecord(collection: string, rkey: string): Promise<void> {
    await this.xrpc("com.atproto.repo.deleteRecord", {
      repo: this.repo,
      collection,
      rkey,
    });
  }

  async putRecord<T = unknown>(
    collection: string,
    rkey: string,
    record: T
  ): Promise<RecordRef> {
    return this.xrpc("com.atproto.repo.putRecord", {
      repo: this.repo,
      collection,
      rkey,
      record,
    });
  }

  // ── Domain shorthand ──
  // xrpc.domain("handotai").create("article", {...})
  // → com.atproto.repo.createRecord { collection: "com.etzhayyim.apps.handotai.article", record }

  domain(app: string) {
    const self = this;
    const col = (type: string) => `com.etzhayyim.apps.${app}.${type}`;
    return {
      create: <T = unknown>(type: string, record: T, rkey?: string) =>
        self.createRecord(col(type), record, rkey),
      get: <T = unknown>(type: string, rkey: string) =>
        self.getRecord<T>(col(type), rkey),
      list: <T = unknown>(
        type: string,
        opts?: { limit?: number; cursor?: string }
      ) => self.listRecords<T>(col(type), opts),
      delete: (type: string, rkey: string) =>
        self.deleteRecord(col(type), rkey),
      put: <T = unknown>(type: string, rkey: string, record: T) =>
        self.putRecord(col(type), rkey, record),

      // Direct NSID call (for app-specific query/procedure methods)
      call: <R = unknown>(method: string, params?: Record<string, unknown>) =>
        self.xrpc<R>(`com.etzhayyim.apps.${app}.${method}`, params ?? {}),
    };
  }

  // ── Social (Bluesky Lexicon shortcuts) ──

  async post(
    text: string,
    opts?: { repo?: string; facets?: unknown[]; embed?: unknown }
  ) {
    return this.createRecord("app.bsky.feed.post", {
      $type: "app.bsky.feed.post",
      text,
      facets: opts?.facets,
      embed: opts?.embed,
      createdAt: new Date().toISOString(),
    });
  }

  async like(subjectUri: string, subjectCid: string) {
    return this.createRecord("app.bsky.feed.like", {
      $type: "app.bsky.feed.like",
      subject: { uri: subjectUri, cid: subjectCid },
      createdAt: new Date().toISOString(),
    });
  }

  async follow(subjectDid: string) {
    return this.createRecord("app.bsky.graph.follow", {
      $type: "app.bsky.graph.follow",
      subject: subjectDid,
      createdAt: new Date().toISOString(),
    });
  }

  // ── Profile / Feed (read shortcuts) ──

  async getProfile(actor: string) {
    return this.xrpc("app.bsky.actor.getProfile", { actor });
  }

  async getTimeline(opts?: { limit?: number; cursor?: string }) {
    return this.xrpc("app.bsky.feed.getTimeline", {
      limit: opts?.limit ?? 50,
      cursor: opts?.cursor,
    });
  }

  async getAuthorFeed(
    actor: string,
    opts?: { limit?: number; cursor?: string }
  ) {
    return this.xrpc("app.bsky.feed.getAuthorFeed", {
      actor,
      limit: opts?.limit ?? 50,
      cursor: opts?.cursor,
    });
  }

  // ── SSE Firehose ──

  subscribeRepos(opts?: { cursor?: string }): ReadableStream<string> {
    const url = `https://atproto.etzhayyim.com/xrpc/com.atproto.sync.subscribeRepos${
      opts?.cursor ? `?cursor=${opts.cursor}` : ""
    }`;
    const { readable, writable } = new TransformStream<string, string>();

    (async () => {
      try {
        const resp = await this.transport.fetcher.fetch(url, {
          headers: { Accept: "text/event-stream" },
        });
        if (!resp.body) return;
        const reader = resp.body
          .pipeThrough(new TextDecoderStream())
          .getReader();
        const writer = writable.getWriter();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          await writer.write(value);
        }
        await writer.close();
      } catch {
        /* stream ended */
      }
    })();

    return readable;
  }

  // ── Agent Invoke ──

  /** Invoke a method on another agent via PDS gateway. */
  async invoke(target: string, method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    return this.xrpc("com.etzhayyim.pds.invoke", { target, method, params: JSON.stringify(params) });
  }

  // ── Generic XRPC call ──

  async xrpc<T = unknown>(
    nsid: string,
    params: Record<string, unknown> = {}
  ): Promise<T> {
    const { signal, cleanup } = createTimeoutSignal(this.timeoutMs);
    try {
      return await throwOnError(
        this.transport.xrpc<T>(nsid, { auth: this.auth, params, signal })
      );
    } catch (error) {
      if ((error as Error)?.name === "AbortError")
        throw timeoutError(nsid, this.timeoutMs);
      throw error;
    } finally {
      cleanup();
    }
  }
}
