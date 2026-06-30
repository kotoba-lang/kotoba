# kotoba-kotodama legacy migration root

This tree is no longer the canonical home for product/domain actors.

Canonical ownership:

- Generic language/runtime substrate remains in `kotoba-lang/kotoba`.
- Domain actors and cells move to `etzhayyim/com-etzhayyim-*` as `.cljc`.
- AT Protocol actors, PDS/AppView, and XRPC app surfaces move to
  `gftdcojp/app-aozora`.
- Hosting, placement, fleet, gateway, and operational runtime code moves to
  `kotoba-lang/murakumo`.

Do not add new domain `cell.py`, Python UDF, AT Protocol actor, or hosting code
here. Use `bb scripts/kotoba-boundary-audit.bb --edn` from the west topdir to
classify remaining legacy files and choose the target repository.

Layout:

- `sdk/kotoba-kotodama-host-sdk`: TypeScript host SDK
- `hosts/kotoba-kotodama-kami-host`: native KAMI host
- `hosts/kotoba-kotodama-desktop-host`: desktop host scaffold
- `inference/kotoba-kotodama-inference`: Rust inference runtime
- `config/kotoba-kotodama-config`: shared Rust config crate
