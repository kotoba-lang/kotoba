# kotoba-fea

[![CI](https://github.com/kotoba-lang/fea/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/fea/actions/workflows/ci.yml)

**Finite-element analysis (FEA) domain logic in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library: mesh
generation, material library, boundary conditions, a dense-Cholesky
linear-static bar solver, and post-processing.

This is a from-scratch `.cljc` port of `kami-cae`, a Rust crate that lived
in `kami-engine` (`orgs/kotoba-lang/kami-engine`). `kami-cae` was deleted
from `kami-engine`'s working tree without being committed, as part of
retiring the Rust game-engine workspace in favor of pure-Clojure "kotoba"
authority repos (ADR-2607010000). This repo exists so that deletion loses
no domain knowledge — `kami-cae`'s full source is still recoverable via
`git show HEAD:kami-cae/src/lib.rs` in `kami-engine`'s history for as long
as that history exists, but the authority for this domain now lives here.

Named "fea" (not "cae"/"cae-solver") — `kotoba-lang/cae-solver` already
exists as an unrelated ROM/LBM CFD solve-dispatch contract.

No network, no I/O in any domain namespace (the one narrow exception,
`kotoba.fea.material`'s EDN-resource loader, is documented below). Pure
data + pure functions, portable `.cljc` across JVM / ClojureScript / SCI /
GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 98 tests, 294 assertions across 13 namespaces (JVM) and 79 tests, 248 assertions across 9 (portable nbb suite), all green |
| Solver scope | linear-static, `:beam2` + `:tet4`; isotropic thermal strain `:temperature`/`:reference-temperature`; `:pressure` face-set BCs; steady-state conduction (`:thermal-steady`); natural-frequency modal analysis for `:tet4` (`:modal`); Miner/Basquin spectrum fatigue; driveline/resonance separation (`:resonance`) |

## Thermal strain (tet4 + beam2)

`kotoba.fea.boundary/temperature` prescribes nodal temperatures; pass
`{:reference-temperature T0}` (Kelvin — caller-supplied, never assumed) as
the 4th argument to `solver/solve-linear-static`. The material model must
carry `:thermal-expansion` [1/K] (the built-in presets do). The solve
carries the isotropic initial strain eps_th = alpha (T − T0) as equivalent
nodal forces and subtracts it in stress recovery. tet4 results expose the
full 6-voigt mechanical stress via `:stress-voigt` — the von Mises scalar
alone reads 0 for the hydrostatic state that fully constrained thermal
expansion produces. `:pressure`/`:convection` BCs (constructed by
`kotoba.fea.boundary` but not implemented by this solver) are rejected
loudly (`:unsupported-bc-type`) instead of being silently dropped.

## What was ported

Namespace-for-module mapping from `kami-cae/src/lib.rs`:

| `kami-cae` (Rust) module | `kotoba.fea.*` (Clojure) namespace |
|---|---|
| `mesh` | `kotoba.fea.mesh` |
| `material` | `kotoba.fea.material` (+ `resources/kami/fea/materials.edn`) |
| `boundary` | `kotoba.fea.boundary` |
| `solver` | `kotoba.fea.solver` |
| `postprocess` | `kotoba.fea.postprocess` |
| `glam::DVec3` (dependency) | `kotoba.fea.vec3` |

`kotoba.fea` is the top-level overview namespace.

### Mesh

```clojure
(require '[kotoba.fea.mesh :as mesh])

(def m (mesh/generate-box-mesh 2.0 3.0 4.0 2)) ; width height depth divisions
(mesh/mesh-stats m) ;=> {:node-count 27 :element-count 8 :min-quality 1.0 :avg-quality 1.0}

(let [{m1 :mesh n0 :id} (mesh/add-node (mesh/new-mesh) [0.0 0.0 0.0])
      {m2 :mesh n1 :id} (mesh/add-node m1 [1.0 0.0 0.0])
      m3 (mesh/add-element m2 (mesh/beam2 0 [n0 n1]))]
  (mesh/create-node-set m3 "fixed" [n0]))
```

Seven element topologies (`:beam2` `:tri3` `:tri6` `:quad4` `:tet4`
`:tet10` `:hex8`) are represented as plain maps `{:type :id :nodes}`
instead of Rust's `FeaElement` enum + `NodeId`/`ElementId` newtype
wrappers — node/element ids are plain non-negative integers, the
idiomatic Clojure equivalent (no information lost: the wrapper types
carried no behavior beyond `Eq`/`Hash`).

### Material

```clojure
(require '[kotoba.fea.material :as material]
         '[kotoba.fea.material-loader :as loader])

(def presets (loader/presets)) ; JVM resource read
(material/find-material presets "Steel-Structural")
;=> {:name "Steel-Structural"
;    :model {:type :linear-elastic :youngs-modulus 2.0E11 :poissons-ratio 0.3
;            :density 7850.0 :thermal-expansion 1.2E-5
;            :thermal-conductivity 50.0 :specific-heat 490.0}}
```

The four built-in presets (Steel-Structural, Aluminum-6061,
Titanium-6Al4V, Concrete) were hardcoded constants in
`MaterialLibrary::{steel_structural,aluminum_6061,titanium_6al4v,concrete}`
— extracted verbatim to `resources/kami/fea/materials.edn` as data, per
this monorepo's Rust-crate-to-EDN+cljc port pattern
(`kotoba-lang/kami-scene-contracts`). `kotoba.fea.material` (`.cljc`) is
100% pure/portable — it never does I/O, not even reader-conditional
guarded. Loading the EDN resource is a separate, deliberately plain
`.clj` (not `.cljc`) namespace, `kotoba.fea.material-loader`, mirroring
`kami-scene-contracts/src/kami/scene/contracts.cljc`'s
`load-edn-resource` pattern but split out rather than reader-conditional
guarded in place — inline `#?(:clj ...)`-only `require`s inside a
`.cljc` `ns` form make `clj-kondo`'s `:cljs` analysis pass see an empty
`(:require)` and hard error (`Invalid require: no libs specified to
load`); splitting to a real `.clj` file sidesteps that cleanly and is
honest about the fact that this loader has no `:cljs` branch at all.
Callers on other hosts (cljs, SCI, GraalVM) read the same EDN file
(`kotoba.fea.material/presets-resource`) via their own host's I/O and
pass the parsed value to `find-material`/`add-material`, which are pure.

Rust's `MaterialLibrary` struct (a `Vec<FeMaterial>` + inherent methods)
has no idiomatic-Clojure counterpart worth keeping — a materials
collection is just a plain vector of material maps here.

### Boundary conditions

```clojure
(require '[kotoba.fea.boundary :as boundary])

(boundary/displacement "fixed" boundary/dof-all [0.0 0.0 0.0])
(boundary/force "load" [1000.0 0.0 0.0])
(boundary/dof-contains? boundary/dof-all boundary/dof-rz) ;=> true
```

`DofMask` was a `u8` bitmask (`X`/`Y`/`Z`/`RX`/`RY`/`RZ` const flags,
`union`/`contains` via bit-or/bit-and) — ported as keyword sets
(`#{:x :y :z}`) with `clojure.set/union`/`clojure.set/subset?`, the
idiomatic Clojure equivalent; no bit-twiddling helpers needed.

### Solver

```clojure
(require '[kotoba.fea.solver :as solver])

(solver/solve-linear-static mesh material bcs)
;=> {:analysis-id "linear-static-0" :displacement [...] :stress [...]
;    :strain [...] :max-displacement d :max-stress s}
```

Direct port of `solver::solve_linear_static` and its private
`cholesky_solve` helper (dense symmetric-positive-definite Cholesky
decomposition + forward/backward substitution) — same algorithm, same
row/column-elimination technique for displacement boundary conditions,
same zero-stiffness-DOF stabilization. `SolverError`'s four variants
(`SingularMatrix` / `UnsupportedElement` / `NoLoads` /
`NodeSetNotFound`) are ported as `ex-info` with `:type`
`:singular-matrix` / `:unsupported-element` / `:no-loads` /
`:node-set-not-found` — idiomatic Clojure error reporting in place of a
`thiserror` enum.

### Thermal (steady-state conduction — beyond upstream scope)

```clojure
(require '[kotoba.fea.thermal :as thermal])

(thermal/solve-thermal-steady mesh 167.0   ; k [W/(m*K)], e.g. Aluminum-6061 preset
                              [(boundary/temperature "hot" 400.0)
                               (boundary/temperature "cold" 300.0)])
;=> {:analysis-id "thermal-steady-0" :temperature [...] :flux [...]
;    :heat-flow [...] :reactions [...] :max-temperature T :min-temperature T}
```

`kami-cae` declared `ThermalSteady` as an enum case but never implemented
it; this repo does, as a new portable namespace `kotoba.fea.thermal`.
Linear isotropic steady conduction (`div(k grad T) = 0`) on `:beam2` and
`:tet4` elements, one temperature DOF per node, sharing the structural
solver's dense-Cholesky path (and, now public, its `tet4-grads` /
`tet4-volume` geometry kernels). Boundary conditions: prescribed
temperature (`:temperature`, node sets) and convection (`:convection`,
triangular face sets with the consistent h*A/12 matrix — register face
sets with `thermal/create-face-set` or pass node triples inline).
Units: temperature [K], k [W/(m*K)], h [W/(m^2*K)], heat flow [W].
`tet4-grads`/`tet4-volume` were made public in `kotoba.fea.solver` for
reuse (no other change to the structural solver). Acceptance invariant:
with no internal sources, `sum(:reactions) = 0` (or the convective loss
when convection is present); tests verify the exact linear field on a
1-D rod and a 6-tet unit cube.

`AnalysisType` (6 variants) and `SolverMethod` (3 variants) are ported as
data (`kotoba.fea.solver/analysis-types`,
`default-solver-method`/`conjugate-gradient-method`/`gmres-method`). Upstream
`kami-cae` only ever *implemented* `LinearStatic` + `DirectCholesky`;
`kotoba.fea.modal` now also executes `:modal` (natural-frequency) for
`:tet4` — the remaining variants (`:nonlinear-static` `:thermal-transient`
`:buckling`) are still declared-but-unimplemented. Same for mesh assembly: `kotoba.fea.mesh`
can construct all seven element topologies (full parity), but
`kotoba.fea.solver` only assembles `:beam2`, because that's all
`kami-cae`'s own `solve_linear_static` ever assembled — this isn't a
porting omission, it's upstream scope, preserved as-is
(`kotoba.fea/solver-assembly-support`).

### Postprocess

```clojure
(require '[kotoba.fea.postprocess :as pp])

(pp/field-range [1.0 5.0 3.0 7.0 2.0]) ;=> {:min 1.0 :max 7.0 :avg 3.6}
(pp/export-color-map-data result :von-mises-stress)
```

`export-color-map-data`'s `:safety-factor` path keeps the hardcoded
250 MPa mild-steel placeholder for kami-cae parity — **do not use it to
grade a real design**. The executable counterpart
`pp/factor-of-safety` takes a caller-supplied allowable stress that
**must** carry provenance (`{:source ... :basis ...}`) — an
unprovenanced allowable is rejected, the same fail-closed rule as
`kotoba.fea.convergence`'s caller-owned `fs`:

```clojure
(pp/factor-of-safety (:stress solver-result)
                     {:allowable-stress 200.0e6   ; Pa, from a dated source you own
                      :provenance {:source "AMS ..., 2026-09 retrieval" :basis :yield}})
;=> {:factors [...] :min-factor {:value v :element i} :allowable-stress ... :provenance ...}
```

`probe-point` is ported *including* its documented limitation:
upstream's own implementation only had `AnalysisResult` (no node
positions) at that call site, so despite the docstring promising
inverse-distance-weighted interpolation, it actually just returns the
average displacement across all nodes. Ported verbatim, limitation and
all, with a note in the docstring — fixing it would need node positions
threaded alongside the result, which is a real (not cosmetic) API change
left for a follow-up.

### Fatigue (new, not a port)

`kotoba.fea.fatigue` is **new** capability with no `kami-cae` counterpart:
Miner's-rule cumulative damage accumulation over constant-amplitude
spectrum blocks against a Basquin S-N curve, with an optional endurance
limit. It exists so a stress history (e.g. FEA-post-processed stress
ranges, or vehicle duty-cycle load spectra) can be turned into an
auditable cumulative-damage number. The contract is deliberately not a
material-property authority: every curve must carry `:provenance`
(`:source` + `:date`) or the call throws — unmeasured constants are never
assumed, and curve fixtures in tests are labelled illustrative-only.

```clojure
(require '[kotoba.fea.fatigue :as fatigue])

(def curve
  {:type :basquin :basquin-b -0.12 :basquin-C 1.0e11
   :endurance-limit-Pa 1.0e7
   :provenance {:source "<measured source>" :date "<measured date>"}})

(fatigue/spectrum-damage
  curve
  [{:stress-range-Pa 2.0e8 :cycles 1000.0}
   {:stress-range-Pa 1.0e7 :cycles 1.0e9}]) ;=> {:total-damage d
                                               :fatigue-margin (- 1.0 d)
                                               :non-damaging-blocks 1
                                               :criterion :miner-linear ...}
```

### Modal (natural frequency — beyond upstream scope)

`kotoba.fea.modal` executes the `:modal` `AnalysisType` / `:mode-shape`
`ResultField` that kami-cae only ever declared (both computed nothing in the
static solver). It is the executable counterpart for the
`:vibration-fatigue-and-safety` design domain: fundamental natural frequencies
let a designer separate motor excitation lines from structural resonance, and
a frequency response feeds the load spectrum `kotoba.fea.fatigue` consumes.

```clojure
(require '[kotoba.fea.modal :as modal])

(modal/solve-modal mesh material
                   [(boundary/displacement "fixed" #{:x :y :z} [0.0 0.0 0.0])])
;=> {:analysis-id "modal-0"
;    :frequencies-hz [...]   ; ascending, f = sqrt(lambda)/(2 pi)
;    :omega-1/s [...]        ; sqrt(lambda)
;    :mode-shapes [[[x y z] ...]] ...}
```

Free vibration solves (K - omega^2 M) phi = 0 on the free-DOF subspace: K is the
same linear-elastic stiffness the static solver assembles, M is the consistent
tet4 mass matrix from the material's `:density` (int_V N_i N_j dV = V/10 for
i=j, V/20 otherwise), Dirichlet displacement BCs eliminate the constrained
DOFs, and the symmetric generalized eigenproblem is reduced to standard form
with Cholesky and diagonalized by cyclic symmetric Jacobi. Applied loads
(`:force`/`:pressure`/`:temperature`/`:convection`) are rejected
(`:unsupported-bc-type`) — forced response is not free vibration. Scope is
`:tet4` only: beam2's transverse DOFs carry no stiffness, so a beam modal would
emit artifact rigid modes. An under-constrained structure reports true
near-zero rigid modes before the elastic ones — the caller reads those as
unanchored modes, not design facts. Dense matrices: educational / small-mesh.


### Resonance (driveline excitation ↔ structural natural frequency)

`kotoba.fea.resonance` is the executable counterpart to the goal
`kotoba.fea.modal` declares in its own docstring — that natural frequencies
let the designer separate motor excitation lines from structural resonance
before committing geometry — which on the landed plane had no contract that
actually does the separating. It is new, not a port.

```clojure
(require '[kotoba.fea.resonance :as resonance])

;; a driveline at 3600 rpm = 60 rev/s, first four harmonics
(def lines (resonance/engine-harmonics-hz 60.0 [1 2 3 4]))

;; how far each harmonic sits from the structure's natural frequencies
(resonance/resonance-separation (:frequencies-hz modal-result) lines)
;=> {:lines [{:order 1 :frequency-hz 60.0 :nearest-natural-hz f :separation-frac s} ...]
;    :min-separation-frac s :worst-case {...}}

;; then the caller's sourced no-resonance band as the acceptance gate
(resonance/resonance-acceptance
  (:frequencies-hz modal-result) lines
  {:min-separation-frac 0.10
   :provenance {:source "<no-resonance band spec>" :date "2026-09-08"}})
;=> {:passed? bool :at-risk n :lines [{... :pass? bool} ...]
;    :provenance {...} :unmeasured {...}}
```

The executed math is exact and compositional: `engine-harmonics-hz` is the
identity `f-order = n × rev-s`; `resonance-separation` is
`|f-exc − f-nat| / f-nat` to the nearest natural frequency; the acceptance
band is a caller decision that MUST carry `:provenance` or the call refuses
(fail closed, same rule as `kotoba.fea.fatigue`). No Mg/MgH2, PEM, thermal,
fatigue, or performance constant is invented — the driveline speed, the
orders present, the natural frequencies, and the exclusion band are all
caller measurements. Damping ratio, excitation amplitude, and material
damping are reported on every result as declared `:unmeasured` — a
separation ratio alone is not a resonance verdict, it is the auditable
input to one.


## What was intentionally left unported, and why

**Nothing was skipped for GPU/wgpu-rendering, OS-syscall, or
wasm-bindgen-bridge reasons** — unlike other `kami-eng-*` crates,
`kami-cae` contained none of that. It declared `kami-eng-core` and
`kami-eng-render` as `Cargo.toml` dependencies but never actually
`use`d either crate anywhere in `lib.rs` (verified: `git show
HEAD:kami-cae/src/lib.rs | grep kami_eng` in `kami-engine` returns
nothing) — the only reference is a doc comment noting that
`export_color_map_data`'s output is *intended* for consumption by
`kami-eng-render`'s color-map pipeline, which is a downstream
host-adapter concern (GPU rendering) outside this repo's scope by
construction, not something to port here. The entire `kami-cae` crate
(mesh, material, boundary, solver, postprocess, and all five inline
`#[test]`s) was pure algorithmic/data logic and has been ported in full.

Representation-only changes (no information lost):

- `NodeId`/`ElementId` newtype wrappers -> plain integers.
- `serde`/`serde_json` (Rust serialization) -> not needed; EDN is
  Clojure's native serialization.
- `thiserror`'s `SolverError` enum -> `ex-info` with `:type`.
- `log` (Rust logging) -> not ported; no logging in domain namespaces,
  consistent with this monorepo's no-I/O convention for `.cljc` domain
  code.

## Tests

Parity tests for all five of `kami-cae`'s inline `#[test]`s, using the
same concrete expected values as the Rust originals:

- `material-library-presets-test` <- `test_material_library_presets`
- `box-mesh-generation-test` <- `test_box_mesh_generation`
- `boundary-condition-creation-test` <- `test_boundary_condition_creation`
- `bar-fea-solve-test` <- `test_1d_bar_fea_solve` (single bar element,
  E = 200 GPa, F = 1000 N -> u = 5e-9 m, sigma = 1000 Pa; same tolerances)
- `field-range-calculation-test` <- `test_field_range_calculation`

Plus additional coverage for error paths (`:no-loads`,
`:node-set-not-found`), `cholesky-solve` against a known 2x2 system, and
`postprocess`'s remaining `ResultField` branches.

```bash
kbb -X:test
kbb -M:lint
```

## License

Apache License 2.0.
