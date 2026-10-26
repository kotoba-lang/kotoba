# capability-clock-monotonic

Atomic authority package for `clock/monotonic`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreiacwmejactezvrcbrxlqqyxha2l3qaw253tcfuwsywvzbajwo5fja`
- artifact: `artifacts/provider.core.wasm` (sha256 `826644dfd0f1cdb8bc225310a2504ad9d019a0397897415951be5d56105b681b`)
- JVM reference: `kotoba.capability.clock.monotonic.provider`
- host ABI: module `kotoba`, field `clock_monotonic`, `() → i64`

Definition CID is the import identity and is **unchanged** by this provider
landing. `:signature :reference-unsigned` is reference packaging; production
signing is follow-up.

The core wasm exports an instance-local incrementing counter (ABI packaging).
JVM `monotonic-ns` uses `System/nanoTime` for host semantics. Embedders
should inject OS monotonic clocks in production.

```sh
kbb -M:test
```

Rebuild the wasm core (optional):

```sh
wasm-tools parse wasm/clock_monotonic.wat -o artifacts/provider.core.wasm
wasm-tools strip artifacts/provider.core.wasm -o artifacts/provider.core.wasm
shasum -a 256 artifacts/provider.core.wasm
```
