(ns browser.compat.quickjs-notification-smoke-test
  "Real page-script round-trip proof for `Notification.permission`/
  `Notification.requestPermission`.

  Companion to `quickjs-geolocation-smoke-test` (same shape: a real,
  end-to-end proof that a permission-gated webapi shim reflects the REAL
  host-side permission decision synchronously, not a hardcoded placeholder).
  Before this change, `Notification.permission` and
  `Notification.requestPermission`'s callback/return value could NEVER be
  anything but the literal string 'default', regardless of what the active
  profile actually granted or denied -- `quickjs-execution/notification-
  permission-result` already computed the REAL decision, but only for the
  POST-script `:capability/results` audit trail (via `apply-capability`'s
  `:notification/request-permission` case), never for the running script's
  own JS-visible read. This closes that gap the same way geolocation's was
  closed: `quickjs-execution/evaluate!`/`load-module!` compute a REAL
  `notification-permission-snapshot` (the SAME `permission-decision-for` gate
  `apply-capability`'s `:notification/show` case uses) host-side BEFORE the
  script runs, thread it into `quickjs-wasm` as `:notification/snapshot`,
  which installs it as `globalThis.__kotobaNotificationSnapshot` before eval,
  and the webapi shim's `Notification.permission`/`requestPermission` read it
  synchronously instead of the hardcoded literal.

  Both tests below use a real profile (granted or not granted
  `:notification/show`) -- the engine, the JS execution, the capability
  request queuing, and the permission-decision gate are all real -- nothing
  here is mocked or inlined. The proof is genuinely JS-visible: both tests
  assert the REAL committed `document.title` a real `<script>` tag set from
  what `Notification.requestPermission`'s callback actually received AND from
  reading `Notification.permission` itself as a property, not a host-side
  `:capability/results` log entry."
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

(deftest quickjs-notification-request-permission-granted-round-trips-real-decision-test
  (async done
    (let [url "kotoba://quickjs-runner/notification-round-trip/granted"
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
                               "var live = Notification.permission;"
                               "Notification.requestPermission(function(callback_permission) {"
                               "document.title = live + ',' + callback_permission + ',' + Notification.permission;"
                               "});"
                               "</script></main>")
                     after (session/load-html! ready-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "notification round-trip (granted): real committed document.title ->"
                          (pr-str title))
                 (is (= "granted,granted,granted" title)
                     (str "expected the real <script> tag's Notification.permission property read "
                          "(BEFORE requestPermission was even called), requestPermission's real "
                          "callback argument, AND a second Notification.permission property read "
                          "(AFTER requestPermission) to all synchronously report the REAL 'granted' "
                          "decision the active profile's :notification/show grant actually gives -- "
                          "not the engine's hardcoded 'default' -- got document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))

(deftest quickjs-notification-request-permission-denied-round-trips-real-decision-test
  (async done
    (let [url "kotoba://quickjs-runner/notification-round-trip/denied"
          ;; A real profile that exists but was never granted :notification/show
          ;; -- mirrors quickjs-execution-test's
          ;; quickjs-notification-show-denies-without-profile-grant, just
          ;; proven here via a real JS-visible callback/property read instead
          ;; of a host-side :capability/results entry.
          denied-profile (profile/new-profile {:id "notification-denied"})
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :profile denied-profile}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (try
               (let [html (str "<main><script>"
                               "var live = Notification.permission;"
                               "Notification.requestPermission(function(callback_permission) {"
                               "document.title = live + ',' + callback_permission + ',' + Notification.permission;"
                               "});"
                               "</script></main>")
                     after (session/load-html! ready-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "notification round-trip (denied): real committed document.title ->"
                          (pr-str title))
                 (is (= "denied,denied,denied" title)
                     (str "expected the real <script> tag's Notification.permission property read, "
                          "requestPermission's real callback argument, AND a second "
                          "Notification.permission property read to all synchronously report the "
                          "REAL 'denied' decision because the active profile never granted "
                          ":notification/show -- not the engine's hardcoded 'default' -- got "
                          "document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
