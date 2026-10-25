# denrei

伝令 — a **channel-posting control plane** for the
[`kaisha`](../kaisha) communication space (Slack/Teams 相当): a post-LLM ⊣
MembershipGovernor StateGraph that drafts channel messages, but never posts
into the space itself. The actor is **propose → draft only**: a draft commits
as data (a *casual commit* — phase-gated auto-approval is fine, it's just
proposed content sitting there for review); actually posting a message into
the space is **always a human call**, regardless of phase.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`tayori`](../tayori) (reply-LLM ⊣ ComplianceGovernor,
external Email/Slack/WhatsApp) and [`koyomi`](../koyomi) (schedule-LLM ⊣
ComplianceGovernor, calendar sharing). Here it is **post-LLM ⊣
MembershipGovernor**, over the internal space. The message content itself is
[`kotoba-lang/kaisha`](../kaisha)'s `kaisha.model` EDN — a pure, portable
space/channel/message model with ZERO posting/consent/governor concept —
held verbatim; denrei owns the delivery record and the membership/consent
layer on top.

> Charter: **(G1)** propose → draft only, no direct actuation — the actor
> writes proposed message content, a human turns it into an actual post;
> **(G2)** posting is **always a human call** (high-stakes), independent of
> rollout phase; **(G3)** membership is structural — the actor posts as its
> own member identity (`denrei`), and a channel that identity doesn't belong
> to (e.g. a private `#ops`) is un-postable by HARD invariant, not by
> review; **(G4)** mention discipline — @mentions are parsed with
> `kaisha.model/mentions` on BOTH sides (governor consent check and delivery
> record), so what goes out is exactly the handle set that was governed;
> **(G5)** the surface model's own invariants (`kaisha.validate`: unknown
> author, orphan reply, nested thread) are the governor's floor.

## The core contract

| op | flow | outcome |
|---|---|---|
| `:space/register` | ingest (no LLM) | kaisha space (channels/members) recorded as durable ground fact |
| `:message/draft` | assess | HARD: missing-activity / no-actuation / target-mismatch / missing-channel / not-a-member / model-invalid / tenant-mismatch → HOLD。clean+confident → phase 2+ auto-commit（データのみ） |
| `:message/post` | assess | 常に human sign-off。HARD: missing-draft / consent-blocked mention / membership / tenant → HOLD（人間でも覆せない） |

SOFT (escalate, human CAN approve past): confidence floor, duplicate-body
(identical body already in the channel), first-contact mention (even at
draft time).

TOCTOU-safe: the content a human approves at govern-time is checkpointed and
is exactly what `post!` delivers — a concurrent draft mutation while the
approval sits in the interrupt queue never changes what goes out
(`test/denrei/governor_contract_test.cljk`).

## Run

```bash
kbb -M:dev:test    # 31 tests / 129 assertions
kbb -M:dev:run     # drive the demo storyline (ingest → draft → post → holds)
kbb -M:lint
```

## Swap points

- **Store** — `MemStore` ‖ `DatomicStore` (langchain.db `:db-api`; contract
  test proves parity). `denrei.kotoba/kotoba-store` wires the same record to
  a kotoba-server pod (kotobase.net) with a **self-minted CACAO** from the
  actor's own Ed25519 key (`denrei.cacao/load-or-create-identity!` —
  `.denrei/identity.edn`, gitignored; the key-derived IPNS name IS the
  actor's graph).
- **Advisor** — `mock-advisor` (deterministic) ‖ `llm-advisor`
  (langchain.model ChatModel).
- **ChannelTarget** — `mock-channelport` (in-memory, injectable deliverer) ‖
  **`denrei.pod`** (LIVE — see below).
- **Phase** — 0 ingest-only → 1 assisted → 2/3 assisted-draft; posting is
  never phase-autonomous.

## Live pod (`denrei.pod`, ADR-2607072400)

`denrei.pod` is the live ChannelTarget: `post!` transacts the governed
delivery record into a **kaisha pod** — a kotoba-server datom graph — indexed
by channel (`:kaisha-msg/channel`), so the graph itself is the fan-out
substrate (`channel-messages` is the reference consumer query). It speaks
only the langchain.db `:db-api` map, so the in-process backend (tests) and a
real pod (production) are the same code path.

`fleet-channelport` pre-wires every murakumo-fleet-node requirement, each
verified live against `asher` (2026-07-07): graph = the actor's
account-owned private graph (`private-graph-cid`, auto-registered
`Private{owner=actor}` on first write), CACAO `aud` = the node's did:key,
multi-cap grant (`datom:read` + `datom:transact` + `tx:create`), dual graph
scope (the node's write path checks the CID, its read path the
`private/<did>` name form), second-precision timestamps, explicit `:db/id`
in tx maps.

```clojure
(def tm (pod/fleet-channelport
         {:url "http://<node>:8077"            ; tailnet; murakumo fleet.edn :fleet/port
          :identity (cacao/load-or-create-identity! ".denrei/identity.edn")
          :node-did "did:key:z6Mk..."          ; the node's DID (disclosed in its 401)
          :json-write json/write-str
          :json-read #(json/read-str % :key-fn keyword)}))
(op/build store {:channelport (:target tm)})   ; the actor now posts to the live pod
(pod/channel-messages tm "gftd" "general")     ; fan-out consumer read
(pod/follow! tm "gftd" "general" prn)          ; incremental tail (returns a stop fn)
```

Realtime follow is `messages-since`/`follow!` — cursor-based incremental
reads on the **same `:db-api` contract**, i.e. the datom-plane common
denominator shared by kotobase / kotoba-peer / a fleet kotoba-server.
Deliberately **no KSE/LiveBus dependency**: KSE is a kotoba-server-runtime
facility (absent from the workerd/browser kotobase engines) and its datomic
live-tail is ephemeral with no catch-up, so it cannot be the fan-out's
source of truth (ADR-2607072400 addendum).

See ADR-2607072330 (denrei), ADR-2607072310 (kaisha), ADR-2607072400 (pod
deployment).
