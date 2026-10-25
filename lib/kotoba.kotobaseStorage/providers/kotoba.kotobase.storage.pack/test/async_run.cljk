(ns async-run
  "The Promise-returning packed block store.

  Same claim as the synchronous suite and a different runtime: on a Worker
  every object read is a Promise, so a store that used the answer directly
  would not run there at all. The numbers must come out the same, because
  the plan is the same code."
  (:require [datalog.core :as d]
            [datalog.index :as index]
            [ipld.car.bytes :as b]
            [ipld.core :as ipld]
            [kotobase.storage.core :as storage]
            [kotobase.storage.object :as object]
            [kotobase.storage.object-memory :as omem]
            [kotobase.storage.pack :as pack]
            [kotobase.storage.pack-async :as apack]
            [kotobase.storage.pack-catalog :as cat]
            [kotobase.storage.pack-catalog-async :as acat]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defrecord AsyncObjects [inner]
  object/IObjectStore
  (-stat-object [_ cid] (js/Promise.resolve (object/-stat-object inner cid)))
  (-delete-object! [_ cid] (js/Promise.resolve (object/-delete-object! inner cid)))
  object/IProxiedTransfer
  (-put-object! [_ cid bytes] (js/Promise.resolve (object/-put-object! inner cid bytes)))
  (-get-object [_ cid] (js/Promise.resolve (object/-get-object inner cid)))
  object/IRangeRead
  (-get-object-range [_ cid start end]
    (js/Promise.resolve (object/-get-object-range inner cid start end)))
  object/IObjectCapabilities
  (-object-capabilities [_] (object/-object-capabilities inner)))

(defn- async-objects [] (->AsyncObjects (omem/memory-object-store)))

(defn- cons-chain [n]
  (loop [i (dec n) next-cid nil acc ()]
    (if (neg? i)
      (vec acc)
      (let [blk (ipld/node->block
                 (cond-> {"e" i} next-cid (assoc "rest" (ipld/link next-cid))))]
        (recur (dec i) (:cid blk) (conj acc blk))))))

(defn- walk-chain!
  "Follow the chain one link at a time, as a hydrate loop must."
  [store head-cid seen]
  (-> (storage/-get-blocks store [head-cid])
      (.then (fn [got]
               (let [node (ipld/decode (get got head-cid))
                     nxt (some-> (get node "rest") ipld/link-cid)
                     seen (conj seen (get node "e"))]
                 (if nxt (walk-chain! store nxt seen) (js/Promise.resolve seen)))))))

(defn- measure [opts]
  (let [objects (async-objects)
        chain (cons-chain 100)
        store (apack/pack-block-store objects (pack/memory-catalog) opts)]
    (-> (storage/-put-blocks! store chain)
        (.then (fn [_]
                 (apack/drop-cache! store)
                 (apack/reset-stats! store)
                 (walk-chain! store (:cid (first chain)) [])))
        (.then (fn [seen] {:seen seen :stats (apack/stats store)
                           :objects objects :chain chain})))))


;; ── a datom catalog whose ports resolve LATER ───────────────────────────────
;;
;; The sync catalog test uses a real Datalog engine because "a map will agree
;; with anything". The same applies twice over here: a fake whose promises are
;; already resolved would agree with a catalog that never awaited at all. These
;; ports defer a microtask and count their calls, so the suite can show that
;; the value genuinely was not available when `lookup` returned.

(defn- deferred-datalog-catalog []
  (let [db (atom (index/empty-db))
        calls (atom {:q 0 :transact 0})
        later (fn [thunk]
                (-> (js/Promise.resolve nil) (.then (fn [_] (thunk)))))]
    {:db db
     :calls calls
     :catalog
     (acat/datom-catalog
      {:transact! (fn [quads]
                    (swap! calls update :transact inc)
                    (later (fn []
                             (swap! db (fn [dbv]
                                         (reduce #(index/assert-quad %1 %2 cat/cid-ref?)
                                                 dbv quads)))
                             nil)))
       :q (fn [query inputs]
            (swap! calls update :q inc)
            (later (fn [] (d/q @db query (constantly true) inputs))))})}))

(defn -main [& _]
  (-> (measure {})
      (.then
       (fn [{:keys [seen stats]}]
         (expect (= (range 100) seen) "every link was actually followed")
         (expect (= 1 (:requests stats))
                 (str "100 links, 1 range request on the Promise path: "
                      (pr-str stats)))
         (expect (= 99 (:cache-hits stats)) "and 99 of them came from the window")))

      (.then (fn [_] (measure {:window-bytes 0 :cache-bytes 0})))
      (.then
       (fn [{:keys [stats]}]
         (expect (= 100 (:requests stats))
                 (str "without a window the same walk costs 100: " (pr-str stats)))))

      ;; the catalog is a projection, and this is what makes that checkable
      (.then (fn [_]
               (let [objects (async-objects)
                     blocks (mapv #(ipld/node->block {"kind" "leaf" "v" %}) (range 5))
                     catalog (pack/memory-catalog)
                     store (apack/pack-block-store objects catalog)]
                 (-> (storage/-put-blocks! store blocks)
                     (.then (fn [_]
                              (let [pack-cid (:pack-cid (first (vals ((:snapshot catalog)))))]
                                (apack/rebuild-catalog! objects pack-cid))))
                     (.then (fn [recovered]
                              (let [original ((:snapshot catalog))]
                                (expect (= (set (keys original))
                                           (set (map :cid recovered)))
                                        "a lost catalog is recovered from the pack itself")
                                (expect (= (select-keys (get original (:cid (first recovered)))
                                                        [:file-offset :frame-length])
                                           (select-keys (first recovered)
                                                        [:file-offset :frame-length]))
                                        "with the same offsets the writer recorded"))))))))

      ;; ── the catalog on Promise-returning ports ─────────────────────────
      ;;
      ;; Until now every async run here used `memory-catalog`, which is a map
      ;; and answers instantly. A Worker's datom store does not, and a catalog
      ;; that assumed it did was why this plane could not be wired to one.
      ;;
      ;; Cheapest and most specific first, deliberately. Both of the ways this
      ;; namespace can break -- not awaiting a port, and keeping a CID with no
      ;; location -- take the chain walk down with a throw, and a runner that
      ;; exits on the first throw would never reach the checks that say WHICH
      ;; of the two happened. Measured: both breaks killed the walk before
      ;; these three assertions ran even once.
      ;; That the ports are really asynchronous, rather than promises that
      ;; were already resolved -- which a catalog that never awaited would
      ;; also satisfy.
      (.then
       (fn [_]
         (let [{:keys [catalog]} (deferred-datalog-catalog)
               blk (ipld/node->block {"kind" "leaf" "v" 1})
               entry {:cid (:cid blk) :pack-cid "bafyPACK"
                      :file-offset 7 :frame-length 11}
               resolved (atom nil)
               p (-> (js/Promise.resolve ((:record! catalog) [entry]))
                     (.then (fn [_] ((:lookup catalog) [(:cid blk)])))
                     (.then (fn [got] (reset! resolved got))))]
           ;; This first one does NOT discriminate on its own: a catalog that
           ;; never awaited its ports still returns a Promise, so `@resolved`
           ;; is nil here either way. It is the second one that needs the
           ;; ports to have been awaited, and the `.catch` is what makes a
           ;; rejection show up as this test failing rather than as the
           ;; runner dying and everything after it being skipped.
           (expect (nil? @resolved)
                   "lookup had not produced its answer when it returned")
           (-> p
               (.then (fn [_]
                        (expect (= entry (get @resolved (:cid blk)))
                                "and the answer, once awaited, is the row that was written")))
               (.catch (fn [e]
                         (expect false (str "lookup rejected instead of resolving: "
                                            (or (some-> e .-message) e)))))))))

      ;; A CID with no location must be ABSENT from the lookup, not present
      ;; with a nil value: `-get-blocks` reads `(vals located)` and would
      ;; plan a run for a frame that has no offset.
      (.then
       (fn [_]
         (let [objects (async-objects)
               {:keys [catalog]} (deferred-datalog-catalog)
               store (apack/pack-block-store objects catalog)
               stranger (:cid (ipld/node->block {"kind" "never-stored"}))]
           ;; `-get-blocks` is entered through a `.then` rather than called
           ;; directly: `lookup` evaluates its queries synchronously, so a
           ;; catalog that throws does so BEFORE the promise this `->` would
           ;; attach `.catch` to exists, and the rejection escapes to the
           ;; runner instead. Measured -- the guard below did nothing until
           ;; the call moved inside a callback.
           (-> (js/Promise.resolve nil)
               (.then (fn [_] (storage/-get-blocks store [stranger])))
               (.then (fn [got]
                        (expect (= {} got) "an unknown CID yields nothing")
                        (expect (zero? (:requests (apack/stats store)))
                                "and costs no object request")))
               (.catch (fn [e]
                         ;; Keeping the CID with a nil value does not return a
                         ;; wrong answer here -- it plans a run for a frame
                         ;; with no offset and the object store rejects a nil
                         ;; CID. Naming it keeps the rest of the suite alive.
                         (expect false (str "an unknown CID reached the object store: "
                                            (or (some-> e .-message) e)))))))))

      (.then
       (fn [_]
         (let [objects (async-objects)
               {:keys [catalog calls]} (deferred-datalog-catalog)
               chain (cons-chain 40)
               store (apack/pack-block-store objects catalog)]
           (-> (js/Promise.resolve nil)
               (.then (fn [_] (storage/-put-blocks! store chain)))
               (.then (fn [_]
                        (apack/drop-cache! store)
                        (apack/reset-stats! store)
                        (walk-chain! store (:cid (first chain)) [])))
               (.then
                (fn [seen]
                  (let [stats (apack/stats store)]
                    (expect (= (range 40) seen)
                            "40 links followed through a Promise-returning catalog")
                    (expect (= :served (:evidence stats))
                            "and blocks were actually served, not merely counted")
                    (expect (= 40 (:blocks-served stats)) "all 40 of them")
                    (expect (= 1 (:requests stats))
                            (str "still one ranged GET -- the catalog changed, "
                                 "not the plan: " (pr-str stats)))
                    ;; The honest other half. Packing removed 39 object round
                    ;; trips and removed none on the datom plane: one
                    ;; `locate-query` per link, because a hydrate loop can
                    ;; only ask for the CID it has just decoded.
                    (expect (= 40 (:q @calls))
                            (str "and 40 catalog queries, one per link -- "
                                 "packing does not remove these: "
                                 (pr-str @calls))))))
               (.catch (fn [e]
                         (expect false (str "the packed walk failed: "
                                            (or (some-> e .-message) e)))))))))

      ;; ── the pack chain on the Promise driver ────────────────────────────
      (.then
       (fn [_]
         (let [objects (async-objects)
               store (apack/pack-block-store objects (pack/memory-catalog))
               commits (mapv (fn [c]
                               (mapv #(ipld/node->block {"kind" "leaf"
                                                         "v" (+ (* c 10) %)})
                                     (range 4)))
                             (range 3))]
           (-> (reduce (fn [p blocks]
                         (.then p (fn [_] (storage/-put-blocks! store blocks))))
                       (js/Promise.resolve nil)
                       commits)
               (.then (fn [_]
                        (apack/bootstrap-catalog! objects (apack/tip-pack store))))
               (.then
                (fn [recovered]
                  (expect (= 3 (count (distinct (map :pack-cid recovered))))
                          "three commits sealed three chained packs")
                  (expect (= (set (map :cid (apply concat commits)))
                             (set (map :cid recovered)))
                          "and the tip alone locates every block, with no catalog")))
               (.catch (fn [e]
                         (expect false (str "the chain walk failed: "
                                            (or (some-> e .-message) e)))))))))

      ;; ── the recovery drill, and that both drivers judge it the same ─────
      ;;
      ;; The synchronous suite proves what a hole in the chain does. What
      ;; this proves is that the Promise driver says the SAME word about it.
      ;; Two walks that each classify a broken chain their own way is the
      ;; failure `pack-plan` exists to prevent, and it is invisible until
      ;; something breaks -- which is exactly when the two answers matter.
      (.then
       (fn [_]
         (let [inner (omem/memory-object-store)
               objects (->AsyncObjects inner)
               store (apack/pack-block-store objects (pack/memory-catalog))
               commits (mapv (fn [c]
                               (mapv #(ipld/node->block {"kind" "leaf"
                                                         "v" (+ (* c 20) %)})
                                     (range 3)))
                             (range 3))]
           (-> (reduce (fn [p blocks]
                         (.then p (fn [_] (storage/-put-blocks! store blocks))))
                       (js/Promise.resolve nil)
                       commits)
               (.then (fn [_] (apack/bootstrap-report objects (apack/tip-pack store))))
               (.then
                (fn [{:keys [entries complete? terminated]}]
                  (expect (and complete? (= :chain-start terminated))
                          "an intact chain terminates at :chain-start")
                  (let [tip (apack/tip-pack store)
                        middle (second (distinct (map :pack-cid entries)))]
                    ;; delete through the inner store: the async wrapper is
                    ;; the store under test, not a fixture to mutate.
                    (object/-delete-object! inner middle)
                    (-> (apack/bootstrap-report objects tip)
                        (.then (fn [report]
                                 (expect (= :missing-pack (:terminated report))
                                         "and a hole terminates at :missing-pack, the same word the synchronous driver uses")
                                 (expect (false? (:complete? report))
                                         "not complete")
                                 (expect (= middle (:stopped-at report))
                                         "naming the pack that is gone")
                                 (expect (= 3 (count (:entries report)))
                                         "keeping the tip pack's entries, which alone look exactly like a healthy one-pack store")))
                        (.then (fn [_]
                                 (-> (apack/bootstrap-catalog! objects tip)
                                     (.then (fn [_]
                                              (expect false "bootstrap-catalog! returned a fragment as a catalog")))
                                     (.catch (fn [e]
                                               (expect (= :kotobase.storage.pack/incomplete-chain
                                                          (:type (ex-data e)))
                                                       "and the entries-only form rejects rather than returning it"))))))))))
               (.catch (fn [e]
                         (expect false (str "the async drill failed: "
                                            (or (some-> e .-message) e)))))))))

      (.then (fn [_]
               (if (zero? @failures)
                 (println "async packed block store: all green")
                 (do (println (str "async packed block store: " @failures
                                   " FAILURE(S) above"))
                     (js/process.exit 1)))))
      (.catch (fn [e]
                (js/console.error (str "async runner threw: " e))
                (js/process.exit 1)))))

(-main)
