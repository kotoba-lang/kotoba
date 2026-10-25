(ns signal-integrity.crosstalk
  "Crosstalk analysis between adjacent transmission lines. Ported from
  kami-si's `crosstalk.rs` (kotoba-lang/kami-engine, retired Rust crate,
  ADR-2607010000). No network, no I/O."
  (:require [signal-integrity.constants :as constants]
            [signal-integrity.math :as math]))

(def ^:private spacing-decay-mm (:crosstalk/spacing-decay-mm constants/constants))
(def ^:private backward-coefficient (:crosstalk/backward-coefficient constants/constants))
(def ^:private forward-coefficient (:crosstalk/forward-coefficient constants/constants))
(def ^:private driver-source-impedance-ohm
  (:crosstalk/driver-source-impedance-ohm constants/constants))
(def ^:private driver-amplitude-mv (:crosstalk/driver-amplitude-mv constants/constants))
(def ^:private saturation-floor-mm (:crosstalk/saturation-floor-mm constants/constants))

(defn crosstalk-result
  "Build a crosstalk result map."
  [{:keys [victim-net aggressor-net coupling-type peak-mv width-ps]}]
  {:crosstalk/victim-net victim-net
   :crosstalk/aggressor-net aggressor-net
   :crosstalk/coupling-type coupling-type
   :crosstalk/peak-mv peak-mv
   :crosstalk/width-ps width-ps})

(defn analyze-crosstalk
  "Analyze crosstalk coupling between a victim and aggressor transmission
  line. `victim`/`aggressor` are `:tline/*` parameter maps (see
  `signal-integrity.transmission-line/calculate-z0`); `coupling-length-mm`
  and `spacing-mm` describe the coupled-line geometry; `rise-time-ps` is
  the aggressor signal's rise time.

  Uses a simplified capacitive/inductive coupling model. Backward
  (near-end, NEXT) crosstalk depends on coupling length relative to
  signal rise time; forward (far-end, FEXT) crosstalk depends on the
  difference in inductive and capacitive coupling coefficients. Returns
  a `:crosstalk/*`-keyed map for whichever coupling type dominates
  (`:crosstalk/coupling-type` is `:backward` or `:forward`)."
  [victim aggressor coupling-length-mm spacing-mm rise-time-ps]
  (let [victim-delay (:tline/delay-ps-per-mm victim)
        ;; Coupling coefficient decreases with spacing (simplified exponential model).
        k-coupling (math/exp (/ (- spacing-mm) spacing-decay-mm))
        ;; Backward crosstalk coefficient (NEXT).
        td (* victim-delay coupling-length-mm)
        kb (* k-coupling backward-coefficient)
        ;; Saturation: backward crosstalk saturates when coupled length >
        ;; rise_time / (2 * delay).
        saturation-length (/ rise-time-ps (* 2.0 victim-delay))
        effective-kb (if (> coupling-length-mm saturation-length)
                       kb
                       (* kb (/ coupling-length-mm saturation-length)))
        ;; Aggressor amplitude assumed from impedance (1V driver into Z0).
        aggressor-amplitude-mv (/ (* driver-amplitude-mv (:tline/z0-ohm aggressor))
                                   (+ (:tline/z0-ohm aggressor) driver-source-impedance-ohm))
        backward-peak (* effective-kb aggressor-amplitude-mv)
        backward-width (* 2.0 td)
        ;; Forward crosstalk coefficient (FEXT) — proportional to
        ;; coupling_length * delta(Kl-Kc).
        kf (* k-coupling forward-coefficient
              (/ coupling-length-mm (max saturation-length saturation-floor-mm)))
        forward-peak (* kf aggressor-amplitude-mv)
        forward-width rise-time-ps]
    ;; Return the dominant coupling type.
    (if (>= backward-peak forward-peak)
      (crosstalk-result {:victim-net "victim"
                          :aggressor-net "aggressor"
                          :coupling-type :backward
                          :peak-mv backward-peak
                          :width-ps backward-width})
      (crosstalk-result {:victim-net "victim"
                          :aggressor-net "aggressor"
                          :coupling-type :forward
                          :peak-mv forward-peak
                          :width-ps forward-width}))))
