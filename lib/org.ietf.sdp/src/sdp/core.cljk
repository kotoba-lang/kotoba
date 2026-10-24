(ns sdp.core
  "SDP — the Session Description Protocol, [RFC 4566] — decode and
  encode between wire text and an EDN session-description value.

  The one property that makes SDP different from a bag of key/value
  lines is the one this namespace exists to enforce: **the RFC fixes the
  order every line type may appear in, and a parser that accepts them
  out of order is not parsing SDP, it is parsing \"a text format that
  happens to resemble SDP on well-formed input\"** — indistinguishable
  from the real thing until a device sends two `c=` lines or an `a=`
  before the mandatory `t=`, which every deployed SDP producer treats as
  a hard error precisely because [RFC 4566] §5 says so in these words:

    \"all MUST appear in exactly the order given here (the fixed order
    greatly enhances error detection and allows for a simple parser)\"

  A `str/split` over `\\n` followed by grouping on the type
  character throws that guarantee away: `group-by` happily accepts `a=`,
  `t=`, `s=`, `v=` in any order, because nothing about it cares about
  sequence. This namespace instead walks the token list once with an
  explicit *position in the grammar* and rejects any line the grammar
  cannot advance to from there as `[:error :sdp/line-out-of-order]` — the
  same one-pass-with-a-cursor shape [RFC 4566] §9's own ABNF has.

  The four phases below are §9's `session-description` production read
  left to right: a fixed preamble (`v=` through `b=`), the required
  `1*( t= *(r=) )` repeating group, a fixed tail (`z= k= a=`), then zero
  or more media descriptions, each with its own `i= c=* b=* k=? a=*`
  scope that starts over at every `m=` line.

  Every internal `consume-*` step returns the same 3-element shape,
  `[:ok value next-index]` or `[:error fail-map nil]` — never a bare map
  on one branch and a vector on the other, which is the kind of asymmetry
  that makes a caller's `(let [[status value idx] (step ...)])`
  destructure silently wrong instead of loudly broken.")

(require '[sdp.grammar :as g]
         '[sdp.attrs :as attrs]
         '[kotoba.lang.text :as str])

;; ── slot tables ──────────────────────────────────────────────────────────
;; One entry per line type, in the exact order [RFC 4566] §9 names them.
;; `:one` = exactly once (required), `:opt` = zero or one, `:many` = zero
;; or more.

(def preamble-slots
  [[\v :one] [\o :one] [\s :one] [\i :opt] [\u :opt]
   [\e :many] [\p :many] [\c :opt] [\b :many]])

(def tail-slots
  [[\z :opt] [\k :opt] [\a :many]])

(def media-slots
  [[\i :opt] [\c :many] [\b :many] [\k :opt] [\a :many]])

(defn- advance
  "First index at or after `pos` in `slots` whose type is `type-char`, or
  nil if there is none reachable. A slot once stepped past is never
  revisited, so a repeated `:one`/`:opt` line is out of order, not a
  duplicate-key overwrite.

  Skipping is only legal over `:opt`/`:many` slots. Hitting an
  unsatisfied `:one` (required, exactly-once) slot that does not match
  `type-char` stops the search — it must NOT be silently skipped. Without
  this check, `advance` would let `c=` satisfy the grammar by scanning
  straight past a still-unfilled required `s=` slot (both come later in
  the table), decoding a session with no session name at all as if it
  were well-formed. This is the same bug class as Modbus's MBAP length
  field: the wrong version *parses successfully* on realistic input and
  is missing exactly the thing it was supposed to guarantee."
  [slots pos type-char]
  (let [n (count slots)]
    (loop [i pos]
      (cond
        (>= i n) nil
        (= (first (nth slots i)) type-char) i
        (= (second (nth slots i)) :one) nil
        :else (recur (inc i))))))

(defn- required-missing [slots pos]
  (->> (drop pos slots) (filter #(= (second %) :one)) (map first) vec))

(defn- err
  "The one shape every failure in this namespace takes on the wire out of
  `decode`, and the one shape every internal `consume-*` step returns on
  its error branch — a 3-tuple, so a caller can always
  `(let [[status value idx] (step ...)])` without checking which branch
  it landed in first."
  ([reason] [:error {:status :error :reason reason} nil])
  ([reason context] [:error {:status :error :reason reason :context context} nil]))

;; ── field parsers (two-element `[:ok v]` / `[:error reason]`) ─────────────

(defn- parse-origin [v]
  (let [parts (str/split v #" ")]
    (if (= 6 (count parts))
      (let [[username sess-id sess-version nettype addrtype address] parts]
        [:ok {:username username :sess-id sess-id :sess-version sess-version
              :nettype nettype :addrtype addrtype :address address}])
      [:error :sdp/malformed-origin])))

(defn- encode-origin [{:keys [username sess-id sess-version nettype addrtype address]}]
  (str/join " " [username sess-id sess-version nettype addrtype address]))

(defn- parse-connection [v]
  (let [parts (str/split v #" ")]
    (if (= 3 (count parts))
      (let [[nettype addrtype address] parts]
        [:ok {:nettype nettype :addrtype addrtype :address address}])
      [:error :sdp/malformed-connection])))

(defn- encode-connection [{:keys [nettype addrtype address]}]
  (str/join " " [nettype addrtype address]))

(defn- parse-bandwidth [v]
  (let [colon (str/index-of v \:)]
    (if (nil? colon)
      [:error :sdp/malformed-bandwidth]
      (let [n (parse-long (subs v (inc colon)))]
        (if n [:ok {:type (subs v 0 colon) :value n}] [:error :sdp/malformed-bandwidth])))))

(defn- encode-bandwidth [{:keys [type value]}] (str type ":" value))

(defn- parse-time [v]
  (let [parts (str/split v #" ")]
    (if (= 2 (count parts))
      [:ok {:start (nth parts 0) :stop (nth parts 1) :repeat []}]
      [:error :sdp/malformed-time])))

(defn- encode-time [{:keys [start stop]}] (str start " " stop))

(defn- parse-repeat [v]
  (let [parts (str/split v #" ")]
    (if (>= (count parts) 2) [:ok parts] [:error :sdp/malformed-repeat])))

(defn- parse-media [v]
  (let [parts (str/split v #" " 4)]
    (if (< (count parts) 4)
      [:error :sdp/malformed-media]
      (let [[media port-field proto fmts-str] parts
            [port-str count-str] (str/split port-field #"/" 2)
            port (parse-long port-str)]
        (if (nil? port)
          [:error :sdp/malformed-media]
          [:ok (cond-> {:media media :port port :proto proto
                        :fmts (str/split fmts-str #" ")
                        :information nil :connection nil :bandwidth [] :key nil :attributes []}
                 count-str (assoc :port-count (parse-long count-str)))])))))

(defn- encode-media [{:keys [media port port-count proto fmts]}]
  (str media " " port (when port-count (str "/" port-count))
       " " proto " " (str/join " " fmts)))

(defn- parse-key [v]
  (cond
    (= v "prompt") [:ok {:method "prompt"}]
    (str/starts-with? v "clear:") [:ok {:method "clear" :value (subs v 6)}]
    (str/starts-with? v "base64:") [:ok {:method "base64" :value (subs v 7)}]
    (str/starts-with? v "uri:") [:ok {:method "uri" :value (subs v 4)}]
    :else [:error :sdp/malformed-key]))

(defn- encode-key [{:keys [method value]}] (if value (str method ":" value) method))

;; ── decode: the four phases ─────────────────────────────────────────────

(defn- consume-preamble
  "`v= o= s= i=? u=? e=* p=* c=? b=*`, stopping at the first `t=` (which
  always follows, per the grammar) or at end of input."
  [tokens i]
  (let [n (count tokens)]
    (loop [i i pos 0 sess {:emails [] :phones [] :bandwidth []}]
      (cond
        (>= i n)
        (let [missing (required-missing preamble-slots pos)]
          (if (seq missing) (err :sdp/missing-required-field {:fields missing})
              (err :sdp/missing-time-field {:line (inc n)})))

        (= (:type (nth tokens i)) \t)
        (let [missing (required-missing preamble-slots pos)]
          (if (seq missing) (err :sdp/missing-required-field {:fields missing})
              [:ok sess i]))

        :else
        (let [{:keys [type value]} (nth tokens i)
              p (advance preamble-slots pos type)]
          (if (nil? p)
            (err :sdp/line-out-of-order {:line (inc i) :type type})
            (case type
              \v (recur (inc i) (inc p) (assoc sess :version value))
              \o (let [[st v] (parse-origin value)]
                   (if (= st :error) (err v {:line (inc i)}) (recur (inc i) (inc p) (assoc sess :origin v))))
              \s (if (empty? value)
                   (err :sdp/empty-session-name {:line (inc i)})
                   (recur (inc i) (inc p) (assoc sess :session-name value)))
              \i (recur (inc i) (inc p) (assoc sess :information value))
              \u (recur (inc i) (inc p) (assoc sess :uri value))
              \e (recur (inc i) p (update sess :emails conj value))
              \p (recur (inc i) p (update sess :phones conj value))
              \c (let [[st v] (parse-connection value)]
                   (if (= st :error) (err v {:line (inc i)}) (recur (inc i) (inc p) (assoc sess :connection v))))
              \b (let [[st v] (parse-bandwidth value)]
                   (if (= st :error) (err v {:line (inc i)}) (recur (inc i) p (update sess :bandwidth conj v)))))))))))

(defn- consume-time-fields
  "`1*( t= *(r=) )` — at least one `t=`, each optionally followed by any
  number of `r=` lines."
  [tokens i]
  (let [n (count tokens)]
    (loop [i i acc []]
      (if (and (< i n) (= (:type (nth tokens i)) \t))
        (let [[st tval] (parse-time (:value (nth tokens i)))]
          (if (= st :error)
            (err tval {:line (inc i)})
            (let [rloop (loop [j (inc i) tv tval]
                          (if (and (< j n) (= (:type (nth tokens j)) \r))
                            (let [[st2 rv] (parse-repeat (:value (nth tokens j)))]
                              (if (= st2 :error)
                                [:error rv j]
                                (recur (inc j) (update tv :repeat conj rv))))
                            [:ok tv j]))
                  [rst rval ridx] rloop]
              (if (= rst :error)
                (err rval {:line (inc ridx)})
                (recur ridx (conj acc rval))))))
        (if (empty? acc) (err :sdp/missing-time-field {:line (inc i)}) [:ok acc i])))))

(defn- consume-tail
  "`z=? k=? a=*` — the fixed tail after the time-fields group and before
  the first media description (or end of message)."
  [tokens i]
  (let [n (count tokens)]
    (loop [i i pos 0 sess {:attributes []}]
      (if (or (>= i n) (= (:type (nth tokens i)) \m))
        [:ok sess i]
        (let [{:keys [type value]} (nth tokens i)
              p (advance tail-slots pos type)]
          (if (nil? p)
            (err :sdp/line-out-of-order {:line (inc i) :type type})
            (case type
              \z (recur (inc i) (inc p) (assoc sess :zone-adjustments value))
              \k (let [[st v] (parse-key value)]
                   (if (= st :error) (err v {:line (inc i)}) (recur (inc i) (inc p) (assoc sess :key v))))
              \a (recur (inc i) p (update sess :attributes conj (attrs/parse-attribute-line value))))))))))

(defn- consume-one-media
  "One `m= i=? c=* b=* k=? a=*` group, starting at a token known to be
  `m=`."
  [tokens i]
  (let [n (count tokens)
        [st m] (parse-media (:value (nth tokens i)))]
    (if (= st :error)
      (err m {:line (inc i)})
      (loop [i (inc i) pos 0 media m]
        (if (or (>= i n) (= (:type (nth tokens i)) \m))
          [:ok media i]
          (let [{:keys [type value]} (nth tokens i)
                p (advance media-slots pos type)]
            (if (nil? p)
              (err :sdp/line-out-of-order {:line (inc i) :type type})
              (case type
                \i (recur (inc i) (inc p) (assoc media :information value))
                \c (let [[st v] (parse-connection value)]
                     (if (= st :error) (err v {:line (inc i)}) (recur (inc i) p (assoc media :connection v))))
                \b (let [[st v] (parse-bandwidth value)]
                     (if (= st :error) (err v {:line (inc i)}) (recur (inc i) p (update media :bandwidth conj v))))
                \k (let [[st v] (parse-key value)]
                     (if (= st :error) (err v {:line (inc i)}) (recur (inc i) (inc p) (assoc media :key v))))
                \a (recur (inc i) p (update media :attributes conj (attrs/parse-attribute-line value)))))))))))

(defn- consume-media-descriptions [tokens i]
  (let [n (count tokens)]
    (loop [i i acc []]
      (cond
        (>= i n) [:ok acc i]
        (= (:type (nth tokens i)) \m)
        (let [[st m i2] (consume-one-media tokens i)]
          (if (= st :error) [:error m nil] (recur i2 (conj acc m))))
        :else (err :sdp/line-out-of-order {:line (inc i) :type (:type (nth tokens i))})))))

(defn decode
  "Wire text -> `{:status :ok :session {...}}` or
  `{:status :error :reason <keyword> :context {...}}`.

  Threads a single token index through the four phases in the order
  [RFC 4566] §9 defines them; each phase either consumes some lines and
  hands the index forward, or fails with a named reason and the line
  number that caused it."
  [text]
  (let [[status result reason-ctx] (g/tokenize text)]
    (if (= status :error)
      {:status :error :reason result :context (or reason-ctx {})}
      (let [tokens result
            [st1 preamble i1] (consume-preamble tokens 0)]
        (if (= st1 :error) preamble
            (let [[st2 tfields i2] (consume-time-fields tokens i1)]
              (if (= st2 :error) tfields
                  (let [[st3 tail i3] (consume-tail tokens i2)]
                    (if (= st3 :error) tail
                        (let [[st4 media _i4] (consume-media-descriptions tokens i3)]
                          (if (= st4 :error) media
                              {:status :ok
                               :session (-> preamble
                                            (assoc :time tfields)
                                            (merge tail)
                                            (assoc :media media))})))))))))))

;; ── encode ───────────────────────────────────────────────────────────────

(defn- encode-attr-lines [attrs] (mapv #(str "a=" (attrs/encode-attribute-line %)) attrs))

(defn- encode-media-lines [{:keys [information connection bandwidth key attributes] :as m}]
  (concat [(str "m=" (encode-media m))]
          (when information [(str "i=" information)])
          (when connection [(str "c=" (encode-connection connection))])
          (map #(str "b=" (encode-bandwidth %)) bandwidth)
          (when key [(str "k=" (encode-key key))])
          (encode-attr-lines attributes)))

(defn- encode-time-lines [{:keys [repeat] :as t}]
  (cons (str "t=" (encode-time t))
        (map #(str "r=" (str/join " " %)) repeat)))

(defn encode
  "EDN session-description -> wire text (CRLF-terminated), or
  `[:error :sdp/missing-required-field ...]` if the value is missing
  `:version`/`:origin`/`:session-name` or has no `:time` entries.
  `encode` never itself produces an out-of-order line — the line order
  is fixed by which vector this function appends to, not by the input
  map's key order — so `decode(encode(x)) == x` exercises the parser
  honestly rather than trivially."
  [{:keys [version origin session-name information uri emails phones connection
           bandwidth time zone-adjustments key attributes media]}]
  (let [missing (cond-> []
                  (nil? version) (conj \v)
                  (nil? origin) (conj \o)
                  (nil? session-name) (conj \s))]
    (cond
      (seq missing) {:status :error :reason :sdp/missing-required-field :context {:fields missing}}
      (empty? time) {:status :error :reason :sdp/missing-time-field :context {}}
      :else
      (let [lines (concat
                   [(str "v=" version) (str "o=" (encode-origin origin)) (str "s=" session-name)]
                   (when information [(str "i=" information)])
                   (when uri [(str "u=" uri)])
                   (map #(str "e=" %) emails)
                   (map #(str "p=" %) phones)
                   (when connection [(str "c=" (encode-connection connection))])
                   (map #(str "b=" (encode-bandwidth %)) bandwidth)
                   (mapcat encode-time-lines time)
                   (when zone-adjustments [(str "z=" zone-adjustments)])
                   (when key [(str "k=" (encode-key key))])
                   (encode-attr-lines attributes)
                   (mapcat encode-media-lines media))]
        {:status :ok :text (str (str/join "\r\n" lines) "\r\n")}))))

;; ── semantic validity (beyond grammar) ────────────────────────────────────

(defn validate
  "[RFC 4566] §5's `c=` note: \"a connection field must be present in
  every media description or at the session-level\". This is not a
  grammar rule — both are syntactically optional — so `decode` cannot
  enforce it while staying a pure grammar parser. `validate` checks it
  separately, returning the index of the first offending media section."
  [session]
  (if (:connection session)
    {:status :ok}
    (if-let [idx (->> (:media session)
                       (map-indexed vector)
                       (remove (fn [[_ m]] (:connection m)))
                       first
                       first)]
      {:status :error :reason :sdp/missing-connection :context {:media-index idx}}
      {:status :ok})))
