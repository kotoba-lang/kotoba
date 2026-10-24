(ns libp2p.provider.node
  "The socket. Node `net` sockets driven by this repo's pure `.cljc` protocol
  layers, so a process can dial a real libp2p peer without Kubo, go-libp2p or
  js-libp2p.

  The README of this repo used to end with *what remains after this repo is the
  socket itself*. This namespace is that socket, and it is deliberately thin:
  it owns the file descriptor, the buffer and the clock, and nothing else.
  `libp2p.multistream`, `noise.core` and `protobuf.wire` own every decision.

  ## The libp2p Noise profile is not plain Noise XX

  Three things sit on top of the Noise pattern, and a dialer that implements
  only the pattern is refused by every real peer:

  1. **2-byte big-endian length prefix** on each handshake message.
  2. A **`NoiseHandshakePayload`** protobuf carried inside messages 2 and 3,
     binding the peer's long-term identity key to the ephemeral Noise static.
  3. The signature in that payload is over
     `\"noise-libp2p-static-key:\" || noise_static_public`, **not** over the
     payload itself.

  The prologue is empty. The suite is `Noise_XX_25519_ChaChaPoly_SHA256` —
  SHA256, not this workspace's BLAKE2s default, so `noise.provider.noble/ports`
  must be asked for `:sha256` on both the ports and the suite.

  ## What a timeout returns

  `read-until!` throws on timeout, on socket error and on a peer that closed
  with nothing buffered. It never resolves to nil. A dialer that returned nil
  for all three would make *could not measure* and *measured an empty answer*
  the same value, which is the failure mode ADR-2608136000 is about.

      (require '[libp2p.provider.node :as node])
      (node/dial! {:host \"104.131.131.82\" :port 4001})
      ;; => Promise of {:done? true :remote-static-len 32 :remote-identity {…}}"
  (:require ["net" :as net]
            ["@noble/curves/ed25519.js" :refer [ed25519]]
            [kotoba.lang.text :as str]
            [libp2p.multistream :as ms]
            [noise.core :as noise]
            [noise.provider.noble :as noble]
            [protobuf.wire :as pb]))

;; ── bytes ─────────────────────────────────────────────────────────────────

(defn u8->vec [u8] (vec (js/Array.from u8)))
(defn vec->u8 [v] (js/Uint8Array.from (clj->js (vec v))))
(defn- utf8 [s] (u8->vec (.encode (js/TextEncoder.) s)))
(defn- be16 [n] [(bit-and (bit-shift-right n 8) 0xff) (bit-and n 0xff)])

(defn- ed-secret-key
  "@noble renamed this between majors. Pick whichever exists rather than
  pinning a version here — the caller's lockfile owns the version."
  []
  (let [u (.-utils ed25519)]
    (cond
      (fn? (.-randomSecretKey u)) (.randomSecretKey u)
      (fn? (.-randomPrivateKey u)) (.randomPrivateKey u)
      :else (throw (js/Error. "no ed25519 secret-key generator on this @noble build")))))

;; ── libp2p protobuf schemas ───────────────────────────────────────────────

(def public-key-schema
  "libp2p `crypto.pb.PublicKey`. `:key-type` is the KeyType enum:
  RSA=0, Ed25519=1, Secp256k1=2, ECDSA=3."
  {1 {:name :key-type :type :uint64}
   2 {:name :data :type :bytes}})

(def handshake-payload-schema
  "libp2p `pb.NoiseHandshakePayload`."
  {1 {:name :identity-key :type :bytes}
   2 {:name :identity-sig :type :bytes}
   3 {:name :extensions :type :bytes}})

(def ^:const noise-sig-prefix "noise-libp2p-static-key:")

;; ── socket ────────────────────────────────────────────────────────────────

(defn connect!
  "Open a TCP socket. Returns `{:sock :inbox :state}`; `inbox` accumulates every
  received octet and `state` records the first error and the close."
  [host port]
  (let [inbox (atom [])
        state (atom {})
        sock (.connect net #js {:host host :port port})]
    (.on sock "data" (fn [buf] (swap! inbox into (u8->vec buf))))
    (.on sock "error" (fn [e] (swap! state assoc :error (.-message e))))
    (.on sock "close" (fn [] (swap! state assoc :closed true)))
    {:sock sock :inbox inbox :state state}))

(defn write! [{:keys [sock]} bytes] (.write sock (vec->u8 bytes)))
(defn close! [{:keys [sock]}] (.destroy sock))

(defn read-until!
  "Poll until `pred` returns truthy on the buffered octets. Rejects — never
  resolves nil — on timeout, socket error, or a peer that closed with an empty
  buffer, so the three are distinguishable at the call site."
  [{:keys [inbox state]} pred timeout-ms label]
  (js/Promise.
   (fn [resolve reject]
     (let [t0 (js/Date.now)]
       (letfn [(tick []
                 ;; `pred` parses octets the peer chose and throws on a
                 ;; malformed frame. Without this catch the throw escapes the
                 ;; promise chain and surfaces as an unhandled rejection with a
                 ;; stack trace instead of a stated reason — the caller sees a
                 ;; crash where it should see a verdict. Polling must also stop
                 ;; here: a rejected promise whose loop keeps running holds the
                 ;; process open long after the answer is known.
                 (let [r (try {:ok (pred @inbox)}
                              (catch :default e {:err (or (.-message e) (str e))}))]
                   (cond
                     (:err r) (reject (js/Error. (str label ": " (:err r))))
                     (:ok r) (resolve (:ok r))
                     :else
                     (let [s @state]
                       (cond
                         (:error s)
                         (reject (js/Error. (str label ": socket error: " (:error s))))
                         (and (:closed s) (empty? @inbox))
                         (reject (js/Error. (str label ": peer closed with nothing buffered")))
                         (> (- (js/Date.now) t0) timeout-ms)
                         (reject (js/Error. (str label ": timeout after " timeout-ms
                                                 "ms, buffered=" (count @inbox) " octets")))
                         :else (js/setTimeout tick 20))))))]
         (tick))))))

(defn take-ms-message!
  "Pred: one complete multistream message, consumed off `inbox`."
  [inbox]
  (fn [bs]
    (let [{:keys [message rest error detail]} (ms/decode bs)]
      (when error (throw (js/Error. (str "multistream " error ": " detail))))
      (when message (reset! inbox rest) message))))

(defn take-noise-frame!
  "Pred: one 2-byte big-endian length-prefixed Noise frame."
  [inbox]
  (fn [bs]
    (let [bs (vec bs)]
      (when (>= (count bs) 2)
        (let [n (+ (* 256 (nth bs 0)) (nth bs 1))]
          (when (>= (count bs) (+ 2 n))
            (let [frame (subvec bs 2 (+ 2 n))]
              (reset! inbox (subvec bs (+ 2 n)))
              frame)))))))

(defn write-noise! [conn payload]
  (write! conn (into (be16 (count payload)) payload)))

;; ── the libp2p identity payload ───────────────────────────────────────────

(defn handshake-payload
  "Our `NoiseHandshakePayload`: the identity key, and a signature over the
  prefix concatenated with the Noise static public key."
  [ed-sk ed-pub noise-static-pub]
  (let [to-sign (into (utf8 noise-sig-prefix) noise-static-pub)
        sig (u8->vec (.sign ed25519 (vec->u8 to-sign) ed-sk))]
    (pb/encode handshake-payload-schema
               {:identity-key (pb/encode public-key-schema {:key-type 1 :data ed-pub})
                :identity-sig sig})))

(defn parse-remote-payload
  "Read the peer's identity out of their payload. Returns `{:parse-error …}`
  rather than throwing — a malformed payload is a fact about the peer."
  [octets]
  (try
    (let [p (pb/decode handshake-payload-schema octets)
          k (some->> (:identity-key p) (pb/decode public-key-schema))]
      {:key-type (:key-type k)
       :identity-key-len (count (:data k))
       :identity-sig-len (count (:identity-sig p))})
    (catch :default e {:parse-error (.-message e)})))

;; ── dial ──────────────────────────────────────────────────────────────────

(defn dial!
  "Dial `host`:`port`, negotiate `/noise`, run the libp2p Noise XX handshake and
  return a Promise of the result. Closes the socket either way.

  `opts`: `:host` `:port` `:timeout-ms` (default 25000)."
  [{:keys [host port timeout-ms] :or {timeout-ms 25000}}]
  (let [conn (connect! host port)
        st (noise/suite (noble/ports {:hash :sha256}) {:hash :sha256})
        stat (noise/keypair st)
        ed-sk (ed-secret-key)
        ed-pub (u8->vec (.getPublicKey ed25519 ed-sk))
        fin (fn [r] (close! conn) r)]
    (-> (js/Promise.resolve)
        (.then (fn []
                 (write! conn (:out (ms/dialer-start (ms/dialer ["/noise"]))))
                 (read-until! conn (take-ms-message! (:inbox conn)) timeout-ms "ms-header")))
        (.then (fn [_hdr]
                 (read-until! conn (take-ms-message! (:inbox conn)) timeout-ms "ms-proto")))
        (.then (fn [proto]
                 (when-not (= "/noise" (str/trim proto))
                   (throw (js/Error. (str "peer refused /noise, offered " (pr-str proto)))))
                 (let [i (noise/initiator {:suite st :s stat :pattern :XX :prologue []})
                       [i m1] (noise/write-message i [])]
                   (write-noise! conn m1)
                   (-> (read-until! conn (take-noise-frame! (:inbox conn)) timeout-ms "noise-msg2")
                       (.then (fn [m2] [i m2]))))))
        (.then (fn [[i m2]]
                 (let [[i payload] (noise/read-message i m2)
                       remote (parse-remote-payload payload)
                       [i m3] (noise/write-message
                               i (handshake-payload ed-sk ed-pub (:pub stat)))]
                   (write-noise! conn m3)
                   {:done? (noise/done? i)
                    :protocol (noise/protocol-name st :XX)
                    :remote-static-len (count (noise/remote-static i))
                    :handshake-hash-len (count (noise/handshake-hash i))
                    :remote-identity remote})))
        (.then fin)
        (.catch (fn [e] (fin nil) (throw e))))))
