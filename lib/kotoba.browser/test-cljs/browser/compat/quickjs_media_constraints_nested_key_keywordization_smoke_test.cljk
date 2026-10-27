(ns browser.compat.quickjs-media-constraints-nested-key-keywordization-smoke-test
  "Real page-script round-trip proof that `navigator.mediaDevices.
  getUserMedia(constraints)`'s `constraints` object -- pushed by the webapi
  shim verbatim as `'media/constraints': constraints || {}` (see
  `quickjs-wasm/webapi-shim-source`) -- genuinely has ITS OWN nested keys
  (`video`/`audio`) keywordized before `quickjs-execution/media-required-
  capabilities` ever sees them.

  Before this change: `browser.compat.quickjs-wasm/normalize-request`
  keywordized nested map keys only under the TOP-LEVEL `:request`/`:event`
  fields (its `cond`'s two explicit `(and (= :request k) (map? v))`/
  `(and (= :event k) (map? v))` branches) -- `:media/constraints` was NOT
  one of those two, so `js->clj` left ITS keys as raw JS-object-turned-
  Clojure-map STRINGS (a real `getUserMedia({video: true})` call round-
  tripped as `{:media/constraints {\"video\" true}}`, NOT `{:video true}`).
  `media-required-capabilities`'s `(:video constraints)`/`(:audio
  constraints)` are bare KEYWORD lookups, so on a string-keyed map they
  ALWAYS returned nil regardless of what the script actually requested,
  which made `media-capture-result`'s `(empty? capabilities)` branch ALWAYS
  fire -- producing a `:media/no-tracks-requested` domain error even for a
  script that correctly called `getUserMedia({video: true})` against a
  profile that HAD genuinely granted `:media/camera`. This is exactly the
  bug `quickjs_capability_op_field_keywordization_smoke_test.cljs`'s
  `quickjs-media-capture-genuinely-reaches-real-case-test` originally
  documented as a separate, then-out-of-scope issue (see that test's
  history) before this fix closed it.

  `normalize-request` now recognizes `:media/constraints` as a third
  `nested-keywordize-key?` field, alongside `:request`/`:event`, and
  keywordizes its own top-level nested keys the exact same (single-level)
  way. This is deliberately NOT a blanket 'keywordize every nested map's
  keys, always' rule -- see `nested-keywordize-key?`'s docstring in
  `quickjs_wasm.cljc` for the verified counter-examples (`history.
  pushState`/`replaceState`'s `:state`, `Worker`/`BroadcastChannel`
  `postMessage`'s `:message`) where a nested map's OWN keys are genuinely
  arbitrary page-author-chosen data that must stay string-keyed.

  Both tests below prove the fix cuts both ways: a genuinely GRANTED
  `:media/camera` capability now genuinely SUCCEEDS (not
  `:media/no-tracks-requested`), and a genuinely UNGRANTED one still
  correctly DENIES (proving the constraints-parsing fix did not
  accidentally punch a hole in the permission gate). A third test proves
  `getUserMedia({video: true, audio: true})` correctly asks for BOTH
  capabilities independently (a camera grant alone still denies audio).

  The engine, the JS execution, the capability request queuing, and the
  permission-decision gates below are all real -- nothing here is mocked or
  inlined. Every assertion is on the real, host-side `:capability/results`
  audit trail (`getUserMedia` itself always synchronously RESOLVES in this
  engine regardless of the host-side decision -- see
  `quickjs_clipboard_media_promise_smoke_test.cljs`'s namespace docstring --
  so `:capability/results` is the only real signal for whether the
  underlying `:media/capture` capability request itself succeeded)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(def ^:private origin "kotoba://quickjs-media-constraints")

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- build-session
  [profile]
  (let [h (host/recording-host)]
    (session/new-session
     (quickjs-runner/quickjs-session-opts {:host h :profile profile}))))

(defn- quickjs-run-events
  "`:script/quickjs-run` history events for `session`'s CURRENT page only --
  mirrors `quickjs_runtime_state_threading_smoke_test.cljs`'s /
  `quickjs_capability_op_field_keywordization_smoke_test.cljs`'s identically
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

(defn- run-media-smoke!
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

(deftest quickjs-getusermedia-video-succeeds-with-real-camera-grant-test
  (async done
    (run-media-smoke!
     {:profile (-> (profile/new-profile {:id "media-constraints-granted"})
                   (profile/grant-permission origin :media/camera))
      :path "/media-constraints/video-granted"
      :html (str "<main><script>"
                 "navigator.mediaDevices.getUserMedia({video: true});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [results (results-for after :media/capture)]
          (println "getUserMedia({video: true}) with real :media/camera grant: "
                   "real :capability/results ->" (pr-str results))
          (is (= 1 (count results))
              (str "expected exactly one real :media/capture capability result -- got "
                   (pr-str results)))
          (let [result (first results)]
            (is (true? (:ok? result))
                (str "expected getUserMedia({video: true}) against a profile that genuinely "
                     "granted :media/camera to SUCCEED (constraints' own nested `video` key must "
                     "keywordize to :video so media-required-capabilities actually sees the "
                     "request), not fail with " (pr-str (:error result)) " -- got "
                     (pr-str result)))
            (is (not= :media/no-tracks-requested (:error result))
                (str "the exact wrong-error regression this fix closes: getUserMedia({video: "
                     "true}) must never be misread as requesting NO tracks at all -- got "
                     (pr-str result)))
            (is (= {:stream/id "media-stream-1"
                    :tracks [{:kind :video
                              :capability :media/camera
                              :constraints true}]}
                   (:result result))
                (str "expected a real, correctly-shaped simulated MediaStream with exactly one "
                     "video track -- got " (pr-str (:result result))))
            (is (= [{:permission/decision :allow
                     :origin origin
                     :capability :media/camera
                     :profile/id "media-constraints-granted"}]
                   (:permission/decisions result))
                (str "expected exactly one real :media/camera permission decision, genuinely "
                     "ALLOW -- proving media-required-capabilities genuinely recognized the "
                     "request needed :media/camera -- got " (pr-str (:permission/decisions result)))))))
      :done done})))

(deftest quickjs-getusermedia-video-still-denies-without-camera-grant-test
  (async done
    (run-media-smoke!
     {;; A real profile that exists but never granted :media/camera --
      ;; proves the constraints-parsing fix did NOT accidentally bypass the
      ;; permission gate: this must still be a real, correctly-attributed
      ;; :permission/not-granted denial, not a silent success and not the
      ;; unrelated :media/no-tracks-requested misdiagnosis either.
      :profile (profile/new-profile {:id "media-constraints-denied"})
      :path "/media-constraints/video-denied"
      :html (str "<main><script>"
                 "navigator.mediaDevices.getUserMedia({video: true});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [results (results-for after :media/capture)]
          (println "getUserMedia({video: true}) without :media/camera grant: "
                   "real :capability/results ->" (pr-str results))
          (is (= 1 (count results))
              (str "expected exactly one real :media/capture capability result -- got "
                   (pr-str results)))
          (let [result (first results)]
            (is (false? (:ok? result))
                (str "expected getUserMedia({video: true}) against a profile that never granted "
                     ":media/camera to genuinely FAIL -- got " (pr-str result)))
            (is (= :permission/not-granted (:error result))
                (str "expected the real permission-decision denial reason, proving "
                     "media-required-capabilities genuinely recognized the request needed "
                     ":media/camera and routed it through the real permission gate (NOT the "
                     "unrelated :media/no-tracks-requested misdiagnosis this fix closes) -- got "
                     (pr-str (:error result))))
            (is (= [{:permission/decision :deny
                     :origin origin
                     :capability :media/camera
                     :profile/id "media-constraints-denied"
                     :reason :permission/not-granted}]
                   (:permission/decisions result))
                (str "expected exactly one real :media/camera permission decision, genuinely "
                     "DENY -- got " (pr-str (:permission/decisions result)))))))
      :done done})))

(deftest quickjs-getusermedia-video-and-audio-requests-both-capabilities-independently-test
  (async done
    (run-media-smoke!
     {;; Camera granted, microphone NOT granted -- proves BOTH constraints
      ;; keys (`video` AND `audio`) independently keywordize and drive their
      ;; own :media/camera / :media/microphone permission decision, rather
      ;; than (e.g.) only the first key ever being recognized.
      :profile (-> (profile/new-profile {:id "media-constraints-partial"})
                   (profile/grant-permission origin :media/camera))
      :path "/media-constraints/video-and-audio-partial-grant"
      :html (str "<main><script>"
                 "navigator.mediaDevices.getUserMedia({video: true, audio: true});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [results (results-for after :media/capture)]
          (println "getUserMedia({video: true, audio: true}) with camera-only grant: "
                   "real :capability/results ->" (pr-str results))
          (is (= 1 (count results))
              (str "expected exactly one real :media/capture capability result -- got "
                   (pr-str results)))
          (let [result (first results)]
            (is (false? (:ok? result))
                (str "expected a request for BOTH video and audio, with only :media/camera "
                     "granted, to genuinely FAIL on the ungranted :media/microphone -- got "
                     (pr-str result)))
            (is (= :permission/not-granted (:error result))
                (str "expected the denial reason to come from the real :media/microphone "
                     "permission decision -- got " (pr-str (:error result))))
            (is (= [{:permission/decision :allow
                     :origin origin
                     :capability :media/camera
                     :profile/id "media-constraints-partial"}
                    {:permission/decision :deny
                     :origin origin
                     :capability :media/microphone
                     :profile/id "media-constraints-partial"
                     :reason :permission/not-granted}]
                   (:permission/decisions result))
                (str "expected TWO independent real permission decisions -- one ALLOW for "
                     ":media/camera (the `video` key) and one DENY for :media/microphone (the "
                     "`audio` key) -- proving getUserMedia({video: true, audio: true}) genuinely "
                     "requests BOTH capabilities independently once both nested constraint keys "
                     "keywordize correctly -- got " (pr-str (:permission/decisions result)))))))
      :done done})))
