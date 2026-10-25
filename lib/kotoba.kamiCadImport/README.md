# kami-cad-import

`src/cad_transform_golden.kotoba` is the policy-v7 safety qualification slice
for quaternion-derived scaled affine point transforms and parent/child
composition. Tests compare the existing CLJC transform oracle with the Kotoba
reference executor, restricted JavaScript, and typed Wasm without capabilities.

CAD/GLTF/SCAD/STEP parsing, string metadata, general matrices, AABB collections,
and asset emission remain CLJC boundaries until bounded parsers and a structured
f64 collection/record ABI are qualified.

CAD source (STEP / glTF / OpenSCAD) -> vehicle part graph -> JBeam topology
+ CycloneDX 1.5 SBOM, restored as portable zero-dependency CLJC.

Restored from the deleted `kami-cad-import` Rust crate
(`kotoba-lang/kami-engine`, removed in PR #82, "Remove Rust workspace"), per
[ADR-2607010930](../../90-docs/adr/) (kami-engine crate restoration wave).
Original design reference: ADR 2605051430 (CAD -> JBeam/SBOM pipeline).

Bridges CAD/parametric source to `kami-vehicle` (soft-body sim, also
restored to CLJC under the same ADR — see `kotoba-lang/kami-vehicle`'s
`vehicle.*` namespaces) and `sbom.etzhayyim.com` (CVE / recall pipeline).
Every part carries provenance — without it the emitters refuse to produce
output.

## Why two outputs from one part graph

Without a single source of truth the simulator and the SBOM drift apart. A
part that exists in physics but not in the SBOM hides supplier-quality
risk; a part that exists in the SBOM but not in physics produces fake CVE
matches. Same `VehicleAssembly`, two emitters, no drift.

## Pipeline

```
STEP / glTF / OpenSCAD source
   |
   v
cad-import.part/VehicleAssembly { parts hardpoints }
   |   |
   |   +--> cad-import.jbeam-emit/emit  -> JBeam data (vehicle.jbeam/load-edn-ready)
   +--> cad-import.sbom/emit        -> CycloneDX 1.5 data -> sbom.etzhayyim.com
```

Unlike the original Rust crate, `jbeam-emit/emit` and `sbom/emit` return
plain Clojure maps rather than JSON strings — this crate has no
JSON-library dependency (zero-dependency requirement, ADR-2607010930).
Callers that need JSON text run the returned map through whatever JSON
library they already depend on; callers that want to load JBeam data
straight into a `vehicle.Vehicle` can pass `jbeam-emit/emit`'s result
straight to `vehicle.jbeam/load-edn` with no serialisation round-trip at
all.

## Modules restored

| namespace | ported from | lines | what |
|---|---|---:|---|
| `cad-import.xform` | (new — `glam` replacement) | 108 | portable vec3 / quaternion / 3x3-affine-transform helpers used by the ingest adapters |
| `cad-import.part` | `src/part.rs` | 219 | `VehicleAssembly` / `VehiclePart` / `Hardpoint` data model, validation |
| `cad-import.jbeam-emit` | `src/jbeam_emit.rs` | 273 | `VehicleAssembly` -> JBeam node/beam/wheel topology (AabbCube / AabbHull20 / WheelRing strategies) |
| `cad-import.sbom` | `src/sbom.rs` | 220 | `VehicleAssembly` -> CycloneDX 1.5 SBOM (device components, purl synthesis, dependency graph) |
| `cad-import.register` | `src/register.rs` | 95 | SBOM registration request builder for `sbom.etzhayyim.com`'s XRPC endpoint, plus a `curl(1)` command builder |
| `cad-import.ingest.gltf` | `src/ingest/gltf.rs` | 271 | glTF 2.0 subset reader — node hierarchy, TRS/matrix transforms, POSITION-accessor AABBs, `extras.gftd_part`/`gftd_vehicle`/`gftd_hardpoints` annotation contract |
| `cad-import.ingest.scad` | `src/ingest/scad.rs` | 92 | OpenSCAD-style parametric primitive (Sphere/Cube/Cylinder) -> `VehicleAssembly` ingest |
| `cad-import.ingest.step` | `src/ingest/step.rs` (partial) | 46 | FreeCAD console-script builder only — see "What was not ported" below |
| `cad-import.demos.synth-sedan` | `src/demos/synth_sedan.rs` | 84 | 9-part synthetic sedan reference assembly |
| `cad-import.demos.roadster` | `src/demos/roadster.rs` | 189 | 33-part Miata-class roadster reference assembly (parametric SCAD primitives) |
| `cad-import.demos`, `cad-import.ingest`, `cad-import` | `src/demos.rs`, `src/ingest.rs`, `src/lib.rs` | 42 | module aggregators / root namespace |

## What was not ported

`cad-import.ingest.step`'s `from-step-file` (the original `from_step_file`)
shelled out to the `freecad`/`freecadcmd` CLI binary
(`std::process::Command`) to convert STEP/IGES to an intermediate glTF
file. That is inherently a native, OS-process, filesystem-touching
operation with no portable CLJC equivalent — it is not a *data
transformation* in the sense the rest of this crate is, and is out of
scope for the zero-dependency portable-CLJC restoration mandate
(ADR-2607010930). The pure part — `freecad-script`, the FreeCAD console
script template — is ported; a JVM-hosted caller that needs the actual
conversion can shell out itself (e.g. via `clojure.java.shell/sh`) using
that template, then feed the resulting glTF through
`cad-import.ingest.gltf/from-gltf-map`.

## Tests

All applicable original Rust `#[test]`s ported 1:1, across 8 original test
modules (6 `#[cfg(test)]` unit-test modules + 2 `tests/*.rs` integration
files) plus a namespace-loads smoke test for the root namespace:

- `cad-import.part-test` — 6 tests (assembly validation, break-group rollup)
- `cad-import.jbeam-emit-test` — 5 tests (AabbCube/AabbHull20/WheelRing strategies, hardpoint anchoring, node/beam referential integrity)
- `cad-import.sbom-test` — 8 tests (CDX 1.5 structure, purl synthesis, evidence, dependency graph, deterministic serial numbers)
- `cad-import.register-test` — 5 tests (request envelope, auth header, curl command)
- `cad-import.ingest.scad-test` — 5 tests (primitive AABBs, transform composition, annotated round-trip)
- `cad-import.ingest.gltf-test` — 9 tests (node hierarchy, TRS/rotation AABB growth, annotation contract, strict vs. auto-part-kind modes)
- `cad-import.ingest.step-test` — 2 tests (adapted — see "What was not ported")
- `cad-import.demos.roadster-test` — 1 test (33-part topology)
- `cad-import.jbeam-loadback-test` — 6 tests, **integration** against `vehicle.jbeam/load-edn` (kotoba-lang/kami-vehicle): proves the emitted JBeam data is semantically valid, not just structurally well-formed — exact node/beam counts (432 nodes / 1221 beams for the roadster, 132 nodes for the synth sedan) match the original Rust integration test's asserted values byte-for-byte
- `cad-import.jbeam-physics-smoke-test` — 4 tests, **integration**: loads each demo through the full emit -> load chain, steps the simulator for ~1-3 seconds via `vehicle.vehicle/step`, and checks finite positions, bounded centre-of-mass drift, bounded beam breakage, tire-ring deformation under load, and throttle-driven forward motion
- `cad-import-test` — 1 namespace-loads smoke test

**53 tests / 1184 assertions, 0 failures, 0 errors.**

Run with:

```bash
kbb -M:test
```

(pulls `kotoba-lang/kami-vehicle` as a test-only dependency for the two
integration test namespaces above; the crate's `src/` itself remains
zero-dependency).
