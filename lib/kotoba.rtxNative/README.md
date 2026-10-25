# kotoba-lang/rtx-native

Kotoba-owned reservation metadata for the contingent native RTX fallback. This
repository does not implement a renderer. Future RTX/3D execution belongs to a
Kami provider.

The sole production source is `src/kotoba/rtx_native.kotoba`. It compiles to
restricted JavaScript and typed Wasm without a JVM or ClojureScript production
runtime. See `docs/adr/0001-kotoba-source-authority.md` for the ABI decision.

```sh
kbb -M:test
kbb -M:lint
```
