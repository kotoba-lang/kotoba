(ns sigma.ports
  "Host-injected ports for Sigma event matching. sigma-clj defines the protocol;
  the host supplies a concrete implementation that maps its event schema to field
  names. The evaluator in sigma.execute is pure over these — no I/O of its own.")

(defprotocol IField
  "Extract a named field value from an event map."
  (extract [this field-name event]
   "field-name (String) + event map → value (or nil if absent)"))

(defn default-ports
  "A host-free IField implementation. Looks up `field-name` first as a string key,
  then falls back to a keyword key. Sufficient for plain string- or keyword-keyed
  maps; replace with a host-specific extractor for structured log schemas."
  []
  {:field (reify IField
            (extract [_ field-name event]
              (if (contains? event field-name)
                (get event field-name)
                (get event (keyword field-name)))))})
