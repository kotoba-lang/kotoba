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
