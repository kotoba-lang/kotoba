# goyoukiki

御用聞き — a **government-procurement signal + bidder-matching control
plane**: a match-LLM ⊣ ProcurementGovernor StateGraph that watches Japan's
government procurement pipeline (both published 入札公告/公示 tenders AND
their *advance* 調達予定 forecast disclosures — the anticipatory, 先回り
signal) and proposes which pre-qualified candidate (全省庁統一資格 registrant)
could respond, but never notifies anyone itself. The actor is **propose →
match only**: a match commits as data (a *casual commit*); actually notifying
a candidate that a match exists (`:match/share`) is **always a human call**,
regardless of phase.

Historically, a 御用聞き was a merchant who visited a patron regularly to
anticipate their needs *before* being asked. Here the patron is the actor's
own client — a candidate vendor — and the "household" whose needs are
anticipated is a government agency. goyoukiki only ever relays PUBLIC signals
(forecast disclosures, published tenders, the government-wide qualified-
vendor registry) to its own client-side candidates; **it has no code path to
contact the issuing agency at all** — see the Charter and `goyoukiki.matchport`
below.

Built on this workspace's
[`langgraph`](https://github.com/kotoba-lang/langgraph) StateGraph runtime —
the same pattern as [`teian`](../teian) (deck-LLM ⊣ BriefingGovernor) and
[`koyomi`](../koyomi) (schedule-LLM ⊣ ComplianceGovernor). Here it is
**match-LLM ⊣ ProcurementGovernor**.

> Charter: **(G1)** propose → match only, no direct actuation — the actor
> writes a proposed opportunity⟷candidate pairing, a human turns it into an
> outbound notification; **(G2)** notifying a candidate is **always a human
> call** (high-stakes), independent of rollout phase; **(G3)** `:match/share`
> is structurally incapable of contacting the issuing AGENCY — its
> destination is always resolved from the matched candidate's own registered
> `:contact`, never from a caller-supplied field (no unsolicited-proposal /
> ex-parte-contact risk by construction); **(G4)** sharing is additionally
> blocked outright while an opportunity is flagged `:silence-period?`, even
> if everything else about the match is clean (官製談合防止法/入札談合等
> 関与行為防止法 — never a channel for bid-rigging/collusion during a live
> competitive window); **(G5)** goyoukiki does not draft the bid-response
> document itself — that is `teian`/`tayori`'s job, consuming a shared match
> as their own itonami-activity input (out of scope here, ADR-2607070200).

## The core contract

```
opportunity/candidate ground facts (先回り forecast + live tender + qualified-vendor registry)
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌───────────┐  proposal: propose /  ┌─────────────────────────┐
   │ match-LLM  │  share                │  ProcurementGovernor     │  (independent system)
   │ (sealed)   │ ────────────────────▶ │  no-actuation ·          │
   └───────────┘  + cited facts        │  nomination · eligibility │
                                       │  redaction · silence-period│
                                       └──────────┬───────────────┘
                            commit ◀─────────────┼──────────────▶ hold (no
                     (propose: casual commit,  escalate            nomination /
                      auto ok at phase≥2;          │               ineligible /
                      share: ALWAYS here) ──▶ 人間 承認            missing-redaction /
                                          (shareは常に人間)         silence-period;
                                                                    un-overridable)
```

**The actor never notifies a candidate the ProcurementGovernor would reject,
and match-LLM never actuates directly.** HARD invariants force **hold** (a
proposal that names no candidate, an ineligible candidate, a missing
redaction on a sensitive cite, or an attempt to share during a bid-silence
window); a clean share still routes to a human.

## Run

```bash
kbb -M:dev:run     # drive: forecast ingest → propose → share through the actor
kbb -M:dev:test    # the propose-only contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

Demo: register a forecast (先回り observe → ground fact) → propose a match for
a known, eligible-candidate opportunity (phase 3 → clean → auto-commits, no
interrupt) → share it (**always** human sign-off, even though clean) →
phase-0 disables proposing entirely → a silence-period-flagged opportunity
still allows propose but blocks share → prints the matching audit ledger →
swaps to `DatomicStore` with identical results.

## Layout

| File | Role |
|---|---|
| `src/goyoukiki/model.cljk` | pure **opportunity**/**candidate**/**match** data shapes |
| `src/goyoukiki/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **matching audit ledger** |
| `src/goyoukiki/policy.cljk` | pure checks (cross-candidate confidentiality redaction · 全省庁統一資格 category/rank eligibility) — shared by governor & match-LLM, no I/O |
| `src/goyoukiki/matchllm.cljk` | **match-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); nominates/pass-through proposals |
| `src/goyoukiki/governor.cljk` | **ProcurementGovernor** — no-actuation · nomination · eligibility · redaction · silence-period · high-stakes |
| `src/goyoukiki/phase.cljk` | **Phase 0→3** — ingest-only → assisted → assisted-match → supervised (share always human) |
| `src/goyoukiki/operation.cljk` | **MatchActor** — langgraph StateGraph; ingest vs assess flows |
| `src/goyoukiki/matchport.cljk` | **MatchTarget** port (`fetch-match`/`propose-match!`/`share!`) + `mock-matchport` — `share!`'s destination is always the candidate's own `:contact`, never a caller-supplied field |
| `src/goyoukiki/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor key) |
| `src/goyoukiki/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/goyoukiki/query.cljk` | pure status lookups (`match-status`/`shared?`) for callers that don't want to run the actor |
| `src/goyoukiki/sim.cljk` | demo driver |
| `src/goyoukiki/cli.cljk` | minimal JVM status-check entrypoint |
| `src/goyoukiki/jp/kkj.cljk` | real ingestion — kkj.go.jp live 入札公告 search API (全省庁+団体) |
| `src/goyoukiki/jp/geps.cljk` | real ingestion — GEPS 落札実績オープンデータ (全53省庁, awarded history) |
| `test/goyoukiki/*_test.clj` | propose-only contract · store parity · CACAO |
| `test/goyoukiki/jp/*_test.clj` | ingestion connector parsing/mapping, against real captured fixtures |

## MatchTarget → real backend (injection)

`goyoukiki.matchport/mock-matchport` is the runnable, deterministic default —
no network/creds. A live run needs a real Notifier (email/portal/etc) — inject
your own `notify-fn`; goyoukiki does not ship one.

```clojure
;; actor issues its own key, self-mints CACAO (same pattern as teian/kekkai)
(require '[goyoukiki.kotoba :as k] '[goyoukiki.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".goyoukiki/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))

;; a real match-LLM + a real Notifier
(require '[langchain.model :as model] '[goyoukiki.operation :as op]
         '[goyoukiki.matchllm :as matchllm] '[goyoukiki.matchport :as matchport])
(op/build store
  {:advisor (matchllm/llm-advisor (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))
   :matchport (matchport/mock-matchport (atom {}) my-real-notify-fn)})
```

An unparseable/hallucinating LLM response falls to confidence 0 / noop, and
**ProcurementGovernor always hold/escalates** it (no path from a malformed
LLM response to an actual notification).

## Data sourcing & licensing (JP v1 scope)

v1 targets Japan only. Two real, verified `opportunity` ingestion connectors
ship in `src/goyoukiki/jp/` (JVM-only, not loaded by the `.cljc` core):

- **`goyoukiki.jp.kkj`** — 官公需情報ポータルサイト (kkj.go.jp, 中小企業庁), a
  documented public search API (検索APIガイド V1.1) aggregating LIVE 入札公告
  from national ministries, independent administrative agencies,
  universities, AND local governments — the "全省庁、団体" breadth in one
  feed. `:status :open`.
- **`goyoukiki.jp.geps`** — 落札実績オープンデータ (調達ポータル/GEPS, Digital
  Agency), a documented open-data download covering AWARDED-bid history
  across the complete, closed set of all 53 official 府省コード bodies.
  `:status :awarded` — a stronger eligibility/capability signal (who
  actually WON what) than a self-declared rank, but historical, not a live
  invitation to bid.

Both were verified against real live responses (not just the spec docs) —
see each namespace's docstring and `test/goyoukiki/jp/*_test.clj` (fixture-
based, no network in CI; the connectors' own `-main` entrypoints do make
real network calls and are meant for manual/ops runs, e.g. `kbb -M:dev
-m goyoukiki.jp.kkj "情報システム" 20`). `candidate` ground facts (全省庁統一
資格 registrants) still have no shipped connector — that registry is
interactive-HTML-only (no bulk/API access found), so v1 keeps hand-seeded
`goyoukiki.store/demo-data` for candidates; only `opportunity` ingestion is
real. Per-source terms of use (kkj.go.jp's own 利用規約, GEPS's implicit
政府標準利用規約) govern reuse — this repo fetches only through the
documented public API/download surface, nothing scraped outside it.

## cloud-itonami / downstream consumption

See `90-docs/adr/2607070200-kotoba-lang-goyoukiki-procurement-signal-actor.md`.
Add `io.github.kotoba-lang/goyoukiki {:local/root
"../../kotoba-lang/goyoukiki"}` to `deps.edn` for in-process use, or read via
`goyoukiki.kotoba/kotoba-store` against a kotobase.net graph. Drafting the
actual bid-response document from a `:shared` match is explicitly out of
scope here — a follow-up wiring layer would translate a shared match into a
`teian`/`tayori` drafting request.

## Status

Scaffold + runnable. Store is `:db-api` driven — `MemStore ≡
DatomicStore(langchain.db) ≡ kotoba-store(kotobase.net)` on the same
contract. CACAO self-issuance is offline-verified. Real `opportunity`
ingestion (`goyoukiki.jp.kkj` + `goyoukiki.jp.geps`) is shipped and verified
against live government data. Still not shipped: a `candidate` (全省庁統一
資格) connector and a live Notifier (inject your own) — same known state
teian/koyomi/tayori ship in for the notify side.
