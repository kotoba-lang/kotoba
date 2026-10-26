# wasm/ — kotoba-wasm port of `kototama.unspsc.life/prior-shortcut?`

`prior_shortcut.kotoba` is a narrow-slice port of
`kototama.unspsc.life/prior-shortcut?` (`../src/kototama/unspsc/life.cljc`)
into the minimal `.kotoba` language subset, compiled to a real WASM module
via `kotoba wasm emit`, and wired up as
`kototama.unspsc.prior-shortcut-kotoba/prior-shortcut?`
(`../src/kototama/unspsc/prior_shortcut_kotoba.clj`) — a genuine,
tested drop-in replacement for the original function, hosted via a real
Chicory `Instance`. The compiled `.wasm` itself lives at
`../resources/prior_shortcut.wasm` (loaded via `io/resource`, classpath-
based, so it resolves regardless of the caller's working directory) —
`.kotoba`, being source, stays here in `wasm/` alongside this README.

This is ADR-2607151500's kotoba-lang-org-internal narrow-slice port
candidate, realized. The first candidate considered
(`kototama.unspsc.capability`'s `segment-capabilities` table) turned out to
store predicate **closures as data** (keyed by UNSPSC segment) — exactly the
general first-class-function pattern ADR-2607150000's triage rejected for
`.kotoba` (T2 effect-soundness: a static effect-fixpoint analysis can't see
through an arbitrary closure argument). `prior-shortcut?` has no such
dependency: it's a genuinely pure integer/boolean decision, and — unlike
the abandoned candidate — has a real call site today
(`kototama.unspsc.organism`, line ~68).

## Why the source differs from `kototama.unspsc.life`

The `.kotoba` compiler's safe subset has no string-equality operation, so:

- The original function takes one `consensus` map and compares
  `(:dominant-status consensus)` against the string `"authorized"`. The
  port takes 4 flattened positional scalar args instead (no maps needed at
  all here), with the string comparison pushed to the **caller**: the host
  precomputes `dominant-status-authorized` (1 if
  `(= (:dominant-status consensus) "authorized")` holds, 0 otherwise)
  before writing it into the guest's linear memory. Same convention
  `cloud-itonami-isic-6492`'s `wasm/affordability.kotoba` and its governor
  port already established for turning map-shaped inputs into a host-side
  precomputation + flat scalar ABI.

## ABI — parameterized invocation

`kotoba wasm emit` rejects any `main` with parameters, so real inputs are
passed through the guest's exported linear memory instead. A host writes 4
little-endian i32 values before calling `main()`:

| offset | field                          |
|--------|--------------------------------|
| 0      | `outcome-count`                |
| 4      | `confidence-permille` (0..1000)|
| 8      | `input-match-count`            |
| 12     | `dominant-status-authorized` (flag: 0 or non-0) |

`main()` returns `1` (take the prior shortcut) or `0` (fall through to full
evaluation).

## Rebuilding

```sh
cd ../../kotoba              # sibling checkout, west-managed (orgs/kotoba-lang/kotoba)
bin/kotoba-clj wasm emit ../kototama/clj/wasm/prior_shortcut.kotoba \
  --package-lock kotoba.lock.edn \
  --output ../kototama/clj/resources/prior_shortcut.wasm --json
```

## Verification

Every oracle case in
`test/kototama/unspsc/prior_shortcut_kotoba_test.clj` is copied directly
from `kototama.unspsc.life-test`'s own `prior-consensus-parity` test
(`test/kototama/unspsc/life_test.clj`), calling
`kototama.unspsc.prior-shortcut-kotoba/prior-shortcut?` with the SAME
map-shaped `consensus` argument the original function takes — so this
test exercises the full translation (map -> flattened scalars -> WASM
call -> boolean) end to end, not just the compiled module's own ABI in
isolation, and doubles as a cross-check that the `.kotoba` port and the
in-process reference function never disagree. Hosted directly via a real
Chicory `Instance` (no host imports needed — this module calls no
capability/heap ops, only `mem-i32-at`/arithmetic/comparison), not a
separate interpreter. Chicory is kept out of `clj/deps.edn`'s main
`:deps` (test-only for now) — same isolation pattern `langchain.jvm`/
`langchain.kotobase-persist` use for optional backends, so requiring
`kototama.unspsc.life`/`.organism` never forces it on a consumer who
doesn't want the WASM-backed variant. A consumer who DOES want
`prior-shortcut-kotoba` adds Chicory to their own project.

## Follow-ups

- **Not wired into `kototama.unspsc.organism`'s actual `validate-node`
  call site.** `prior-shortcut-kotoba/prior-shortcut?` is available and
  verified as a genuine drop-in replacement, but flipping
  `organism.cljc`'s live decision gate (18,342 actors) to actually call it
  is a real production-behavior change to a shared fleet, left for an
  explicit owner decision rather than an autonomous substitution.
- No fleet/production deployment — out of scope here.
