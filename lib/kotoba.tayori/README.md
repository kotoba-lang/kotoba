# tayori

便り — a **correspondence-drafting control plane**: a reply-LLM ⊣
ComplianceGovernor StateGraph that drafts replies across Email/Slack/WhatsApp
threads and revisions for git-backed documents, but never sends or publishes
anything itself. The actor is **propose → draft/revision only**: a draft or a
document revision commits as data (a *casual commit* — phase-gated
auto-approval is fine, it's just proposed text sitting there for review);
actually sending a message or publishing a document is a *PR merge* — it is
**always a human call**, regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`kekkai`](../kekkai) (coord-LLM ⊣ TailnetGovernor) and
`gijiroku` (scribe-LLM ⊣ PrivacyGovernor). Here it is
**reply-LLM ⊣ ComplianceGovernor**.

> Charter: **(G1)** propose → draft/revision only, no direct actuation — the
> actor writes proposed text, a human turns it into an outbound effect;
> **(G2)** sending a reply and publishing a document are **always a human
> call** (high-stakes), independent of rollout phase; **(G3)** kotoba-native —
> thread/message/contact/document facts are durable EAVT ground facts,
> drafts/revisions are transient until committed; **(G4)** documents get a
> *literal* PR — `propose-revision!` is a real git branch+commit, `publish!`
> is a real merge, mirroring this superproject's own "GitHub API single-entry
> commit" pattern for advancing `manifest/west.yml` pins.

## The core contract

```
thread/message/contact/document facts
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌───────────┐  proposal: draft /  ┌────────────────────┐
   │ reply-LLM  │  revise / send /    │ ComplianceGovernor │  (independent system)
   │ (sealed)   │  publish            │  no-actuation ·     │
   └───────────┘ ──────────────────▶ │  redaction ·        │
                 + cited facts        │  consent · tenant   │
                                      └─────────┬──────────┘
                            commit ◀────────────┼──────────▶ hold (consent-
                     (draft/revision:      escalate      blocked / missing-
                      casual commit,           │          redaction / tenant-
                      auto ok at phase≥2;      ▼          mismatch / claims-
                      send/publish:      人間 承認         already-actuated;
                      ALWAYS here) ─▶  (send/publish は    un-overridable)
                                        phase に関わらず
                                        常に人間)
```

**The actor never sends a message or publishes a document the
ComplianceGovernor would reject, and reply-LLM never actuates directly.**
HARD invariants force **hold** (a human cannot approve past a consent-blocked
recipient, a missing redaction on a protected-tag cite, a proposal that
claims to have already sent/published, or a publish target that doesn't match
the document's own registered path); a clean send/publish still routes to a
human.

## Run

```bash
kbb -M:dev:run     # drive: draft → send / revise → publish through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register a contact/thread/message (observe → facts) → draft a reply to
a known contact (phase 3 → clean → auto-commits, no interrupt) → send it
(**always** human sign-off, even though clean) → draft a reply to a
consent-blocked contact → send it (**HARD HOLD**, un-overridable) → revise a
git-backed memo (auto-commits → a real branch+commit is proposed) → publish it
(always human sign-off → a real merge) → phase-0 disables drafting entirely →
prints the correspondence audit ledger → swaps to `DatomicStore` with
identical results.

## Layout

| File | Role |
|---|---|
| `src/tayori/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **correspondence audit ledger** |
| `src/tayori/policy.cljk` | pure checks (redaction requirement · consent-blocked · target-mismatch) — shared by governor & reply-LLM, no I/O |
| `src/tayori/replyllm.cljk` | **reply-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); draft/revise/send/publish proposals |
| `src/tayori/governor.cljk` | **ComplianceGovernor** — no-actuation · redaction-required · consent-required · tenant-isolation · high-stakes |
| `src/tayori/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-draft → supervised (send/publish always human) |
| `src/tayori/operation.cljk` | **CorrespondenceActor** — langgraph StateGraph; ingest vs assess flows |
| `src/tayori/channel.cljk` | **Channel** port (`fetch-thread`/`list-new-messages`/`send-reply!`) + `mock-channel` |
| `src/tayori/channel/{email,slack,whatsapp}.cljc` | real Channel implementations (Gmail API / Slack Web API / WhatsApp Business Cloud API); I/O injected, live untested |
| `src/tayori/docport.cljk` | **DocTarget** port (`fetch-doc`/`propose-revision!`/`publish!`) + `mock-doctarget` |
| `src/tayori/docport/git.cljk` | real DocTarget — GitHub API, a literal branch+commit+merge PR |
| `src/tayori/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/tayori/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/tayori/query.cljk` | pure status lookups (`draft-status`/`sent?`/`revision-status`/`published?`) for callers that don't want to run the actor |
| `src/tayori/sim.cljk` | demo driver |
| `test/tayori/*_test.clj` | propose-only contract · store parity (Mem≡Datomic) · CACAO — **28 tests / 99 assertions** |

## Channel / DocTarget → real backend (injection)

Every real port (`tayori.channel.email/slack/whatsapp`, `tayori.docport.git`)
takes injected I/O (`:http-fn` `:json-write` `:json-read` `:creds`), same
contract as `tayori.kotoba`/kekkai's ports — this keeps `src/` dependency-free
and lets a JVM host supply `tayori.kotoba/jvm-http-fn`, a cljs host something
else. **Live bindings are untested** (they need OAuth apps / bot tokens / a
GitHub token with `contents`+`pull_requests` scope) — `mock-channel` and
`mock-doctarget` are the runnable, deterministic defaults.

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as kekkai/gijiroku)
(require '[tayori.kotoba :as k] '[tayori.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".tayori/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real reply-LLM + real channels/docport
(require '[langchain.model :as model] '[tayori.operation :as op]
         '[tayori.replyllm :as r] '[tayori.channel.email :as email]
         '[tayori.docport.git :as gitdoc])
(op/build store
  {:advisor (r/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :channel (email/email-channel {:http-fn k/jvm-http-fn :json-write json/write-str
                                  :json-read #(json/read-str % :key-fn keyword)
                                  :creds {:token "…"} :raw-fn my-mime-encoder})
   :docport (gitdoc/git-doctarget {:http-fn k/jvm-http-fn :json-write json/write-str
                                   :json-read #(json/read-str % :key-fn keyword)
                                   :creds {:token "…" :owner "…" :repo "…"} :encode-fn my-base64-fn})})
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**ComplianceGovernor always hold/escalates** it (no path from a malformed
LLM response to an actual send/publish).

## local-manimani / cloud-manimani consumption

See ADR-2607061500. Add `io.github.kotoba-lang/tayori {:local/root
"../../kotoba-lang/tayori"}` to `deps.edn` for in-process use, or read via
`tayori.kotoba/kotoba-store` against a kotobase.net graph. Wiring
local-manimani's `reply_llm` triage policy onto this actor (Decision Ledger
schema extension) is tracked as a separate follow-up — out of scope here.

## Status

Scaffold + runnable. **28 tests / 99 assertions / 0 failures**, lint clean.
Store is `:db-api` driven — `MemStore ≡ DatomicStore(langchain.db) ≡
kotoba-store(kotobase.net)` on the same contract. CACAO self-issuance is
offline-verified. Real Channel/DocTarget bindings (Gmail/Slack/WhatsApp/
GitHub) are structurally complete but **live-untested** — same known state
kekkai/gijiroku ship in.
