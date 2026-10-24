(ns kotoba.raytrace
  "hikari-rt (光) — WebGPU ray tracing primitive, ported pure to .cljc from
   kami-rt (Rust) per ADR-2607010930 (clj-wgsl migration Phase 4).

   `kami.rt` (clj/edn, elsewhere) is the brain — it authors an EDN
   ray-tracing recipe and normalizes it to a backend-neutral IR. This
   library is the **portable executor half**: it builds the acceleration
   structure (`kotoba.raytrace.bvh`) and generates the WGSL ray-query trace
   shader (`kotoba.raytrace.wgsl`) from the same integrator parameters,
   plus GPU buffer packing (`kotoba.raytrace.gpu`). GPU dispatch
   (pipeline/bind-group creation + submission on an actual device) is a
   host integration step that was never part of kami-rt either — see
   README.md for the full adapter-boundary note.

   ADR-2605261800 (upstream Rust ADR, referenced by the Rust source
   verbatim): R1.0 path reservation -> R1.2 brings PSNR >= 35 dB vs
   Mitsuba 3."
  (:require [kotoba.raytrace.wgsl :as wgsl]))

(def adr "ADR-2605261800")
(def phase "R1.2-cpu-accel+wgsl-gen")
(def kami-name "hikari-rt")
(def nv-compat-target "OptiX")

(defn default-config
  "RtConfig::default() equivalent — {:max-bounces 4 :spp 8 :clamp 10.0 :seed 0}."
  []
  (wgsl/default-config))

(def wgsl-ray-query
  "Generate the WGSL ray-query compute shader for a recipe name + RtConfig
   map. See kotoba.raytrace.wgsl/ray-query-source."
  wgsl/ray-query-source)
