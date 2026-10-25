(ns nostr.relay.transport
  "A real, working WebSocket transport for nostr.relay (NIP-01) — hand-rolled
  RFC 6455 handshake and frame parsing/encoding over Node's raw node:net,
  NOT the `ws` npm package. Follows the exact discipline
  ADR-2607161817/ADR-2607162135 (kotoba-lang/dtn, kotoba-lang/io-libp2p)
  established for this workspace's transport layers:

  .cljs, NOT .cljc — this namespace requires real socket I/O, so it only
  runs under a Node.js-hosted ClojureScript runtime (nbb in this repo). It
  is a pure CONSUMER of nostr.relay/nostr.event (unmodified, .cljc, zero
  I/O) — every actual protocol decision (event validation, storage,
  subscription filter matching) still happens there; this namespace only
  moves bytes and tracks which live socket owns which subscription.

  RFC 6455 SCOPE: text frames only (Nostr is JSON-over-text, binary frames
  are out of scope), close/ping/pong control frames handled, per-frame
  masking required and verified for client->server frames (RFC 6455 §5.1:
  a server MUST close the connection upon receiving an unmasked frame —
  this implementation drops the connection on that condition), server->
  client frames sent unmasked (also per spec — only client frames are
  masked). No permessage-deflate extension, no fragmented-message
  reassembly across multiple continuation frames (single-frame messages
  only — real Nostr clients send each EVENT/REQ/CLOSE as one text frame,
  well under any reasonable single-frame size limit for this repo's scope)."
  (:require ["node:net" :as net]
            ["node:crypto" :as ncrypto]
            [kotoba.lang.text :as str]
            [kotobase.local :as local]
            [nostr.event :as event]
            [nostr.json :as json]
            [nostr.relay :as relay]))

(def ^:private ws-guid "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")

;; ------------------------------------------------------------- frame codec

(defn- unmask!
  "XOR-unmask `payload-buf` (a Buffer) in place against the 4-byte
  `mask-bytes` vector, per RFC 6455 §5.3."
  [payload-buf mask-bytes]
  (dotimes [i (.-length payload-buf)]
    (.writeUInt8 payload-buf
                 (bit-xor (.readUInt8 payload-buf i) (nth mask-bytes (mod i 4)))
                 i))
  payload-buf)

(defn try-decode-frame
  "buf: a Buffer possibly containing 0, 1, or more complete WS frames.
  Returns {:fin? :opcode :payload (Buffer, unmasked) :consumed N} for the
  first complete frame in buf, or nil if buf doesn't yet contain one
  complete frame (caller should wait for more `data`)."
  [buf]
  (when (>= (.-length buf) 2)
    (let [b0 (.readUInt8 buf 0)
          b1 (.readUInt8 buf 1)
          fin? (not (zero? (bit-and b0 0x80)))
          opcode (bit-and b0 0x0f)
          masked? (not (zero? (bit-and b1 0x80)))
          len0 (bit-and b1 0x7f)
          [payload-len header-extra]
          (cond
            (< len0 126) [len0 0]
            (= len0 126) (when (>= (.-length buf) 4) [(.readUInt16BE buf 2) 2])
            :else (when (>= (.-length buf) 10) [(js/Number (.readBigUInt64BE buf 2)) 8]))]
      (when payload-len
        (let [mask-offset (+ 2 header-extra)
              mask-len (if masked? 4 0)
              payload-offset (+ mask-offset mask-len)
              total (+ payload-offset payload-len)]
          (when (>= (.-length buf) total)
            (let [mask-bytes (when masked?
                                [(.readUInt8 buf mask-offset)
                                 (.readUInt8 buf (+ mask-offset 1))
                                 (.readUInt8 buf (+ mask-offset 2))
                                 (.readUInt8 buf (+ mask-offset 3))])
                  payload (.slice buf payload-offset total)]
              (when masked? (unmask! payload mask-bytes))
              {:fin? fin? :opcode opcode :masked? masked? :payload payload :consumed total})))))))

(defn- encode-len-bytes [len]
  (cond
    (< len 126) (js/Buffer.from #js [len])
    (< len 65536) (let [b (js/Buffer.alloc 3)]
                    (.writeUInt8 b 126 0) (.writeUInt16BE b len 1) b)
    :else (let [b (js/Buffer.alloc 9)]
            (.writeUInt8 b 127 0) (.writeBigUInt64BE b (js/BigInt len) 1) b)))

(defn encode-frame
  "Server->client frames are unmasked, per RFC 6455 §5.1."
  [opcode payload-buf]
  (let [b0 (bit-or 0x80 opcode) ;; FIN=1
        header (js/Buffer.concat #js [(js/Buffer.from #js [b0]) (encode-len-bytes (.-length payload-buf))])]
    (js/Buffer.concat #js [header payload-buf])))

(defn encode-text-frame [s] (encode-frame 0x1 (js/Buffer.from s "utf8")))
(defn encode-close-frame ([] (encode-frame 0x8 (js/Buffer.alloc 0)))
  ([payload] (encode-frame 0x8 payload)))
(defn encode-pong-frame [payload] (encode-frame 0xA payload))

;; ---------------------------------------------------------------- handshake

(defn- parse-request-headers
  "Raw ASCII header text (request line + header lines, no body, no trailing
  blank line) -> {lower-case-header-name value}."
  [header-text]
  (into {}
        (keep (fn [line]
                (when-let [idx (str/index-of line ":")]
                  [(str/lower (str/trim (subs line 0 idx)))
                   (str/trim (subs line (inc idx)))])))
        (rest (str/split header-text #"\r\n"))))

(defn accept-key
  "RFC 6455 §1.3: base64(sha1(client-key + magic guid))."
  [client-key]
  (-> (.createHash ncrypto "sha1")
      (.update (str client-key ws-guid))
      (.digest "base64")))

;; --------------------------------------------------------------- connection

(defn- send! [socket buf] (.write socket buf))

(defn- send-message! [socket msg] (send! socket (encode-text-frame (json/encode msg))))

(defn- fan-out-event!
  "Push `ev` as an EVENT message to every open subscription (across every
  connection, including the one that submitted it — Nostr relays echo an
  accepted event back to the submitter's own matching subscriptions too)
  whose filters match it."
  [conns-atom ev]
  (doseq [[_id {:keys [socket subs]}] @conns-atom]
    (doseq [[sub-id filters] subs]
      (when (some #(event/matches-filter? ev %) filters)
        (send-message! socket (relay/event-message sub-id ev))))))

(defn- handle-text-message!
  [ctx conns-atom conn-id socket text]
  (let [parsed (try (json/parse text)
                     (catch :default _ ::parse-error))]
    (if (= parsed ::parse-error)
      (send-message! socket (relay/notice-message "invalid JSON"))
      (let [{:keys [type] :as result} (relay/handle-client-message ctx parsed)]
        (case type
          :event-result
          (do (send-message! socket (:ok-message result))
              (when-let [ev (:accepted-event result)]
                (fan-out-event! conns-atom ev)))

          :req-result
          (do (swap! conns-atom assoc-in [conn-id :subs (:sub-id result)] (:filters result))
              (doseq [m (:messages result)] (send-message! socket m)))

          :close-result
          (do (swap! conns-atom update conn-id
                     (fn [c] (update c :subs dissoc (:sub-id result))))
              (send-message! socket (:message result)))

          :notice
          (send-message! socket (:message result)))))))

(defn- process-frames!
  "Drain every complete WS frame currently sitting in @buf-atom, dispatching
  each. Leaves any trailing partial frame in @buf-atom for the next `data`
  event."
  [ctx conns-atom conn-id socket buf-atom]
  (loop []
    (when-let [{:keys [opcode payload masked? consumed]} (try-decode-frame @buf-atom)]
      (swap! buf-atom #(.slice % consumed))
      (cond
        ;; RFC 6455 §5.1: server MUST close the connection upon receiving an
        ;; unmasked frame from a client.
        (not masked?)
        (do (send! socket (encode-close-frame))
            (.destroy socket))

        (= opcode 0x1) ;; text
        (do (handle-text-message! ctx conns-atom conn-id socket (.toString payload "utf8"))
            (recur))

        (= opcode 0x8) ;; close
        (do (send! socket (encode-close-frame))
            (.end socket))

        (= opcode 0x9) ;; ping
        (do (send! socket (encode-pong-frame payload))
            (recur))

        (= opcode 0xA) ;; pong
        (recur)

        :else (recur)))))

(defn- try-handshake!
  [conns-atom conn-id socket buf-atom handshake-done?-atom ctx]
  (let [buf @buf-atom
        text (.toString buf "latin1")
        idx (str/index-of text "\r\n\r\n")]
    (when idx
      (let [headers (parse-request-headers (subs text 0 idx))
            ws-key (get headers "sec-websocket-key")
            remaining (.slice buf (+ idx 4))]
        (if-not ws-key
          (do (send! socket (js/Buffer.from "HTTP/1.1 400 Bad Request\r\n\r\n" "ascii"))
              (.destroy socket))
          (do
            (send! socket (js/Buffer.from
                           (str "HTTP/1.1 101 Switching Protocols\r\n"
                                "Upgrade: websocket\r\n"
                                "Connection: Upgrade\r\n"
                                "Sec-WebSocket-Accept: " (accept-key ws-key) "\r\n\r\n")
                           "ascii"))
            (reset! handshake-done?-atom true)
            (reset! buf-atom remaining)
            (when (pos? (.-length remaining))
              (process-frames! ctx conns-atom conn-id socket buf-atom))))))))

;; ------------------------------------------------------------------ server

(defn start-relay!
  "opts: {:port int, :store IStore (optional, defaults to a fresh
  kotobase.local/local-store)}. Returns a node-handle map:
    {:net-server <node:net Server> :ctx {:store ...} :conns (atom {...})}
  :conns maps a connection-id to {:socket <net.Socket> :subs {sub-id filters}}
  — used both to fan out newly-accepted events to every matching open
  subscription (see fan-out-event!) and (mainly for tests/introspection) to
  see who's currently subscribed to what."
  [{:keys [port store]}]
  (let [ctx {:store (or store (local/local-store))}
        conns-atom (atom {})
        next-id (atom 0)
        server (net/createServer
                (fn [socket]
                  (let [conn-id (swap! next-id inc)
                        buf-atom (atom (js/Buffer.alloc 0))
                        handshake-done?-atom (atom false)]
                    (swap! conns-atom assoc conn-id {:socket socket :subs {}})
                    (.on socket "data"
                         (fn [chunk]
                           (swap! buf-atom (fn [b] (js/Buffer.concat #js [b chunk])))
                           (if @handshake-done?-atom
                             (process-frames! ctx conns-atom conn-id socket buf-atom)
                             (try-handshake! conns-atom conn-id socket buf-atom
                                            handshake-done?-atom ctx))))
                    (.on socket "close" (fn [] (swap! conns-atom dissoc conn-id)))
                    (.on socket "error" (fn [_e] (swap! conns-atom dissoc conn-id))))))]
    (.on server "error" (fn [e] (println "nostr.relay.transport: server error" (.-message e))))
    (.listen server port)
    {:net-server server :ctx ctx :conns conns-atom}))

(defn stop-relay!
  "Returns a Promise resolved once the server has actually closed (safe to
  re-start-relay! on the same port right after)."
  [{:keys [net-server conns]}]
  (js/Promise.
   (fn [resolve _reject]
     (doseq [[_id {:keys [socket]}] @conns] (.destroy socket))
     (reset! conns {})
     (if net-server
       (.close net-server (fn [_err] (resolve true)))
       (resolve true)))))
