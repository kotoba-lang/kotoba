# WASI-HTTP Egress and XRPC Ingress Implementation

## Overview
This historical document covered the Rust `kotoba-runtime` / `kotoba-server`
WASI-HTTP prototype. Those crates have been retired from this repo during the
Kotoba/CLJC migration; current runtime ingress/egress must be supplied by
host-owned adapters.

## Deliverable 1: WASI-HTTP Egress
1. Added `wasmtime-wasi-http = "25"` to `kotoba-runtime/Cargo.toml`.
2. Implemented `WasiHttpView` for `HostState` in `crates/kotoba-runtime/src/host.rs`.
3. Extended `HostState` to initialize `WasiHttpCtx`.
4. Added an outbound allow-list policy based on `KOTOBA_HTTP_EGRESS_ALLOW` environment variable (CSV of host globs).
5. Enforced egress metering by wrapping the outbound call with `self.charge_gas(1000)` mirroring `evm` call cost.
6. Bound `wasmtime_wasi_http::add_only_http_to_linker_sync` into `KotobaLinker::bind_kotoba_interfaces` to expose the STANDARD `wasi:http/outgoing-handler` path.
7. Verified instantiation without unresolved-import errors by adding `test_wasi_http_instantiates` WAT guest fixture.

## Deliverable 2: Generic XRPC→wasm Ingress Dispatch
1. Added `POST /xrpc/:nsid` as a fallback generic dispatch route inside `build_router` in `crates/kotoba-server/src/lib.rs`.
2. Extracted the `app` identifier from `nsid` (`com.etzhayyim.apps.<app>.<method>`).
3. Reused the `kotoba/network/nodes` Datomic graph (accessed via `state.ipns_registry` and `DistributedDatomReader`) to resolve the application's `program_cid`. The routing logic looks for `node/did` matching `<app>` or `<app>.etzhayyim.com`, then extracts the `node/endpoint` field as the `program_cid`. If not found, it falls back to using the `<app>` directly.
4. Serialized the inbound JSON to CBOR and routed it through `state.router.dispatch_with_snapshot`.
5. Added `generic_xrpc_dispatch_resolves` test in `kotoba-server/src/lib.rs` to verify that `POST /xrpc/com.etzhayyim.apps.yata.some_method` reaches the handler (asserts response is not 404).

## Historical verification
- Both `cargo test` runs in `kotoba-runtime` and `kotoba-server` completed
  successfully in the retired prototype.
- `cargo build -p kotoba-runtime -p kotoba-server` exited 0 in the retired
  prototype.

## Next Steps
- Validate real app deployments by pushing `KOTOBA_HTTP_EGRESS_ALLOW` overrides if specific strict isolation is required.
- Migrate `yatabase` domain-write paths and eventually sunset `bpmn-dispatcher`.
