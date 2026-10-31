# kami-engine-cae-solver

[![CI](https://github.com/kotoba-lang/kami-engine-cae-solver/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-engine-cae-solver/actions/workflows/ci.yml)

The CAE solver **contract**: one `solve` multimethod dispatching on `[:solver :kind]`, so a case is answered by a portable reduced-order backend today and a dedicated high-fidelity host adapter tomorrow with no caller change.

`cae.backend/backend` also implements the unified `kotoba.physics.contract` at
`:high-fidelity`. Kami Engine and Network Isekai can use one immutable
scene/case/result envelope for realtime physics, vehicle models and CAE.
Existing `cae.solver/solve` methods remain compatible behind the adapter.
Missing V&V evidence defaults to not qualified; execution never implies an
industrial release.

`cae.industrial` provides deterministic, zero-dependency reference backends:

| kind | Coverage |
| --- | --- |
| `:cfd` | duct/ventilation flow, straight/fitting pressure-loss breakdown, fan power, heat removal, steady combustion heat source |
| `:fem` | axial bar / cantilever beam deformation, stress, first mode, fatigue life |
| `:fatigue` | Miner's-rule cumulative damage over a caller-supplied load spectrum (Basquin SN curve + optional Goodman mean-stress correction); the SN curve must be supplied by the caller |
| `:process` | welding heat input, casting energy/Chvorinov solidification time, rolling force |
| `:materials` | constant-rate / Arrhenius-JMAK phase transformation and resulting hardness |
| `:emag` | three-phase motor power/torque/losses and induction-heating workpiece temperature rise |
| `:production-des` | discrete-event throughput, utilisation, waiting, transport, lead time, WIP and busy-time energy |

Load `cae.industrial` before dispatching so its methods are registered:

```clojure
(require '[cae.industrial] '[cae.solver :as cae])
(cae/solve {:solver {:kind :cfd}
            :flow-m3-s 1.2 :duct-diameter-m 0.4 :duct-length-m 20.0})
```

Every result identifies its `:fidelity` (`:reduced-order`), `:status`
(`:screening-only`), `:model`, SI unit system, and modelling assumptions; an
optional `:case/id` is carried through unchanged. Inputs are validated for
finite values and physical bounds before a result is calculated. These models
are therefore suitable for early design-space exploration and simulation
orchestration, but not as a substitute for validated, high-fidelity CAE or
manufacturing release signoff.

For a design sweep or a set of factory scenarios, `cae.orchestration/run-cases`
isolates each failure and retains the input order. It returns one envelope per
case (`:succeeded` with `:result`, or `:failed` with data-only `:error`), while
`summary` reports total, succeeded, failed, and solver-kind counts. This makes
the reference solvers safe to use as one branch of a larger CAD/BIM → OpenUSD
or production-planning workflow.

`cae.interchange/attach-provenance` binds a validated source reference to a
case. It supports `:cad`, `:bim`, `:equipment`, and `:openusd`; OpenUSD inputs
require both an asset URI and absolute prim path. The source URI, revision,
coordinate convention, and scale are copied into every solver result, making
the model used for a screening result explicit without making this library a
CAD/BIM/USD parser.

`cae.assessment/assess` evaluates solver outputs against explicit engineering
limits such as `{:pressure-drop-Pa {:max 500.0}}` or
`{:safety-factor {:min 1.5}}`. Missing and non-finite values are always
failed, while invalid acceptance configuration is rejected separately. The
assessment retains case, solver, model, and provenance information so it can
serve as auditable design-review or manufacturing-gate evidence.

For design-space exploration, `cae.study/parameter-sweep` varies a nested case
parameter while preserving input order and isolating invalid points.
`central-sensitivity` produces a traceable central finite-difference derivative
for any finite result metric. Both work against the common solver contract, so
the study remains valid when a host replaces a screening model with a dedicated
CAE adapter.

Part of the clean-sheet vehicle-design / CAE stack (purpose-split shared libs).
Zero-dep portable `.cljc`. Run `kbb -M:test`.

## CLJS / Node smoke test

The same source executes under ClojureScript through NBB (no JVM solver
fallback). With [NBB](https://github.com/babashka/nbb) installed, run:

```sh
kbb --backend sci -cp src:test -e "(require '[cae.cljs-smoke-test])"
```

It executes CFD (fittings + combustion), FEM beam, Arrhenius materials,
induction heating, production energy, OpenUSD provenance, assessment, batch
failure isolation, and sensitivity analysis in the Node/CLJS runtime.

## High-fidelity reference contracts

`cae.high-fidelity` and `cae.verification` expose portable numerical reference
kernels behind the same `cae.solver/solve` dispatch:

| kind | Contract |
| --- | --- |
| `:fvm-compressible` | 1D conservative Euler finite-volume update with Rusanov flux; `:sod-shock-tube` initial condition and density/pressure profiles |
| `:rans-k-epsilon` | 1D k–epsilon transport reference with diffusion, production, dissipation and standard constants |
| `:combustion-reaction` / `:boundary-layer` | Arrhenius reaction and laminar/turbulent boundary-layer correlations |
| `:fem-elastoplastic` / `:finite-strain-elastic` | return-mapping plasticity and finite-strain Neo-Hookean reference response |
| `:friction-contact` / `:friction-contact-3d` / `:fracture-criterion` | penalty contact, Coulomb friction cone and stress-intensity failure criterion |
| `:fem-mesh` / `:mesh-quality` / `:adaptive-mesh` | TRI3/TET4 generation, area/volume quality and gradient-marked refinement |
| `:mpi-domain` / `:mpi-halo-exchange` / `:mpi-load-balance` | deterministic partition, ghost indices, halo synchronization and weighted rank balancing |
| `:material-database` | temperature-dependent SS304, Al6061, water and air properties |
| `:benchmark-suite` / `:benchmark-catalog` / `:experimental-comparison` / `:validation-report` | analytic Poiseuille/bar/wall checks, Sod/Taylor/cantilever metadata, experimental RMSE/bias and aggregate regression gate |

These kernels are deliberately labelled `:fidelity :*-reference` and
`:status :screening-only`. They define a deterministic CLJ/CLJS boundary for
swapping in validated CFD/FEM/MPI implementations; they do not claim commercial
solver verification or manufacturing release authority.

## Numerical V&V and qualification gates

### Repo-wide maturity data

`resources/cae/maturity.edn` is the versioned maturity SSoT for this solver and
the connected `physics`, `physics-2d`, `kami-engine-vphysics`, `kami-engine`
and `network-isekai` repositories.  It scores implementation, numerical
verification, experimental validation, software quality and integration on a
0--5 rubric, retains evidence links for every component and computes both a
0--5 score and percentage.  The current evidence-backed aggregate is
`2.40/5.00` (`48.0%`); this is not an industrial-readiness claim.

Run `kbb -M:dataset -m report-maturity` to emit the full numeric EDN report.
`cae.maturity/tx-data` emits portable entity maps accepted by DataScript and
Datomic.  The committed schemas are `cae/maturity-datascript-schema.edn` and
`cae/maturity-datomic-schema.edn`; `all-components-query` and
`repo-summary-query` are reusable Datalog queries.  Updating a score requires
updating its evidence in the same EDN entity, making maturity changes
reviewable rather than hidden in UI code.

Hugging Face datasets are governed by the same fail-closed rule.
`resources/cae/datasets.edn` contains only commercial-compatible, immutable
40-character revisions with per-file SHA-256 and byte sizes. Z24 bridge
vibration (MIT) and MCC5-THU motor current/vibration (MIT) are pinned as
experimental candidates; missing measurement uncertainty keeps both outside
industrial qualification until a defensible uncertainty model is sourced.
HiLiftAeroML (CC-BY-4.0) is pinned only as a simulation reference, never as an
experiment. Non-commercial Intel welding and SURF data plus license-unverified
FactoryNet are isolated in `cae/dataset-quarantine.edn`; the standard downloader
rejects them before network access. Large experimental archives are opt-in:
`scripts/download_hf_datasets.sh z24-bridge-processed` or
`scripts/download_hf_datasets.sh mcc5-thu-motor`.
The Z24 archive has now been downloaded in full and byte-verified. Its NPY
semantics are also gated: little-endian float32 input must be exactly
`[1530,27,6000]`, and little-endian int64 labels exactly `[1530]`, both
C-order. Existing verified files are reused but rehashed on every invocation;
a cached file cannot bypass integrity checking. Content and structure pass,
while experimental qualification remains blocked by missing measurement
uncertainty.
Deeper FEM-readiness inspection also found that the processed card omits sample
frequency, sensor coordinates/directions and the physical meaning of its 17
labels; it declares float64 although the pinned bytes are float32. Therefore
`z24-fem-validation-readiness` rejects frequency and mode-shape correlation
until all five provenance gaps are resolved from an authoritative original
source. No normalized FFT bin is relabeled as Hz.

`cae.vv` provides fail-closed evidence checks for a narrowly declared solver
scope. A passing `:qualification-gate` requires all of the following, not just
a regression test:

- an independently evaluated analytic/public benchmark;
- integral conservation with a scale-aware relative imbalance;
- a finite iterative residual history meeting both final tolerance and
  reduction requirements;
- a monotonic three-grid study with observed order, Richardson extrapolation,
  and fine-grid GCI below its declared tolerance;
- complete traceability for case, solver/version, model revision, input, mesh,
  execution time, and platform.

Missing or failed evidence returns `:status :not-qualified` and
`:claim :no-industrial-accuracy-claim`. Passing evidence returns only
`:verified-for-declared-scope`; it never promotes the whole package to a
commercial-fidelity claim. The Poiseuille and axial-bar analytic benchmarks
now execute the actual `:cfd` and `:fem` solver paths instead of copying the
analytic answer into the computed field.

The `:axial-bar-fe` benchmark assembles and solves a real linear-element
stiffness system for a sinusoidal distributed load. `:axial-bar-vv-study`
runs 8/16/32-element meshes and derives analytic error, force equilibrium,
algebraic residual reduction, observed order, Richardson extrapolation and
GCI from those solver runs. This scope can pass as
`:verified-for-declared-scope`; it does not qualify other FEM models.

The compressible FVM update is expressed as the difference of shared Rusanov
interface fluxes. Every run reports initial/final conserved quantities,
integrated boundary outflow, conservation defect and time-step update norms.
An explicit transient update norm is deliberately not mislabeled as an
iterative residual.

## Reproducible external datasets

`resources/cae/datasets.edn` pins Hugging Face repositories to immutable
40-character revisions and records license, origin, intended use, commercial
permission, validation independence, citation, split, byte size and SHA-256.
`kbb -M:dataset -m verify-external-dataset aethron-cfd-pinn` downloads only the
manifested files and rejects any size/hash drift. CI executes this byte-level
check on JDK 21.

Dataset provenance is not accuracy evidence by itself. `cae.dataset` rejects
synthetic and simulation-only datasets as independent experimental validation,
and rejects non-commercial licenses from a commercial qualification claim.
The current registry includes pinned metadata for RealPDEBench, PDEBench 1D
compressible flow, RAE2822 CFD and CMU SFEM. RealPDEBench contains paired real
and simulated trajectories, but its CC-BY-NC-4.0 license makes it unsuitable
for commercial qualification. The small pinned Aethron CFD CSV is downloaded
in CI, but remains training-only synthetic data.

The registry also content-pins the NIST MIDAS experimental compression data
for annealed AISI 1045 steel. Run
`kbb -M:dataset -m verify-external-dataset nist-midas-1045-dynamic-plasticity`
to download the NIST CSV over HTTPS, reject byte/hash drift, parse its experiment
blocks, and reproduce paired published-model residual statistics. The source
does not publish per-sample measurement uncertainty, so the resulting report is
explicitly a calibration correlation—not independent validation or a released
production material card.

`resources/cae/qualification-matrix.edn` separately tracks numerical
verification, independent experimental validation and software quality for
each applicability scope. `cae.vv/industrial-release-gate` requires all three,
complete traceability, and explicit included/excluded conditions; numerical
verification alone cannot produce an industrial release claim.

The registry also pins the NASA/TMBWG Smooth-Body Separation Experiment OFI
measurements at a fixed Git commit under CC0-1.0. CI verifies the repository
license and three Mach-condition data files by SHA-256 and byte count, parses
the measured skin-friction coefficient together with each sample's `e_Cf`
uncertainty, and marks the dataset itself eligible for commercial independent
validation. The corresponding RANS solver scope remains not release-qualified:
qualified experimental data is now available, but this package does not yet
produce a verified prediction for that geometry. `experimental-validation-check`
performs normalized-RMSE and uncertainty-envelope coverage checks when such
predictions become available.

The same immutable NASA revision now also pins the two as-designed MADCAP IGES
halves (`speedBump_v3a.igs` and `speedBump_v3b.igs`), totaling 39,487,986
bytes. Download verification checks their SHA-256, declared inch unit and NURBS
surface records. `cae.sbse-geometry` independently implements the published
3D Gaussian/error-function surface at L=0.9144 m and emits a deterministic
triangulated STL. This establishes geometry provenance; it does not yet prove
an as-built CMM match, volume-mesh quality or RANS accuracy.

`kbb -M:dataset -m run-openfoam-sbse-mesh-evidence` generates a body-fitted
3D structured-Hex test-section mesh directly from that parametric surface. The
first accepted grid contains 27,648 cells and passes full OpenFOAM topology and
geometry checks with one region, positive volume, 34.21-degree maximum
non-orthogonality and 0.4456 maximum skewness. Every generated dictionary and
`polyMesh` file is hashed. This is the coarse RANS grid; y+ suitability, grid
convergence and experimental correlation remain separate required gates.

`kbb -M:dataset -m run-openfoam-sbse-rans-evidence` now generates and
executes a real 3D OpenFOAM v2506 k-omega SST case on that grid. The inlet uses
the Mach 0.1 OFI header values (`Uinf=34.59 m/s`, `P=99 kPa`, `T=21.3 C`,
`RH=81%`); moist-air density, Sutherland viscosity, Reynolds number, `k` and
`omega` are derived and recorded, while turbulence intensity and length scale
are explicitly marked as model assumptions. SIMPLE converges in 1,607
iterations. The floor wall-function result spans y+=11.72--413.41, so the
single coarse grid is not uniformly inside a defensible wall-function range.
Nearest-face comparison against all 20 Mach 0.1 OFI samples gives Cf RMSE
`0.0048801`, zero samples inside their experimental uncertainty, and 32.74 mm
maximum sampling distance. Execution is qualified, but experimental
correlation and industrial accuracy are deliberately rejected. Three-grid
near-wall refinement is required before reevaluation.

The next refinement family is defined in `cae.sbse-grid-study`: 41,472,
139,968 and 331,776 cells with effective refinement ratios 1.5 and 1.333.
Unlike an invalid single-block extreme grading attempt, each mesh uses a
surface-following 50 mm inner block (40/60/80 cells, grading 500) connected to
a smoothly graded outer block. The coarse first layer is about 17 micrometres
with a 1.173 expansion ratio. Its FVM acceptance gate requires positive volume,
one region, non-orthogonality below 40 degrees, skewness below 2 and no concave
cells; high-aspect/tet-decomposition/determinant warnings are retained rather
than hidden. Low-Re SST selects `nutLowReWallFunction`, bounded upwind transport
and a potential-flow initializer. The first steady coarse attempt remained
above the declared residual limits, so no grid-convergence or validation claim
is made; transient URANS time averaging is the next required solve path.

`kbb -M:dataset -m run-openfoam-sbse-urans-evidence` implements that path
with adaptive PIMPLE, Euler time integration, strict final pressure correction,
low-Re SST, `fieldAverage`, area-averaged wall-shear time series and optional
OpenMPI decomposition. A short 0.002 s coarse-grid pilot completes 200 stable
steps with maximum Co 0.01685 and floor y+=0.031--1.051 (average 0.766). The
last two equal Cf windows differ by 0.83%, but their normalized slope is 2.65%
against a 2% limit, so execution and wall resolution pass while statistical
stationarity remains not qualified. `renumberMesh` is deliberately prohibited
for this high-aspect layered grid: it increased computed maximum
non-orthogonality from 32.50 to 76.67 degrees. Four-rank OpenMPI decomposition
is supported and balance-audited, but was slower for the 41k-cell pilot; rank
selection for the 140k/332k grids must be based on measured scaling.

The coarse pilot has also been resumed from its written `0.005 s` checkpoint
to `0.01 s`, proving `startFrom latestTime` continuation without regenerating
the mesh or overwriting the initial fields.  A conservative `3e-6 s` maximum
step kept maximum Courant number at 0.03597; the final fields remained bounded
(`max|U|=50.2491 m/s`, `max(k)=16.5185 m2/s2`) with no turbulence bounding and
floor y+=0.026--1.203.  The 96-sample wall-shear series is not stationary
(11.22% half-window drift and 5.73% normalized slope), so the pilot waiver
qualifies execution only and is recorded separately from the failed
stationarity check.  A trial at `4e-5 s` produced an unsafe turbulence growth;
the generator therefore rejects requested maximum steps above `2e-5 s`.
Longer physical time, rather than a looser numerical step, is required next.
Production qualification now independently requires at least three domain
flow-throughs before averaging and five flow-throughs in the averaging window.
At 34.59 m/s one flow-through is 0.07931 s; the 0.01 s pilot therefore has only
0.013 warm-up and 0.113 averaged flow-throughs.  A pilot may waive this cost for
execution testing, but cannot obtain temporal-coverage or stationarity
qualification from that waiver.

As a reproducible RANS baseline,
`kbb -M:dataset -m run-openfoam-bump-rans-evidence` executes the official
NASA TMR 2D bump verification case with OpenFOAM v2506 and k-omega SST. Kotoba
statically expands the NASA analytic bump into 100 spline points, eliminating
the tutorial's runtime C++ `codeStream`. The 13,770-cell solve converges in
1,984 SIMPLE iterations and records Cp, wall shear and y+ with hash-complete
evidence. `checkMesh -allGeometry` retains two boundary-layer quality warnings;
this is a solver-execution baseline, not the 3D Boeing SBSE experiment and not
an experimental validation claim.

## Real external solver execution

`resources/cae/external-solvers.edn` pins OpenFOAM v2506 to an ARM64 OCI image
digest. `kbb -M:dataset -m run-openfoam-evidence` copies the image's own
`icoFoam/cavity` tutorial, hashes every input dictionary, executes the real
`blockMesh` and `icoFoam` binaries, parses residual/Courant/continuity records,
hashes the logs and final fields, verifies the local image digest, and emits an
EDN evidence envelope. No shell command or unpinned image reference comes from
the case payload.

The committed run in `resources/cae/evidence` completed 100 time steps to
`t=0.5` with maximum Courant number 0.852134 and final cumulative continuity
error `-4.17776e-18`. This proves real process execution and traceability, not
general OpenFOAM solution accuracy; its qualification-matrix scope explicitly
excludes an accuracy or design-signoff claim.

The same evidence path now executes CalculiX 2.21 from a locally built ARM64
container whose Ubuntu base digest and `calculix-ccx=2.21-1` package version are
fixed in `containers/calculix/Dockerfile`. Run
`kbb -M:dataset -m run-calculix-evidence` to solve the committed C3D8 unit
cube, hash its INP/log/FRD/STA/CVG files, parse the actual FRD displacement
field, and compare maximum axial displacement with the closed-form 0.001 m
answer. The committed run has eight nodal samples and zero relative error for
that quantity. This narrowly verifies linear, small-strain axial response; it
does not qualify nonlinear contact, plasticity, large deformation, fracture,
or arbitrary industrial models.

`kbb -M:dataset -m run-mpi-evidence` verifies a real four-rank OpenMPI
4.1.6 runtime in a digest-pinned ARM64 container. The clean-room Kotoba worker
distributes one million midpoint-integration samples, performs real
`MPI_Allreduce` and `MPI_Gather` collectives, and emits one audit record per
rank. The runner executes it twice, requires byte-identical output hashes,
checks contiguous rank IDs and sample conservation, and rejects a π error above
`1e-12`. The committed run assigns 250,000 samples to every rank and has an
absolute error of about `1.10e-13`. This proves single-container multi-process
execution only; multi-node networking, scaling efficiency, failure recovery,
and production CFD/FEM decomposition remain outside the qualified scope.

`kbb -M:dataset -m run-calculix-contact-evidence` executes a separate 3D
geometrically nonlinear contact case. Two C3D8 blocks start with a gap; a
prescribed `-0.2` displacement closes it and compresses the pair using
surface-to-surface penalty contact. The evidence parser requires every one of
the 22 load increments to converge, a nonzero final contact set, compressive
normal force, completed NLGEOM output, and reaction/contact-force equilibrium.
The committed CalculiX 2.21 run activates 28 contact elements and reports
12,377.43 units of opposing contact force and top reaction, for a parsed
relative balance error of zero. This verifies this frictionless elastic block
case only; it does not validate friction, plasticity, self-contact, impact,
mesh convergence, or general production assemblies.

`kbb -M:dataset -m run-calculix-plastic-evidence` executes a material-
nonlinear C3D8 load/unload cycle with bilinear isotropic hardening. The
piecewise amplitude rises beyond yield and returns to zero; the parser joins 42
DAT history snapshots and requires every increment to converge, positive PEEQ
near mid-cycle, zero final axial load and stress, retained PEEQ, and nonzero
residual elongation. The committed run reaches `PEEQ=2.02765e-4`, unloads to an
axial force below `1e-15`, and retains `1.158657e-4` residual elongation. This
is a constrained uniaxial-strain material verification, not calibration for a
specific production alloy; cyclic hardening, anisotropy, damage, rate and
temperature dependence still require independent material data and validation.

`kbb -M:dataset -m run-calculix-mesh-study` generates and executes four
consistently refined C3D8 meshes for a 3D NLGEOM cantilever: 10, 80, 640 and
5,120 elements. It hashes every generated INP and solver output, requires all
real runs to complete, and evaluates rolling three-grid Richardson/GCI studies.
Adding the 6,561-node level changes the mean tip response from `-1.779019` to
`-1.824416`; the fine-side observed order rises from `1.3935` to `1.7751` and
GCI falls from `6.709%` to `1.2839%`, a `5.225x` reduction that passes the
declared 3% study target. This target applies only to this response and case;
it is not a universal mesh-independent or industrial-accuracy claim.

`kbb -M:dataset -m run-calculix-contact-mesh-study` executes three tilted
surface-to-surface contact meshes and deliberately separates global equilibrium
from local pressure qualification. All runs balance top reaction and integrated
contact force to the printed precision, but maximum CSTR is `1850.36`,
`1648.05`, then `1651.93`: the sequence is non-monotonic, so observed order and
GCI are undefined. The evidence run passes as a sensitivity audit while the
local-pressure scope fails closed as `:local-pressure-not-qualified`. A correct
total force must never be used to claim a converged local contact maximum.

`kbb -M:dataset -m run-calculix-plastic-mesh-study` applies a controlled
strain gradient to three bilinear-isotropic-hardening C3D8 meshes and parses
every final PEEQ integration-point value. Maximum PEEQ increases monotonically
from `0.0017421` through `0.0018330` to `0.0018788`; the observed order is
`0.9899` and fine-grid GCI is `3.0886%`, below the declared 5% target. This
qualifies maximum PEEQ only for this smooth gradient case. It does not cover
notches, singularities, damage, fracture, another geometry, or an uncalibrated
production material.

`kbb -M:dataset -m run-calculix-thermoplastic-evidence` executes a real
CalculiX 2.21 3D coupled temperature-displacement step with temperature-dependent
elastic/plastic tables, thermal expansion and conduction. The pinned run solves
an interior temperature between 293.15 K and 773.15 K, activates nonzero heat
flux and plastic strain, and converges all 22 increments. It proves execution of
the coupled kernels for this two-element reference case only; mesh convergence,
transient accuracy, experimental correlation and production material validity
remain excluded.

`kbb -M:dataset -m run-calculix-thermoplastic-mesh-study` repeats the
coupled case with 2, 4 and 8 through-thickness elements. All three real runs
converge, but the midpoint temperature is `321.0526`, `289.1376`, then
`292.6594` K; maximum heat flux is `35.90498`, `61.0368`, then `86.0267`; and
maximum PEEQ is `0.003626556`, `0.006797741`, then `0.01966108`. The evidence
therefore passes as a sensitivity audit while all three response qualifications
fail closed. Solver increment convergence is not mesh convergence.

Passing `steady` to the same runner selects CalculiX's explicit `STEADY STATE`
coupled procedure. This removes the transient time-discretization effect:
midpoint temperature is `518.2081` K and maximum heat flux is `19.2` on all
three meshes, giving exact grid agreement and zero GCI for those thermal
responses. Maximum PEEQ still changes from `0.003760695` to `0.005771508` to
`0.006803207`, with `19.97%` fine GCI, so the plastic response remains rejected.

`steady-ultrafine` advances the rolling study to 8, 16 and 32 layers. Maximum
PEEQ is `0.006803207`, `0.007343157`, then `0.007619623`; observed order is
`0.9657` and fine GCI is `4.7589%`, below the declared 5% target. Together with
the zero-GCI thermal responses, all declared responses pass only for this
steady, through-thickness reference geometry and synthetic material law.

For a host-native validated solver, use `cae.adapter` with
`:solver {:kind :external-backend}`. The descriptor records backend, version,
domain, input format, command/MPI transport and result provenance, while this
portable library remains process-neutral. A missing host result is reported as
`:adapter-pending`; a returned result is marked `:completed` without silently
promoting its fidelity.

## GitHub Pages WebGPU view

The Pages report compiles `cae.webgpu` from ClojureScript and drives the browser
WebGPU API directly through CLJS-to-JavaScript interop. Scene selection, GPU
buffers, WGSL pipelines, render passes, frames, and draw counters no longer
cross a per-frame Wasm host boundary. Wasm remains an appropriate optional
backend for large solver hot loops, but is not loaded for UI/render dispatch.
All 15 scenes have time-dependent state, realtime geometry regeneration,
pause/resume, reset, speed control, and live telemetry. The Sod shock-tube scene
steps the portable finite-volume kernel; the other scenes currently use
stateful reduced-order/analytic dynamics and must not be read as commercial CAE
validation results. The report DOM is generated from Hiccup2 and its minified,
zero-runtime stylesheet is extracted by Shadow CSS.
Clicking or dragging on the canvas applies a scene-specific action (for example
an inlet impulse, point load, heat/current source, contact force, crack-tip
load, job injection, or mesh perturbation). Its position and decaying strength
are part of the simulation state; the Sod scene additionally injects momentum
and energy into the selected FVM cell before subsequent solver steps.
The single-screen interface keeps scene navigation, the simulation viewport,
controls, and response telemetry visible together. A dashed action boundary,
crosshair, plain-language instruction, and pointer-following action ring make
the interactive region perceivable without relying on color alone.

UI localization uses [`kotoba-lang/i18n`](https://github.com/kotoba-lang/i18n):
the English and Japanese EDN catalogs are embedded at CLJS compile time and
resolved at runtime through `i18n.core`. The toolbar locale selector updates
both Hiccup chrome and dynamic WebGPU scene/action labels without a rebuild,
and persists the choice in browser storage.
If WebGPU is unavailable, the CAE report remains readable and reports the
fallback state rather than pretending to render.
