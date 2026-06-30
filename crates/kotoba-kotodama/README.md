# kotoba-kotodama legacy redirect root

This tree is no longer the canonical home for product/domain actors.

Canonical ownership:

- Generic language/runtime substrate remains in `kotoba-lang/kotoba`.
- Shared WASM/CLJC inference runtime lives in `kotoba-lang/inference`.
- Host SDK, Rust config, and native host crates live in
  `kotoba-lang/kotodama-host`.
- MCP server packages live in `kotoba-lang/kotodama-mcp`.
- Cell manifests and generated cell packages live in `kotoba-lang/kotodama-cells`.
- Python worker layer lives in `kotoba-lang/kotodama-py`.
- Holochain runtime lives in `kotoba-lang/kotodama-holochain`.
- Domain actors and cells move to `etzhayyim/com-etzhayyim-*` as `.cljc`.
- AT Protocol actors, PDS/AppView, and XRPC app surfaces move to
  `gftdcojp/app-aozora`.
- Hosting, placement, fleet, gateway, and operational runtime code moves to
  `kotoba-lang/murakumo`.

Do not add new domain `cell.py`, Python UDF, AT Protocol actor, or hosting code
here. Use `bb scripts/kotoba-boundary-audit.bb --edn` from the west topdir to
classify remaining legacy files and choose the target repository.

Layout:

- `sdk/README.md`: redirect to `kotoba-lang/kotodama-host`
- `hosts/README.md`: redirect to `kotoba-lang/kotodama-host`
- `config/README.md`: redirect to `kotoba-lang/kotodama-host`
- `inference/README.md`: redirect to `kotoba-lang/inference`
- `mcp/README.md`: redirect to `kotoba-lang/kotodama-mcp`
- `cells/README.md`: redirect to `kotoba-lang/kotodama-cells`
- `py/README.md`: redirect to `kotoba-lang/kotodama-py`
- `holochain/README.md`: redirect to `kotoba-lang/kotodama-holochain`
