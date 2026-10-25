(ns cloudflare.workers.provider-test
  "Provider conformance against stub bindings.

  The stubs are shaped like the real `KVNamespace` / `D1Database` / `R2Bucket`
  including the members the provider uses to tell them apart, so a shape check
  that passes here is the same check that passes in workerd."
  (:require [cljs.test :refer [deftest is testing async]]
            [cloudflare.workers.fixtures :as fix]
            [cloudflare.workers.provider :as provider]))

;; ---------------------------------------------------------------------------
;; Binding stubs
;; ---------------------------------------------------------------------------

(defn- kv-stub
  [store]
  #js {:get (fn [k] (js/Promise.resolve (get @store k)))
       :put (fn [k v _opts] (swap! store assoc k v) (js/Promise.resolve nil))
       :delete (fn [k] (swap! store dissoc k) (js/Promise.resolve nil))
       :getWithMetadata (fn [_k] (js/Promise.resolve nil))})

(defn- d1-stub
  [log]
  (letfn [(statement [sql params]
            #js {:bind (fn [& ps] (statement sql (vec ps)))
                 :all (fn []
                        (swap! log conj {:sql sql :params params :op :all})
                        (js/Promise.resolve #js {:results #js [] :meta #js {:rows_read 0}}))
                 :run (fn []
                        (swap! log conj {:sql sql :params params :op :run})
                        (js/Promise.resolve #js {:meta #js {:changes 1}}))})]
    #js {:prepare (fn [sql] (statement sql []))
         :batch (fn [_stmts] (js/Promise.resolve #js []))}))

(defn- r2-stub
  [store]
  #js {:get (fn [k]
              (js/Promise.resolve
               (when-let [bytes (get @store k)]
                 #js {:arrayBuffer (fn [] (js/Promise.resolve (.-buffer bytes)))
                      :size (.-length bytes)
                      :httpMetadata #js {:contentType "image/png"}})))
       :put (fn [k body _opts] (swap! store assoc k body) (js/Promise.resolve nil))
       :delete (fn [k] (swap! store dissoc k) (js/Promise.resolve nil))
       :head (fn [_k] (js/Promise.resolve nil))})

(defn- env
  [{:keys [kv d1 r2]}]
  #js {:SESSIONS (kv-stub (or kv (atom {})))
       :READONLY (kv-stub (atom {}))
       :WIDE (kv-stub (atom {}))
       :APP_DB (d1-stub (or d1 (atom [])))
       :ASSETS (r2-stub (or r2 (atom {})))})

;; ---------------------------------------------------------------------------

(deftest admitted-commands-run-and-report-typed-events
  (async done
    (let [store (atom {})]
      (-> (provider/execute! {:env (env {:kv store})
                              :policy fix/policy
                              :commands [fix/session-write fix/session-read]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :allowed (:outcome r)))
                   (is (= [:cf.kv/written :cf.kv/value] (mapv :event (:events r))))
                   (is (= "ok" (get @store "user:42")))
                   (is (true? (:found (second (:events r)))))
                   (is (= 2 (count (:receipts r))))
                   (done)))))))

(deftest a-denied-batch-runs-nothing
  (testing "the property the whole design exists for"
    (async done
      (let [store (atom {})
            batch [fix/session-write
                   {:cmd :cf.kv/put :binding "SESSIONS" :key "admin:1" :value "escalate"}]]
        (-> (provider/execute! {:env (env {:kv store})
                                :policy fix/policy
                                :commands batch
                                :now fix/now})
            (.then (fn [r]
                     (is (= :denied (:outcome r)))
                     (is (= :key-outside-prefix-scope (:reason r)))
                     (is (= [] (:events r)))
                     (is (= {} @store)
                         "the admissible first command must not have been applied")
                     (done))))))))

(deftest d1-executes-the-registered-sql-not-anything-the-guest-said
  (async done
    (let [log (atom [])]
      (-> (provider/execute! {:env (env {:d1 log})
                              :policy fix/policy
                              :commands [fix/order-query]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :allowed (:outcome r)))
                   (is (= :cf.d1/rows (:event (first (:events r)))))
                   (is (= [{:sql "select id, qty from orders where id = ?1"
                            :params ["o-1"]
                            :op :all}]
                          @log)
                       "SQL text came from policy; the guest supplied only params")
                   (done)))))))

(deftest r2-round-trips-binary-through-base64
  (async done
    (let [store (atom {})]
      (-> (provider/execute! {:env (env {:r2 store})
                              :policy fix/policy
                              :commands [fix/asset-write
                                         {:cmd :cf.r2/get :binding "ASSETS"
                                          :key "img/logo.png"}]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :allowed (:outcome r)))
                   (let [object (second (:events r))]
                     (is (true? (:found object)))
                     (is (= {:b64 "AAAA"} (:body object))
                         "bodies come back base64 -- lossless for binary")
                     (is (= 3 (:size object))))
                   (done)))))))

(deftest a-missing-binding-is-a-failure-not-a-silent-skip
  (async done
    (let [store (atom {})
          incomplete (doto (env {:kv store}) (js-delete "APP_DB"))]
      (-> (provider/execute! {:env incomplete
                              :policy fix/policy
                              :commands [fix/session-write fix/order-query]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :failed (:outcome r)))
                   (is (= :binding-absent (:reason r)))
                   (is (= 1 (:index r)))
                   (is (= 1 (count (:events r)))
                       "the command before the failure did run; execution stops there")
                   (is (= "ok" (get @store "user:42")))
                   (done)))))))

(deftest a-mis-shaped-binding-is-caught-before-use
  (async done
    (let [wrong (doto (env {}) (unchecked-set "APP_DB" (kv-stub (atom {}))))]
      (-> (provider/execute! {:env wrong
                              :policy fix/policy
                              :commands [fix/order-query]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :failed (:outcome r)))
                   (is (= :binding-shape-mismatch (:reason r)))
                   (done)))))))

(deftest a-provider-error-is-reported-as-failed-not-denied
  (async done
    (let [exploding #js {:get (fn [_] (js/Promise.reject (js/Error. "KV is down")))
                         :put (fn [_ _ _] (js/Promise.reject (js/Error. "KV is down")))
                         :delete (fn [_] (js/Promise.resolve nil))
                         :getWithMetadata (fn [_] (js/Promise.resolve nil))}]
      (-> (provider/execute! {:env #js {:SESSIONS exploding}
                              :policy fix/policy
                              :commands [fix/session-read]
                              :now fix/now})
          (.then (fn [r]
                   (is (= :failed (:outcome r)))
                   (is (= :provider-error (:reason r)))
                   (is (= "KV is down" (:detail r)))
                   (is (= :failed (:receipt/outcome (last (:receipts r))))
                       "an availability failure must not read as an authorization denial")
                   (done)))))))

(deftest preflight-catches-a-deploy-that-does-not-match-its-policy
  (let [problems (provider/preflight #js {:SESSIONS (kv-stub (atom {}))} fix/policy)]
    (is (= #{"READONLY" "WIDE" "APP_DB" "ASSETS"}
           (set (map :binding problems))))
    (is (every? (fn [p] (= :binding-absent (:problem p))) problems)))
  (testing "a matching deployment is clean"
    (is (= [] (provider/preflight (env {}) fix/policy)))))
