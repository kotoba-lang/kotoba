(ns vllm.prefix-cache
  "Bounded exact-prefix decoder-state cache with independent state clones."
  (:require [vllm.llama :as llama])
  (:import [java.io Closeable]))

(defrecord PrefixCache [entries clock capacity]
  Closeable
  (close [_]
    (doseq [{:keys [state]} (vals @entries)] (llama/close-state! state))
    (reset! entries {})))

(defn prefix-cache [capacity]
  (when-not (pos-int? capacity)
    (throw (ex-info "prefix cache capacity must be positive" {:capacity capacity})))
  (->PrefixCache (atom {}) (atom 0) capacity))

(defn lookup [cache key]
  (when-let [{:keys [state]} (get @(:entries cache) key)]
    (let [tick (swap! (:clock cache) inc)]
      (swap! (:entries cache) update key assoc :access tick)
      (llama/clone-state state))))

(defn store! [cache key state]
  (let [tick (swap! (:clock cache) inc) snapshot (llama/clone-state state)
        evicted (atom [])]
    (swap! (:entries cache)
           (fn [entries]
             (let [entries (if-let [old (get entries key)]
                             (do (swap! evicted conj (:state old))
                                 (assoc entries key {:state snapshot :access tick}))
                             (assoc entries key {:state snapshot :access tick}))]
               (if (<= (count entries) (:capacity cache)) entries
                 (let [[oldest {:keys [state]}]
                       (apply min-key (comp :access val) entries)]
                   (swap! evicted conj state)
                   (dissoc entries oldest))))))
    (doseq [old @evicted] (llama/close-state! old))
    nil))

(defn stats [cache] {:entries (count @(:entries cache)) :capacity (:capacity cache)})
