# capability-random-bytes

Atomic authority package for `random/bytes`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreidauidawvzfmrbe2wi2dn62flk2sejjpfp6omszbvhwjqfeslk7ai`
- artifact: `artifacts/provider.core.wasm` (sha256 `59535aedb5f325d33fa0e86da8a6368d440fffb447f14a48a876ee7f565cbd8e`)
- JVM reference: `kotoba.capability.random.bytes.provider`
- host ABI: module `kotoba`, field `random_bytes`, `(ptr, len) → i32`

Definition CID is unchanged. `:signature :reference-unsigned`.

Core wasm fills guest memory with a tiny xorshift32 stream (non-crypto
packaging reference). JVM `random-bytes` uses `SecureRandom` for host
semantics. Production hosts should inject OS CSPRNG into linear memory.

```sh
kbb -M:test
```
