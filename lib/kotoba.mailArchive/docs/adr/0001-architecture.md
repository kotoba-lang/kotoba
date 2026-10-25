# ADR-0001 — mail-archive architecture: one schema, two query-equal backends over a content-addressed Gmail archive

- Status: Accepted
- Date: 2026-07-13
- Context tags: gmail-api, content-addressing, datomic-datascript-parity, portable-cljc, oauth2
- Builds on:
  - `kotoba-lang/com-gmail` (ADR-2607061423 — the portable Gmail API v1 client /
    `:http-fn` injection this ingest consumes)
  - the com-gmail / org-ietf-imap channel split (ADR-2607061503 — Gmail's REST
    API is the right surface for label/thread reads, not IMAP)
  - `kotoba-lang/mail` (ADR-2606301200 — `mail.inbound`/`mail.message`
    provider-independent address/message normalization, reused here rather than
    hand-rolled)
  - ADR-2607122000 (`cloud-murakumo-market-intel` — the `Store` protocol +
    Datomic-API ⊣ DataScript dual-backend + shared-contract-test parity precedent
    this repo generalizes to a ref-bearing domain)

## Decision

Re-do the ad hoc Python/bash Gmail archiver (`orgs/personal/bin/*.py`,
`orgs/personal/bin/datomic/`) as a kotoba-lang `.cljc` library with:

- **One shared schema** (`src/mail_archive/schema.edn`) in DataScript-style *map*
  form (`{attr {:db/unique ... :db/valueType ... :db/cardinality ...}}`), loaded
  identically by both backends — NOT the Datomic-native `{:db/ident ...}` vector
  the prior art used. It has real entity **refs** (`:email/from`/`:to`/`:cc` →
  person, `:email/blob` → blob, `:email/attachments` → attachment,
  `:attachment/blob` → blob, `:person/canonical` → person).
- **One `Store` protocol, two backends** proven query-equal by a shared contract
  test:
  - `LangchainDbStore` — wraps `langchain.db` (a Datomic-API-compatible in-memory
    EAV store; swappable to Datomic Local or a kotoba-server pod without touching
    a query).
  - `DataScriptStore` — real DataScript via npm `datascript`, reachable only from
    nbb; a separate `.cljs` entrypoint (not the same namespace) because the npm
    package can't be `:require`d from a JVM `.cljc` namespace.
- **Content-addressed blobs.** Every raw message is reconstructed into a canonical
  RFC822-ish source, stored under its sha256 hex (`cid`) via a `BlobStore`, and
  referenced from `:email/blob`. Same bytes → same cid → stored once.
- **Ingest** = paginated backfill (`gmail.threads/list-threads` loop on
  `:nextPageToken`) + incremental sync (`users.history.list` from a caller-owned
  historyId cursor). **Auth** = OAuth2 refresh-token flow built on
  `org-ietf-oauth2`'s pure shaping + an injectable `:http-fn`, with secrets read
  from macOS Keychain (mirroring `orgs/personal/bin/google-auth.py`).

## Why one schema and a contract test, not two ad hoc loaders

The prior art had two query surfaces that had silently diverged: the Datomic
loader (`warehouse/load.clj`) joined `email/from`/`to`/`cc` through a `:person/*`
ref graph, while the standalone nbb+datascript script
(`orgs/personal/bin/mail-datascript.cljs`) flattened those to bare address
strings — so "who did I hear from" returned different structures depending on
which runtime you asked. That's exactly the failure mode ADR-2607122000's
`Store`-parity pattern exists to prevent. Making the schema the single source of
truth and pinning both backends to a shared contract test (same entities, same
Datalog, asserted-identical answers) is what keeps a Datomic-side answer and a
browser-side DataScript answer the same fact.

## Why the DataScript backend needs its own two-pass ref flattening

DataScript itself supports nested-map ref expansion — but not through the JS
interface nbb uses. The established nbb pattern (`manifest/edn-query.cljs`)
marshals cljs maps to JS objects and stringifies any nested map
(`(map? v) (pr-str v)`), so a nested ref map becomes a useless string, not a
linked entity. `mail_archive.datascript_store/flatten-tx` therefore does its own
expansion: it hoists every nested map under a ref attr into its own entity with a
fresh negative tempid and replaces the nested map with that tempid (a scalar the
JS layer passes through). Unique-identity upsert then unifies tempids carrying the
same `:person/id`/`:blob/cid` into one entity — matching `langchain.db` exactly —
so the person graph resolves identically on both sides. This is the concrete
thing that makes DataScriptStore *better than* the prior flatten-to-strings
script.

## Module boundaries

```
schema.edn         attribute/ref/cardinality/uniqueness SSoT (map form, both backends)
store              Store protocol (transact! / q / pull) + LangchainDbStore
datascript-store   DataScript backend (nbb): create-store / transact! (two-pass flatten) / q / pull
blob-store         BlobStore protocol + LocalDirBlobStore (sha256-cid, one file per blob)
auth               token-request! / exchange-code! / refresh! / access-token + CredentialStore (Keychain)
ingest             backfill! (paginate + decode + normalize + content-address + transact) + incremental-sync!
```

## Non-goals

- **MIME beyond text/plain + attachment enumeration niceties.** `ingest/text-body`
  takes the first `text/plain` part (falling back to top-level body); rich
  multipart/HTML reconstruction and per-attachment blob extraction are left to a
  follow-up (the schema already has `:email/attachments`/`:attachment/*` for it).
- **A unified CLJS build of the whole library.** Only the DataScript backend is
  cljs (nbb); ingest/auth/blob-store are JVM-only because com-gmail, Base64,
  java.time and Keychain are. Per the repo runtime priority this is acceptable —
  the browser-facing surface (querying an already-built index) is the cljs part.
- **The OAuth consent-screen UX.** `auth/authorize-url` shapes the consent URL
  (PKCE-ready); actually running a localhost redirect server / opening a browser
  is the caller's job (as `google-auth.py` does).
- **Cursor persistence policy.** `incremental-sync!` takes injected
  `cursor-get`/`cursor-set!`; where the historyId lives (a file, the Store, a KV)
  is the caller's choice — no schema attr is spent on it.

## Consequences

- The same schema + Datalog now answer identically on the server (Datomic-API,
  `langchain.db`) and in the browser (DataScript), closing the divergence the two
  prior loaders had.
- `com-gmail` has no `history`/`messages` namespace yet, so `ingest/list-history`
  and `ingest/get-message` call `gmail.client/request!` directly (documented
  deviation — same auth/transport seam, still fully stubbable). If com-gmail grows
  those namespaces, ingest can switch to them without changing its callers.
- Follow-up (not done by this ADR): west manifest registration
  (`kbb --backend sci scripts/gen-west-manifest.cljk --entry mail-archive`) and RAD/registry
  bookkeeping, handled by the superproject's API-based manifest tooling.
