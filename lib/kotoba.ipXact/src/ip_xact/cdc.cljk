(ns ip-xact.cdc
  "Clock Domain Crossing (CDC) analysis and violation detection. Restored
  from kami-ip's `cdc` module (deleted PR #82).")

(def crossing-types #{:single-bit :multi-bit :handshake :fifo-async})
(def synchronizer-types #{:two-ff :three-ff :gray-code :mux-sync})
(def cdc-violation-kinds #{:missing-synchronizer :convergence-issue :reconvergence-issue :glitch-prone})

(defn cdc-crossing [signal-name from-clock to-clock crossing-type synchronizer]
  {:signal-name signal-name :from-clock from-clock :to-clock to-clock
   :crossing-type crossing-type :synchronizer synchronizer})

(defn cdc-violation [signal issue] {:signal signal :issue issue})
(defn cdc-report [crossings violations] {:crossings (vec crossings) :violations (vec violations)})

(defn clock-domain [name freq-mhz] {:name name :freq-mhz freq-mhz})

(defn cdc-signal
  [{:keys [name source-clock dest-clock width has-synchronizer synchronizer]}]
  {:name name :source-clock source-clock :dest-clock dest-clock :width width
   :has-synchronizer has-synchronizer :synchronizer synchronizer})

(defn analyze-cdc
  "Analyze `signals` for CDC issues against known `clocks`: checks each
  signal that crosses clock domains for missing synchronizers, multi-bit
  glitch-prone crossings, and structural issues."
  [signals clocks]
  (let [clock-names (into #{} (map :name clocks))]
    (reduce
     (fn [report sig]
       (if (or (= (:source-clock sig) (:dest-clock sig))
               (not (clock-names (:source-clock sig)))
               (not (clock-names (:dest-clock sig))))
         report
         (let [crossing-type (if (= (:width sig) 1) :single-bit :multi-bit)
               crossing (cdc-crossing (:name sig) (:source-clock sig) (:dest-clock sig)
                                       crossing-type (:synchronizer sig))
               report (update report :crossings conj crossing)
               report (if-not (:has-synchronizer sig)
                        (update report :violations conj (cdc-violation (:name sig) :missing-synchronizer))
                        report)
               report (if (> (:width sig) 1)
                        (let [has-gray (= (:synchronizer sig) :gray-code)
                              has-fifo (= crossing-type :fifo-async)]
                          (if (and (not has-gray) (not has-fifo) (:has-synchronizer sig))
                            (update report :violations conj (cdc-violation (:name sig) :glitch-prone))
                            report))
                        report)]
           report)))
     (cdc-report [] [])
     signals)))
