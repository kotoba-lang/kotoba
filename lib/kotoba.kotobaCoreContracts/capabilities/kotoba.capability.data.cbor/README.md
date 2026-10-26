# capability-data-cbor

Atomic authority package for `data/cbor`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreibcxvtartawnqeasi6sblidclt5qimza65zni4p7nsac47s62xjii`
- artifact: `artifacts/provider.core.wasm`
- JVM reference: `kotoba.capability.data.cbor.provider`
- host ABI: module `kotoba`, field `cbor_encode`,
  `(i32 i32 i32 i32) → i32` (pairs-ptr, pairs-len, out-ptr, out-cap)

Input wire format: flat `key\tvalue` pairs, LF-separated. Encodes a
definite-length CBOR map of UTF-8 text keys/values. Dotted-path nesting is a
host extension (see capability_contract.edn); the reference wasm accepts flat
keys only.

Definition CID is unchanged by this provider landing.
`:signature :reference-unsigned` is reference packaging.

```sh
kbb -M:test
```
