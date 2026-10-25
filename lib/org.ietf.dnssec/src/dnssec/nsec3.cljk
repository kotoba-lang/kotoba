(ns dnssec.nsec3
  "NSEC3 — hashed denial of existence (RFC 5155).

  NSEC proves a name does not exist by handing you the two names that surround
  it. That works, and it also means anyone can walk the chain and read out
  **every name in the zone**, one query at a time. For a registry whose name
  list is its business, that is not a theoretical concern.

  NSEC3 replaces the plaintext neighbours with *hashes* of them. A validator
  can still confirm the queried name falls between two hashes; it cannot turn
  those hashes back into names without guessing them.

  ## Why the iterations count is not a security dial

  The obvious reading is that more iterations means more work for an attacker,
  so higher is safer. It is not:

  - The attacker guesses **once per candidate name** and pays the iterations
    once. Zone names are short, structured and drawn from dictionaries, so the
    guessing cost is dominated by the candidate list, not the hash.
  - The **validator** pays the same cost on **every negative answer**, and an
    authoritative server pays it for every query it denies. A high count is a
    denial-of-service amplifier pointed at yourself.

  RFC 9276 (best current practice) concluded the same and recommends
  **`iterations = 0` and an empty salt**. This library defaults to that and
  refuses more than `max-iterations`, because a knob that only hurts the person
  turning it should be hard to turn.

  ## Opt-out is not implemented, deliberately

  The Opt-Out flag lets a zone skip NSEC3 records for unsigned delegations,
  which is why large TLDs adopted it — but it also means the zone can no longer
  prove those delegations do *not* exist, so a name can be inserted without
  detection. That is a real trade-off a registry may want, and it is a
  different security model rather than a parameter; `flags` is carried on the
  wire so an existing zone round-trips, and this library will not *produce* a
  zone that uses it."
  (:require [dnssec.canonical :as c]
            [dnssec.sign :as sign]))

(def ^:const hash-sha1
  "The only hash algorithm RFC 5155 defines, and the only one IANA has
  registered. SHA-1's collision weakness is not load-bearing here — NSEC3
  needs preimage resistance, not collision resistance — but the value is fixed
  by the protocol either way, so there is nothing to choose."
  1)

(def ^:const max-iterations
  "RFC 9276 §3.1 recommends 0. Resolvers in the field treat high counts as
  hostile and some return SERVFAIL above 100; this refuses anything above a
  small bound so a zone cannot be signed into a state validators will reject."
  16)

(def ^:const default-iterations 0)
(def ^:const default-salt [])

(defn- ->bytes [v]
  #?(:clj (byte-array (map unchecked-byte v))
     :cljs (js/Uint8Array.from (clj->js (vec v)))))

(defn- ->octets [b]
  (mapv #(bit-and % 0xFF) (vec (seq #?(:clj b :cljs (array-seq b))))))

(defn hash-name
  "The NSEC3 hash of a name (RFC 5155 §5):

      IH(salt, x, 0) = H(x || salt)
      IH(salt, x, k) = H(IH(salt, x, k-1) || salt)

  where `x` is the **canonical wire form of the name** — lowercased and
  uncompressed, not the text. Hashing the text produces a chain that no
  validator can reproduce, and the symptom is a zone whose negative answers
  never validate while every positive answer does.

  The salt is appended at **every** iteration, not just the first. Applying it
  once is the common implementation error, and it also produces a chain nobody
  else computes.

  `sha1-fn` is injected for the same reason the rest of this library injects
  crypto — see `dnssec.provider`, which supplies one."
  [sha1-fn name {:keys [salt iterations]
                 :or {salt default-salt iterations default-iterations}}]
  (when (> iterations max-iterations)
    (throw (ex-info "NSEC3 iterations above the supported bound; RFC 9276 recommends 0"
                    {:iterations iterations :max max-iterations})))
  (let [salt (vec salt)
        h (fn [octets] (->octets (sha1-fn (->bytes octets))))]
    (loop [digest (h (into (vec (c/encode-name name)) salt))
           k 0]
      (if (>= k iterations)
        digest
        (recur (h (into digest salt)) (inc k))))))

;; ── base32hex, the encoding NSEC3 owner names use ─────────────────────────

(def ^:private b32hex-alphabet "0123456789ABCDEFGHIJKLMNOPQRSTUV")

(defn base32hex
  "RFC 4648 base32**hex** — the extended-hex alphabet, **not** standard base32.

  This is the one that trips people: standard base32 uses `A-Z2-7`, and
  base32hex uses `0-9A-V`. They differ in every symbol, so encoding an NSEC3
  hash with the wrong one yields an owner name that sorts differently and
  matches nothing. The whole chain then proves nothing, while looking correct.

  Unpadded, because NSEC3 owner names carry no `=`."
  [octets]
  (let [bits (apply str (map #(let [b #?(:clj (Integer/toBinaryString (bit-and % 0xFF))
                                        :cljs (.toString (bit-and % 0xFF) 2))]
                               (str (apply str (repeat (- 8 (count b)) "0")) b))
                             octets))
        chunks (map #(apply str %) (partition-all 5 bits))]
    (apply str
           (for [ch chunks
                 :let [padded (str ch (apply str (repeat (- 5 (count ch)) "0")))]]
             (nth b32hex-alphabet
                  #?(:clj (Integer/parseInt padded 2)
                     :cljs (js/parseInt padded 2)))))))

(defn owner-name
  "The NSEC3 record's owner: `<base32hex(hash)>.<zone apex>`."
  [hash-octets apex]
  (str (base32hex hash-octets) "." (c/canonical-name apex)))

;; ── records ───────────────────────────────────────────────────────────────

(defn params-rdata
  "The shared parameter block every NSEC3 and NSEC3PARAM record starts with:
  hash algorithm, flags, iterations, salt length, salt."
  [{:keys [flags salt iterations]
    :or {flags 0 salt default-salt iterations default-iterations}}]
  (-> (vec (c/u8 hash-sha1))
      (into (c/u8 flags))
      (into (c/u16 iterations))
      (into (c/u8 (count salt)))
      (into (vec salt))))

(defn nsec3param
  "The NSEC3PARAM record at the apex. It tells a resolver which parameters to
  hash a queried name with — without it, a validator cannot compute the hash it
  needs to look for, so a fully signed NSEC3 zone still fails to prove
  nonexistence."
  [{:keys [apex ttl] :as opts}]
  {:zone/name (c/canonical-name apex)
   :zone/type "NSEC3PARAM"
   :zone/class "IN"
   :zone/ttl (or ttl 3600)
   :zone/rdata {:zone/raw (params-rdata opts)}})

(defn nsec3
  "One NSEC3 record: this hash, the **next** hash in order, and the types that
  exist at the name this hash came from."
  [{:keys [hash next-hash types apex ttl] :as opts}]
  {:zone/name (owner-name hash apex)
   :zone/type "NSEC3"
   :zone/class "IN"
   :zone/ttl (or ttl 3600)
   :zone/rdata {:zone/raw (-> (params-rdata opts)
                              (into (c/u8 (count next-hash)))
                              (into (vec next-hash))
                              (into (sign/type-bitmap types)))}
   :nsec3/hash hash
   :nsec3/next next-hash})

(defn chain
  "Build the NSEC3 chain for a zone.

  The records are ordered by **hash**, not by name — that reordering is the
  entire point, since it is what stops the chain from revealing the zone's
  alphabetical structure. And like NSEC, the chain is **circular**: the last
  hash points at the first, so a queried name hashing beyond the largest hash
  is still covered. Stopping at the last one leaves that whole range unprovable
  and those queries fail rather than returning a proven NXDOMAIN.

  Every NSEC3 asserts `RRSIG` at its own name, because the record is signed
  once the zone is."
  [sha1-fn records {:keys [apex ttl] :as opts}]
  (let [by-name (group-by #(c/canonical-name (:zone/name %)) records)
        hashed (->> (keys by-name)
                    (map (fn [nm]
                           {:name nm
                            :hash (hash-name sha1-fn nm opts)
                            :types (into #{"RRSIG"} (map :zone/type (get by-name nm)))}))
                    (sort-by :hash c/compare-bytes)
                    vec)]
    (when (seq hashed)
      (mapv (fn [[cur nxt]]
              (nsec3 (merge opts
                            {:hash (:hash cur)
                             :next-hash (:hash (or nxt (first hashed)))
                             :types (:types cur)
                             :apex apex :ttl ttl})))
            (map vector hashed (concat (rest hashed) [nil]))))))

(defn covers?
  "Does this NSEC3 record cover `hash` — i.e. does the hash fall strictly
  between its own and its successor?

  The wrap-around case is why this is a function rather than two comparisons:
  for the last record in the chain, `next` is *smaller* than `hash`, and the
  covered range is everything above `hash` **or** below `next`. Writing it as a
  plain `<` range silently fails to cover exactly that interval, which is the
  one an attacker would aim at."
  [record hash]
  (let [lo (:nsec3/hash record)
        hi (:nsec3/next record)
        after-lo (pos? (c/compare-bytes hash lo))
        before-hi (neg? (c/compare-bytes hash hi))]
    (if (neg? (c/compare-bytes lo hi))
      (and after-lo before-hi)                 ; ordinary interval
      (or after-lo before-hi))))               ; the wrap at the end of the chain

(defn hex [octets] (c/hex octets))
