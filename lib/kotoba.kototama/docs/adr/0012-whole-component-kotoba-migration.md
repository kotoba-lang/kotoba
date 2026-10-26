# ADR 0012: migrate complete components through Kotoba CLI and Amu

- Status: Accepted
- Date: 2026-08-30
- Supersedes: decision-only `.cljk` extraction as a Kototama migration unit
- Canonical Q9 decision: `kotoba-lang/kotoba-lang` `docs/adr/ADR-q9-whole-component-build-migration.md`
- Machine record: `qualification/q9-whole-component-build.edn`

## Context

The proposed first step extracted only the expiry/scope/present-only decision
from `lib/kototama/leash.cljk`, and only mood/cadence/prior-shortcut decisions
from `clj/src/kototama/unspsc/life.cljk`. That would have proved that Amu can
compile a few pure functions, but it would not have migrated either component.
The Clojure namespace would still own its API, data model, folds and calls, and
the caller would have to project business inputs into a second implementation.

That split is verbose for Clojure/CLJS callers and leaves two semantic owners.
It also hides the important language question: whether Kotoba can express the
component's complete values, control flow, effects, imports and resource
bounds.

## Decision

### The migration unit is the complete component

A migrated `.cljc` component is replaced by one `.cljk` entry with its closed
transitive Kotoba source set. Every public var and function is implemented, or
is removed by a separate versioned API decision. Private helpers needed by
that surface move with it.

Accordingly:

- `kototama.leash` means `leash`, `valid?`, `write-author` and `revoked?` as
  one component, not an extracted validity predicate;
- `kototama.unspsc.life` means its public mood data, event vocabulary and
  deltas, event fold, labels, cadence, validation, consensus and shortcut as
  one component, not three extracted decisions.

`.cljk` denotes CLJ-shaped Kotoba source. It does not mean code loaded by the
JVM, and it does not authorize a mechanical extension rename.

### Native behavior is a declared provider boundary

Clocks, storage, sockets, randomness, cryptography and host handles remain
native mechanisms when required. They cross the component boundary only as
declared imports guarded by capabilities. The Kotoba component still owns the
complete orchestration and public decision surface. Ambient host fallback is
forbidden.

For the current `leash` component, the opaque CACAO/Biscuit token remains
present-only data. If later revisions require decoding or signature
verification, those mechanisms are explicit provider imports; they are not a
reason to migrate only the expiry predicate.

### Both build paths are mandatory

For every declared target, the repository records and runs:

```sh
kotoba check --safe <entry.cljk>
kotoba compile <entry.cljk> --target <target> --output <cli-artifact>
kotoba rad build --project <repository> --profile release
amu check <entry.cljk> --jvm-free
amu compile <entry.cljk> --target <target> --jvm-free --output <amu-artifact>
```

The public Kotoba path is `kotoba compile` plus the package-level
`kotoba rad build`; the direct compiler path is `amu compile`. Calling an
internal compiler namespace or a test-only KIR evaluator satisfies neither
build gate.

### The migration gate is JVM-free

The `kotoba` command is the verified native release executable. It is not a
Java launcher, `kbb -M` wrapper or development classpath. Amu executes its
nbb/Node compiler entry with `--jvm-free`; dependency-lock failure,
project-linker use or an unsupported target stops the migration instead of
falling back to Clojure/JVM.

Acceptance runs with `JAVA_HOME` unset or invalid and denies and traces
`java`, `javac`, `clojure` and `clj`. The retained `.cljc` surface is compared
under CLJS/nbb, native or Wasm. When a portable executable oracle is not
available, content-addressed golden vectors replace a live JVM oracle. JVM
observations may remain historical diagnostics but cannot be required to make
the migration pass.

The repository gate pins the first fail-closed Amu implementation as feature
commit `47feca70c7cffb59c1b86f9735e499370eb0f472`. The selected Amu release or
commit must contain it; a local branch alone does not satisfy the build gate.

For locked inputs, the two paths must report the same payload CID, definition
CIDs, exports, imports, effects and resource bounds. Wrapper provenance may
differ, but executable meaning may not.

### Full-surface parity precedes cutover

The retained `.cljc` component is the rollback oracle. Parity covers every
public export and externally visible refusal, effect, receipt and state
transition. A successful function-level test cannot authorize consumer
cutover, source deletion or deployment.

“Retained oracle” here means its content and behavior contract; it does not
require executing Clojure on the JVM during acceptance.

The historical `clj/wasm/prior_shortcut.kotoba` experiment remains compiler
evidence only. It receives no new production consumer and is eventually
absorbed into the complete `kototama.unspsc.life` component.

## Consequences

- The first migration increment is larger, but it produces one semantic owner
  instead of permanent adapters around decision fragments.
- Missing Kotoba language or Amu features become explicit blockers and feed
  the language surface plan.
- Clojure and ClojureScript consumers select one component rather than
  spelling capabilities around every extracted predicate.
- Migration build and parity gates require Node/nbb and native/Wasm tooling,
  but no JDK or Clojure CLI.
- No current consumer is cut over, no legacy source is deleted and no
  deployment is authorized by this ADR.
