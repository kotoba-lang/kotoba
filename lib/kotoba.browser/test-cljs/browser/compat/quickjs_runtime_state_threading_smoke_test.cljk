(ns browser.compat.quickjs-runtime-state-threading-smoke-test
  "Real page-script-lifecycle smoke test proving `browser.compat.quickjs-runner`
  threads `quickjs-execution` runtime state (not just `:document`) across
  every `<script>` tag within one page load, and resets it on a real
  navigation.

  Companion to `quickjs-script-runner-smoke-test` (which proves a single
  script's DOM mutation lands for real). This test exercises TWO real
  `<script>` tags on the same real page, where the second only gets the
  right real host-side answer if runtime state (here: the
  `:storage/get|put|delete` capability, which `quickjs-execution` models as
  page-lifetime state) genuinely survived from the first -- then does a
  second, separate real `load-html!` proving that survival does NOT leak
  across a real navigation/reload.

  `quickjs-runtime-state-threads-across-scripts-and-resets-on-navigation-test`
  below inspects the REAL, host-side capability answer that
  `browser.compat.quickjs-execution/apply-capability` computed for the real
  `:storage/get` request the second script's real JS emits, via the
  `:capability/results` this change adds to the session's committed
  `:script/quickjs-run` history events -- that host-side threading proof
  predates, and is unaffected by, the JS-visible round-trip below.

  `quickjs-storage-getitem-round-trips-into-vm-test` closes the gap that
  test's original docstring used to document: `localStorage.getItem`'s
  JS-VISIBLE return value now genuinely reflects real host `:storage` state,
  via a `:storage/snapshot` (`browser.compat.quickjs-execution`'s
  `invocation-with-snapshots`) installed as a VM global
  (`globalThis.__kotobaStorageSnapshot`, `browser.compat.quickjs-wasm`'s
  `storage-snapshot-source`/`install-document-shim!`) before each script
  evaluates -- proven by asserting the real, committed `document.title` a
  later `<script>` tag sets from `localStorage.getItem(...)`, not just a
  host-side log entry. The engine, the JS execution, the capability
  requests, and their host-side/VM answers are all real -- nothing here is
  mocked or inlined."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- quickjs-run-events
  "`:script/quickjs-run` history events for `session`'s CURRENT page only
  (`:browser.session/history` is a single append-only log across every
  `load-html!` a session has ever done, so this filters by the current
  page's real, committed URL rather than accidentally reaching back into a
  prior page's events)."
  [session]
  (let [current-url (get-in session [:browser.session/page :browser/url])]
    (filter #(and (= :script/quickjs-run (:event %))
                  (= current-url (:script/url %)))
            (:browser.session/history session))))

(defn- storage-get-results
  "Real :storage/get `:capability/results` entries across every real
  quickjs-run history event for `session`'s current page."
  [session]
  (->> (quickjs-run-events session)
       (mapcat :capability/results)
       (filter #(= :storage/get (:capability %)))))

(deftest quickjs-runtime-state-threads-across-scripts-and-resets-on-navigation-test
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
             (try
               (let [;; Page 1: two REAL <script> tags. The second only sees
                     ;; "set-by-script-one" if :storage (page-lifetime
                     ;; quickjs-execution state) survived from the first.
                     html-1 (str "<main>"
                                 "<script>localStorage.setItem('probe', 'set-by-script-one');</script>"
                                 "<script>localStorage.getItem('probe');</script>"
                                 "</main>")
                     after-1 (session/load-html!
                              ready-session
                              {:url "kotoba://quickjs-runner/runtime-state/page-one"
                               :html html-1})
                     gen-1 (:browser.session/page-generation after-1)
                     runtime-1 (:browser.session/quickjs-runtime-state after-1)
                     storage-atom-1 (get-in runtime-1 [:quickjs-runtime/state :storage])
                     get-results-1 (storage-get-results after-1)]
                 (println "quickjs runtime-state threading: page 1 real quickjs-run count ->"
                          (count (quickjs-run-events after-1)))
                 (println "quickjs runtime-state threading: page 1 real storage/get"
                          ":capability/results ->" (pr-str get-results-1))
                 (println "quickjs runtime-state threading: page 1 persisted storage atom ->"
                          (pr-str (some-> storage-atom-1 deref)))
                 (is (= 4 (count (quickjs-run-events after-1)))
                     "expected 4 real quickjs runs: 2 inline <script> tags + DOMContentLoaded + load")
                 (is (= gen-1 (:quickjs-runtime/generation runtime-1))
                     "persisted quickjs runtime state should be tagged with page 1's real generation")
                 (is (= {"probe" "set-by-script-one"} (some-> storage-atom-1 deref))
                     "the persisted :storage atom should hold what the first real <script> wrote")
                 (is (= [{:capability :storage/get :request/id nil :ok? true
                          :result "set-by-script-one"}]
                        get-results-1)
                     (str "the SECOND real <script> tag's real storage/get request should be "
                          "answered by the host with what the FIRST real <script> tag wrote via "
                          "localStorage.setItem -- only possible if quickjs-execution runtime "
                          "state genuinely survived across the two separate evaluate! calls, "
                          "got: " (pr-str get-results-1)))

                 ;; Page 2: a real, separate navigation (fresh load-html! call,
                 ;; a real new :browser.session/page-generation). Its single
                 ;; real <script> tag re-reads the SAME storage key and must
                 ;; NOT see page 1's real value.
                 (let [html-2 "<main><script>localStorage.getItem('probe');</script></main>"
                       after-2 (session/load-html!
                                after-1
                                {:url "kotoba://quickjs-runner/runtime-state/page-two"
                                 :html html-2})
                       gen-2 (:browser.session/page-generation after-2)
                       runtime-2 (:browser.session/quickjs-runtime-state after-2)
                       storage-atom-2 (get-in runtime-2 [:quickjs-runtime/state :storage])
                       get-results-2 (storage-get-results after-2)]
                   (println "quickjs runtime-state threading: page 2 (after a real navigation)"
                            "real storage/get :capability/results ->" (pr-str get-results-2))
                   (println "quickjs runtime-state threading: page 2 persisted storage atom ->"
                            (pr-str (some-> storage-atom-2 deref)))
                   (is (not= gen-1 gen-2)
                       "sanity: the second load-html! must be a real, new page generation")
                   (is (= gen-2 (:quickjs-runtime/generation runtime-2))
                       "persisted quickjs runtime state should now be tagged with page 2's real generation")
                   (is (= {} (some-> storage-atom-2 deref))
                       "a real navigation must reset the persisted :storage atom, not carry page 1's forward")
                   (is (= [{:capability :storage/get :request/id nil :ok? true :result nil}]
                          get-results-2)
                       (str "after a REAL navigation to a new page, the same storage key must "
                            "really read back nil from the host -- page 1's runtime state must "
                            "not leak into page 2, got: " (pr-str get-results-2)))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))

(deftest quickjs-storage-getitem-round-trips-into-vm-test
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
             (try
               ;; Page 1: the FIRST real <script> tag writes via
               ;; localStorage.setItem; the SECOND real <script> tag reads it
               ;; back via localStorage.getItem and assigns the result to
               ;; document.title. document.title only ends up
               ;; "set-by-script-one" if the real value genuinely round-trips
               ;; back into the running QuickJS VM as getItem's JS-visible
               ;; return value -- not just recorded in a host-side log.
               (let [html-1 (str "<main>"
                                  "<script>localStorage.setItem('probe', 'set-by-script-one');</script>"
                                  "<script>document.title = localStorage.getItem('probe');</script>"
                                  "</main>")
                     after-1 (session/load-html!
                              ready-session
                              {:url "kotoba://quickjs-runner/capability-read-round-trip/page-one"
                               :html html-1})
                     title-1 (get-in after-1 [:browser.session/page :browser/title])]
                 (println "capability read round-trip: real document.title after"
                          "`document.title = localStorage.getItem('probe')` ->" (pr-str title-1))
                 (is (= "set-by-script-one" title-1)
                     (str "expected the SECOND real <script> tag's localStorage.getItem('probe') "
                          "to synchronously return the value the FIRST real <script> tag wrote via "
                          "setItem, genuinely round-tripped back into the running QuickJS VM (not "
                          "just recorded host-side) and visible to the rest of that script's real "
                          "JS execution -- got document.title = " (pr-str title-1)))

                 ;; Page 2: a real, separate navigation. Its single real
                 ;; <script> tag reads a key that was never set on this new
                 ;; page and must genuinely get null back -- page 1's real
                 ;; storage must not leak forward across generations.
                 (let [html-2 (str "<main><script>"
                                   "document.title = String(localStorage.getItem('probe'));"
                                   "</script></main>")
                       after-2 (session/load-html!
                                after-1
                                {:url "kotoba://quickjs-runner/capability-read-round-trip/page-two"
                                 :html html-2})
                       title-2 (get-in after-2 [:browser.session/page :browser/title])]
                   (println "capability read round-trip: fresh navigation's real"
                            "localStorage.getItem('probe') on an unset key ->" (pr-str title-2))
                   (is (= "null" title-2)
                       (str "a fresh navigation must not leak page 1's real storage forward -- "
                            "localStorage.getItem on a key unset on the new page must genuinely "
                            "return null to JS (String(null) === \"null\"), got document.title = "
                            (pr-str title-2)))))
               (finally
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
