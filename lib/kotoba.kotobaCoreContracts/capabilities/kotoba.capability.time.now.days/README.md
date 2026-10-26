# capability-time-now-days

Atomic authority package for `time/now-days`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreigg7f4obntus3fdmeuxuhcatwg4ijkhyurjwh27kegrm2co2xuaxm`
- artifact: `artifacts/provider.core.wasm` (sha256 `939e4b4f13757b429299cbd86d24dba5b69874544828550a7628bfb690a0f7fa`)
- JVM reference: `kotoba.capability.time.now-days.provider`
- host ABI: module `kotoba`, field `now_days`, `() → f32`

Definition CID is unchanged by this provider landing.
`:signature :reference-unsigned` is reference packaging.

Core wasm returns `0.0` (ABI packaging). JVM `now-days` uses UTC millis /
86400000 as a continuous day counter for host semantics.

```sh
kbb -M:test
```
