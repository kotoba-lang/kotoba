(ns browser.compat.quickjs-websocket-onopen-smoke-test
  "Real page-script proof that `ws.onopen` actually fires, and fires
  EXACTLY ONCE across multiple `<script>` tags, mirroring
  `quickjs_websocket_smoke_test.cljs`'s real echo-server infra (deliberately
  duplicated here rather than shared, matching that file's own precedent
  alongside `demo_smoke_test.cljs`).

  Before this cycle's fix, `ws.onopen` was accepted (`this.onopen = null;`
  in the constructor) but the webapi shim's delivery IIFE never invoked it
  -- the field was permanently dead, exactly the same bug class as
  Notification's missing `close()` and BroadcastChannel's missing
  delivery, both fixed earlier this session. This test proves BOTH halves
  of the fix: `onopen` genuinely fires once real `:websocket/handles`
  state reflects the connection (script 2, the first snapshot install
  after script 1's `new WebSocket(...)`), AND it does NOT fire again on a
  later script tag (script 3) now that
  `quickjs-execution/take-websocket-opened-ids`'s dedup set has recorded
  it as already delivered -- without that dedup, `websocket-snapshot`
  would re-report the SAME still-open connection as newly-opened on every
  later script tag forever, firing `onopen` repeatedly instead of exactly
  once.

  Script 1's `onopen` handler APPENDS a single 'X' onto `document.title`
  rather than overwriting it, specifically so a second, buggy firing would
  be observable as 'XX' instead of 'X'."
  (:require ["net" :as net]
            ["crypto" :as crypto]
            [cljs.test :refer [deftest is async]]
            [kotoba.lang.text :as str]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.net.websocket :as ws]
            [browser.origin :as origin]
            [browser.profile :as profile]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

;; ---------------------------------------------------------------------
;; A minimal, hand-rolled RFC6455 echo server on Node's built-in `net` +
;; `crypto` -- duplicated from quickjs_websocket_smoke_test.cljs. Only the
;; handshake matters here (no data frames are ever sent), but the same
;; server is reused so onopen's delivery timing is proven against a REAL
;; connection, not a mock.
;; ---------------------------------------------------------------------

(def ^:private websocket-magic "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")

(defn- accept-value
  [key]
  (-> (.createHash crypto "sha1")
      (.update (str key websocket-magic))
      (.digest "base64")))

(defn- parse-header-block
  [^js header-text]
  (let [lines (str/split header-text #"\r\n")]
    (reduce (fn [headers line]
              (let [colon (.indexOf line ":")]
                (if (pos? colon)
                  (assoc headers
                         (str/lower (str/trim (subs line 0 colon)))
                         (str/trim (subs line (inc colon))))
                  headers)))
            {}
            (rest lines))))

(defn- handle-socket!
  [^js socket]
  (let [state (atom {:handshaked? false :buffer (js/Buffer.alloc 0)})]
    (.on socket "data"
         (fn [chunk]
           (swap! state update :buffer #(js/Buffer.concat #js [% chunk]))
           (when-not (:handshaked? @state)
             (let [buf (:buffer @state)
                   idx (.indexOf buf "\r\n\r\n")]
               (when (>= idx 0)
                 (let [header-text (.toString (.slice buf 0 idx) "ascii")
                       headers (parse-header-block header-text)
                       accept (accept-value (get headers "sec-websocket-key"))
                       response (str "HTTP/1.1 101 Switching Protocols\r\n"
                                     "Upgrade: websocket\r\n"
                                     "Connection: Upgrade\r\n"
                                     "Sec-WebSocket-Accept: " accept "\r\n"
                                     "\r\n")]
                   (.write socket response "ascii")
                   (swap! state assoc :handshaked? true :buffer (.slice buf (+ idx 4)))))))))
    (.on socket "error" (fn [_] nil))))

(defn- start-echo-server!
  []
  (js/Promise.
   (fn [resolve _reject]
     (let [server (.createServer net (fn [socket] (handle-socket! socket)))]
       (.listen server 0 "127.0.0.1"
                (fn []
                  (let [port (.-port (.address server))]
                    (resolve {:server server
                              :url (str "ws://127.0.0.1:" port "/echo")}))))))))

(defn- stop-echo-server!
  [{:keys [server]}]
  (.close server))

;; ---------------------------------------------------------------------
;; Real three-script proof: opens once, delivers onopen once, never twice.
;; ---------------------------------------------------------------------

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
                      {:url "kotoba://quickjs-runner/websocket-onopen"
                       :html "<main></main>"})
        generation (:browser.session/page-generation page-session)
        script1 {:script/type :classic
                 :script/url "kotoba://quickjs-runner/websocket-onopen/script1.js"
                 :script/generation generation
                 :script/source
                 (str "var ws = new WebSocket(" (pr-str url) ");"
                      "ws.onopen = function(e) { document.title = (document.title || '') + 'X'; };")}]
    {:session (quickjs-runner/run-script! page-session script1)
     :generation generation}))

(defn- run-noop-script!
  [session generation url-suffix]
  (quickjs-runner/run-script!
   session
   {:script/type :classic
    :script/url (str "kotoba://quickjs-runner/websocket-onopen/" url-suffix)
    :script/generation generation
    :script/source "void 0;"}))

(deftest quickjs-websocket-onopen-fires-exactly-once-across-three-script-tags-test
  (async done
    (let [server-atom (atom nil)
          session-atom (atom nil)
          fail! (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err))))
          cleanup! (fn []
                     (dispose-engine! @session-atom)
                     (when-let [server @server-atom] (stop-echo-server! server))
                     (done))]
      (-> (start-echo-server!)
          (.then (fn [server]
                   (reset! server-atom server)
                   (let [base-session (build-session (:url server))]
                     (reset! session-atom base-session)
                     (session/ensure-script-engine! base-session))))
          (.then (fn [ready-session]
                   (reset! session-atom ready-session)
                   (run-script1! ready-session (:url @server-atom))))
          (.then (fn [{:keys [session generation]}]
                   (reset! session-atom session)
                   ;; Real wall-clock time genuinely has to pass for the
                   ;; real handshake to complete -- see
                   ;; quickjs_websocket_smoke_test.cljs's namespace
                   ;; docstring for why this is the honest place for it.
                   (-> (wait-ms 500)
                       (.then (fn [_] (run-noop-script! session generation "script2.js"))))))
          (.then (fn [session2]
                   (reset! session-atom session2)
                   (let [title (get-in session2 [:browser.session/page :browser/title])]
                     (println "websocket onopen smoke: document.title after script 2 ->" (pr-str title))
                     (is (= "X" title)
                         (str "expected script 2's snapshot install to fire the real, "
                              "still-registered ws.onopen exactly once -- got " (pr-str title))))
                   (run-noop-script! session2 (:browser.session/page-generation session2) "script3.js")))
          (.then (fn [session3]
                   (reset! session-atom session3)
                   (let [title (get-in session3 [:browser.session/page :browser/title])]
                     (println "websocket onopen smoke: document.title after script 3 ->" (pr-str title))
                     (is (= "X" title)
                         (str "onopen must NOT fire a second time on a later script tag now that "
                              "take-websocket-opened-ids has recorded it as already delivered -- "
                              "'XX' would mean it silently re-fired -- got " (pr-str title))))))
          (.catch fail!)
          (.finally cleanup!)))))
