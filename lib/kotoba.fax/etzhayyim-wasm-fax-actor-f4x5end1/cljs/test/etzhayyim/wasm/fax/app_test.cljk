(ns etzhayyim.wasm.fax.app-test
  (:require [cljs.test :refer [deftest is testing]]
            [re-frame.core :as rf]
            [etzhayyim.wasm.fax.app :as app]))

(deftest default-db-matches-original-scaffold-fields
  (testing "app-db data holds the exact fields +page.svelte's inline `app`
            object used to render as markup literals, before the migration"
    (is (= "cloudflare surface" (:page/kind app/default-db)))
    (is (= "Fax Actor F4x5end1" (:page/title app/default-db)))
    (is (= "etzhayyim-wasm-fax-actor-f4x5end1" (:page/name app/default-db)))
    (is (= "etzhayyim-project-fax" (:page/project app/default-db)))
    (is (= 0 (:page/route-count app/default-db)))
    (is (= [] (:page/routes app/default-db)))
    (is (= [] (:page/vars app/default-db)))
    (is (true? (:page/xrpc? app/default-db)))))

(deftest initialize-db-event-sets-title-sub
  (testing "dispatching the :initialize-db reg-event-db handler makes the
            :page/title reg-sub resolve to default-db's value"
    (rf/dispatch-sync [:initialize-db])
    (is (= (:page/title app/default-db) @(rf/subscribe [:page/title])))))

(deftest initialize-db-event-sets-xrpc-sub
  (testing "same, for :page/xrpc?"
    (rf/dispatch-sync [:initialize-db])
    (is (= (:page/xrpc? app/default-db) @(rf/subscribe [:page/xrpc?])))))

(deftest initialize-db-is-idempotent
  (testing "dispatching :initialize-db twice leaves subs unchanged"
    (rf/dispatch-sync [:initialize-db])
    (rf/dispatch-sync [:initialize-db])
    (is (= (:page/name app/default-db) @(rf/subscribe [:page/name])))
    (is (= (:page/source-path app/default-db) @(rf/subscribe [:page/source-path])))))

(deftest empty-routes-and-vars-are-treated-as-empty-not-nil
  (testing "the seq checks in routes-panel/vars-panel need real empty
            collections, not nil, or the muted-message branch never renders"
    (is (vector? (:page/routes app/default-db)))
    (is (vector? (:page/vars app/default-db)))))
