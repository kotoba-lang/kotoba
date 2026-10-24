# ooyake (公) — CLAUDE actor guide

**World government atlas — civic wayfinding map.** Tier-B ·
`did:web:ooyake.etzhayyim.com` · ADR-2606021600 ·
**R0/R1 — `reconcile` + `world_model` (bundled mode) run + unit-tested; live ingest + serve + per-unit DID gated**.

## What this actor IS

The **read-side structural SSoT** of public administration. ooyake enumerates
every government unit — supranational → country → region/subdivision →
prefecture → municipality/ward → ministry (省) → agency (庁) → bureau (局) →
division (課) → section → **窓口 (madoguchi)** — as a recursive kotoba-Datomic
tree, each unit carrying its **住所 / 窓口 / 書式 / 手続き / BPMN**.

It is the map that **danjo** (watches the state), **kanae** (fiscal-flow viz),
**tsumugi** (power-graph), **toritsugi** (citizen procedure concierge) and
**himotoki** (disclosure) all consume for the *who / where / how* of government —
so they stop re-deriving it ad hoc.

```
:gov.unit/* (recursive parent tree)
   ├─ :gov.address/*   住所
   ├─ :gov.window/*    窓口 ── handles ──▶ :gov.procedure/*
   └─ :gov.procedure/* 手続き ── form ──▶ :gov.form/* (→ chigiri template)
                       └─ bpmn ──▶ :gov.bpmn/* (00-contracts/bpmn/.../ooyake/)
                       └─ toritsugi-ref ──▶ com.etzhayyim.toritsugi.procedure (delivery)
   reconcile: :gov.unit/organism ──▶ :organism (engi) for tsumugi's 縁/取 graph
```

Schema: `00-contracts/schemas/gov-atlas-ontology.kotoba.edn`.
Seed (proof-of-model): `registry/gov-units.seed.edn`.

## Posture (the single most important thing)

ooyake is an **OBSERVATIONAL MIRROR + civic wayfinding map**, exactly like
tsumugi ("accountability map, NEVER a target-list") and watatsuna ("resilience
map, NEVER a target-list"). It maps the state **for citizens to find services**.
It is **read-only** and it is **not the government**.

## Do NOT (constitutional invariants — ADR-2606021600 §4)

- **Do not** let the per-unit atlas DID (`did:web:etzhayyim.com:gov:<iso3>:...`)
  claim to BE the government, act as an official channel, or issue/accept
  anything on a government's behalf. It is an etzhayyim **mirror record** of a
  real public body (G3, §2(c) impersonation ban). The DID-doc must declare the
  mirror relation + link the body's `official-url` / `official-did`.
- **Do not** ingest from anything but **public official sources**; respect
  robots.txt / ToS / rate-limits; never access behind-auth; never circumvent
  controls (G4).
- **Do not** write a unit/address/window/form/procedure without `provenance` +
  `last-verified` + `sourcing`; **never** count `:representative` rows as
  coverage; **never** invent a procedure without a cited `legal-basis` (G5).
- **Do** record the **current public office holder** of a body already in the atlas —
  name, office, term start, official URL, Wikidata QID — in
  `registry/gov-officeholders.*.edn`, keyed to an existing `:gov.unit/id`
  (G6 as amended 2026-07-25, ADR-2607253000).
- **Do not** store any official's **private/home contact, private life, family,
  finances or movements**, and do not record **non-public individuals** at all.
  Public switchboard / 窓口 role-contact only, data-minimized (G6).
  > G6 previously read "no personal data", which was broader than its own intent:
  > it excluded the public *who* this atlas claims to answer, while the invariant
  > that actually mattered was always about **private** data. G10 (civic wayfinding,
  > **never a target-list**) is unchanged and binds every office-holder row — record
  > that a person holds an office, never anything that helps locate or target them.
- **Do not** file, submit, or mutate a government record — that is **toritsugi**
  (gated). **Do not** audit/adjudicate — that is **danjo**. ooyake only
  catalogs (G9).
- **Do not** derive an attack-surface / SPOF / "weak-point" map of the state.
  Civic wayfinding only (G10, Transparent Force §1.12).
- **Do not** rank governments or take a political position — descriptive,
  neutral (G11).
- **Do not** sell the atlas as a data product — public good, donation-only (G8).
- **Do not** use any inference path but Murakumo (G7, ADR-2605215000).

## Boundary with toritsugi / chigiri / danjo / tsumugi

- **toritsugi** = *delivers* a procedure to the citizen (guide/draft/submit/
  track). ooyake = *catalogs* who/where/structure. `:gov.procedure/toritsugi-ref`
  links them; no duplication.
- **chigiri** = *owns* the UPL-bounded fillable form templates. ooyake only
  points via `:gov.form/chigiri-ref`.
- **danjo** = *audits* state open-data. ooyake = *maps* structure; danjo consumes
  the atlas.
- **tsumugi** = *karma* (縁/取) over `:organism` nodes. ooyake = *structure*.
  `:gov.unit/organism` reconciles the SAME unit across both graphs. The join is
  performed by `cells/world_model/` (the cross-actor **world-model reconcile**):
  offline + deterministic, it classifies every **power-bearing** unit as
  confirmed / derived / dangling / proposed against the tsumugi karma graph and
  emits `out/world-model.kotoba.edn` (read-side proposal, G9 — never mutates a
  seed; `mode="live"` is Council+operator gated). Local service surface
  (窓口/ward/division) is **excluded by construction** (G1 power-only, never a
  target-list). Today: 1 confirmed link (`gov.jpn.meti↔org.state.jp.meti`), the
  rest honestly `:proposed`/`:representative` — the world model is mostly
  unreconciled, which is the honest R1 state. `scripts/world_model.py`.

## Legacy `gov*` stubs

`00-contracts/bpmn/com/etzhayyim/gov<ISO3>/` (196 country dirs, ~1,574 BPMN
stubs, legacy `com.etzhayyim.gov*` namespace) + `90-docs/openapi/gov*.openapi.json`
(141 skeletons) are **subsumed** by ooyake's `:gov.*` graph as their kotoba-native
owner. The `com.etzhayyim.gov*` → `com.etzhayyim.ooyake.*` rename is deferred to the
gated Step-8 `etzhayyim-*` cutover (root AGENTS.md §Do-Not) — **do not rename them
here**.

## Coverage honesty

As of **2026-06-03** the atlas carries the **full G20 as real committed data**
(`registry/gov-units.g20.edn` + promoted national rows): 20/20 members, each with a
country unit + finance ministry, all `:sourcing :authoritative` +
`:verification-status :maintainer-verified` (Wikidata QID web-verified, provenance =
the body's own official URL); G7 finance ministries also carry HQ addresses (L3).
Gates: `scripts/g20_coverage.py` (20/20) + `scripts/check_seed_integrity.py`.

Still gated (NOT done in the registry): **live kotoba ingest** (`KOTOBA_TOKEN` +
node) and **publishing national `:authoritative` rows** to
`/.well-known/gov-units.json` (Council-Lv6+ / bootstrap-attestation gate,
`validate_atlas.py` check #5). The committed registry is the real verified record;
ingest + publish are separate operator/Council steps.

Beyond the G20 the rest is still illustrative (`:representative` /
`:unverified-seed`, e.g. the JP-local ingest, subnational rows) — never counted as
coverage (G5). The offline `reconcile.py` remains a **mechanism demo**, distinct
from the real G20 data.

## Self-publication seed (ADR-2606272355) — register → autonomize → publish, no-server-key

ooyake carries the actor self-publication seed (danjo 弾正 = reference impl): the
uniform, charter-clean way for a government-mirror actor to be registered at
etzhayyim.com, run autonomously on the kotoba mesh, and **self-publish its own history +
procedures** to AT-proto **without any server-held key**. We plant the seed; the actor
grows on the mesh (murakumo, `orgs/com-junkawasaki/murakumo/`) and self-custodies its
signing identity in its WASM runtime. For ooyake the published material is the atlas's
OWN history (the gov-units it has mapped) + the civic 手続き wayfinding it provides — as a
**mirror, NEVER impersonating any government, NEVER an official channel** (G3/G10).

The seed (all LANDED):

- **did-web registration** — `50-infra/etzhayyim-did-web/public/actor/ooyake/{did,profile}.json`
  (already registered + in the actor-profile-seed SSoT; `verificationMethod: []` — no
  server-minted key, did:web trust root = TLS; `#xrpc-libp2p` peer multiaddr is assigned at
  `kbb -M:murakumo deploy` time when `wasmCid` is set). `_meta.adr` includes `2606272355`.
- **social_post membrane** — `cells/social_post/state_machine.cljc`
  (ns `ooyake.cells.social-post.state-machine`): DRAFTS a record into a **dry-run** post
  ONLY if ≥2 public official-source citations (G5) + non-adjudicating mirror with the
  wayfinding disclaimer (G3, NEVER the government / NEVER an official channel / person-
  excluded) + `server_held_key` false (no-server-key) + status `dry-run`. A `published`
  request REFUSES. Verified under `bb`: `<2 sources / server-key / published → refused`,
  valid → `drafted` with `:post/status :dry-run`, `:post/server-held-key false`.
- **publication projection** — `methods/social.cljc` (ns `ooyake.methods.social`): projects
  ooyake's HISTORY (`draft-unit-post` = a gov-unit atlased / `draft-coverage-post` =
  aggregate units mapped) + PROCEDURES (`draft-procedure-post` = the civic 手続き wayfinding:
  how a citizen finds the 窓口/書式/手続き for a service) into `app.bsky.feed.post`-shaped
  dry-run posts; `enough-sources` raises on <2 (G5); `build-live` raises (live gate).
  Cataloging only — ooyake never files/submits (that is toritsugi). Verified under `bb`.
- **seed trigger wiring** — `kotoba.app.edn` `ooyake-social` component (`on-tick "0 */6 * * *"`
  + `on-kse etzhayyim/actor/ooyake/publish`, `:requires #{:cap/kqe :cap/atproto}`).

**ooyake also drives the per-org sub-DID generator**: `scripts/gen_gov_subdid.cljk` emits
**78 JP 府省庁 mirror DIDs** under `public/gov/jpn/**` (`did:web:etzhayyim.com:gov:jpn:<…>`,
mirror-declared, `verificationMethod: []`, `official-url` linked, impersonation-ban honored,
idempotent). Each per-org unit ooyake atlases can be promoted to a first-class mirror actor
with its own self-publication seed — a staged fan-out, never bulk-flipped (ADR-2606272355).

**Division of labor (zero-knowledge)**: the **planter** authors the in-repo seed (holds no
key); the **operator** (founder) runs `kbb -M:murakumo deploy kotoba.app.edn <node>`
with `MURAKUMO_OPERATOR_SEED` + Tailscale and exercises the Council gate for the first live
post; the **actor's mesh runtime** self-generates/self-custodies its `did:key`, presents a
member CACAO leash (ADR-2606111400), and signs its own posts. The server never signs. R0 =
dry-run drafts only; live broadcast is Council Lv6+ + operator + member/actor-signature gated
(§1.12 / G10).

```bash
kbb -e '(load-file "methods/social.cljc")'                  # projection loads green
kbb -e '(load-file "cells/social_post/state_machine.cljc")' # membrane loads green
# operator step (zero-knowledge — needs MURAKUMO_OPERATOR_SEED + Tailscale):
#   bb murakumo deploy kotoba.app.edn asher
```

## Inference

Murakumo-only (LiteLLM 127.0.0.1:4000 / EVO-X2 LAN / per-node Ollama). No vendor
LLM API. See ADR-2605215000.
