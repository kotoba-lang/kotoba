(ns msgpack.core
  "[MessagePack](https://msgpack.org) encode and decode, portable `.cljc`,
  with no dependencies.

  Why this exists as its own library. Two copies of MessagePack already sit
  in this workspace and neither can be shared: `checkpointer` carries a
  hand-rolled codec that is `#?(:clj ...)` throughout with throwing
  ClojureScript stubs, and the same repository's JavaScript side reaches for
  the npm package `@msgpack/msgpack`. So the wire format is implemented
  twice, once per runtime, and a fix to either is a fix to one. MessagePack
  is a byte format; it has no reason to be host-shaped.

  Bytes are `Sequential` collections of ints in 0..255, in and out — the one
  representation both runtimes agree on without typed arrays.

  ## The value mapping

      msgpack        Clojure
      nil            nil
      bool           true / false
      int            integer
      float 32/64    double
      str            string
      bin            {:msgpack/bin [bytes]}
      array          vector
      map            map
      ext            {:msgpack/ext {:type n :data [bytes]}}

  `bin` and `ext` are tagged because they would otherwise be
  indistinguishable from an array of small integers and from a map. The tag
  is a plain map, so a decoded value stays comparable and printable.

  ## Two limits worth reading before you use it

  **Integers are the exact-integer intersection of the two runtimes**:
  -(2^53-1) .. 2^53-1. Outside that, `encode` and `decode` both refuse with
  `:integer-unrepresentable`. A JVM `long` reaches 2^63-1 and a ClojureScript
  number does not, so supporting the wider range would mean this codec
  answers differently depending on where it runs — which is worse than
  refusing, because the difference is silent. If you need the full 64-bit
  range on the wire, carry it as `bin` or `ext`.

  **Whether 3.0 is an integer is a property of the host, not of this codec.**
  ClojureScript has one numeric type, so `3.0` is `integer?` there and
  encodes as a fixint, while the JVM sees a double and writes a float64.
  Nothing here can reconcile that. If the distinction matters on your wire,
  do not put a whole-valued double on it.

  ## Errors

  Returned, never thrown. `:status` is `:ok`, `:incomplete` (decode only), or
  `:error` with a keyword `:reason` naming the rule. The reason keywords are
  contract; renaming one is a breaking change."
  (:require [msgpack.bytes :as b]))

(def max-safe-integer
  "2^53-1 — the largest integer both target runtimes represent exactly."
  9007199254740991)

(def min-safe-integer (- max-safe-integer))

;; ------------------------------------------------------------------ encode

(defn- be-bytes
  "`n` as `width` big-endian bytes. Written with division rather than shifts:
  ClojureScript takes a bit-shift count mod 32, so a shift of 32 or more
  silently becomes a different shift, and an 8-byte field is exactly where
  that bites."
  [n width]
  (mapv (fn [i]
          (let [divisor (reduce * 1 (repeat (- width 1 i) 256))]
            (bit-and (quot n divisor) 0xFF)))
        (range width)))

(defn- two-complement
  "`n` (negative) as an unsigned `width`-byte value. Widths up to 4 only —
  forming 2^64 to complement an 8-byte value overflows a JVM `long` before
  the value is ever written, so `int64-bytes` does that case with modular
  arithmetic instead."
  [n width]
  (+ n (reduce * 1 (repeat width 256))))

(defn- int64-bytes
  "`n` as 8 big-endian two's-complement bytes, without ever forming 2^64.

  `mod` in Clojure is floored, so it returns the unsigned residue for a
  negative `n` on both runtimes — which is exactly the two's-complement
  word. Computing `(+ n 18446744073709551616)` instead throws
  `ArithmeticException: long overflow` on the JVM and loses precision under
  ClojureScript."
  [n]
  (let [lo (mod n 4294967296)
        hi (mod (quot (- n lo) 4294967296) 4294967296)]
    (into (be-bytes hi 4) (be-bytes lo 4))))

(declare encode-value)

(defn- encode-int [n]
  (cond
    (and (<= 0 n) (<= n 127)) [n]
    (and (<= -32 n) (< n 0)) [(+ 256 n)]
    (and (<= 0 n) (<= n 0xFF)) (into [0xCC] (be-bytes n 1))
    (and (<= 0 n) (<= n 0xFFFF)) (into [0xCD] (be-bytes n 2))
    (and (<= 0 n) (<= n 0xFFFFFFFF)) (into [0xCE] (be-bytes n 4))
    (<= 0 n) (into [0xCF] (be-bytes n 8))
    (<= -128 n) (into [0xD0] (be-bytes (two-complement n 1) 1))
    (<= -32768 n) (into [0xD1] (be-bytes (two-complement n 2) 2))
    (<= -2147483648 n) (into [0xD2] (be-bytes (two-complement n 4) 4))
    :else (into [0xD3] (int64-bytes n))))

(defn- encode-str [s]
  (let [bs (b/string->bytes s)
        n (count bs)]
    (cond
      (< n 32) (into [(bit-or 0xA0 n)] bs)
      (<= n 0xFF) (into (into [0xD9] (be-bytes n 1)) bs)
      (<= n 0xFFFF) (into (into [0xDA] (be-bytes n 2)) bs)
      :else (into (into [0xDB] (be-bytes n 4)) bs))))

(defn- encode-bin [bs]
  (let [bs (vec bs) n (count bs)]
    (cond
      (<= n 0xFF) (into (into [0xC4] (be-bytes n 1)) bs)
      (<= n 0xFFFF) (into (into [0xC5] (be-bytes n 2)) bs)
      :else (into (into [0xC6] (be-bytes n 4)) bs))))

(defn- encode-ext [{:keys [type data]}]
  (let [d (vec data) n (count d)
        t (if (neg? type) (+ 256 type) type)]
    (cond
      (= n 1) (into [0xD4 t] d)
      (= n 2) (into [0xD5 t] d)
      (= n 4) (into [0xD6 t] d)
      (= n 8) (into [0xD7 t] d)
      (= n 16) (into [0xD8 t] d)
      (<= n 0xFF) (into (into (into [0xC7] (be-bytes n 1)) [t]) d)
      (<= n 0xFFFF) (into (into (into [0xC8] (be-bytes n 2)) [t]) d)
      :else (into (into (into [0xC9] (be-bytes n 4)) [t]) d))))

(defn- encode-value
  "Returns a byte vector, or throws `ex-info` carrying `:reason`. The throw
  is internal only; `encode` catches it and returns the error map."
  [x]
  (cond
    (nil? x) [0xC0]
    (true? x) [0xC3]
    (false? x) [0xC2]

    (and (map? x) (contains? x :msgpack/bin)) (encode-bin (:msgpack/bin x))
    (and (map? x) (contains? x :msgpack/ext)) (encode-ext (:msgpack/ext x))

    (integer? x)
    (if (or (> x max-safe-integer) (< x min-safe-integer))
      (throw (ex-info "integer outside the exact range both runtimes share"
                      {:reason :integer-unrepresentable :value x}))
      (encode-int x))

    (number? x) (into [0xCB] (b/f64->bytes (double x)))

    (string? x) (encode-str x)
    ;; msgpack has no keyword or symbol type. Encoding them as strings is
    ;; lossy on the way back -- `{:a 1}` decodes to `{"a" 1}` -- and that is
    ;; stated rather than hidden, because the alternative is refusing values
    ;; that every Clojure caller will hand us.
    (keyword? x) (encode-str (if-let [ns' (namespace x)] (str ns' "/" (name x)) (name x)))
    (symbol? x) (encode-str (str x))

    (map? x)
    (let [n (count x)
          header (cond
                   (< n 16) [(bit-or 0x80 n)]
                   (<= n 0xFFFF) (into [0xDE] (be-bytes n 2))
                   :else (into [0xDF] (be-bytes n 4)))]
      (into header (mapcat (fn [[k v]] (into (encode-value k) (encode-value v))) x)))

    (sequential? x)
    (let [v (vec x)
          n (count v)
          header (cond
                   (< n 16) [(bit-or 0x90 n)]
                   (<= n 0xFFFF) (into [0xDC] (be-bytes n 2))
                   :else (into [0xDD] (be-bytes n 4)))]
      (into header (mapcat encode-value v)))

    (set? x)
    (throw (ex-info "msgpack has no set type; convert to a vector first"
                    {:reason :unsupported-type :type :set}))

    :else
    (throw (ex-info "no msgpack representation for this value"
                    {:reason :unsupported-type :value x}))))

(defn encode
  "Serialize `x`. Returns `{:status :ok :bytes [...]}` or
  `{:status :error :reason kw ...}`.

  Map entries are written in the map's own seq order. For a `hash-map` that
  order is unspecified, so two encodes of an equal map may differ in bytes.
  MessagePack is a wire format, not a content-addressing scheme, and every
  conformant decoder reads either. If you need stable bytes, hand this an
  `array-map` or a `sorted-map`."
  [x]
  (try
    {:status :ok :bytes (encode-value x)}
    (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) e
      (merge {:status :error} (ex-data e)))))

(defn encode!
  "`encode`, throwing on a value it cannot represent."
  [x]
  (let [r (encode x)]
    (if (= :ok (:status r))
      (:bytes r)
      (throw (ex-info (str "msgpack.core/encode! refused the value: "
                           (name (:reason r)))
                      r)))))

;; ------------------------------------------------------------------ decode

(defn- read-uint [buf off n]
  (reduce (fn [acc i] (+ (* acc 256) (nth buf (+ off i)))) 0 (range n)))

(defn- read-int
  "Signed big-endian, `n` bytes.

  The sign is taken from the top byte and carried through the fold rather
  than subtracted from an unsigned result at the end. Folding first and
  correcting afterwards needs 2^(8n), which for n=8 overflows a JVM `long`
  before the correction can happen."
  [buf off n]
  (let [b0 (nth buf off)
        start (if (>= b0 0x80) (- b0 256) b0)]
    (reduce (fn [acc i] (+ (* acc 256) (nth buf (+ off i)))) start (range 1 n))))

(declare decode-at)

(defn- need [n] {:status :incomplete :need n})

(defn- decode-seq
  "Read `n` consecutive values starting at `off`."
  [buf off n]
  (loop [i 0 off off acc []]
    (if (= i n)
      {:status :ok :values acc :end off}
      (let [r (decode-at buf off)]
        (case (:status r)
          :ok (recur (inc i) (:end r) (conj acc (:value r)))
          r)))))

(defn- with-payload
  "Common shape: a header of `hdr` bytes, then `len` payload bytes at
  `off`+`hdr`, handed to `f`."
  [buf off hdr len f]
  (let [start (+ off hdr)
        end (+ start len)]
    (if (> end (count buf))
      (need (- end (count buf)))
      {:status :ok :value (f (subvec buf start end)) :end end})))

(defn- decode-at [buf off]
  (if (>= off (count buf))
    (need 1)
    (let [t (nth buf off)
          n (count buf)
          fits? (fn [k] (<= (+ off k) n))]
      (cond
        ;; positive fixint / negative fixint
        (<= t 0x7F) {:status :ok :value t :end (inc off)}
        (>= t 0xE0) {:status :ok :value (- t 256) :end (inc off)}

        ;; fixmap / fixarray / fixstr
        (<= 0x80 t 0x8F)
        (let [cnt (bit-and t 0x0F)
              r (decode-seq buf (inc off) (* 2 cnt))]
          (if (= :ok (:status r))
            {:status :ok :value (apply hash-map (:values r)) :end (:end r)}
            r))

        (<= 0x90 t 0x9F)
        (let [r (decode-seq buf (inc off) (bit-and t 0x0F))]
          (if (= :ok (:status r))
            {:status :ok :value (:values r) :end (:end r)}
            r))

        (<= 0xA0 t 0xBF)
        (with-payload buf off 1 (bit-and t 0x1F) b/bytes->string)

        (= t 0xC0) {:status :ok :value nil :end (inc off)}
        (= t 0xC1) {:status :error :reason :never-used-byte :offset off}
        (= t 0xC2) {:status :ok :value false :end (inc off)}
        (= t 0xC3) {:status :ok :value true :end (inc off)}

        ;; bin 8/16/32
        (<= 0xC4 t 0xC6)
        (let [w (bit-shift-left 1 (- t 0xC4))]
          (if-not (fits? (inc w))
            (need (- (+ off 1 w) n))
            (with-payload buf off (inc w) (read-uint buf (inc off) w)
                          (fn [bs] {:msgpack/bin bs}))))

        ;; ext 8/16/32
        (<= 0xC7 t 0xC9)
        (let [w (bit-shift-left 1 (- t 0xC7))]
          (if-not (fits? (+ 2 w))
            (need (- (+ off 2 w) n))
            (let [len (read-uint buf (inc off) w)
                  ty (nth buf (+ off 1 w))
                  ty (if (>= ty 0x80) (- ty 256) ty)]
              (with-payload buf off (+ 2 w) len
                            (fn [bs] {:msgpack/ext {:type ty :data bs}})))))

        (= t 0xCA)
        (if-not (fits? 5) (need (- (+ off 5) n))
                {:status :ok :value (b/bytes->f32 (subvec buf (inc off) (+ off 5)))
                 :end (+ off 5)})

        (= t 0xCB)
        (if-not (fits? 9) (need (- (+ off 9) n))
                {:status :ok :value (b/bytes->f64 (subvec buf (inc off) (+ off 9)))
                 :end (+ off 9)})

        ;; uint 8/16/32/64
        (<= 0xCC t 0xCF)
        (let [w (bit-shift-left 1 (- t 0xCC))]
          (cond
            (not (fits? (inc w))) (need (- (+ off 1 w) n))
            ;; The byte pre-check is what makes the fold safe: on the JVM,
            ;; folding a full uint64 throws `long overflow`, so a guard
            ;; placed only after the fold never runs in the case it exists
            ;; for. `b0 = 0` and `b1 <= 0x1F` bound the value at 2^53-1
            ;; exactly, which is also the range check, so nothing further is
            ;; needed on this branch.
            (and (= w 8) (or (pos? (nth buf (inc off)))
                             (> (nth buf (+ off 2)) 0x1F)))
            {:status :error :reason :integer-unrepresentable :offset off}
            :else {:status :ok :value (read-uint buf (inc off) w) :end (+ off 1 w)}))

        ;; int 8/16/32/64
        (<= 0xD0 t 0xD3)
        (let [w (bit-shift-left 1 (- t 0xD0))]
          (cond
            (not (fits? (inc w))) (need (- (+ off 1 w) n))
            ;; Two stages, and both are needed. The byte pre-check bounds
            ;; the magnitude at 2^53 so the fold cannot overflow a JVM
            ;; `long`; the value check afterwards is what makes the bound
            ;; exact, since 0xFFE0000000000000 is -2^53 and this codec's
            ;; range stops one short of it.
            (and (= w 8)
                 (let [b0 (nth buf (inc off)) b1 (nth buf (+ off 2))]
                   (if (>= b0 0x80)
                     (or (< b0 0xFF) (< b1 0xE0))
                     (or (pos? b0) (> b1 0x1F)))))
            {:status :error :reason :integer-unrepresentable :offset off}
            :else
            (let [v (read-int buf (inc off) w)]
              (if (or (> v max-safe-integer) (< v min-safe-integer))
                {:status :error :reason :integer-unrepresentable :offset off}
                {:status :ok :value v :end (+ off 1 w)}))))

        ;; fixext 1/2/4/8/16
        (<= 0xD4 t 0xD8)
        (let [len (bit-shift-left 1 (- t 0xD4))]
          (if-not (fits? 2) (need (- (+ off 2) n))
                  (let [ty (nth buf (inc off))
                        ty (if (>= ty 0x80) (- ty 256) ty)]
                    (with-payload buf off 2 len
                                  (fn [bs] {:msgpack/ext {:type ty :data bs}})))))

        ;; str 8/16/32
        (<= 0xD9 t 0xDB)
        (let [w (bit-shift-left 1 (- t 0xD9))]
          (if-not (fits? (inc w))
            (need (- (+ off 1 w) n))
            (with-payload buf off (inc w) (read-uint buf (inc off) w) b/bytes->string)))

        ;; array 16/32
        (<= 0xDC t 0xDD)
        (let [w (if (= t 0xDC) 2 4)]
          (if-not (fits? (inc w))
            (need (- (+ off 1 w) n))
            (let [r (decode-seq buf (+ off 1 w) (read-uint buf (inc off) w))]
              (if (= :ok (:status r))
                {:status :ok :value (:values r) :end (:end r)}
                r))))

        ;; map 16/32
        (<= 0xDE t 0xDF)
        (let [w (if (= t 0xDE) 2 4)]
          (if-not (fits? (inc w))
            (need (- (+ off 1 w) n))
            (let [r (decode-seq buf (+ off 1 w) (* 2 (read-uint buf (inc off) w)))]
              (if (= :ok (:status r))
                {:status :ok :value (apply hash-map (:values r)) :end (:end r)}
                r))))

        :else {:status :error :reason :unknown-type-byte :byte t :offset off}))))

(defn decode
  "Read one value from the front of `buf`.

  Returns `{:status :ok :value v :consumed n}`, `{:status :incomplete
  :need n}` when more bytes are required, or `{:status :error :reason kw}`.
  Trailing bytes past the first value are left for the caller — MessagePack
  streams are a concatenation of values."
  [buf]
  (let [buf (vec buf)
        r (decode-at buf 0)]
    (if (= :ok (:status r))
      {:status :ok :value (:value r) :consumed (:end r)}
      r)))

(defn decode!
  "`decode`, throwing on anything but a complete value."
  [buf]
  (let [r (decode buf)]
    (if (= :ok (:status r))
      (:value r)
      (throw (ex-info (str "msgpack.core/decode! could not read a value: "
                           (name (or (:reason r) (:status r))))
                      r)))))

(defn decode-all
  "Read every whole value in `buf`.

  Returns `{:values [...] :rest [...]}`, or the same with an `:error` key
  when a value was malformed."
  [buf]
  (loop [buf (vec buf) out []]
    (if (empty? buf)
      {:values out :rest []}
      (let [r (decode buf)]
        (case (:status r)
          :ok (recur (subvec buf (:consumed r)) (conj out (:value r)))
          :incomplete {:values out :rest buf}
          :error {:values out :rest buf :error r})))))
