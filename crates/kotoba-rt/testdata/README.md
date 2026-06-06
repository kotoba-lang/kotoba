# kotoba-rt test fixtures

## `kge_counter.wasm`

A real `kotoba:kge` **Component-Model** guest (the `game` world), used by
`wasm_component_rollback_reconverges` (`--features wasm-component`) to prove the
host drives a true component through the rollback engine.

Regenerate after changing `kge-counter-guest/`:

```sh
cd kge-counter-guest
cargo component build --release
cp target/wasm32-wasip1/release/kge_counter_guest.wasm ../kge_counter.wasm
```

Requires `cargo-component` + the `wasm32-wasip1` target. The committed `.wasm`
(~17 KB, stripped) lets the test run without that toolchain in CI.

> **Determinism by construction:** the guest is `no_std` (dlmalloc global
> allocator), so the component imports **NO `wasi:*`** — wall-clock, random and
> sockets are not merely unused but *uninstantiable*. Verify with
> `wasm-tools component wit kge_counter.wasm` (only `export kotoba:kge/kge`).
