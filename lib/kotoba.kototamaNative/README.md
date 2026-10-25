# kototama-native

Kototama's **native host** — loads and runs artifacts that
[`amu`](https://github.com/kotoba-lang/amu) wove through
[`kotoba-native`](https://github.com/kotoba-lang/kotoba-native), under a
capability gate.

GitHub id `1312673399`. Previously `tender-native`; that URL still redirects.
The product is [`kototama`](https://github.com/kotoba-lang/kototama) (言霊).
Namespace: `kototama.native.executor`. See root ADR-2608139980.

**Tier**: `T3`  **Role**: `host` of kototama

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside. Do not merge this tree back into kototama core.

## Owns

- `kototama.native.executor (native artifact execution host)`
- The selected export's typed host boundary. `:bool` parameters accept host
  booleans and lower to native 0/1 words; `:bool` results return host booleans.
  `:i64` remains distinct and accepts integers only.
- `:string` parameters are canonical UTF-8 copied into the bounded native
  arena before guest entry. Selected `:string` results are independently
  validated and copied from that arena into the structured report before the
  process exits; pair handles never escape as host strings.
- Scalar `:record` parameters and selected results use the published aggregate
  ABI's declaration-order pair chain. The host accepts exactly the declared
  keyword keys, supports only unique `:i64`/`:bool` fields (1–128), and the
  loader requires the exact chain length and zero terminator before copying
  field words into evidence. Pair handles never escape to callers.
- `:option-i64` and `:result-i64` use the same canonical tagged vectors as the
  reference and restricted-ESM hosts (`[false]`/`[true value]` and
  `[ok? value]`). The loader materializes and inspects the established
  `pair(tag,payload)` representation; tags must be boolean words and option
  none must carry payload zero.
- Scalar variants keep the canonical KIR host value
  `[type case-keyword payload]`. Qualified descriptors with 1--32 unique cases
  and only `:i64`/`:bool` payloads lower to a bounded token containing case
  count, declaration ordinal, payload kind, and word. Results are copied from
  the pair arena as ordinal/word evidence, then reconstructed only after the
  sealed descriptor validates the ordinal and boolean word.

- The session boundary. `prepare` verifies a signed artifact once and stages
  the measured loader and its code; `invoke` runs one export against that
  staging; `close!` removes it. `execute` is those three composed, and stays
  the right call for a host that runs one entry once.

  What a session amortizes is time-invariant: the Ed25519 signature, the
  `verify-artifact!` structural check, the loader measurement, and the
  target-profile agreement. What it does not amortize is everything that can
  change between two calls -- expiry, not-before, revoked signers, revoked
  artifacts, and capability admission against that call's policy all run per
  `invoke`. Measured on an M4, verification of a 19k-word module costs
  1.7--3.6 s while the loader process costs about 2 ms over a bare spawn, so
  the split is the difference between native being an execution path and
  native being a conformance target.

- Locating the reviewed loader source. `measure-runtime` takes
  `:loader-source-dir`, falls back to `KOTOBA_LOADER_SOURCE_DIR`, and only
  then to `tools/` under the working directory. Naming a directory cannot
  substitute a different loader: the source digest must still be the reviewed
  one for the target profile.

## Does not own

- compile
- decide grants
- require Rust in the core path
- expose nested aggregate, vector, parametric option/result, non-scalar
  variant, or document
  handles as host
  values. Those boundaries remain explicitly rejected until each has a bounded
  copy/validation protocol.

## Depends on

- `kotoba-lang/osaho` (formerly `kotoba-kir`)
- `kotoba-lang/artifact`
- `kotoba-lang/kotoba-verifier`
- `kotoba-lang/error`, `kotoba-lang/bytes`, `kotoba-lang/text`, `kotoba-lang/test`

## Hosts

`kototama.native.executor` is one namespace with a `:clj` and a `:cljs`
branch at every host-specific site (process spawning, digests, the toolchain
PATH walk, temp directories). Since 2026-09-11 (amu ADR 0347 / 0348) the
host that ships is **Node**, through amu's nbb route: `amu run` and
`amu measure-runtime` call `execute` / `measure-runtime` here. The `:clj`
branch is the original and stays as the reference text; nothing in this
workspace runs it any more.

Two things the Node host does that the JVM host did not:

- **Integers may be bigint.** An argument or a report field read through the
  kotoba reader arrives as a JavaScript bigint; a `:result`, `:result-word`
  or `:result-words` entry past 2^53 is re-read from the report TEXT as
  bigint so that the value that leaves the loader is the value the caller
  gets (`examples/i64-beyond-double.kotoba` in amu is the check).
- **Timeouts kill the direct child, not a tree.** `spawnSync` has no process
  tree; the loader spawns nothing, so on this executor the two are the same
  process. A killed child reports `128 + signal`.

## Test

The Node suite (68 assertions on the decisions: report validation, argument
lowering, result boxing, the Make dependency parser, bigint handling) runs on
the nbb engine with the executor's closure on the classpath. amu's lock is
that closure already resolved:

```bash
cd <amu>
node bin/kbb --backend sci \
  --classpath "<kototama-native>/src:<kototama-native>/test:$(node bin/kbb --backend sci --classpath src scripts/print-classpath.cljk . | paste -sd:)" \
  <kototama-native>/test/nbb/executor_test.cljk
```

The executed evidence -- a loader measured twice for reproducibility, a
signed artifact run, a receipt verified -- is amu's `scripts/conformance.cljk`
(`attested-run`), which drives this executor through `amu measure-runtime`
and `amu run` on the host ISA.

`test/tender/native_test.cljk` is the JVM suite. `kbb -M:test` reports
`Ran 0 tests` since the `.cljk` rename (the JVM runner does not load that
extension); it is kept as the origin of the fixtures the Node suite mirrors.

## Scoped native lease transport

The explicit POSIX Node v2 path forwards every unary i64 call to Kototama host
lease reservation before a provider effect. The native host owns bounded IO and
process supervision; Kototama owns authorization and its durable ledger.
See [transport contract](docs/native-lease-transport.md). This is bootstrap host
evidence; Q9/selfhost, Windows and aggregate transport remain separate.
