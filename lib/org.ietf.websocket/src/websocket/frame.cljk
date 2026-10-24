(ns websocket.frame
  "RFC 6455 §5 framing — the byte layer of a WebSocket, in portable Clojure,
  with no dependencies.

  Why this exists as its own library: two nodes in this workspace
  (`inga-node`, `torihiki-node`) reach for the npm package `ws` to get one
  thing — turning a payload into RFC 6455 frames and back. `ws` is a Node
  addon boundary, so the moment a build targets the JVM or kotoba-WASM the
  framing is simply gone. Framing is arithmetic over bytes; there is no
  reason for it to be host-shaped.

  Bytes are `Sequential` collections of ints in 0..255, and every function
  here returns vectors of the same. That is the one representation both
  runtimes agree on without typed arrays, and it keeps a frame a *value* —
  comparable, printable, and usable as a test fixture. Callers holding a
  `byte[]` or a `Uint8Array` convert at their own edge.

  Errors are returned, never thrown: `decode` answers a map whose `:status`
  is `:ok`, `:incomplete`, or `:error`. An `:error` carries a keyword
  `:reason` naming the RFC rule that rejected the frame, so a caller can
  branch on the rule rather than on a message string. The reason keywords
  are part of this namespace's contract; renaming one is a breaking change."
  (:require [websocket.bytes :as b]))

;; ---------------------------------------------------------------- opcodes

(def opcode->kind
  {0x0 :continuation
   0x1 :text
   0x2 :binary
   0x8 :close
   0x9 :ping
   0xA :pong})

(def kind->opcode (into {} (map (fn [[k v]] [v k])) opcode->kind))

(defn control-opcode?
  "RFC 6455 §5.5 — opcodes 0x8..0xF are control frames."
  [op]
  (>= op 0x8))

(defn reserved-opcode?
  "0x3..0x7 and 0xB..0xF are reserved (§5.2) and must be rejected."
  [op]
  (not (contains? opcode->kind op)))

;; ------------------------------------------------------------------ masking

(defn mask-payload
  "RFC 6455 §5.3 — XOR each payload byte with `key[i mod 4]`.

  The transformation is its own inverse, so this is both the masking and the
  unmasking step. `key` is 4 bytes."
  [key payload]
  (let [k (vec key)]
    (into [] (map-indexed (fn [i b] (bit-xor b (nth k (mod i 4))))) payload)))

;; ------------------------------------------------------------------ encode

(defn- length-bytes
  "§5.2 — the minimal encoding of a payload length. Lengths under 126 ride in
  the 7-bit field; 126 selects a 16-bit extension; 127 a 64-bit one. Using a
  wider field than needed is a protocol error on receipt, so it must not be
  produced here either."
  [n]
  (cond
    (< n 126) [[n] []]
    (<= n 0xFFFF) [[126] [(bit-and (bit-shift-right n 8) 0xFF) (bit-and n 0xFF)]]
    :else [[127] (let [hi (quot n 4294967296)
                       lo (rem n 4294967296)]
                   ;; Division, not shifts. ClojureScript takes a shift count
                   ;; mod 32, so `(unsigned-bit-shift-right n 48)` silently
                   ;; becomes `>>> 16` and a 64 KiB frame announces its length
                   ;; as 0x0001000000010000. The JVM computes it correctly, so
                   ;; a one-runtime suite reports this as green.
                   (mapv #(bit-and % 0xFF)
                         [(quot hi 16777216) (quot hi 65536) (quot hi 256) hi
                          (quot lo 16777216) (quot lo 65536) (quot lo 256) lo]))]))

(defn encode
  "Serialize one frame to a vector of bytes.

  Options:

    :opcode    keyword from `kind->opcode`, or an int. Required.
    :payload   Sequential of bytes 0..255. Defaults to empty.
    :fin?      defaults to true.
    :mask-key  4 bytes. When present the frame is masked (§5.3). A client
               MUST set this on every frame it sends; a server MUST NOT.
    :rsv1/2/3  booleans, default false. Only set when an extension that
               defines them has been negotiated.

  Returns `{:status :ok :bytes [...]}`, or `{:status :error :reason ...}`
  when the frame the caller asked for is one the RFC forbids — a control
  frame over 125 bytes, or a fragmented control frame."
  [{:keys [opcode payload fin? mask-key rsv1 rsv2 rsv3]
    :or {payload [] fin? true}}]
  (let [op (if (keyword? opcode) (kind->opcode opcode) opcode)
        payload (vec payload)
        n (count payload)]
    (cond
      (nil? op)
      {:status :error :reason :unknown-opcode :opcode opcode}

      (and (control-opcode? op) (> n 125))
      {:status :error :reason :control-frame-too-long :length n}

      (and (control-opcode? op) (not fin?))
      {:status :error :reason :fragmented-control-frame}

      (and (some? mask-key) (not= 4 (count mask-key)))
      {:status :error :reason :bad-mask-key-length :length (count mask-key)}

      :else
      (let [b0 (bit-or (if fin? 0x80 0)
                       (if rsv1 0x40 0)
                       (if rsv2 0x20 0)
                       (if rsv3 0x10 0)
                       op)
            [len-first len-ext] (length-bytes n)
            masked? (some? mask-key)
            b1 (bit-or (if masked? 0x80 0) (first len-first))
            body (if masked? (mask-payload mask-key payload) payload)]
        {:status :ok
         :bytes (into (into (into [b0 b1] len-ext)
                            (if masked? (vec mask-key) []))
                      body)}))))

(defn encode!
  "`encode`, but returns the byte vector and throws on a rejected frame.

  For call sites that have already established the frame is well-formed —
  a library that only ever emits pongs, say. Anything reading from the wire
  should use `encode`/`decode` and branch on `:status`."
  [opts]
  (let [r (encode opts)]
    (if (= :ok (:status r))
      (:bytes r)
      (throw (ex-info (str "websocket.frame/encode! rejected the frame: "
                           (name (:reason r)))
                      r)))))

;; ------------------------------------------------------------------ decode

(defn- read-uint
  "Big-endian unsigned integer from `n` bytes starting at `off`."
  [buf off n]
  (reduce (fn [acc i] (+ (* acc 256) (nth buf (+ off i)))) 0 (range n)))

(defn decode
  "Read one frame from the front of `buf`.

  A WebSocket rides on a stream, so a caller almost never holds exactly one
  frame. The three answers reflect that:

    {:status :incomplete :need n}   n more bytes are required before the
                                    frame's length is even known, or before
                                    the known-length frame is whole. `n` is a
                                    lower bound, not a promise.
    {:status :ok :frame {...} :consumed n}
    {:status :error :reason kw ...}

  A frame map is `{:fin? :rsv1 :rsv2 :rsv3 :opcode :kind :masked? :mask-key
  :payload}`, where `:payload` is already unmasked and `:kind` is nil for a
  reserved opcode (which is also an `:error`, so it is never seen)."
  [buf]
  (let [buf (vec buf)
        n (count buf)]
    (if (< n 2)
      {:status :incomplete :need (- 2 n)}
      (let [b0 (nth buf 0)
            b1 (nth buf 1)
            fin? (pos? (bit-and b0 0x80))
            rsv1 (pos? (bit-and b0 0x40))
            rsv2 (pos? (bit-and b0 0x20))
            rsv3 (pos? (bit-and b0 0x10))
            op (bit-and b0 0x0F)
            masked? (pos? (bit-and b1 0x80))
            len7 (bit-and b1 0x7F)
            [len-size len-off] (case len7 126 [2 2] 127 [8 2] [0 2])
            header-known (+ 2 len-size)]
        (cond
          (reserved-opcode? op)
          {:status :error :reason :reserved-opcode :opcode op}

          (and (control-opcode? op) (> len7 125))
          {:status :error :reason :control-frame-too-long :length len7}

          (and (control-opcode? op) (not fin?))
          {:status :error :reason :fragmented-control-frame}

          (< n header-known)
          {:status :incomplete :need (- header-known n)}

          ;; The two bounds below are checked on the RAW BYTES, before the
          ;; eight of them are folded into a number. Placing them after the
          ;; fold looks equivalent and is not: on the JVM the fold throws
          ;; `ArithmeticException: long overflow` and the check never runs,
          ;; and under ClojureScript the fold silently returns a float that
          ;; is no longer the length being checked. Either way the guard
          ;; would have been unreachable in exactly the case it exists for.
          (and (= len7 127) (>= (nth buf len-off) 0x80))
          {:status :error :reason :length-msb-set}

          ;; Past 2^53-1 (bytes 00 1F FF FF FF FF FF FF) a ClojureScript
          ;; number stops being an exact integer, so the fold would stop
          ;; answering the question. Refusing is the only honest answer;
          ;; neither runtime could buffer such a frame anyway.
          (and (= len7 127)
               (or (pos? (nth buf len-off))
                   (> (nth buf (inc len-off)) 0x1F)))
          {:status :error :reason :length-unrepresentable}

          :else
          (let [length (if (zero? len-size) len7 (read-uint buf len-off len-size))]
            (cond
              ;; §5.2: the length must use the minimal number of bytes. A
              ;; peer that pads it is either broken or probing, and either
              ;; way the frame is not the one it claims to be.
              (and (= len7 126) (< length 126))
              {:status :error :reason :non-minimal-length :length length}

              (and (= len7 127) (<= length 0xFFFF))
              {:status :error :reason :non-minimal-length :length length}

              :else
              (let [mask-size (if masked? 4 0)
                    total (+ header-known mask-size length)]
                (if (< n total)
                  {:status :incomplete :need (- total n)}
                  (let [mask-off (+ header-known)
                        mask-key (when masked? (subvec buf mask-off (+ mask-off 4)))
                        body-off (+ mask-off mask-size)
                        raw (subvec buf body-off (+ body-off length))]
                    {:status :ok
                     :consumed total
                     :frame {:fin? fin?
                             :rsv1 rsv1 :rsv2 rsv2 :rsv3 rsv3
                             :opcode op
                             :kind (opcode->kind op)
                             :masked? masked?
                             :mask-key mask-key
                             :payload (if masked?
                                        (mask-payload mask-key raw)
                                        raw)}}))))))))))

(defn decode-all
  "Decode as many whole frames as `buf` holds.

  Returns `{:frames [...] :rest [...]}` — `:rest` is the trailing partial
  frame, to be prepended to the next read — or `{:frames [...] :rest [...]
  :error {...}}` when a frame was malformed. Frames decoded before the bad
  one are still returned: a caller that must send a Close frame naming the
  failure usually needs them."
  [buf]
  (loop [buf (vec buf) out []]
    (let [r (decode buf)]
      (case (:status r)
        :ok (recur (subvec buf (:consumed r)) (conj out (:frame r)))
        :incomplete {:frames out :rest buf}
        :error {:frames out :rest buf :error r}))))

;; ------------------------------------------------------------------- close

(defn close-payload
  "§5.5.1 — a Close frame body: a 2-byte big-endian status code, then the
  reason as UTF-8. `reason` is optional.

  UTF-8 encoding is done here rather than deferred to the host, because the
  code is the part a peer acts on and splitting the two across a seam has no
  benefit."
  ([code] (close-payload code nil))
  ([code reason]
   (into [(bit-and (bit-shift-right code 8) 0xFF) (bit-and code 0xFF)]
         (when (seq reason)
           (b/string->bytes reason)))))

(defn parse-close
  "Read a Close frame body back into `{:code n :reason s}`.

  An empty body is `{:code 1005}` — the RFC's \"no status received\" — which
  is not a code that may appear on the wire but is the right thing to hand a
  caller. A 1-byte body is malformed (§5.5.1)."
  [payload]
  (let [p (vec payload)
        n (count p)]
    (cond
      (zero? n) {:code 1005 :reason ""}
      (= 1 n) {:status :error :reason :truncated-close-payload}
      :else
      {:code (+ (* 256 (nth p 0)) (nth p 1))
       :reason (let [body (subvec p 2)]
                 (if (empty? body) "" (b/bytes->string body)))})))

;; -------------------------------------------------------------- conversions
;; Re-exported from `websocket.bytes` so a caller that only needs framing has
;; one namespace to require. The definitions live there because `handshake`
;; needs them too and two copies of a UTF-8 codec is how they drift.

(def string->bytes "UTF-8 encode, for building a text frame's payload." b/string->bytes)
(def bytes->string "UTF-8 decode a text frame's payload." b/bytes->string)
(def hex "Lowercase hex, for reading a frame in a test failure." b/hex)
