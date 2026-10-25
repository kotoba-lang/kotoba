(ns cnc-toolpath.gcode
  "G-code generation from toolpath segments with post-processor
  configuration. Restored from kami-cam's `gcode` module (deleted PR
  #82).")

(def machine-types #{:mill-3axis :mill-4axis :mill-5axis :lathe :laser-cutter :printer-3d})
(def post-processors #{:fanuc :haas :siemens :heidenhain :linuxcnc :marlin :grbl})
(def gcode-units #{:millimeters :inches})
(def coordinate-systems #{:g54 :g55 :g56 :g57 :g58 :g59})

(defn- coord-system-str [cs] (case cs :g54 "G54" :g55 "G55" :g56 "G56" :g57 "G57" :g58 "G58" :g59 "G59"))

(defn gcode-config
  []
  {:machine-type :mill-3axis :post-processor :fanuc :units :millimeters
   :safe-height 5.0 :coordinate-system :g54 :program-number 1 :coolant true})

(defn- fmt4
  "Format a double with exactly 4 decimal places, matching Rust's `{:.4}`."
  [x]
  #?(:clj (format "%.4f" (double x))
     :cljs (.toFixed (double x) 4)))

(defn- fmt1 [x]
  #?(:clj (format "%.1f" (double x))
     :cljs (.toFixed (double x) 1)))

(defn- program-number-str [n]
  #?(:clj (format "%04d" (long n))
     :cljs (let [s (str (long n))] (str (apply str (repeat (max 0 (- 4 (count s))) "0")) s))))

(defn- program-number-str2
  "2-digit tool-id formatting, matching Rust's `T{:02}`."
  [n]
  #?(:clj (format "%02d" (long n))
     :cljs (let [s (str (long n))] (str (apply str (repeat (max 0 (- 2 (count s))) "0")) s))))

(defn generate-gcode
  "Generate a G-code string from `segments` and `config`. Produces:
  program header (O-number, units, coordinate system, absolute mode);
  tool changes (T/M06) when `:tool-id` changes between segments;
  spindle start (M03) / stop (M05); coolant on (M08) / off (M09);
  motion commands G00/G01/G02/G03; program end (M30)."
  [segments config]
  (let [lines (atom [])
        emit! (fn [s] (swap! lines conj s))]
    (emit! "%")
    (emit! (str "O" (program-number-str (:program-number config))))
    (emit! "(KAMI CAM — generated G-code)")
    (emit! (case (:units config) :millimeters "G21 (metric)" :inches "G20 (imperial)"))
    (emit! "G90 (absolute)")
    (emit! (coord-system-str (:coordinate-system config)))
    (emit! "G40 (cancel cutter comp)")
    (emit! "G49 (cancel tool length offset)")
    (emit! (str "G00 Z" (fmt4 (:safe-height config))))

    (let [{:keys [current-tool spindle-on]}
          (reduce
           (fn [{:keys [current-tool spindle-on]} seg]
             (let [{:keys [current-tool spindle-on]}
                   (if (not= current-tool (:tool-id seg))
                     (let [_ (when spindle-on
                               (emit! "M05 (spindle stop)")
                               (when (:coolant config) (emit! "M09 (coolant off)")))
                           _ (emit! (str "G00 Z" (fmt4 (:safe-height config))))
                           _ (emit! (str "T" (program-number-str2 (:tool-id seg)) " M06 (tool change)"))
                           _ (emit! "M03 S10000 (spindle CW)")
                           _ (when (:coolant config) (emit! "M08 (coolant on)"))]
                       {:current-tool (:tool-id seg) :spindle-on true})
                     {:current-tool current-tool :spindle-on spindle-on})]
               (case (:segment-type seg)
                 :rapid (emit! (str "G00 X" (fmt4 (nth (:end seg) 0)) " Y" (fmt4 (nth (:end seg) 1)) " Z" (fmt4 (nth (:end seg) 2))))
                 :linear (emit! (str "G01 X" (fmt4 (nth (:end seg) 0)) " Y" (fmt4 (nth (:end seg) 1)) " Z" (fmt4 (nth (:end seg) 2))
                                     " F" (fmt1 (:feed-rate seg))))
                 :arc-cw (when-let [c (:center seg)]
                           (let [i (- (nth c 0) (nth (:start seg) 0)) j (- (nth c 1) (nth (:start seg) 1))]
                             (emit! (str "G02 X" (fmt4 (nth (:end seg) 0)) " Y" (fmt4 (nth (:end seg) 1)) " Z" (fmt4 (nth (:end seg) 2))
                                         " I" (fmt4 i) " J" (fmt4 j) " F" (fmt1 (:feed-rate seg))))))
                 :arc-ccw (when-let [c (:center seg)]
                            (let [i (- (nth c 0) (nth (:start seg) 0)) j (- (nth c 1) (nth (:start seg) 1))]
                              (emit! (str "G03 X" (fmt4 (nth (:end seg) 0)) " Y" (fmt4 (nth (:end seg) 1)) " Z" (fmt4 (nth (:end seg) 2))
                                          " I" (fmt4 i) " J" (fmt4 j) " F" (fmt1 (:feed-rate seg)))))))
               {:current-tool current-tool :spindle-on spindle-on}))
           {:current-tool nil :spindle-on false}
           segments)]
      (when spindle-on
        (emit! "M05 (spindle stop)")
        (when (:coolant config) (emit! "M09 (coolant off)"))))

    (emit! (str "G00 Z" (fmt4 (:safe-height config)) " (retract)"))
    (emit! "G00 X0.0000 Y0.0000 (return to origin)")
    (emit! "M30 (program end)")
    (emit! "%")
    (str (apply str (map #(str % "\n") @lines)))))
