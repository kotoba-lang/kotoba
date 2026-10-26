(ns browser.compat.quickjs-notification-request-permission-promise-smoke-test
  "Real page-script proof that `Notification.requestPermission()` returns a
  REAL thenable, not a bare string.

  Companion to `quickjs_notification_smoke_test.cljs`, which already proves
  the legacy callback argument round-trips the real permission decision.
  Before this cycle's fix, `requestPermission()` returned the plain
  permission string directly -- every OTHER capability in this shim that
  resolves an already-known-synchronous host decision (clipboard.readText/
  writeText, fetch(), getUserMedia()) wraps it in `__kotobaMakeDeferred`,
  but this one skipped that convention, so the extremely common
  `Notification.requestPermission().then(perm => ...)` pattern crashed with
  a real TypeError (`permission.then is not a function`), not just a
  missing feature.

  `__kotobaMakeDeferred` settles SYNCHRONOUSLY the moment `resolve()` is
  called (see its own docstring in quickjs_wasm.cljc for why -- this
  engine's native QuickJS Promise jobs are never pumped), so `.then()`'s
  callback genuinely runs within the SAME script tag, no second
  `<script>`/real wall-clock wait needed here (unlike the WebSocket
  onopen/onerror/onclose fixes, which needed real async I/O to complete)."
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

(deftest quickjs-notification-request-permission-then-resolves-with-real-decision-test
  (async done
    (let [url "kotoba://quickjs-runner/notification-request-permission-promise"
          allowed-profile (-> (profile/new-profile {:id "notification-allowed"})
                              (profile/grant-permission "kotoba://quickjs-runner" :notification/show))
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :profile allowed-profile}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (try
               (let [html (str "<main><script>"
                               "document.title = 'pending';"
                               "var p = Notification.requestPermission();"
                               "document.title = (typeof p.then === 'function') ? 'has-then' : 'no-then';"
                               "p.then(function(perm) { document.title = document.title + ':' + perm; });"
                               "</script></main>")
                     after (session/load-html! ready-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "notification requestPermission().then() smoke: document.title ->"
                          (pr-str title))
                 (is (= "has-then:granted" title)
                     (str "expected requestPermission() to return a real thenable "
                          "(typeof .then === 'function') whose .then() callback runs "
                          "SYNCHRONOUSLY within the same script tag and receives the real "
                          "'granted' decision -- got document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))

(deftest quickjs-notification-request-permission-catch-is-never-invoked-test
  ;; Per spec, requestPermission() never rejects -- it always resolves,
  ;; even when the user/profile denies permission ('denied' is a valid
  ;; RESOLVED value, not an error). Proves .catch() exists (mirrors
  ;; clipboard's own promise shape) and is genuinely never invoked, using
  ;; a profile that never granted :notification/show.
  (async done
    (let [url "kotoba://quickjs-runner/notification-request-permission-promise-catch"
          denied-profile (profile/new-profile {:id "notification-denied"})
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :profile denied-profile}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (try
               (let [html (str "<main><script>"
                               "document.title = 'not-caught';"
                               "Notification.requestPermission()"
                               ".then(function(perm) { document.title = 'resolved:' + perm; })"
                               ".catch(function() { document.title = 'caught'; });"
                               "</script></main>")
                     after (session/load-html! ready-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "notification requestPermission().catch() smoke: document.title ->"
                          (pr-str title))
                 (is (= "resolved:denied" title)
                     (str "requestPermission() must resolve (never reject) even when permission "
                          "is denied -- .catch() must never fire -- got document.title = "
                          (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
