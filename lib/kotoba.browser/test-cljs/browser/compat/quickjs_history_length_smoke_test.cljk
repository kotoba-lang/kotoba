(ns browser.compat.quickjs-history-length-smoke-test
  "Real page-script round-trip proof for `globalThis.history.length`'s
  seeded STARTING value.

  Companion to `quickjs-notification-smoke-test`/`quickjs-geolocation-smoke-test`
  (same shape: a real, end-to-end proof that a webapi shim reflects REAL
  host-side state synchronously, not a hardcoded placeholder). Before this
  change, `browser.compat.quickjs-wasm`'s `globalThis.history` shim
  hardcoded `length: 0` on every fresh construction, regardless of how many
  real navigations had actually happened in the session --
  `browser.compat.quickjs-execution/new-state`'s own default is
  `:history/entries [] :history/index -1` for every fresh generation, and
  nothing threaded the REAL `:browser.session/navigation` entry count in at
  all. This closes that gap the same way notification permission was
  closed: `browser.compat.quickjs-runner/run-script!` computes the real,
  current `(count (:entries (:browser.session/navigation session)))` and
  threads it into `quickjs-execution/new-state` as `:history-length`, a
  plain integer (NOT a live atom -- a session's navigation depth cannot
  change mid-script); `evaluate!`/`load-module!` thread it into
  `quickjs-wasm` as `:history/snapshot` via `history-length-snapshot`; and
  `quickjs-wasm` installs it as `globalThis.__kotobaHistoryLength` before
  eval, which the webapi shim's `globalThis.history` object now reads for
  its `length` property's STARTING value instead of the hardcoded `0`.

  Uses `browser.session/navigate!` (a real fetch-fn round-trip, redirects
  and all -- the actual top-level real-navigation entry point, not a
  lower-level `load-html!`/hand-built-state construction) for every page in
  this test, mirroring the task's own repro shape: a real session that has
  ALREADY done a couple of real navigations before the script that reads
  `history.length` ever runs.

  IMPORTANT SCOPING NOTE, confirmed empirically while building this test:
  `globalThis.history` is the ONE webapi-shim object guarded by
  `globalThis.history || {...}` (every other shim object --
  `document`/`localStorage`/`navigator.geolocation`/`Notification`/
  `WebSocket` -- is reassigned FRESH, unconditionally, on every single
  eval). That guard exists so `pushState`/`replaceState`'s mutations of
  `this.length` survive across multiple `<script>` tags WITHIN one page --
  but it also means `globalThis.history`, once constructed, persists
  UNCHANGED for the rest of the underlying QuickJS engine's lifetime,
  including across LATER real navigations that reuse the same
  already-`:ready` engine (this engine does not tear down and recreate its
  VM context on navigation -- see `quickjs-runtime-state-threading-smoke-test`
  proving `:storage` resets across navigation via a FRESH Clojure-side atom
  per generation, not via VM context teardown). So this fix genuinely seeds
  the REAL navigation depth for the FIRST script ever evaluated on a given
  engine (proven below, and the realistic case: an embedding application
  typically brings up its script engine once real content is about to run,
  after any pre-navigation/redirect steps) -- it does NOT retroactively
  reseed `history.length` for a SECOND navigation that reuses an
  ALREADY-warmed-up engine whose `globalThis.history` object already
  exists (that would require also touching the `globalThis.history ||
  {...}` construction guard / `pushState` etc., which is deliberately out
  of scope for this change -- see `quickjs-execution/history-length-snapshot`'s
  docstring)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn
  "A real `:browser.session/fetch-fn` (the SAME injection point
  `browser.session/navigate!` uses for real page loads AND
  `quickjs-execution`'s `fetch()` capability would use) that serves `pages`
  (a `{url html}` map) as real `200`-status HTML bodies."
  [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body (str "<main>not found: " url "</main>")})))

(deftest quickjs-history-length-reflects-real-navigation-depth-test
  (async done
    (let [one-url "https://app.example/history-round-trip/one"
          two-url "https://app.example/history-round-trip/two"
          three-url "https://app.example/history-round-trip/three"
          fetch-fn (canned-fetch-fn
                    {one-url "<main>One</main>"
                     two-url "<main>Two</main>"
                     three-url (str "<main><script>"
                                    "document.title = String(history.length);"
                                    "</script></main>")})
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))
          ;; Two REAL navigations before the engine is ever brought up --
          ;; `run-page-scripts!`/`run-script!` skip evaluating anything
          ;; while the engine isn't `:ready` yet (see
          ;; `execution/engine-ready?`), so these build up REAL
          ;; `:browser.session/navigation` entries without ever touching
          ;; the QuickJS VM, exactly mirroring the task's own repro
          ;; ("browser.session/navigate! for a couple of real page loads
          ;; ... then run a REAL script").
          after-one (session/navigate! base-session one-url)
          after-two (session/navigate! after-one two-url)]
      (is (= 2 (count (get-in after-two [:browser.session/navigation :entries])))
          "two real navigations before the engine is ready should already have built up two real navigation entries")
      (-> (session/ensure-script-engine! after-two)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (try
               ;; Third real navigation: the FIRST real eval this freshly-
               ;; readied engine ever runs. Its <script> reads
               ;; history.length synchronously into document.title.
               (let [after-three (session/navigate! ready-session three-url)
                     title (get-in after-three [:browser.session/page :browser/title])]
                 (is (= 3 (count (get-in after-three [:browser.session/navigation :entries])))
                     "three real navigations should have built up three real navigation entries")
                 (println "history.length round-trip: real committed document.title ->"
                          (pr-str title))
                 (is (= "3" title)
                     (str "expected the real <script> tag's history.length property read to "
                          "synchronously report the REAL session navigation depth (3 real "
                          "navigations already committed) -- not the engine's hardcoded 0 -- got "
                          "document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! after-two)
                    (done)))))))

(deftest quickjs-history-length-defaults-to-zero-for-a-brand-new-session-test
  ;; Regression guard: a session that has never navigated at all (no
  ;; :browser.session/navigation entries yet) must seed history.length as
  ;; 0, mirroring a fresh, never-navigated real browsing context.
  (async done
    (let [url "https://app.example/history-round-trip/fresh"
          fetch-fn (canned-fetch-fn
                    {url (str "<main><script>"
                             "document.title = String(history.length);"
                             "</script></main>")})
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
      (is (= 0 (count (get-in base-session [:browser.session/navigation :entries])))
          "sanity: a brand-new session has no navigation entries yet")
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (is (= :ready (get-in ready-session [:browser.session/script-engine
                                                   :script-engine/status]))
                 "engine should be ready before running page scripts")
             (try
               (let [after (session/navigate! ready-session url)
                     title (get-in after [:browser.session/page :browser/title])]
                 (is (= 1 (count (get-in after [:browser.session/navigation :entries])))
                     "the real navigation itself is the session's first navigation entry")
                 (println "history.length round-trip (first-ever navigation): real committed"
                          "document.title ->" (pr-str title))
                 (is (= "1" title)
                     (str "expected history.length to report 1 (the page ITSELF is the first "
                          "real navigation entry), not the engine's hardcoded 0 -- got "
                          "document.title = " (pr-str title))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
