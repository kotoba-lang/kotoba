# kototama

`kototama` is the Kotoba **virtual-machine contract** — 言霊, the spirit of
the word when it acts. It defines the deterministic transition from closed
Lisp data, an IPLD world, a closed admission predicate and a message to a new
world and receipt. Runtime engines validate, budget, **runtime-link**, and run
artifacts that [`amu`](https://github.com/kotoba-lang/amu) wove. Kototama does
**not** own the language, compiler, grant policy, consensus or fleet placement.

Solo5 called this role a *tender*. That word is a nautical metaphor for the
attendant host. It is not the product name. The product is kototama.
Hosts live in sibling repos so the dependency direction stays checkable
(ADR-2607266000 / ADR-2608139980).

```text
kotoba     言葉      language
amu        編む      compiler — project link, one closed cloth
abi        経        WIT / admission contract (no implementation)
kototama   言霊      VM contract — reduction, state, authority, receipt
grant                who may do what, decided as pure data (never executes)
aiueos     あいうえお  operating system — enforces grant's answer; supplies named providers
sahai      差配      T6 placement loop (leases/checkpoints/fencing)
murakumo   叢雲      inference node network and its own fleet control plane (never grants)
hata       機        proposed conductor: runs cells and calls kototama's hosts (ADR-2610082200)
```

Grant decisions left aiueos for `kotoba-lang/grant` on 2026-08-21 (root
ADR-2608219500): grant answers, aiueos enforces. The reusable T6 placement
library is `sahai`; murakumo operates an inference fleet with its own control
plane (root ADR-2610071730) and is not the placement owner for every Kotoba
workload. The hosts (宿) below are engines a conductor calls per cell; root
ADR-2610082200 proposes that conductor as `hata` (機) and keeps the two apart.

## Lisp machine architecture

AiueOS is the OS for a modern Kotoba Lisp machine in development. Kototama
is its implementation-independent Lisp VM contract: closed S-expression
computation, IPLD state, bounded authority and content-addressed receipts.
Amu checks and compiles code; grant decides permission; runtime hosts and OS
mechanisms enforce the admitted boundary. Kototama also has hosted engines
and does not require AiueOS for every execution.

The [stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture.md) separates responsibility, source/library
and artifact dependencies. Its [composition contract](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture.edn) routes
to each owner's specification; it is not a new language or runtime semantics.
"Modern Lisp machine" describes the architectural direction. It does not
certify a complete integrated debugger, live system modification, full heap
image restore, selfhost compiler or physical-machine qualification.

## Kototama as the Kotoba VM

Kototama occupies the architectural role that EVM and FVM occupy in their
ecosystems, without making one concrete engine or opcode encoding normative.
Its native instruction form is a closed S-expression; its state is IPLD; its
admission core is a closed predicate written in Kotoba and compiled by amu
([`src/kototama/admission.kotoba`](src/kototama/admission.kotoba)), over a
capability-chain grant; Datalog and Biscuit sit outside that core as a query
library and a boundary adapter (root ADR-2610082200); its outputs are
content-addressed receipts.

The normative specification is
[`docs/kototama-virtual-machine.md`](docs/kototama-virtual-machine.md), with a
machine-readable contract at
[`spec/kototama-vm-v1.edn`](spec/kototama-vm-v1.edn). Compatibility is
declared through versioned `core/v1`, `fvm-actor/v1`, `evm/v1` and `fevm/v1`
profiles. An implementation must say whether it provides message, semantic,
bytecode or state compatibility and attach conformance evidence; an unqualified
“EVM compatible” claim is not valid.

This repository also contains host contracts and a historical JVM compatibility
tender. They are implementations of Kototama surfaces, not the definition of
the VM.

## Kotoba / CLJ Kotoba refactor

Q9 migration from the historical `lib/` and `clj/` trees is whole-component
only. A predicate or decision-core extraction is compiler research, not a
migration. Each component must move its complete public surface and transitive
Kotoba source closure, with native mechanisms represented as declared provider
imports rather than used as a reason to shrink the migration unit.

Every declared target must pass both the public Kotoba CLI build path and the
direct Amu compile path, and the resulting manifests must agree. The accepted
decision is [ADR 0012](docs/adr/0012-whole-component-kotoba-migration.md); the
machine-readable adoption gate is
[`qualification/q9-whole-component-build.edn`](qualification/q9-whole-component-build.edn).
Both acceptance paths are JVM-free: `kotoba` is a verified native executable,
and Amu runs with `--jvm-free`, which fails instead of invoking `clojure`.

## What a run leaves behind

Running is the point at which the stack touches the world, so the record of it
is a first-class value rather than a side effect. Root ADR-2608160200 makes
that explicit:

- **A receipt is a value, not a line** — *landed 2026-08-16*.
  `kototama.linear-journal` is a durable at-most-once capability-consumption
  journal, and that safety property is untouched: the file lock, the fsync
  and the count still own it. **Content addressing is not idempotence** — a
  CID does not stop a second execution, and nothing about the linear
  guarantee moved into the hash.

  What changed is that an entry has an identity. Each line is addressed by
  the raw CIDv1 of its own bytes (`entry-cid`, over `canonical-line`, so
  anyone can recompute it from the file alone), and carries `:prev`. Two
  things follow that an append log cannot give: a transaction elsewhere can
  **cite** the consumption that authorised it, and an edited or removed
  middle entry stops being invisible — `verify-chain` says where.

  Journals written before this carry no `:prev`. They are reported as an
  unchained prefix, not as corruption; a journal that predates the chain is
  not a broken chain. Stripping `:prev` from a chained entry is *not*
  accepted as legacy, or the escape hatch would be the forgery route.

  **Outcomes are recorded too** — *landed 2026-08-16*. A claim is written
  *before* the provider runs (that is what makes the guarantee at-most-once
  rather than exactly-once), so at claim time there is no outcome; the
  outcome is a second entry carrying the four fields
  `lang/capability-semantics.edn` requires — `:receipt/cap`, `:receipt/at`,
  `:receipt/call`, `:receipt/outcome` — plus `:receipt/value` for a source,
  which is exactly what `kototama.execution` needs before it will treat an
  execution CID as a cache key.

  A receipt never consumes budget, an incomplete one is refused, and a
  receipt for a consumption that never happened is refused — it would be a
  record of authority nobody spent.

  `capability-semantics.edn` also declares `:attempt-always-receipted true`,
  and a rule nothing can check is a wish, so **`unreceipted` answers which
  consumptions have no outcome recorded**. A crash between the claim and the
  provider returning shows up there, which is the point: the authority was
  spent and nothing knows what came of it.

  Still to come: dag-cbor rather than raw, so generic tooling can read the
  fields. It costs a CBOR dependency in a repo that keeps
  `kototama.contract` and `lib/*` zero-dep, and there is still no reader
  asking for it — the condition for paying, not a date.

- **An execution is addressable** — *landed 2026-08-16*, `kototama.execution`:
  `{program, input, state, runtime, policy, effects} → CID`, the runtime half
  of what amu already does for builds with `:kotoba.output-set/v1` and its
  signed provenance. Incidental fields (timing, host, duration) are dropped
  from the canonical form: two runs of the same program on the same input
  under the same policy are the same execution, and letting them in would
  make every run unique and the CID useless.

- **That CID is a memo key only when the effects allow it** — same landing.
  `execution-cid` always answers, because an execution that cannot be
  memoised is still citable. `memo-key` answers **nil** unless the run is
  replayable, and a caller wanting a key has to come through it — two
  functions rather than a flag, because a flag is easy to ignore.

  Replayable means: a **source** (clock, randomness, a network read) has its
  *value* recorded — an outcome of `:ok` says the call happened, not what it
  returned, and replaying against `:ok` invents the answer; a **sink** has an
  outcome; and an effect kind nobody classified refuses the memo, which is
  `capability-semantics.edn`'s `:unknown-kind :deny` applied here so that an
  unfamiliar effect cannot become cacheable *by* being unfamiliar. The
  classification is passed in rather than hardcoded, because that vocabulary
  belongs to `kotoba-lang` and a second copy would drift.

Receipts and artifacts live on the same physical plane as database state —
IPLD blocks in CARv2 packs on the object store (root ADR-2608160100). Small
frequent values like receipts are exactly what packing is for.

## Hosts (all kototama, not sibling products)

| Host | Repo | What it runs |
|---|---|---|
| browser / native Wasm | [`wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent) | AOT `.wasm` on the host engine. First path. Extracted so other repos can adopt it |
| native ELF | [`kototama-native`](https://github.com/kotoba-lang/kototama-native) | `kototama.native.executor` — sealed native artifacts under a capability gate |
| Component engine | [`kototama-component`](https://github.com/kotoba-lang/kototama-component) | already-admitted Components via Wasmtime micro-TCB / jco / workerd |
| JVM compat | `kototama.tender` (this repo) | Chicory harness. Not the first path |

`provider` is the hand kototama may bind after grant allows it. It is not
shipped inside this repo.

See [`docs/hosts.md`](docs/hosts.md).

Stack vocabulary: [ADR-2607022400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022400-kototama-unikernel-tender-runtime-vocabulary.md)
(role word *tender*), product naming [ADR-2608139980](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2608139980-amu-weaves-kototama-binds.edn).
Stack topology, the deliberate `kototama → aiueos` dependency direction, the
browser-parity gate for new `actor:host` imports, and the canonical
capability-schema plan: [docs/0009](docs/0009-stack-topology-parity-gate-capability-schema.md)
(root authority: `com-junkawasaki/root` ADR-2607241100).

**Not to be confused with [`kotoba-lang/kotodama`](https://github.com/kotoba-lang/kotodama)**
— both names romanize the same word (言霊/言魂, "word-spirit"; "kototama" and
"kotodama" are two real, independently-attested readings of the same kanji,
not a typo), but the repos are unrelated in scope: `kotodama` is the generic
functional-organism runtime (organism/ReAct machinery injected into any
actor, extracted from `etzhayyim/kototama`'s UNSPSC-specific predecessor);
this repo is the Wasm **execution** tender described below.
ADR-2607050900 audited the naming overlap and found no functional
duplication — just an undocumented spelling split, which this note closes.

## Role (detail)

In the `kotoba → amu → kototama → aiueos` stack, runtime engines execute the
programs that **amu** wove, enforcing grant / authority decisions. Native
internal calls share their execution context and typed values. Guest/host
terminology applies to an actual embedding or target ABI crossing; it does not
require a second world for each Kotoba library. **Do not reimplement the compiler here.** Project linking
(many sources → one cloth) is amu. Runtime linking (imports → granted
providers) is kototama.

The current portable contract is WIT plus the WebAssembly Component Model on
WASI 0.3, versioned in [`kotoba-lang/abi`](https://github.com/kotoba-lang/abi).
Kototama verifies and composes compiler-produced component worlds;
sync functions remain sync, while async functions/futures/streams require
explicit cancellation and bounded lifetime/item/byte budgets. A host accepts
only declared WIT imports and a verified, scoped grant decision; it must not turn
a WASI import into ambient filesystem, network, clock, random, environment, or
process access. Kototama is the product-facing engine API; its initial engine
adapter may embed a mature native engine such as Wasmtime. Boot, isolation,
device adapters, and root-key use remain a small native micro-TCB. A nested
Wasm engine is not the product path: it adds an engine but cannot replace the
outer native engine that starts and isolates it. See
[`ADR-2607252500`](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607252500-kotoba-wasm-component-first-execution-boundary.edn).

**Compile guests with [`kotoba-lang/kotoba`](https://github.com/kotoba-lang/kotoba).**

### Runtime priority (ADR-2607100100 / ADR-2607102200 addendum 3)

**First path is not JVM/Chicory.** App/runtime order is:

```
kotoba wasm AOT  >  clojurewasm  >  ClojureScript  >  nbb
(JVM / Chicory is demoted — last-resort / explicit compat only)
```

| Path | Status | Notes |
|---|---|---|
| **`.kotoba` → AOT `.wasm` on native WebAssembly** | **first** | browser/Node via [`wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent) (extracted from this repo's `web/`) |
| **clojurewasm** | next when FFI allows | host-import surface still limited (upstream Phase-16); revisit for host-import guests |
| **ClojureScript host wire** | when native WASM + CLJS host imports | e.g. portable `kotoba.kami-host` |
| **`kototama.tender` (JVM/Chicory)** | **demoted compat / CI** | landed historically (ADR-2607022900 / 2607062330); keep for bit-exact fixtures, not the design premise |

The workerd path is intentionally a Core-Wasm compatibility adapter because
workerd does not instantiate Component Model binaries directly. The production
JavaScript boundary in `workerd/kototama-core-host.mjs` compares the module's
actual imports with the exact admitted manifest, exposes no ambient WASI, and
rechecks authorization on every named provider call. `npm run test:workerd`
runs that boundary and a real provider call inside a pinned workerd binary.
This reuses the ABI's capability semantics; it does not claim that a Component
binary and a Core module are the same artifact.

### Compat tender (Chicory) — still present, not primary

`src/kototama/tender.cljk` wires every `kototama.contract` `actor:host` import
to a Chicory `HostFunction` with pre-flight + per-call grant checks,
`RuntimeLimits`, memory limits, and fuel. Useful as a verification harness
against real Wasm bytes — **not** what "use kototama" means for new work.
Language-repo `kotoba wasm run` (`kotoba.wasm-exec` in `kotoba-lang/kotoba`)
is the same class of **compat bootstrap**, but a deliberately separate
implementation, not shared code: it exists so that repo's own emit path
can prove its own output runs, in its own test suite, without a cross-repo
test dependency on kototama. See com-junkawasaki/root ADR-2607182200 for
the full cross-repo dependency graph and why these two JVM/Chicory paths
are not considered duplicated work to consolidate.

## Contract Surface

- `src/kototama/contract.cljk` defines the `actor:host` import surface,
  `HostCaps`, `RuntimeLimits`, grant normalization, and import validation
  (pure data, zero-dep, no execution — see `kototama.tender` for that).
- `src/kototama/tamaki_contract.cljk` independently admits Tamaki's versioned
  capability envelope before `HostCaps` construction. Business capabilities
  are not authority: imports, grants, limits, effect policy, ABI version, and
  network allowlists are rechecked at this boundary.
- `src/kototama/tender.cljk` is the Chicory-based execution runtime (see
  above). `:clj`-only, matching `com.dylibso.chicory`'s own JVM-only
  nature; pulls in `com.dylibso.chicory/{wasm,runtime}` and
  `kotoba-lang/org-ietf-ed25519` (`kototama.contract` itself stays free of them).
- `src/kototama/aiueos_adapter.cljk` closes the "grant decides, kototama
  enforces" loop for real: calls `grant.cli/command-result` directly (a
  real `io.github.kotoba-lang/grant` dependency, in-process; aiueos is not
  on this path since the grant plane left aiueos on 2026-08-21, root
  ADR-2608219500 — the namespace name is historical) and translates the
  actual grant/deny decision into a `kototama.contract/host-caps` value.
  `kototama.tender` never computes a grant itself either way
  (ADR-2607022700's rule); this only removes the need for every caller to
  hand-build `HostCaps` from a decision grant already made. Covers the
  subset of `actor:host` imports grant's default kernel capabilities recognize
  (`log-write`/`clock-monotonic`/`random-bytes`) — `gen-keypair`/`sign`/
  `verify`/`sha256-hex`/`http-post`/`log-read` have no kernel-capability
  counterpart and still take caller-supplied `HostCaps`, same as before.
- `lib/kototama/*.cljc` contains the portable organism/cell runtime:
  gates, membrane, heartbeat, did:key, atproto shaping, and identity helpers.
- `lib/actor/publish.bb` is the shared actor publish runner.

## Quick start (runtime)

```bash
# Guest must already be AOT-compiled by the language (kotoba):
#   kotoba wasm emit cell.kotoba --package-lock L -o cell.wasm

kbb -M:cli run path/to/guest.wasm --grant …     # execute (tender / CLI)
kbb -M:cli lint path/to/guest.kotoba            # emit-pitfall lint only (no compile)
kbb -M:cli inspect path/to/guest.wasm
kbb -M:doctor
node web/verify-host-free.mjs                       # first path: native WebAssembly engine
```

## Browser / native WASM host (`web/`)

[ADR-2607061630](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607061630-kototama-browser-wasm-aot-webcomponent.md)
and ADR-2607100100: the **first** execution premise is the host's native
WebAssembly engine on already-AOT `.wasm` from **kotoba** — not "JVM hosts a
Wasm interpreter". Hosting library:
[`kotoba-lang/wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent)
(`web/` is a consumer). See `web/README.md` for R0 scope.  
`kotoba wasm run` and `kototama.tender` Chicory paths are **compat / CI**.

## Published site (`index.html`, `docs/index.html`)

GitHub Pages serves this repository from the default branch root, so the demo
and every document are already public. Both directory addresses used to 404 —
there was no document at either, and no map of what was published.
`scripts/generate-site.cljk` builds them from the repository tree: the lead
paragraph is read out of this README, each document title is that file's own
`#` heading, each byte count is `stat` on the real file. It is built on
[`jp-go-dds`](https://github.com/kotoba-lang/jp-go-digital-design-system), the
workspace's base design system.

```bash
D=../jp-go-digital-design-system
kbb --backend sci --classpath "$D/src:../html/src:../css/src" scripts/generate-site.cljk \
  --dds-css "$D/resources/jp_go_dds/dds.css"            # regenerate
kbb --backend sci --classpath "$D/src:../html/src:../css/src" scripts/generate-site.cljk \
  --dds-css "$D/resources/jp_go_dds/dds.css" --check    # 1 if hand-edited
```

The output is generated — do not hand-edit it. `--check` exits 1 when the
committed HTML and a fresh generation disagree, and the generator refuses
(exit 1) rather than publish an index with no documents, a demo section with
no payloads, or a document title it had to invent from a filename. An input
it cannot read at all exits 2, so "could not run" never looks like "ran and
found nothing wrong".

## Maturity

**Current tender level: R2 advanced-partial** (R1 stable). The former R3
shared-store placement implementation and its stable gate now live in
[`kotoba-lang/fleet`](https://github.com/kotoba-lang/fleet).
Ladder and gates: [`docs/maturity.md`](docs/maturity.md).

| Level | Status |
|---|---|
| R0 contract / dry-run | stable |
| R1 tender (compat: JVM/Chicory) | stable as **compat suite** — session report, host-free guests, emit lint, CLI (not the first path) |
| **R2 browser / native WASM host** | **first product path** (advanced-partial, derived from `kototama.browser/parity-score`: 19/58 linkable, the rest explicit native-boundary `:no`) — AOT `.wasm` via wasm-webcomponent; `http-post` and `llm-infer` both real via a Worker-hosted SAB+Atomics bridge, needs COOP/COEP; `llm-infer` additionally needs a caller-supplied proxy URL; host-free web fixtures |
| T6 fleet placement | external — stable gate owned by `kotoba-lang/fleet` |

```bash
kbb -M:doctor                                    # tender/browser snapshot
kbb -M:cli parity                                # R2 import matrix
bash deploy/validate-packaging.sh                    # authority receiver packaging
kbb -M:cli lint  path/to/guest.kotoba            # lint only — compile with kotoba
kbb -M:cli run     path/to/guest.wasm            # RUNTIME: run AOT guest
node web/verify-host-free.mjs                        # R2 host-free under browser Wasm
```

Host-free pure guests are first-class on **native WASM** (browser/Node via
wasm-webcomponent / `web/`) and still verified on the demoted JVM tender
(`fact(5)=120`, peak-cells `@4096→240`).

## Test

```bash
kbb -M:test
kbb --classpath lib lib/kototama/test_actor.cljk
kbb --classpath lib lib/kototama/test_atproto.cljk
```

`kbb -M:test` is the default repository gate (contract + tender + aiueos
adapter + guest lint + maturity fixtures). `kototama.tender-test`
shells out to the `wasm-tools` CLI (Bytecode Alliance) to assemble its WAT
fixtures into real Wasm bytes at test time — install it (`cargo install
wasm-tools` or your package manager) if it isn't already on `PATH`. The
babashka commands cover the current organism runtime helpers when `bb` is
available.

## Migration

The old Rust wrapper around `kotoba-clj` and `kami-engine-clj` has been removed
from this repo. Historical native implementation details remain available in git
history. New behavior should land first as CLJC/EDN contracts; native hosts can
adapt those contracts in their own repositories when needed.

See [`docs/rust-migration.md`](docs/rust-migration.md).

## License

MIT.

## Target-neutral and distributed stack architecture

Defines closed computation, state transitions, bounded authority and receipts. Engines implement this contract; neither a Wasm engine nor an EVM opcode set defines it. Target ABI profiles bind artifacts at host admission. Permission is decided by grant/authority and enforced by the host. Hosted engines do not require AiueOS.

See the [owner integration guide and dependency direction](docs/stack-architecture.md),
[composition metadata](spec/stack-integration.edn), and
[whole-stack refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md).
The direction is adopted; runtime contract migration and qualification remain
explicit, separately verified work. Tier labels are responsibility axes, not
a single dependency ranking.

## Execution contract entrypoints

Neutral descriptors are imported from `kotoba.core.execution` (core-contracts).
Component/WIT profiles and unchanged mixed v1 identity/lease codecs are imported
from `kotoba.abi.component` (abi). The old `kotoba.abi.contract` facade remains
readable for existing callers; new production imports select their owner.
The [integration contract](spec/execution-profile-integration.edn) records this
cutover. Existing v1 blocks/WIT/CIDs remain unchanged; v2 neutral identities
require a verified target binding and fresh CID/signature. This change does not
enable v2 runtime admission or claim Q9/native qualification.

## Explicit v2 execution

See [execution v2](docs/execution-v2.md) and [owner contract](spec/execution-v2.edn).
New target bindings, authority-issued invocation/leases and authenticated admission
are explicit APIs; existing v1 runtime defaults remain compatible.
