(ns nostr.event
  "Pure NIP-01 event semantics: canonical serialization, id computation/
  verification, signature verification, and subscription filter matching.
  Zero I/O, zero storage — nostr.relay wires this to kotobase.store and the
  WebSocket transport.

  REQUIRED EVENT FIELDS (NIP-01): id, pubkey, created_at, kind, tags,
  content, sig — all required, `validate` rejects anything missing one.

  Event map shape used throughout this repo (string keys, matching the wire
  JSON exactly — NOT keywordized, per this repo's nostr.json convention):
    {\"id\" \"<64-hex>\" \"pubkey\" \"<64-hex>\" \"created_at\" <int>
     \"kind\" <int> \"tags\" [[\"e\" \"...\"] ...] \"content\" \"...\"
     \"sig\" \"<128-hex>\"}"
  (:require [kotoba.lang.text :as str]
            [nostr.crypto :as crypto]
            [nostr.json :as json]))

;; ------------------------------------------------------ canonical serialize

(defn- escape-canonical
  "NIP-01's canonical-serialization string escaping: ONLY the 7 named
  characters get a backslash escape; every other byte (including all other
  control characters and all non-ASCII Unicode) is emitted as literal UTF-8.
  This is narrower than general JSON (nostr.json/encode) and MUST be used
  for id computation specifically — using the general encoder here would
  compute a different id than every other Nostr implementation for any
  content containing an escaped-but-not-NIP-01-named control character."
  [s]
  (let [n (count s)]
    (loop [i 0 acc (transient [])]
      (if (= i n)
        (apply str (persistent! acc))
        (let [c (subs s i (inc i))
              piece (case c
                      "\"" "\\\""
                      "\\" "\\\\"
                      "\n" "\\n"
                      "\r" "\\r"
                      "\t" "\\t"
                      "\b" "\\b"
                      "\f" "\\f"
                      c)]
          (recur (inc i) (conj! acc piece)))))))

(defn- canonical-json
  "Minimal JSON encoder used ONLY for the canonical id-computation array —
  deliberately separate from nostr.json/encode, see escape-canonical."
  [x]
  (cond
    (nil? x)     "null"
    (true? x)    "true"
    (false? x)   "false"
    (number? x)  (str x)
    (string? x)  (str "\"" (escape-canonical x) "\"")
    (sequential? x) (str "[" (str/join "," (map canonical-json x)) "]")
    :else (throw (ex-info "canonical-json: unsupported value in NIP-01 id array" {:value x}))))

(defn canonical-serialize
  "NIP-01 canonical serialization: [0, pubkey, created_at, kind, tags,
  content] as a compact JSON string (no whitespace), used as the sha256
  preimage for the event id."
  [{:strs [pubkey created_at kind tags content]}]
  (canonical-json [0 pubkey created_at kind (or tags []) content]))

(defn compute-id
  "sha256 hex of the canonical serialization — this repo's `id` value."
  [event]
  (crypto/sha256-of-str (canonical-serialize event)))

;; --------------------------------------------------------------- validate

(def required-fields ["id" "pubkey" "created_at" "kind" "tags" "content" "sig"])

(defn- hex-of-len? [len s]
  (and (string? s) (= len (count s)) (re-matches #"(?i)[0-9a-f]+" s)))

(defn structurally-valid?
  "Every required field present with the right shape (hex lengths, tags is
  an array of arrays of strings, created_at/kind are integers). Does NOT
  check id/signature — see `valid?` for the full check."
  [event]
  (and (map? event)
       (every? #(contains? event %) required-fields)
       (hex-of-len? 64 (get event "id"))
       (hex-of-len? 64 (get event "pubkey"))
       (integer? (get event "created_at"))
       (integer? (get event "kind"))
       (vector? (get event "tags"))
       (every? (fn [tag] (and (vector? tag) (every? string? tag))) (get event "tags"))
       (string? (get event "content"))
       (hex-of-len? 128 (get event "sig"))))

(defn id-matches?
  "The event's claimed id actually equals sha256 of its canonical serialization."
  [event]
  (= (get event "id") (compute-id event)))

(defn signature-valid?
  "BIP-340 schnorr signature over the (raw bytes of the) event id, using the
  event's own pubkey. Delegates to nostr.crypto/schnorr-verify — REAL
  verification, see that namespace's docstring."
  [event]
  (crypto/schnorr-verify (get event "pubkey")
                          (crypto/hex->bytes (get event "id"))
                          (get event "sig")))

(defn validate
  "Full NIP-01 event acceptance check: structural shape, id matches its own
  canonical serialization, and the signature verifies. Returns {:valid? bool
  :reason (nil or keyword)}."
  [event]
  (cond
    (not (structurally-valid? event))
    {:valid? false :reason :malformed}

    (not (id-matches? event))
    {:valid? false :reason :id-mismatch}

    (not (signature-valid? event))
    {:valid? false :reason :invalid-signature}

    :else {:valid? true :reason nil}))

;; ------------------------------------------------------------- tag lookups

(defn tag-values
  "All values (position 1) of tags named `tag-name`, e.g. (tag-values ev \"e\")."
  [event tag-name]
  (into [] (comp (filter #(= tag-name (first %))) (map second)) (get event "tags")))

;; ---------------------------------------------------------- filter matching

(defn- field-matches? [event k vs]
  (or (empty? vs) (some #(= % (get event k)) vs)))

(defn- tag-matches? [event tag-char vs]
  (or (empty? vs) (some (set vs) (tag-values event tag-char))))

(defn matches-filter?
  "NIP-01 REQ filter matching over one stored event. `filt` uses string
  keys exactly as they arrive on the wire: \"ids\" \"authors\" \"kinds\"
  \"#e\" \"#p\" \"since\" \"until\" \"limit\". `limit` is NOT applied here
  (it's a result-count cap the caller applies after matching, not a
  per-event predicate) — see nostr.relay/run-filter."
  [event filt]
  (let [{:strs [ids authors kinds since until]} filt]
    (and (field-matches? event "id" ids)
         (field-matches? event "pubkey" authors)
         (field-matches? event "kind" kinds)
         (or (nil? since) (>= (get event "created_at") since))
         (or (nil? until) (<= (get event "created_at") until))
         (every? (fn [[k vs]]
                   (if (and (str/starts-with? k "#") (= 2 (count k)))
                     (tag-matches? event (subs k 1 2) vs)
                     true))
                 filt))))

(defn run-filter
  "Apply `matches-filter?` over `events`, sort newest-first (NIP-01 REQ
  default), then cap at (get filt \"limit\") if present."
  [events filt]
  (let [matched (->> events
                      (filter #(matches-filter? % filt))
                      (sort-by #(get % "created_at") >))]
    (if-let [limit (get filt "limit")]
      (vec (take limit matched))
      (vec matched))))

(defn run-filters
  "OR of multiple filters (NIP-01 REQ takes a list of filters — an event
  matching ANY one of them is included), de-duplicated by id, newest-first.
  Per-filter :limit is honored per-filter before the union, matching typical
  relay behavior (each filter's own cap, not a global cap)."
  [events filters]
  (->> filters
       (mapcat #(run-filter events %))
       (reduce (fn [{:keys [seen out]} ev]
                 (if (contains? seen (get ev "id"))
                   {:seen seen :out out}
                   {:seen (conj seen (get ev "id")) :out (conj out ev)}))
               {:seen #{} :out []})
       :out
       (sort-by #(get % "created_at") >)
       vec))
