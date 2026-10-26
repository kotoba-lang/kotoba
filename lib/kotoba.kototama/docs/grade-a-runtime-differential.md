# Grade A differential runtime conformance

`kototama.runtime-conformance` executes identical host-free Wasm bytes in:

1. Chicory 1.4.0, the current JVM tender runtime;
2. Wasmtime, an independent native runtime;
3. Node's independent WebAssembly engine.

The checked corpus covers compiler-produced factorial and peak-cell guests,
the web demo, signed arithmetic, bounded `memory.grow`, and an integer
division trap. Qualification requires unanimous values for successful modules
and unanimous trapping for invalid execution.

The existing independent actor-host smoke test additionally exercises
`clock-monotonic`, `log-write`, and `sha256-hex` through the pinned
`wasm-webcomponent` JavaScript host rather than Chicory:

```sh
kbb -M:test -n kototama.runtime-conformance-test
node web/verify-actor-host.mjs
```

T-07 remains `in-progress`: the differential lane must cover every
`actor:host` import and the future WASI 0.3 component profile, then run as a
clean-checkout release gate rather than relying on locally installed
Wasmtime/Node.
