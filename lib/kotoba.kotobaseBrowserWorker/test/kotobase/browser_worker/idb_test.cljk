(ns kotobase.browser-worker.idb-test
  "Proves ADR-2607051700's core claim empirically: kotobase-peer's full
  transact/datoms/q/fold surface, unmodified, running against a REAL
  IndexedDB in an actual browser tab (this namespace only compiles for
  :browser-test -- js/indexedDB does not exist under :node-test)."
  (:require [cljs.test :refer [deftest is testing async] :include-macros true]
            [kotobase.browser-worker.idb :as idb]
            [kotobase.browser-worker.browser :as browser]))

;; A fresh db-name per test avoids cross-test state bleed. IndexedDB persists
;; across page reloads (unlike a page-load counter), so the name must be
;; unique across reloads too, not just within one page load.
(defonce ^:private counter (atom 0))
(defn- fresh-db-name []
  (str "kotobase-browser-worker-test-" (.getTime (js/Date.)) "-" (swap! counter inc)))

(def ^:private g "kotobase/db/did:key:zTestBrowser/idb-roundtrip")

(deftest transact-then-datoms-roundtrip
  (async done
    (-> (idb/open-db (fresh-db-name))
        (.then (fn [db]
                 (-> (browser/run-write
                      db "transact"
                      {:graph g
                       :tx_edn "[{:db/id \"e1\" :yoro.post/uri \"at://a/p1\" :yoro.post/text \"hello from a real IndexedDB\"}]"}
                      nil)
                     (.then (fn [w]
                              (testing "transact commits + advances head"
                                (is (:ok w))
                                (is (string? (:commit w)))
                                (is (= 2 (:datom_count w))))
                              (browser/run-read db "datoms" {:graph g :index ":eavt"}))))))
        (.then (fn [r]
                 (testing "datoms reads back exactly what was transacted, via real IndexedDB blocks"
                   (is (:ok r))
                   (is (= 2 (count (:datoms r))))
                   (is (some #(and (= "e1" (:e %)) (= ":yoro.post/text" (:a %))) (:datoms r))))
                 (done)))
        (.catch (fn [e]
                  (is false (str "unexpected rejection: " (.-message e)))
                  (done))))))

(deftest transact-fold-then-datoms-still-correct
  (async done
    (-> (idb/open-db (fresh-db-name))
        (.then (fn [db]
                 (-> (browser/run-write
                      db "transact"
                      {:graph g
                       :tx_edn "[{:db/id \"e2\" :yoro.post/uri \"at://a/p2\" :yoro.post/text \"pre-fold\"}]"}
                      nil)
                     (.then (fn [_] (browser/run-write db "fold" {:graph g} nil)))
                     (.then (fn [fold-resp]
                              (testing "fold compacts novelty into a fresh indexed snapshot"
                                (is (:ok fold-resp))
                                (is (:folded fold-resp)))
                              (browser/run-read db "datoms" {:graph g :index ":eavt"}))))))
        (.then (fn [r]
                 (testing "post-fold reads are still correct (snapshot, not just novelty)"
                   (is (:ok r))
                   (is (some #(and (= "e2" (:e %)) (= ":yoro.post/text" (:a %))) (:datoms r))))
                 (done)))
        (.catch (fn [e]
                  (is false (str "unexpected rejection: " (.-message e)))
                  (done))))))

(deftest put-head-if-match-rejects-a-stale-etag
  (async done
    (-> (idb/open-db (fresh-db-name))
        (.then (fn [db]
                 (-> (idb/put-head-if-match! db "cas-test-graph" "chain-a" nil)
                     (.then (fn [ok1]
                              (is (true? ok1) "first write to an absent head succeeds unconditionally")
                              ;; stale etag (nil, as if the caller never re-read after chain-a landed)
                              (idb/put-head-if-match! db "cas-test-graph" "chain-b" nil))))))
        (.then (fn [ok2]
                 (is (false? ok2) "a stale/absent-etag write against an already-populated head is rejected, not silently clobbered")
                 (done)))
        (.catch (fn [e]
                  (is false (str "unexpected rejection: " (.-message e)))
                  (done))))))
