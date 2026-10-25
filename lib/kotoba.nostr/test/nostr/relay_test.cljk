(ns nostr.relay-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotobase.local :as local]
            [kotobase.store :as st]
            [nostr.event :as event]
            [nostr.fixtures :as fx]
            [nostr.relay :as relay]))

(defn- ctx [] {:store (local/local-store)})

(deftest accept-and-store-regular-event
  (let [c (ctx)
        ev (fx/text-note fx/alice-sk "hello")
        {:keys [ok? stored? duplicate?]} (relay/handle-event! c ev)]
    (is ok?)
    (is stored?)
    (is (not duplicate?))
    (is (= ev (st/-get (:store c) relay/events-coll (get ev "id"))))))

(deftest duplicate-event-is-a-no-op-ok
  (let [c (ctx)
        ev (fx/text-note fx/alice-sk "hello")]
    (relay/handle-event! c ev)
    (let [{:keys [ok? stored? duplicate?]} (relay/handle-event! c ev)]
      (is ok?)
      (is (not stored?))
      (is duplicate?))))

(deftest invalid-event-rejected
  (let [c (ctx)
        ev (assoc (fx/text-note fx/alice-sk "hello") "content" "tampered")
        {:keys [ok? reason stored?]} (relay/handle-event! c ev)]
    (is (not ok?))
    (is (= :id-mismatch reason))
    (is (not stored?))
    (is (nil? (st/-get (:store c) relay/events-coll (get ev "id"))))))

(deftest replaceable-event-keeps-only-newest
  (let [c (ctx)
        profile1 (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 100 "tags" [] "content" "{\"name\":\"v1\"}"})
        profile2 (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 200 "tags" [] "content" "{\"name\":\"v2\"}"})]
    (relay/handle-event! c profile1)
    (let [{:keys [ok? stored?]} (relay/handle-event! c profile2)]
      (is ok?) (is stored?))
    (is (nil? (st/-get (:store c) relay/events-coll (get profile1 "id")))
        "older replaceable event was deleted")
    (is (= profile2 (st/-get (:store c) relay/events-coll (get profile2 "id"))))))

(deftest replaceable-event-rejects-older-arriving-late
  (let [c (ctx)
        profile1 (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 200 "tags" [] "content" "{\"name\":\"v2\"}"})
        profile-old (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 100 "tags" [] "content" "{\"name\":\"v1\"}"})]
    (relay/handle-event! c profile1)
    (let [{:keys [ok? stored? reason]} (relay/handle-event! c profile-old)]
      (is ok? "still OK per NIP-01 relay convention, just not stored")
      (is (not stored?))
      (is (= :superseded-by-newer reason)))
    (is (= profile1 (st/-get (:store c) relay/events-coll (get profile1 "id"))))))

(deftest addressable-event-scoped-by-d-tag
  (let [c (ctx)
        art1 (fx/sign-event fx/alice-sk {"kind" 30023 "created_at" 100 "tags" [["d" "post-a"]] "content" "draft"})
        art1v2 (fx/sign-event fx/alice-sk {"kind" 30023 "created_at" 200 "tags" [["d" "post-a"]] "content" "final"})
        art2 (fx/sign-event fx/alice-sk {"kind" 30023 "created_at" 150 "tags" [["d" "post-b"]] "content" "other"})]
    (relay/handle-event! c art1)
    (relay/handle-event! c art1v2)
    (relay/handle-event! c art2)
    (is (nil? (st/-get (:store c) relay/events-coll (get art1 "id"))) "post-a v1 replaced")
    (is (= art1v2 (st/-get (:store c) relay/events-coll (get art1v2 "id"))))
    (is (= art2 (st/-get (:store c) relay/events-coll (get art2 "id"))) "different d-tag, independent slot")))

(deftest ephemeral-event-accepted-but-not-stored
  (let [c (ctx)
        ev (fx/sign-event fx/alice-sk {"kind" 20001 "created_at" 100 "tags" [] "content" "typing..."})
        {:keys [ok? stored?]} (relay/handle-event! c ev)]
    (is ok?)
    (is (not stored?))
    (is (nil? (st/-get (:store c) relay/events-coll (get ev "id"))))))

(deftest audit-trail-records-writes
  (let [c (ctx)
        ev (fx/text-note fx/alice-sk "audited")]
    (relay/handle-event! c ev)
    (let [events (st/-read (:store c) :nostr.relay/audit 0)]
      (is (= [:store] (map :op events))))))

;; -------------------------------------------------------- client message dispatch

(deftest handle-client-message-event-flow
  (let [c (ctx)
        ev (fx/text-note fx/alice-sk "via EVENT message")
        {:keys [type ok-message accepted-event]} (relay/handle-client-message c ["EVENT" ev])]
    (is (= :event-result type))
    (is (= ["OK" (get ev "id") true ""] ok-message))
    (is (= ev accepted-event))))

(deftest handle-client-message-event-rejects-invalid
  (let [c (ctx)
        ev (assoc (fx/text-note fx/alice-sk "x") "sig" (apply str (repeat 128 "0")))
        {:keys [type ok-message accepted-event]} (relay/handle-client-message c ["EVENT" ev])]
    (is (= :event-result type))
    (is (= false (nth ok-message 2)))
    (is (nil? accepted-event))))

(deftest handle-client-message-req-flow
  (let [c (ctx)
        ev1 (fx/text-note fx/alice-sk "one" {:created_at 100})
        ev2 (fx/text-note fx/alice-sk "two" {:created_at 200})]
    (relay/handle-event! c ev1)
    (relay/handle-event! c ev2)
    (let [{:keys [type sub-id filters messages]}
          (relay/handle-client-message c ["REQ" "sub1" {"authors" [(fx/pubkey fx/alice-sk)]}])]
      (is (= :req-result type))
      (is (= "sub1" sub-id))
      (is (= [{"authors" [(fx/pubkey fx/alice-sk)]}] filters))
      (is (= ["EVENT" "sub1" ev2] (first messages)))
      (is (= ["EVENT" "sub1" ev1] (second messages)))
      (is (= ["EOSE" "sub1"] (last messages))))))

(deftest handle-client-message-close-flow
  (let [c (ctx)
        {:keys [type sub-id message]} (relay/handle-client-message c ["CLOSE" "sub1"])]
    (is (= :close-result type))
    (is (= "sub1" sub-id))
    (is (= ["CLOSED" "sub1" ""] message))))

(deftest handle-client-message-unknown-type-notice
  (let [c (ctx)
        {:keys [type message]} (relay/handle-client-message c ["BOGUS" 1 2 3])]
    (is (= :notice type))
    (is (= "NOTICE" (first message)))))

(deftest handle-client-message-superseded-replaceable-not-fanned-out
  ;; Regression: a stale replaceable event arriving late gets a true OK
  ;; (per NIP-01 convention) but must NOT be handed back as :accepted-event
  ;; — the transport layer uses that field to decide what to live-broadcast
  ;; to other subscribers, and this event was never actually stored.
  (let [c (ctx)
        profile-new (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 200 "tags" [] "content" "{\"name\":\"v2\"}"})
        profile-old (fx/sign-event fx/alice-sk {"kind" 0 "created_at" 100 "tags" [] "content" "{\"name\":\"v1\"}"})]
    (relay/handle-client-message c ["EVENT" profile-new])
    (let [{:keys [ok-message accepted-event]} (relay/handle-client-message c ["EVENT" profile-old])]
      (is (true? (nth ok-message 2)) "NIP-01 convention: OK is still true")
      (is (nil? accepted-event) "must not be live-broadcast — it was not actually stored"))))
