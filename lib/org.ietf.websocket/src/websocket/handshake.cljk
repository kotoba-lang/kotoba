(ns websocket.handshake
  "RFC 6455 §4 — the opening handshake, as data.

  The handshake is an HTTP/1.1 upgrade whose only computed field is
  `Sec-WebSocket-Accept`: base64(SHA-1(key + GUID)). This namespace builds
  and validates the header maps and computes that field.

  SHA-1 is injected, not implemented here. `kotoba-lang/hash` owns SHA-1 for
  this workspace and it is written in `.kotoba`, so a `.cljc` leaf cannot
  require it; and duplicating a hash function to avoid one seam is a worse
  trade than the seam. Both host runtimes already ship SHA-1:

    JVM   (fn [bs] (vec (.digest (java.security.MessageDigest/getInstance \"SHA-1\")
                                 (byte-array (map unchecked-byte bs)))))
    node  (fn [bs] (vec (.digest (.update (crypto/createHash \"sha1\")
                                          (js/Uint8Array.from (clj->js bs))))))

  Base64 *is* implemented here. It is 30 lines of table lookup with no
  security surface, and pulling a dependency for it would pin this leaf to
  a runtime — the same reasoning `org-ietf-blake2` gives for having no deps
  at all."
  (:require [kotoba.lang.text :as str]
            [websocket.bytes :as b]))

(def guid
  "RFC 6455 §1.3. Fixed by the specification; it is not a secret and not a
  parameter."
  "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")

;; ------------------------------------------------------------------ base64

(def ^:private b64-alphabet
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")

(defn base64-encode
  "RFC 4648 §4 with padding. `bs` is a Sequential of bytes 0..255."
  [bs]
  (let [bs (vec bs)]
    (str/join
     (for [chunk (partition-all 3 bs)]
       (let [n (count chunk)
             [a b c] (concat chunk [0 0])
             v (+ (* a 65536) (* b 256) c)
             idx (mapv #(bit-and (bit-shift-right v %) 63) [18 12 6 0])
             chars (mapv #(nth b64-alphabet %) idx)]
         (case n
           3 (str/join chars)
           2 (str (str/join (subvec chars 0 3)) "=")
           1 (str (str/join (subvec chars 0 2)) "==")))))))

(defn base64-decode
  "Inverse of `base64-encode`. Returns a vector of bytes, or nil when the
  input is not well-formed base64 — a malformed `Sec-WebSocket-Key` is a
  handshake to reject, not an exception to propagate."
  [s]
  (let [s (str/replace s #"=+$" "")
        idx (into {} (map-indexed (fn [i c] [c i])) b64-alphabet)]
    (when (every? idx s)
      (let [bits (mapcat (fn [c] (let [v (idx c)]
                                   (map #(bit-and (bit-shift-right v %) 1) [5 4 3 2 1 0])))
                         s)]
        (into [] (comp (partition-all 8)
                       (filter #(= 8 (count %)))
                       (map (fn [byte-bits] (reduce (fn [a b] (+ (* a 2) b)) 0 byte-bits))))
              bits)))))

;; -------------------------------------------------------------- accept key

(defn accept-key
  "Compute `Sec-WebSocket-Accept` from the client's `Sec-WebSocket-Key`.

  `sha1` takes a Sequential of bytes and returns one. The key is used as the
  ASCII string the client sent, *not* its decoded bytes — §4.2.2 is explicit
  that the concatenation is of the base64 text with the GUID."
  [key sha1]
  ;; `(map int s)` would do on the JVM and yields a vector of zeros under
  ;; ClojureScript, where a character is a one-character string and `int` of
  ;; one is not its code point. The concatenation is ASCII, so UTF-8 encoding
  ;; is the same bytes and is correct on both.
  (base64-encode (sha1 (b/string->bytes (str key guid)))))

(defn valid-key?
  "§4.1 — `Sec-WebSocket-Key` must be the base64 of exactly 16 bytes.

  Servers routinely skip this and echo whatever arrived. Checking costs
  nothing and turns a class of confused-client bugs into a 400."
  [key]
  (boolean (some-> key base64-decode count (= 16))))

;; ------------------------------------------------------------------ headers

(defn client-request
  "The header map a client sends. `key` is the caller's base64 nonce — this
  namespace does not generate randomness, because randomness is a capability
  and this is a leaf.

  `opts` may carry `:protocols` (a seq for `Sec-WebSocket-Protocol`),
  `:extensions`, and `:origin`."
  [{:keys [host path key protocols extensions origin]
    :or {path "/"}}]
  {:method "GET"
   :path path
   :headers (cond-> {"Host" host
                     "Upgrade" "websocket"
                     "Connection" "Upgrade"
                     "Sec-WebSocket-Key" key
                     "Sec-WebSocket-Version" "13"}
              (seq protocols) (assoc "Sec-WebSocket-Protocol" (str/join ", " protocols))
              (seq extensions) (assoc "Sec-WebSocket-Extensions" (str/join ", " extensions))
              origin (assoc "Origin" origin))})

(defn server-response
  "The 101 a server sends back. `sha1` is as in `accept-key`."
  [{:keys [key protocol]} sha1]
  {:status 101
   :headers (cond-> {"Upgrade" "websocket"
                     "Connection" "Upgrade"
                     "Sec-WebSocket-Accept" (accept-key key sha1)}
              protocol (assoc "Sec-WebSocket-Protocol" protocol))})

(defn- header
  "Header lookup that is case-insensitive, because HTTP/1.1 field names are
  (RFC 9110 §5.1) and a peer that sends `sec-websocket-accept` is correct."
  [headers name]
  (let [want (str/lower name)]
    (some (fn [[k v]] (when (= want (str/lower (str k))) v)) headers)))

(defn validate-server-response
  "Check a server's response against the key the client sent.

  Returns `{:status :ok :protocol s}` or `{:status :error :reason kw}`. The
  reason keywords are contract, as in `websocket.frame`."
  [{:keys [status headers]} key sha1]
  (let [upgrade (header headers "Upgrade")
        connection (header headers "Connection")
        accept (header headers "Sec-WebSocket-Accept")]
    (cond
      (not= 101 status) {:status :error :reason :not-switching-protocols :http-status status}
      (not= "websocket" (some-> upgrade str/lower)) {:status :error :reason :bad-upgrade-header}
      (not (some-> connection str/lower (str/includes? "upgrade"))) {:status :error :reason :bad-connection-header}
      (nil? accept) {:status :error :reason :missing-accept-header}
      (not= accept (accept-key key sha1)) {:status :error :reason :accept-mismatch}
      :else {:status :ok :protocol (header headers "Sec-WebSocket-Protocol")})))
