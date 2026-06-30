# kotoba-clj self-hosting seeds

This directory holds Kotoba programs that reimplement small compiler or
admission-gate responsibilities in Kotoba itself.

The architectural target is self-hosting in slices, not a flag-day rewrite.
Rust remains the portable substrate and bootstrap compiler; Kotoba
progressively takes over language/admission semantics that can be expressed and
verified as safe Wasm components.

System vocabulary used by this directory and the related ADRs:

```text
kotoba              = language + database + semantic substrate
kotoba wasm         = executable language path / safe Kotoba -> Wasm
kotoba-clj          = implementation crate for the compiler path
aiueos              = OS / component supervisor / capability broker
```

This is the canonical responsibility split for self-hosting work:

- `kotoba` owns the language/database semantics that should eventually be
  expressible in Kotoba itself.
- `kotoba wasm` / safe Kotoba turns those semantics into executable, confined
  Wasm components; `kotoba-clj` currently provides the bootstrap compiler and
  safe gates.
- `aiueos` runs the resulting components as an OS-level graph, brokering
  capabilities, lifecycle, scheduling, and audit.

The security boundary is Wasm plus an explicit capability broker, not generated
JavaScript. JS/Node/browser code may host components, but it must bind only
policy-derived imports. Raw `fetch`, filesystem, DOM, environment, `eval`, or
unrestricted message channels are not component capabilities. DID/CACAO is the
external identity and delegation envelope; aiueos normalizes it into typed
Kotoba grants, intersects those grants with local policy, component manifest,
surface policy, and runtime limits, and materializes only the effective
capability set as Wasm imports plus per-host-call gates.

Content addresses bind "what" to "who may do what": authority targets exact
`wasm-sha256` / manifest CID / source CID instead of only mutable component
names; graphs, models, policies, grants, inputs, and outputs use CIDs when exact
bytes define semantics; run receipts form a hash-linked audit DAG; revocation
remains a separate policy layer because immutable CIDs identify bytes, not
current trust.

In this split, "Rust-independent Kotoba" means moving the authoritative
language/admission/policy semantics out of Rust and into confined safe Kotoba
components. It does not mean removing the bootstrap substrate first. Rust is
still the reader/parser bootstrap, Wasm emitter, host runtime integration, and
parity oracle until the corresponding safe Kotoba slices are precise enough to
replace those roles.

The next migration units should be EDN-shaped contracts first, Rust fallback
second:

- evidence/profile maps are EDN canonical data, with JSON retained only for
  external CI/store-tool interoperability;
- shell/provider/surface policy projections should move from Rust-only JSON
  builders to safe Kotoba programs that emit EDN maps and are checked against the
  Rust bootstrap output;
- admission/policy/type/effect slices graduate only when the safe Kotoba
  component is deterministic, wasm-confined, ABI-versioned, and covered by a
  Rust parity oracle test.

The first target is intentionally narrow: classify safe Kotoba host-call builtins
into their effect and capability classes. That is a seed of the Rust
`effects.rs` / `policy.rs` analyzer, written in the language it helps compile.

Current seed:

- `safe_analyzer.kotoba` — accepts CBOR `{"op": "...", "target": "..."}` and
  returns CBOR `{"effect": "...", "cap": "...", "target": "...", "known": ...}`.
  It also accepts CBOR `{"calls": [["op", "target"], ...]}` and returns the
  unique `effects`, `caps`, and resource `targets` it inferred. The next input
  shape is CBOR `{"forms": [[...], ...]}`: a simple s-expression/AST form
  stream where the analyzer recursively walks nested forms such as `do`, `let`,
  `if`, and host-call builtins. String literals are encoded as CBOR text, while
  variables are encoded as `{"var": "name"}` so dynamic resource targets can be
  distinguished from literal resource ids. Inert forms (`quote`, `var`, and
  `comment`) are not descended into, matching Rust's analyzer contract that
  quoted/commented data performs no effects and needs no grants. It also accepts
  parser-owned AST facts under function `body`, for example
  `{"tag": "builtin", "op": "kqe-assert!", "args": [...]}`, so the Kotoba
  analyzer can walk AST-shaped data without relying only on the older lowered
  form stream. It also accepts CBOR
  `{"program": [{"name": "...", "forms": [...], "body": [...]}, ...], "entry": "run"}` and
  propagates effects/caps/targets across user function calls reachable from the
  entry function. If `entry` is omitted, it returns a `functions` array with the
  transitive summary for every function, matching the shape needed to compare
  against Rust `infer_effects`. With `{"check": "effects"}`, function maps may
  include `{"declared": ["graph-write", ...]}` and the analyzer returns `ok`
  plus `violations`, catching under-declared transitive effects and unknown
  effect names. With `{"check": "policy"}`, the top-level `policy` map grants
  class-level capabilities (`graph-read`, `graph-write`, `infer`, `auth`) and
  per-resource allowlists. The analyzer returns `ok`, `used`, `granted`,
  missing-capability `denials`, and per-resource `target-denials`.
  With `{"check": "minimal-policy"}`, it synthesizes the least policy skeleton
  for the covered literal-resource surface: `graph-read`, `graph-write`,
  `infer`, and `auth`. With `{"check": "unused-grants"}`, it reports policy
  over-grants as machine-readable entries such as `graph-write:graphB`,
  `infer:*`, and `auth`. With `{"check": "admission"}`, it returns both
  `{"effects": ...}` and `{"policy": ...}` in one analyzer run, which is the
  path used by selfhost-backed compilation.
- `shell_evidence_profile.edn` — declares the safe Kotoba-owned shell evidence
  profile projection seed. `kotoba-shell` embeds it in generated profile
  metadata as `selfhostProjection` and checks that Rust bootstrap output still
  exposes the required command surface.
- `shell_evidence_profile.kotoba` — executable safe Kotoba oracle for the same
  profile seed. Release export writes it as
  `kototama-shell-evidence-profile.component.wasm` with EDN/JSON manifests.
  `kotoba shell selfhost-profile-check --profile-oracle-manifest
  <release-dir>/kototama-shell-evidence-profile.edn` executes that shipped
  Kototama artifact and runs the profile/command/evidence count exports against
  the EDN seed before accepting the generated profile, so this contract is no
  longer only a Rust EDN parser check or a check-time bootstrap compile. It also
  exposes profile, command, and evidence-stem digests so generated shell profile
  structure is tied to Kotoba-owned names and order, not only counts. Release
  evidence and `evidence-check` require the bundled oracle marker, component
  source marker, component sha marker, and those digests before accepting
  `selfhost-profile-ready-evidence`. The same seed now requires
  `kototamaWasmCheck` (legacy evidence key), which proves the bundled safe
  Kotoba analyzer compiles and runs as a confined Wasm Component before shell
  release promotion. Release export also writes the component bytes under the
  legacy artifact name `kototama-selfhost-analyzer.component.wasm` with an EDN
  manifest, and CLI release evidence requires that manifest, so promotion
  validates the shipped safe Kotoba artifact, not only a fresh bootstrap compile.
- `provider_surface_policy.kotoba` — executable safe Kotoba oracle for the
  shell provider/surface policy projection. `kotoba shell
  provider-contract-check` compiles it to Wasm and checks the provider universe
  derived from `aiueos_provider_catalog.edn` against the oracle's provider
  family, command, portable command, and status-class counts before accepting
  provider contract evidence.
- `aiueos_provider_catalog.edn` — EDN source of truth for the aiueos shell
  provider catalog. Rust now reads this seed and filters it by target
  capabilities instead of constructing the provider catalog from hard-coded
  provider branches. Release export writes the canonical EDN and an interop JSON
  projection beside `aiueos-shell-surface.*`.
  The oracle also exposes per-provider scores encoding command count, portable
  command count, and status code plus a catalog digest covering provider order,
  family id, capability, status, and command sequence for ledger, filesystem,
  notification, clipboard, HTTP, keychain, contacts, and calendar providers.
  This moves the first provider/surface projection invariants out of Rust-only
  JSON construction.
  Release export writes the same oracle as
  `kototama-provider-surface-policy.component.wasm` with EDN/JSON manifests, and
  `provider-contract-check --provider-oracle-manifest` can execute that shipped
  kototama artifact instead of compiling the oracle at check time. CLI release
  evidence for provider contract, app surface, and app surface parity now
  requires `--provider-oracle-manifest`; release `evidence-check` requires the
  resulting evidence to prove that bundled oracle path, not only a fresh compile.
  App safe components are exported the same way under `kototama/components/`
  with `kototama-app-components.edn`, including `admissionGate:
  selfhost/kotoba` and the analyzer ABI, giving release promotion
  byte-level evidence for the safe Kotoba application Wasm artifacts and
  the selfhost gate that admitted them. The manifest also carries a component
  contract digest across component ids, artifacts, source/policy/artifact hashes,
  exports, imports, and byte sizes. The corresponding readiness evidence
  repeats those values as structured report/component fields rather than only
  free-form check strings, and shell `evidence-check` requires those fields
  before accepting `kototama-app-components-ready-evidence` for promotion.
  `sourceSha256` is recorded per component and checked against the current
  source file, binding each shipped Wasm artifact back to the Kotoba source body
  that was admitted. The app component manifest also records
  `analyzerComponentSha256` and checks it against the bundled
  `kototama-selfhost-analyzer.component.wasm`, tying application artifacts to
  the selfhost analyzer component shipped in the same release. Component
  `policySha256` is regenerated from the current source by the selfhost analyzer
  and verified as the least policy, so Rust-side plan metadata cannot silently
  substitute a broader or stale policy. The checker also recompiles the source
  with that selfhost policy and compares the Wasm sha256 to the shipped artifact
  to reject forged or stale bytes even when manifest hashes were updated.
  Supervisor dry-runs can also take that manifest with
  `--kototama-app-components`, so runtime evidence executes the shipped
  safe Kotoba artifact instead of recompiling source during the release check.
  CLI `supervisor-check --run --evidence` requires that manifest; source-compile
  dry-runs remain a development path only.
  Adapter-supervisor release evidence requires that dry-run report to identify a
  legacy `kototama artifact` source marker plus the same selfhost admission
  gate, analyzer ABI, analyzer component sha, artifact sha, source sha, and
  policy sha. Shell `evidence-check` applies the same requirement when
  `live-adapter-supervisor-evidence` is required directly by a CI or release
  profile, preserving the source -> policy -> Wasm chain through runtime
  evidence.
- `app_components_contract.kotoba` — executable safe Kotoba oracle for the
  shipped safe app component manifest contract. Release export writes it as
  `kototama-app-components-contract.component.wasm` with EDN/JSON manifests.
  `kotoba shell kototama-app-components-check <release-dir>/kototama-app-components.edn`
  requires the sibling `kototama-app-components-contract.edn`, executes that
  shipped oracle, and checks the manifest schema/admission/analyzer ABI digests,
  digest modulus, and required top-level/component field counts before accepting
  `kototama-app-components-ready-evidence`. This moves another release-critical
  app component invariant out of Rust-only constants while Rust continues to
  verify source hashes, minimal policy, reproducible Wasm, and artifact bytes.
- `plugin_contract.kotoba` — executable safe Kotoba oracle for shell plugin
  registry, plugin SDK, and plugin loader release contracts. Release export
  writes it as `kototama-plugin-contract.component.wasm` with EDN/JSON
  manifests. Plugin registry/SDK/load checks execute the shipped oracle when it
  is present beside the release manifests, and release `evidence-check` requires
  those bundled oracle markers before accepting plugin promotion evidence. This
  moves schema, ABI, permission-mode, loader-mode, audit-import, and required
  field-count invariants out of Rust-only promotion checks.
- `compatibility_contract.kotoba` — executable safe Kotoba oracle for the shell
  schema/ABI compatibility policy. Release export writes it as
  `kototama-compatibility-contract.component.wasm` with EDN/JSON manifests.
  `kotoba shell compatibility-check` executes the shipped oracle when present
  beside `kotoba-shell-compatibility.json`, and release `evidence-check`
  requires the bundled oracle markers before accepting
  `compatibility-ready-evidence`. This moves policy version, stability, ABI,
  bridge/event, schema-compatibility, notice-period, boolean-policy, and known
  schema-count invariants out of Rust-only promotion checks.
- `updater_contract.kotoba`, `updater_channel_contract.kotoba`,
  `updater_ui_contract.kotoba`, and `updater_lifecycle_contract.kotoba` —
  executable safe Kotoba oracles for the shell updater manifest, channel
  policy, updater UI contract, and bundle/install/publication lifecycle gates.
  Release export
  writes them as `kototama-updater-contract.component.wasm`,
  `kototama-updater-channel-contract.component.wasm`, and
  `kototama-updater-ui-contract.component.wasm`, plus
  `kototama-updater-lifecycle-contract.component.wasm`, with EDN/JSON
  manifests.
  `kotoba shell updater-check` executes the shipped oracle when present beside
  `kotoba-shell-updater-manifest.json`; `updater-channel-check` and
  `updater-ui-check` use the same shipped oracle beside their release manifests.
  Release `evidence-check` requires the bundled oracle markers before accepting
  updater, updater-channel, updater-UI, updater-bundle, updater-install, or
  updater-publication readiness evidence. This moves updater schema, version,
  channel, channel-policy, bridge/audit/UI state/action/event, required contract
  paths, install verification, publication probing, lifecycle evidence schemas,
  and artifact field-count invariants out of Rust-only promotion checks.
- `signing_contract.kotoba` and `submission_contract.kotoba` — executable safe
  Kotoba oracles for store signing and submission readiness. Release export
  writes them as `kototama-signing-contract.component.wasm` and
  `kototama-submission-contract.component.wasm` with EDN/JSON manifests.
  `kotoba shell signing-check` and `submission-check` execute the shipped
  oracles when present beside the release artifacts, and release
  `evidence-check` requires bundled oracle markers before accepting
  signing/submission readiness evidence. This moves store schema, helper script,
  credential-env count, artifact/file count, and signing gate-count invariants
  out of Rust-only promotion checks.
- `release_contract.kotoba` and `release_target_contract.kotoba` —
  executable safe Kotoba oracles for release metadata readiness. Release export
  writes them as `kototama-release-contract.component.wasm` and
  `kototama-release-target-contract.component.wasm` with EDN/JSON manifests.
  `kotoba shell release-check` executes the shipped oracle when present beside
  the release metadata, and release `evidence-check` requires bundled oracle
  markers before accepting `release-metadata-ready-evidence`. This moves release
  schema, permissions schema, evidence profile schema, common release file
  count, target file count, script count, and credential-env count invariants
  out of Rust-only promotion checks.
- Rust bridge inputs and all analyzer outputs carry
  `{"abi": "kotoba.selfhost.safe-analyzer.v1"}`. The analyzer rejects inputs
  without this marker, and the Rust bridge rejects outputs without it before
  decoding typed results. This makes the selfhost CBOR boundary an explicit
  versioned contract instead of an implicit test fixture.

The test suite fixes three bootstrap properties:

- the analyzer compiles as safe Kotoba under `Policy::deny_all()`;
- the emitted wasm has no `kotoba:kais/*` host capability imports;
- the Rust bridge sends, the analyzer requires and emits, the versioned CBOR ABI
  marker;
- crate callers can invoke the bundled analyzer through `kotoba_clj::selfhost`
  without copying the test-only CBOR lowering helpers;
- results from `calls`, hand-written `forms`, forms derived from
  `ast::parse_program`, and body-only AST facts match Rust `infer_effects` /
  `minimal_policy` facts for the covered host-call surface;
- function-call propagation over `program` input matches Rust transitive
  `infer_effects` for the covered host-call surface;
- parser-owned AST calls are recorded as `name + arity`, so transitive
  effect/capability propagation does not mix multi-arity overloads with the
  same source name;
- all-function summary output over `program` input matches Rust transitive
  `infer_effects` for every parsed function in the test program;
- cyclic call graphs / mutual recursion converge to the same transitive effect
  sets as Rust `infer_effects` for the covered host-call surface;
- executable-body safe-subset checking rejects covered forbidden forms such as
  `eval` and raw-memory primitives (`alloc`, `load64`, `store64!`, `load32`,
  `store32!`) from parser-owned AST facts, plus the covered Rust subset
  body-level denylist for read-as-code, runtime namespace loading, dynamic var
  mutation, shared mutable references, ambient I/O, nondeterminism, ambient
  concurrency, and reflection/host-object construction. Inert `comment` /
  `quote` / `var` contents remain ignored. The Rust bridge also sends
  source-level `source-subset` facts for top-level forms; the analyzer rejects
  `ns` loading / host interop clauses such as `:require`, `:use`, and
  `:import`, top-level `defmacro`, runtime loading forms, and host constructor /
  member syntax before Rust's full subset fallback. If Rust AST lowering fails,
  `check_subset` and the selfhost-backed compile path can still send these
  source facts as a subset-only analyzer request, so forbidden source forms are
  rejected by safe Kotoba before the Rust lowering fallback. The source-level
  subset walker records non-executable declaration heads such as `defmacro` but
  does not descend into their bodies; those bodies are not runtime code. Rust's
  full subset gate still covers source constructs that are not represented or
  normalized in analyzer facts;
- local type checking rejects covered body-level mismatches such as string
  literals passed to numeric/bitwise/comparison/math/conversion builtins and
  numeric literals passed to string-first builtins (`str-len`, `byte-at`), plus
  direct literal mismatches against byte-buffer builtins (`byte-append!`,
  `bytes-len`, `bytes-finish`) and string-handle host imports (`kqe-*`,
  `llm-infer`, `has-capability?`). It also rejects direct value-dependent literal traps:
  `byte-at` out-of-bounds / negative index, negative `bytes-alloc`, and
  division/mod/rem by literal zero from parser-owned AST facts. The Rust bridge
  also sends source-level `source-types` facts with small literal kind codes, so
  covered direct literal kind mismatches can be rejected by safe Kotoba even when
  Rust AST lowering fails. The source-level type walker skips inert forms and
  non-executable declarations such as `defmacro`; those constructs are handled
  by the subset gate instead. Value-dependent literal checks remain AST-owned;
- source-only tooling fallback also carries `source-effects` facts for direct
  executable host calls in `defn` bodies. This lets the safe Kotoba analyzer
  synthesize minimal policy, check policy/admission, and lint over-grants for
  direct calls such as `(kqe-assert! "graphB" ...)` even when a separate source
  form prevents Rust AST lowering. Namespaced direct calls such as
  `(kotoba/kqe-assert! "graphB" ...)` are normalized to the same builtin
  operation for source-only policy tooling. Interprocedural propagation,
  dynamic targets, and declaration soundness remain parser-owned AST facts;
  division/mod/rem by literal zero. The Rust bridge preserves these builtin
  names in parser-owned AST facts instead of collapsing them to `pure-builtin`.
  The bridge also sends a parser-owned `type-body` AST copy; the analyzer uses
  it for a type-only pass that carries `Str`/`Num`/`Bytes` facts through direct
  `let`/`loop` locals, `do` finals, and same-type `if` joins before checking
  builtin arguments. The same pass records cross-function call-argument rows for local
  `Str` facts, matching Rust's boundary rule that `Num`/`Bytes` local facts do
  not cross a function-call boundary.
  It also checks concrete `loop`/`recur` rebinding: if a loop binding's initial
  fact and the corresponding `recur` argument fact are both concrete and their
  types differ, the analyzer rejects the body as `recur`. Unknown values remain
  permissive.
  The type walker keeps the normal recursive effect/capability walk for nested
  arguments, so moving this slice does not hide host calls inside arithmetic
  expressions.
  It also derives a first cross-function parameter requirement slice: when a
  callee uses a non-shadowed parameter directly in a numeric, math/conversion,
  string, byte-buffer, or string-handle host-import position, a direct literal
  with the opposite type at the call site is rejected by the safe Kotoba analyzer.
  Call-site parameter checks resolve multi-arity functions by `name + arity`,
  so an arity-2 overload is not rejected using the arity-1 signature for the
  same source name.
  The bridge also sends a parser-owned `ret` AST fact for the function's final
  expression and a parser-owned `ret-call-ast` duplicate for the same expression;
  the analyzer derives a first `Str` return slice and direct tail-call return
  relation from those facts.
  String literals, `bytes-finish`, and `llm-infer` are treated as genuine `Str`
  returns, and an `if` whose `then`/`else` branches both derive direct `Str`
  joins to `Str`; a direct `do` returns the kind of its final expression, and
  direct `let`/`loop` carry sequential direct-`Str` locals through their final
  body expressions. Direct call returns, including `do`/`let`/`loop` final tail calls,
  recursively resolve to `Str` when the callee return resolves to `Str`; an
  `if` whose final `then`/`else` expressions are tail calls joins to `Str` only
  when both callees resolve to the same concrete `Str`. Cycles, unknown callees,
  mixed branch returns, and non-`Str` shadowed locals collapse to Unknown at the
  function boundary. A direct `Str` result is rejected when it is passed into a
  numeric/math/byte-buffer/host-import position. Direct call-return checks
  resolve multi-arity callees by `name + arity`, so `(f 1 2)` is typed against
  the arity-2 return signature rather than the first `f` overload.
  Rust still owns typed-HIR inference and non-literal/runtime-dependent type
  checks, including richer call-site flows;
- effect declaration checking over `program` input rejects transitive
  under-declaration and unknown declared effect names in the same cases where
  Rust `compile_safe_kotoba` returns `CljError::Effect`;
- class-level capability policy checking over `program` input rejects and
  accepts the same covered capability classes as Rust `compile_safe_kotoba` /
  `CljError::Policy`;
- per-resource target allowlist checking rejects ungranted graph/model targets
  and accepts wildcard (`"*"`) grants in the same covered cases as Rust
  `Policy::check_resource_targets`;
- minimal policy synthesis over `program` input matches Rust `minimal_policy`
  for pure programs and literal graph/model/auth resources;
- unused grant linting over `program` input matches Rust `unused_grants` for
  exact-fit policies, unused whole classes, unused specific resource ids, and
  unused auth grants on the covered surface;
- dynamic resource targets widen minimal policy to wildcard (`"*"`) grants,
  fall back to class-level policy checking, and suppress per-cid unused-grant
  claims in the same covered cases as Rust;
- graph-scope-free reads such as `kqe-query` widen minimal graph-read policy to
  wildcard (`"*"`) grants, require the graph-read class without producing
  target-denials, and suppress per-cid unused-grant claims in the same covered
  cases as Rust;
- inert forms (`quote`, `var`, `comment`) are ignored for effect inference and
  policy synthesis, matching Rust `infer_effects` / `minimal_policy` for the
  covered quoted/commented host-call cases.

This is not yet a full reader/analyzer. It is a verified bootstrap foothold:
Kotoba code can run as a WASM Component and perform compiler-admission decisions
over structured bytes that are now close to the existing parser/lowering path,
including a small function-summary graph.

Current Rust bridge:

- `kotoba_clj::selfhost::analyzer_component()` compiles the bundled analyzer to
  a Wasm Component;
- `kotoba_clj::selfhost::Analyzer` keeps a compiled analyzer component and
  reuses it across repeated admission queries. `Analyzer::new()` compiles the
  bundled source once, while `Analyzer::from_component(bytes)` lets callers use
  their own component cache. The same handle also exposes the selfhost-backed
  `compile_safe_kotoba*` methods (with legacy `compile_safe_clj*` aliases),
  `compile_safe_file*`, and `minimal_policy_file*` methods
  so a runtime or tool can compile multiple cells without rebuilding the
  analyzer component for each admission gate. The free functions below remain
  convenience wrappers that compile a fresh analyzer per call;
- Rust lowers source into a versioned `AnalyzerRequest` before CBOR encoding.
  That request is the current Rust-owned reader/AST boundary: it carries the ABI
  marker, function parameter names, AST body facts, declared effect rows carried
  by parser-owned `Function` facts from source `{:effects ...}` metadata,
  optional check mode, and optional policy map in one place. Runtime/tooling
  callers can build and serialize this request explicitly, then run it through
  `Analyzer::run_request_value`. The older `forms` shape remains accepted as a
  compatibility/test input, but the bridge's default source path now feeds
  `body` AST facts to the Kotoba analyzer. Rust no longer injects legacy
  `param-targets` / `call-args` facts on that source-backed path; the
  safe Kotoba analyzer derives parameter-as-resource-target and direct-call
  literal-argument facts from `params` + `body` itself. This is an important
  ownership move: policy precision for one-call-layer resource pass-through is
  now analyzer-owned, not bridge-owned. `AnalyzerRequest::from_source` keeps
  the default Kotoba reader target, while
  `AnalyzerRequest::from_source_with_reader_target` lets runtime/tooling callers
  build the same request from `clj` / `cljs` reader-conditional source;
- `kotoba_clj::selfhost::analyze_program_all(src)` parses source with the Rust
  reader/parser, serializes function bodies as AST facts for the analyzer's CBOR
  input, runs the safe Kotoba analyzer, and returns typed `FunctionSummary` rows;
- `kotoba_clj::selfhost::infer_effects(src)` returns a Rust-shaped
  `BTreeMap<String, BTreeSet<String>>` backed by the safe Kotoba analyzer;
- `kotoba_clj::selfhost::minimal_policy(src)` returns a `Policy` synthesized by
  the safe Kotoba analyzer. Source-backed requests let the analyzer use
  parameter-as-resource-target and direct-call literal-argument facts when
  synthesizing least-privilege policy, so `(writer "graphA")` where `writer`
  uses `[g]` as `(kqe-assert! g ...)` now yields `:graph-write ["graphA"]`
  instead of widening to `["*"]`. A dynamic pass-through such as `(writer g)`
  still widens to wildcard. Multi-arity resource pass-through is resolved by
  `name + arity`, so an overload that does not target a resource does not widen
  or deny calls to a different arity that does. On Rust AST lowering failure,
  source-only direct host-call facts still let minimal policy pin direct literal
  resource targets;
- `kotoba_clj::selfhost::check_effect_declarations(src)` returns typed
  `EffectCheck` / `EffectViolation` rows for declared `{:effects ...}` soundness;
- `kotoba_clj::selfhost::check_policy(src, policy)` returns typed `PolicyCheck`
  rows for class-level and per-resource policy admission. Source-backed
  requests now let the safe Kotoba analyzer derive direct-call literal argument
  facts and parameter-as-resource-target facts from `params` + `body`, then
  reject one-call-layer literal resource ids passed through function parameters,
  e.g. `(helper "graphB")` where `helper` uses `[g]` as `(kqe-assert! g ...)`.
  On Rust AST lowering failure, source-only direct host-call facts still enforce
  class-level and literal resource-target policy for direct calls;
- `kotoba_clj::selfhost::check_admission(src, policy)` returns both
  `EffectCheck` and `PolicyCheck` from a single safe Kotoba analyzer execution;
- `kotoba_clj::selfhost::check_compile_gate(src, policy)` returns the
  selfhost-backed compile gate from one analyzer execution: `SubsetCheck`,
  `TypeCheck`, `EffectCheck`, and `PolicyCheck`. This is the path used by the
  selfhost-backed compiler for covered source. If Rust AST lowering fails,
  `check_compile_gate` falls back to a source-only analyzer request so
  source-level subset, literal-kind type, and direct host-call policy denials
  are still returned instead of losing the safe Kotoba decision to a Rust
  `Lower` error;
- `kotoba_clj::selfhost::check_subset(src)` returns the analyzer's
  executable-body plus source-level subset decision. The selfhost-backed compile
  path invokes this slice before Rust's full subset fallback, so body-level
  forbidden calls, `ns` loading clauses, top-level macro definitions, runtime
  loading forms, and host constructor/member syntax are now rejected by
  safe Kotoba while Rust still handles source constructs that are outside the
  analyzer facts;
- `kotoba_clj::selfhost::check_types(src)` returns the analyzer's first
  parser-owned AST plus source-level literal kind decision. The selfhost-backed
  compile path invokes this slice before Rust's full `ty.rs` / `ty_infer.rs`
  fallback, so direct body-level literal kind/value denials, direct local
  `let`/`loop` flow denials, concrete `loop`/`recur` type-change denials, and
  the covered direct literal/local-`Str` call-argument denials are rejected by
  safe Kotoba. If Rust AST lowering fails, `check_types` and the compile path can
  still send source-level literal kind facts for executable forms, while wider
  type inference, non-executable declaration bodies, value-dependent source
  checks, and dynamic checks remain Rust-owned or subset-owned;
- `kotoba_clj::selfhost::unused_grant_ids(src, policy)` exposes the analyzer's
  compact machine-readable over-grant ids, while
  `kotoba_clj::selfhost::unused_grants(src, policy)` returns the same
  human-readable messages as the Rust `unused_grants` helper, including
  over-grants detected through one-call-layer literal resource pass-through and,
  on Rust AST lowering failure, direct source-only host-call facts;
- `kotoba_clj::selfhost::compile_safe_kotoba(src, policy)` and
  `compile_safe_kotoba_with_prelude(src, policy)` are real compile entry points
  (`compile_safe_clj*` remains as a compatibility alias).
  Their `*_with_reader_target` variants keep `kotoba` / `clj` / `cljs`
  reader-conditional selection on the selfhost-backed compile path. Rust still
  performs reader, full subset/type fallback, typed-HIR inference, and codegen
  work, but the covered subset/type/effect-soundness/capability-resource
  admission decisions now come from a single `compile-gate` analyzer request
  before Wasm emission. On Rust AST lowering failure, that request degrades to
  source-only subset/type/direct-effect facts before Rust's full fallback gates
  run;
- the public `kotoba_clj::infer_effects*`, `minimal_policy*`,
  `unused_grants*`, `compile_safe_kotoba*`, legacy `compile_safe_clj*`, and
  `compile_safe_file*` APIs now use
  the bundled selfhost analyzer by default when the `component` feature is
  enabled. The Rust-only implementations remain as explicit bootstrap/fallback
  surfaces for parity oracles, building the analyzer itself, and builds without
  component support;
- file graph entry points mirror the Rust safe API:
  `compile_safe_file*`, `compile_safe_file_with_prelude*`, and
  `minimal_policy_file*` load `.kotoba` / `.clj` / `.cljc` / `.cljs` sources
  through the same reader-target/source-path resolver and keep that target on
  the subsequent selfhost-backed compile/admission path;
- CLI dogfood: `kotoba wasm safe-build <cell> --policy <policy.edn>` uses those
  selfhost-backed admission gates by default and reports
  `admission gate: selfhost/kotoba`. Within one `safe-build` command, the
  same `Analyzer` handle is reused for compile admission, over-grant linting,
  and effect reporting. `kotoba wasm safe-policy <cell>` synthesizes policy
  through the same analyzer component path. `--selfhost-gate` is retained as a
  compatibility alias. Both commands accept `--reader-target kotoba|clj|cljs`
  and repeated `-S` / `--source-path` options before invoking the shared file
  graph loader. `kotoba wasm
  selfhost-inspect <cell> --policy <policy.edn> --request-hex --json` exposes
  the same boundary without compiling: it prints the analyzer ABI, request
  function count, optional request CBOR hex, selfhost per-function summaries,
  type-gate result, and optional effect+policy admission results as either
  human-readable lines or structured JSON.

Verification:

```bash
cargo test -p kotoba-clj --features component --test selfhost
cargo test -p kotoba-clj --features cli --test kotoba_file selfhost
```

Next boundary:

- widen the AST fact surface beyond the covered effect/admission subset and,
  later, move reader/analyzer code itself into Kotoba;
- keep every widened slice paired against the Rust implementation until the
  safe Kotoba path is precise enough to become authoritative.
