(ns kotoba.rtx-native
  "kami-rtx-native — from-scratch WGSL path tracer + differentiable
   rendering. 1:1 port of kami-rt-native's `lib.rs` to .cljc per
   ADR-2607010930 (clj-wgsl migration Phase 4).

   R1.0 path reservation per ADR-2605261800 (upstream Rust ADR, referenced
   by the Rust source verbatim) §D10.4. **Contingent fallback** — activated
   only if the Mitsuba 3 wgpu upstream PR fails the R1.2 viability gate
   (Cornell box 30 fps Chrome 121+, PSNR >= 35dB). Activation requires
   Council Lv6+ >=3 attestation per §D10.2.

   Intended (not-yet-built, per the Rust source) to sit on top of
   `kotoba.raytrace` (WGSL ray-query + LBVH) — note the upstream Rust crate
   `kami-rtx-native` does not actually `use kami_rt::*` anywhere and its
   `Cargo.toml` does not depend on `kami-rt` either; \"built on top of
   kami-rt\" in its README is aspirational future scope, not a current
   compiled dependency. This port mirrors that: no dependency on
   kotoba-lang/raytrace is declared here, matching the Rust source exactly.

   There is no algorithm here to port — the entire upstream crate is this
   reservation/status metadata (\"No runtime code yet\" applies to kami-rt
   itself; kami-rtx-native has even less: it is pure path-reservation, not
   even a stub build). Nothing in this namespace is adapter-only for the
   same reason nothing in kotoba.raytrace is: there was never any GPU
   dispatch code in the source being ported.")

(def adr "ADR-2605261800")
(def phase "R1.0-path-reservation")
(def kami-name "kami-rtx-native")
(def status "contingent-fallback-pending-viability-gate")
(def triggered-by "Mitsuba 3 wgpu backend gate fail (R1.2)")
(def nv-compat-targets ["OptiX" "RTX Renderer"])

(defn activated?
  "Has the contingent fallback been triggered? Always false until the R1.2
   viability gate fails and Council Lv6+ >=3 attestation lands — there is no
   runtime activation path yet (mirrors the Rust source, which has none)."
  []
  false)
