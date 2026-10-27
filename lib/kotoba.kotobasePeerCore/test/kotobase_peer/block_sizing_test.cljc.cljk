(ns kotobase-peer.block-sizing-test
  (:require #?(:clj [kotoba.test :refer [deftest is testing]]
               :cljs [cljs.test :refer-macros [deftest is testing]])
            [kotobase-peer.block-sizing :as sizing]))

(defn- cohort [block-bytes samples wall]
  {:block-bytes block-bytes :samples samples :wall-p95-ms wall
   :cpu-ms 0 :fetched-blocks 0 :fetched-bytes 0 :cache-hit-ratio 0})

(deftest controller-moves-only-one-qualified-class
  (let [decision
        (sizing/select-next
         {:current 16384
          :observations [(cohort 16384 5 100)
                         (cohort 32768 5 70)
                         (cohort 65536 5 10)]})]
    (is (= 32768 (:selected decision)))
    (is (:changed? decision))
    (is (= :hysteresis-passed (:reason decision)))
    (is (= #{16384 32768} (set (keys (:qualified-scores decision)))))
    (is (< (abs (- 0.3 (:improvement-ratio decision))) 1.0e-9))))

(deftest controller-advances-at-most-one-class-per-epoch
  (let [observations [(cohort 16384 5 100)
                      (cohort 32768 5 70)
                      (cohort 65536 5 40)]
        first-epoch (sizing/select-next
                     {:current 16384 :observations observations})
        second-epoch (sizing/select-next
                      {:current (:selected first-epoch)
                       :observations observations})]
    (is (= 32768 (:selected first-epoch)))
    (is (= 65536 (:selected second-epoch)))))

(deftest controller-holds-for-samples-and-hysteresis
  (testing "the current cohort itself must be qualified"
    (is (= :insufficient-current-evidence
           (:reason
            (sizing/select-next
             {:current 32768
              :observations [(cohort 32768 2 100)
                             (cohort 65536 5 10)]})))))
  (testing "a small apparent win cannot flap the manifest size"
    (let [decision
          (sizing/select-next
           {:current 32768
            :observations [(cohort 32768 5 100)
                           (cohort 65536 5 95)]})]
      (is (= 32768 (:selected decision)))
      (is (= :hysteresis-held (:reason decision))))))

(deftest explicit-resource-costs-can-change-the-decision
  (let [observations
        [(assoc (cohort 16384 5 80)
                :fetched-blocks 12 :fetched-bytes 100000)
         (assoc (cohort 32768 5 85)
                :fetched-blocks 2 :fetched-bytes 120000)]
        wall-only (sizing/select-next
                   {:current 16384 :observations observations})
        request-aware
        (sizing/select-next
         {:current 16384 :observations observations
          :policy {:request-ms-equivalent 5
                   :hysteresis-ratio 0.05}})]
    (is (= 16384 (:selected wall-only)))
    (is (= 32768 (:selected request-aware)))))

(deftest malformed-or-duplicate-evidence-fails-closed
  (is (thrown? #?(:clj Exception :cljs js/Error)
               (sizing/select-next
                {:current 123
                 :observations []})))
  (is (thrown? #?(:clj Exception :cljs js/Error)
               (sizing/select-next
                {:current 16384
                 :observations [(cohort 16384 3 10)
                                (cohort 16384 4 9)]})))
  (is (thrown? #?(:clj Exception :cljs js/Error)
               (sizing/select-next
                {:current 16384
                 :observations [(assoc (cohort 16384 3 10)
                                       :cache-hit-ratio 1.1)]}))))
