(ns kami.webvr.engine-test
  "New coverage for the reactive engine layer (createIncidentVrEngine.svelte.ts's
   CLJS port) -- no cine-bridge involved (nodes below have no :cine hint), so
   onScene is called exactly once per publish, matching the base-scene-only path."
  (:require [cljs.test :refer [deftest is testing]]
            [kami.webvr.engine :as e]))

(def tiny
  {:id "tiny" :title "Tiny" :synopsis "test fixture" :start "a"
   :nodes {"a" {:id "a" :stage :detect :severity :high :location :scada-room
                :briefing "..." :choices [{:id "good" :label "Good" :next "win"
                                           :delta {:mttd-sec 10} :grade :best :rationale "..."}]}
          "win" {:id "win" :stage :recover :severity :info :location :scada-room
                 :briefing "..." :choices [] :terminal :success}}})

(deftest publishes-the-base-scene-synchronously-on-construction
  (let [scenes (atom [])
        engine (e/create-incident-vr-engine {:scenario tiny :on-scene #(swap! scenes conj %)})]
    (is (= 1 (count @scenes)))
    (is (= "a" (:node-id (first @scenes))))
    (is (= "a" (:current ((:state engine)))))))

(deftest select-advances-state-and-republishes
  (let [scenes (atom [])
        oplog (atom [])
        engine (e/create-incident-vr-engine {:scenario tiny
                                              :on-scene #(swap! scenes conj %)
                                              :on-oplog #(swap! oplog conj %)})]
    ((:select! engine) "good")
    (is (= "win" (:current ((:state engine)))))
    (is (true? (:done ((:state engine)))))
    (is (= 2 (count @scenes)))
    (is (= "win" (:node-id (last @scenes))))
    (is (= [:enter :choose :terminate] (mapv :op @oplog)))))

(deftest reset-restores-initial-state-and-republishes
  (let [scenes (atom [])
        engine (e/create-incident-vr-engine {:scenario tiny :on-scene #(swap! scenes conj %)})]
    ((:select! engine) "good")
    ((:reset! engine))
    (is (= "a" (:current ((:state engine)))))
    (is (false? (:done ((:state engine)))))
    (is (= "a" (:node-id (last @scenes))))))

(deftest select-after-done-is-a-no-op
  (let [scenes (atom [])
        engine (e/create-incident-vr-engine {:scenario tiny :on-scene #(swap! scenes conj %)})]
    ((:select! engine) "good")
    (let [n (count @scenes)]
      ((:select! engine) "good")
      (is (= n (count @scenes))))))
