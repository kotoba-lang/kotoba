# ADR 0002: Keep W3C bindings separate from the KAMI WebGPU renderer

- Status: Accepted
- Date: 2026-07-15

## Decision

The dependency direction is:

`kotoba-lang/render` quality plan → `kotoba-lang/webgpu` executor →
`kotoba-lang/org-w3-webgpu` binding → browser WebGPU API.

`org-w3-webgpu` remains a thin, opinion-free, one-function-per-spec-call
binding. It must not own EDN render graphs, materials, shaders, LOD, quality
profiles, fallback policy, or scene semantics.

`webgpu` owns KAMI's browser execution policy: render-IR interpretation,
resource/pipeline construction, draw submission, WebGL2 fallback, and explicit
capability resolution. Unsupported quality-plan features are reported as
degradation evidence rather than silently advertised as rendered.

## Consequences

The standards binding can track W3C API changes independently. KAMI can evolve
its renderer without turning a nominal standards package into an engine API.
Backends remain replaceable consumers of the same `kotoba-lang/render` plan.
