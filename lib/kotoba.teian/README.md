# teian

提案 — a **briefing-drafting control plane**: a deck-LLM ⊣ BriefingGovernor
StateGraph that drafts decks/docs/sheets for corporate briefings (sales
reviews, board meetings) but never delivers anything itself. The actor is
**propose → draft only**: a draft commits as data (a *casual commit* —
phase-gated auto-approval is fine, it's just a proposed deck/doc/sheet
sitting there for review); actually delivering a briefing (`:deck/publish`)
is a *PR merge* — it is **always a human call**, regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`kekkai`](../kekkai) (coord-LLM ⊣ TailnetGovernor) and
[`tayori`](../tayori) (reply-LLM ⊣ ComplianceGovernor). Here it is
**deck-LLM ⊣ BriefingGovernor**.

> Charter: **(G1)** propose → draft only, no direct actuation — the actor
> writes proposed deck/doc/sheet content, a human turns it into an outbound
> delivery; **(G2)** delivering a briefing is **always a human call**
> (high-stakes), independent of rollout phase; **(G3)** kotoba-native —
> artifact/draft facts are durable EAVT ground facts, drafts are transient
> until committed; **(G4)** teian holds `kotoba-lang/slides` EDN verbatim as
> draft content — it does not reimplement the deck/doc/sheet data model.

## The core contract

```
artifact facts (the itonami activity a briefing is drafted for)
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌───────────┐  proposal: draft /  ┌─────────────────────┐
   │ deck-LLM   │  publish            │  BriefingGovernor    │  (independent system)
   │ (sealed)   │ ──────────────────▶ │  no-actuation ·      │
   └───────────┘  + cited facts       │  redaction · tenant  │
                                      └──────────┬───────────┘
                            commit ◀─────────────┼───────────▶ hold (missing-
                     (draft: casual commit,   escalate           redaction /
                      auto ok at phase≥2;         │              tenant-mismatch /
                      publish: ALWAYS here) ─▶ 人間 承認         claims-already-
                                            (publishは常に人間)   published; un-
                                                                  overridable)
```

**The actor never delivers a deck/doc/sheet the BriefingGovernor would
reject, and deck-LLM never actuates directly.** HARD invariants force
**hold** (a human cannot approve past a missing redaction on a sensitive
cite, a draft declared for the wrong tenant, or a proposal that claims to
have already published); a clean publish still routes to a human.

## Run

```bash
kbb -M:dev:run     # drive: draft → publish through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register an artifact (observe → ground fact) → draft a briefing for a
known, clean-tenant artifact (phase 3 → clean → auto-commits, no interrupt)
→ publish it (**always** human sign-off, even though clean) → phase-0
disables drafting entirely → prints the briefing audit ledger → swaps to
`DatomicStore` with identical results.

## Layout

| File | Role |
|---|---|
| `src/teian/model.cljk` | pure **draft**/**artifact** data shapes — `content` is verbatim `kotoba-lang/slides` EDN, never teian's own representation |
| `src/teian/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **briefing audit ledger** |
| `src/teian/policy.cljk` | pure checks (sensitive-cite redaction requirement · tenant mismatch) — shared by governor & deck-LLM, no I/O |
| `src/teian/deckllm.cljk` | **deck-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); draft/publish proposals |
| `src/teian/governor.cljk` | **BriefingGovernor** — no-actuation · redaction-required · tenant-isolation · high-stakes |
| `src/teian/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-draft → supervised (publish always human) |
| `src/teian/operation.cljk` | **BriefingActor** — langgraph StateGraph; ingest vs assess flows |
| `src/teian/deckport.cljk` | **DeckTarget** port (`fetch-deck`/`propose-revision!`/`publish!`) + `mock-deckport` (best-effort `slides.office` pptx export + injected Distributor fn) |
| `src/teian/distribute.cljk` | REAL email **Distributor** — `resend-distribute-fn` (Resend via `kotoba-lang/mailer` + `java.net.http`, JVM-only, opt-in — mock-deckport stays the default) |
| `src/teian/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/teian/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/teian/query.cljk` | pure status lookups (`draft-status`/`published?`) for callers that don't want to run the actor |
| `src/teian/sim.cljk` | demo driver |
| `src/teian/cli.cljk` | minimal JVM status-check entrypoint |
| `test/teian/*_test.clj` | propose-only contract · store parity (Mem≡Datomic) · CACAO |

## DeckTarget → real backend (injection)

`teian.deckport/mock-deckport` is the runnable, deterministic default — no
network/creds. `publish!` optionally exports real pptx bytes via
`kotoba-lang/slides`'s `slides.office` when the draft's content is a
`:slides/deck` (best-effort, `requiring-resolve`d lazily — a `:doc`/`:sheet`
kind or any export failure degrades to no pptx bytes rather than throwing),
and always calls an injected `:distribute-fn` once per delivery. Two real
Distributors ship in this repo — `teian.distribute/resend-distribute-fn`
(email, live/usable today) and `teian.deckport/slack-deckport` (Slack,
request-shape-tested, needs owner app setup — see 'Slack Distributor'
below) — both opt-in, neither replaces `mock-deckport` as the default; any
other Distributor is on you to inject.

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as kekkai/tayori)
(require '[teian.kotoba :as k] '[teian.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".teian/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real deck-LLM + a real Distributor
(require '[langchain.model :as model] '[teian.operation :as op]
         '[teian.deckllm :as deckllm] '[teian.deckport :as deckport])
(op/build store
  {:advisor (deckllm/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :deckport (deckport/mock-deckport (atom {}) my-real-distribute-fn)})

;; the REAL Distributor this repo ships: Resend email (opt-in — the :deckport
;; passed to op/build's opts is what actually wires it in; leaving :deckport
;; unset keeps mock-deckport, i.e. no live send, ever)
(require '[teian.distribute :as distribute])
(op/build store
  {:deckport (deckport/mock-deckport
              (atom {})
              (distribute/resend-distribute-fn {:from "ops@your-verified-sender.example"}))})
;; RESEND_API_KEY must be set (env); :from must be a Resend-verified sender.
;; publish! best-effort attaches a real pptx (kotoba-lang/slides's
;; slides.office) when the draft's content is a :slides/deck; the returned
;; {:delivery/tool "resend:<id>" ...} is threaded back through publish! and
;; recorded on both the draft record and the :committed ledger fact's :tool.
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**BriefingGovernor always hold/escalates** it (no path from a malformed LLM
response to an actual delivery).

## Slack Distributor (owner setup required)

`teian.deckport/slack-deckport` is a real Slack `chat.postMessage`
Distributor — an opt-in `distribute-fn` for `mock-deckport`, alongside
(not replacing) the default no-op and a Resend-email Distributor. It
posts a short text notification (deck title + a note a deck was
published) to a channel; it does **not** attach the actual pptx bytes —
that would need Slack's separate `files.upload` multipart endpoint, out
of scope here (a real, if plain, notification beats a half-implemented
file upload). **Nothing in this repo makes a live Slack API call** — there
is no Slack app/token yet; that's the below, owner-side.

Before this is usable, the owner needs to:

1. Go to <https://api.slack.com/apps> → **Create New App** → **From
   scratch**. Name it something like `kotoba-lang-teian-notifier` (one app
   per actor keeps scopes/audit narrow; a single shared app across
   teian/koyomi/ichiran is also fine if you'd rather manage one integration
   — either way, note the choice in the app's description for whoever
   rotates the token later).
2. Under **OAuth & Permissions → Bot Token Scopes**, add `chat:write`
   (minimum required for `chat.postMessage`). Add `chat:write.public` too
   if you want the bot to post into channels it hasn't been explicitly
   invited to.
3. **Install to Workspace**, then copy the **Bot User OAuth Token**
   (`xoxb-...`).
4. Invite the bot to whichever channel should receive deck-publish
   notifications (`/invite @your-bot-name` in that channel) — or skip this
   if you added `chat:write.public` above.
5. Inject the token + channel id into the constructor:
   ```clojure
   (require '[teian.deckport :as deckport])
   (deckport/mock-deckport (atom {})
     (deckport/slack-deckport {:token "xoxb-..." :channel "C0123456"}))
   ```
   In production, resolve the token the way this ecosystem resolves other
   provider credentials — env var first, falling back to a secrets store
   (see `cloud-itonami/scripts/mail-creds.bb` for the pattern this should
   eventually follow once a real Slack app exists; there is no vault entry
   for it yet, so don't invent one).

## cloud-itonami consumption

See `90-docs/adr/2607062000-kotoba-lang-teian-briefing-actor.md`. Add
`io.github.kotoba-lang/teian {:local/root "../../kotoba-lang/teian"}` to
`deps.edn` for in-process use, or read via `teian.kotoba/kotoba-store`
against a kotobase.net graph. A `cloud_itonami.workspace` projection layer
translating `:itonami.effect/kind :document/generate-deck` into a
`:deck/draft` request, and the `:deck/publish` human approval riding on
`cloud_itonami.approval` (ADR-0005), is tracked as a separate follow-up —
out of scope here.

## Status

Scaffold + runnable. Store is `:db-api` driven — `MemStore ≡
DatomicStore(langchain.db) ≡ kotoba-store(kotobase.net)` on the same
contract. CACAO self-issuance is offline-verified. `DeckTarget`'s pptx
export path (`kotoba-lang/slides`'s `slides.office`) and
`teian.distribute/resend-distribute-fn` (Resend email Distributor) are
**live-verified** — a real deck was exported to pptx, attached, and
delivered via Resend end to end, not just unit-tested against a stub.
`teian.deckport/slack-deckport` is a real, request-shape-tested (never
live-called) opt-in Distributor scaffold — see 'Slack Distributor (owner
setup required)' above for what's still needed before it's usable. Any
other Distributor (BI-tool/etc) is not shipped here at all (inject your
own).
