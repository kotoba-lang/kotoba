(ns browser.compat.quickjs-websocket-onerror-smoke-test
  "Real page-script proof that `ws.onerror` actually fires, and fires
  EXACTLY ONCE across multiple `<script>` tags, mirroring
  `quickjs_websocket_onopen_smoke_test.cljs`'s real-connection infra.

  Before this cycle's fix, `browser.net.websocket`'s real `:cljs`
  `connect!` genuinely captured a real `onerror` event into a real
  `:error` atom (see that namespace), and `drain-messages!` genuinely
  returned it -- the data pipeline worked end-to-end up to the very last
  step, where `quickjs-execution/websocket-connection-snapshot` silently
  dropped `(:error drained)` on the floor, so the webapi shim's delivery
  IIFE (which never checked for an `:error` key at all) could never fire
  `ws.onerror`. This test proves BOTH halves of the fix: a REAL
  connection failure (a real TCP connection refused by the OS -- nothing
  is listening on the target port) genuinely reaches `ws.onerror` on the
  first snapshot install after the failure is observed, AND does NOT fire
  again on a later script tag now that `:websocket/errored`'s dedup set
  has recorded it as already delivered -- the underlying real `error`
  atom never resets once set, so without that dedup the same error would
  redeliver on every later script tag forever."
  (:require ["net" :as net]
            [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.net.websocket :as ws]
            [browser.origin :as origin]
            [browser.profile :as profile]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- get-refused-port!
  "Open a real server on an OS-assigned loopback port, then immediately
   close it -- the returned port is now guaranteed to refuse new
   connections (nothing listening), a genuine, portable way to force a
   real connection-refused error rather than guessing at a hardcoded
   port number that might happen to be in use."
  []
  (js/Promise.
   (fn [resolve _reject]
     (let [server (.createServer net (fn [_socket] nil))]
       (.listen server 0 "127.0.0.1"
                (fn []
                  (let [port (.-port (.address server))]
                    (.close server (fn [] (resolve port))))))))))

(defn- wait-ms
  [ms]
  (js/Promise. (fn [resolve _reject] (js/setTimeout resolve ms))))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- build-session
  [url]
  (let [profile (-> (profile/new-profile {:id "ws-allowed"})
                    (profile/grant-permission (origin/origin url) :websocket/connect))
        h (host/recording-host)]
    (session/new-session
     (quickjs-runner/quickjs-session-opts
      {:host h
       :profile profile
       :websocket-fn (ws/websocket-fn)}))))

(defn- run-script1!
  [ready-session url]
  (let [page-session (session/load-html!
                      ready-session
                      {:url "kotoba://quickjs-runner/websocket-onerror"
                       :html "<main></main>"})
        generation (:browser.session/page-generation page-session)
        script1 {:script/type :classic
                 :script/url "kotoba://quickjs-runner/websocket-onerror/script1.js"
                 :script/generation generation
                 :script/source
                 (str "var ws = new WebSocket(" (pr-str url) ");"
                      "ws.onerror = function(e) { document.title = (document.title || '') + 'E'; };")}]
    {:session (quickjs-runner/run-script! page-session script1)
     :generation generation}))

(defn- run-noop-script!
  [session generation url-suffix]
  (quickjs-runner/run-script!
   session
   {:script/type :classic
    :script/url (str "kotoba://quickjs-runner/websocket-onerror/" url-suffix)
    :script/generation generation
    :script/source "void 0;"}))

(deftest quickjs-websocket-onerror-fires-exactly-once-across-three-script-tags-test
  (async done
    (let [session-atom (atom nil)
          url-atom (atom nil)
          fail! (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err))))
          cleanup! (fn []
                     (dispose-engine! @session-atom)
                     (done))]
      (-> (get-refused-port!)
          (.then (fn [port]
                   (let [url (str "ws://127.0.0.1:" port "/nope")
                         base-session (build-session url)]
                     (reset! url-atom url)
                     (reset! session-atom base-session)
                     (session/ensure-script-engine! base-session))))
          (.then (fn [ready-session]
                   (reset! session-atom ready-session)
                   (run-script1! ready-session @url-atom)))
          (.then (fn [{:keys [session generation]}]
                   (reset! session-atom session)
                   ;; Real wall-clock time genuinely has to pass for the OS
                   ;; to reject the real connection attempt and Node's real
                   ;; WebSocket to fire its real onerror -- see
                   ;; quickjs_websocket_smoke_test.cljs's namespace
                   ;; docstring for why this is the honest place for it.
                   (-> (wait-ms 500)
                       (.then (fn [_] (run-noop-script! session generation "script2.js"))))))
          (.then (fn [session2]
                   (reset! session-atom session2)
                   (let [title (get-in session2 [:browser.session/page :browser/title])]
                     (println "websocket onerror smoke: document.title after script 2 ->" (pr-str title))
                     (is (= "E" title)
                         (str "expected script 2's snapshot install to fire the real, "
                              "still-registered ws.onerror exactly once for a genuine "
                              "connection-refused failure -- got " (pr-str title))))
                   (run-noop-script! session2 (:browser.session/page-generation session2) "script3.js")))
          (.then (fn [session3]
                   (reset! session-atom session3)
                   (let [title (get-in session3 [:browser.session/page :browser/title])]
                     (println "websocket onerror smoke: document.title after script 3 ->" (pr-str title))
                     (is (= "E" title)
                         (str "onerror must NOT fire a second time on a later script tag now "
                              "that :websocket/errored has recorded it as already delivered -- "
                              "'EE' would mean it silently re-fired -- got " (pr-str title))))))
          (.catch fail!)
          (.finally cleanup!)))))
