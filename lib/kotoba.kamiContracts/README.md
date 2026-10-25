# kami-contracts

CLJC/EDN authority for KAMI Engine component boundaries.

Rust, WebGPU, WGSL, JavaScript, Python, and native host code are providers or
launchers. They execute validated EDN requests and receipts. WIT is generated
from, or checked against, these contracts and is not the semantic authority.

Initial authority namespaces:

- `kami.component` — Wasm Component Model worlds, imports/exports, render frame
  validation, physics step request validation.
- `kami.scene` — portable scene snapshot and ECS-as-data schema.
- `kami.contracts.render` — render-IR frame and draw validation.
- `kami.contracts.ipc` — KAMI columnar frame layout validation.
- `kami.contracts.gpu` — GPU provider asset and packed-frame validation.
- `kami.contracts.rt` — ray-tracing recipe and backend-plan validation.
- `kami.contracts.sim` — simulation run config and step receipt validation.
- `kami.contracts.wit` — generated/check-only WIT text emitter from EDN worlds.

Primary EDN artifacts:

- `resources/kami/component_worlds.edn`

Run:

```sh
kbb -M:test
kbb -M:check-wit
```

Regenerate adapter WIT:

```sh
kbb -M:gen-wit --write wit/kami-component-worlds.wit
```
