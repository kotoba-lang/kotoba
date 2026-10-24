# ADR-0001: shadow-css-compatible static CSS contract

- Status: Accepted
- Date: 2026-07-20

## Decision

`kotoba-lang/css` follows shadow-css semantics: CSS forms are static, the UI receives a
source-position-derived class string, source files are indexed at build time, only reachable/requested
styles are emitted, and browsers pay no CSS-generation runtime cost. Utility keywords, declaration maps,
pass-through class strings, deterministic output, minification and external CSS inclusion are supported.

Portable EDN sheets, material-token compilation and native-renderer data are additive extensions. They must
not change the meaning of the shadow-compatible class DSL. Dynamic values use ordinary conditional classes,
inline style or CSS custom properties, not runtime stylesheet generation.

App repositories may compose sheets and choose outputs, but must not implement their own CSS serializer,
source indexer, minifier or Tailwind/Node-only parallel pipeline.
