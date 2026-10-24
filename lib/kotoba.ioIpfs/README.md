# ipfs

`kotoba.lang.ipfs` — Kubo (IPFS) HTTP API pin/fetch/node-info helpers, as a
**pure portable Clojure (`.cljc`) core over an injected `IHttp` transport**.

| Function | What it does |
|---|---|
| `(pin-blob http api-url content)` | POSTs a blob to Kubo's `/api/v0/add?pin=true&cid-version=1`, returns `{:cid :size}` |
| `(fetch-blob http gateway-url cid)` | GETs a blob from a Kubo gateway's `/ipfs/<cid>` (returns bytes) |
| `(node-info http api-url)` | Checks a Kubo node is reachable, returns `{:id :version}` |

`http` is a host-supplied `IHttp` impl (see `kotoba.lang.ipfs/IHttp`): the host
provides `-get` / `-post` / `-post-file` backed by `java.net` /
`babashka.http-client` (JVM) or `fetch`/`FormData` (CLJS/WASM). **The library
itself performs zero network I/O and has zero vendor/SDK deps** — every URL,
request body and response parse is a pure function; only raw byte transport is
injected. This is the kotoba-lang layer contract (ADR-2606302300 §Step-1: pure
`.cljc`, zero network I/O, zero vendor SDK).

JVM is synchronous (returns plain values); CLJS is async (returns `js/Promise`,
mirroring the original TypeScript). JSON parsing uses `json.data-json` (JVM)
/ `js/JSON.parse` (CLJS) behind reader conditionals.

## Kotoba pilot

The transport-neutral HTTP 2xx admission predicate also has a closed,
two-module Kotoba implementation under `kotoba/`. `kotoba-project.edn` is
checked and compiled in CI with the checksum-verified released native CLI, and
the resulting restricted ESM is tested against the same 200--299 boundary.
The project declares an explicit empty package lock and trust policy; their
verified receipt identities are sealed into the generated ESM even though this
leaf pilot currently has no external Kotoba package dependencies.
The wider IPFS transport and JSON data model remain genuine `.cljc`; they are
not relabelled until Kotoba has safe bounded maps, byte values, and host ports.

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/ipfs.ts`
to `kotoba-lang/ipfs` per the org-taxonomy library-placement rule
(ADR-2606302300). Originally relocated as TypeScript (a physical move), then
ported to portable `.cljc`. The original TypeScript has been **deleted** — the
`.cljc` core is now the single canonical implementation (TypeScript was only
ever the npm-consumable artifact; the kotoba-lang layer contract requires a
pure `.cljc` substrate). Design authority: ADR-2605171800 Stage 4 (in
`etzhayyim/root`).

The one in-repo consumer is `kotoba-lang/checkpointer` (relocated alongside
this package), which injects its own `IHttp` when calling `pin-blob`.

## Develop

```bash
kbb -M:lint     # clj-kondo (errors fail)
kbb -M:test     # cognitect test-runner (pure helpers + JVM orchestration, no network)
```

`kbb -M:test` is **unavailable**: babashka was retired as this workspace's script
host (ADR-2607173000) and the conversion left `scripts/tasks.edn` empty, so the
task has had no runnable path since 2026-07-17 (ADR-2608131600). The recovered
babashka body is in `scripts/tasks-complex.edn`. `kbb -M:test` above runs
the same suite — 5 tests / 11 assertions, verified 2026-08-13.
