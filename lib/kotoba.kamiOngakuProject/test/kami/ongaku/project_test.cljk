(ns kami.ongaku.project-test
  (:require [clojure.test :refer [deftest is]]
            [kami.ongaku.project :as project]
            [kami.ongaku.sequencer :as sq]
            [kami.ongaku.notation :as notation]))

;; ---------------------------------------------------------------------------
;; fixture: a small but real multi-track session

(def midi-pattern
  (let [ev {:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 240 :channel 0}]
    {:name "verse" :length-ticks 960 :loop? true :events [ev]}))

(def notation-part
  (notation/part
   {:id "P1" :name "Piano"
    :measures [(notation/measure
                {:number 1
                 :time-sig {:beats 4 :beat-type 4}
                 :notes [(notation/note {:pitches [{:step :C :octave 4}] :type :whole})]})]}))

(defn base-tracks []
  [(project/track {:id "t-midi" :type :midi :name "Lead" :output-bus "b-inst"})
   (project/track {:id "t-notation" :type :notation :name "Piano" :output-bus "b-inst"})])

(defn base-buses []
  [(project/bus {:id "b-inst" :name "Instruments" :inputs #{}
                 :plugin-chain [(project/plugin-ref {:id "eq-1"})]})
   (project/bus {:id "b-master" :name "Master" :inputs #{"b-inst"}})])

(defn base-clips []
  [(project/clip-placement {:id "c-midi" :track-id "t-midi" :start-tick 0
                             :length-ticks 960 :content midi-pattern})
   (project/clip-placement {:id "c-notation" :track-id "t-notation" :start-tick 0
                             :length-ticks 1920 :content notation-part})])

(defn base-automation []
  [(project/automation-lane
    {:id "a-vol" :target-id "b-master" :param :gain
     :points [(project/automation-point {:tick 0 :value 0.8})
              (project/automation-point {:tick 480 :value 1.0})]})])

(defn base-project []
  (project/project
   {:tempo-map [(project/tempo-point {:tick 0 :bpm 120 :time-sig [4 4]})]
    :tracks (base-tracks)
    :buses (base-buses)
    :clips (base-clips)
    :automation (base-automation)}))

(deftest constructors-reject-invalid-shapes
  (is (nil? (project/track {:id "" :type :midi :name "x"})))
  (is (nil? (project/track {:id "t" :type :bogus :name "x"})))
  (is (nil? (project/bus {:id "b" :name "x" :inputs [1 2]})))
  (is (nil? (project/clip-placement {:id "c" :track-id "t" :start-tick -1 :length-ticks 1 :content {}})))
  (is (nil? (project/automation-point {:tick 0 :value 1 :interp :bogus})))
  (is (nil? (project/tempo-point {:tick 0 :bpm 0 :time-sig [4 4]})))
  (is (some? (project/track {:id "t" :type :midi :name "x"}))))

(deftest bus-gain-defaults-and-validates
  ;; :bus/gain defaults to 1.0 (unity, backward compatible with every
  ;; existing (project/bus ...) call site that doesn't pass :gain) and is
  ;; validated as a non-negative number -- see README, 'Real bus-graph
  ;; mixing proof', for the render-time semantics this field drives.
  (is (= 1.0 (:bus/gain (project/bus {:id "b" :name "x"}))))
  (is (= 0.5 (:bus/gain (project/bus {:id "b" :name "x" :gain 0.5}))))
  (is (nil? (project/bus {:id "b" :name "x" :gain -1})))
  (is (nil? (project/bus {:id "b" :name "x" :gain "loud"}))))

(deftest valid-project-round-trips-clean
  (let [proj (base-project)]
    (is (some? proj))
    (is (project/valid-project? proj))
    (is (= [] (project/validate-project proj)))))

(deftest dangling-clip-track-reference-is-rejected
  (let [proj (base-project)
        broken (update proj :project/clips
                        (fn [clips] (conj clips (project/clip-placement
                                                  {:id "c-orphan" :track-id "does-not-exist"
                                                   :start-tick 0 :length-ticks 1 :content {}}))))
        errs (project/validate-project broken)]
    (is (some #(re-find #"references unknown track: does-not-exist" %) errs))))

(deftest dangling-bus-output-and-automation-target-are-rejected
  (let [proj (base-project)
        broken-track (update proj :project/tracks
                              (fn [ts] (conj ts (project/track {:id "t-orphan" :type :midi :name "x"
                                                                 :output-bus "no-such-bus"}))))
        broken-lane (update proj :project/automation
                             (fn [as] (conj as (project/automation-lane
                                                {:id "a-orphan" :target-id "no-such-target" :param :pan
                                                 :points [(project/automation-point {:tick 0 :value 0})]}))))]
    (is (some #(re-find #"track/output-bus references unknown id: no-such-bus" %)
              (project/validate-project broken-track)))
    (is (some #(re-find #"references unknown target: no-such-target" %)
              (project/validate-project broken-lane)))))

(deftest cyclic-bus-graph-is-rejected
  (let [proj (base-project)
        cyclic (assoc proj :project/buses
                      [(project/bus {:id "b1" :name "b1" :inputs #{"b2"}})
                       (project/bus {:id "b2" :name "b2" :inputs #{"b1"}})])
        errs (project/validate-project cyclic)]
    (is (some #(re-find #"bus graph has a cycle" %) errs))
    (is (nil? (project/find-cycle proj))) ; the acyclic base fixture has none
    (is (some? (project/find-cycle cyclic)))))

(deftest clip-content-must-match-track-type
  (let [proj (base-project)
        mismatched (assoc-in proj [:project/clips 0 :clip/content] {:not :a-pattern})
        errs (project/validate-project mismatched)]
    (is (some #(re-find #"content shape does not match track type" %) errs))))

(deftest unsorted-tempo-map-and-automation-points-are-rejected
  (let [proj (base-project)
        bad-tempo (assoc proj :project/tempo-map
                         [(project/tempo-point {:tick 0 :bpm 120 :time-sig [4 4]})
                          (project/tempo-point {:tick 100 :bpm 140 :time-sig [4 4]})])
        out-of-order (update bad-tempo :project/tempo-map (comp vec reverse))
        errs (project/validate-project out-of-order)]
    (is (some #(re-find #"tempo-map points are not tick-sorted" %) errs))))

(deftest real-sequencer-and-notation-content-are-usable-as-clip-content
  ;; exercises the actual sibling-repo dependency, not just shape-compatible maps
  (is (= 1 (count (:events midi-pattern))))
  (is (empty? (sq/validate-pattern midi-pattern)) "sequencer's own validator accepts our fixture content")
  (is (some? notation-part))
  (is (= "P1" (:part/id notation-part))))
