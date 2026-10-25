(ns sdc.clock
  "SDC (Synopsys Design Constraints) `create_clock` command model. SDC is
  the TCL-based de facto industry-standard timing/design-constraint format
  consumed by STA and synthesis tools (synopsys.com), specified here as a
  simplified subset as part of the kotoba-lang org-<vendor>-<spec>
  reverse-domain naming initiative (ADR-2607072500, com-junkawasaki/root).")

(defn create-clock
  "Build a clock map from `create_clock -period <p> -name <n>
  -waveform {t1 t2} [get_ports <port>]` arguments. `:waveform` defaults to
  a 50% duty-cycle waveform ([0 period/2]) when not given, matching SDC's
  own default."
  [{:keys [name period waveform source-port]}]
  {:name name
   :period period
   :waveform (or waveform [0.0 (/ period 2.0)])
   :source-port source-port})

(defn duty-cycle
  "Percentage of the clock period during which the clock is high, derived
  from the waveform edges `[rise fall]` (rise = first edge, fall = second
  edge). Handles an inverted waveform (fall < rise, i.e. the clock starts
  high) by wrapping the high interval around the period. Returns nil for
  a non-positive period."
  [{:keys [period waveform]}]
  (when (and period (pos? period) (= 2 (count waveform)))
    (let [[rise fall] waveform
          high (if (>= fall rise) (- fall rise) (+ (- fall rise) period))]
      (* 100.0 (/ high period)))))
