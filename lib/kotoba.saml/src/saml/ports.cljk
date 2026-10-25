(ns saml.ports)

(defprotocol ISaml
  (verify-assertion! [port request assertion-ref]))

(defprotocol IRelayStateStore
  (consume-relay-state! [store relay-state]))

(defn memory-relay-state-store [states]
  (let [state* (atom (set states))]
    (reify IRelayStateStore
      (consume-relay-state! [_ relay-state]
        (let [present? (contains? @state* relay-state)]
          (swap! state* disj relay-state)
          present?)))))
