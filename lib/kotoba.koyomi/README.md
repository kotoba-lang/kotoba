# koyomi

暦 — a **schedule-sharing control plane**: a schedule-LLM ⊣
ComplianceGovernor StateGraph that drafts calendar events (title/agenda over
a mechanically-registered time/attendee slot) and shares them with
attendees, but never invites anyone itself. The actor is **propose → draft
only**: a draft commits as data (a *casual commit* — phase-gated
auto-approval is fine, it's just proposed content sitting there for review);
actually sharing an event (sending invites) is **always a human call**,
regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`kekkai`](../kekkai) (coord-LLM ⊣ TailnetGovernor) and
[`tayori`](../tayori) (reply-LLM ⊣ ComplianceGovernor). Here it is
**schedule-LLM ⊣ ComplianceGovernor**. The event content itself is
[`kotoba-lang/calendar`](../calendar)'s `calendar.model` EDN — a pure,
portable event model with ZERO ICS-export/consent/governor concept — held
verbatim; koyomi owns the ICS generation and the compliance layer on top.

> Charter: **(G1)** propose → draft only, no direct actuation — the actor
> writes proposed event content, a human turns it into an outbound invite;
> **(G2)** sharing an event is **always a human call** (high-stakes),
> independent of rollout phase; **(G3)** kotoba-native — activity/contact/
> event facts are durable EAVT ground facts, drafts are transient until
> committed; **(G4)** koyomi builds the ICS itself — `calendar.model` has no
> export concept, so `koyomi.scheduleport` owns the RFC 5545 string and
> hands it to an injected Distributor for actual invite delivery.

## The core contract

```
activity/contact/event facts
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌─────────────┐  proposal: draft /   ┌────────────────────┐
   │ schedule-LLM │  share               │ ComplianceGovernor │  (independent system)
   │ (sealed)     │ ───────────────────▶ │  no-actuation ·     │
   └─────────────┘  + cited facts        │  consent ·          │
                                         │  tenant-isolation    │
                                         └─────────┬──────────┘
                            commit ◀────────────────┼──────────▶ hold (consent-
                     (draft: casual            escalate       blocked / tenant-
                      commit, auto ok              │           mismatch / claims-
                      at phase≥2;                  ▼           already-shared;
                      share: ALWAYS            人間 承認       un-overridable)
                      here) ─────────▶     (share は phase に
                                            関わらず常に人間)
```

**The actor never shares/invites the ComplianceGovernor would reject, and
schedule-LLM never actuates directly.** HARD invariants force **hold** (a
human cannot approve past a proposal that claims to have already shared, a
share to a consent-blocked attendee, or an event whose tenant doesn't match
the activity driving it); a clean share still routes to a human. A
double-booking (an existing event overlapping the same attendee/resource,
via `calendar.model/overlaps?`) is a SOFT escalate, not a hold — concurrent
events can be entirely legitimate, but a human should still take a look.

## Run

```bash
kbb -M:dev:run     # drive: draft → share through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register an event from an activity's due-at (observe → facts) → draft
a clean board-meeting event (phase 3 → clean → auto-commits, no interrupt) →
share it (**always** human sign-off, even though clean) → draft an event
with a consent-blocked attendee → share it (**HARD HOLD**, un-overridable) →
draft an event that double-books an existing one on a shared attendee
(**SOFT escalate**, a human can still approve it) → phase-0 disables
drafting entirely → prints the schedule-sharing audit ledger → swaps to
`DatomicStore` with identical results.

## Layout

| File | Role |
|---|---|
| `src/koyomi/model.cljk` | unified `draft`/`contact` shapes (the koyomi analog of tayori's contact model, applied to calendar attendees) |
| `src/koyomi/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **schedule-sharing audit ledger** |
| `src/koyomi/coordllm.cljk` | **schedule-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); draft/share proposals |
| `src/koyomi/governor.cljk` | **ComplianceGovernor** — no-actuation · consent-required · tenant-isolation · double-booking (soft) · high-stakes |
| `src/koyomi/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-draft → supervised (sharing always human) |
| `src/koyomi/operation.cljk` | **ScheduleActor** — langgraph StateGraph; ingest vs assess flows |
| `src/koyomi/scheduleport.cljk` | **ScheduleTarget** port (`fetch-event`/`propose-revision!`/`share!`) + koyomi-owned RFC 5545 ICS builder + `mock-scheduleport` |
| `src/koyomi/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/koyomi/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/koyomi/distribute.cljk` | **REAL Resend Distributor** — `resend-scheduleport`, an opt-in `ScheduleTarget` that actually emails the ICS via `kotoba-lang/mailer` (JVM `java.net.http`, live-verified — see below) |
| `src/koyomi/query.cljk` | pure status lookups (`draft-status`/`shared?`) for callers that don't want to run the actor |
| `src/koyomi/cli.cljk` | minimal JVM entrypoint for a status read against an EDN-seeded MemStore |
| `src/koyomi/sim.cljk` | demo driver |
| `test/koyomi/*_test.clj` | propose-only contract · store parity (Mem≡Datomic) · CACAO · Resend/Slack request-building (stubbed transport) |

## ScheduleTarget → real backend (injection)

`calendar.model` has zero ICS-export or sharing concept (verified — grepping
`ics|ical|share|publish` across it is a zero hit), so `koyomi.scheduleport`
owns building the RFC 5545 string itself; `share!` hands that ICS to an
injected **Distributor** for actual delivery, same injection shape as
`tayori.channel`/`tayori.docport`. `mock-scheduleport` is the runnable,
deterministic DEFAULT — it records what WOULD have gone out
(`{:event-id :ics :attendees}`) into an atom and hands that same map to an
injected `distributor` fn (a no-op by default; this is the slot
`slack-scheduleport` below plugs into for a channel notification).

`koyomi.distribute/resend-scheduleport` is the opt-in REAL `ScheduleTarget` —
not a `distributor` fn plugged into `mock-scheduleport`, but a full drop-in
replacement swapped in via `koyomi.operation/build`'s `:scheduleport` opt.
It builds the Resend request via `kotoba-lang/mailer` (`mailer.core/request`,
same layering `cloud-itonami.mail` rides on), attaches the already-built ICS
as a `text/calendar` `invite.ics` attachment, POSTs it with a real
`java.net.http` client, and records the returned Resend message id onto the
given `koyomi.store/Store`'s append-only ledger (`:tool (str "resend:" id)`,
the koyomi analog of `cloud_itonami.mail`'s `:itonami.effect/tool` pattern).
`:calendar/attendees` entries are used directly as recipient email addresses
(the same assumption `ics-string`'s `ATTENDEE:mailto:` lines already make) —
`koyomi.store/demo-data`'s placeholder ids (`"att-alice"` etc.) are NOT real
addresses and a real share against them fails closed (invalid recipient).

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as kekkai/tayori)
(require '[koyomi.kotoba :as k] '[koyomi.cacao :as cacao] '[json.data-json :as json])
(def me    (cacao/load-or-create-identity! ".koyomi/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real schedule-LLM + the real Resend ScheduleTarget
(require '[langchain.model :as model] '[koyomi.operation :as op]
         '[koyomi.coordllm :as c] '[koyomi.distribute :as distribute])
(op/build store
  {:advisor (c/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :scheduleport (distribute/resend-scheduleport store "ops@mail.itonami.cloud")})
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**ComplianceGovernor always hold/escalates** it (no path from a malformed
LLM response to an actual share).

## Slack Distributor (owner setup required)

`koyomi.scheduleport/slack-scheduleport` is a real Slack `chat.postMessage`
Distributor — an opt-in `distributor` for `mock-scheduleport`'s
`distributor` slot, alongside (not replacing) the default no-op. It is a
channel *notification* only, a distinct concern from `koyomi.distribute/
resend-scheduleport` above (a full `ScheduleTarget` that actually delivers
the ICS invite) — the two can be used together (Resend for the real invite,
Slack for a heads-up) or independently. It posts a short text notification
(event title, recovered from the ICS SUMMARY line, + attendee count) to a
channel; it does **not** attach the
.ics invite itself — that would need Slack's separate `files.upload`
multipart endpoint, out of scope here (a real, if plain, notification
beats a half-implemented file upload — and attendees still need the
actual .ics via a real invite channel, which a Slack heads-up is not a
substitute for). **Nothing in this repo makes a live Slack API call** —
there is no Slack app/token yet; that's the below, owner-side.

Before this is usable, the owner needs to:

1. Go to <https://api.slack.com/apps> → **Create New App** → **From
   scratch**. Name it something like `kotoba-lang-koyomi-notifier` (one app
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
4. Invite the bot to whichever channel should receive schedule-share
   notifications (`/invite @your-bot-name` in that channel) — or skip this
   if you added `chat:write.public` above.
5. Inject the token + channel id into the constructor:
   ```clojure
   (require '[koyomi.scheduleport :as sp])
   (sp/mock-scheduleport (atom {})
     (sp/slack-scheduleport {:token "xoxb-..." :channel "C0123456"}))
   ```
   In production, resolve the token the way this ecosystem resolves other
   provider credentials — env var first, falling back to a secrets store
   (see `cloud-itonami/scripts/mail-creds.bb` for the pattern this should
   eventually follow once a real Slack app exists; there is no vault entry
   for it yet, so don't invent one).

## cloud-itonami consumption

See `90-docs/adr/2607062010-kotoba-lang-koyomi-schedule-actor.md`. Add
`io.github.kotoba-lang/koyomi {:local/root "../../kotoba-lang/koyomi"}` to
`deps.edn` for in-process use. `cloud_itonami.workspace`'s projection layer
translates an `:itonami.effect/kind :calendar/schedule-event` into a koyomi
`:event/draft` request, and `:event/share`'s human approval rides on
cloud-itonami's existing approval flow (ADR-0005) — that wiring is tracked
as a separate follow-up, out of scope here.

## Status

Scaffold + runnable. Store is `:db-api` driven — `MemStore ≡
DatomicStore(langchain.db) ≡ kotoba-store(kotobase.net)` on the same
contract. CACAO self-issuance is offline-verified. `koyomi.distribute/
resend-scheduleport` (the real email `ScheduleTarget`) is **live-verified** —
a real invite send against Resend returned a real message id and the ledger
fact recording it; `koyomi.scheduleport/slack-scheduleport` is a real,
request-shape-tested (never live-called) opt-in Distributor scaffold — see
'Slack Distributor (owner setup required)' above for what's still needed
before it's usable. `mock-scheduleport` remains the runnable, deterministic
default.
