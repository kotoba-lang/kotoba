(ns kami.ongaku.sequencer.smf-test
  (:require [kami.ongaku.sequencer.smf :as smf]
            #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])))

;; ---------------------------------------------------------------------------
;; VLQ

(deftest vlq-round-trip-small-and-large
  (doseq [n [0 1 63 127 128 200 16383 16384 2097151 2097152 268435455]]
    (let [enc (smf/vlq-encode n)
          [dec next-off] (smf/vlq-decode enc 0)]
      (is (= n dec) (str "n=" n))
      (is (= (count enc) next-off)))))

(deftest vlq-known-encodings
  ;; values from the SMF spec's own VLQ worked examples
  (is (= [0x00] (smf/vlq-encode 0x00000000)))
  (is (= [0x40] (smf/vlq-encode 0x40)))
  (is (= [0x7F] (smf/vlq-encode 0x7F)))
  (is (= [0x81 0x00] (smf/vlq-encode 0x80)))
  (is (= [0xC0 0x00] (smf/vlq-encode 0x2000)))
  (is (= [0xFF 0x7F] (smf/vlq-encode 0x3FFF)))
  (is (= [0x81 0x80 0x00] (smf/vlq-encode 0x4000))))

;; ---------------------------------------------------------------------------
;; full export/import round-trip

(def ^:private track-a
  {:channel 0
   :events [{:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 240 :channel 0}
            {:type :note :pitch 64 :velocity 90 :tick 240 :duration-ticks 240 :channel 0}
            {:type :cc :controller 7 :value 100 :tick 0 :channel 0}
            {:type :pitch-bend :value 2000 :tick 120 :channel 0}
            {:type :aftertouch :pitch 60 :value 50 :tick 60 :channel 0}
            {:type :channel-aftertouch :value 30 :tick 300 :channel 0}]})

(def ^:private track-b
  {:channel 9
   :events [{:type :note :pitch 36 :velocity 127 :tick 0 :duration-ticks 60 :channel 9}
            {:type :note :pitch 38 :velocity 100 :tick 120 :duration-ticks 60 :channel 9}]})

(deftest export-import-round-trip
  (let [session {:ppq 480 :bpm 128 :time-signature [3 4] :tracks [track-a track-b]}
        bytes (smf/export-smf session)
        parsed (smf/import-smf bytes)]
    (is (= 480 (:ppq parsed)))
    (is (= 128 (:bpm parsed)))
    (is (= [3 4] (:time-signature parsed)))
    (is (= 2 (count (:tracks parsed))))
    (is (= (set (:events track-a)) (set (:events (first (:tracks parsed))))))
    (is (= (set (:events track-b)) (set (:events (second (:tracks parsed))))))))

(deftest export-import-round-trip-overlapping-notes-same-pitch
  ;; two notes on the same pitch/channel, second starts before the first ends
  ;; note-off ordering (sorted before other events at equal tick) plus FIFO
  ;; pairing must keep them from being scrambled.
  (let [track {:channel 0
               :events [{:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 240 :channel 0}
                        {:type :note :pitch 60 :velocity 80 :tick 240 :duration-ticks 240 :channel 0}]}
        bytes (smf/export-smf {:ppq 480 :bpm 120 :time-signature [4 4] :tracks [track]})
        parsed (smf/import-smf bytes)]
    (is (= (sort-by :tick (:events track))
           (sort-by :tick (:events (first (:tracks parsed))))))))

(deftest import-skips-meta-only-conductor-track
  (let [bytes (smf/export-smf {:ppq 480 :bpm 100 :time-signature [4 4] :tracks [track-a]})
        parsed (smf/import-smf bytes)]
    ;; conductor track (tempo/time-sig only) must not appear in :tracks
    (is (= 1 (count (:tracks parsed))))))

(deftest export-header-fields
  (let [bytes (smf/export-smf {:ppq 240 :bpm 120 :time-signature [4 4] :tracks [track-a]})]
    (is (= [0x4D 0x54 0x68 0x64] (subvec bytes 0 4)))            ;; "MThd"
    (is (= [0x00 0x00 0x00 0x06] (subvec bytes 4 8)))            ;; header length 6
    (is (= [0x00 0x01] (subvec bytes 8 10)))                     ;; format 1
    (is (= [0x00 0x02] (subvec bytes 10 12)))                    ;; 2 tracks (conductor + 1)
    (is (= [0x00 0xF0] (subvec bytes 12 14)))))                  ;; ppq 240
