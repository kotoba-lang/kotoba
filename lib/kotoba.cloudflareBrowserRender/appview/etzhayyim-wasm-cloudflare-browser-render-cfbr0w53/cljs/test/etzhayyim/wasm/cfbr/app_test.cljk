(ns etzhayyim.wasm.cfbr.app-test
  (:require [cljs.test :refer [deftest is testing]]
            [re-frame.core :as rf]
            [etzhayyim.wasm.cfbr.app :as app]))

(deftest default-db-matches-original-scaffold-data
  (testing "app-db data holds the exact facts the original +page.svelte
            `<script>` block held as a literal `app` map, before the
            migration"
    (is (= "Cloudflare Browser Render Cfbr0w53" (:page/title app/default-db)))
    (is (= "etzhayyim-project-cloudflare-browser-render" (:page/project app/default-db)))
    (is (= "etzhayyim-wasm-cloudflare-browser-render-cfbr0w53" (:page/name app/default-db)))
    (is (= "appview" (:page/kind app/default-db)))
    (is (= 0 (:page/route-count app/default-db)))
    (is (= [] (:page/routes app/default-db)))
    (is (= [] (:page/vars app/default-db)))
    (is (true? (:page/xrpc? app/default-db)))))

(deftest initialize-db-event-sets-all-subs
  (testing "dispatching :initialize-db makes every page/* sub resolve to
            default-db's value"
    (rf/dispatch-sync [:initialize-db])
    (is (= (:page/title app/default-db) @(rf/subscribe [:page/title])))
    (is (= (:page/project app/default-db) @(rf/subscribe [:page/project])))
    (is (= (:page/name app/default-db) @(rf/subscribe [:page/name])))
    (is (= (:page/kind app/default-db) @(rf/subscribe [:page/kind])))
    (is (= (:page/route-count app/default-db) @(rf/subscribe [:page/route-count])))
    (is (= (:page/routes app/default-db) @(rf/subscribe [:page/routes])))
    (is (= (:page/vars app/default-db) @(rf/subscribe [:page/vars])))
    (is (= (:page/xrpc? app/default-db) @(rf/subscribe [:page/xrpc?])))
    (is (= (:page/relative-path app/default-db) @(rf/subscribe [:page/relative-path])))))

(deftest initialize-db-is-idempotent
  (testing "dispatching :initialize-db twice leaves subs unchanged"
    (rf/dispatch-sync [:initialize-db])
    (rf/dispatch-sync [:initialize-db])
    (is (= (:page/title app/default-db) @(rf/subscribe [:page/title])))
    (is (= (:page/xrpc? app/default-db) @(rf/subscribe [:page/xrpc?])))))

(deftest empty-routes-and-vars-are-empty-not-invented
  (testing "the source `+page.svelte` declared no routes/vars for this app
            surface (empty arrays in its `app` literal) — the migration must
            not invent placeholder entries"
    (is (empty? (:page/routes app/default-db)))
    (is (empty? (:page/vars app/default-db)))))
