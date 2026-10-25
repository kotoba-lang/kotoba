/**
 * @etzhayyim/sdk-mock
 *
 * In-memory mock implementation of the Etzhayyim SDK for testing
 * kotoba reference implementations without PDS/IPFS/L2 dependencies.
 *
 * Simulates:
 * - `write<T>(params)` → persists to in-memory store, returns URI
 * - `read<T>(params)` → retrieves with optional pagination
 * - Collection namespace isolation
 * - Record ordering by insertion sequence (TID-like ordering)
 *
 * Usage:
 * ```ts
 * const mock = new MockEtzhayyim({ did: "did:web:example.com" });
 * await mock.write({ collection: "com.etzhayyim.apps.example.record", record: {...}, rkey: "key-1" });
 * const result = await mock.read({ collection: "com.etzhayyim.apps.example.record", rkey: "key-1" });
 * ```
 */

export interface MockReadResult<T> {
  records: Array<{ uri: string; value: T }>;
  cursor?: string;
}

export interface MockWriteReceipt {
  uri: string;
}

export interface MockReadParams {
  collection: string;
  rkey?: string;
  cursor?: string;
  limit?: number;
}

export interface MockWriteParams<T = unknown> {
  collection: string;
  record: T;
  rkey: string;
}

/** Mirrors @etzhayyim/sdk EncryptedWriteOpts (subset used by kotoba registries). */
export interface MockEncryptedWriteOpts<T = unknown> {
  /** Wrapper collection. Default: com.etzhayyim.encrypted.record. */
  collection?: string;
  /** Inner-lexicon NSID (routing/filtering metadata). */
  innerType?: string;
  /** Plaintext body. */
  record: T;
  /** DIDs granted read-cap. Sender auto-added unless wrapToSelf:false. */
  recipients: string[];
  wrapToSelf?: boolean;
  rkey?: string;
}

export interface MockEncryptedWriteReceipt {
  uri: string;
  cid: string;
  keyId: string;
  keyWraps: Array<{ recipient: string; uri: string; cid: string }>;
  skipped: Array<{ recipient: string; reason: string }>;
}

export interface MockEncryptedReadOpts {
  collection?: string;
  innerType?: string;
  cursor?: string;
  limit?: number;
  fromSenders?: string[];
}

export interface MockEncryptedReadResponse<T> {
  records: Array<{
    uri: string;
    cid: string;
    value: T;
    sender: string;
    createdAt: string;
  }>;
  cursor?: string;
  failed: Array<{ uri: string; reason: string }>;
}

const ENC_DEFAULT_COLLECTION = "com.etzhayyim.encrypted.record";

/**
 * In-memory Etzhayyim SDK mock.
 *
 * Stores records in nested maps: collection → rkey → { uri, value, writtenAt, seq }.
 * Pagination is ordered by insertion sequence (ascending).
 * Idempotent writes (same collection + rkey) overwrite the previous value.
 */
export class MockEtzhayyim {
  public did: string;
  /** collection → rkey → { uri, value, writtenAt, seq } */
  private store = new Map<
    string,
    Map<string, { uri: string; value: unknown; writtenAt: number; seq: bigint }>
  >();
  private nextSeq = 1n;
  /** E2E envelope store: collection → rkey → { plaintext value, sender, recipients, innerType, … } */
  private encStore = new Map<
    string,
    Map<
      string,
      {
        uri: string;
        cid: string;
        value: unknown;
        sender: string;
        recipients: string[];
        innerType?: string;
        createdAt: string;
        seq: bigint;
      }
    >
  >();

  constructor(opts: { did: string }) {
    this.did = opts.did;
  }

  /**
   * Write an E2E-encrypted record (Tahoe envelope, ADR-2605181100). The mock
   * stores the plaintext keyed by the wrapper collection and enforces read-cap
   * by recipient DID. Sender (this.did) is auto-added unless wrapToSelf:false.
   */
  async encryptedWrite<T extends Record<string, unknown>>(
    opts: MockEncryptedWriteOpts<T>
  ): Promise<MockEncryptedWriteReceipt> {
    const collection = opts.collection ?? ENC_DEFAULT_COLLECTION;
    let col = this.encStore.get(collection);
    if (!col) {
      col = new Map();
      this.encStore.set(collection, col);
    }
    const seq = this.nextSeq++;
    const rkey = opts.rkey ?? `enc-${seq}`;
    const recipients = [
      ...new Set([
        ...(opts.recipients ?? []),
        ...(opts.wrapToSelf === false ? [] : [this.did]),
      ]),
    ];
    const uri = `at://${this.did}/${collection}/${rkey}`;
    const cid = `bafyenc${seq}`;
    const keyId = `key${seq}`.padEnd(8, "0").slice(0, 16);
    col.set(rkey, {
      uri,
      cid,
      value: opts.record,
      sender: this.did,
      recipients,
      innerType: opts.innerType,
      createdAt: new Date().toISOString(),
      seq,
    });
    return {
      uri,
      cid,
      keyId,
      keyWraps: recipients.map((r) => ({
        recipient: r,
        uri: `at://${this.did}/com.etzhayyim.encrypted.keyWrap/${rkey}-${r}`,
        cid: `bafykw${seq}`,
      })),
      skipped: [],
    };
  }

  /**
   * Read + decrypt E2E records the caller (this.did) holds a read-cap for.
   * Filters by recipient access-control and optional innerType, ordered by
   * insertion sequence with offset-cursor pagination.
   */
  async encryptedRead<T>(
    opts: MockEncryptedReadOpts = {}
  ): Promise<MockEncryptedReadResponse<T>> {
    const collection = opts.collection ?? ENC_DEFAULT_COLLECTION;
    const col = this.encStore.get(collection);
    if (!col) return { records: [], failed: [] };
    let all = [...col.values()].filter((r) => r.recipients.includes(this.did));
    if (opts.innerType) all = all.filter((r) => r.innerType === opts.innerType);
    all.sort((a, b) => (a.seq < b.seq ? -1 : a.seq > b.seq ? 1 : 0));
    const startIdx = opts.cursor ? Number(opts.cursor) || 0 : 0;
    const limit = opts.limit ?? 50;
    const page = all.slice(startIdx, startIdx + limit);
    const cursor =
      startIdx + limit < all.length ? String(startIdx + limit) : undefined;
    return {
      records: page.map((r) => ({
        uri: r.uri,
        cid: r.cid,
        value: r.value as T,
        sender: r.sender,
        createdAt: r.createdAt,
      })),
      cursor,
      failed: [],
    };
  }

  /** Test helper: count E2E records in a wrapper collection (sender's own view). */
  encCount(collection = ENC_DEFAULT_COLLECTION): number {
    return this.encStore.get(collection)?.size ?? 0;
  }

  /**
   * Write (create or update) a record.
   * Returns the AT URI in format: at://{did}/{collection}/{rkey}
   */
  async write<T>(params: MockWriteParams<T>): Promise<MockWriteReceipt> {
    let col = this.store.get(params.collection);
    if (!col) {
      col = new Map();
      this.store.set(params.collection, col);
    }
    const uri = `at://${this.did}/${params.collection}/${params.rkey}`;
    const seq = this.nextSeq++;
    col.set(params.rkey, { uri, value: params.record, writtenAt: Date.now(), seq });
    return { uri };
  }

  /**
   * Read records from a collection.
   *
   * If `rkey` is supplied, fetch that single record only.
   * Otherwise, list all records ordered by insertion sequence (ascending),
   * with optional cursor (encoded as the rkey of the last item) and limit.
   */
  async read<T>(params: MockReadParams): Promise<MockReadResult<T>> {
    const col = this.store.get(params.collection);
    if (!col) return { records: [] };

    // Single record fetch
    if (params.rkey) {
      const r = col.get(params.rkey);
      if (!r) return { records: [] };
      return { records: [{ uri: r.uri, value: r.value as T }] };
    }

    // List path: sort by insertion sequence (ascending), apply cursor and limit.
    const all = [...col.values()].sort((a, b) => {
      if (a.seq < b.seq) return -1;
      if (a.seq > b.seq) return 1;
      return 0;
    });

    let startIdx = 0;
    if (params.cursor) {
      // Cursor is the rkey of the last item in the previous page.
      // Find it and start after it.
      const cursorRkey = params.cursor;
      const foundIdx = [...col.entries()].findIndex(
        ([rkey]) => rkey === cursorRkey
      );
      if (foundIdx >= 0) {
        // Find the position in the sorted array
        const foundRecord = col.get(cursorRkey);
        const sortedIdx = all.findIndex((r) => r.seq === foundRecord!.seq);
        startIdx = sortedIdx >= 0 ? sortedIdx + 1 : 0;
      }
    }

    const limit = params.limit ?? 50;
    const page = all.slice(startIdx, startIdx + limit);
    const nextCursor =
      page.length === limit && startIdx + limit < all.length
        ? ([...col.entries()].find(([, r]) => r.seq === all[startIdx + limit]?.seq)?.[0] ?? undefined)
        : undefined;

    return {
      records: page.map((r) => ({ uri: r.uri, value: r.value as T })),
      cursor: nextCursor,
    };
  }

  /**
   * Test helper: dump all records in a collection in insertion order.
   */
  dump(collection: string): unknown[] {
    const col = this.store.get(collection);
    if (!col) return [];
    return [...col.values()]
      .sort((a, b) => {
        if (a.seq < b.seq) return -1;
        if (a.seq > b.seq) return 1;
        return 0;
      })
      .map((r) => r.value);
  }

  /**
   * Test helper: get record count in a collection.
   */
  count(collection: string): number {
    return this.store.get(collection)?.size ?? 0;
  }

  /**
   * Test helper: reset all collections and sequence counter.
   */
  clear(): void {
    this.store.clear();
    this.encStore.clear();
    this.nextSeq = 1n;
  }
}
