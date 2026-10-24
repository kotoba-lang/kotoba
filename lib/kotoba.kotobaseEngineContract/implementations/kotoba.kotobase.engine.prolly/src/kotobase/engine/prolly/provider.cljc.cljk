(ns kotobase.engine.prolly.provider
  "JVM coordinator joining the Prolly engine to kotobase-storage capabilities.
  Immutable blocks may be orphaned after a CAS loss; the mutable ref is the
  sole publication point."
  (:require [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly :as prolly]
            [kotobase.storage.core :as storage]))

(defn ports
  "Adapt an IBlockStore to Arrangement's single-block put/get ports."
  [backend]
  (storage/validate-block-store! backend)
  {:put! (fn [cid bytes]
           (storage/-put-blocks! backend [{:cid cid :bytes bytes}])
           nil)
   :get-fn (fn [cid]
             (get (storage/-get-blocks backend [cid]) cid))})

(defn engine-from-backend
  [backend crypto]
  (prolly/prolly-engine (merge (ports backend) crypto)))

(defn restore-head
  "Restore the currently published database state, or nil for a missing ref."
  [eng backend ref-name]
  (storage/validate-backend! backend)
  (when-let [head (storage/-read-ref backend ref-name)]
    (engine/restore-state eng (:cid head))))

(defn transact-and-publish!
  "Write immutable blocks, then conditionally publish their manifest root.
  A CAS loss is returned as :conflict and never overwrites the winner."
  [eng backend ref-name state request]
  (storage/validate-backend! backend)
  (let [expected (:physical-root state)
        result (engine/transact eng state request)
        next-root (get-in result [:receipt :physical-root])
        publication (storage/-compare-and-set-ref! backend ref-name expected
                                                    next-root)]
    (if (:published? publication)
      (assoc result :publication publication :publish-status :published)
      {:publish-status :conflict
       :publication publication
       :expected-root expected
       :candidate-root next-root
       :winner-root (:current publication)})))

