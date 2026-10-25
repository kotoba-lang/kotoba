# kotobase-server

Platform-independent XRPC handler + async/sync storage bridge for a
[`kotobase-peer`](https://github.com/kotoba-lang/kotobase-peer)-backed
worker. **No deploy surface** — this repo has no `wrangler.jsonc`, no
Cloudflare bindings, no storage adapter of its own. It's the shared
implementation a deployable Worker (e.g. `gftdcojp/net-kotobase`) wraps
with a thin, platform-specific shell.

## Why this exists

Two independent Cloudflare Worker deployments (`net-kotobase/kotobase-cf-wasm`
and `kotoba-lang/kotobase-cljc-worker`) each reimplemented the same
`ai.gftd.apps.kotobase.datomic.{datoms,transact,q,pull,fold}` XRPC surface
over `kotobase-peer`, independently, without either knowing about the
other. `kotobase-cljc-worker`'s version was further along (filtered reads,
retraction support, a lazy block-miss trampoline instead of a full-prefix
warm, real production incident fixes) — this repo extracts its
storage/platform-independent parts so there is ONE implementation, not two
drifting copies.

## What's here

```
kotobase.server.handler      -- pure XRPC dispatch, a function of an
                                 injected `store` map (get-fn/put!/head-get/
                                 head-put!/blind-fn/encrypt-fn/decrypt-fn).
                                 21 methods total:
                                   -- original 5: datoms/transact/q/pull/fold
                                   -- Datomic Cloud-style read helpers added
                                      since: entity/entid/ident/asOf/since/
                                      history/basisT/dbStats/seekDatoms/
                                      indexRange/indexPull/pullMany/tx/
                                      txRange/log/sync
kotobase.server.trampoline    -- with-blocks: bridges any async block store
                                 (R2, B2, IndexedDB, ...) to kotobase-peer's
                                 synchronous get-fn contract, fetching only
                                 the blocks a read/write actually touches
kotobase.server.ipns          -- pure decision logic for
                                 com.etzhayyim.apps.kotoba.ipns.{head,publish}
                                 (signature-gated writes, no CACAO)
kotobase.server.runtime       -- platform-neutral block/head/claim/authority/
                                 KMS/audit ports and fail-closed service
                                 validation for secured network runtimes
kotobase.server.shadow        -- failure-isolated primary/shadow comparison;
                                 deployment owns sampling, waitUntil scheduling,
                                 normalization and telemetry
```

`kotobase.server.shadow/wrap-handler` is the migration seam from the legacy
`kotobase-peer` path to an `IEngine` adapter. The primary response is always
authoritative. A deployment injects a same-shape shadow handler, removes
expected physical differences through `normalize`, and schedules the task via
its own lifetime primitive (for Workers, `ctx.waitUntil`). This repository does
not choose an engine or hide mismatches by changing the public response.

Storage adapters (R2/B2/IndexedDB), the actual HTTP/`Response` shell, routes,
and product policy are the consumer's job. CACAO/delegation verification,
normalized `SecurityContext`, keyring envelopes, audit receipts, replay and
idempotency orchestration are common security semantics and are being
consolidated here; deployable consumers must not fork them. The sole public
Cloudflare product owner is `gftdcojp/net-kotobase`.

## Crypto is injected, not policy

`kotobase-peer`'s `blind-fn`/`encrypt-fn`/`decrypt-fn` seam (ADR-2607051000,
no silent default) is threaded through `store` like the storage fns are —
the engine remains adapter-neutral. Private/sealed network runtimes use the
common versioned AES-256-GCM-SIV/keyring profile; plaintext passthrough is only
for explicit local/legacy-public use.

## Testing

```
npm install
npm run test:cljs
```

### Cold authorization reads (2026-09-13)

Read visibility and owner-attribute lookups forward the store's optional `:async-get-fn`, just like the data read and write-policy lookup. Without it a cold graph restarts the whole handler per missing metadata block before authorization completes. The same policy rows, owner set, and filters remain authoritative. A cold-store regression permits synchronous head access only and proves anonymous redaction, owner-only visibility, and capability-based visibility after a fold.

Consumer compiled verification: 54 handler tests / 322 assertions. The patch removes five failures in the new cold-store regression; one pre-existing clearance-level failure remains unchanged. This result uses the production graph consumer's exact dependency set, not a claim that the full server suite is green.

### Write-side novelty metadata (2026-09-13)

Ordinary transactions and knowledge-graph ingestion now pass the store's
`blind-fn` into `commit!`. The peer pin includes index-position-correct subject
routing and keyed attribute membership. Without this wiring, even a missing
policy entity caused every write to decrypt all unreflected transactions.
Existing legacy transactions remain conservative until compacted.

The compiled consumer handler suite passes 55 tests / 332 assertions, including
both write entry points followed by policy and bound-attribute reads over 20
unrelated transactions. Those reads decrypt zero unrelated payloads. Existing
policy/owner/clearance tests remain enabled. The full-snapshot cache regression
now expects the incremental ClojureScript fold to avoid whole-row caches; JVM
rebuild retains its cache expectations. Qualification uses Shadow CLJS, not the
native compiler path.

### Direct materialized-view discovery

`do-view` forwards both the blind function and direct async fetch seam to the
peer, matching the other narrow read paths. A cold fixture allows only the two
synchronous control-root reads; the stored view must use direct discovery and
return its original row. Compiled consumer handler suite: 56 tests / 335
assertions pass with the merged selective-view peer pin. Stored data format and
read visibility policy remain unchanged.
