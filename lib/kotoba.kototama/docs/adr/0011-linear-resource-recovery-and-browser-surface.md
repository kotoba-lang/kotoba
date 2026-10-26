# ADR 0011: Linear resources, crash recovery, and browser qualification

- Status: Accepted
- Date: 2026-07-26

Wasmtime and jco/Node bind compiler-produced `own<resource>` capabilities.
The issue operation creates an engine-owned resource and execute consumes it.
Kototama still performs the authoritative lease check at the provider edge.

For multi-call and multi-process authority, `linear-journal` fsyncs a claim
before provider invocation. Recovery treats a claim without a result as spent:
availability may be lost, but authority is never replayed. Claims are
serialized per journal and tested with concurrent contenders and a new-process
reopen.

Browsers do not yet instantiate Component binaries natively. The third
qualified surface is therefore explicitly `jco-transpiled Component in
Chromium`, not a third native Component engine. CI compiles the Kotoba source,
transpiles that Component, and executes it in headless Chromium.

The scheduled Component requalification workflow detects upstream wasm-tools,
Wasmtime, and jco drift and opens one actionable qualification issue. Pin
changes require the full positive and negative matrix.
