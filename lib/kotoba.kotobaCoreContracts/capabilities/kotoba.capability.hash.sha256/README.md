# capability-hash-sha256

Atomic authority package for `hash/sha256`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreigj5lmdlxhxhlebacwoprr2hmqq24zwa45iiocbujuzqjvkkxvtpq`
- artifact: `artifacts/provider.core.wasm` (sha256 `ffa8de62f3114aa8134d840e9ba4febee301cc6966eadea58ad4142ad679848a`)
- JVM reference: `kotoba.capability.hash.sha256.provider`
- host ABI: module `kotoba`, field `sha256_hex`, `(i32 i32 i32 i32) → i32`
  (`ptr`, `len`, `out-ptr`, `out-cap` → bytes written or `-1`)

Definition CID is the import identity and is **unchanged** by this provider
landing. `:signature :reference-unsigned` is reference packaging; production
signing is follow-up.

Wasm core implements FIPS 180-4 SHA-256 over its exported linear memory and
writes 64 lowercase hex ASCII bytes. JVM `digest-hex` uses
`MessageDigest/SHA-256` for the same vectors.

```sh
kbb -M:test
```

Rebuild the wasm core (optional):

```sh
rustc --target wasm32-unknown-unknown -O --crate-type cdylib \
  -C lto -C opt-level=s -C panic=abort \
  wasm/src/lib.rs -o artifacts/provider.core.wasm
wasm-tools strip artifacts/provider.core.wasm -o artifacts/provider.core.wasm
shasum -a 256 artifacts/provider.core.wasm
```
