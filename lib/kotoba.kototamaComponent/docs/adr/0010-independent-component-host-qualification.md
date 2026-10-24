# ADR 0010 — Independent Component host qualification

- Status: Accepted
- Date: 2026-07-26

## Decision

Kototama qualifies three independent engine paths behind the same closed
Component host contract:

- the Rust/Wasmtime micro-TCB;
- pinned `@bytecodealliance/jco` 1.17.9 under Node.js;
- pinned Cloudflare `workerd` 1.20260727.1 after `jco` converts the Component
  into portable ESM/Core-Wasm modules.

Both receive the same compiler-produced Component bytes, exact named WIT
imports, immutable execution identity, Aiueos decision, scoped ability,
resource declaration and host-managed lease. Neither host links WASI.
Concrete executable bytes are pinned separately in each full host receipt;
the execution identity binds the common versioned host contract.

The jco adapter is qualification evidence, not an ambient JavaScript escape
hatch. It is an executable with a closed JSON-line provider protocol. It
generates bindings only for admitted imports and maps only explicitly supported
interfaces. Unknown imports, malformed abilities and non-positive resource
bounds fail before instantiation.

`workerd` is not represented as a Component-native engine. The checked-in
adapter preserves the Component's named WIT imports while workerd executes the
transpiled core modules. Its isolate has `globalOutbound = deny`; no network,
filesystem, environment, argument, or generic WASI capability is inferred.
Eight Components share that isolate and can reach only the explicitly bound
identity, hash, HTTP, log, and object-store providers.

The authoritative typed world contains eleven individually granted operations:
identity sign/verify, SHA-256, HTTP post/get-stream, object get/put/CAS,
log read/append, and clock now. The compiler emits only a singleton implemented
vertical per Component today, so qualification composes multiple Components in
one host rather than creating an umbrella import.

## Cross-host invariant

`kototama.aiueos-adapter/portable-receipt` must be byte-value equivalent across
both hosts for the same run. It compares policy decision semantics, execution
identity, Component CID, exact imports and abilities, resource bounds,
capability consumption and outcome. Host runtime and executable hash remain in
the full receipt and must differ.

The integration qualification also proves equivalent rejection for:

- deny-by-default policy admission;
- live control-plane epoch revocation;
- one-shot capability exhaustion.

For every typed Wasmtime and jco provider call, the host revalidates the named
grant, exact ability, live epoch, expiry, item/byte quota, and audit receipt.
The workerd isolate separately proves named-import confinement and deny-all
ambient outbound access. These are different safety mechanisms and therefore
different evidence; engine diversity is not claimed to make their TCBs
identical.

`test/tender/component_e2e_test.cljk` and the `workerd-component` CI job are the
normative executable evidence.
