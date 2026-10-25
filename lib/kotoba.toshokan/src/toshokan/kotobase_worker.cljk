(ns toshokan.kotobase-worker
  "Cloudflare R2 binding and narrow JavaScript facade for Kotobase Engine."
  (:require [kotoba.lang.text :as str]
            [goog.object :as gobj]
            [kotobase.engine :as engine]
            [kotobase.storage.core :as storage]))

(defn- block-key [prefix cid] (str prefix "/blocks/" cid))
(defn- ref-key [prefix ref-name]
  (str prefix "/refs/" (js/encodeURIComponent ref-name)))

(defrecord R2Backend [bucket prefix]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (->> blocks
         (map (fn [{:keys [cid bytes]}]
                (.put bucket (block-key prefix cid) bytes
                      #js {:onlyIf #js {:etagDoesNotMatch "*"}})))
         into-array
         js/Promise.all))
  (-get-blocks [_ cids]
    (-> (js/Promise.all
         (into-array
          (map (fn [cid]
                 (-> (.get bucket (block-key prefix cid))
                     (.then
                      (fn [object]
                        (if object
                          (-> (.arrayBuffer object)
                              (.then (fn [buffer]
                                       [cid (js/Uint8Array. buffer)])))
                          [cid nil])))))
               cids)))
        (.then
         (fn [entries]
           (into {}
                 (keep (fn [[cid bytes]]
                         (when bytes [cid bytes])))
                 (js->clj entries))))))

  storage/IRefStore
  (-read-ref [_ ref-name]
    (-> (.get bucket (ref-key prefix ref-name))
        (.then
         (fn [object]
           (when object
             (-> (.text object)
                 (.then
                  (fn [cid]
                    {:cid cid :version (gobj/get object "etag")}))))))))
  (-compare-and-set-ref! [this ref-name expected-cid next-cid]
    (let [key (ref-key prefix ref-name)]
      (-> (storage/-read-ref this ref-name)
          (.then
           (fn [current]
             (if (not= expected-cid (:cid current))
               {:published? false
                :current (:cid current)
                :version (:version current)}
               (-> (.put bucket key next-cid
                         #js {:onlyIf
                              (if-let [etag (:version current)]
                                #js {:etagMatches etag}
                                #js {:etagDoesNotMatch "*"})})
                   (.then
                    (fn [written]
                      (if written
                        {:published? true
                         :current next-cid
                         :version (gobj/get written "etag")}
                        (-> (storage/-read-ref this ref-name)
                            (.then
                             (fn [winner]
                               {:published? false
                                :current (:cid winner)
                                :version (:version winner)})))))))))))))

  storage/IBackendCapabilities
  (-capabilities [_]
    #{:immutable-blocks :cid-addressed-read :conditional-ref}))

(defn- identity-async [value] (js/Promise.resolve value))
(defn- blind-async [value] (js/Promise.resolve (pr-str value)))

(defn open-database
  ([bucket] (open-database bucket "kotobase/toshokan"))
  ([bucket prefix]
   (engine/open
    {:storage (->R2Backend bucket (str/replace prefix #"/+$" ""))
     :ref-name "toshokan"
     :encrypt-fn identity-async
     :decrypt-fn identity-async
     :blind-fn blind-async
     :visible? (constantly true)})))

(defn transact [database tx-data]
  (engine/transact! database (js->clj tx-data)))

(defn pull [database entity attributes]
  (-> (engine/pull database entity (js->clj attributes))
      (.then clj->js)))

(defn head [database]
  (engine/head database))
