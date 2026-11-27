(ns kotoba.ontology-viz.validate
  "Fail-closed input validation, normalized-graph boundary validation, explicit
  safety bounds (enforced before full collection realization), remote-context
  guards, strict hex paint validation, and binary CIDv1 multiformats parsing."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]))

(def default-limits
  "Default resource bounds enforced on every projection and render."
  {:max-nodes 500
   :max-edges 2000
   :max-label-length 256
   :max-value-length 1024
   :max-depth 16
   :max-joins 128
   :max-attributes-per-node 64
   :max-input-items 10000
   :max-collection-width 2048})

(def hard-limits
  "Absolute ceilings that caller-supplied `:limits` may never exceed."
  {:max-nodes 5000
   :max-edges 20000
   :max-label-length 1024
   :max-value-length 8192
   :max-depth 64
   :max-joins 1024
   :max-attributes-per-node 512
   :max-input-items 50000
   :max-collection-width 10000})

(def valid-match-rules
  #{:exact :exact-uppercase :exact-lowercase :prefix :mapping})

(def valid-cardinalities
  #{:one-to-one :one-to-many :many-to-one :many-to-many})

(def valid-ambiguous-modes
  #{:error :all})

(def valid-node-kinds
  #{:connector :object-type :attribute :entity :rdf-resource :rdf-blank :ipld-node})

(def valid-edge-kinds
  #{:produces :provenance :has-attribute :instance-of :datom-ref :rdf-predicate
    :join :join-instance :ipld-link})

(def valid-cid-verification-states
  #{:syntax-only :verified})

(defn fail!
  "Throw a structured ex-info refusal with an explicit `:reason` keyword."
  [reason message data]
  (throw (ex-info message (assoc data :reason reason))))

;; ── Strict Binary CIDv1 Parser (Multibase + Multicodec + Multihash) ──────────

(def ^:private base32-alphabet "abcdefghijklmnopqrstuvwxyz234567")

(def ^:private base32-lookup
  (into {} (map-indexed (fn [idx ch] [ch idx]) base32-alphabet)))

(defn- base32-encode [bytes]
  (let [n (count bytes)]
    (loop [i 0
           bits 0
           acc 0
           out (transient [])]
      (if (= i n)
        (let [final-out (if (pos? bits)
                          (conj! out (.charAt base32-alphabet
                                              (bit-and (bit-shift-left acc (- 5 bits)) 31)))
                          out)]
          (apply str (persistent! final-out)))
        (let [b (bit-and (nth bytes i) 0xff)
              next-acc (bit-or (bit-shift-left acc 8) b)
              next-bits (+ bits 8)
              [rem-bits rem-acc next-out]
              (loop [b-rem next-bits
                     a-rem next-acc
                     o out]
                (if (>= b-rem 5)
                  (let [shift (- b-rem 5)
                        idx (bit-and (unsigned-bit-shift-right a-rem shift) 31)
                        mask (dec (bit-shift-left 1 shift))]
                    (recur shift (bit-and a-rem mask) (conj! o (.charAt base32-alphabet idx))))
                  [b-rem a-rem o]))]
          (recur (inc i) rem-bits rem-acc next-out))))))

(defn- base32-decode
  "Decode RFC4648 lower-case unpadded base32. Returns vector of unsigned bytes
  or nil if any character is invalid or trailing bits are non-zero."
  [s]
  (let [n (count s)]
    (when (pos? n)
      (loop [i 0
             bits 0
             acc 0
             out (transient [])]
        (if (= i n)
          ;; Residual bits (< 5) must be zero (canonical base32, no alias padding)
          (when (zero? (bit-and acc (dec (bit-shift-left 1 bits))))
            (persistent! out))
          (let [digit (get base32-lookup (.charAt s i))]
            (when (some? digit)
              (let [next-acc (bit-or (bit-shift-left acc 5) digit)
                    next-bits (+ bits 5)]
                (if (>= next-bits 8)
                  (let [shift (- next-bits 8)
                        byte-val (bit-and (unsigned-bit-shift-right next-acc shift) 0xff)
                        mask (dec (bit-shift-left 1 shift))]
                    (recur (inc i) shift (bit-and next-acc mask) (conj! out byte-val)))
                  (recur (inc i) next-bits next-acc out))))))))))

(defn- decode-varint
  "Decode shortest-representation unsigned LEB128 varint from byte vector.
  Returns {:value n :next-offset idx} or nil on malformed/overlong encoding."
  [bytes offset]
  (let [n (count bytes)]
    (loop [i 0
           shift 0
           acc 0]
      (when (and (< i 8) (< (+ offset i) n))
        (let [b (nth bytes (+ offset i))
              low (bit-and b 0x7f)
              val (+ acc (* low (bit-shift-left 1 shift)))]
          (if (zero? (bit-and b 0x80))
            (when-not (and (pos? i) (zero? b))
              {:value val :next-offset (+ offset i 1)})
            (recur (inc i) (+ shift 7) val)))))))

(def ^:private known-multihash-lengths
  "Standard multihash digest lengths (nil means variable up to 64 bytes for identity)."
  {0x12 #{32}      ;; sha2-256
   0x13 #{64}      ;; sha2-512
   0x16 #{32}      ;; sha3-256
   0x14 #{64}      ;; sha3-512
   0x1e #{32}      ;; blake3
   0xb220 #{32}    ;; blake2b-256
   0x00 nil})      ;; identity (bounded <= 64)

(def ^:private known-cid-codecs
  {0x55 :raw
   0x70 :dag-pb
   0x71 :dag-cbor
   0x0129 :dag-json
   0x51 :cbor
   0x72 :libp2p-key})

(defn parse-cidv1
  "Strictly parse a canonical base32lower ('b'-multibase) CIDv1 binary structure:
  - canonical base32 round-trip (rejects non-zero residual padding bits)
  - varint version == 1
  - positive multicodec varint
  - recognized multihash code + valid digest length
  - exact remaining byte length == declared digest length

  Returns `{:version 1 :codec-code ... :codec ... :hash-code ... :digest-length ...}`
  or `nil` if malformed. NOTE: this validates CIDv1 syntax/structure only
  (`:cid-verification :syntax-only`), never cryptographic block integrity."
  [s]
  (when (and (string? s)
             (<= 10 (count s) 256)
             (str/starts-with? s "b"))
    (when-let [bytes (base32-decode (subs s 1))]
      (when (and (>= (count bytes) 4)
                 (= s (str "b" (base32-encode bytes))))
        (when-let [{ver :value o1 :next-offset} (decode-varint bytes 0)]
          (when (= 1 ver)
            (when-let [{codec :value o2 :next-offset} (decode-varint bytes o1)]
              (when (pos? codec)
                (when-let [{hcode :value o3 :next-offset} (decode-varint bytes o2)]
                  (when (contains? known-multihash-lengths hcode)
                    (when-let [{dlen :value o4 :next-offset} (decode-varint bytes o3)]
                      (let [allowed-lens (get known-multihash-lengths hcode)
                            rem-len (- (count bytes) o4)]
                        (when (and (= rem-len dlen)
                                   (if allowed-lens
                                     (contains? allowed-lens dlen)
                                     (<= 1 dlen 64)))
                          {:version 1
                           :codec-code codec
                           :codec (get known-cid-codecs codec :unknown)
                           :hash-code hcode
                           :digest-length dlen
                           :verification :syntax-only})))))))))))))

(defn valid-cid?
  "True when `s` is a structurally valid canonical base32lower CIDv1 string
  (verified by binary varint/multicodec/multihash parsing)."
  [s]
  (boolean (parse-cidv1 s)))

(defrecord IpldLink [cid])

(defn ipld-link
  "Construct a portable IPLD Link wrapper after strict binary CIDv1 validation."
  [cid]
  (when-not (valid-cid? cid)
    (fail! :invalid-cid
           (str "invalid CIDv1 binary structure: " (pr-str cid))
           {:cid cid}))
  (->IpldLink cid))

(defn ipld-link?
  "True when `x` is a recognized IPLD Link representation:
  - `IpldLink` record from this library,
  - `ipld.link/Link` record (carries `:cid` and type name ending in `Link`),
  - DAG-JSON link map `{\"/\" \"bafy...\"}`,
  - explicit link map `{:ipld/link \"bafy...\"}` or `{:ipld/cid \"bafy...\"}`."
  [x]
  (cond
    (instance? IpldLink x) true
    (and (map? x) (= 1 (count x)) (contains? x "/")) true
    (and (map? x) (contains? x :ipld/link)) true
    (and (map? x) (contains? x :ipld/cid) (= 1 (count x))) true
    (and (record? x) (contains? x :cid)
         (let [tname (str (type x))]
           (or (str/ends-with? tname "Link")
               (str/includes? tname "ipld.link")))) true
    :else false))

(defn extract-cid
  "Extract and strictly parse a CIDv1 string from an IPLD Link wrapper or raw
  CID string. Returns `nil` for `nil`; fails closed with `:invalid-cid` on
  malformed inputs."
  [x]
  (when (some? x)
    (let [raw (cond
                (string? x) x
                (instance? IpldLink x) (:cid x)
                (and (map? x) (contains? x "/")) (get x "/")
                (and (map? x) (contains? x :ipld/link)) (:ipld/link x)
                (and (map? x) (contains? x :ipld/cid)) (:ipld/cid x)
                (and (record? x) (contains? x :cid)) (:cid x)
                :else nil)]
      (when-not (valid-cid? raw)
        (fail! :invalid-cid
               (str "expected valid canonical CIDv1 or IPLD Link, got: " (pr-str x))
               {:value x :extracted raw}))
      raw)))

;; ── Safe Paint & URL Helpers ─────────────────────────────────────────────────

(def ^:private safe-hex-color-re #"^#[0-9a-fA-F]{6}$")

(defn safe-hex-color?
  "True iff `s` is a strict 6-digit hex color string like `#1d4ed8`."
  [s]
  (boolean (and (string? s) (re-matches safe-hex-color-re s))))

(defn assert-safe-hex-color!
  [field value]
  (when (some? value)
    (when-not (safe-hex-color? value)
      (fail! :invalid-color
             (str "paint field " field " must be a strict #RRGGBB hex color, got: " (pr-str value))
             {:field field :value value}))))

(defn safe-display-https-url
  "Return `url` only if it is a benign https:// URL with no whitespace or
  control characters; otherwise `nil`."
  [url]
  (when (and (string? url)
             (<= (count url) 1024)
             (re-matches #"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$" url))
    url))

;; ── Bounds Resolution & Pre-Count Enforcement ────────────────────────────────

(defn resolve-limits
  "Merge caller-supplied `:limits` with `default-limits`, refusing any unknown
  key, non-positive integer, or value exceeding `hard-limits`."
  [custom]
  (when (and (some? custom) (not (map? custom)))
    (fail! :invalid-limit "limits must be a map" {:limits custom}))
  (reduce-kv
   (fn [acc k v]
     (when-not (contains? hard-limits k)
       (fail! :invalid-limit
              (str "unknown limit key: " k)
              {:key k :allowed (sort (keys hard-limits))}))
     (when-not (and (integer? v) (pos? v))
       (fail! :invalid-limit
              (str "limit " k " must be a positive integer")
              {:key k :value v}))
     (let [ceil (get hard-limits k)]
       (when (> v ceil)
         (fail! :invalid-limit
                (str "limit " k " (" v ") exceeds hard ceiling (" ceil ")")
                {:key k :value v :ceiling ceil})))
     (assoc acc k v))
   default-limits
   (or custom {})))

(defn bounded-count-or-fail!
  "Check collection size against `limit` WITHOUT realizing more than `(inc limit)`
  items (prevents DoS on large or lazy inputs). Returns the bounded count."
  [coll limit reason field]
  (let [n (bounded-count (inc limit) coll)]
    (when (> n limit)
      (fail! reason
             (str field " count exceeds limit (" limit ")")
             {:field field :limit limit :observed-at-least n}))
    n))

(defn assert-label-length!
  "Refuse any label string exceeding `:max-label-length`."
  [limits field value]
  (when (some? value)
    (let [s (str value)
          n (count s)
          limit (:max-label-length limits)]
      (when (> n limit)
        (fail! :max-label-length-exceeded
               (str "label length (" n ") exceeds max-label-length (" limit ") for " field)
               {:field field :actual n :limit limit})))))

(defn assert-value-length!
  "Refuse any scalar value string exceeding `:max-value-length`."
  [limits field value]
  (when (some? value)
    (let [s (str value)
          n (count s)
          limit (:max-value-length limits)]
      (when (> n limit)
        (fail! :max-value-length-exceeded
               (str "value length (" n ") exceeds max-value-length (" limit ") for " field)
               {:field field :actual n :limit limit})))))

(defn assert-node-count! [limits actual]
  (let [limit (:max-nodes limits)]
    (when (> actual limit)
      (fail! :max-nodes-exceeded
             (str "node count (" actual ") exceeds max-nodes (" limit ")")
             {:actual actual :limit limit}))))

(defn assert-edge-count! [limits actual]
  (let [limit (:max-edges limits)]
    (when (> actual limit)
      (fail! :max-edges-exceeded
             (str "edge count (" actual ") exceeds max-edges (" limit ")")
             {:actual actual :limit limit}))))

(defn assert-join-count! [limits actual]
  (let [limit (:max-joins limits)]
    (when (> actual limit)
      (fail! :max-joins-exceeded
             (str "join count (" actual ") exceeds max-joins (" limit ")")
             {:actual actual :limit limit}))))

(defn assert-attributes-count! [limits node-id actual]
  (let [limit (:max-attributes-per-node limits)]
    (when (> actual limit)
      (fail! :max-attributes-exceeded
             (str "attribute count (" actual ") exceeds max-attributes-per-node (" limit ") on " node-id)
             {:node-id node-id :actual actual :limit limit}))))

;; ── Remote @context & Deep Structure Guards ──────────────────────────────────

(def ^:private remote-uri-re #"^\s*(https?|ftp|file|ws|wss|data|javascript|vbscript):")

(defn remote-uri-string?
  [x]
  (boolean (and (string? x) (re-find remote-uri-re (str/lower-case x)))))

(def ^:private kw-at-context (keyword "@context"))
(def ^:private kw-at-import (keyword "@import"))

(defn- assert-context-value-local! [ctx path]
  (cond
    (nil? ctx) nil
    (string? ctx)
    (fail! :remote-context-forbidden
           (str "remote or string @context reference is forbidden (offline fail-closed): " ctx)
           {:path path :context ctx})
    (map? ctx)
    (doseq [[k v] ctx]
      (when (and (or (= k "@import") (= k kw-at-import)) (some? v))
        (fail! :remote-context-forbidden
               "JSON-LD @import remote context directive is forbidden"
               {:path (conj path k) :value v})))
    (sequential? ctx)
    (doseq [[idx item] (map-indexed vector ctx)]
      (assert-context-value-local! item (conj path idx)))
    :else
    (fail! :remote-context-forbidden
           "unsupported @context value"
           {:path path :context ctx})))

(defn assert-bounded-and-no-remote-context!
  "Walk `data` enforcing `:max-depth`, `:max-collection-width`, `:max-value-length`,
  and rejecting any remote `@context` references or remote-fetch flags."
  [limits data]
  (let [max-depth (:max-depth limits)
        max-width (:max-collection-width limits)
        max-val-len (:max-value-length limits)]
    (letfn [(walk [x depth path]
              (when (> depth max-depth)
                (fail! :max-depth-exceeded
                       (str "nesting depth (" depth ") exceeds max-depth (" max-depth ")")
                       {:depth depth :limit max-depth :path path}))
              (cond
                (ipld-link? x)
                (do (extract-cid x) nil)

                (string? x)
                (when (> (count x) max-val-len)
                  (fail! :max-value-length-exceeded
                         (str "string value length (" (count x) ") exceeds max-value-length (" max-val-len ")")
                         {:actual (count x) :limit max-val-len :path path}))

                (map? x)
                (do
                  (when (pos? depth)
                    (bounded-count-or-fail! x max-width :max-collection-width-exceeded (pr-str path)))
                  (doseq [[k v] x]
                    (when (or (= k "@context") (= k kw-at-context))
                      (assert-context-value-local! v (conj path k)))
                    (when (and (or (= k :fetch-remote?)
                                   (= k :resolve-remote-context?)
                                   (= k :allow-remote-fetch?))
                               (true? v))
                      (fail! :remote-fetch-forbidden
                             (str "remote fetching is forbidden: " k)
                             {:flag k :path (conj path k)}))
                    (walk v (inc depth) (conj path k))))

                (or (sequential? x) (set? x))
                (do
                  (let [w-limit (if (= depth 1) (:max-input-items limits) max-width)]
                    (bounded-count-or-fail! x w-limit :max-collection-width-exceeded (pr-str path)))
                  (doseq [[idx item] (map-indexed vector x)]
                    (walk item (inc depth) (conj path idx))))

                :else nil))]
      (walk data 0 []))))

;; ── Top-level Projection Input Validation ────────────────────────────────────

(defn- assert-input-budget! [limits items kind]
  (when (some? items)
    (when-not (or (sequential? items) (set? items))
      (fail! :invalid-input
             (str kind " must be a sequence or set")
             {:field kind}))
    (bounded-count-or-fail! items (:max-input-items limits) :max-input-items-exceeded kind)))

(defn validate-input!
  "Validate the projection input map fail-closed and return resolved `:limits`."
  [input]
  (when-not (map? input)
    (fail! :invalid-input "projection input must be a map" {:type (str (type input))}))
  (let [limits (resolve-limits (:limits input))]
    ;; Enforce top-level collection budgets BEFORE full walk
    (when-let [onto (:ontology input)]
      (when-not (map? onto)
        (fail! :invalid-ontology "`:ontology` must be a registry map" {:ontology onto}))
      (assert-input-budget! limits (:object-types onto) :object-types))
    (when-let [conn (:connectors input)]
      (when-not (map? conn)
        (fail! :invalid-connector "`:connectors` must be a registry map" {:connectors conn}))
      (assert-input-budget! limits (:connectors conn) :connectors))
    (when-let [ks (:kotoba-schema input)]
      (when-not (or (map? ks) (sequential? ks))
        (fail! :invalid-kotoba-schema "`:kotoba-schema` must be a map or sequence" {:kotoba-schema ks}))
      (when (sequential? ks) (assert-input-budget! limits ks :kotoba-schema)))
    (assert-input-budget! limits (:facts input) :facts)
    (assert-input-budget! limits (:datoms input) :datoms)
    (assert-input-budget! limits (:quads input) :quads)
    (assert-input-budget! limits (:joins input) :joins)
    (when (:joins input)
      (bounded-count-or-fail! (:joins input) (:max-joins limits) :max-joins-exceeded :joins))
    (when-let [ipld-nodes (:ipld-nodes input)]
      (when-not (or (map? ipld-nodes) (sequential? ipld-nodes))
        (fail! :invalid-ipld-node "`:ipld-nodes` must be a map or sequence" {:ipld-nodes ipld-nodes}))
      (bounded-count-or-fail! ipld-nodes (:max-input-items limits) :max-input-items-exceeded :ipld-nodes))

    ;; Deep bounded walk (depth, collection width, value length, remote @context)
    (assert-bounded-and-no-remote-context! limits input)

    ;; Detailed domain field checks
    (when-let [onto (:ontology input)]
      (doseq [ot (:object-types onto)]
        (when-not (and (map? ot) (some? (:id ot)))
          (fail! :invalid-object-type "object type must be a map with :id" {:object-type ot}))
        (when (and (contains? ot :attributes) (not (map? (:attributes ot))))
          (fail! :invalid-object-type "object type :attributes must be a map" {:id (:id ot)}))
        (when-let [c (:cid ot)] (extract-cid c))
        (assert-label-length! limits :object-type/id (name (:id ot)))
        (assert-label-length! limits :object-type/name (:name ot))))

    (when-let [conn (:connectors input)]
      (doseq [c (:connectors conn)]
        (when-not (and (map? c) (some? (:id c)) (some? (:object-type c)))
          (fail! :invalid-connector "connector must be a map with :id and :object-type" {:connector c}))
        (when-let [cid (:cid c)] (extract-cid cid))
        (assert-label-length! limits :connector/id (name (:id c)))
        (assert-label-length! limits :connector/name (:name c))))

    (doseq [f (:facts input)]
      (when-not (map? f)
        (fail! :invalid-fact "fact must be a map" {:fact f})))

    (doseq [d (:datoms input)]
      (cond
        (vector? d)
        (when-not (<= 3 (count d) 5)
          (fail! :invalid-datom "vector datom must have 3 to 5 elements [e a v tx? added?]" {:datom d}))
        (map? d)
        (when-not (and (contains? d :e) (contains? d :a) (contains? d :v))
          (fail! :invalid-datom "map datom must contain :e, :a, and :v" {:datom d}))
        :else
        (fail! :invalid-datom "datom must be a vector or map" {:datom d})))

    (doseq [q (:quads input)]
      (when-not (and (map? q)
                     (contains? q :subject)
                     (contains? q :predicate)
                     (contains? q :object))
        (fail! :invalid-rdf-quad "RDF quad must be a map with :subject, :predicate, :object" {:quad q})))

    (doseq [j (:joins input)]
      (when-not (and (map? j) (some? (:from-attr j)) (some? (:to-attr j)))
        (fail! :invalid-join "join spec must be a map with :from-attr and :to-attr" {:join j}))
      (when-let [rule (:match-rule j)]
        (when-not (contains? valid-match-rules rule)
          (fail! :invalid-join
                 (str "unsupported join :match-rule " rule)
                 {:match-rule rule :allowed (sort valid-match-rules)})))
      (when-let [card (:cardinality j)]
        (when-not (contains? valid-cardinalities card)
          (fail! :invalid-join
                 (str "unsupported join :cardinality " card)
                 {:cardinality card :allowed (sort valid-cardinalities)})))
      (when-let [amb (:on-ambiguous j)]
        (when-not (contains? valid-ambiguous-modes amb)
          (fail! :invalid-join
                 (str "unsupported join :on-ambiguous mode " amb)
                 {:on-ambiguous amb :allowed (sort valid-ambiguous-modes)})))
      (when-let [sv (:source-values j)]
        (bounded-count-or-fail! sv (:max-collection-width limits) :max-collection-width-exceeded :join/source-values))
      (when-let [tv (:target-values j)]
        (bounded-count-or-fail! tv (:max-collection-width limits) :max-collection-width-exceeded :join/target-values))
      (when-let [ex (:exclude j)]
        (bounded-count-or-fail! ex (:max-collection-width limits) :max-collection-width-exceeded :join/exclude))
      (when-let [mp (:mapping j)]
        (when-not (map? mp)
          (fail! :invalid-join "join :mapping must be a map" {:join j}))
        (bounded-count-or-fail! mp (:max-collection-width limits) :max-collection-width-exceeded :join/mapping))
      (assert-label-length! limits :join/id (:id j))
      (assert-label-length! limits :join/description (:description j)))

    (when-let [ipld-nodes (:ipld-nodes input)]
      (let [entries (if (map? ipld-nodes) (seq ipld-nodes) ipld-nodes)]
        (doseq [entry entries]
          (if (map? ipld-nodes)
            (extract-cid (first entry))
            (do
              (when-not (map? entry)
                (fail! :invalid-ipld-node "IPLD node entry must be a map" {:entry entry}))
              (extract-cid (or (:cid entry) (:link entry))))))))

    (when-let [basis (:basis input)]
      (when-not (map? basis)
        (fail! :invalid-basis "`:basis` must be a map" {:basis basis}))
      (when-let [rc (:root-cid basis)] (extract-cid rc))
      (when-let [rl (:root-link basis)] (extract-cid rl))
      (when-let [ver (:cid-verification basis)]
        (when-not (contains? valid-cid-verification-states ver)
          (fail! :invalid-basis "`:cid-verification` must be :syntax-only or :verified" {:cid-verification ver})))
      (assert-label-length! limits :basis/source (:source basis)))
    limits))

;; ── Normalized Graph Boundary Validation (G3: No Unchecked Caller Bypass) ───

(defn- assert-finite-pos! [field val]
  (when-not (and (esc/finite-number? val) (pos? (double val)))
    (fail! :invalid-layout
           (str "layout field " field " must be a finite positive number, got: " (pr-str val))
           {:field field :value val})))

(defn- assert-finite-coord! [field val]
  (when-not (and (esc/finite-number? val) (>= (double val) 0.0))
    (fail! :invalid-layout
           (str "layout coordinate " field " must be a finite non-negative number, got: " (pr-str val))
           {:field field :value val})))

(defn validate-graph!
  "Fail-closed validation of any caller-supplied normalized `ontology.graph/v1`
  map at render/layout/filter/dispatch boundaries. Enforces schema version,
  resource bounds, finite layout dimensions, CIDv1 structure, and strict
  `#RRGGBB` paint allowlist."
  [graph]
  (when-not (map? graph)
    (fail! :invalid-graph "graph must be a map" {:type (str (type graph))}))
  (when-not (= "ontology.graph" (:schema/kind graph))
    (fail! :invalid-graph-schema
           (str "expected :schema/kind \"ontology.graph\", got: " (pr-str (:schema/kind graph)))
           {:schema/kind (:schema/kind graph)}))
  (when-not (= "ontology.graph/v1" (:schema/version graph))
    (fail! :invalid-graph-schema
           (str "unsupported :schema/version: " (pr-str (:schema/version graph)))
           {:schema/version (:schema/version graph)}))
  (let [basis (:basis graph)]
    (when-not (map? basis)
      (fail! :invalid-basis "graph :basis must be a map" {:basis basis}))
    (let [limits (resolve-limits (:bounds basis))
          nodes (:nodes graph)
          edges (:edges graph)
          layers (:layers graph)
          joins (:joins graph)]
      (when-not (sequential? nodes)
        (fail! :invalid-graph "graph :nodes must be sequential" {:nodes nodes}))
      (when-not (sequential? edges)
        (fail! :invalid-graph "graph :edges must be sequential" {:edges edges}))
      (when-not (sequential? layers)
        (fail! :invalid-graph "graph :layers must be sequential" {:layers layers}))
      (when (and (some? joins) (not (sequential? joins)))
        (fail! :invalid-graph "graph :joins must be sequential" {:joins joins}))
      (bounded-count-or-fail! nodes (:max-nodes limits) :max-nodes-exceeded :nodes)
      (bounded-count-or-fail! edges (:max-edges limits) :max-edges-exceeded :edges)
      (bounded-count-or-fail! layers (:max-nodes limits) :max-nodes-exceeded :layers)
      (when joins
        (bounded-count-or-fail! joins (:max-joins limits) :max-joins-exceeded :joins))
      (assert-bounded-and-no-remote-context! limits graph)
      (when-let [rc (:root-cid basis)] (extract-cid rc))
      (doseq [c (:cids basis)] (extract-cid c))
      (when-let [ver (:cid-verification basis)]
        (when-not (contains? valid-cid-verification-states ver)
          (fail! :invalid-basis "invalid :cid-verification in basis" {:cid-verification ver})))
      ;; Validate layers and paint fields strictly
      (doseq [l layers]
        (when-not (and (map? l) (string? (:id l)) (not (str/blank? (:id l))))
          (fail! :invalid-layer "layer must be a map with non-empty string :id" {:layer l}))
        (assert-label-length! limits :layer/id (:id l))
        (assert-label-length! limits :layer/label (:label l))
        (assert-safe-hex-color! :layer/color (:color l))
        (assert-safe-hex-color! :layer/bg (:bg l))
        (when (contains? l :node-count)
          (when-not (and (integer? (:node-count l)) (not (neg? (:node-count l))))
            (fail! :invalid-layer "layer :node-count must be a non-negative integer" {:layer l}))))
      ;; Validate nodes
      (doseq [n nodes]
        (when-not (and (map? n) (string? (:id n)) (not (str/blank? (:id n)))
                       (string? (:layer n)) (not (str/blank? (:layer n))))
          (fail! :invalid-node "node must be a map with non-empty string :id and :layer" {:node n}))
        (assert-label-length! limits :node/id (:id n))
        (assert-label-length! limits :node/label (:label n))
        (assert-label-length! limits :node/layer (:layer n))
        (when-let [k (:kind n)]
          (when-not (contains? valid-node-kinds k)
            (fail! :invalid-node (str "unsupported node :kind " (pr-str k)) {:node-id (:id n) :kind k})))
        (when-let [c (:cid n)] (extract-cid c))
        (when-let [attrs (:attributes n)]
          (when-not (map? attrs)
            (fail! :invalid-node "node :attributes must be a map" {:node-id (:id n)}))
          (assert-attributes-count! limits (:id n) (count attrs)))
        (when-let [lay (:layout n)]
          (when-not (map? lay)
            (fail! :invalid-layout "node :layout must be a map" {:node-id (:id n)}))
          (assert-finite-coord! :layout/x (:x lay))
          (assert-finite-coord! :layout/y (:y lay))
          (assert-finite-pos! :layout/width (:width lay))
          (assert-finite-pos! :layout/height (:height lay))))
      ;; Validate edges
      (doseq [e edges]
        (when-not (and (map? e) (string? (:id e)) (string? (:source e)) (string? (:target e)))
          (fail! :invalid-edge "edge must be a map with string :id, :source, :target" {:edge e}))
        (assert-label-length! limits :edge/id (:id e))
        (assert-label-length! limits :edge/label (:label e))
        (when-let [k (:kind e)]
          (when-not (contains? valid-edge-kinds k)
            (fail! :invalid-edge (str "unsupported edge :kind " (pr-str k)) {:edge-id (:id e) :kind k})))
        (when-let [c (:cid e)] (extract-cid c)))
      ;; Validate joins
      (doseq [j joins]
        (when-not (and (map? j) (string? (:id j)) (string? (:from-attr j)) (string? (:to-attr j)))
          (fail! :invalid-join "normalized join must have string :id, :from-attr, :to-attr" {:join j}))
        (assert-label-length! limits :join/id (:id j))
        (assert-label-length! limits :join/description (:description j))
        (doseq [ck [:matched-count :unmatched-count :excluded-count :total-source-count :eligible-count]]
          (when (contains? j ck)
            (let [cv (get j ck)]
              (when-not (and (integer? cv) (not (neg? cv)))
                (fail! :invalid-join (str "join " ck " must be a non-negative integer") {:join-id (:id j) :field ck :value cv})))))
        (when (some? (:coverage j))
          (let [cov (:coverage j)]
            (when-not (and (esc/finite-number? cov) (<= 0.0 (double cov) 1.0))
              (fail! :invalid-join "join :coverage must be finite in [0.0, 1.0]" {:join-id (:id j) :coverage cov})))))
      ;; Validate canvas layout if present
      (when-let [lay (:layout graph)]
        (when-not (map? lay)
          (fail! :invalid-layout "graph :layout must be a map" {:layout lay}))
        (assert-finite-pos! :canvas/width (:width lay))
        (assert-finite-pos! :canvas/height (:height lay))
        (when-let [dir (:direction lay)]
          (when-not (contains? #{:horizontal :vertical} dir)
            (fail! :invalid-layout "layout :direction must be :horizontal or :vertical" {:direction dir}))))
      limits)))
