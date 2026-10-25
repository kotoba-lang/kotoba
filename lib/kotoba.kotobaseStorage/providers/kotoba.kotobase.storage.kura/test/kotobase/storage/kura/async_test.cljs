(ns kotobase.storage.kura.async-test
  (:require [ipld.car.bytes :as car-bytes]
            [kotobase.storage.core :as storage]
            [kotobase.storage.kura.async :as sut]
            [kotobase.storage.memory :as catalog-memory]
            [kura.node.async :as shard-async]
            [kura.node.gf :as gf]
            [kura.node.store :as node-store]
            [multiformats.core :as mf]
            ["fs" :as fs]
            ["os" :as os]
            ["path" :as path])
  (:require-macros [cljs.test :refer [deftest is async]]))

(defn- persist-test-catalog! [file-path state]
  (let [blocks (into {}
                     (map (fn [[cid bytes]]
                            [cid (.toString (js/Buffer.from bytes) "base64")]))
                     (:blocks state))
        encoded (js/JSON.stringify
                 (clj->js {:blocks blocks :refs (:refs state)}))
        temporary-path (str file-path ".tmp-" (gensym))]
    (.writeFileSync fs temporary-path encoded)
    (.renameSync fs temporary-path file-path)))

;; Test-only single-process catalog; it is not a production multi-writer store.
(defrecord FileTestCatalog [file-path state]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (let [current @state
          next (update current :blocks
                       (fn [stored]
                         (reduce (fn [out {:keys [cid bytes]}]
                                   (if-let [existing (get out cid)]
                                     (if (= (gf/->vec existing) (gf/->vec bytes))
                                       out
                                       (throw (ex-info "durable test catalog CID collision"
                                                       {:cid cid})))
                                     (assoc out cid (js/Buffer.from bytes))))
                                 stored blocks)))]
      (persist-test-catalog! file-path next)
      (reset! state next)
      (mapv :cid blocks)))
  (-get-blocks [_ cids]
    (select-keys (:blocks @state) cids))

  storage/IRefStore
  (-read-ref [_ name] (get-in @state [:refs name]))
  (-compare-and-set-ref! [_ name expected next-cid]
    (let [current @state
          present (get-in current [:refs name])
          actual (:cid present)]
      (if (= expected actual)
        (let [version (inc (or (:version present) 0))
              ref {:cid next-cid :version version}
              next (assoc-in current [:refs name] ref)]
          (persist-test-catalog! file-path next)
          (reset! state next)
          {:published? true :current next-cid :version version})
        {:published? false :current actual :version (:version present)})))

  storage/IBackendCapabilities
  (-capabilities [_]
    #{:immutable-blocks :cid-addressed-read :conditional-ref
      :linearizable-ref :batch-get :batch-put :local-file :atomic-replace}))

(defn- open-file-test-catalog [file-path]
  (let [stored (when (.existsSync fs file-path)
                 (js->clj (.parse js/JSON (.readFileSync fs file-path "utf8"))))
        blocks (into {}
                     (map (fn [[cid encoded]]
                            [cid (js/Buffer.from encoded "base64")]))
                     (get stored "blocks" {}))
        refs (into {}
                   (map (fn [[name ref]]
                          [name {:cid (get ref "cid")
                                 :version (get ref "version")}]))
                   (get stored "refs" {}))
        state (atom {:blocks blocks :refs refs})]
    (->FileTestCatalog file-path state)))

(defrecord FakeAsyncStore [id state descriptor]
  shard-async/IAsyncShardStore
  (-put-shard!> [_ shard-id bytes]
    (swap! state assoc-in [:shards shard-id] bytes)
    (js/Promise.resolve {:shard-id shard-id
                         :bytes-written (car-bytes/bcount bytes)}))
  (-get-shard> [_ shard-id]
    (swap! state update :full-reads conj shard-id)
    (js/Promise.resolve
     (when-not (contains? (:unavailable @state) shard-id)
       (get-in @state [:shards shard-id]))))
  (-get-range> [_ shard-id offset length]
    (swap! state update :range-reads conj [shard-id offset length])
    (js/Promise.resolve
     (when-not (contains? (:unavailable @state) shard-id)
       (when-let [bytes (get-in @state [:shards shard-id])]
         (let [end (min (car-bytes/bcount bytes) (+ offset length))]
           (when (< offset end)
             (car-bytes/slice bytes offset end)))))))
  (-delete-shard!> [_ shard-id]
    (let [present? (contains? (:shards @state) shard-id)]
      (swap! state update :shards dissoc shard-id)
      (js/Promise.resolve present?)))
  (-list-shards> [_ prefix]
    (js/Promise.resolve
     (->> (:shards @state)
          keys
          (filter #(.startsWith % prefix))
          sort
          vec)))
  (-shard-size> [_ shard-id]
    (js/Promise.resolve
     (when-let [bytes (get-in @state [:shards shard-id])]
       (car-bytes/bcount bytes))))

  node-store/INodeIdentity
  (-descriptor [_] descriptor))

(defn- fake-store [id]
  (let [descriptor (node-store/descriptor
                    {:node-id id
                     :failure-domain {:machine id}
                     :independence :independent
                     :availability :always-on
                     :capabilities #{:range-read}})]
    (->FakeAsyncStore id
                      (atom {:shards {} :unavailable #{}
                             :range-reads [] :full-reads []})
                      descriptor)))

(defn- backend-for [ids fleet placement-context catalog]
  (sut/open
   {:fleet fleet
    :plan-placement
    (fn [_object-id layout _context]
      {:complete? true
       :shortfall 0
       :shards (zipmap (range (:n layout)) ids)})
    :placement-context placement-context
    :catalog catalog
    :verify-block (fn [cid bytes] (= cid (mf/cidv1-raw bytes)))
    :max-pack-bytes 1024
    :max-stripe-bytes 1024
    :layout {:k 4 :r 2 :g 1}}))

(defn- backend-fixture
  ([] (backend-fixture (catalog-memory/memory-store)))
  ([catalog]
   (let [ids (mapv #(str "node-" %) (range 7))
         fleet (into {} (map (fn [id] [id (fake-store id)]) ids))
         placement-context {:nodes (mapv (fn [id] {:id id}) ids)}
         backend (backend-for ids fleet placement-context catalog)]
     {:ids ids :fleet fleet :placement-context placement-context
      :catalog catalog :backend backend})))

(defn- block-fixture []
  (let [bytes (gf/->bytes (mapv #(mod (+ (* 17 %) 5) 256) (range 200)))]
    {:cid (mf/cidv1-raw bytes) :bytes bytes}))

(defn- mark-unavailable! [store shard-id]
  (swap! (:state store) update :unavailable conj shard-id))

(deftest cid-index-survives-reopening-a-file-backed-catalog
  (async done
    (let [directory (.mkdtempSync fs (.join path (.tmpdir os) "kura-catalog-restart-"))
          catalog-path (.join path directory "catalog.json")
          catalog (open-file-test-catalog catalog-path)
          open-catalog (atom catalog)
          {:keys [ids fleet placement-context backend]}
          (backend-fixture catalog)
          {:keys [cid bytes]} (block-fixture)
          cleanup (fn []
                    (reset! open-catalog nil)
                    (try (.rmSync fs directory #js {:recursive true :force true})
                         (catch :default _ nil)))]
      (-> (storage/-put-blocks! backend [{:cid cid :bytes bytes}])
          (.then (fn [_]
                   (reset! (:state catalog) nil)
                   (let [reopened (open-file-test-catalog catalog-path)
                         backend-after-restart
                         (backend-for ids fleet placement-context reopened)]
                     (reset! open-catalog reopened)
                     (storage/-get-blocks backend-after-restart [cid]))))
          (.then (fn [blocks]
                   (is (= (gf/->vec bytes)
                          (gf/->vec (get blocks cid)))
                       "reopened catalog resolves the CID to its CARv2 frame")))
          (.catch (fn [error]
                    (is false (str "durable catalog restart read failed: " error))))
          (.finally (fn [] (cleanup) (done)))))))

(deftest missing-data-range-uses-local-parity-before-full-pack-read
  (async done
    (let [{:keys [ids fleet backend]} (backend-fixture)
          {:keys [cid bytes]} (block-fixture)
          missing-store (get fleet (first ids))]
      (-> (storage/-put-blocks! backend [{:cid cid :bytes bytes}])
          (.then (fn [_]
                   (let [shard-id (first (keys (:shards @(:state missing-store))))]
                     (mark-unavailable! missing-store shard-id)
                     (storage/-get-blocks backend [cid]))))
          (.then (fn [blocks]
                   (is (= (gf/->vec bytes)
                          (gf/->vec (get blocks cid))))
                   (is (pos? (count (:range-reads @(:state (get fleet (nth ids 4))))))
                       "local parity range was fetched")
                   (is (zero? (reduce + (map #(count (:full-reads @(:state %)))
                                             (vals fleet))))
                       "successful local recovery avoids full-pack reconstruction")
                   (done)))
          (.catch (fn [error]
                    (is false (str "local parity recovery failed: " error))
                    (done)))))))

(deftest failed-local-parity-range-falls-back-to-digest-checked-pack-read
  (async done
    (let [{:keys [ids fleet backend]} (backend-fixture)
          {:keys [cid bytes]} (block-fixture)
          missing-data-store (get fleet (first ids))
          missing-parity-store (get fleet (nth ids 4))]
      (-> (storage/-put-blocks! backend [{:cid cid :bytes bytes}])
          (.then (fn [_]
                   (let [data-id (first (keys (:shards @(:state missing-data-store))))
                         parity-id (first (keys (:shards @(:state missing-parity-store))))]
                     (mark-unavailable! missing-data-store data-id)
                     (mark-unavailable! missing-parity-store parity-id)
                     (storage/-get-blocks backend [cid]))))
          (.then (fn [blocks]
                   (is (= (gf/->vec bytes)
                          (gf/->vec (get blocks cid))))
                   (is (pos? (reduce + (map #(count (:full-reads @(:state %)))
                                             (vals fleet))))
                       "Kura's full reconstruction is reached after local reads fail")
                   (done)))
          (.catch (fn [error]
                    (is false (str "verified full-pack fallback failed: " error))
                    (done)))))))

;; A winner already published this deterministic pack. A racing writer sees
;; an old empty catalog read and either loses CAS or gets an ambiguous error.
;; In every case the winner must still be able to read its committed bytes.
(defrecord RacingCatalog [inner fail-at]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (let [result (storage/-put-blocks! inner blocks)]
      (when (= :manifest fail-at)
        (throw (js/Error. "ambiguous manifest publication")))
      result))
  (-get-blocks [_ cids] (storage/-get-blocks inner cids))
  storage/IRefStore
  (-read-ref [_ name]
    (when-not (.startsWith name sut/catalog-prefix)
      (storage/-read-ref inner name)))
  (-compare-and-set-ref! [_ name expected next-cid]
    (let [result (storage/-compare-and-set-ref! inner name expected next-cid)]
      (when (= :cas fail-at)
        (throw (js/Error. "ambiguous catalog CAS")))
      result))
  storage/IBackendCapabilities
  (-capabilities [_] (storage/-capabilities inner)))

(deftest racing-writer-never-removes-the-winners-shared-pack
  (async done
    (-> (reduce
         (fn [previous fail-at]
           (.then previous
             (fn [_]
               (let [{:keys [ids fleet placement-context catalog backend]}
                     (backend-fixture)
                     block (block-fixture)
                     loser (backend-for ids fleet placement-context
                                        (->RacingCatalog catalog fail-at))]
                 (-> (storage/-put-blocks! backend [block])
                     (.then (fn [_]
                              (-> (storage/-put-blocks! loser [block])
                                  (.then (fn [result]
                                           (is (nil? fail-at))
                                           (is (= 1 (:contended (first result))))))
                                  (.catch (fn [error]
                                            (is (some? fail-at))
                                            (is (.includes (.-message error) "ambiguous")))))))
                     (.then (fn [_] (storage/-get-blocks backend [(:cid block)])))
                     (.then (fn [found]
                              (is (= (gf/->vec (:bytes block))
                                     (gf/->vec (get found (:cid block))))
                                  (str "winner survives racing mode " fail-at)))))))))
         (js/Promise.resolve nil)
         [nil :manifest :cas])
        (.catch (fn [error]
                  (is false (str "racing writer destroyed published data: " error))))
        (.finally done))))

(deftest rejected-block-is-never-written-to-the-shard-fleet
  (let [{:keys [fleet backend]} (backend-fixture)
        {:keys [cid]} (block-fixture)]
    (is (thrown? js/Error
                 (storage/-put-blocks! backend [{:cid cid :bytes (gf/->bytes [1 2 3])}])))
    (is (every? #(empty? (:shards @(:state %))) (vals fleet)))))
