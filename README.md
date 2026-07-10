<p align="center">
  <img src="docs/assets/header.png" alt="kotoba" width="480">
</p>

# kotoba

**Role: the language** — safe Kotoba (`.kotoba`) profile, admission gates, and
**WASM AOT emit**. Not the guest execution runtime.

```text
kotoba   = language   (.kotoba → check → wasm emit → guest.wasm)
kototama = runtime    (host & run that .wasm)   ← kotoba-lang/kototama
aiueos   = OS / broker (decides grants; tender only enforces)
```

Stack vocabulary: [ADR-2607022400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022400-kototama-unikernel-tender-runtime-vocabulary.md).

```
KOTOBA ≝ safe Kotoba[cap⊗effect] × Datom[e a v] (kgraph, in-mem)
          × WASM/WIT × CACAO × AT Protocol × LLM/Weight
```

**kotoba : kotobase = Clojure : Datomic** (ADR-2607032500). kotoba is the
**language** — a capability-safe Lisp/EDN that compiles to WebAssembly, plus its
in-memory **datom data model** (`kotoba.kgraph`, an EAVT `[e a v]` store). The
**database** — the persistent, indexed, Datalog-queryable, content-addressed,
time-versioned datom store built _on_ this model — is
[**`kotoba-lang/kotobase`**](https://github.com/kotoba-lang/kotobase) (the
"Datomic"): it depends on kotoba, never the reverse. Keep kotoba the language;
the datom **database** lives in kotobase.

- **Language + compiler** — [`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang)
  defines the source profile (`.kotoba` canonical, portable `.cljc` with
  `#?(:kotoba ...)` for Kotoba-specific branches); this repo’s `kotoba wasm emit`
  compiles that subset to **WebAssembly** (AOT compiler, not a guest runtime).
  **safe Kotoba** is the capability-confined profile. **Execute guests with
  [kototama](https://github.com/kotoba-lang/kototama)** — not this repo’s primary job.
  See [**Language**](#language--kotoba-lang--kotoba-wasm) below.
- **Clojure on Clojure** — the compiler that implements this Clojure-shaped
  language is itself written in Clojure/ClojureScript (`.cljc`); the earlier
  Rust workspace has been fully removed (see
  [Rust-free CLJ launcher](#rust-free-clj-launcher) below). Guest **execution**
  is **kototama**, not a second runtime in this repo. Capability-safety design
  is *benchmarked against* Rust on an explicit safety ladder — see the "Safety
  model" bullet under
  [Language — kotoba-lang & kotoba wasm](#language--kotoba-lang--kotoba-wasm)
  or `kotoba-lang/docs/adr/ADR-safe-capability-language.md`.

## Repository boundary

`kotoba-lang/kotoba` is the **language** substrate: profile consumers, safe
gates, AOT compiler, package admission, and reusable language-side libraries
(datom view, crypto adapters used by the compiler/CLI). **Guest WASM execution
belongs in `kotoba-lang/kototama`**, not here. Keep storage/crypto/fixtures that
serve the language; do not grow a second tender. The split policy is recorded in
[`docs/ADR-repository-boundaries.md`](docs/ADR-repository-boundaries.md).

`kotoba-lang/kotoba-lang` owns the standalone language and public CLI contract.
This repository keeps host implementations, integration tests, and legacy Rust
adapters while they are migrated to consume the CLJC/EDN authority there.

The Rust `kotoba` crate/CLI is an integration adapter over multiple workspace
crates. It is no longer the semantic authority for the public CLI. New command
shape belongs in `kotoba-lang/kotoba-lang`, and host launchers should delegate
to that CLJC contract.

`kami-engine` is the strongest future split candidate when the Kami host,
rendering/devtool SDK, templates, and golden UI verification can build without
`kotoba-kotodama` path dependencies. After that split, this repository should
keep only thin WIT/component fixtures and integration tests for Kami surfaces.

Domain actors do not belong in this repository. They live in
`etzhayyim/com-etzhayyim-*` as `.cljc` actors/cells. AT Protocol actors,
PDS/AppView handlers, and XRPC application surfaces live in
`gftdcojp/app-aozora`. Hosting, placement, fleet, gateway, and runtime
operations live in `kotoba-lang/murakumo`.

The historical `crates/kotoba-kotodama` tree (and the rest of `crates/`) has
since been removed from this repository entirely (`604896171b`, 2026-07-01);
domain cells, Python UDF pools, AT Protocol actors, and hosting code moved to
their canonical owners per the boundary above.

## 📺 Explainers & Docs site

A static documentation site (landing page + **two interactive, auto-playing
explainer videos** with Japanese narration) lives under [`docs/`](docs/) and is
published via GitHub Pages:

> **🌐 [kotoba-lang.github.io/kotoba](https://kotoba-lang.github.io/kotoba/)**

| explainer | what it covers |
|---|---|
| **Part 1 — [Datomic × IPFS × Prolly Tree](https://kotoba-lang.github.io/kotoba/explainer/kotoba-datomic-ipfs-explainer.html)** | how a Datomic-style query runs over a Prolly-Tree index that is DAG-CBOR/IPLD content-addressed and pinned to IPFS — write → 4-index build → CID → CommitDag → query `scan_prefix` → result provenance CID |
| **Part 2 — [Query / CACAO / Signal](https://kotoba-lang.github.io/kotoba/explainer/kotoba-query-auth-signal-explainer.html)** | complex/large queries (BGP join, MaterializedView), multihop (property paths, Pregel BSP), federation (`SERVICE`), the transact write path, CACAO auth/authz (depth-2 delegation), and Signal E2E (X3DH → Double Ratchet) + t-of-N custody |

> These are self-contained HTML (open the Pages links above, or open the files
> in [`docs/explainer/`](docs/explainer/) directly in a browser). GitHub does not
> render the interactive HTML inline in this README. Every claim is grounded in
> the actual source (`prolly.rs`, `arrangement.rs`, `cacao.rs`, `delegation.rs`,
> `x3dh.rs`, `ratchet.rs`, `shares.rs`).

See [**Documentation**](#documentation) below for the full ADR / design index.

## Install

### Homebrew (macOS / Linux)

```bash
# Tap the kotoba formula
brew tap kotoba-lang/kotoba        # one-time
brew install kotoba                # installs the CLJC/EDN-backed `kotoba` launcher
```

To track the upstream `main` branch instead of the latest tagged release,
add `--HEAD`:

```bash
brew install --HEAD kotoba
```

Or, install the formula directly from this repo without tapping:

```bash
brew install --build-from-source ./Formula/kotoba.rb
```

### From source (any platform)

```bash
git clone https://github.com/kotoba-lang/kotoba.git
cd kotoba
bin/kotoba-clj check --kind cli-contract --json
```

### npm / npx

The npm package is also a CLJC/EDN-backed launcher. It requires a local
`clojure` command on `PATH`.

```bash
npm install -g @kotoba-lang/kotoba
kotoba check --kind cli-contract --json
```

### Rust-free CLJ launcher

The CLJ launcher delegates to `kotoba-lang/kotoba-lang`'s CLJC CLI authority
instead of adding new Rust command semantics:

```bash
clojure -M -m kotoba.launcher check --kind cli-contract --json
bin/kotoba-clj deploy --manifest package-manifest.edn --target dev
```

Side-effecting commands return EDN/JSON data for host adapters. They do not
invent independent Rust behavior. There is no Rust code or `crates/` tree left
in this repository (removed `604896171b`, 2026-07-01) — the CLJC launcher
above is the only current install path.

## Quick start

**Language (this repo):** `.kotoba` → check → **WASM AOT emit**.  
**Runtime (sibling):** run the emitted `.wasm` with
[`kotoba-lang/kototama`](https://github.com/kotoba-lang/kototama).

```bash
# ── LANGUAGE (kotoba) ──────────────────────────────────────────
kotoba check cell.kotoba --json
kotoba wasm emit cell.kotoba --policy policy.edn --package-lock lock.edn -o cell.wasm
kotoba wasm safe-build cell.kotoba --policy policy.edn --package-lock lock.edn -o cell.wasm  # alias of emit
kotoba wasm build cell.kotoba --policy policy.edn --package-lock lock.edn -o cell.wasm         # alias of emit

# ── RUNTIME (kototama) — canonical execute path ────────────────
cd ../kototama   # or any checkout of kotoba-lang/kototama
clojure -M:cli run cell.wasm --grant …
# browser / Node: kototama/web + kotoba-lang/wasm-webcomponent

# ── Compat / debug only (not the product execute story) ────────
# kotoba wasm run …          # Chicory bootstrap in this repo; prefer kototama
# kotoba run --engine wasm …
# kotoba run …               # JVM tree-walk interpreter; debug only

kotoba check --kind cli-contract --json
kotoba package verify --lock lock.edn --trust trust.edn --json
```

`--package-lock` is mandatory for `wasm emit` / `safe-build` / `build` (and for
compat `wasm run`): the package admission gate always runs first — no opt-out
(F-001).

Looking for things to run? [`docs/DEMONSTRATIONS.md`](docs/DEMONSTRATIONS.md)
indexes every real program built with `.kotoba` so far — the mesh apps, the
**kami-survivors game**, and the capability demos under `src/`, the browser-
and kototama-hosted tools, and the kami-lineage games — with the host that
executes each one.

`db` / `git` / `rad` / `deploy` / `hinshitsu` are declared in the same
contract for the distributed-graph, git-adapter, RAD sovereign-repo, and
deploy/quality-gate surfaces; consult `lang/cli.edn` for their current tier
and option shape rather than this README, since the contract is the
versioned source of truth and this file is not.

CACAO ecosystem helpers:

```bash
kotoba did-derive <32-byte-hex-seed>             # → did:key:z…
kotoba cacao-sign <seed> --graph <cid> \
    --capability datom:read [--private] [--aud <did>]
```

## Language — kotoba-lang & kotoba wasm

### `kotoba-lang/kotoba-lang` — the language contract

The language itself is not defined in this repository. **[`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang)**
("Kotoba language design, source profile, and conformance contract") is the
semantic authority — see [Repository boundary](#repository-boundary) above.
This repo hosts launchers and adapters that consume that contract; it does
not define new command shape or language semantics of its own.

- **Not a Clojure superset or dialect in the full sense — a Clojure-family
  *profile/subset*** with its own compatibility contract. Canonical source
  extension: `.kotoba`. Compatibility extensions: `.clj`, `.cljc` (portable,
  shared Clojure-family source). **`.cljs` is retired as a dedicated source
  extension** (profile v2) — ClojureScript-targeted behavior lives inside
  `.cljc` via `#?(:cljs ...)`, not a separate file type. Reader-target
  resolution order for `.cljc`: `:kotoba → :clj → :default`; namespace file
  resolution priority: `.kotoba → .cljc → .clj`.
- **The CLI/command contract is EDN, not code.** `lang/cli.edn`
  (`:kotoba.cli.contract`, versioned M0–M3) and `lang/adapters.edn` (scopes
  which repos may host adapters) define the command surface; `lang/profile.edn`
  is the machine-readable profile spec. `src/kotoba/cli.cljc` validates the
  contract and shapes argv as EDN — host launchers (like this repo's
  `bin/kotoba-clj`) adapt to this contract; they don't define protocol
  semantics of their own.
- **Compilation target is WebAssembly.** The public compiler surface is
  `kotoba -e` / `kotoba wasm ...`; `kotoba -e '(+ 1 2)'` is compile-and-run
  sugar (wraps the expression as an exported `main`, compiles Kotoba → core
  Wasm, runs it) — not a runtime `eval`.
- **Safety model — "safe Kotoba."** Three formal soundness goals: **T1
  Memory Safety**, **T2 Effect Soundness** (`Γ ⊢ e : T ! E`), **T3 Capability
  Confinement** (a compile-time analog of CACAO delegation attenuation).
  Capabilities are explicit, scoped, typed *values* (`GraphReadCap`,
  `GraphWriteCap`, `InferCap`, `EgressCap`, `SecretReadCap`, `ClockCap`,
  `RandomCap`) — never ambient strings a module can summon by name. Design
  ranking from the language repo's own ADR: capability-sandboxed +
  deny-by-default + reproducible builds (Kotoba's target) ranks above
  Rust-style ownership/borrow Wasm, which ranks above "Clojure syntax + safe
  subset + borrow checker," which ranks above linter-only Clojure/
  ClojureScript.
- **Conformance, not vibes.** `lang/conformance/`, `lang/capability-conformance/`,
  and `lang/package-conformance/` hold positive/negative EDN fixtures run by
  a manifest-driven conformance suite, tracked on an M0–M6 maturity scale
  (`docs/lang/coverage.edn`), with its own versioning policy
  (`docs/lang/versioning.md`) and CI gates (`docs/lang/gates.md`).
- **Package/lock contract.** `lang/package.edn` — CID-pinned packages,
  RID+signature authority, no capability grant without an explicit lockfile
  + policy (`docs/adr/ADR-kotoba-package-cid-lock.md`). Wire protocol:
  Transit JSON (`docs/adr/ADR-kotoba-transit-wire-protocol.md`).
- **Where "authority" stops.** `kotoba-lang/kotoba-lang` owns the *semantic
  contract* (what the language and CLI mean), not every implementation.
  Capability *value-passing* (typed cap params, `cap-acquire`, i64 ABI
  threading) is implemented in this sibling repo's CLJ runtime, not in
  `kotoba-lang/kotoba-lang` itself — the contract repo defines the shape
  (`docs/lang/capability-values.md`), hosts implement it.

The rest of this section (below) walks through the **historical Rust
implementation** of this same design (`kotoba-clj`, `policy.rs`/`subset.rs`/
`effects.rs`). That Rust workspace was removed from this repository
(`604896171b`, 2026-07-01) — the file paths below are a historical record
(see git history), not current source. The CLJC-native successor is tracked
in [ADR-2607022600](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022600-kotoba-database-crates-cljc-migration-roadmap.md)
(database side) and lives entirely in `kotoba-lang/kotoba-lang` itself
(language/compiler side).

## 言語性（Language-ness）

`kotoba` の言語性は、単なる「シンタックス定義」ではなく、次の3点で成立しています。

1. **言語契約の明示化**  
   `.kotoba` が正規ソース契約、`.clj/.cljc/.cljs` が互換入力という優先順位付きの入力面を持つ。  
   `#?(:kotoba ...)` と名前空間解決ルールで、Rust 実装に依存しない公開仕様として運用します。

2. **コンパイルの主権移譲**  
   `kotoba wasm` / `kotoba -e` は `kotoba-lang` の言語面をコンパイラ API として明示し、最終的に
   **WASM Component** として発行します。実行環境は AST ではなく、コンパイル済みバイナリで評価されます。

3. **実行可能性の拘束化**  
   `safe` プロファイルは「言語で強く動く」ではなく、**許可されたものしか実行できない** という意味論で安全性を定義します。  
   capability/subset/effect の3ゲートは、実行前に入口で拒否され、`allow-by-default` ではない言語挙動を採用します。

この `言語性` は `docs/lang/` 配下のプロフィール・互換性仕様と、`docs/ADR-kotoba-lang-profile.md` / `ADR-safe-capability-language.md`
（および `ADR-kotoba-wasm.md`）で追跡しています。

kotoba is not only a database — it ships its **own language profile**.
[`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang) defines the source contract: `.kotoba` is
the canonical Kotoba source extension, portable `.cljc` is for shared
Clojure-family source, `.clj` is a compatibility input, and
`#?(:kotoba ...)` selects Kotoba-specific code.

### Primary path: safe Kotoba → WASM AOT

`kotoba wasm emit` / `safe-build` / `build` compile the **safe Kotoba**
(Clojure/EDN subset + capability/subset/effect gates) **directly to a real
WebAssembly MVP binary**. This is AOT, not an embedded JVM Clojure interpreter.
`.kotoba` is the canonical guest language; JVM Clojure is only the bootstrap
implementation of the compiler CLI today (portable emit core is moving to
`.cljc` for nbb/browser-adjacent hosts).

```bash
# Language AOT surface (package-lock mandatory, F-001)
kotoba wasm emit cell.kotoba --policy policy.edn --package-lock kotoba.lock.edn -o cell.wasm
kotoba wasm safe-build cell.kotoba --policy policy.edn --package-lock kotoba.lock.edn -o cell.wasm
```

**Run** those bytes with **`kotoba-lang/kototama`** (`clojure -M:cli run cell.wasm`)
or browser host (`kototama/web`, `wasm-webcomponent`).  
`kotoba wasm run` remains Chicory **compat** only — not the product runtime.

### Safe Kotoba gates

| Gate | Guarantee | Theorem |
|---|---|---|
| **Capability** | a module's wasm import section ⊆ the policy's grants — ungranted host capability is *physically absent* from emitted bytes | **T3 — Capability Confinement** |
| **Subset** | no `eval`, no runtime `require`/`import`, no dynamic-var mutation (`set!`/`binding`), no reflection, no unrestricted `defmacro` | no ambient code/effect |
| **Effect** | a function may not perform an effect outside its declared effect row (interprocedural) | **T2 — Effect Soundness** |

See [`docs/ADR-safe-capability-language.md`](docs/ADR-safe-capability-language.md).
Policy is deny-by-default EDN (e.g. `src/demo_policy.edn` in this repo).

### Historical / not current CLI names

Rust-era docs still mention `kotoba -e`, `wasm safe-policy`, and
`wasm selfhost-inspect`. Those verbs are **not** the live CLJ launcher surface
(crates removed 2026-07-01). Live **language** verbs: `wasm emit`/`safe-build`/
`build`, `check`, `selfhost list|check`. Guest **runtime**: kototama.  
`wasm run` here is compat only. Self-hosting the analyzer as a `.kotoba` guest
(executed on kototama) is a follow-up track.

Audit/tooling APIs, usable standalone: `embedded_capability_ifaces(wasm)`
(byte-level capability surface), `infer_effects(src)` (source-level transitive
effects), `minimal_policy(src)` (least-privilege synthesis), `Policy::to_edn`.
Self-hosting has started in slices under
[`crates/kotoba-clj/selfhost/`](crates/kotoba-clj/selfhost/): the
`safe_analyzer.kotoba` seed is written in Kotoba, compiles as safe Kotoba to a
Wasm Component, has no embedded host capability imports, and is checked against
the Rust analyzer for the covered effect/capability/policy surface. Rust callers
can exercise that path through `kotoba_clj::selfhost::{Analyzer,
infer_effects, minimal_policy, check_effect_declarations, check_policy,
check_admission, unused_grants, compile_safe_kotoba}`. Status:
capability (instance-level), subset, and effect (interprocedural) gates
implemented and byte-verified (S0–S4) with safe-mode tests; typed HIR / borrow
checker (T1) and wider self-hosting are tracked in the ADRs.

Current naming: `kotoba` is the language + database + semantic substrate,
`kotoba wasm` / safe Kotoba is the executable language path that turns Kotoba
into Wasm, and `aiueos` is the OS/component supervisor and capability broker.
`kotoba-clj` remains the implementation crate for that compiler path. In that
split, Rust-free self-hosting means moving authoritative language/admission
semantics into confined Kotoba components slice by slice, while Rust remains
the bootstrap/emitter/oracle for unfinished slices.

## Current repositories (CLJC, post-migration)

This repo (`kotoba-lang/kotoba`) is the launcher + host-adapter substrate. Its
`deps.edn` and CI (`.github/workflows/ci.yml`) pull in the sibling repos that
hold the rest of the stack as `:local/root`/git dependencies, not `crates/`
subdirectories:

| Repo | Role |
|---|---|
| `kotoba-lang/kotoba-lang` | the language/CLI semantic authority — `.kotoba` source contract, `lang/cli.edn` command contract, conformance fixtures |
| `kotoba-lang/kotoba-core-contracts` | core CID/contract types shared across hosts |
| `kotoba-lang/kotoba-selfhost-contracts` | self-hosting analyzer contract |
| `kotoba-lang/cacao`, `kotoba-lang/ed25519`, `kotoba-lang/dag-cbor` | CACAO auth, signing, and content-addressing primitives |

In this repo, `src/kotoba/` holds the host implementation: `launcher.clj`
(dispatch), `wasm_exec.clj` (Wasm execution via Chicory), `git_adapter.cljc` /
`rad_adapter.cljc` (git and RAD sovereign-repo adapters), `kgraph.clj`,
`host_providers.clj`, `package_admission.clj`, `cap_table.clj`, `runtime.clj`.

The database/runtime crates described below (`kotoba-core`, `kotoba-graph`,
`kotoba-store`, `kotoba-runtime`, `kotoba-auth`, `kotoba-signal`, …) were a
**Rust workspace removed from this repository** (`604896171b`, 2026-07-01).
They're kept here as a design-vocabulary reference — the same names/roles
recur throughout the Architecture, Query Surfaces, and Performance sections
below — while the CLJC-native successors land per
[ADR-2607022600](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022600-kotoba-database-crates-cljc-migration-roadmap.md).
None of the `cargo` commands or `crates/*` paths below are runnable in this
repository today.

## Crates, architecture & performance (historical Rust design record)

The pre-migration Rust implementation's crate table, canonical write/query
architecture, SPARQL query surfaces, and benchmark numbers are kept as a
design-vocabulary reference in
[`docs/HISTORICAL-RUST-ARCHITECTURE.md`](docs/HISTORICAL-RUST-ARCHITECTURE.md)
rather than in this README — that Rust workspace was removed from this
repository (`604896171b`, 2026-07-01), and per
[ADR-2607032500](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607032500-kotoba-kotobase-clojure-datomic-relationship.md)
the persistent, distributed database itself is not this repository's
identity — that's [`kotoba-lang/kotobase`](https://github.com/kotoba-lang/kotobase).
This repo is the language; the CLJC-native rebuild of the database design is
tracked in [ADR-2607022600](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022600-kotoba-database-crates-cljc-migration-roadmap.md).

## Properties

- **Content-addressed** — IPFS-compatible CIDv1 sha2-256 over raw / dag-pb / dag-cbor blocks
- **Immutable datoms** — Datomic-style 5-tuple `(E,A,V,T,Added)` with retract tombstones
- **5-index arrangement** — EAVT / AEVT / AVET / VAET / TEA for O(1)–O(log n) access
- **Prolly Tree storage** — deterministic, hash-consistent B-tree over blocks
- **Distributed Pregel** — BSP graph computation across nodes via libp2p
- **AT Protocol native** — Datom projection backed by commit DAG and JetStream
- **WASM runtime** — arbitrary graph logic as Component Model guests
- **Capability-safe language** — `kotoba wasm` compiles Kotoba/EDN → WASM; **safe Kotoba** confines untrusted/AI-generated modules by deny-by-default capability, subset, and (interprocedural) effect gates — capability confinement (T3) and effect soundness (T2)
- **E2E encryption** — Signal Protocol + CACAO auth for consent-gated data
- **Datomic/Datalog primary, SPARQL auxiliary** — the distributed Datom DB is the source of truth; SPARQL 1.1 reads the same projection for RDF-compatible query and federation
- **CACAO-native authz** — depth-2 delegation chains, multi-graph grants, anti-replay nonce
- **X-Road-style accountability** — ciphertext-only replication, purpose-declared + signed + receipted key release via t-of-N custodians, anchored tamper-evident audit log, slashable unreceipted releases. See [`docs/SECURITY-ARCHITECTURE.md`](docs/SECURITY-ARCHITECTURE.md)

## kotoba-shell release pipeline (design, not yet shipped)

`kotoba-shell` — a desktop/mobile app shell layer over safe Kotoba components
and the aiueos shell surface — is designed in
[`docs/ADR-kotoba-shell-aiueos-safe-kotoba.md`](docs/ADR-kotoba-shell-aiueos-safe-kotoba.md).
There is no `kotoba shell` subcommand wired up in this repo's launcher yet
(current commands: see [Quick start](#quick-start)); treat the ADR as the
design record, not a usable CLI.

## Documentation

The published docs site — [**kotoba-lang.github.io/kotoba**](https://kotoba-lang.github.io/kotoba/)
— is the entry point (overview, the two explainers, architecture, crates,
security, and this index). It is the static site under [`docs/`](docs/), served
by [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

| doc | topic |
|---|---|
| [`docs/index.html`](docs/index.html) | docs-site landing page (hub) |
| [`docs/DEMONSTRATIONS.md`](docs/DEMONSTRATIONS.md) | **demonstrations** — index of real programs built with `.kotoba` (mesh apps, capability demos, browser/kototama-hosted tools, kami-lineage games) and the hosts that execute them |
| [`docs/HISTORICAL-RUST-ARCHITECTURE.md`](docs/HISTORICAL-RUST-ARCHITECTURE.md) | pre-migration Rust crate table, architecture, query surfaces, and benchmarks (design-vocabulary reference) |
| [`docs/paper/`](docs/paper/) | arXiv-style research paper (LaTeX source) — full system description |
| [`docs/explainer/`](docs/explainer/) | the two interactive explainer videos |
| [`docs/SECURITY-ARCHITECTURE.md`](docs/SECURITY-ARCHITECTURE.md) | X-Road-style accountability, R0–R3 custody, threat model |
| [`docs/ADR-001-five-axis-distributed-redesign.md`](docs/ADR-001-five-axis-distributed-redesign.md) | five-axis distributed redesign |
| [`docs/ADR-sealed-cold-tier.md`](docs/ADR-sealed-cold-tier.md) | encrypted cold tier + t-of-N custody |
| [`docs/ADR-clojure-wasm.md`](docs/ADR-clojure-wasm.md) | Clojure/EDN-subset → WebAssembly compiler (the language) |
| [`docs/ADR-safe-capability-language.md`](docs/ADR-safe-capability-language.md) | **safe-clj** — capability-confined language design (capability/subset/effect gates, T2/T3) |
| [`docs/ADR-kotoba-shell-aiueos-safety-clj.md`](docs/ADR-kotoba-shell-aiueos-safety-clj.md) | kotoba-shell, aiueos runner integration, and release security gates |
| [`docs/lang/README.md`](docs/lang/README.md) | language profile (`.kotoba`/reader target), conformance fixtures, and gates |
| [`docs/ADR-browser-cid-query-vs-p2p.md`](docs/ADR-browser-cid-query-vs-p2p.md) | browser execution boundary |
| [`docs/ADR-wallet-actor-cljs.md`](docs/ADR-wallet-actor-cljs.md) | CLJS wallet actor and Ethereum library surface |
| [`docs/ADR-turn-relay.md`](docs/ADR-turn-relay.md) | pure-Rust TURN relay for WebRTC |
| [`docs/ADR-kotoba-word.md`](docs/ADR-kotoba-word.md) | word/root registry + capability boundary |
| [`docs/ADR-research-paper-arxiv.md`](docs/ADR-research-paper-arxiv.md) | arXiv paper as a grounded, derived artifact |
| [`docs/WASI-HTTP-EGRESS-XRPC-INGRESS.md`](docs/WASI-HTTP-EGRESS-XRPC-INGRESS.md) | I/O boundary (egress/ingress) |

The cross-cutting design SSoT remains the parent-monorepo ADR (see [ADR](#adr) below).

## Build

This repo has no Rust build (see [Current repositories](#current-repositories-cljc-post-migration)
above). CI (`.github/workflows/ci.yml`) runs two jobs:

```bash
# CLJ launcher gates — checks out the deps.edn :local/root contract siblings, then:
clojure -M:test
bin/kotoba-clj check --kind cli-contract --json
bin/kotoba-clj package verify --lock test/fixtures/package/positive-lock.edn \
  --trust test/fixtures/package/trust.edn --json

# Python SDK gates (sdk/kotoba-modal): pytest + wheel-contents check
```

## ADR

Design decisions live in
[`90-docs/adr/2605240001-kotoba-cleanroom-architecture.md`](https://github.com/etzhayyim/etzhayyim-apps-etzhayyim/blob/main/90-docs/adr/2605240001-kotoba-cleanroom-architecture.md)
of the parent monorepo.  Section §27 captures the current SPARQL surface,
HTTP loadtest matrix, and operator-UX defaults.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
