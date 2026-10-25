(ns kotoba.document.change
  "Portable, domain-neutral document change events and deterministic replay.")

(def schema-version 1)

(defn event [{:keys [id actor clock operation path value]}]
  {:event/id id :event/actor actor :event/clock clock
   :event/operation operation :event/path (vec path) :event/value value
   :event/schema-version schema-version})

(defn apply-event [document change]
  (case (:event/operation change)
    :assoc (assoc-in document (:event/path change) (:event/value change))
    :update-conj (update-in document (:event/path change) (fnil conj []) (:event/value change))
    :dissoc (update-in document (butlast (:event/path change)) dissoc
                       (last (:event/path change)))
    (throw (ex-info "unsupported document operation" {:event change}))))

(defn replay
  "Replay in stable [clock actor id] order so all peers converge."
  [document events]
  (reduce apply-event document
          (sort-by (juxt :event/clock :event/actor :event/id) events)))
