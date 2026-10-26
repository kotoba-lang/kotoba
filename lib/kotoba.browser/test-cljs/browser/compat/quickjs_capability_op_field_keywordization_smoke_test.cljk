(ns browser.compat.quickjs-capability-op-field-keywordization-smoke-test
  "Real page-script round-trip proof that `:cookie/op`, `:location/op`,
  `:geolocation/op`, `:notification/op`, `:fullscreen/op`, `:media/op`, and
  `:crypto/op` -- every remaining `/op`- or `/format`-suffixed capability
  request field the real webapi shim pushes as a raw JS STRING (e.g.
  `'cookie/op': 'set'`) -- genuinely normalize to KEYWORDS before
  `browser.compat.quickjs-execution/capability-request-error`'s shape checks
  see them, the same fix `:clipboard/format` already got (see that fix's
  `quickjs_clipboard_media_promise_smoke_test.cljs`).

  Before this change, `browser.compat.quickjs-wasm/normalize-request`
  keywordized only `#{:capability :dom/query :dom/op :clipboard/format}` --
  every other key's value (including all 7 above) passed through its
  `:else v` fallback UNCHANGED, i.e. stayed a raw string. Since
  `capability-request-error` compares each of these fields against a
  KEYWORD literal with `=` (e.g. `(= :set (:cookie/op request))`), a raw
  string value NEVER equals the keyword, so EVERY real (JS-shim-originated)
  request naming one of these ops failed shape validation and was silently
  rejected as `:quickjs/invalid-capability-request` before ever reaching
  `apply-capability`'s real per-capability handling -- even though each of
  these ops' immediate JS-visible return value (a resolved/rejected Promise,
  a callback invocation, a hardcoded stub) is driven by a separate,
  precomputed-snapshot or synchronous-stub code path in the webapi shim
  that does NOT depend on the request round-trip succeeding (see
  `quickjs-wasm/webapi-shim-source`), so none of these bugs were ever
  visible via `document.title` alone -- only via the real, host-side
  `:capability/results` audit trail this test asserts on directly, exactly
  as `quickjs_runtime_state_threading_smoke_test.cljs` already does for
  `:storage/get`.

  `normalize-request` now keywordizes by a general rule instead of an
  ever-growing explicit set: `:capability`/`:dom/query` (enum-like but not
  named like the rest) plus ANY key whose name is exactly `op` or `format`
  -- verified (by inspecting every `'<ns>/op'`/`'<ns>/format'` field the
  webapi shim pushes) to always be a fixed enum-like discriminator token in
  this codebase, never free-form user/network data (a URL, a cookie VALUE,
  clipboard TEXT, etc., which must stay strings and do NOT use this naming
  convention).

  The engine, the JS execution, the capability request queuing, and the
  permission-decision gates below are all real -- nothing here is mocked or
  inlined."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
            [browser.session :as session]
            [browser.storage :as storage]
            [kotoba.wasm.host :as host]))

(def ^:private origin "kotoba://quickjs-op-field")

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- build-session
  "A session with a REAL `:store` + `:profile` wired up (so
  `browser.session/net-context` -- and therefore `:cookie/get`/`:cookie/set`,
  which require a real `:net/context` -- actually work), mirroring
  `quickjs_clipboard_media_promise_smoke_test.cljs`'s `build-session` plus
  an explicit empty cookie store."
  [profile]
  (let [h (host/recording-host)]
    (session/new-session
     (quickjs-runner/quickjs-session-opts
      {:host h :profile profile :store (storage/empty-store)}))))

(defn- quickjs-run-events
  "`:script/quickjs-run` history events for `session`'s CURRENT page only --
  mirrors `quickjs_runtime_state_threading_smoke_test.cljs`'s identically
  named helper."
  [session]
  (let [current-url (get-in session [:browser.session/page :browser/url])]
    (filter #(and (= :script/quickjs-run (:event %))
                  (= current-url (:script/url %)))
            (:browser.session/history session))))

(defn- results-for
  "Real `:capability/results` entries for `capability` across every real
  quickjs-run history event for `session`'s current page."
  [session capability]
  (->> (quickjs-run-events session)
       (mapcat :capability/results)
       (filter #(= capability (:capability %)))))

(defn- run-op-field-smoke!
  "Shared harness: build a session with `profile`, run `html` as a single
  real page load at `path`, and hand the resulting session to
  `assertions-fn` -- mirrors every other `test-cljs` smoke test's `async
  done` + `.then`/`.catch` skeleton."
  [{:keys [profile path html assertions-fn done]}]
  (let [base-session (build-session profile)]
    (-> (session/ensure-script-engine! base-session)
        (.then
         (fn [ready-session]
           (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                 :script-engine/status]))
               "engine should be ready before running page scripts")
           (try
             (let [after (session/load-html! ready-session {:url (str origin path) :html html})]
               (assertions-fn after))
             (finally
               (dispose-engine! ready-session)
               (done)))))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (dispose-engine! base-session)
                  (done))))))

;; -----------------------------------------------------------------------
;; :cookie/op ("get"/"set") -- HIGHEST-VALUE case: `:cookie/set` mutates the
;; REAL, persisted cookie store `apply-capability`'s `:net/fetch` case reads
;; from for the Cookie header on subsequent same-origin fetches (see
;; `browser.net/script-set-cookie`/`script-cookie-header`), not just an
;; isolated audit-log entry. Proven here via a REAL cross-script-tag
;; persistence check (script 1 sets, script 2 reads back), mirroring
;; `quickjs_runtime_state_threading_smoke_test.cljs`'s storage-threading
;; proof.
;; -----------------------------------------------------------------------

(deftest quickjs-cookie-set-genuinely-persists-into-real-store-test
  (async done
    (run-op-field-smoke!
     {:profile (profile/new-profile {:id "cookie-op"})
      :path "/cookie/set-then-get"
      :html (str "<main>"
                 "<script>document.cookie = 'theme=dark; Path=/';</script>"
                 "<script>document.cookie;</script>"
                 "</main>")
      :assertions-fn
      (fn [after]
        (let [set-results (results-for after :cookie/set)
              get-results (results-for after :cookie/get)]
          (println "cookie/set round-trip: real :capability/results ->" (pr-str set-results))
          (println "cookie/get round-trip (2nd script): real :capability/results ->"
                   (pr-str get-results))
          (is (= [{:capability :cookie/set :request/id nil :ok? true
                   :result {:cookie/value "theme=dark; Path=/"
                            :cookie/header "theme=dark"}}]
                 set-results)
              (str "expected the real <script> tag's `document.cookie = '...'` to genuinely reach "
                   "apply-capability's :cookie/set case (not be rejected as "
                   ":quickjs/invalid-capability-request because 'cookie/op': 'set' failed to "
                   "keywordize) and really mutate the persisted cookie store -- got "
                   (pr-str set-results)))
          (is (= [{:capability :cookie/get :request/id nil :ok? true
                   :result {:cookie/header "theme=dark"}}]
                 get-results)
              (str "expected the SECOND real <script> tag's `document.cookie` read to see the "
                   "cookie the FIRST real <script> tag wrote -- only possible if :cookie/set "
                   "genuinely reached apply-capability and mutated the real store -- got "
                   (pr-str get-results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :fullscreen/op ("exit") -- mutates the REAL `:fullscreen/element` host
;; state `apply-capability`'s `:fullscreen/request` case sets, not just an
;; audit-log entry. `document.exitFullscreen()` never permission-gates (see
;; `apply-capability`'s `:fullscreen/exit` case), so this is provable with
;; no profile grants at all.
;; -----------------------------------------------------------------------

(deftest quickjs-fullscreen-exit-genuinely-reaches-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (profile/new-profile {:id "fullscreen-op"})
      :path "/fullscreen/exit"
      :html "<main><script>document.exitFullscreen();</script></main>"
      :assertions-fn
      (fn [after]
        (let [exit-results (results-for after :fullscreen/exit)]
          (println "fullscreen/exit round-trip: real :capability/results ->" (pr-str exit-results))
          (is (= [{:capability :fullscreen/exit :request/id nil :ok? true
                   :result {:exited? true :previous-node/id nil}}]
                 exit-results)
              (str "expected the real <script> tag's document.exitFullscreen() to genuinely reach "
                   "apply-capability's :fullscreen/exit case (not be rejected as "
                   ":quickjs/invalid-capability-request because 'fullscreen/op': 'exit' failed to "
                   "keywordize) -- got " (pr-str exit-results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :media/op ("get-user-media") -- mutates the REAL `:media/streams` host
;; state. Requires a real `:media/camera` permission grant for
;; `media-capture-result` to actually produce a stream (otherwise it's
;; correctly denied for an unrelated, legitimate reason).
;;
;; This test USED TO document a SEPARATE, then-out-of-scope bug: prior to
;; `normalize-request`'s `nested-keywordize-key?` fix,
;; `:media/constraints`'s own nested JS object (`{video: true}`) was left
;; with raw STRING keys (`{"video" true}`) by `js->clj`, so
;; `media-required-capabilities`'s `(:video constraints)`/`(:audio
;; constraints)` keyword lookups always came back nil and a REAL
;; getUserMedia() call always hit `media-capture-result`'s `(empty?
;; capabilities)` branch (`:media/no-tracks-requested`) regardless of what
;; constraints the script actually passed -- even with a real `:media/camera`
;; grant in place, as asserted here. That bug is now closed (see
;; `quickjs_media_constraints_nested_key_keywordization_smoke_test.cljs` for
;; the dedicated granted-succeeds/denied-still-denies proof), so this test
;; now asserts the CORRECT, fixed outcome: a genuine `:ok? true` stream.
;; -----------------------------------------------------------------------

(deftest quickjs-media-capture-genuinely-reaches-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (-> (profile/new-profile {:id "media-op"})
                   (profile/grant-permission origin :media/camera))
      :path "/media/get-user-media"
      :html (str "<main><script>"
                 "navigator.mediaDevices.getUserMedia({video: true});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [media-results (results-for after :media/capture)]
          (println "media/capture round-trip: real :capability/results ->" (pr-str media-results))
          (is (= [{:capability :media/capture :request/id nil :ok? true
                   :result {:stream/id "media-stream-1"
                            :tracks [{:kind :video
                                      :capability :media/camera
                                      :constraints true}]}
                   :permission/decisions [{:permission/decision :allow
                                           :origin origin
                                           :capability :media/camera
                                           :profile/id "media-op"}]}]
                 media-results)
              (str "expected the real <script> tag's getUserMedia({video: true}) call to genuinely "
                   "reach apply-capability's :media/capture case AND genuinely succeed (proven by "
                   "getting a REAL :ok? true stream result, not :quickjs/invalid-capability-request "
                   "-- 'media/op': 'get-user-media' keywordizes correctly -- and not "
                   ":media/no-tracks-requested -- ':media/constraints' own nested keys now "
                   "keywordize correctly too, see `nested-keywordize-key?`) -- got "
                   (pr-str media-results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :crypto/op ("random-values"/"random-uuid") -- the lowest-severity of the
;; 7: this engine's `crypto.getRandomValues`/`randomUUID` shim NEVER reads
;; any host-computed value back into JS (always a hardcoded zero-filled
;; array / placeholder UUID -- see `quickjs-wasm/webapi-shim-source`), so
;; this bug was audit-trail/host-state-bookkeeping-only (the
;; `:crypto/random-bytes`/`:crypto/random-uuids` draw-queue
;; `take-random-bytes`/`take-random-uuid` consume) with ZERO JS-visible
;; symptom either way. Proven here purely via `:capability/results`.
;; -----------------------------------------------------------------------

(deftest quickjs-crypto-random-values-and-uuid-genuinely-reach-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (profile/new-profile {:id "crypto-op"})
      :path "/crypto/random"
      :html (str "<main><script>"
                 "crypto.getRandomValues(new Uint8Array(4));"
                 "crypto.randomUUID();"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [values-results (results-for after :crypto/random-values)
              uuid-results (results-for after :crypto/random-uuid)]
          (println "crypto/random-values round-trip: real :capability/results ->"
                   (pr-str values-results))
          (println "crypto/random-uuid round-trip: real :capability/results ->"
                   (pr-str uuid-results))
          (is (= [{:capability :crypto/random-values :request/id nil :ok? true
                   :result {:bytes [0 0 0 0]}}]
                 values-results)
              (str "expected the real <script> tag's crypto.getRandomValues(new Uint8Array(4)) to "
                   "genuinely reach apply-capability's :crypto/random-values case (not be rejected "
                   "as :quickjs/invalid-capability-request because 'crypto/op': 'random-values' "
                   "failed to keywordize) -- got " (pr-str values-results)))
          (is (= [{:capability :crypto/random-uuid :request/id nil :ok? true
                   :result {:uuid "00000000-0000-4000-8000-000000000000"}}]
                 uuid-results)
              (str "expected the real <script> tag's crypto.randomUUID() to genuinely reach "
                   "apply-capability's :crypto/random-uuid case (not be rejected as "
                   ":quickjs/invalid-capability-request because 'crypto/op': 'random-uuid' failed "
                   "to keywordize) -- got " (pr-str uuid-results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :notification/op ("request-permission") -- audit-trail/host-state
;; bookkeeping only (the JS-visible callback is a hardcoded 'default'
;; regardless), but still a real gap in `:capability/results`.
;; -----------------------------------------------------------------------

(deftest quickjs-notification-request-permission-genuinely-reaches-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (profile/new-profile {:id "notification-op"})
      :path "/notification/request-permission"
      :html "<main><script>Notification.requestPermission();</script></main>"
      :assertions-fn
      (fn [after]
        (let [results (results-for after :notification/request-permission)]
          (println "notification/request-permission round-trip: real :capability/results ->"
                   (pr-str results))
          (is (= [{:capability :notification/request-permission :request/id nil :ok? true
                   :result {:state "denied"
                            :permission/decision {:permission/decision :deny
                                                  :origin origin
                                                  :capability :notification/show
                                                  :profile/id "notification-op"
                                                  :reason :permission/not-granted}}}]
                 results)
              (str "expected the real <script> tag's Notification.requestPermission() to "
                   "genuinely reach apply-capability's :notification/request-permission case "
                   "(not be rejected as :quickjs/invalid-capability-request because "
                   "'notification/op': 'request-permission' failed to keywordize) -- got "
                   (pr-str results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :location/op ("reload") -- audit-trail/`:context/requests` bookkeeping
;; only (no JS-visible callback at all for reload()).
;; -----------------------------------------------------------------------

(deftest quickjs-location-reload-genuinely-reaches-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (profile/new-profile {:id "location-op"})
      :path "/location/reload"
      :html "<main><script>location.reload();</script></main>"
      :assertions-fn
      (fn [after]
        (let [results (results-for after :location/reload)]
          (println "location/reload round-trip: real :capability/results ->" (pr-str results))
          (is (= [{:capability :location/reload :request/id nil :ok? true
                   :result {:url (str origin "/location/reload") :location/kind :reload}}]
                 results)
              (str "expected the real <script> tag's location.reload() to genuinely reach "
                   "apply-capability's :location/reload case (not be rejected as "
                   ":quickjs/invalid-capability-request because 'location/op': 'reload' failed "
                   "to keywordize) -- got " (pr-str results)))))
      :done done})))

;; -----------------------------------------------------------------------
;; :geolocation/op ("current-position") -- the existing
;; `quickjs_geolocation_smoke_test.cljs` only asserts on `document.title`,
;; which is driven by a permission/position SNAPSHOT computed independently
;; of `capability-request-error` (see that ns's docstring) and so does NOT
;; prove this specific field genuinely keywordizes. This test closes that
;; gap directly via `:capability/results`.
;; -----------------------------------------------------------------------

(deftest quickjs-geolocation-read-genuinely-reaches-real-case-test
  (async done
    (run-op-field-smoke!
     {:profile (-> (profile/new-profile {:id "geolocation-op"})
                   (profile/grant-permission origin :geolocation/read))
      :path "/geolocation/current-position"
      :html (str "<main><script>"
                 "navigator.geolocation.getCurrentPosition(function(){}, function(){});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [results (results-for after :geolocation/read)]
          (println "geolocation/read round-trip: real :capability/results ->" (pr-str results))
          (is (= 1 (count results))
              (str "expected exactly one real :geolocation/read capability result -- got "
                   (pr-str results)))
          (is (true? (:ok? (first results)))
              (str "expected the real <script> tag's getCurrentPosition() call, with a real "
                   ":geolocation/read grant in place, to genuinely reach apply-capability's "
                   ":geolocation/read case and succeed (not be rejected as "
                   ":quickjs/invalid-capability-request because 'geolocation/op': "
                   "'current-position' failed to keywordize) -- got " (pr-str results)))))
      :done done})))
