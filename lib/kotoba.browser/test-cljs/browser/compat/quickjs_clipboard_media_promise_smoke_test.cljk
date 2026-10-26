(ns browser.compat.quickjs-clipboard-media-promise-smoke-test
  "Real page-script round-trip proof for `navigator.clipboard.readText`/
  `writeText` and `navigator.mediaDevices.getUserMedia` being genuinely
  Promise-shaped, and for clipboard's permission gate genuinely rejecting.

  Before this change: `readText()` returned a bare string (not a Promise),
  `writeText()` returned `undefined` (no Promise, no return value at all),
  and `getUserMedia()` returned a plain object (not a Promise) -- any
  real-world caller doing `.then()`/`await` on any of the three crashed with
  a real `TypeError` (`cannot read property 'then' of undefined` /
  `not a function`), aborting that `<script>` tag's whole execution. Also,
  unlike every sibling permission-gated capability (geolocation,
  notifications, fullscreen, media, ...), clipboard never checked
  permission at all -- a denied `:clipboard/read`/`:clipboard/write` grant
  still silently \"succeeded\".

  This closes both gaps together, mirroring `quickjs_geolocation_smoke_test.
  cljs` exactly: `quickjs-execution/evaluate!` computes a REAL
  `clipboard-snapshot` (permission decisions for BOTH `:clipboard/read` and
  `:clipboard/write`, plus the real clipboard text, from the persisted
  `:clipboard` atom -- see `browser.compat.quickjs-runner`'s
  `persistent-execution-keys` -- and the SAME `permission-decision-for` gate
  `apply-capability`'s `:clipboard/read`/`:clipboard/write` cases use)
  host-side BEFORE the script runs, threads it into `quickjs-wasm` as
  `:clipboard/snapshot`, which installs it as
  `globalThis.__kotobaClipboardSnapshot` before eval, and the webapi shim's
  `readText`/`writeText` read it and resolve/reject the promise each
  returns SYNCHRONOUSLY (this engine evaluates a whole script synchronously
  in one pass, so there is no realistic way to defer settlement the way a
  real, async/permission-prompted browser would).

  `getUserMedia` has no real camera/microphone capture pipeline in this
  engine at all (unlike clipboard/geolocation, there is no real permission-
  gated snapshot computed ahead of time for it -- media permission-gating
  stays exactly where it already lived: `apply-capability`'s `:media/capture`
  case, processed post-hoc for the host-side audit trail only, mirroring
  WebSocket/Worker's fire-and-forget precedent). So `getUserMedia` always
  RESOLVES with a placeholder, clearly-simulated `MediaStream`-shaped
  object -- this test proves only that it is now genuinely Promise-shaped
  (no more `TypeError` on `.then()`), not that it enforces media permission.

  The engine, the JS execution, the capability request queuing, and the
  permission-decision gate are all real -- nothing here is mocked or
  inlined. Every assertion below is on the REAL committed `document.title` a
  real `<script>` tag set from what `readText`/`writeText`/`getUserMedia`'s
  real `.then()`/`.catch()` callbacks actually received, not a host-side
  `:capability/results` log entry."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(def ^:private origin "kotoba://quickjs-runner")

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- seed-clipboard
  "Seed a real `:clipboard` text atom into `session`'s page-lifetime
  `quickjs-execution` runtime state, tagged with the generation the page
  about to be `load-html!`'d will commit -- mirrors
  `quickjs_geolocation_smoke_test.cljs`'s `seed-geolocation` exactly (see
  that fn's docstring for why the generation has to be `inc`'d ahead of
  time). This is the host-side injection point a real host would use to
  seed a real system clipboard's current contents; JS itself only ever
  reads it via `readText`, never sets it directly (`writeText` queues a
  `clipboard/write` request the host applies AFTER the script, exactly like
  `localStorage.setItem`)."
  [session text]
  (assoc session :browser.session/quickjs-runtime-state
         {:quickjs-runtime/generation (inc (:browser.session/page-generation session 0))
          :quickjs-runtime/state {:clipboard (atom {:text text})}}))

(defn- persisted-clipboard-text
  [session]
  (some-> (get-in session [:browser.session/quickjs-runtime-state
                           :quickjs-runtime/state :clipboard])
          deref
          :text))

(defn- build-session
  [profile]
  (let [h (host/recording-host)]
    (session/new-session
     (quickjs-runner/quickjs-session-opts {:host h :profile profile}))))

(defn- run-page!
  "Load a single real page at a fresh path under `origin` with `html` as its
  only content, on the already-`ensure-script-engine!`'d `ready-session`.
  Returns the resulting session after that page's real `<script>` tag(s) ran."
  [ready-session path html]
  (session/load-html! ready-session {:url (str origin path) :html html}))

(defn- title-of
  [session]
  (get-in session [:browser.session/page :browser/title]))

(defn- run-clipboard-media-smoke!
  "Shared harness: build a session with `profile`, optionally seed a real
  clipboard snapshot (`clipboard-text`, or nil to skip seeding), run `html`
  as a single real `<script>` tag at a fresh path (`path`), and hand the
  final session + persisted-clipboard-text to `assertions-fn` -- mirrors
  every other `test-cljs` smoke test's `async done` + `.then`/`.catch`
  skeleton (see `quickjs_geolocation_smoke_test.cljs`)."
  [{:keys [profile clipboard-text path html assertions-fn done]}]
  (let [base-session (build-session profile)]
    (-> (session/ensure-script-engine! base-session)
        (.then
         (fn [ready-session]
           (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                 :script-engine/status]))
               "engine should be ready before running page scripts")
           (try
             (let [seeded-session (cond-> ready-session
                                    (some? clipboard-text)
                                    (seed-clipboard clipboard-text))
                   after (run-page! seeded-session path html)]
               (assertions-fn after))
             (finally
               (dispose-engine! ready-session)
               (done)))))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (dispose-engine! base-session)
                  (done))))))

(deftest quickjs-clipboard-readtext-resolves-with-real-text-test
  (async done
    (run-clipboard-media-smoke!
     {:profile (-> (profile/new-profile {:id "clipboard-read-allowed"})
                   (profile/grant-permission origin :clipboard/read))
      :clipboard-text "real-clipboard-value"
      :path "/clipboard-round-trip/readtext-success"
      :html (str "<main><script>"
                 "navigator.clipboard.readText().then(function(text) {"
                 "document.title = text;"
                 "}, function(err) {"
                 "document.title = 'unexpected-rejection:' + err.name;"
                 "});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [title (title-of after)]
          (println "clipboard readText round-trip (granted): real committed document.title ->"
                   (pr-str title))
          (is (= "real-clipboard-value" title)
              (str "expected readText()'s real .then() callback to synchronously receive the "
                   "real, host-seeded clipboard text and commit it into document.title -- got "
                   (pr-str title)))))
      :done done})))

(deftest quickjs-clipboard-readtext-rejects-when-permission-denied-test
  (async done
    (run-clipboard-media-smoke!
     {;; A real profile that exists but was never granted :clipboard/read --
      ;; mirrors quickjs-execution-test's
      ;; quickjs-clipboard-read-denies-without-profile-grant, proven here via
      ;; a real JS-visible .catch() instead of a host-side :capability/results
      ;; entry.
      :profile (profile/new-profile {:id "clipboard-read-denied"})
      ;; A real clipboard value IS available host-side -- proving the
      ;; rejection is genuinely gated by the permission decision, not merely
      ;; by "no clipboard text was ever seeded".
      :clipboard-text "should-never-be-observed"
      :path "/clipboard-round-trip/readtext-denied"
      :html (str "<main><script>"
                 "navigator.clipboard.readText().then(function(text) {"
                 "document.title = 'unexpected-success:' + text;"
                 "}, function(err) {"
                 "document.title = err.name + ':' + err.message;"
                 "});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [title (title-of after)]
          (println "clipboard readText round-trip (denied): real committed document.title ->"
                   (pr-str title))
          (is (= "NotAllowedError:User denied Clipboard read (permission/not-granted)" title)
              (str "expected the real <script> tag's readText() promise to genuinely REJECT "
                   "(not resolve) because the active profile never granted :clipboard/read -- "
                   "even though a real clipboard value WAS available host-side -- got "
                   "document.title = " (pr-str title)))))
      :done done})))

(deftest quickjs-clipboard-writetext-resolves-and-really-writes-test
  (async done
    (run-clipboard-media-smoke!
     {:profile (-> (profile/new-profile {:id "clipboard-write-allowed"})
                   (profile/grant-permission origin :clipboard/write))
      :clipboard-text "before-write"
      :path "/clipboard-round-trip/writetext-success"
      :html (str "<main><script>"
                 "navigator.clipboard.writeText('written-by-real-script').then(function(value) {"
                 "document.title = 'write-ok:' + (value === undefined);"
                 "}, function(err) {"
                 "document.title = 'unexpected-rejection:' + err.name;"
                 "});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [title (title-of after)
              persisted-text (persisted-clipboard-text after)]
          (println "clipboard writeText round-trip (granted): real committed document.title ->"
                   (pr-str title))
          (println "clipboard writeText round-trip (granted): real persisted clipboard text ->"
                   (pr-str persisted-text))
          (is (= "write-ok:true" title)
              (str "expected writeText()'s real .then() callback to synchronously fire with "
                   "`undefined` (real writeText() resolves to no value) -- got document.title = "
                   (pr-str title)))
          (is (= "written-by-real-script" persisted-text)
              (str "expected the real <script> tag's writeText() call to genuinely mutate the "
                   "sandboxed clipboard store (applied post-hoc by apply-capability's "
                   ":clipboard/write case), not just resolve its promise -- got persisted text = "
                   (pr-str persisted-text)))))
      :done done})))

(deftest quickjs-clipboard-writetext-rejects-when-permission-denied-and-does-not-write-test
  (async done
    (run-clipboard-media-smoke!
     {:profile (profile/new-profile {:id "clipboard-write-denied"})
      :clipboard-text "must-remain-unchanged"
      :path "/clipboard-round-trip/writetext-denied"
      :html (str "<main><script>"
                 "navigator.clipboard.writeText('attempted-overwrite').then(function() {"
                 "document.title = 'unexpected-success';"
                 "}, function(err) {"
                 "document.title = err.name + ':' + err.message;"
                 "});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [title (title-of after)
              persisted-text (persisted-clipboard-text after)]
          (println "clipboard writeText round-trip (denied): real committed document.title ->"
                   (pr-str title))
          (println "clipboard writeText round-trip (denied): real persisted clipboard text ->"
                   (pr-str persisted-text))
          (is (= "NotAllowedError:User denied Clipboard write (permission/not-granted)" title)
              (str "expected the real <script> tag's writeText() promise to genuinely REJECT "
                   "because the active profile never granted :clipboard/write -- got "
                   "document.title = " (pr-str title)))
          (is (= "must-remain-unchanged" persisted-text)
              (str "a denied writeText() must NOT mutate the sandboxed clipboard store -- got "
                   "persisted text = " (pr-str persisted-text)))))
      :done done})))

(deftest quickjs-getusermedia-resolves-without-throwing-test
  (async done
    (run-clipboard-media-smoke!
     {;; getUserMedia has no real permission-gated snapshot in this engine
      ;; (see namespace docstring) -- a profile with no grants at all is
      ;; deliberately used here to prove it still resolves rather than
      ;; throwing/rejecting, i.e. this test is purely a Promise-SHAPE proof.
      :profile (profile/new-profile {:id "media-no-grants"})
      :path "/media-round-trip/getusermedia-resolves"
      :html (str "<main><script>"
                 "navigator.mediaDevices.getUserMedia({video: true, audio: true}).then(function(stream) {"
                 "document.title = 'media-ok:' + (typeof stream.getTracks === 'function') "
                 "+ ':' + Array.isArray(stream.getTracks());"
                 "}, function(err) {"
                 "document.title = 'unexpected-rejection:' + (err && err.name);"
                 "});"
                 "</script></main>")
      :assertions-fn
      (fn [after]
        (let [title (title-of after)]
          (println "getUserMedia round-trip: real committed document.title ->" (pr-str title))
          (is (= "media-ok:true:true" title)
              (str "expected getUserMedia(...)'s real .then() callback to synchronously fire "
                   "(not throw a TypeError on a non-Promise, not reject) with a placeholder, "
                   "clearly-simulated MediaStream-shaped object exposing a real getTracks() "
                   "function -- got document.title = " (pr-str title)))))
      :done done})))
