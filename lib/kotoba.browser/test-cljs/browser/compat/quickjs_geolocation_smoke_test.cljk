(ns browser.compat.quickjs-geolocation-smoke-test
  "Real page-script round-trip proof for `navigator.geolocation.getCurrentPosition`.

  Companion to `quickjs-runtime-state-threading-smoke-test` (which proves the
  same kind of round-trip for `localStorage`/`clipboard`). Before this
  change, `getCurrentPosition` pushed a `geolocation/read` capability request
  onto the queue and returned -- `success`/`error` were NEVER called, so no
  script could ever observe a position or a denial. This closes that gap the
  same way storage/clipboard reads were closed: `quickjs-execution/evaluate!`
  computes a REAL `geolocation-snapshot` (permission decision + position,
  from the persisted `:geolocation` atom -- see
  `browser.compat.quickjs-runner`'s `persistent-execution-keys` -- and the
  SAME `permission-decision-for` gate `apply-capability`'s `:geolocation/read`
  case uses) host-side BEFORE the script runs, threads it into `quickjs-wasm`
  as `:geolocation/snapshot`, which installs it as
  `globalThis.__kotobaGeolocationSnapshot` before eval, and the webapi shim's
  `getCurrentPosition` reads it and calls `success`/`error` SYNCHRONOUSLY
  (this engine evaluates a whole script synchronously in one pass, so there
  is no realistic way to defer the callback the way a real, async/
  permission-prompted browser would).

  Both tests below seed a real position into the session's page-lifetime
  `quickjs-execution` runtime state (`:browser.session/quickjs-runtime-state`,
  the same host-side mechanism `browser.compat.quickjs-runner/run-script!`
  persists/rehydrates across a page's own scripts) BEFORE the real
  `<script>` tag runs, mirroring how a real host would inject a real GPS
  fix. The engine, the JS execution, the capability request queuing, and the
  permission-decision gate are all real -- nothing here is mocked or
  inlined. The proof is genuinely JS-visible: both tests assert the REAL
  committed `document.title` a real `<script>` tag set from what
  `getCurrentPosition`'s callback actually received, not a host-side
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

(defn- seed-geolocation
  "Seed a real `:geolocation` position atom into `session`'s page-lifetime
  `quickjs-execution` runtime state, tagged with the generation the page
  `load-html!` is about to commit (`page-generation` is bumped by
  `commit-page!` BEFORE `run-page-scripts!` runs -- see
  `browser.compat.quickjs-runner`'s `run-script!`/`runtime-state-for-generation`),
  so the FIRST real `<script>` tag on the page `load-html!` is about to run
  sees this atom as its `:geolocation` state instead of the zeroed default
  `quickjs-execution/new-state` would otherwise install. This is the
  host-side injection point the real host uses for a real GPS fix; JS itself
  has no way to set its own geolocation, only read it."
  [session position]
  (assoc session :browser.session/quickjs-runtime-state
         {:quickjs-runtime/generation (inc (:browser.session/page-generation session 0))
          :quickjs-runtime/state {:geolocation (atom position)}}))

(deftest quickjs-geolocation-getcurrentposition-success-round-trips-real-position-test
  (async done
    (let [url "kotoba://quickjs-runner/geolocation-round-trip/success"
          allowed-profile (-> (profile/new-profile {:id "geo-allowed"})
                              (profile/grant-permission "kotoba://quickjs-runner" :geolocation/read))
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
               (let [real-position {:latitude 35.6812 :longitude 139.7671 :accuracy 12.5}
                     seeded-session (seed-geolocation ready-session real-position)
                     html (str "<main><script>"
                               "navigator.geolocation.getCurrentPosition(function(pos) {"
                               "document.title = String(pos.coords.latitude) + ',' + String(pos.coords.longitude);"
                               "}, function(err) {"
                               "document.title = 'unexpected-error:' + err.code;"
                               "});"
                               "</script></main>")
                     after (session/load-html! seeded-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "geolocation round-trip (success): real injected position ->"
                          (pr-str real-position))
                 (println "geolocation round-trip (success): real committed document.title ->"
                          (pr-str title))
                 (is (= "35.6812,139.7671" title)
                     (str "expected the real <script> tag's getCurrentPosition success callback "
                          "to synchronously receive the REAL host-injected position "
                          "{:latitude 35.6812 :longitude 139.7671} and commit it into "
                          "document.title, genuinely round-tripped back into the running QuickJS "
                          "VM (not just recorded host-side) -- got document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))

(deftest quickjs-geolocation-getcurrentposition-permission-denied-round-trips-error-test
  (async done
    (let [url "kotoba://quickjs-runner/geolocation-round-trip/denied"
          ;; A real profile that exists but was never granted :geolocation/read
          ;; -- mirrors quickjs-execution-test's
          ;; quickjs-geolocation-read-denies-without-profile-grant, just
          ;; proven here via a real JS-visible callback instead of a
          ;; host-side :capability/results entry.
          denied-profile (profile/new-profile {:id "geo-denied"})
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
               ;; A real position IS available host-side -- proving the
               ;; error path is genuinely gated by the permission decision,
               ;; not merely by "no position was ever injected".
               (let [real-position {:latitude 35.6812 :longitude 139.7671 :accuracy 12.5}
                     seeded-session (seed-geolocation ready-session real-position)
                     html (str "<main><script>"
                               "navigator.geolocation.getCurrentPosition(function(pos) {"
                               "document.title = 'unexpected-success:' + pos.coords.latitude;"
                               "}, function(err) {"
                               "document.title = String(err.code) + ':' + err.message;"
                               "});"
                               "</script></main>")
                     after (session/load-html! seeded-session {:url url :html html})
                     title (get-in after [:browser.session/page :browser/title])]
                 (println "geolocation round-trip (denied): real committed document.title ->"
                          (pr-str title))
                 (is (= "1:User denied Geolocation (permission/not-granted)" title)
                     (str "expected the real <script> tag's getCurrentPosition ERROR callback "
                          "to synchronously fire (not success) with a real "
                          "GeolocationPositionError-shaped {code, message} because the active "
                          "profile never granted :geolocation/read -- even though a real position "
                          "WAS available host-side -- got document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
