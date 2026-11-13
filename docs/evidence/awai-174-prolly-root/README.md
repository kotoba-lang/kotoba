# AWAI-174: persisted Prolly root verification — 2026-11-13

This is a one-off local JVM reference measurement on macOS, **not** a Native
build, gate, fallback, signed basis, real authorization policy, encrypted
store, or production durability qualification. The actual Kotoba Prolly
engine and Datalog implementation used a test-owned file-per-CID store, with
injected identity encryption and a fixture blinding function. A separate JVM
restored the Prolly root and ran the join, time-travel and visibility checks.

Source inputs: Kotoba revision `05fc7c5c62ca0e44fc9d7539fe9834ec9a6b0b14`;
Prolly engine source at origin/main `4fcddfaa99bcbc78ddfe40accad0cf876a3291f4`
was byte-identical to that revision before the patch. Clojure CLI
`1.12.5.1654`; Temurin OpenJDK `21.0.1+12`. No downloaded source or external
dependency was used by the measurement.

The `.cljk` source copies were renamed `.cljc` for the oracle, with existing
same-name `.cljc` twins preferred. The attached JSON records source/copy SHA-256
and per-file `:kotoba/export` quotation adaptations; the previously recorded
`kotoba.lang.coll` oracle copy had SHA-256
`6880ecaf27a40f6385a5861d6b04ea31456c69d745964a97f513acfded86041e`.
One extra oracle-only reader correction changed `ipld/schema`'s unguarded
`(catch :default _ false)` to `(catch #?(:clj Exception :cljs :default) _ false)`;
the resulting copy SHA-256 was
`d413cdf49cde44df5d76467867ca7f501a449048a73cdcd989af8a99d654061f`.
This adaptation is a qualification limitation, not a change to the owning
schema source or evidence of JVM compatibility without adaptation.

## Observed results

The writer persisted 12 CID-named blocks. The second physical root was
`bafyreiakmttcp6otxvnyqmdjpzlschlskibp7enadlvkguw3nnp47f5wqm`.
The reader ran in a fresh JVM, restored this root, and queried the real
`datalog.core/q` via an injected `IPatternSource` over `engine/scan`. It
returned the expected logical-file root and chunk CID; filtering the chunk
CID attribute returned no rows. `:as-of 1` returned `before`, and the current
snapshot returned `after` after a real retraction/assertion.

In two independent copies of the test store, the root file was respectively
renamed away or had its last byte XORed with 1. **Before the fix**, missing
root raised a `NullPointerException`; the altered valid CBOR was accepted and
the query still returned rows. Its computed CID was
`bafyreid5gp4s3yizaqbyqaqwkeyp6tbveoujc3sd6kd76otaghkdckfu2m`, not the
requested root. **After the fix**, the intact root still passed, the missing
root returned `:kotobase.engine/block-not-found`, and the altered bytes returned
`:ipld/cid-mismatch` before decoding. The new and existing Prolly test namespace
ran as a local JVM oracle: **11 tests, 32 assertions, 0 failures, 0 errors**.

The patched engine copy SHA-256 was
`8630f6ba2cb4aac8193cb581e0545214eafc4e36147f3a3670a2eff809292d9b`;
the test copy SHA-256 was
`c946d14d8e4c0ddc28c10ce05e3a839754732d3142c291e32467704d7f67b2a8`.
The oracle driver at `oracle/awai-174/prolly-disk-oracle.clj` has SHA-256
`359b2a96332e4cd9af9458ba41ac18574e2fe0e79b85293e8268677429fa8c38`.

Representative commands, from the task's scratch worktree after preparing the
pinned/adapted classpath recorded above:

```sh
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v3"]}' -M .agent-output/prolly-disk-oracle.clj write .agent-output/prolly-disk-20261113
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v3"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-20261113
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v4"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-20261113
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v4"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-missing
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v4"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-corrupt
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v4"]}' -M -e "(require '[clojure.test :as t] 'kotobase.engine.prolly-test) (let [r (t/run-tests 'kotobase.engine.prolly-test)] (System/exit (+ (:fail r) (:error r))))"
```

The `v4` classpath is the `v3` reference copy with the patched engine and test
source plus the recorded test/spec modules. Missing and corrupt test stores
were made as separate copies; the original remains intact. These results do
not show that signed commits, actual policy/receipt, Native, off-host recovery,
or OS-cache loss have been implemented or verified.

### 2026-11-13: nested Arrangement snapshot

Starting from the v4 JVM oracle classpath described above, copy the candidate
`arrangement/core.cljk`, `arrangement/source.cljk`, `arrangement/source_test.cljk`
and existing `arrangement/core_test.cljk` as `.cljc` into a v5 copy. The other
oracle adaptations and versions remain as recorded above. Candidate SHA-256:

- core: `f3a63bcfeebcdc253ce656930ab7264c0510f597e86841bbc6e12d20f44797b5`
- source: `8e49b842afc943384cb9df6bfd11376b16133b5f55325473481ba9ef2b063917`
- source-test: `63afca33f364891a7f46c91e8795a88c7d85863e49aaa639f75e5794e4f07c56`

On the same 12-block file store and pinned root as the earlier experiment, a
copy of snapshot `bafyreic4fxqlzoq4emxpczfgdmf7wfvzrbvp23q7rmjjmrljdkmtgez5uq`
was replaced at its original filename by a valid DAG-CBOR snapshot with a
modified `prev` link. The old implementation restored and queried it. The v5
candidate rejects it with `:ipld/cid-mismatch`; the untouched store still
restores and produces the same join and temporal results. The focused JVM test
calls restore, cursor root lookup, delta commit and mixed changes with missing
and mismatching snapshot blocks; 1 test / 9 assertions passed and no writes
occurred. The Prolly suite passed 11 tests / 32 assertions.

Commands, from the experiment worktree:

```
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v5"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-20261113
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v5"]}' -M .agent-output/prolly-disk-oracle.clj read .agent-output/prolly-disk-snapshot-corrupt
clojure -Sdeps '{:paths [".agent-output/prolly-oracle-classpath-v5"]}' -M -e "(require '[arrangement.source-test] '[clojure.test :as t]) (binding [t/*report-counters* (ref t/*initial-report-counters*)] (t/test-vars [#'arrangement.source-test/snapshot-reads-reject-missing-and-mismatched-blocks]) (prn @t/*report-counters*))"
```

An attempted nbb 1.4.208 / Node 26.0.0 oracle load of the v5 classpath failed
before the test at `multiformats/base32.cljc:107` (unresolved `drain-5`). The
ClojureScript asynchronous test is added but not locally executed; neither
this reference run nor CI proves Native Forest I/O, signed basis, real policy,
or complete traversal integrity.

### 2026-11-13: ClojureScript asynchronous snapshot oracle

Standard ClojureScript 1.12.42 and Node 26.0.0 compiled and ran the direct
`oracle/awai-174/snapshot.cljs` driver against the v5 classpath described
above. A valid snapshot was accepted and missing and CID-mismatched snapshots
were rejected. This driver calls the product asynchronous snapshot reader; it
is a local reference oracle, not a Native gate or a full provider/recovery
integration test. The compiler downloaded Closure Compiler v20250402 from
Maven Central; no dependency was added to the product or CI.

```
# copy oracle/awai-174/snapshot.cljs to the v5 classpath as awai_oracle/snapshot.cljs
clojure -Sdeps '{:deps {org.clojure/clojurescript {:mvn/version "1.12.42"}} :paths [".agent-output/prolly-oracle-classpath-v5"]}' -M -m cljs.main -co '{:target :nodejs :output-dir ".agent-output/cljs-oracle-out" :output-to ".agent-output/cljs-oracle.js" :optimizations :none}' -c awai-oracle.snapshot
node .agent-output/cljs-oracle.js
```

Output: `async snapshot valid accepted; missing and mismatch rejected`.
The older nbb and test-namespace loading failures above remain separate facts;
the direct driver avoids loading the incompatible test namespace.

### 2026-11-13: asynchronous provider prefetch integrity

`provider.cljs.cljk` now verifies fetched block bytes before caching, decoding,
or following links. With ClojureScript 1.12.42 and Node 26.0.0, the direct
`oracle/awai-174/provider.cljs` driver uses the actual provider and an async
in-memory protocol backend. In two independent scenarios a valid-CBOR but
CID-mismatched manifest or metadata block is rejected with `:ipld/cid-mismatch`,
the corrupt block is not cached, and a link planted in it is not fetched.
The previous provider, compiled against the same corpus, followed that link and
failed instead with `:kotobase.engine/block-not-found`: a negative control.
This is not a remote-store, power-loss or Native test. The v5 oracle source
adaptations above still apply; `kotobase.storage.core` was additionally copied
from this revision unchanged and `provider.cljs.cljk` was named `provider.cljs`
for the standard host compiler. Candidate provider SHA-256:
`d3887183769eaadcdbe04fe727b73301f10268268521142053115e4bfb546d38`.
Driver SHA-256:
`f33ce0cb065662507ad1338b3cc6644449de7096546a1350b890a8270200b4a7`.

```
# copy the driver, storage.core, and selected provider to the v5 oracle classpath
clojure -Sdeps '{:deps {org.clojure/clojurescript {:mvn/version "1.12.42"}} :paths [".agent-output/prolly-oracle-classpath-v5"]}' -M -m cljs.main -co '{:target :nodejs :output-dir ".agent-output/cljs-provider-out" :output-to ".agent-output/cljs-provider.js" :optimizations :none}' -c awai-oracle.provider
node .agent-output/cljs-provider.js
```

Candidate output: `provider corrupt head and metadata rejected before following links`.
