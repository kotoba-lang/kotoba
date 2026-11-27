(ns kotoba.ontology-viz.validate
  "Fail-closed input validation, explicit safety bounds, remote-context guards,
  and portable IPLD CIDv1 / Link helpers."
  (:require [clojure.string :as str]))

(def default-limits
  "Default resource bounds enforced on every projection and render."
  {:max-nodes 500
   :max-edges 2000
   :max-label-length 256
   :max-depth 16
   :max-joins 128
   :max-attributes-per-node 64
   :max-input-items 10000})

(def hard-limits
  "Absolute ceilings that caller-supplied `:limits` may never exceed."
  {:max-nodes 5000
   :max-edges 20000
   :max-label-length 1024
   :max-depth 64
   :max-joins 1024
   :max-attributes-per-node 512
   :max-input-items 50000})

(def valid-match-rules
  #{:exact :exact-uppercase :exact-lowercase :prefix :mapping})

(def valid-cardinalities
  #{:one-to-one :one-to-many :many-to-one :many-to-many})

(defn fail!
  "Throw a structured ex-info refusal with an explicit `:reason` keyword."
  [reason message data]
  (throw (ex-info message (assoc data :reason reason))))

;; ── Portable IPLD Link & CIDv1 helpers ───────────────────────────────────────

;; Base32lower CIDv1 (multibase 'b', typically 59+ chars like bafy... / bafk...,
;; minimum realistic CIDv1 base32 length >= 16), base16 ('f'), base58btc ('z'),
;; or base64url ('u'). Rejects whitespace, angle brackets, quotes, and short tokens.
(def ^:private cidv1-base32-re #"^b[a-z2-7]{15,256}$")
(def ^:private cidv1-base16-re #"^f[0-9a-f]{16,256}$")
(def ^:private cidv1-base58-re #"^z[1-9A-HJ-NP-Za-km-z]{16,256}$")
(def ^:private cidv1-base64url-re #"^u[A-Za-z0-9_-]{16,256}$")

(defn valid-cid?
  "True when `s` is a structurally valid multibase CIDv1 string (no whitespace,
  no control chars, valid multibase prefix and alphabet)."
  [s]
  (boolean
   (and (string? s)
        (or (re-matches cidv1-base32-re s)
            (re-matches cidv1-base16-re s)
            (re-matches cidv1-base58-re s)
            (re-matches cidv1-base64url-re s)))))

(defrecord IpldLink [cid])

(defn ipld-link
  "Construct a portable IPLD Link wrapper after validating CIDv1 syntax."
  [cid]
  (when-not (valid-cid? cid)
    (fail! :invalid-cid
           (str "invalid CIDv1 string: " (pr-str cid))
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
  "Extract and validate a CIDv1 string from an IPLD Link wrapper or raw CID
  string. Returns `nil` for `nil`; fails closed with `:invalid-cid` on
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
               (str "expected valid CIDv1 or IPLD Link, got: " (pr-str x))
               {:value x :extracted raw}))
      raw)))

;; ── Bounds resolution & enforcement ──────────────────────────────────────────

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

;; ── Remote @context & external fetch guards ──────────────────────────────────

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
  "Walk `data` up to `(:max-depth limits)`, refusing excessive nesting depth
  and rejecting any remote `@context` references or remote-fetch flags."
  [limits data]
  (let [max-depth (:max-depth limits)]
    (letfn [(walk [x depth path]
              (when (> depth max-depth)
                (fail! :max-depth-exceeded
                       (str "nesting depth (" depth ") exceeds max-depth (" max-depth ")")
                       {:depth depth :limit max-depth :path path}))
              (cond
                (ipld-link? x)
                (do (extract-cid x) nil)

                (map? x)
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
                  (walk v (inc depth) (conj path k)))

                (or (sequential? x) (set? x))
                (doseq [[idx item] (map-indexed vector x)]
                  (walk item (inc depth) (conj path idx)))

                :else nil))]
      (walk data 0 []))))

(defn safe-display-https-url
  "Return `url` only if it is a benign https:// URL with no whitespace or
  control characters; otherwise `nil`."
  [url]
  (when (and (string? url)
             (re-matches #"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$" url))
    url))

;; ── Top-level input structural validation ────────────────────────────────────

(defn- assert-input-budget! [limits items kind]
  (when (some? items)
    (when-not (or (sequential? items) (set? items))
      (fail! :invalid-input
             (str kind " must be a sequence or set")
             {:field kind}))
    (let [n (count items)
          limit (:max-input-items limits)]
      (when (> n limit)
        (fail! :max-input-items-exceeded
               (str kind " count (" n ") exceeds max-input-items (" limit ")")
               {:field kind :actual n :limit limit})))))

(defn validate-input!
  "Validate the projection input map fail-closed and return resolved `:limits`."
  [input]
  (when-not (map? input)
    (fail! :invalid-input "projection input must be a map" {:type (str (type input))}))
  (let [limits (resolve-limits (:limits input))]
    (assert-bounded-and-no-remote-context! limits input)
    ;; Ontology registry
    (when-let [onto (:ontology input)]
      (when-not (map? onto)
        (fail! :invalid-ontology "`:ontology` must be a registry map" {:ontology onto}))
      (let [otypes (:object-types onto)]
        (assert-input-budget! limits otypes :object-types)
        (doseq [ot otypes]
          (when-not (and (map? ot) (some? (:id ot)))
            (fail! :invalid-object-type "object type must be a map with :id" {:object-type ot}))
          (when (and (contains? ot :attributes) (not (map? (:attributes ot))))
            (fail! :invalid-object-type "object type :attributes must be a map" {:id (:id ot)}))
          (when-let [c (:cid ot)] (extract-cid c))
          (assert-label-length! limits :object-type/id (name (:id ot)))
          (assert-label-length! limits :object-type/name (:name ot)))))
    ;; Connector registry
    (when-let [conn (:connectors input)]
      (when-not (map? conn)
        (fail! :invalid-connector "`:connectors` must be a registry map" {:connectors conn}))
      (let [rows (:connectors conn)]
        (assert-input-budget! limits rows :connectors)
        (doseq [c rows]
          (when-not (and (map? c) (some? (:id c)) (some? (:object-type c)))
            (fail! :invalid-connector "connector must be a map with :id and :object-type" {:connector c}))
          (when-let [cid (:cid c)] (extract-cid cid))
          (assert-label-length! limits :connector/id (name (:id c)))
          (assert-label-length! limits :connector/name (:name c)))))
    ;; Kotoba schema (ontology.kotoba EDN attributes/classes)
    (when-let [ks (:kotoba-schema input)]
      (when-not (or (map? ks) (sequential? ks))
        (fail! :invalid-kotoba-schema "`:kotoba-schema` must be a map or sequence of attribute/class declarations"
               {:kotoba-schema ks}))
      (when (sequential? ks)
        (assert-input-budget! limits ks :kotoba-schema)))
    ;; Tagged facts
    (assert-input-budget! limits (:facts input) :facts)
    (doseq [f (:facts input)]
      (when-not (map? f)
        (fail! :invalid-fact "fact must be a map" {:fact f})))
    ;; EAVT datoms
    (assert-input-budget! limits (:datoms input) :datoms)
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
    ;; RDF quads
    (assert-input-budget! limits (:quads input) :quads)
    (doseq [q (:quads input)]
      (when-not (and (map? q)
                     (contains? q :subject)
                     (contains? q :predicate)
                     (contains? q :object))
        (fail! :invalid-rdf-quad "RDF quad must be a map with :subject, :predicate, :object" {:quad q})))
    ;; Joins
    (assert-input-budget! limits (:joins input) :joins)
    (assert-join-count! limits (count (:joins input)))
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
      (assert-label-length! limits :join/id (:id j))
      (assert-label-length! limits :join/description (:description j)))
    ;; IPLD nodes
    (when-let [ipld-nodes (:ipld-nodes input)]
      (when-not (or (map? ipld-nodes) (sequential? ipld-nodes))
        (fail! :invalid-ipld-node "`:ipld-nodes` must be a map {cid -> node} or sequence of {:cid ... :node ...}"
               {:ipld-nodes ipld-nodes}))
      (let [entries (if (map? ipld-nodes) (seq ipld-nodes) ipld-nodes)]
        (assert-input-budget! limits entries :ipld-nodes)
        (doseq [entry entries]
          (if (map? ipld-nodes)
            (extract-cid (first entry))
            (do
              (when-not (map? entry)
                (fail! :invalid-ipld-node "IPLD node entry must be a map" {:entry entry}))
              (extract-cid (or (:cid entry) (:link entry))))))))
    ;; Basis
    (when-let [basis (:basis input)]
      (when-not (map? basis)
        (fail! :invalid-basis "`:basis` must be a map" {:basis basis}))
      (when-let [rc (:root-cid basis)] (extract-cid rc))
      (when-let [rl (:root-link basis)] (extract-cid rl))
      (assert-label-length! limits :basis/source (:source basis)))
    limits))
