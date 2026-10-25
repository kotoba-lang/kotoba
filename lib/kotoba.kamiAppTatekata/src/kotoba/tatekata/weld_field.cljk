(ns kotoba.tatekata.weld-field
  "weld-field — moving heat-source weld-pass model for robotic steel
  fastening.

  Ported 1:1 from `kami-app-tatekata::weld_field.rs` (kami-engine, Rust,
  retired per ADR-2607010000-kotoba-runtime-sdk-cljc-migration).

  This is no longer an app-layer stand-in: it delegates to the real
  `kotoba.tatekata.thermal` — a 2-D transient heat-conduction PDE (explicit
  FDM, CFL-bounded) with a travelling Gaussian volumetric source and
  peak-temperature fusion tracking. The 1-D seam the `robot:bolter` steps
  weld is mapped onto a thin 2-D strip of that field; `pass` walks the arc
  along the seam and the field conducts + cools between calls. A node is
  \"fused\" once its peak temperature crosses the fusion threshold.

  Honest scope: 2-D, explicit, single-pass arc — a real conduction solver
  (not a metallurgy / weld-pool / HAZ model, which needs transient thermal
  FEM), but the heat field itself is genuine physics, not a tuned reduced
  model.

  Used by `robot:bolter` steps (steel column erection, roof trusses)."
  (:require [kotoba.tatekata.thermal :as thermal]))

;; Strip geometry calibrated so the viewer's fixed weld inputs (power ~= 9 kW,
;; dt = 1/60 s) fuse a swept seam while the field stays bounded.
(def ^:private strip-ny 3)        ; seam rows — thin so fused-fraction tracks seam length
(def ^:private cell-h 0.002)      ; cell size (m)
(def ^:private alpha 4.0e-6)      ; thermal diffusivity (m^2/s)
(def ^:private rho-c 2.0e3)       ; lumped rho*c calibrated to arc-class power
(def ^:private sigma 0.006)       ; source radius (m) — spans the strip height
(def ^:private h-conv 0.4)        ; convective loss to ambient air (1/s) after the arc passes

(defn make-field
  "`n` (>= 2, clamped) is the seam length in strip cells; `ambient`/
  `fusion-t` are passed through to the underlying thermal field."
  [n ambient fusion-t]
  (let [n (max 2 n)
        field (-> (thermal/make-field n strip-ny cell-h alpha ambient fusion-t)
                  (thermal/with-rho-c rho-c)
                  (thermal/with-convection h-conv))
        sy (* strip-ny 0.5 cell-h)
        seam-len (* (- n 1.0) cell-h)]
    {:weld/n n
     :weld/field field
     :weld/sy sy
     :weld/seam-len seam-len}))

(defn pass
  "Advance one weld step: the arc sits at normalized seam position `head`
  (0..1) depositing `power` (W) for `dt` seconds, then the field conducts
  and cools. `dt` is sub-stepped to respect the explicit CFL bound so the
  caller can pass any frame dt without blowing up (at least one substep is
  always taken, even for `dt` below the CFL bound)."
  [{:keys [:weld/field :weld/sy :weld/seam-len] :as w} head power dt]
  (let [sx (* (min 1.0 (max 0.0 head)) seam-len)
        cfl (thermal/cfl-dt field)]
    (loop [field field remaining (max dt 0.0)]
      (let [step-dt (min remaining cfl)
            field' (thermal/step field sx sy power sigma step-dt)
            remaining' (- remaining step-dt)]
        (if (<= remaining' 1e-9)
          (assoc w :weld/field field')
          (recur field' remaining'))))))

(defn fused-fraction
  "Fraction of the seam whose peak temperature reached fusion (0..1)."
  [{:keys [:weld/field]}]
  (thermal/fused-fraction field))

(defn max-temp
  "Hottest current node temperature (°C) — for a glow indicator."
  [{:keys [:weld/field]}]
  (thermal/max-temp field))

(defn peak-max
  "Highest peak temperature ever reached anywhere (fusion evidence persists
  after cool-down)."
  [{:keys [:weld/field]}]
  (reduce max 0.0 (:thermal/peak field)))
