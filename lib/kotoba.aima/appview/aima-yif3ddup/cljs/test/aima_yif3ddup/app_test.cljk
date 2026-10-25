(ns aima-yif3ddup.app-test
  (:require [cljs.test :refer [deftest is testing use-fixtures]]
            [re-frame.core :as rf]
            [re-frame.db :as rf-db]
            [aima-yif3ddup.app :as app]))

;; re-frame keeps its db in a global atom (re-frame.db/app-db). Reset it
;; around each test so events fired in one test can't leak into the next.
(use-fixtures :each
  {:before (fn [] (reset! rf-db/app-db {}))})

(deftest initialize-db-sets-defaults
  (testing "::initialize-db seeds the expected scaffold defaults"
    (rf/dispatch-sync [::app/initialize-db])
    (is (= "aima-yif3ddup" @(rf/subscribe [::app/app-name])))
    (is (= 0 @(rf/subscribe [::app/clicks])))
    (is (string? @(rf/subscribe [::app/tagline])))))

(deftest increment-clicks-updates-sub
  (testing "::increment-clicks increments :clicks and the sub reflects it"
    (rf/dispatch-sync [::app/initialize-db])
    (rf/dispatch-sync [::app/increment-clicks])
    (rf/dispatch-sync [::app/increment-clicks])
    (is (= 2 @(rf/subscribe [::app/clicks])))))

(deftest increment-clicks-does-not-touch-other-keys
  (testing "incrementing clicks leaves app-name/tagline untouched"
    (rf/dispatch-sync [::app/initialize-db])
    (rf/dispatch-sync [::app/increment-clicks])
    (is (= "aima-yif3ddup" @(rf/subscribe [::app/app-name])))
    (is (= (:tagline app/default-db) @(rf/subscribe [::app/tagline])))))

(deftest app-view-renders-hiccup
  (testing "app-view returns a hiccup vector rooted at the DADS container"
    (rf/dispatch-sync [::app/initialize-db])
    (let [hiccup (app/app-view)]
      (is (vector? hiccup))
      (is (= :div (first hiccup)))
      (is (= "dds-ext-container" (:class (second hiccup)))))))
