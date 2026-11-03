# Multilanguage VM contract: initial evidence, 2026-11-03

This is bounded research evidence for JUN-792, not a conformance declaration.
The comparison of both engines on the same inputs remains open.

## Native receipt profile

On a Linux x86-64 host, the existing Amu native receipt gate was run with
`python3 check-kototama-receipt.py --compiler ./amu-linux-x86_64 --output
./receipt` from a dedicated staging directory. Python staged bytes and observed
native processes; the Amu-built Kotoba gate decided the verdict. Inputs:

- Amu checkout `a4c16e7c47005d2235dc48d3f69569773a1606e7`;
- `amu-linux-x86_64` SHA-256 `5fb29403553b3ba6b7136f71820bbe9526ba830c8e865057aba74b91f5fc96bc`;
- `check-kototama-i64.py` SHA-256 `4072981ee12afa143e35efdb1b0f9aef24de939e0fc774a420ff7320c834b020`;
- `check-kototama-receipt.py` SHA-256 `e2adc50a836e0ca4feeae39e8dc9fac6fdaea1062ad7a1564a4e48a934d1ce19`.

Result: 262 vectors, ordered native gate exit 0; corrupted-observation and
metering-removal controls both exit 1; output transport failure exit 74. The
gate binary SHA-256 was
`addc5cad5b5b0bc518a2281ed8980ba5f8ae357614053a3b780af1a920f19813`.
The report marks whole-VM qualification false and makes no performance claim.
This is evidence for the measured compiler image and profile, not the latest
Amu source, other ISAs, actor integration, or the evaluator.

## Canonical decoder admission discrepancy

The normative `spec/kototama-vm-v1.edn` requires unknown fields to be
rejected. At Kotoba commit `ae81af44e8c3a00d908adc07a9e19be598ab7c8b`, the
historical `lib/kotoba.kotobaVm/src/kotoba/vm/kototama/program.cljk`
`decode-canonical` instead accepts both an unknown program field and an
unknown method field. It reconstructs the program map while retaining the
original method map. This is an implementation violation of the declared
contract; it is not a reason to weaken the normative requirement. It does
not, by itself, demonstrate that a capability was granted or an effect ran.

One-time local reference observation on macOS ARM64, Node v26.0.0 and nbb
v1.4.208, from the Kotoba checkout:

```sh
nbb --classpath lib/kotoba.kotobaVm/src -e '(require (quote [kotoba.vm.kototama.program :as p])) (let [m {"params" [] "param-types" [] "result" "i64" "effects" [] "body" ["const" ["integer" "42"]]} base ["kototama.vm/program" 1 {"entry" "run" "exports" ["run"] "value-profile" "kotoba.i64-wrap/v1" "methods" {"run" m}}]] (doseq [[label v] [["baseline" base] ["unknown-program-field" (assoc-in base [2 "unexpected"] true)] ["unknown-method-field" (assoc-in base [2 "methods" "run" "unexpected"] true)]]] (try (p/decode-canonical v) (println label "accepted") (catch :default e (println label "rejected" (ex-message e))))))'
```

Output: `baseline accepted`, `unknown-program-field accepted`,
`unknown-method-field accepted`. This invocation used the checkout's
`nbb.edn`; its first run downloaded/extracted the pinned Kotoba dependency at
`b94158fd48ec541b70d3c455912a06f407537ddc` into the tool's managed cache.
This is a reference observation of historical CLJK only, not a new CI gate or
a native implementation. A separate attempt to load the evaluator with
the local CLJK dependencies failed during nbb analysis of
`multiformats.base32` (`drain-5` unresolved); it produced no evaluator result.

The VM component rules require canonical Kotoba and Amu selfhost native for
new implementation and final execution, and say no replacement native CI is
qualified for this portable CLJK suite. Do not treat a patch to the historical
decoder or this local reference as a native fix. Native admission and a
negative-control gate remain open.

## Common-input expression observation

After the initial evaluator loading failure, a one-time local reference run
loaded the unchanged CLJK evaluator and kernel with a test-only `ipld.core`
namespace whose nine exported functions all throw if called. The selected
pure programs have empty method effects, and none invoked this stub. No IPLD,
actor, message admission, persistence, capability, or VM receipt behavior was
tested. nbb v1.4.208 / Node v26.0.0 were used only as a local reference, not
as a build, CI gate, fallback, or native engine. The invocation context directly
supplied `:budget`, `:spent 0` and `:args []` to `invoke` after calling the
historical `decode-canonical`; it bypassed the full actor entry path.

The inputs and native receipt fields are recorded in
[`cases.json`](evidence/jun-792-20261103/cases.json); the separate evaluator
observations are in
[`evaluator-observations.jsonl`](evidence/jun-792-20261103/evaluator-observations.jsonl).
Each program was serialized with the existing Amu fixed-vector encoder and
its SHA-256 checked against the native gate report before comparison. Of 24
observations, all 12 successful and 11 fuel-exhausted observations matched
the native result/charge projection. These include constant, add, wrapping
add, negative quotient, branch selection and loop/recur, with zero, exact,
above or one-short budgets where present in the original vectors.

One observation differs: for division by zero with budget 100, native v2
reported status 2 and spent 3, while the direct evaluator returned
`:aborted? true`, `:last-error :not-callable`, and spent 0. The evaluator's
division reports a `:kototama.vm/not-callable` exception; `invoke` catches
it and calls `kernel/abort` using the incoming context, thereby discarding
the progressed context in this direct-call scenario. This is a measured
difference in the tested paths; preserving failure charges and failure kinds
needs an explicit contract and native implementation. A direct invocation is
not an end-to-end VM receipt comparison.

Reproduction: the inputs were staged by a local Python data-only script using
`program`, `const`, `var`, `arith` and `encode` from the pinned
`check-kototama-i64.py` and the native report. The exact observations were
obtained by `nbb --classpath oracle:<kotoba-checkout>/lib/kotoba.kotobaVm/src
oracle/observe.cljs` from a scratch directory; that script calls
`decode-canonical` and `invoke` and prints result fields. The scripts and
throwing IPLD seam are retained with the local evidence, not installed into
the product. SHA-256: staged cases
`eb21cc529ae20519ff6059f5529d00766153b8c0635860625e14bb9b21c9cd96`;
observations `9baadb4efcc49dbe17bc6a52a69969edbff405122b204a951d3a594bfbd94124`;
observer `1b691de07dbccf7588bf1c47df678184486196ed1ebf87069cb9856e69b32f68`;
IPLD stub `5ec8af7471eee46c5180ebc855c8867eb1c892aa7cee0857e9bc19f4351362c8`;
stager `b560fbd0744047c68e34b30dbbc5964172481a4acf34e2908785e23dcf0aa6d8`.
These vectors do not establish full evaluator or VM conformance.

## Native receipt/v2 validation component

`src/kototama/pure_i64_receipt.kotoba` defines a reusable, pure check of the
complete 64-byte receipt, supplied normal exit code, independently admitted
fuel budget and exact stack bound. It checks framing, byte domain, magic,
status/exit consistency, failure result, budget, spent/remaining arithmetic,
zero arena and stack bound. It does not authenticate the producer, establish
artifact identity or fresh authorization, perform process I/O, or implement
state/receipt semantics. No existing host has been switched to this function.
The Amu cache host already performs its own low-level checks and remains the
current implementation; this component is a candidate for typed consumers.

On Linux x86-64, the source-locked two-module native test
`test/kototama/pure_i64_receipt_gate.kotoba` was checked and compiled by the
Amu main compiler image SHA-256
`f6c887b23c8b8447dc397821cc82a972c3502a269ae51893075bf888a32aea9a`.
The `kx64-v1` linked project ran through the Amu-native `kx64-runner` with
result 42. The test includes two exact 64-byte outputs from the independent
Amu receipt/v2 corpus (SHA-256
`2c528254e9bec17fdea5f7102d738441325c1c795a88fe1673410d8e60feafb0` and
`ad805790638ff1c0f9aabf90862e8e7d402caf75399bcbb40cb004ce26e5713f`),
success and all three typed failures, malformed lengths, invalid byte values,
wrong exits, contradictory resource fields, invalid budget and stack bounds.
Changing only the magic check in a separate negative-control source made the
same native gate return 0 instead of 42. The positive project container hash
was `2990d843b8f43583fcac7ff5121df3695381f23af91e5a2c8d83247f517b415e`;
the native runner hash was
`27349b7edfea5833f41263cdbf6195e5f26848bfb491e406c2d826987194d3b2`.
This tests a source-locked component on one ISA, not a host integration,
independent compiler rebuild, cross-architecture parity or full VM contract.

The same two source files were also tested on macOS ARM64 with the public
Amu host CLI SHA-256
`616a41c017e92dd475e7472d791629a65d0811552b305b93d8c8c4b87bf3b1b0`,
using a KSL2 source lock with both module names and byte hashes. `check`
returned `ok`; `compile` produced a native executable, which printed `42`
and exited zero. Weakening only the magic check in a separately locked
negative-control build made its executable print `0`. The positive executable
SHA-256 was `da8cf8ee7bc5576e3bed553d1a82d17563da8b51b1105381f9c4630048deb6b8`;
the modified source SHA-256 was
`f19aa486174a00d3b38c3502f0148b2051db6ffcac30fed830aaf95bae478ffe`.
The test gate returns its decision as an i64; the native CLI process exits
zero for both outputs, so a runner must check the returned value rather than
equating a zero process exit with a passing gate. These are observations on
two OS/ISA combinations, not Linux ARM64 or a full host integration.

## Actual native receipt corpus through the validator

On Linux x86-64, the updated Amu gate from
[`amu#1802`](https://github.com/kotoba-lang/amu/pull/1802) produced 194
complete receipts among its 275 cases: 77 successes, 100 fuel exhaustions,
12 division-by-zero and 5 division-overflow failures. The other cases were
compiler refusals and produced no receipt. The compiler image SHA-256 was
`f6c887b23c8b8447dc397821cc82a972c3502a269ae51893075bf888a32aea9a`.

`scripts/stage-pure-i64-receipt-corpus.py` stages those actual output files,
their recorded budgets and exit codes, and an individually magic-corrupted
copy of each as literals in a source-locked native Kotoba test. Python does
not implement the validator or decide the test result. The generated test
and the unchanged validator compiled and ran with the Amu-native KX64 runner:
the native result was 42 for all 194 actual receipts and 194 corrupt controls.
Weakening the validator's magic check in a separately compiled control made
the same generated test return 0. The generated gate source SHA-256 was
`d280d91b42a03d385c89401e26ae950772593fea455cd3dd24e1a0e32bb6c221`.

The stager uses each receipt's observed stack field as the supplied expected
stack. This checks handling of the varied stack values, but is not evidence
that a host independently binds the stack to an admitted artifact. The test
does not exercise live process transport, identity checks, signed receipts,
host integration, Linux ARM64, or whole-VM execution. The generated program
returns the verdict as an i64: an observer must check 42, not just process exit.

## Experimental live FS2 boundary

On Linux x86-64, the current main compiler image (`f6c887b2…`) checked the
source-locked FS2 and CLI test project, but refused compilation with `E7101`;
the same refusal occurred for a CLI-only project. This is the existing
source-locked x86 capability limitation, not a passing production route.

For an isolated experiment, the Amu main `7a755126bbd8` 61-module full
manifest was staged with only `seed/98-x86_64-project.kotoba` replaced by the
existing `seed/experimental/98-x86_64-project-fs-cli.kotoba` candidate from
AWAI-97. The candidate unity SHA-256 was
`5553eb4c4e5130b75896ce79990b826854f0ce33d3203e08fb937d4e7169f9fa`.
Native x86 builds F1, F2 and F3 all had SHA-256
`c4cd294bf79339a38cd3a02d51997aa185043676888f9550727d5910d72e19ec`.
This fixed point does not promote the experimental compiler or prove its
complete product gates.

Using F3, the source-locked `pure_i64_receipt_fs_gate.kotoba` and unchanged
validator were compiled to KX64 and run under the native KX64 runner. A fresh
execution of the Amu receipt/v2 `const` image (image SHA-256
`f6aed1a910b690a4e1fc3f90d95ad705164c62292a67fcd05e8e894e35a4620d`)
produced 64 bytes with SHA-256
`ad805790638ff1c0f9aabf90862e8e7d402caf75399bcbb40cb004ce26e5713f`.
The test consumer read that file through the explicit FS2 app-data capability
and returned 1. It returned 0 for a changed magic byte, a truncated receipt,
and an outside-scope path. Missing and symlink paths trapped/refused; denying
the FS or CLI capability refused with exit 120 and did not return success.
Changing the imported validator's magic comparison in a separately compiled
negative control made the real receipt return 0. The linked candidate
container SHA-256 was
`029023a4998d51f1be01babedf93058abb06c956f9fe3d810c2690ff3237f9da`.

The test fixture at commit `1a6909136` binds its known expected exit, budget and stack directly;
it is not a process supervisor and does not independently admit artifacts.
The separate staging process launched the producer and wrote its bytes to a
private test directory. This does not establish a production host, signed
receipt, same-process transport, host lifecycle or entire VM conformance.

## Cache host receipts with separate invocation context

The existing Amu native cache host gate was run on Linux x86-64 with the
same candidate compiler image and source digest `a5f990fc…`. Its native
ordered gate passed 57 observations; the corrupted-observation control
refused. The optional deadline control was not enabled. The source digest
matches the staged full manifest, but the `native-product.json` at this
revision explicitly marks the current compiler/source link and broader
qualification unverified; this experiment does not establish that link.

The FS2 fixture now receives exit, budget and stack as separate CLI arguments
instead of using its original fixed values. The test supervisor invoked the
cache host four more times and passed the emitted receipt bytes through FS2 to
the independently compiled validator: success at budgets 1 and 2, exhaustion
at budget 0, and division by zero at budget 3 were all accepted. The host's
invocation exit was checked by the test supervisor; the budget came from the
request, and the expected stack (160 or 192) from the respective cache binding,
not from the receipt. For each receipt, a wrong exit, budget or stack was
rejected: 4 valid observations and 12 mismatched-context observations.
Malformed and missing numeric arguments returned 0, and withholding the FS or
CLI capability refused with exit 120. These values and capabilities belong to
the test supervisor; guest-supplied arguments are not authority.

The native cache host image SHA-256 was
`ca551b4bc2768d1f28b1dbe76378fbff286062a70987a5bf582bfbf39f1ea27f`;
the linked FS2 test container SHA-256 was
`9b27688e83e08f4c0d3228414f7d09789ca78763423aa97dd1fe3cd8d5a042a2`.
The consumer still needs the experimental compiler candidate described above,
and the file bridge and numeric context are test orchestration, not an
integrated production supervisor. No signed or remote receipt, deployment,
whole-VM parity, or Linux ARM64 result is claimed.

## Experimental native expression reference

`test/kototama/experimental_i64_reference.kotoba` is a test-only iterative
interpreter over a manually supplied vector tree. It covers constants, binary
wrapping addition, and signed quotient, with a bounded frame stack and a
per-node charge. It returns success, exhaustion, zero-divisor or signed
quotient-overflow as data. It is deliberately not a canonical CBOR decoder,
program admission, general evaluator, public API, host, or a replacement for
any complete VM component. Its malformed-tree response is not an admission
contract. Loop/recur, calls, most operators and all effects remain absent.

Its separately source-locked fixture returned 42 as native code on macOS
ARM64 (Amu CLI SHA-256 `616a41c017e92dd475e7472d791629a65d0811552b305b93d8c8c4b87bf3b1b0`)
and Linux x86-64 (compiler SHA-256
`f6c887b23c8b8447dc397821cc82a972c3502a269ae51893075bf888a32aea9a`;
native KX64 runner SHA-256
`27349b7edfea5833f41263cdbf6195e5f26848bfb491e406c2d826987194d3b2`).
A separate macOS build with addition's charge removed returned 0 instead of
42. The fixture includes 12 manually constructed two-fault/budget cases whose
status, value and spent projections agree with the corresponding real Amu
receipt/v2 observations on Linux x86-64. This is a manual correspondence
between two representations; it does not prove that a common canonical
program was decoded or interpreted by the test model. The source and gate
are retained to support that future work; they are not wired to CI.

The follow-up `scripts/stage-i64-reference-comparison.py` reads actual v2
corpus inputs and receipts, verifies each input against the report hash, and
stages a native reference gate for the subset expressible by this experiment.
On Linux x86-64 it selected 68 actual observations from the 287-case corpus;
the native gate returned 42 when comparing status, value and spent to those
receipts. A separate model with addition's charge removed returned 0; an input
with a changed byte and the original report digest was refused before staging.
The adapter decodes CBOR and constructs the model tree in Python, so this is
not an independently implemented native canonical decoder or admission, and
the subset filtering and representation mapping remain part of the test's
trusted scaffolding. It does not cover programs with other operators, loops,
methods, state or effects. The generated reference gate was compiled with the
Linux source-lock route and is not yet a continuous CI gate.

The experimental model and adapter were subsequently extended with `if`:
the native model evaluates the condition and only its selected branch. On
Linux x86-64 the generated gate compared 80 actual AOT receipt observations
and returned 42; a model with the branch selection reversed returned 0. The
macOS ARM64 standalone source-locked fixture returned 42 for true and false
branches, unselected divide-by-zero and a short budget. These are still
bounded test models with a Python input adapter, not VM admission or a native
canonical decoder. The earlier three-operator model and 68-case count above
refer to the prior experiment.

The experimental expression model was extended again with binary subtraction,
wrapping multiplication and signed remainder, including zero divisor and
`MIN rem -1 = 0`. The standalone native macOS fixture and its existing branch
mutant gate passed. On Linux x86-64 the limited CBOR adapter staged 98 actual
receipt observations; the native comparison returned 42 and a separate
remainder-sign mutant returned 0. This supersedes the earlier 80-case count
for this tested corpus; it does not remove the Python adaptation, native
decoder, whole-program admission or full VM limitations described above.

## Native CBOR-to-reference experiment

The checked-in `org.ietf.cbor` native codec was source-locked and its existing
codec fixture returned 0 on macOS ARM64 with the pinned Amu CLI. Generic CBOR
is not by itself VM admission: for example, it normalizes duplicate keys and
non-shortest integer heads. The new test-only
`experimental_cbor_reference_bridge.kotoba` decodes and re-encodes bytes for
exact equality, extracts the selected entry body, and constructs the limited
expression model tree in native Kotoba. It does not check the complete program
or its authority and is not suitable as a general admission boundary.

`stage-native-cbor-reference.py` transports selected actual AOT input bytes
and receipt observations into a source-locked native gate; it checks the source
and report hashes but does not decode or evaluate the CBOR. On macOS ARM64,
98 actual Linux x86-64 AOT receipt projections (status, value, spent) matched
the native CBOR bridge plus reference model. The gate also refused an overlong
array header and trailing byte. A separate native bridge mutant mapping add
to multiply made the earlier 98-case comparison return 0 rather than 42.
The selection is supplied by the earlier limited adapter and is not a claim
of complete coverage. The bridge supports only binary arithmetic and `if`;
method reachability, unused invalid code, effects, limits and the complete
canonical DAG-CBOR/program profile still need independently qualified native
admission and CI. No production execution or host integration is claimed.

The test-only bridge now checks the entire *supported experiment subset*
before evaluating: exact program and method field counts, the declared i64
profile, bounded unique exports that name existing methods, empty parameters
and effects, and supported bodies in every method and both branches. The
fixed native fixture refuses unknown fields, invalid declarations, an invalid
unused method and an invalid unselected branch, while accepting a valid unused
method. The source-locked macOS gate returned 42; replacing the method scan
with `true` made its negative control return 0. The 98 actual-receipt native
comparison still returned 42. These checks deliberately refuse features such
as method parameters and calls even when another profile supports them. They
are neither full pure-i64 nor general VM admission, do not establish safe
resource limits for untrusted inputs, and do not resolve the pending normative
`exports` question. The accepted test shape follows the existing Amu route
only for this experiment.
