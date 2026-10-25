(ns simulated-user.interaction)

(def allowed-actions
  #{:observe :answer :send :receive :click :type :select :submit :finish})
(def maximum-events 100)

(defn- fail [message data]
  (throw (ex-info message data)))

(defn validate-trace
  "Validate a bounded, content-free product interaction trace. Raw user text,
  screenshots, recordings, and identifiers are deliberately outside it."
  [trace]
  (when-not (and (vector? trace) (seq trace) (<= (count trace) maximum-events))
    (fail "An interaction trace must contain 1..100 events"
          {:count (when (vector? trace) (count trace))}))
  (doseq [[expected-index event] (map-indexed vector trace)]
    (when-not (= #{:event/index :event/action :event/target :event/outcome}
                 (set (keys event)))
      (fail "Interaction events have an unexpected shape" {:event event}))
    (when-not (= expected-index (:event/index event))
      (fail "Interaction event indexes must be contiguous"
            {:expected expected-index :actual (:event/index event)}))
    (when-not (contains? allowed-actions (:event/action event))
      (fail "Interaction action is unsupported" {:event event}))
    (when-not (and (keyword? (:event/target event))
                   (keyword? (:event/outcome event)))
      (fail "Interaction target and outcome must be categorical keywords"
            {:event event})))
  trace)
