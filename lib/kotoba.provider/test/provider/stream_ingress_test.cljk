(ns provider.stream-ingress-test
  "The bidirectional stream provider, exercised as a host would drive it.

  Most of this suite is about the two decisions that are easy to get wrong in a
  way nothing observes: that a full queue closes the stream instead of dropping
  a frame, and that hearing and speaking are separate grants."
  (:require [clojure.test :refer [deftest is testing]]
            [provider.stream-ingress :as stream]))

(defn- accept! [p]
  ((get-in p [:providers stream/accept-capability-id :invoke])
   [stream/accept-request-type 0]))

(defn- send! [p id payload final]
  ((get-in p [:providers stream/send-capability-id :invoke])
   [stream/send-request-type id payload final]))

(defn- event [accepted]
  (when (second accepted) (nth accepted 2)))

;; ── the ordinary shape of a call ─────────────────────────────────────────────

(deftest test-open-frame-frame-close-arrive-in-order
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    ((:deliver! p) id "AAA")
    ((:deliver! p) id "BBB")
    ((:close! p) id :hangup)
    (let [evs (repeatedly 4 #(event (accept! p)))]
      (is (= [:opened :frame :frame :closed] (map second evs)))
      (testing "and the frames carry monotonic sequence numbers from zero"
        (is (= [0 1] (map #(nth (nth % 2) 3) (filter #(= :frame (second %)) evs))))))))

(deftest test-an-empty-queue-is-none-not-an-error
  (let [p (stream/create-provider)]
    (is (false? (second (accept! p))))))

(deftest test-accept-drains-one-event-at-a-time
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    ((:deliver! p) id "AAA")
    (is (= :opened (second (event (accept! p)))))
    (is (= 1 (:queued ((:snapshot p)))))
    (is (= :frame (second (event (accept! p)))))
    (is (= 0 (:queued ((:snapshot p)))))))

;; ── overflow closes; it does not drop ────────────────────────────────────────

(deftest test-a-full-queue-closes-the-stream-rather-than-losing-a-frame
  (testing "a dropped audio frame is inaudible to the program and audible to the caller"
    (let [p (stream/create-provider {:max-queue-depth 3})
          id ((:open! p) :media)]
      ;; :opened already occupies one slot; two frames fill it.
      (is (true? ((:deliver! p) id "A")))
      (is (true? ((:deliver! p) id "B")))
      (is (false? ((:deliver! p) id "C")) "the third is refused, not silently dropped")
      (let [evs (repeatedly 4 #(event (accept! p)))]
        (is (= [:opened :frame :frame :closed] (map second evs)))
        (testing "and the close says why"
          (is (= :queue-overflow (nth (nth (last evs) 2) 2))))))))

(deftest test-a-closed-stream-refuses-further-frames
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    ((:close! p) id :hangup)
    (is (thrown? Exception ((:deliver! p) id "A")))))

;; ── hearing is not permission to speak ───────────────────────────────────────

(deftest test-the-two-capabilities-are-separate-ids
  (is (not= stream/accept-capability-id stream/send-capability-id))
  (testing "so a host can install one without the other"
    (let [p (stream/create-provider)]
      (is (contains? (:providers p) 25))
      (is (contains? (:providers p) 26)))))

(deftest test-sending-records-what-was-said
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    (is (true? (send! p id "hello" false)))
    (is (= [{:stream id :payload "hello" :final false}] ((:sent p))))))

(deftest test-a-final-frame-closes-the-stream
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    (send! p id "bye" true)
    (is (= 0 (:open ((:snapshot p)))))
    (testing "and the close is observable, not just internal"
      (let [evs (repeatedly 2 #(event (accept! p)))]
        (is (= [:opened :closed] (map second evs)))
        (is (= :sent-final (nth (nth (last evs) 2) 2)))))))

(deftest test-speaking-into-a-closed-stream-is-refused
  (let [p (stream/create-provider)
        id ((:open! p) :media)]
    ((:close! p) id :hangup)
    (is (thrown? Exception (send! p id "hello" false)))))

;; ── bounds ───────────────────────────────────────────────────────────────────

(deftest test-open-streams-are-capped
  (let [p (stream/create-provider {:max-open-streams 2})]
    ((:open! p) :media)
    ((:open! p) :media)
    (is (thrown? Exception ((:open! p) :media)))
    (testing "and closing one frees a slot"
      (let [p2 (stream/create-provider {:max-open-streams 1})
            a ((:open! p2) :media)]
        ((:close! p2) a :hangup)
        (is (some? ((:open! p2) :media)))))))

(deftest test-configuration-outside-the-kit-limits-is-refused
  (is (thrown? Exception (stream/create-provider {:max-queue-depth 0})))
  (is (thrown? Exception (stream/create-provider {:max-queue-depth 2048})))
  (is (thrown? Exception (stream/create-provider {:max-open-streams 0})))
  (is (thrown? Exception (stream/create-provider {:max-open-streams 128}))))

(deftest test-a-contract-mismatch-is-refused
  (let [p (stream/create-provider)]
    (is (thrown? Exception
                 ((get-in p [:providers stream/accept-capability-id :invoke])
                  [[:record :wrong/type [[:slot :i64]]] 0])))
    (testing "and a non-zero slot, which v1 does not define"
      (is (thrown? Exception
                   ((get-in p [:providers stream/accept-capability-id :invoke])
                    [stream/accept-request-type 1]))))))
