# ichiran

一覧 — a **tally/rollup-sheet generation control plane**: a tally-LLM ⊣
TallyGovernor StateGraph that drafts aggregate report workbooks
(`kotoba-lang/sheets` EDN — workbook/tab/cell/formula/named-range/chart) from
itonami ledger facts, but never distributes anything itself. The actor is
**propose → draft only**: a draft commits as data (a *casual commit* —
phase-gated auto-approval is fine, it's just a proposed tally workbook sitting
there for review); actually publishing a tally (`:tally/publish`) is a *PR
merge* — it is **always a human call**, regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`teian`](../teian) (deck-LLM ⊣ BriefingGovernor,
briefing-drafting) and [`koyomi`](../koyomi) (schedule-LLM ⊣
ComplianceGovernor, schedule-sharing). Here it is **tally-LLM ⊣
TallyGovernor**.

> Charter: **(G1)** propose → draft only, no direct actuation — the actor
> writes proposed workbook content, a human turns it into an outbound
> publish; **(G2)** publishing a tally is **always a human call**
> (high-stakes), independent of rollout phase; **(G3)** kotoba-native —
> artifact/draft facts are durable EAVT ground facts, drafts are transient
> until committed; **(G4)** ichiran holds `kotoba-lang/sheets` EDN verbatim as
> draft content — it does not reimplement the workbook/tab/cell/formula/chart
> data model.

## The core contract

```
artifact facts (the itonami activity a tally is drafted for)
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌───────────┐  proposal: draft /  ┌─────────────────────┐
   │ tally-LLM  │  publish            │  TallyGovernor       │  (independent system)
   │ (sealed)   │ ──────────────────▶ │  missing-subject ·   │
   └───────────┘  + cited facts       │  no-actuation ·      │
                                      │  redaction · tenant  │
                                      └──────────┬───────────┘
                            commit ◀─────────────┼───────────▶ hold (missing-
                     (draft: casual commit,   escalate           subject /
                      auto ok at phase≥2;         │              redaction /
                      publish: ALWAYS here) ─▶ 人間 承認         tenant-mismatch;
                                            (publishは常に人間)   un-overridable)
```

**The actor never publishes a tally workbook the TallyGovernor would reject,
and tally-LLM never actuates directly.** HARD invariants force **hold** (a
human cannot approve past a draft for an unregistered activity, a missing
redaction on a sensitive cite, or a workbook declared for the wrong tenant);
a clean publish still routes to a human.

## Run

```bash
kbb -M:dev:run     # drive: draft → publish through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register an artifact (observe → ground fact) → draft a Q3 財務集計
tally for a known, clean-tenant artifact (phase 3 → clean → auto-commits, no
interrupt) → publish it (**always** human sign-off, even though clean) →
phase-0 disables drafting entirely → prints the tally-generation audit ledger
→ swaps to `DatomicStore` with identical results.

## Layout

| File | Role |
|---|---|
| `src/ichiran/model.cljk` | pure **draft**/**artifact** data shapes — `content` is verbatim `kotoba-lang/sheets` EDN, never ichiran's own representation |
| `src/ichiran/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **tally-generation audit ledger** |
| `src/ichiran/policy.cljk` | pure checks (sensitive-cite redaction requirement · tenant mismatch) — shared by governor & tally-LLM, no I/O |
| `src/ichiran/coordllm.cljk` | **tally-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); draft/publish proposals |
| `src/ichiran/governor.cljk` | **TallyGovernor** — missing-subject (independent, unconditional) · no-actuation · redaction-required · tenant-isolation · high-stakes |
| `src/ichiran/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-draft → supervised (publish always human) |
| `src/ichiran/operation.cljk` | **TallyActor** — langgraph StateGraph; ingest vs assess flows |
| `src/ichiran/tallyport.cljk` | **TallyTarget** port (`fetch-workbook`/`propose-revision!`/`publish!`) + `mock-tallyport` (best-effort `sheets.wire` Transit export + injected Distributor fn) |
| `src/ichiran/resend.cljk` | **opt-in REAL Distributor** — `resend-tallyport` actually emails the governed workbook via Resend (`kotoba-lang/mailer`), same provider `cloud-itonami.mail` uses. `mock-tallyport` stays the default. |
| `src/ichiran/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/ichiran/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/ichiran/query.cljk` | pure status lookups (`draft-status`/`published?`) for callers that don't want to run the actor |
| `src/ichiran/sim.cljk` | demo driver |
| `src/ichiran/cli.cljk` | minimal JVM status-check entrypoint |
| `test/ichiran/*_test.clj` | propose-only contract · store parity (Mem≡Datomic) · CACAO |

## TallyTarget → real backend (injection)

`ichiran.tallyport/mock-tallyport` is the runnable, deterministic default —
no network/creds. `publish!` exports the workbook via `kotoba-lang/sheets`'s
`sheets.wire/workbook-envelope` (Kotoba Transit JSON) — best-effort; any
encoding failure degrades to no envelope bytes rather than throwing — and
always calls an injected `:distribute-fn` once per delivery. A live
BI-tool Distributor is still **not shipped here** — inject your own (a
Slack scaffold exists, see 'Slack Distributor (owner setup required)'
below, and a live-tested Resend email Distributor is shipped, see next).

A REAL email Distributor for Resend IS shipped, opt-in only:
`ichiran.resend/resend-tallyport` (`src/ichiran/resend.cljk`, JVM-only, same
`java.net.http` transport shape as `cloud-itonami.mail`). `publish!` emails
the recipient (`target`) a human-readable text summary of the workbook's
tabs/cells, with the `sheets.wire` Transit JSON envelope attached
(`kotoba-lang/sheets` has no CSV/xlsx export); on success the Resend message
id lands on the artifact's `:draft` record as `:tool "resend:<id>"` (the
ichiran analog of `cloud_itonami.mail`'s `:itonami.effect/tool` pattern)
plus a `:delivered` ledger fact. `mock-tallyport` stays the actor's default
either way — this is only reached if a caller explicitly constructs and
injects it:

```clojure
(require '[ichiran.resend :as resend])
(op/build store {:tallyport (resend/resend-tallyport store {:from "ops@example.com"})})
```

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as kekkai/teian/koyomi)
(require '[ichiran.kotoba :as k] '[ichiran.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".ichiran/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real tally-LLM + a real Distributor
(require '[langchain.model :as model] '[ichiran.operation :as op]
         '[ichiran.coordllm :as coordllm] '[ichiran.tallyport :as tallyport])
(op/build store
  {:advisor (coordllm/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :tallyport (tallyport/mock-tallyport (atom {}) my-real-distribute-fn)})
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**TallyGovernor always hold/escalates** it (no path from a malformed LLM
response to an actual publish).

## Slack Distributor (owner setup required)

`ichiran.tallyport/slack-tallyport` is a real Slack `chat.postMessage`
Distributor — an opt-in `distribute-fn` for `mock-tallyport`, alongside
(not replacing) the default no-op and a Resend-email Distributor. It
posts a short text notification (report title + a note a tally was
published) to a channel; it does **not** attach the actual Transit
envelope bytes — that would need Slack's separate `files.upload`
multipart endpoint, out of scope here (a real, if plain, notification
beats a half-implemented file upload). **Nothing in this repo makes a
live Slack API call** — there is no Slack app/token yet; that's the below,
owner-side.

Before this is usable, the owner needs to:

1. Go to <https://api.slack.com/apps> → **Create New App** → **From
   scratch**. Name it something like `kotoba-lang-ichiran-notifier` (one
   app per actor keeps scopes/audit narrow; a single shared app across
   teian/koyomi/ichiran is also fine if you'd rather manage one integration
   — either way, note the choice in the app's description for whoever
   rotates the token later).
2. Under **OAuth & Permissions → Bot Token Scopes**, add `chat:write`
   (minimum required for `chat.postMessage`). Add `chat:write.public` too
   if you want the bot to post into channels it hasn't been explicitly
   invited to.
3. **Install to Workspace**, then copy the **Bot User OAuth Token**
   (`xoxb-...`).
4. Invite the bot to whichever channel should receive tally-publish
   notifications (`/invite @your-bot-name` in that channel) — or skip this
   if you added `chat:write.public` above.
5. Inject the token + channel id into the constructor:
   ```clojure
   (require '[ichiran.tallyport :as tallyport])
   (tallyport/mock-tallyport (atom {})
     (tallyport/slack-tallyport {:token "xoxb-..." :channel "C0123456"}))
   ```
   In production, resolve the token the way this ecosystem resolves other
   provider credentials — env var first, falling back to a secrets store
   (see `cloud-itonami/scripts/mail-creds.bb` for the pattern this should
   eventually follow once a real Slack app exists; there is no vault entry
   for it yet, so don't invent one).

## cloud-itonami consumption

See `90-docs/adr/2607062030-kotoba-lang-ichiran-tally-scaffold.md`. Add
`io.github.kotoba-lang/ichiran {:local/root "../../kotoba-lang/ichiran"}` to
`deps.edn` for in-process use, or read via `ichiran.kotoba/kotoba-store`
against a kotobase.net graph. A `cloud_itonami.workspace` projection layer
translating an itonami-ledger rollup request into a `:tally/draft` request,
and the `:tally/publish` human approval riding on `cloud_itonami.approval`
(ADR-0005), is tracked as a separate follow-up — out of scope here.

## Status

Runnable + fully tested. Store is `:db-api` driven — `MemStore ≡
DatomicStore(langchain.db) ≡ kotoba-store(kotobase.net)` on the same
contract, with a per-id-upsert `seed!` from the start (never a wholesale
`:artifacts` replace). CACAO self-issuance is offline-verified.
`TallyTarget`'s Transit export path is structurally complete. The Resend
email Distributor (`ichiran.resend/resend-tallyport`) has been **live-tested
end-to-end** (a real Resend message id came back for a real send).
`ichiran.tallyport/slack-tallyport` is a real, request-shape-tested (never
live-called) opt-in Distributor scaffold — see 'Slack Distributor (owner
setup required)' above for what's still needed before it's usable. Any
other Distributor (BI-tool/etc) is not shipped here at all (inject your
own).
