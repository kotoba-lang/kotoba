(ns ssh.connection
  "The SSH connection protocol (RFC 4254): opening a `session` channel and
  running a command over it. After userauth the client sends CHANNEL_OPEN, the
  server confirms, the client sends a `exec`/`shell` CHANNEL_REQUEST, and the
  server answers with CHANNEL_SUCCESS, streams CHANNEL_DATA, then an exit-status
  request and CHANNEL_EOF / CHANNEL_CLOSE.

  Pure byte assembly reusing ssh.transport's string/uint32; every message rides
  the encrypted record layer (ssh.record). This is the wire contract the aiueos
  kernel mirrors to turn an authenticated login into an actual command session."
  (:require [ssh.transport :as t]))

(def msg-channel-open 90)
(def msg-channel-open-confirmation 91)
(def msg-channel-open-failure 92)
(def msg-channel-window-adjust 93)
(def msg-channel-data 94)
(def msg-channel-eof 96)
(def msg-channel-close 97)
(def msg-channel-request 98)
(def msg-channel-success 99)
(def msg-channel-failure 100)

(defn- s [str-val] (t/string-bytes (t/str->bytes str-val)))
(defn- be32 [b o] (+ (* 16777216 (nth b o)) (* 65536 (nth b (+ o 1)))
                     (* 256 (nth b (+ o 2))) (nth b (+ o 3))))

;; ── client -> server ────────────────────────────────────────────────────────

(defn channel-open-payload
  "CHANNEL_OPEN: string type, uint32 sender-channel, uint32 window, uint32 max-packet."
  [chan-type sender-channel window max-packet]
  (-> [msg-channel-open]
      (into (s chan-type))
      (into (t/u32 sender-channel))
      (into (t/u32 window))
      (into (t/u32 max-packet))))

(defn channel-request-exec-payload
  "CHANNEL_REQUEST exec: uint32 recipient, string \"exec\", boolean want-reply, string command."
  [recipient want-reply command]
  (-> [msg-channel-request]
      (into (t/u32 recipient))
      (into (s "exec"))
      (conj (if want-reply 1 0))
      (into (s command))))

;; ── server -> client ────────────────────────────────────────────────────────

(defn channel-open-confirmation-payload
  "CHANNEL_OPEN_CONFIRMATION: uint32 recipient, uint32 sender, uint32 window, uint32 max-packet."
  [recipient sender window max-packet]
  (-> [msg-channel-open-confirmation]
      (into (t/u32 recipient))
      (into (t/u32 sender))
      (into (t/u32 window))
      (into (t/u32 max-packet))))

(defn channel-success-payload
  "CHANNEL_SUCCESS: uint32 recipient."
  [recipient]
  (into [msg-channel-success] (t/u32 recipient)))

(defn channel-data-payload
  "CHANNEL_DATA: uint32 recipient, string data. `data` is a byte vector."
  [recipient data]
  (-> [msg-channel-data]
      (into (t/u32 recipient))
      (into (t/string-bytes data))))

(defn channel-exit-status-payload
  "CHANNEL_REQUEST exit-status: uint32 recipient, string \"exit-status\",
  boolean FALSE, uint32 status."
  [recipient status]
  (-> [msg-channel-request]
      (into (t/u32 recipient))
      (into (s "exit-status"))
      (conj 0)
      (into (t/u32 status))))

(defn channel-eof-payload [recipient] (into [msg-channel-eof] (t/u32 recipient)))
(defn channel-close-payload [recipient] (into [msg-channel-close] (t/u32 recipient)))

;; ── parsers (server admits the client's messages) ───────────────────────────

(defn parse-channel-open
  "Return {:type :sender-channel :window :max-packet} or nil."
  [payload]
  (when (= msg-channel-open (first payload))
    (let [b (vec (rest payload))
          n (be32 b 0)
          type (apply str (map char (subvec b 4 (+ 4 n))))
          rest-b (subvec b (+ 4 n))]
      {:type type
       :sender-channel (be32 rest-b 0)
       :window (be32 rest-b 4)
       :max-packet (be32 rest-b 8)})))

(defn parse-channel-request
  "Return {:recipient :request-type :want-reply :command} or nil. `command` is
  present only for exec."
  [payload]
  (when (= msg-channel-request (first payload))
    (let [b (vec (rest payload))
          recipient (be32 b 0)
          rb (subvec b 4)
          n (be32 rb 0)
          req-type (apply str (map char (subvec rb 4 (+ 4 n))))
          after (subvec rb (+ 4 n))
          want-reply (= 1 (first after))]
      (merge {:recipient recipient :request-type req-type :want-reply want-reply}
             (when (= "exec" req-type)
               (let [cb (vec (rest after))
                     cn (be32 cb 0)]
                 {:command (apply str (map char (subvec cb 4 (+ 4 cn))))}))))))

(defn parse-channel-data
  "Return {:recipient :data} or nil."
  [payload]
  (when (= msg-channel-data (first payload))
    (let [b (vec (rest payload))
          recipient (be32 b 0)
          n (be32 b 4)]
      {:recipient recipient :data (subvec b 8 (+ 8 n))})))
