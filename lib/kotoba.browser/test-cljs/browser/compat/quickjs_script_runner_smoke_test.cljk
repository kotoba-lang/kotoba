(ns browser.compat.quickjs-script-runner-smoke-test
  "Real page-script-lifecycle smoke test: loads a real HTML page containing a
  real inline `<script>` tag, runs it through `browser.session/run-page-scripts!`
  (via `load-html!`) using the real QuickJS-backed `:script-runner`
  (`browser.compat.quickjs-runner/run-script!`), and asserts that the session's
  committed page/document state actually reflects what the script did.

  This is the companion to `quickjs-wasm-smoke-test` (which proves the bare
  engine evaluates real JS) and to `browser.quickjs-execution-test` (which
  proves the capability-request/response loop against a hand-rolled mock
  engine fn). Here the engine is the genuine
  `browser.compat.quickjs-wasm/engine!` WASM engine, wired through
  `browser.session` exactly the way a real caller would use it -- nothing
  about the script execution or the DOM mutation is mocked. Run via
  `npm run test:cljs` (shadow-cljs `:node-test` target, executed under Node)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(deftest quickjs-script-sets-document-title-for-real-test
  (async done
    (let [h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (let [before-title (get-in ready-session
                                        [:browser.session/page :browser/title])
                   html (str "<head><title>Before</title></head>"
                             "<main><script>"
                             "document.title = 'Set by real QuickJS';"
                             "</script></main>")
                   after (session/load-html!
                          ready-session
                          {:url "kotoba://quickjs-runner/smoke"
                           :html html})
                   after-title (get-in after [:browser.session/page :browser/title])
                   ready-state (get-in after
                                       [:browser.session/page :browser/document :ready-state])
                   quickjs-events (filter #(= :script/quickjs-run (:event %))
                                          (:browser.session/history after))
                   skipped-events (filter #(= :script/skipped (:event %))
                                          (:browser.session/history after))]
               (println "quickjs page-script lifecycle: document.title before ->"
                        (pr-str before-title))
               (println "quickjs page-script lifecycle: document.title after real"
                        "<script>document.title = 'Set by real QuickJS';</script> ->"
                        (pr-str after-title))
               (println "quickjs page-script lifecycle: real script/quickjs-run"
                        "history events ->" (pr-str quickjs-events))
               (try
                 (is (nil? before-title)
                     "sanity: no page/title exists yet before the first load-html!")
                 (is (= "Set by real QuickJS" after-title)
                     (str "expected the REAL QuickJS-executed script to set "
                          "document.title, got: " (pr-str after-title)))
                 (is (= "complete" ready-state)
                     "page lifecycle should still reach 'complete' after real script execution")
                 (is (= 3 (count quickjs-events))
                     (str "expected 3 real quickjs runs (the inline script + "
                          "DOMContentLoaded + load dispatch), got: "
                          (pr-str quickjs-events)))
                 (is (empty? skipped-events)
                     (str "no script should have been skipped for a not-ready engine: "
                          (pr-str skipped-events)))
                 (finally
                   (dispose-engine! after)
                   (done))))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
