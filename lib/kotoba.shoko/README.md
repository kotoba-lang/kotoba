# shoko (書庫)

書庫 — a **storage-governance control plane**: an archive-LLM ⊣
ArchiveGovernor StateGraph that drafts archival records for
[`kotoba-lang/drive`](https://github.com/kotoba-lang/drive)'s file/folder
EDN model and grants principals access to them, but never grants access
itself. The actor is **propose → draft only**: a draft commits as data (a
*casual commit* — phase-gated auto-approval is fine, it's just a proposed
archival record sitting there for review); actually granting a principal
access (`:file/share`) is **always a human call**, regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`kekkai`](https://github.com/kotoba-lang/kekkai)
(coord-LLM ⊣ TailnetGovernor), [`teian`](https://github.com/kotoba-lang/teian)
(deck-LLM ⊣ BriefingGovernor) and
[`koyomi`](https://github.com/kotoba-lang/koyomi) (schedule-LLM ⊣
ComplianceGovernor). Here it is **archive-LLM ⊣ ArchiveGovernor** —
architecturally a hybrid of kekkai's deny-by-default ACL shape (`kekkai.acl`,
`deny-by-default-violations`) and teian's/koyomi's draft/publish shape: the
file itself is held as `kotoba-lang/drive`'s pure EDN, verbatim, while "who
can access it" is decided by shoko's own deny-by-default grant ledger.

> Charter: **(G1)** propose → draft only, no direct actuation — the actor
> writes a proposed archival record, a human turns it into an access grant;
> **(G2)** granting access is **always a human call** (high-stakes),
> independent of rollout phase; **(G3)** kotoba-native — activity/file/grant
> facts are durable EAVT ground facts, drafts are transient until committed;
> **(G4)** shoko holds `kotoba-lang/drive` EDN verbatim as draft content — it
> does not reimplement the file/folder data model; **(G5)** deny-by-default —
> `drive.model` has zero ACL concept of its own (verified — grepping
> `acl|access-control|permission|share` across it is a zero hit), so an
> entirely unregistered principal can never receive a share, regardless of
> how confident the archive-LLM is.

## The core contract

```
file/activity facts (the itonami activity an archive request is drafted for)
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌────────────┐  proposal: draft /  ┌───────────────────┐
   │ archive-LLM │  share              │ ArchiveGovernor    │  (independent system)
   │ (sealed)    │ ──────────────────▶ │  no-actuation ·     │
   └────────────┘  + cited facts       │  subject-exists ·   │
                                       │  share-requires-acl ·│
                                       │  tenant-isolation    │
                                       └──────────┬──────────┘
                            commit ◀──────────────┼──────────▶ hold (missing-
                     (draft: casual          escalate          file/activity /
                      commit, auto ok            │             unregistered-
                      at phase≥2;                ▼             principal /
                      share: ALWAYS         人間 承認           tenant-mismatch;
                      here) ────────▶  (shareは常に人間)         un-overridable)
```

**The actor never grants access to a file the ArchiveGovernor would reject,
and archive-LLM never actuates directly.** HARD invariants force **hold**
(a human cannot approve past a missing file/activity, a share to a principal
who has never been vouched for anywhere in the grant ledger, or a file
declared for the wrong tenant); a clean share still routes to a human.

## Run

```bash
kbb -M:dev:run     # drive: draft → share through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register a file (observe → ground fact) → draft an archival record
for a known, clean-tenant file (phase 3 → clean → auto-commits, no
interrupt) → share it with an already-known principal (**always** human
sign-off, even though clean) → attempt to share a different file with an
entirely unregistered principal (**HARD HOLD**, un-overridable) → attempt to
draft a file registered under a different tenant (**HARD HOLD**) →
phase-0 disables drafting entirely → prints the storage-governance audit
ledger → swaps to `DatomicStore` with identical results.

## Layout

| File | Role |
|---|---|
| `src/shoko/model.cljk` | pure **draft**/**grant**/**activity** data shapes — `content` is verbatim `kotoba-lang/drive` EDN, never shoko's own representation |
| `src/shoko/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **storage-governance audit ledger** |
| `src/shoko/coordllm.cljk` | **archive-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); draft/share proposals |
| `src/shoko/governor.cljk` | **ArchiveGovernor** — no-actuation · subject-exists (independent/unconditional) · share-requires-acl (deny-by-default) · tenant-isolation · high-stakes |
| `src/shoko/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-draft → supervised (sharing always human) |
| `src/shoko/operation.cljk` | **ArchiveActor** — langgraph StateGraph; ingest vs assess flows |
| `src/shoko/archiveport.cljk` | **ArchiveTarget** port (`fetch-file`/`propose-revision!`/`share!`) + `mock-archiveport` (default, deterministic in-memory + injected Distributor fn) + `r2-archiveport` (JVM-only, opt-in — real Cloudflare R2 backend over R2's S3-compatible API, SigV4-signed plain HTTP, live-verified) |
| `src/shoko/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/shoko/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/shoko/query.cljk` | pure status lookups (`draft-status`/`shared-with?`/`known-principal?`) for callers that don't want to run the actor |
| `src/shoko/sim.cljk` | demo driver |
| `src/shoko/cli.cljk` | minimal JVM status-check entrypoint |
| `test/shoko/*_test.clj` | propose-only contract (happy path + adversarial per hard invariant, incl. a TOCTOU test) · store parity (Mem≡Datomic, incl. a seed-twice-per-id-upsert test) · CACAO |

## share-requires-acl: what "registered principal" means here

`drive.model` has zero ACL concept, so shoko carries its own deny-by-default
grant ledger (`shoko.model/grant`, keyed by `(principal, file-id)`). A
principal is **"known"** the moment ANY grant record exists for them — on
**any** file, not necessarily the one being shared right now. Demo data
pre-seeds one such grant (alice was onboarded onto `f-handbook` by HR before
this ledger's genesis, mirroring how kekkai's demo seeds pre-authorized
nodes). That means:

- alice (known via her `f-handbook` grant) **can** receive a brand-new share
  on a **different** file (`f-contract`) — she's vouched for somewhere in
  the ledger, so a new grant elsewhere is not a blind, unauthenticated act.
- an entirely unregistered principal (e.g. `"mallory-external"`, who has
  never appeared in the grant ledger at all) **can never** receive a first
  share — `share-requires-acl` holds it un-overridably, exactly like
  `kekkai.acl`'s `deny-by-default-violations` reject an edge with no backing
  ACL grant.

This is deny-by-default in the same spirit as kekkai's tag-ownership check:
being vouched for once (by whatever out-of-band onboarding process seeded
that first grant) is what lets an actor keep extending trust incrementally;
an unvouched-for identity is never trusted from zero.

## ArchiveTarget → real backend (injection)

`shoko.archiveport/mock-archiveport` is the runnable, deterministic
default — no network/creds. `share!` hands the already-governed content to
an injected `:distribute-fn` once per grant. A live notification/email
client is **not shipped here** — inject your own.

`shoko.archiveport/r2-archiveport` (JVM-only) is a REAL, opt-in
`ArchiveTarget` backed by a Cloudflare R2 bucket, speaking R2's
S3-compatible API over plain HTTP with hand-verified SigV4 signing (no AWS
SDK) — shoko is a plain JVM library, not a Cloudflare Worker, so it can't use
the R2Bucket binding app-aozora's PDS Worker uses (ADR-2607071000); this is
the JVM-side equivalent. `fetch-file` = GET object, `share!` = PUT object
(keyed by `file-id`, EDN-encoded). Mock stays the default everywhere — real
R2 is only ever used when explicitly constructed and injected:

```clojure
(require '[shoko.archiveport :as archiveport])
;; :account-id/:access-key-id/:secret-access-key fall back to env
;; R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY when omitted
;; (see scripts/r2-creds.bb for the env→1Password resolution used to get
;; real creds into a shell for manual verification — never in code/CI).
(archiveport/r2-archiveport {:bucket "cloud-itonami-shoko-archive"})
```

Live-verified (2026-07-07): a real `share!`/`fetch-file` round trip against
bucket `cloud-itonami-shoko-archive` — 236 bytes PUT, 236 bytes GET back,
byte-for-byte identical (`java.util.Arrays/equals`), cleaned up after. The
SigV4 canonicalization is cross-checked function-for-function against
`kotobase.sigv4-test`'s golden vectors (gftdcojp/net-kotobase clj-edge, the
proven cljs implementation this JVM port mirrors). The automated suite
(`test/shoko/archiveport_test.cljk`) covers request-building against an
injected fake `:http-fn` only — no real network/creds in CI.

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as kekkai/teian/koyomi)
(require '[shoko.kotoba :as k] '[shoko.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".shoko/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real archive-LLM + a real ArchiveTarget
(require '[langchain.model :as model] '[shoko.operation :as op]
         '[shoko.coordllm :as coordllm] '[shoko.archiveport :as archiveport])
(op/build store
  {:advisor (coordllm/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :archiveport (archiveport/r2-archiveport {:bucket "cloud-itonami-shoko-archive"
                                             :distributor my-real-distribute-fn})})
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**ArchiveGovernor always hold/escalates** it (no path from a malformed LLM
response to an actual access grant).

## cloud-itonami consumption

See `90-docs/adr/2607062020-kotoba-lang-shoko-archive-scaffold.md`. Add
`io.github.kotoba-lang/shoko {:local/root "../../kotoba-lang/shoko"}` to
`deps.edn` for in-process use (already pre-registered there). A
`cloud_itonami.workspace` projection layer translating a share request into
a `:file/share` request, and its human approval riding on
`cloud_itonami.approval`, is tracked as a separate follow-up — out of scope
here.

## Status

Full implementation (upgraded from the initial scaffold-only cut). Store is
`:db-api` driven — `MemStore ≡ DatomicStore(langchain.db) ≡
kotoba-store(kotobase.net)` on the same contract. CACAO self-issuance is
offline-verified. `ArchiveTarget` has a real, opt-in, **live-verified**
backend (`r2-archiveport`, Cloudflare R2 via SigV4 — see above); mock stays
the default. A real Distributor (email/Slack/etc) is still not shipped here
at all (inject your own) — same known state kekkai/teian/koyomi ship in.

## References

- `90-docs/adr/2607062020-kotoba-lang-shoko-archive-scaffold.md` — this
  repo's design ADR (Context/Decision/Consequences full text)
- [`kotoba-lang/drive`](https://github.com/kotoba-lang/drive) — the
  file/folder EDN model shoko holds verbatim and governs access to
- [`kotoba-lang/kekkai`](https://github.com/kotoba-lang/kekkai) — the
  deny-by-default ACL shape (`kekkai.acl`) shoko's `share-requires-acl`
  mirrors
- [`kotoba-lang/teian`](https://github.com/kotoba-lang/teian) /
  [`kotoba-lang/koyomi`](https://github.com/kotoba-lang/koyomi) — the
  draft/publish (propose→draft-only, always-human actuation) shape shoko
  follows, and the source of the confirmed-bug lessons (subject-exists
  independence, TOCTOU-safe commit, publish-time recheck) folded into this
  implementation from the start
