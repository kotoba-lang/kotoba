(ns browser.compat.quickjs-websocket-onclose-smoke-test
  "Real page-script proof that a genuine PEER-INITIATED `ws.onclose` fires
  EXACTLY ONCE across multiple `<script>` tags, mirroring
  `quickjs_websocket_onopen_smoke_test.cljs`'s real-connection infra.

  Before this cycle's fix, `browser.net.websocket`'s real `closed?` atom
  (set true by a real `onClose`/`onclose` event on either backend) never
  resets once true, and `quickjs-execution/websocket-connection-snapshot`
  recomputed the plain, JS-visible `:closed` key from that raw atom on
  EVERY script tag with zero dedup -- unlike the `:opened`/`:error`
  sibling fields fixed the two cycles before this one. A real peer-
  initiated close (this test's server sends an UNSOLICITED real RFC6455
  close frame right after the handshake, simulating a server closing the
  connection on its own -- as opposed to a `ws.close()` the SAME script
  already called, which the webapi shim flips `readyState` for locally)
  would fire `ws.onclose` on EVERY later `<script>` tag forever instead
  of exactly once. This test proves BOTH halves of the fix: a real close
  genuinely reaches `ws.onclose` on the first snapshot install after it
  is observed (script 2), AND does NOT fire again on a later script tag
  (script 3) now that `:websocket/closed`'s dedup set has recorded it as
  already delivered -- even though the real underlying `closed?` atom
  still reports `true` forever."
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
;; A minimal, hand-rolled RFC6455 server on Node's built-in `net` +
;; `crypto` -- duplicated from quickjs_websocket_smoke_test.cljs, plus a
;; real close-frame WRITER (that file only ever ECHOES a client-sent
;; close, never initiates one) so this test can simulate a genuine,
;; unsolicited, server-initiated close.
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

(defn- write-frame!
  [^js socket opcode ^js payload]
  (let [len (.-length payload)
        header (cond
                 (< len 126)
                 (js/Buffer.from #js [(bit-or 0x80 opcode) len])

                 (< len 65536)
                 (let [b (js/Buffer.alloc 4)]
                   (.writeUInt8 b (bit-or 0x80 opcode) 0)
                   (.writeUInt8 b 126 1)
                   (.writeUInt16BE b len 2)
                   b)

                 :else
                 (let [b (js/Buffer.alloc 10)]
                   (.writeUInt8 b (bit-or 0x80 opcode) 0)
                   (.writeUInt8 b 127 1)
                   (.writeBigUInt64BE b (js/BigInt len) 2)
                   b))]
    (.write socket (js/Buffer.concat #js [header payload]))))

(defn- write-close-frame!
  "Write a real, unsolicited RFC6455 close frame (opcode 8): a 2-byte
   big-endian status code followed by a UTF-8 reason -- the genuine wire
   format a real peer-initiated close uses, not a mock."
  [^js socket code reason]
  (let [code-buf (js/Buffer.alloc 2)
        _ (.writeUInt16BE code-buf code 0)
        reason-buf (js/Buffer.from reason "utf8")]
    (write-frame! socket 8 (js/Buffer.concat #js [code-buf reason-buf]))))

(defn- handle-socket!
  "Performs the real handshake, then immediately sends a real, unsolicited
   close frame -- simulating a server that closes the connection on its
   own, the scenario this bug is specifically about."
  [^js socket]
  (let [state (atom {:handshaked? false :buffer (js/Buffer.alloc 0)})]
    (.on socket "data"
         (fn [chunk]
           (swap! state update :buffer #(js/Buffer.concat #js [% chunk]))
           (if (:handshaked? @state)
             ;; Any post-handshake byte is the client's own RFC6455 close-
             ;; frame echo (a real WebSocket client always answers a peer's
             ;; close frame with its own before the connection is really
             ;; done). A real close ISN'T observable client-side as
             ;; `ws.onclose` merely from receiving a close FRAME -- Node's
             ;; real WebSocket only fires it once the underlying TCP
             ;; connection actually ends, exactly like a real server would
             ;; do after completing the close handshake.
             (.end socket)
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
                   (swap! state assoc :handshaked? true :buffer (.slice buf (+ idx 4)))
                   (write-close-frame! socket 1000 "server closing"))))))
    (.on socket "error" (fn [_] nil)))))

(defn- start-close-server!
  []
  (js/Promise.
   (fn [resolve _reject]
     (let [server (.createServer net (fn [socket] (handle-socket! socket)))]
       (.listen server 0 "127.0.0.1"
                (fn []
                  (let [port (.-port (.address server))]
                    (resolve {:server server
                              :url (str "ws://127.0.0.1:" port "/close-me")}))))))))

(defn- stop-close-server!
  [{:keys [server]}]
  (.close server))

;; ---------------------------------------------------------------------
;; Real three-script proof.
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
                      {:url "kotoba://quickjs-runner/websocket-onclose"
                       :html "<main></main>"})
        generation (:browser.session/page-generation page-session)
        script1 {:script/type :classic
                 :script/url "kotoba://quickjs-runner/websocket-onclose/script1.js"
                 :script/generation generation
                 :script/source
                 (str "var ws = new WebSocket(" (pr-str url) ");"
                      "ws.onclose = function(e) { document.title = (document.title || '') + 'C'; };")}]
    {:session (quickjs-runner/run-script! page-session script1)
     :generation generation}))

(defn- run-noop-script!
  [session generation url-suffix]
  (quickjs-runner/run-script!
   session
   {:script/type :classic
    :script/url (str "kotoba://quickjs-runner/websocket-onclose/" url-suffix)
    :script/generation generation
    :script/source "void 0;"}))

(deftest quickjs-websocket-onclose-fires-exactly-once-across-three-script-tags-test
  (async done
    (let [server-atom (atom nil)
          session-atom (atom nil)
          fail! (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err))))
          cleanup! (fn []
                     (dispose-engine! @session-atom)
                     (when-let [server @server-atom] (stop-close-server! server))
                     (done))]
      (-> (start-close-server!)
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
                   ;; real close frame to arrive and Node's real WebSocket
                   ;; to fire its real onclose -- see
                   ;; quickjs_websocket_smoke_test.cljs's namespace
                   ;; docstring for why this is the honest place for it.
                   (-> (wait-ms 500)
                       (.then (fn [_] (run-noop-script! session generation "script2.js"))))))
          (.then (fn [session2]
                   (reset! session-atom session2)
                   (let [title (get-in session2 [:browser.session/page :browser/title])]
                     (println "websocket onclose smoke: document.title after script 2 ->" (pr-str title))
                     (is (= "C" title)
                         (str "expected script 2's snapshot install to fire the real, "
                              "still-registered ws.onclose exactly once for a genuine "
                              "peer-initiated close -- got " (pr-str title))))
                   (run-noop-script! session2 (:browser.session/page-generation session2) "script3.js")))
          (.then (fn [session3]
                   (reset! session-atom session3)
                   (let [title (get-in session3 [:browser.session/page :browser/title])]
                     (println "websocket onclose smoke: document.title after script 3 ->" (pr-str title))
                     (is (= "C" title)
                         (str "onclose must NOT fire a second time on a later script tag now "
                              "that :websocket/closed has recorded it as already delivered -- "
                              "'CC' would mean it silently re-fired -- got " (pr-str title))))))
          (.catch fail!)
          (.finally cleanup!)))))
