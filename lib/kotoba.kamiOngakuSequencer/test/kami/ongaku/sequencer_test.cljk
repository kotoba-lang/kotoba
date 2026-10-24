(ns kami.ongaku.sequencer-test
  (:require [kami.ongaku.sequencer :as sq]
            #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])))

;; ---------------------------------------------------------------------------
;; validation

(deftest validate-event-note-ok
  (is (empty? (sq/validate-event {:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 480 :channel 0}))))

(deftest validate-event-note-out-of-range
  (let [errs (sq/validate-event {:type :note :pitch 200 :velocity 999 :tick -1 :duration-ticks 0 :channel 20})]
    (is (= 5 (count errs)))))

(deftest validate-event-pitch-bend-range
  (is (empty? (sq/validate-event {:type :pitch-bend :value -8192 :tick 0 :channel 0})))
  (is (empty? (sq/validate-event {:type :pitch-bend :value 8191 :tick 0 :channel 0})))
  (is (seq (sq/validate-event {:type :pitch-bend :value 8192 :tick 0 :channel 0}))))

(deftest validate-event-unknown-type
  (is (= ["unknown event :type :bogus"] (sq/validate-event {:type :bogus :tick 0}))))

(deftest validate-pattern-overflow
  (let [pattern {:length-ticks 480
                 :events [{:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 480 :channel 0}
                          {:type :note :pitch 62 :velocity 100 :tick 240 :duration-ticks 480 :channel 0}]}]
    (is (= 1 (count (filter #(re-find #"exceed pattern length-ticks" %) (sq/validate-pattern pattern)))))))

;; ---------------------------------------------------------------------------
;; quantize (PPQ 480, 16th-note grid = 120 ticks)

(deftest quantize-full-strength-no-swing
  (let [events [{:type :note :tick 50 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}
                {:type :note :tick 100 :pitch 61 :velocity 100 :duration-ticks 10 :channel 0}]
        out (sq/quantize-events events 120 {:strength 1.0 :swing 0.0})]
    (is (= [0 120] (mapv :tick out)))))

(deftest quantize-partial-strength
  (let [events [{:type :note :tick 100 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}]
        out (sq/quantize-events events 120 {:strength 0.5 :swing 0.0})]
    (is (= [110] (mapv :tick out)))))

(deftest quantize-swing-delays-odd-grid-lines
  (let [events [{:type :note :tick 115 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}]
        out (sq/quantize-events events 120 {:strength 1.0 :swing 0.5})]
    ;; nearest grid index for 115 is 1 (odd) -> base target 120, swing adds 0.5*120=60 -> 180
    (is (= [180] (mapv :tick out)))))

(deftest quantize-even-grid-line-unaffected-by-swing
  (let [events [{:type :note :tick 5 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}]
        out (sq/quantize-events events 120 {:strength 1.0 :swing 0.5})]
    ;; nearest grid index for 5 is 0 (even) -> swing does not apply
    (is (= [0] (mapv :tick out)))))

;; ---------------------------------------------------------------------------
;; groove

(deftest apply-groove-cycles-and-clamps-velocity
  (let [template [{:offset-ticks 0 :velocity-offset 0}
                  {:offset-ticks 12 :velocity-offset -10}
                  {:offset-ticks -5 :velocity-offset 5}
                  {:offset-ticks 0 :velocity-offset 0}]
        events [{:type :note :tick 0 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}     ;; slot 0
                {:type :note :tick 120 :pitch 61 :velocity 100 :duration-ticks 10 :channel 0}    ;; slot 1
                {:type :note :tick 240 :pitch 62 :velocity 125 :duration-ticks 10 :channel 0}    ;; slot 2 (velocity clamp check)
                {:type :cc :controller 7 :value 100 :tick 120 :channel 0}]                       ;; slot 1, no velocity field
        out (sq/apply-groove events 120 template)]
    (is (= [0 132 235 132] (mapv :tick out)))
    (is (= [100 90 127] (->> out (filter #(= :note (:type %))) (mapv :velocity))))
    (is (nil? (:velocity (nth out 3))))))

(deftest apply-groove-empty-template-is-identity
  (let [events [{:type :note :tick 50 :pitch 60 :velocity 100 :duration-ticks 10 :channel 0}]]
    (is (= events (sq/apply-groove events 120 [])))))

;; ---------------------------------------------------------------------------
;; flatten-track

(deftest flatten-track-offsets-and-sorts-clips
  (let [pattern-a {:name "a" :length-ticks 240 :loop? false
                    :events [{:type :note :tick 120 :pitch 64 :velocity 90 :duration-ticks 60 :channel nil}]}
        pattern-b {:name "b" :length-ticks 120 :loop? false
                    :events [{:type :note :tick 0 :pitch 60 :velocity 100 :duration-ticks 60 :channel nil}]}
        track {:name "piano" :channel 2
               :clips [{:clip pattern-a :start-tick 0}
                       {:clip pattern-b :start-tick 480}]}
        {:keys [channel events]} (sq/flatten-track track)]
    (is (= 2 channel))
    (is (= [120 480] (mapv :tick events)))
    (is (every? #(= 2 (:channel %)) events))))
