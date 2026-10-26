(ns browser.compat.quickjs-fullscreen-promise-smoke-test
  "Real page-script proof that `Element.prototype.requestFullscreen()` and
  `document.exitFullscreen()` return REAL thenables, not bare `undefined`.

  Before this cycle's fix, both functions fell off the end of their bodies
  with no `return` statement at all -- real spec declares both
  `Promise<undefined>`, so `el.requestFullscreen().then(...)` /
  `document.exitFullscreen().then(...)` crashed with a real TypeError
  (\"undefined.then is not a function\"), not just a missing feature. Both
  now build a `__kotobaMakeDeferred` thenable and resolve it SYNCHRONOUSLY
  (see that fn's own docstring in quickjs_wasm.cljc for why -- this
  engine's native QuickJS Promise jobs are never pumped), so `.then()`'s
  callback genuinely runs within the SAME script tag, no second
  `<script>`/real wall-clock wait needed here, mirroring
  `quickjs_notification_request_permission_promise_smoke_test.cljs`."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(deftest quickjs-fullscreen-request-and-exit-return-real-promises-test
  (async done
    (let [url "kotoba://quickjs-runner/fullscreen-promise"
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :profile (profile/new-profile {:id "any"})}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (try
               (let [html (str "<main><div id=\"target\"></div></main><script>"
                               "document.title = 'pending';"
                               "var el = document.getElementById('target');"
                               "var reqResult = el.requestFullscreen();"
                               "document.title = (typeof reqResult.then === 'function') ? 'req-has-then' : 'req-no-then';"
                               "reqResult.then(function(v) {"
                               "  document.title = document.title + ':req-resolved:' + (v === undefined ? 'undefined' : v);"
                               "  var exitResult = document.exitFullscreen();"
                               "  document.title = document.title + ':' + ((typeof exitResult.then === 'function') ? 'exit-has-then' : 'exit-no-then');"
                               "  exitResult.then(function(v2) {"
                               "    document.title = document.title + ':exit-resolved:' + (v2 === undefined ? 'undefined' : v2);"
                               "  });"
                               "});"
                               "</script>")
                     after (session/load-html! ready-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "fullscreen promise smoke: document.title ->" (pr-str title))
                 (is (= "req-has-then:req-resolved:undefined:exit-has-then:exit-resolved:undefined" title)
                     (str "expected both requestFullscreen() and exitFullscreen() to return real "
                          "thenables (typeof .then === 'function') whose .then() callbacks run "
                          "SYNCHRONOUSLY within the same script tag and resolve with undefined -- "
                          "got document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
