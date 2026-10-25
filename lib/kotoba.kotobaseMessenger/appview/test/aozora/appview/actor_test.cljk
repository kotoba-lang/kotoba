(ns aozora.appview.actor-test
  "Backend read-projection tests for aozora.appview.actor — mirrors
  aozora.appview.convo-test's record-datoms/with-datoms fixture pattern
  (same feed/scan-yoro substrate)."
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.lang.text :as str]
            [kotobase.client :as kc]
            [aozora.appview.actor :as actor]))

(def db-name "yoro-social")

(defn- edn-str [s]
  (str "\"" (str/replace s "\"" "\\\"") "\""))

(defn- record-datoms [entity-id collection author-did value]
  [#js {:e entity-id :a ":atproto.record/uri"
       :v_edn (edn-str (str "at://" author-did "/" collection "/" entity-id)) :added true}
   #js {:e entity-id :a ":atproto.record/collection" :v_edn (edn-str collection) :added true}
   #js {:e entity-id :a ":atproto.record/did" :v_edn (edn-str author-did) :added true}
   #js {:e entity-id :a ":atproto.record/json" :v_edn (edn-str (js/JSON.stringify (clj->js value))) :added true}])

(defn- stub-datoms [entities-datoms]
  (let [all (into-array (apply concat entities-datoms))]
    (fn ([_ _ _] (js/Promise.resolve #js {:datoms all}))
        ([_ _ _ _] (js/Promise.resolve #js {:datoms all})))))

(defn- with-datoms [entities-datoms f]
  (let [orig kc/datoms]
    (set! kc/datoms (stub-datoms entities-datoms))
    (-> (f) (.finally (fn [] (set! kc/datoms orig))))))

(deftest list-blocks-returns-only-callers-own-blocks
  (async done
    (with-datoms
      [(record-datoms "b1" "app.aozora.actor.block" "did:web:alice"
                       {:did "did:web:alice" :blockedDid "did:web:mallory" :createdAt "2026-07-01T00:00:00Z"})
       ;; a different actor's block record — must not leak into alice's list
       (record-datoms "b2" "app.aozora.actor.block" "did:web:bob"
                       {:did "did:web:bob" :blockedDid "did:web:trudy" :createdAt "2026-07-01T00:00:00Z"})]
      #(-> (actor/list-blocks nil db-name {:did "did:web:alice"})
           (.then (fn [{:keys [blocks]}]
                    (is (= 1 (count blocks)))
                    (is (= "did:web:mallory" (:blockedDid (first blocks))))
                    (done)))))))

(deftest list-blocks-ignores-a-strangers-claimed-value-field
  (async done
    (with-datoms
      ;; authored by mallory but the :value claims :did "did:web:alice" —
      ;; author (top-level :did from the URI) must win, not the claim.
      [(record-datoms "b1" "app.aozora.actor.block" "did:web:mallory"
                       {:did "did:web:alice" :blockedDid "did:web:bob" :createdAt "2026-07-01T00:00:00Z"})]
      #(-> (actor/list-blocks nil db-name {:did "did:web:alice"})
           (.then (fn [{:keys [blocks]}]
                    (is (empty? blocks) "not authored by alice, so it doesn't count as alice's block")
                    (done)))))))

(deftest list-blocks-rejects-without-did
  (async done
    (-> (actor/list-blocks nil db-name {})
        (.then (fn [{:keys [blocks]}]
                 (is (empty? blocks))
                 (done))))))

(deftest blocked?-true-when-blocker-has-blocked-blocked-did
  (async done
    (with-datoms
      [(record-datoms "b1" "app.aozora.actor.block" "did:web:alice"
                       {:did "did:web:alice" :blockedDid "did:web:mallory" :createdAt "2026-07-01T00:00:00Z"})]
      #(-> (actor/blocked? nil db-name "did:web:alice" "did:web:mallory")
           (.then (fn [res] (is (true? res)) (done)))))))

(deftest blocked?-false-when-no-such-block-exists
  (async done
    (with-datoms
      [(record-datoms "b1" "app.aozora.actor.block" "did:web:alice"
                       {:did "did:web:alice" :blockedDid "did:web:mallory" :createdAt "2026-07-01T00:00:00Z"})]
      #(-> (actor/blocked? nil db-name "did:web:alice" "did:web:bob")
           (.then (fn [res] (is (false? res)) (done)))))))

(deftest blocked?-is-directional
  (async done
    (with-datoms
      ;; alice has blocked mallory, NOT the other way around
      [(record-datoms "b1" "app.aozora.actor.block" "did:web:alice"
                       {:did "did:web:alice" :blockedDid "did:web:mallory" :createdAt "2026-07-01T00:00:00Z"})]
      #(-> (actor/blocked? nil db-name "did:web:mallory" "did:web:alice")
           (.then (fn [res] (is (false? res) "mallory blocking alice is not the same as alice blocking mallory") (done)))))))
