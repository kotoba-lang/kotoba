(ns signal-integrity.transmission-line
  "Transmission line parameter calculation for microstrip, stripline, and
  coplanar waveguide. Ported from kami-si's `transmission_line.rs`
  (kotoba-lang/kami-engine, retired Rust crate, ADR-2607010000).
  No network, no I/O."
  (:require [signal-integrity.constants :as constants]
            [signal-integrity.math :as math]))

(def trace-thickness-mm
  "Trace thickness in mm (assumed 1 oz copper = 0.035 mm)."
  (:tline/trace-thickness-mm constants/constants))

(def c-mm-per-ps
  "Speed of light in mm/ps."
  (:tline/c-mm-per-ps constants/constants))

(def ^:private microstrip-loss-base (:tline/microstrip-loss-base constants/constants))
(def ^:private stripline-loss-base (:tline/stripline-loss-base constants/constants))
(def ^:private coplanar-loss-base (:tline/coplanar-loss-base constants/constants))

(defn microstrip
  "Build a `:microstrip` transmission-line geometry descriptor: trace on
  top of dielectric above a ground plane. `width`/`height` in mm, `er` =
  relative permittivity."
  [{:keys [width height er]}]
  {:tline-type/kind :microstrip :width width :height height :er er})

(defn stripline
  "Build a `:stripline` transmission-line geometry descriptor: trace
  between two ground planes. `width`/`height1`/`height2` in mm, `er` =
  relative permittivity."
  [{:keys [width height1 height2 er]}]
  {:tline-type/kind :stripline :width width :height1 height1 :height2 height2 :er er})

(defn coplanar
  "Build a `:coplanar` transmission-line geometry descriptor: trace with
  ground on the same layer. `width`/`gap`/`height` in mm, `er` = relative
  permittivity."
  [{:keys [width gap height er]}]
  {:tline-type/kind :coplanar :width width :gap gap :height height :er er})

(defn- calculate-microstrip-z0
  "IPC-2141 microstrip formula:
    Z0 = (87 / sqrt(er + 1.41)) * ln(5.98 * h / (0.8 * w + t))"
  [{:keys [width height er]} length-mm]
  (let [t trace-thickness-mm
        z0 (* (/ 87.0 (math/sqrt (+ er 1.41)))
              (math/ln (/ (* 5.98 height) (+ (* 0.8 width) t))))
        eff-er (+ (/ (+ er 1.0) 2.0)
                  (/ (- er 1.0)
                     (* 2.0 (math/sqrt (+ 1.0 (/ (* 12.0 height) width))))))
        delay (/ (math/sqrt eff-er) c-mm-per-ps)
        loss (* microstrip-loss-base (+ 1.0 (/ 1.0 z0)))] ; simplified conductor + dielectric loss
    {:tline/z0-ohm z0
     :tline/delay-ps-per-mm delay
     :tline/loss-db-per-mm loss
     :tline/length-mm length-mm}))

(defn- calculate-stripline-z0
  "Simplified closed-form stripline approximation."
  [{:keys [width height1 height2 er]} length-mm]
  (let [b (+ height1 height2)
        t trace-thickness-mm
        z0 (* (/ 60.0 (math/sqrt er))
              (math/ln (/ (* 4.0 b) (* 0.67 math/pi (+ (* 0.8 width) t)))))
        delay (/ (math/sqrt er) c-mm-per-ps)
        loss (* stripline-loss-base (+ 1.0 (/ 1.0 z0)))]
    {:tline/z0-ohm z0
     :tline/delay-ps-per-mm delay
     :tline/loss-db-per-mm loss
     :tline/length-mm length-mm}))

(defn- calculate-coplanar-z0
  "Simplified coplanar waveguide impedance approximation."
  [{:keys [width gap height er]} length-mm]
  (let [k (/ width (+ width (* 2.0 gap)))
        eff-er (+ 1.0
                  (* (/ (- er 1.0) 2.0)
                     (/ 1.0 (math/sqrt (+ 1.0 (* 0.7 (/ width height)))))))
        z0 (* (/ (* 30.0 math/pi) (math/sqrt eff-er)) (math/ln (/ 1.0 k)))
        delay (/ (math/sqrt eff-er) c-mm-per-ps)
        loss (* coplanar-loss-base (+ 1.0 (/ 1.0 z0)))]
    {:tline/z0-ohm z0
     :tline/delay-ps-per-mm delay
     :tline/loss-db-per-mm loss
     :tline/length-mm length-mm}))

(defn calculate-z0
  "Calculate transmission line parameters from geometry.

  Microstrip Z0 uses the IPC-2141 formula:
    Z0 = (87 / sqrt(er + 1.41)) * ln(5.98 * h / (0.8 * w + t))

  Stripline and coplanar use simplified closed-form approximations.

  `tline-type` is a map built by [[microstrip]], [[stripline]], or
  [[coplanar]]; `length-mm` is the physical trace length. Returns a
  `:tline/*`-keyed parameter map (see `signal-integrity` docstring)."
  [tline-type length-mm]
  (case (:tline-type/kind tline-type)
    :microstrip (calculate-microstrip-z0 tline-type length-mm)
    :stripline (calculate-stripline-z0 tline-type length-mm)
    :coplanar (calculate-coplanar-z0 tline-type length-mm)))
