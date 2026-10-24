(ns model-checking.assertion
  "SVA-style assertion evaluation over signal traces. Restored from
  kami-verify's `assertion` module (deleted PR #82).")

(def assertion-types #{:assert :assume :cover :restrict})
(def severities #{:fatal :error :warning :info})
(def assertion-statuses #{:pass :fail :vacuous})

(defn sva-assertion [name assertion-type expression clock severity]
  {:name name :assertion-type assertion-type :expression expression :clock clock :severity severity})

(defn sva-result [assertion-name status hit-count fail-count first-fail-time]
  {:assertion-name assertion-name :status status :hit-count hit-count
   :fail-count fail-count :first-fail-time first-fail-time})

(defn- truthy-signal? [v] (or (= v "1") (= v "true")))

(defn evaluate-assertions-simple
  "Evaluate `assertions` against `signal-trace` (a seq of time-steps, each
  a map of signal names to string values). Each assertion's `expression`
  is evaluated as a simple signal-name lookup: passes at a time-step when
  the named signal equals `\"1\"` or `\"true\"`. Only evaluated on active
  clock edges (the assertion's `:clock` signal truthy; defaults to active
  when absent)."
  [assertions signal-trace]
  (mapv
   (fn [a]
     (let [{:keys [hit-count fail-count first-fail-time clock-active-count]}
           (reduce
            (fn [acc [t signals]]
              (let [clock-val (if-let [v (get signals (:clock a))] (truthy-signal? v) true)]
                (if-not clock-val
                  acc
                  (let [acc (update acc :clock-active-count inc)
                        expr-val (truthy-signal? (get signals (:expression a)))]
                    (if expr-val
                      (update acc :hit-count inc)
                      (-> acc
                          (update :fail-count inc)
                          (update :first-fail-time (fn [f] (or f t)))))))))
            {:hit-count 0 :fail-count 0 :first-fail-time nil :clock-active-count 0}
            (map-indexed vector signal-trace))
           status (cond
                    (zero? clock-active-count) :vacuous
                    (zero? fail-count) :pass
                    :else :fail)]
       (sva-result (:name a) status hit-count fail-count first-fail-time)))
   assertions))
