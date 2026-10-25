(ns etzhayyim-wasm-tms.app-test
  "Real assertions over the re-frame event/sub logic and the rendered
  hiccup — not just a placeholder `(is true)`."
  (:require [cljs.test :refer [deftest is testing use-fixtures]]
            [re-frame.core :as rf]
            [re-frame.db :as rf-db]
            [etzhayyim-wasm-tms.app :as app]))

;; re-frame keeps its db in a global atom (re-frame.db/app-db). Reset it
;; around each test so events fired in one test can't leak into the next.
(use-fixtures :each
  {:before (fn [] (reset! rf-db/app-db {}))})

(deftest initialize-db-sets-title-and-subtitle
  (testing "::initialize-db seeds the db with the ported scaffold copy"
    (rf/dispatch-sync [::app/initialize-db])
    (is (= "etzhayyim-wasm-tms-tm5x7k9q" @(rf/subscribe [::app/title])))
    (is (= "Vite entry scaffold after SvelteKit cleanup."
           @(rf/subscribe [::app/subtitle])))))

(deftest default-db-matches-what-initialize-produces
  (testing "the event handler and the constant it returns stay in sync"
    (rf/dispatch-sync [::app/initialize-db])
    (is (= (:title app/default-db) @(rf/subscribe [::app/title])))
    (is (= (:subtitle app/default-db) @(rf/subscribe [::app/subtitle])))))

(deftest app-view-renders-hiccup
  (testing "app-view returns a hiccup vector rooted at the DADS container"
    (rf/dispatch-sync [::app/initialize-db])
    (let [hiccup (app/app-view)]
      (is (= :main (first hiccup)))
      (let [container (second hiccup)]
        (is (= :div (first container)))
        (is (= "dds-ext-container" (:class (second container))))))))
