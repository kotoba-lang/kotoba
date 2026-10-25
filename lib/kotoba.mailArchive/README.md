# mail-archive

Bulk-archive a Gmail mailbox into content-addressed `.eml`-style blobs plus a
queryable index, in the kotoba-lang idiom: portable `.cljc`, **one `Store`
protocol with two backends that must return identical query answers** — a
Datomic-API-compatible store (`langchain.db`) and a datalog-backed nbb query
surface (`kotoba-lang/datalog`, via `mail-archive.datascript-store`) —
loaded from one shared schema, proven equal by a shared contract test.

## Why this exists

A prior session built an ad hoc Python/bash pipeline
(`orgs/personal/bin/*.py`, `orgs/personal/bin/datomic/`) that bulk-archives a
Gmail mailbox into content-addressed `.eml` files + a Datomic (JVM,
`com.datomic/local`) index, with a *separate*, hand-written nbb query loader
that flattened `email/from`/`to`/`cc` to bare strings (losing the person graph). That worked, but the two query surfaces
diverged (Datomic joined a person graph; the DataScript script did not), the
schema was Datomic-native (`{:db/ident ...}` vectors), and none of it was
portable `.cljc` or tested.

This repo re-does that capability properly: the **same schema** and the **same
Datalog** answer identically whether the backend is the Datomic-API store
(`langchain.db` — swappable to Datomic Local or a kotoba-server pod) or
`kotoba-lang/datalog` (browser-native / zero-JVM, via nbb). It generalizes the
`Store`-protocol / dual-backend / shared-contract-test shape ADR-2607122000
established for `cloud-murakumo-market-intel` (itself after `gftd-talent-actor`'s
`talent.store`) to a domain that actually needs entity **refs** (email → person,
email → blob), not just flat attributes.

## Design

```text
mail-archive.schema.edn        the SSoT schema map (DataScript-style, not Datomic-native
                               vectors) that BOTH backends load — blob / person / email /
                               attachment, with :db.type/ref links and cardinalities

mail-archive.store             Store protocol (transact! / q / pull) + LangchainDbStore
                               (Datomic-API-compatible, thin delegation to langchain.db)

mail-archive.datascript-store  the nbb query backend (`kotoba-lang/datalog`): same three
                               ops as plain fns, with TWO-PASS ref flattening so it accepts the
                               same nested-map tx-data langchain.db does

mail-archive.blob-store        BlobStore protocol + LocalDirBlobStore (content-addressed by
                               sha256 hex = cid, one file per blob)

mail-archive.auth              OAuth2 token acquisition/refresh (org-ietf-oauth2 shaping +
                               injectable :http-fn) + CredentialStore (macOS Keychain default,
                               mirroring orgs/personal/bin/google-auth.py)

mail-archive.ingest            backfill (paginate gmail.threads, decode base64url bodies,
                               normalize addresses via mail.inbound/from-parts, content-address,
                               transact) + incremental sync (users.history.list from a cursor)
```

**Portability / runtime.** `store`/`blob-store`/`auth`/`ingest` are `.cljc` but
JVM-only in practice: they lean on `com-gmail` (JVM-only today), `java.util.Base64`,
`java.time`, and macOS `security`. The **datalog query backend is a separate nbb
entrypoint** (`.cljs`) backed by `kotoba-lang/datalog` via `nbb.edn` —
it can't be `:require`d from a JVM `.cljc` namespace. Address normalization
(`mail.message`) and the OAuth request/response shaping (`oauth2.core`) are the
genuinely portable parts.

**Query parity (the point).** Every HTTP boundary is an injectable `:http-fn`
(`{:url :method :headers :body} -> {:status :body}`, com-gmail's convention), so
nothing here needs a live account to test. `test/mail_archive/store_contract_test.cljk`
(JVM) and `test/mail_archive/datascript_contract_test.cljk` (nbb) transact the
**same** sample entities and run the **same** Datalog (by-thread, by-sender via a
person ref, by-label, date-range, blob ref join) — asserting identical answers.

**Design choices worth knowing.**

- `:email/date` is a `YYYYMMDD` **integer**, not an ISO string, so date-range
  queries use numeric `<`/`<=` — the only comparators `langchain.db` and
  `datalog.core` share (both treat `<`/`<=` as numeric).
- `:email/cid` = sha256 hex of the reconstructed source bytes (the bytes the
  BlobStore stores), so the content id is reproducible from content.
- Incremental-sync's `historyId` cursor is caller-owned (injected
  `cursor-get`/`cursor-set!`) — no schema change, keeps the store to the mail graph.

## Usage

```clojure
(require '[mail-archive.store :as store]
         '[mail-archive.blob-store :as blob-store]
         '[mail-archive.auth :as auth]
         '[mail-archive.ingest :as ingest])

;; a fresh in-memory Datomic-API-compatible store over the shared schema
(def s (store/langchain-store))
(def blobs (blob-store/local-dir-blob-store "/path/to/blobs"))

;; obtain an access token (refresh_token grant, secrets from macOS Keychain)
(def token (auth/access-token (auth/keychain-credential-store) "jun784"))

;; backfill everything matching a Gmail search, then query the index
(ingest/backfill! s blobs {:token token :q "in:anywhere"})
(store/q s '[:find ?subj :where [?p :person/id "someone@example.com"]
                                [?e :email/from ?p] [?e :email/subject ?subj]])

;; later: incremental sync from a persisted historyId cursor
(def cursor (atom "SOME_HISTORY_ID"))
(ingest/incremental-sync! s blobs {:cursor-get #(deref cursor) :cursor-set! #(reset! cursor %)}
                          {:token token})
```

## Tests

```sh
kbb -M:test                                       # JVM: store / ingest / auth contract tests
kbb --backend sci test/mail_archive/datascript_contract_test.cljk  # nbb datalog parity twin (exits non-zero on mismatch)
kbb -M:lint                                        # clj-kondo
```

No live Gmail account required — every test injects a stub `:http-fn` and a fake
in-memory `CredentialStore` and asserts on request shape / transformed data
(com-gmail's own pattern). The two contract tests are the parity proof: same
query, same answer, both backends.
