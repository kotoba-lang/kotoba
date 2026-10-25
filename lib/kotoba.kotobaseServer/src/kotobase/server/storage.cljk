(ns kotobase.server.storage
  "Bridge the common storage contract to the historical server runtime ports."
  (:require [kotobase.server.runtime :as runtime]
            [kotobase.storage.core :as storage]))

(defn- ref-name [tenant graph]
  (storage/scoped-ref tenant graph))

(defrecord RuntimeStorage [backend]
  runtime/BlockStore
  (-get-block [_ _tenant _graph cid]
    #?(:clj (storage/get-block backend cid)
       :cljs (-> (storage/-get-blocks backend [cid])
                 js/Promise.resolve
                 (.then #(get % cid)))))
  (-put-block [_ _tenant _graph cid bytes]
    (storage/put-block! backend cid bytes))

  runtime/HeadStore
  (-read-head [_ tenant graph]
    #?(:clj
       (let [ref (storage/-read-ref backend (ref-name tenant graph))]
         {:head (:cid ref) :version (:version ref)})
       :cljs
       (-> (storage/-read-ref backend (ref-name tenant graph))
           js/Promise.resolve
           (.then (fn [ref]
                    {:head (:cid ref) :version (:version ref)})))))
  (-compare-and-set-head [_ tenant graph expected-version new-head]
    (let [name (ref-name tenant graph)]
      #?(:clj
         (let [current (storage/-read-ref backend name)]
           (and (= expected-version (:version current))
                (:published?
                 (storage/-compare-and-set-ref!
                  backend name (:cid current) new-head))))
         :cljs
         (-> (storage/-read-ref backend name)
             js/Promise.resolve
             (.then
              (fn [current]
                (if (not= expected-version (:version current))
                  false
                  (-> (storage/-compare-and-set-ref!
                      backend name (:cid current) new-head)
                      js/Promise.resolve
                      (.then (fn [result]
                               (:published? result))))))))))))

(defn runtime-storage
  "Expose BACKEND through the legacy server BlockStore and HeadStore ports."
  [backend]
  (storage/validate-backend! backend)
  (->RuntimeStorage backend))

(defn services
  "Return the storage portion of a server service map."
  [backend]
  (let [adapter (runtime-storage backend)]
    {:block-store adapter :head-store adapter}))
