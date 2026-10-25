# shinkansen（新幹線）

**shinkansen is the content-addressed web framework for the Kotoba stack: the
view, the state, and the agent-facing tool surface are all addressed by CID.
Nothing in a shinkansen app is located by a mutable name — a link is a CID,
a state transition is a CID, and an agent fetches UI through the same
address a browser does.**

Like its namesake, the framework is fast, straight, and every station is a
stop you can get off at: each document, each db value, each tool result is a
station addressed by content. This is a metaphor name for the
kotoba-lang family and is registered in
`manifest/concept-vocabulary.edn` (com-junkawasaki root).

## What it is — and what it is NOT

shinkansen is a **connection layer over three existing substrates** (ADR-2609131808).
It deliberately does not re-implement UI, state management, or event handling:

| layer | existing substrate shinkansen connects | what shinkansen adds |
|---|---|---|
| view | [`shitsuke/kotoba/*.kotoba`](https://github.com/kotoba-lang/shitsuke) — re-frame/reagent algebra already implemented as amu guests (`reframe_core.kotoba` 304 lines, `reagent_core.kotoba` 150 lines, plus hiccup/hig/tokens/components) | **document → CID publish** (two-plane, via `publish-document.cljk`) |
| state | same `reframe_core.kotoba` — `db + event → db` as a pure guest | **db value → CID chain**: every dispatch's db value is hashed, addressed, and appended |
| tool call | kotoba-server's `word mcp` stdio server shape | **MCP tools** `lake_list` / `lake_head` / `lake_fetch` / `lake_dispatch` so an LLM agent reads the lake and drives the app through tool calls |

js and events stay where they already are: the host's authority. A Kotoba
guest returns an inert document; the host (dom-gpu renderer, browser host,
Worker) renders it and owns every effect. This is the shitsuke boundary
unchanged — shinkansen does not add a DOM capability wire.

## Five axes, one envelope (SPEC §1.5–1.8, 2026-09-16)

A request raises five questions and five different mechanisms answer them —
none is a stand-in for another:

    who    principal   DID          what   artifact   CID
    where  origin      Web origin   may    grant      Biscuit (an upper bound, not authority)
    do     effect      effect request

`shinkansen.invoke` is the one shape every transport (HTTP, MCP, CLI) carries —
`{:artifact cid :principal did :grant … :input {:kind :query|:action|:event …}}` —
and the seam where authority is decided: an injected `authorize-fn` sees
`{:principal :artifact :grant :effect}` and **nothing about where the call
came from**. No authorizer is a refusal (`:no-authorizer`), not a pass. The
framework parses no Biscuit and holds no policy; that is `kotoba-lang/authority`
and `org-biscuitsec`. A URL path is a name that resolves to an artifact — the
same CID is reachable through N names on N origins, and none of them is its
identity or its authority.

## The four planes (ADR-2609092600)

    identity  ipfs://{cid}                       immutable, the only address an app records
    naming    DNSLink / IPNS                     the mutable name over the identity
    bytes     https://{cid}.ipfs.yataverse.com   Location (owner directive 2026-09-14; {cid}.ipfs.kotobase.net is retired)
    entry     https://{name}.itonami.app/        Location (one DNS label)

A shinkansen link in HTML is `href="https://{cid}.ipfs.yataverse.com/"` — the
CID IS the link. The `:document` kind is self-contained by the ADR's rule:
a document that needs to fetch its own runtime from the CDN is not one file
and cannot claim a CID.

## Repo layout

    docs/SPEC.md                   仕様（設計原理・モジュール契約・検証・次の一段）
    docs/HOST-BINDING.md           kotoba.cloud Worker/host cheat sheet (locale / theme / audit / invoke / receipts)
    src/shinkansen/publish.cljk    view/document → CID (both planes), fail-closed
    src/shinkansen/state.cljk      db value → CID chain (Unison-style content addressing)
    src/shinkansen/invoke.cljk     invocation envelope (query / action / event) + the authority seam
    src/shinkansen/routes.cljk     name → artifact resolver (the path is a reference, not identity)
    src/shinkansen/actions.cljk    post-authorization declaration check + chain entry
    src/shinkansen/mcp.cljk        MCP tool surface (stdio JSON-RPC, kotoba-server shape); lake_dispatch is an invoke transport
    src/shinkansen/interaction.cljk  browser contract (data-action / run stream / hydrate / theme / locale) + one runtime
    src/shinkansen/theme.cljk      light / dark / system — storage, attribute, head script, theme/set
    src/shinkansen/viewport.cljk   multi-screen-size contract (viewport meta + phone band)
    src/shinkansen/audit.cljk      UI/UX document contract as a deterministic fitness function (21 axes)
    src/shinkansen/coscientist.cljk Generate→Reflect→Rank(Elo)→Evolve→Meta kaizen loop, judge = audit
    kotoba/                        .kotoba guests (bridge modules, compiled by amu)
    test/                          kbb -M:test

## Run the reference host

```bash
npm run host           # http://127.0.0.1:8787/ — real CIDs as ETags, real Ed25519 Biscuit
                       # authorizer on POST /invoke, ssr /todos, dev live-reload
npm run verify:host    # the same host on port 0, driven over HTTP: 19 cases, SCANNED 19 / FAILED 0
npm run verify:live    # the contract on a LIVE name host (kotoba.cloud, docs.kotoba.cloud): bytes hash
                       # to the ETag's CID, 304 strong + weak, assets claim nothing, /v1/invoke refuses
```

The host is the one place every contract is DRIVEN rather than declared
(SPEC §2.5). `src/shinkansen/maturity.cljk` is the honest map of what a
product still has to pick up — declared vs driven, with measured consumer
counts — and its test pins that every namespace it names exists.

## Performance

**<https://kotoba-lang.github.io/shinkansen/>** — server CPU per response
against node:http, Fastify, Hono, Express, Next.js and Nuxt on the same bytes
(also as [`docs/bench.md`](docs/bench.md)). Both are generated from a results
file by `bench/report.cljk`, so the numbers live in exactly one place and are
not repeated here. How it is measured and how to re-run:
[`bench/README.md`](bench/README.md).

Where the numbers come from: an answered document's ETag is the CID of its
bytes, so `shinkansen.serve` answers a repeat URL from a per-URL table of
pre-encoded bytes (:ssr only after its load answers `=` data). When the data
changes on every request the app's render and the CID encoding run
interpreted under kbb/sci, and that path costs several times the JIT'd
frameworks; closing it needs a compiled build, which does not exist yet.

## Test

```bash
npm run verify:authority   # the seam under a REAL authorizer: Ed25519 Biscuit → biscuit.kotoba/authorize
                           # → invoke → chain, 16 cases both directions (SPEC §3.1); needs the sibling
                           # repos org-biscuitsec / authority / text at their west pins
npm test           # nbb runner: requires each test ns explicitly (nbb 1.5.212
                   # no longer auto-requires), prints per-ns + TOTAL summary,
                   # exits non-zero on failure. 172 tests / 703 assertions.
```

## MCP stdio server

```bash
npm run mcp        # JSON-RPC over stdin/stdout; lake = https://yataverse.com
# e.g.: echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | npm run mcp
```

Four tools: `lake_list` / `lake_head` / `lake_fetch` / `lake_dispatch`.
`lake_dispatch` takes `artifact` + `event`; the caller's principal and grant
are the session's (ctx), never tool arguments. It honestly answers "no app
attached yet (R0)" — declared but unimplemented must be visible.

## Status

The map is [`src/shinkansen/maturity.cljk`](src/shinkansen/maturity.cljk)
(declared vs driven-by-host vs driven-by-product). Measured-at **2026-09-16**.
Counts by status: **driven-by-product 12**, **driven-by-host 4**, **declared 3**,
**not-by-design 2**, **absent 1**.

Still declared (contract + tests, nobody requires them): locale
(`shinkansen.locale`), mcp (`shinkansen.mcp`), form (`shinkansen.form`).
MCP's stdio process still answers **"no app attached yet (R0)"**.

kotoba.cloud product binding already landed for routes / adapter / invoke /
state identity (PR #16, SPEC §6) — a Worker host on that product answers
ETag = CID and `POST /v1/invoke`. Layouts and render stay the app's.

Host maintainers: [`docs/HOST-BINDING.md`](docs/HOST-BINDING.md) is the cheat
sheet for using those contracts instead of re-deriving them.
