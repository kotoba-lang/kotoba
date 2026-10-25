# Kototama Wasmtime Component host

This is the native micro-TCB adapter used for effectful Component execution.
It links no WASI interfaces. The only host functions it can define are the
closed aiueos WIT imports, and each is bound to a validated ability descriptor.
The v0.3 binding is generated from the ABI repository's pinned WIT source and
implements identity, hash, HTTP, object-store, log, and clock interfaces.
Streaming bytes remain host-owned resources: polling, bounded reads,
cancellation, byte ceilings, and item ceilings are enforced inside this
process rather than delegated to a provider.

The line-delimited JSON protocol is private to kototama.wasmtime-component.
It must not be exposed as a general component runner or used to pass ambient
environment, files, sockets, clock, random, process, or command-line access.

## Resident mode

`tender-resident-component-host --serve` keeps a sealed Component
available on a loopback-only HTTP endpoint:

- `GET /healthz` reports the exact Component CID/SHA and receipt public key.
- `POST /v1/run` executes `main`, checks the admitted expected result, appends
  an fsync'd Ed25519-signed receipt, and returns that receipt.

The receipt envelope carries both the decoded `body` and the exact canonical
JSON `payload` whose UTF-8 bytes are signed. Verifiers must require
`parse(payload) == body` before checking the signature; they never need to
reproduce a language-specific map serialization.

The daemon verifies the Component SHA before binding its socket and executes it
once before advertising readiness. It rejects non-loopback binds, request
bodies, and ambient WASI. Without a capability configuration it remains
provider-free. A SHA-pinned `kototama.resident-capabilities/v1` configuration
may link exactly `http/post`, `storage/transact`, and `llm/generate`: endpoints
must be literal loopback HTTP; storage is either one absolute append-only fsync
log or one exact loopback provider endpoint. Each capability is one-shot per
execution, and every call appears in the signed receipt.

The default `tender-component-host` remains the typed v0.3 protocol host used
by the compiler/runtime E2E suite. Resident deployment is a separate binary so
adding lifecycle, receipt persistence, and loopback providers cannot widen or
replace the typed host's authority surface.

The receipt seed is read from an absolute node-local file; deployments should
generate it on the node and must not transport it from the control plane.

Required environment:

```text
KOTOTAMA_COMPONENT_PATH       KOTOTAMA_COMPONENT_CID
KOTOTAMA_COMPONENT_SHA256     KOTOTAMA_EXPECTED_RESULT
KOTOTAMA_FUEL                 KOTOTAMA_MEMORY_PAGES
KOTOTAMA_NODE                 KOTOTAMA_RECEIPT_SEED_PATH
KOTOTAMA_RECEIPT_LOG
```

`KOTOTAMA_BIND_ADDR` defaults to `127.0.0.1:18901`.
Effectful deployments additionally set both
`KOTOTAMA_CAPABILITY_CONFIG_PATH` and
`KOTOTAMA_CAPABILITY_CONFIG_SHA256`; an unknown configuration field or digest
mismatch fails startup.
