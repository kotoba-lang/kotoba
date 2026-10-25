(ns xdr.core
  "XDR — External Data Representation (RFC 4506), schema-driven, portable `.cljc`.

  The codec every ONC RPC protocol is written in: NFS, MOUNT, NLM, and the
  portmapper all describe themselves in the XDR language and then say
  nothing further about bytes, because XDR has already said it.

  ## A schema is data

  Same shape as `protobuf.wire`'s: an ordinary EDN value, reviewable next to
  the RFC it came from rather than hidden in generated output.

      [:struct
       [:status  [:enum]]
       [:handle  [:opaque* 64]]
       [:name    [:string 255]]]

  ## The four rules that are not obvious

  - **Everything is a multiple of four bytes.** Opaque and string data are
    followed by up to three zero bytes. The padding is not optional and it
    is not part of the length: a decoder that forgets to skip it reads the
    next field from the wrong offset, and every field after that is wrong
    too.
  - **There are no optional fields, only optional *data*.** RFC 4506 §4.19
    encodes it as a boolean followed by the value when true. NFS uses it
    everywhere (`post_op_attr`, `post_op_fh3`), which is why `[:optional T]`
    is here rather than being someone's convention.
  - **A union's arms are selected by a discriminant that is itself
    encoded.** The default arm is legal and common; `void` arms are how NFS
    says \"on failure there is nothing else\".
  - **Signed and unsigned differ only in interpretation**, both four bytes
    big-endian. Getting this wrong is invisible until a file is larger than
    2 GiB or a status code has the high bit set.

  ## Bytes

  In and out are platform bytes (`byte[]` on the JVM, `Uint8Array` on
  ClojureScript). Opaque and string payloads stay as platform bytes inside
  decoded values rather than being exploded into integer vectors — an NFS
  READ reply carries up to 64 KiB of file content, and turning that into a
  boxed vector per call is the difference between a filesystem and a
  demonstration."
  (:require [kotoba.lang.text :as str]))

;; ── bytes ─────────────────────────────────────────────────────────────────

(defn- byte-at [bs i]
  #?(:clj (bit-and (int (aget ^bytes bs i)) 0xff)
     :cljs (bit-and (aget bs i) 0xff)))

(defn- byte-count [bs]
  #?(:clj (alength ^bytes bs) :cljs (.-length bs)))

(defn ->bytes
  "Anything byte-shaped → platform bytes."
  [x]
  (cond
    (nil? x) #?(:clj (byte-array 0) :cljs (js/Uint8Array. 0))
    (string? x) #?(:clj (.getBytes ^String x "UTF-8")
                   :cljs (.encode (js/TextEncoder.) x))
    #?@(:clj [(bytes? x) x]
        :cljs [(instance? js/Uint8Array x) x])
    :else #?(:clj (byte-array (map unchecked-byte x))
             :cljs (js/Uint8Array.from (into-array (map #(bit-and % 0xff) x))))))

(defn utf8 [bs]
  #?(:clj (String. ^bytes bs "UTF-8")
     :cljs (.decode (js/TextDecoder.) bs)))

(defn- slice [bs from to]
  #?(:clj (java.util.Arrays/copyOfRange ^bytes bs (int from) (int to))
     :cljs (.slice bs from to)))

;; ── a sink that grows ─────────────────────────────────────────────────────

(defn- sink [] #?(:clj (java.io.ByteArrayOutputStream.) :cljs (array)))

(defn- push-byte! [s b]
  #?(:clj (.write ^java.io.ByteArrayOutputStream s (int (bit-and b 0xff)))
     :cljs (.push s (bit-and b 0xff)))
  s)

(defn- push-bytes! [s bs]
  #?(:clj (.write ^java.io.ByteArrayOutputStream s ^bytes bs)
     :cljs (dotimes [i (.-length bs)] (.push s (aget bs i))))
  s)

(defn- sink->bytes [s]
  #?(:clj (.toByteArray ^java.io.ByteArrayOutputStream s)
     :cljs (js/Uint8Array.from s)))

;; ── primitives ────────────────────────────────────────────────────────────

(def ^:private mask32 0xffffffff)

(defn- put-u32! [s n]
  (let [n (bit-and n mask32)]
    (-> s
        (push-byte! (unsigned-bit-shift-right n 24))
        (push-byte! (unsigned-bit-shift-right n 16))
        (push-byte! (unsigned-bit-shift-right n 8))
        (push-byte! n))))

(defn- get-u32 [bs pos]
  (+ (* (byte-at bs pos) 16777216)
     (* (byte-at bs (+ pos 1)) 65536)
     (* (byte-at bs (+ pos 2)) 256)
     (byte-at bs (+ pos 3))))

(defn- get-i32 [bs pos]
  (let [v (get-u32 bs pos)]
    (if (>= v 2147483648) (- v 4294967296) v)))

;; ── a hyper is 64 bits wide, on a host that has no such number ────────────
;;
;; The JVM has `long`, which is exactly the wire's eight bytes, and
;; `clojure.lang.BigInt` for the one unsigned range a long cannot hold
;; (2^63 and above). ClojureScript has doubles: exact only to 2^53, and
;; every bitwise operator truncates to 32 bits first. Neither is a hyper.
;;
;; The one primitive on that side with the right semantics is `BigInt`, and
;; that is what this library already does everywhere a 64-bit value has to
;; survive a wire: `blake2.word` ("a `long` on :clj, a `BigInt` on :cljs"),
;; `kotoba.kir.cljs-i64` ("never a plain cljs number"), and `ipld.value`,
;; which puts one on a wire with `DataView.setBigInt64`.
;;
;; The other approach in this workspace — `io-multiformats` and
;; `dev-protobuf` refuse anything above 2^53 rather than encode it — is
;; right for those two and wrong here, and both say so themselves: they
;; scope the refusal to codecs whose values do not reach 2^53, and both
;; name the big-integer path as the thing you grow when they do. NFS's
;; `fileid3`, `cookie3` and `writeverf3` are full-width `uint64` and the
;; high bit is ordinary in all three. Refusing them on ClojureScript while
;; the JVM decodes them exactly — which the `+'` below already did — is the
;; cross-host disagreement `protobuf.wire` calls worse than either answer.
;;
;; So on ClojureScript a decoded `hyper`/`uhyper` is ALWAYS a `BigInt`,
;; never sometimes one. A codec that returned a plain number below 2^53 and
;; a BigInt above it would work against one NFS server and throw `Cannot
;; mix BigInt and other types` against the next, and which server you had
;; is not a property anyone tests for.

#?(:clj (def ^:private u64-modulus 18446744073709551616N))

#?(:cljs
   (defn- bigint-value? [x]
     (boolean (and (some? x)
                   (try (identical? js/BigInt (.-constructor x))
                        (catch :default _ false))))))

#?(:cljs
   (defn- ->hyper
     "A hyper argument as a `BigInt`.

     A plain number is accepted only while it is still exactly itself:
     past `Number.MAX_SAFE_INTEGER` the caller has already lost the value
     and we would be encoding a different one, so it is refused rather than
     written down — the same check `ipld.value` makes before it calls
     `setBigInt64`."
     [n]
     (cond
       (bigint-value? n) n
       (and (number? n) (js/Number.isSafeInteger n)) (js/BigInt n)
       :else (throw (ex-info "xdr: a hyper must be a BigInt or an exactly-representable number"
                             {:value n})))))

#?(:clj (def ^:private hyper-min -9223372036854775808))

(defn- check-hyper-range!
  "`hyper` and `unsigned hyper` are the same eight bytes, so this accepts the
  union of both ranges: -2^63 through 2^64-1.

  Outside it, the low 64 bits are a different number, and every path here
  used to write them silently — the JVM's `.longValue` truncates and
  ClojureScript's `BigInt.asUintN` wraps."
  [n]
  #?(:clj
     (when (or (< n hyper-min) (>= n u64-modulus))
       (throw (ex-info "xdr: hyper out of range" {:value n})))
     :cljs
     (when (or (< n (js/BigInt "-9223372036854775808"))
               (> n (js/BigInt "18446744073709551615")))
       (throw (ex-info "xdr: hyper out of range" {:value n})))))

(defn- put-64!
  "Both `hyper` and `unsigned hyper`, because on the wire they are the same
  eight bytes and only the reader's interpretation differs.

  A JVM long already *is* two's complement, so splitting it with bit
  operations is correct for negatives without normalising first — and
  normalising first is what broke: `(+ -2 2^64)` leaves the long range
  entirely. The divide path is kept for the one input a long cannot hold,
  an unsigned value at or above 2^63, which arrives as a BigInt."
  [s n]
  #?(:clj
     (do
       (check-hyper-range! n)
       (if (instance? clojure.lang.BigInt n)
         ;; `quot`/`rem` truncate toward zero, so a NEGATIVE BigInt would split
         ;; into halves that are each negative and reassemble as a different
         ;; number — `-2N` encoded as `00000000fffffffe` where `-2` encoded
         ;; as `fffffffffffffffe`. Normalising into the unsigned range first
         ;; is safe here precisely because BigInt has no ceiling to leave.
         (let [m (if (neg? n) (+' n u64-modulus) n)
               hi (biginteger (quot m 4294967296))
               lo (biginteger (rem m 4294967296))]
           (-> s (put-u32! (.longValue hi)) (put-u32! (.longValue lo))))
         (let [n (long n)]
           (-> s
               (put-u32! (bit-and (unsigned-bit-shift-right n 32) 0xffffffff))
               (put-u32! (bit-and n 0xffffffff))))))
     :cljs
     (let [b (->hyper n)
           _ (check-hyper-range! b)
           ;; Two's complement, exactly: a negative hyper and the unsigned
           ;; hyper 2^64 above it are the same eight bytes by definition.
           m (js/BigInt.asUintN 64 b)
           hi (js/Number (/ m (js/BigInt 4294967296)))
           lo (js/Number (js/BigInt.asUintN 32 m))]
       (-> s (put-u32! hi) (put-u32! lo)))))

#?(:cljs
   (defn- get-u64-bigint [bs pos]
     ;; Both halves are below 2^32, so each is an exact `Number` before it
     ;; becomes a BigInt; the multiply that would have lost the top bits
     ;; happens in BigInt, where it cannot.
     (+ (* (js/BigInt (get-u32 bs pos)) (js/BigInt 4294967296))
        (js/BigInt (get-u32 bs (+ pos 4))))))

(defn- get-i64 [bs pos]
  #?(:clj (bit-or (bit-shift-left (long (get-u32 bs pos)) 32)
                  (long (get-u32 bs (+ pos 4))))
     :cljs (js/BigInt.asIntN 64 (get-u64-bigint bs pos))))

(defn- get-u64 [bs pos]
  ;; JVM: auto-promoting arithmetic, because an unsigned hyper can exceed
  ;; Long/MAX_VALUE and `*` throws there rather than wrapping. Throwing is
  ;; right; promoting is righter, because the value is representable and the
  ;; caller asked for it unsigned.
  ;;
  ;; ClojureScript has no `+'`/`*'` at all — they are not slower there, they
  ;; do not exist — which is why this namespace would not even load. BigInt
  ;; is the promotion.
  #?(:clj (+' (*' (get-u32 bs pos) 4294967296) (get-u32 bs (+ pos 4)))
     :cljs (get-u64-bigint bs pos)))

(defn- padding [n] (mod (- 4 (mod n 4)) 4))

;; ── encode ────────────────────────────────────────────────────────────────

(declare encode-into!)

(defn- encode-opaque! [s bs]
  (push-bytes! s bs)
  (dotimes [_ (padding (byte-count bs))] (push-byte! s 0))
  s)

(defn- check-max! [n max-n schema]
  (when (and max-n (> n max-n))
    (throw (ex-info "xdr: value exceeds the schema's declared maximum"
                    {:length n :max max-n :schema schema}))))

(defn- encode-into! [s schema value]
  (let [[kind a b] (if (keyword? schema) [schema] schema)]
    (case kind
      :void s
      :int (put-u32! s (if (neg? value) (+ value 4294967296) value))
      :uint (put-u32! s value)
      :enum (put-u32! s (if (neg? value) (+ value 4294967296) value))
      :bool (put-u32! s (if value 1 0))
      :hyper (put-64! s value)
      :uhyper (put-64! s value)

      :opaque (let [bs (->bytes value)]
                (when (not= (byte-count bs) a)
                  (throw (ex-info "xdr: fixed opaque has the wrong length"
                                  {:expected a :actual (byte-count bs)})))
                (encode-opaque! s bs))

      :opaque* (let [bs (->bytes value)]
                 (check-max! (byte-count bs) a schema)
                 (put-u32! s (byte-count bs))
                 (encode-opaque! s bs))

      :string (let [bs (->bytes value)]
                (check-max! (byte-count bs) a schema)
                (put-u32! s (byte-count bs))
                (encode-opaque! s bs))

      ;; `[:array T n]` — `a` is the element type, `b` the count. Stated
      ;; because the two are both "the second thing" at a glance and
      ;; transposing them type-checks, encodes, and produces nonsense.
      :array (do (when (not= (count value) b)
                   (throw (ex-info "xdr: fixed array has the wrong length"
                                   {:expected b :actual (count value)})))
                 (reduce #(encode-into! %1 a %2) s value))

      :array* (do (check-max! (count value) b schema)
                  (put-u32! s (count value))
                  (reduce #(encode-into! %1 a %2) s value))

      :struct (reduce (fn [s [k t]] (encode-into! s t (get value k)))
                      s (rest schema))

      :optional (if (some? value)
                  (-> (put-u32! s 1) (encode-into! a value))
                  (put-u32! s 0))

      :union (let [disc (:disc value)
                   arm (if (contains? b disc) (get b disc) (get b :default))]
               (when (nil? arm)
                 (throw (ex-info "xdr: union has no arm for this discriminant"
                                 {:disc disc :arms (keys b)})))
               (-> (encode-into! s a disc)
                   (encode-into! arm (:value value))))

      (throw (ex-info "xdr: unknown schema kind" {:kind kind :schema schema})))))

(defn encode
  "`value` as XDR bytes, per `schema`."
  [schema value]
  (sink->bytes (encode-into! (sink) schema value)))

;; ── decode ────────────────────────────────────────────────────────────────

(declare decode-at)

(defn- need! [bs pos n]
  (when (> (+ pos n) (byte-count bs))
    (throw (ex-info "xdr: truncated message"
                    {:want n :at pos :have (byte-count bs)})))
  pos)

(defn- decode-at
  "→ `[value next-pos]`."
  [schema bs pos]
  (let [[kind a b] (if (keyword? schema) [schema] schema)]
    (case kind
      :void [nil pos]
      :int (do (need! bs pos 4) [(get-i32 bs pos) (+ pos 4)])
      :uint (do (need! bs pos 4) [(get-u32 bs pos) (+ pos 4)])
      :enum (do (need! bs pos 4) [(get-u32 bs pos) (+ pos 4)])
      :bool (do (need! bs pos 4) [(not (zero? (get-u32 bs pos))) (+ pos 4)])
      :hyper (do (need! bs pos 8) [(get-i64 bs pos) (+ pos 8)])
      :uhyper (do (need! bs pos 8) [(get-u64 bs pos) (+ pos 8)])

      :opaque (do (need! bs pos a)
                  [(slice bs pos (+ pos a)) (+ pos a (padding a))])

      :opaque* (let [_ (need! bs pos 4)
                     n (get-u32 bs pos)]
                 (check-max! n a schema)
                 (need! bs (+ pos 4) n)
                 [(slice bs (+ pos 4) (+ pos 4 n)) (+ pos 4 n (padding n))])

      :string (let [_ (need! bs pos 4)
                    n (get-u32 bs pos)]
                (check-max! n a schema)
                (need! bs (+ pos 4) n)
                [(utf8 (slice bs (+ pos 4) (+ pos 4 n))) (+ pos 4 n (padding n))])

      :array (loop [i 0 p pos acc []]
               (if (= i b)
                 [acc p]
                 (let [[v p'] (decode-at a bs p)]
                   (recur (inc i) p' (conj acc v)))))

      :array* (let [_ (need! bs pos 4)
                    n (get-u32 bs pos)]
                (check-max! n b schema)
                (loop [i 0 p (+ pos 4) acc []]
                  (if (= i n)
                    [acc p]
                    (let [[v p'] (decode-at a bs p)]
                      (recur (inc i) p' (conj acc v))))))

      :struct (loop [fields (rest schema) p pos acc {}]
                (if-let [[k t] (first fields)]
                  (let [[v p'] (decode-at t bs p)]
                    (recur (next fields) p' (assoc acc k v)))
                  [acc p]))

      :optional (let [_ (need! bs pos 4)
                      present? (not (zero? (get-u32 bs pos)))]
                  (if present?
                    (decode-at a bs (+ pos 4))
                    [nil (+ pos 4)]))

      :union (let [[disc p] (decode-at a bs pos)
                   arm (if (contains? b disc) (get b disc) (get b :default))]
               (when (nil? arm)
                 (throw (ex-info "xdr: union has no arm for this discriminant"
                                 {:disc disc :arms (keys b)})))
               (let [[v p'] (decode-at arm bs p)]
                 [{:disc disc :value v} p']))

      (throw (ex-info "xdr: unknown schema kind" {:kind kind :schema schema})))))

(defn decode
  "XDR bytes → `{:value v :end <offset after the value>}`.

  `:end` rather than a bare value because a stream carries more than one
  message and the caller needs to know where this one stopped."
  ([schema bs] (decode schema bs 0))
  ([schema bs pos]
   (let [[v end] (decode-at schema bs pos)]
     {:value v :end end})))

(defn decode-value
  "`decode`'s value alone, for callers holding exactly one message."
  ([schema bs] (:value (decode schema bs 0)))
  ([schema bs pos] (:value (decode schema bs pos))))

(defn hexify
  "For fixtures and failures — not part of the codec."
  [bs]
  (str/join (map (fn [i]
                   (let [h #?(:clj (Integer/toString (byte-at bs i) 16)
                              :cljs (.toString (byte-at bs i) 16))]
                     (if (= 1 (count h)) (str "0" h) h)))
                 (range (byte-count bs)))))
