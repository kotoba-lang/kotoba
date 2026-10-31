(ns cae.assessment
  "Data-only acceptance assessment for CAE result maps.

  Solvers remain responsible for physics; this namespace turns explicitly
  declared engineering limits into auditable pass/fail evidence. It never
  silently treats a missing or non-finite metric as a pass.")

(defn- finite-number? [value]
  (and (number? value)
       #?(:clj (Double/isFinite (double value))
          :cljs (js/isFinite value))))

(defn- validate-rule! [metric rule]
  (when-not (map? rule)
    (throw (ex-info "CAE acceptance rule must be a map" {:metric metric :rule rule})))
  (when-not (or (contains? rule :min) (contains? rule :max))
    (throw (ex-info "CAE acceptance rule needs :min and/or :max" {:metric metric :rule rule})))
  (doseq [bound [:min :max]
          :when (contains? rule bound)]
    (when-not (finite-number? (get rule bound))
      (throw (ex-info "CAE acceptance bound must be finite"
                      {:metric metric :bound bound :value (get rule bound)}))))
  (when (and (contains? rule :min) (contains? rule :max)
             (> (:min rule) (:max rule)))
    (throw (ex-info "CAE acceptance :min cannot exceed :max" {:metric metric :rule rule})))
  rule)

(defn validate-rules
  "Validate and return a `{metric {:min ... :max ...}}` acceptance map."
  [rules]
  (when-not (map? rules)
    (throw (ex-info "CAE acceptance rules must be a map" {:rules rules})))
  (doseq [[metric rule] rules]
    (when-not (keyword? metric)
      (throw (ex-info "CAE acceptance metric must be a keyword" {:metric metric})))
    (validate-rule! metric rule))
  rules)

(defn- assess-metric [result metric rule]
  (let [value (get result metric)]
    (cond
      (not (contains? result metric))
      {:metric metric :status :failed :reason :missing-metric :rule rule}

      (not (finite-number? value))
      {:metric metric :value value :status :failed :reason :non-finite-value :rule rule}

      :else
      (let [below? (and (contains? rule :min) (< value (:min rule)))
            above? (and (contains? rule :max) (> value (:max rule)))
            reasons (cond-> [] below? (conj :below-min) above? (conj :above-max))]
        {:metric metric :value value :rule rule
         :status (if (empty? reasons) :passed :failed)
         :reasons reasons}))))

(defn assess
  "Assess a solver result against explicit metric limits.

  Result: `{:status :passed|:failed :checks [...]}`. `:case/id`, solver, and
  provenance are copied when present, so this map can be retained as release
  evidence alongside the result."
  [result rules]
  (when-not (map? result)
    (throw (ex-info "CAE assessment result must be a map" {:result result})))
  (validate-rules rules)
  (let [checks (mapv (fn [[metric rule]] (assess-metric result metric rule)) rules)]
    (merge (select-keys result [:case/id :case/provenance :solver :model :fidelity])
           {:status (if (every? #(= :passed (:status %)) checks) :passed :failed)
            :checks checks})))

(defn attach-assessment
  "Attach an `assess` result to a solver result under `:assessment`."
  [result rules]
  (assoc result :assessment (assess result rules)))
