(ns kotobase.engine.archive
  "Pure lifecycle contracts for asynchronous archives and chain anchors.

  Filecoin/FEVM are deliberately outside IEngine: neither belongs in the
  foreground query or mutable-head path.")

(def archive-transitions
  {:packing #{:uploaded :failed}
   :uploaded #{:registered :failed}
   :registered #{:proving :failed}
   :proving #{:verified :failed}
   :verified #{}
   :failed #{:packing}})

(def anchor-transitions
  {:pending #{:submitted :failed}
   :submitted #{:confirmed :failed}
   :confirmed #{:finalized :failed}
   :finalized #{}
   :failed #{:pending}})

(defn archive-request
  [{:keys [database-id epoch logical-checkpoint-root physical-root provider]
    :as request}]
  (when-not (and (string? database-id)
                 (integer? epoch)
                 (string? logical-checkpoint-root)
                 (string? physical-root)
                 (#{:s3 :r2 :b2 :ipfs :filecoin} provider))
    (throw (ex-info "invalid archive request"
                    {:type :kotobase.engine/invalid-archive-request
                     :request request})))
  (assoc request :status :packing))

(defn anchor-request
  [{:keys [database-id epoch logical-checkpoint-root anchor-provider] :as request}]
  (when-not (and (string? database-id)
                 (integer? epoch)
                 (string? logical-checkpoint-root)
                 (#{:fevm :evm :base-l2} anchor-provider))
    (throw (ex-info "invalid anchor request"
                    {:type :kotobase.engine/invalid-anchor-request
                     :request request})))
  (assoc request :status :pending))

(defn transition
  "Apply a legal lifecycle transition. Details such as PieceCID or tx hash are
  immutable evidence merged into the returned value."
  [transitions state next-status evidence]
  (when-not ((get transitions (:status state) #{}) next-status)
    (throw (ex-info "illegal lifecycle transition"
                    {:type :kotobase.engine/illegal-transition
                     :from (:status state) :to next-status})))
  (merge state evidence {:status next-status}))

(defn transition-archive [state next-status evidence]
  (transition archive-transitions state next-status evidence))

(defn transition-anchor [state next-status evidence]
  (transition anchor-transitions state next-status evidence))

