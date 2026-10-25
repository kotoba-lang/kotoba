(ns dnssec.canonical
  "Canonical forms — RFC 4034 §6. This is the whole foundation of DNSSEC and
  the part that silently breaks everything downstream when it is wrong.

  A signature is over *bytes*. If a validator serializes an RRset even one byte
  differently from the signer, every signature fails and the zone goes bogus —
  which looks like a key problem, a clock problem, or a resolver problem, and is
  none of them. So §6 fixes three things exactly:

  **Canonical name form.** All uppercase ASCII letters in owner names are
  lowercased, and names are written **uncompressed**. This is why this namespace
  has its own encoder instead of reusing `nameserver.wire`'s: that one applies
  RFC 1035 name compression, which is correct for a message and fatal here,
  because a compressed name's bytes depend on what else is in the message. The
  same RRset would then sign differently depending on which query produced it.

  **Canonical RR form.** Owner name in canonical form; the **original TTL**
  from the RRSIG, not whatever TTL the record currently carries (a cached copy
  has a decremented TTL and would otherwise fail against a signature made at
  the authoritative server); and, for a fixed list of RR types, embedded domain
  names in the RDATA lowercased too.

  **Canonical RR ordering.** Within an RRset, records sort by their RDATA as
  unsigned left-justified octet sequences — a plain byte comparison, not a
  parse-and-compare. Two servers that order an RRset differently produce
  different signed blobs from the same records.

  There is a fourth ordering, for *names* rather than records, used to build the
  NSEC chain: labels compared right to left, each label as lowercased octets.
  `example.com` sorts before `a.example.com` because the comparison starts at
  the rightmost label and a shorter name is a prefix. Sorting names as ordinary
  strings — the obvious mistake — puts `a.example.com` first and produces an
  NSEC chain that proves nonexistence of the wrong things."
  (:require [kotoba.lang.text :as str]))

;; ── bytes ─────────────────────────────────────────────────────────────────

(defn- char-code [c]
  #?(:clj (int c) :cljs (.charCodeAt c 0)))

(defn ascii-bytes [s] (mapv char-code (seq s)))

(defn u8  [n] [(bit-and n 0xFF)])
(defn u16 [n] [(bit-and (bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn u32 [n] [(bit-and (bit-shift-right n 24) 0xFF)
               (bit-and (bit-shift-right n 16) 0xFF)
               (bit-and (bit-shift-right n 8) 0xFF)
               (bit-and n 0xFF)])

;; ── names ─────────────────────────────────────────────────────────────────

(defn labels
  "Split a name into its labels, dropping the root's empty final label.
  `\".\"` is zero labels, which is what makes the root sort before everything."
  [name]
  (let [n (-> (str name) (str/replace #"\.$" ""))]
    (if (str/blank? n) [] (str/split n #"\."))))

(defn canonical-name
  "Lowercased, trailing-dot form. RFC 4034 §6.1 — only uppercase *ASCII*
  letters are folded, which matters for names carrying bytes above 0x7F: a
  locale-aware or Unicode-aware lower-casing would change octets the spec
  requires to be left alone."
  [name]
  (let [ls (labels name)]
    (if (empty? ls)
      "."
      (str (str/join "." (map #(str/lower %) ls)) "."))))

(defn encode-name
  "Uncompressed wire form of a canonical name: each label length-prefixed, a
  zero octet for root. **Never compressed** — see the namespace docstring."
  [name]
  (into (vec (mapcat (fn [l] (into [(count l)] (ascii-bytes l)))
                     (map str/lower (labels name))))
        [0]))

(defn compare-bytes
  "Compare two octet sequences as unsigned, left-justified — the comparison
  RFC 4034 §6.3 specifies. A shorter sequence that is a prefix of a longer one
  sorts first."
  [a b]
  (loop [i 0]
    (cond
      (and (>= i (count a)) (>= i (count b))) 0
      (>= i (count a)) -1
      (>= i (count b)) 1
      :else (let [x (bit-and (nth a i) 0xFF)
                  y (bit-and (nth b i) 0xFF)]
              (if (= x y) (recur (inc i)) (if (< x y) -1 1))))))

(defn compare-names
  "Canonical DNS name order (RFC 4034 §6.1): compare **label by label from the
  right**, each label as lowercased octets.

  This is not string order. `example.com` precedes `a.example.com` because a
  name with fewer labels sorts first when it is a suffix. And
  `z.a.example.com` precedes `a.b.example.com` — the rightmost labels tie, then
  `a` beats `b`, and the leftmost label never gets a say. String order
  disagrees there, and every place it disagrees produces an NSEC chain that
  proves the nonexistence of names that do exist."
  [a b]
  (let [la (reverse (map str/lower (labels a)))
        lb (reverse (map str/lower (labels b)))]
    (loop [xs la ys lb]
      (cond
        (and (empty? xs) (empty? ys)) 0
        (empty? xs) -1
        (empty? ys) 1
        :else
        (let [c (compare-bytes (ascii-bytes (first xs)) (ascii-bytes (first ys)))]
          (if (zero? c) (recur (rest xs) (rest ys)) c))))))

(defn sort-names [names]
  (vec (sort compare-names names)))

;; ── RDATA ─────────────────────────────────────────────────────────────────

(def rdata-name-types
  "RR types whose RDATA contains a domain name that RFC 4034 §6.2 requires to
  be **lowercased** in canonical form. The list is closed and explicit in the
  RFC; types added later are deliberately *not* included, because §6.2 was
  amended (RFC 6840 §5.1) to stop extending it — a validator and a signer that
  disagree about whether a newer type's embedded name is folded produce
  different bytes."
  #{"NS" "CNAME" "SOA" "PTR" "MX" "SRV" "DNAME" "RP" "AFSDB" "RT"
    "NAPTR" "KX" "SIG" "NXT" "MINFO" "MD" "MF" "MB" "MG" "MR" "HINFO"})

(defn- ipv4-bytes [s]
  (mapv #?(:clj #(Integer/parseInt %) :cljs #(js/parseInt % 10)) (str/split s #"\.")))

(defn- ipv6-bytes [s]
  (let [[head tail] (str/split (str s "|") #"::" 2)
        parse (fn [x] (if (str/blank? x) []
                          (mapv #?(:clj #(Integer/parseInt % 16) :cljs #(js/parseInt % 16))
                                (str/split x #":"))))
        h (parse head)
        t (parse (str/replace (or tail "") #"\|" ""))
        gap (- 8 (count h) (count t))
        groups (into (into (vec h) (repeat (max 0 gap) 0)) t)]
    (vec (mapcat (fn [g] [(bit-and (bit-shift-right g 8) 0xFF) (bit-and g 0xFF)]) groups))))

(defn encode-rdata
  "Canonical RDATA octets for the RR types this library signs.

  `:zone/raw` passes through verbatim, which is what makes an unsigned zone
  containing a type this library does not model still signable: RFC 4034 does
  not require a signer to *understand* an RR, only to serialize it identically
  to whoever validates it, and opaque bytes satisfy that by construction."
  [type rdata]
  (let [nm #(encode-name %)]
    (cond
      (:zone/raw rdata) (vec (:zone/raw rdata))
      :else
      (case type
        "A"     (ipv4-bytes (:zone/address rdata))
        "AAAA"  (ipv6-bytes (:zone/address rdata))
        ("CNAME" "NS" "PTR" "DNAME") (nm (:zone/target rdata))
        "MX"    (into (u16 (:zone/pref rdata)) (nm (:zone/exchange rdata)))
        "TXT"   (let [b (ascii-bytes (str (:zone/text rdata)))]
                  (into (u8 (count b)) b))
        "SOA"   (-> (vec (nm (:zone/mname rdata)))
                    (into (nm (:zone/rname rdata)))
                    (into (u32 (:zone/serial rdata)))
                    (into (u32 (:zone/refresh rdata)))
                    (into (u32 (:zone/retry rdata)))
                    (into (u32 (:zone/expire rdata)))
                    (into (u32 (:zone/minimum rdata))))
        "SRV"   (-> (vec (u16 (:zone/pri rdata)))
                    (into (u16 (:zone/weight rdata)))
                    (into (u16 (:zone/port rdata)))
                    (into (nm (:zone/target rdata))))
        "CAA"   (let [tag (ascii-bytes (:zone/tag rdata))
                      val (ascii-bytes (str (:zone/value rdata)))]
                  (-> (vec (u8 (:zone/flags rdata)))
                      (into (u8 (count tag)))
                      (into tag)
                      (into val)))
        (throw (ex-info "no canonical RDATA encoding for this type; supply :zone/raw"
                        {:type type}))))))

(def type->int
  {"A" 1 "NS" 2 "CNAME" 5 "SOA" 6 "PTR" 12 "MX" 15 "TXT" 16 "AAAA" 28 "SRV" 33
   "DS" 43 "RRSIG" 46 "NSEC" 47 "DNSKEY" 48 "NSEC3" 50 "NSEC3PARAM" 51
   "CAA" 257 "DNAME" 39})

(defn rr-type->int [t]
  (or (get type->int t)
      (when-let [[_ d] (re-matches #"TYPE(\d+)" (str t))]
        #?(:clj (Integer/parseInt d) :cljs (js/parseInt d 10)))
      (throw (ex-info "unknown RR type" {:type t}))))

(def ^:const class-in 1)

(defn encode-rr
  "Canonical RR form (RFC 4034 §6.2): canonical owner name, type, class,
  **original TTL**, rdlength, canonical RDATA.

  `original-ttl` is a required argument rather than read from the record. The
  RRSIG carries the TTL the RRset had at the authoritative server, and any
  cached copy has a smaller one — signing with the record's current TTL
  produces a signature that validates at the origin and fails everywhere else,
  which is the hardest DNSSEC failure to reproduce."
  [{:zone/keys [name type rdata]} original-ttl]
  (let [rd (encode-rdata type rdata)]
    (-> (vec (encode-name name))
        (into (u16 (rr-type->int type)))
        (into (u16 class-in))
        (into (u32 original-ttl))
        (into (u16 (count rd)))
        (into rd))))

(defn sort-rrset
  "Canonical ordering within an RRset (RFC 4034 §6.3): by RDATA as unsigned
  left-justified octets. Two servers that order an RRset differently produce
  different signed blobs from the same records."
  [records]
  (vec (sort-by #(encode-rdata (:zone/type %) (:zone/rdata %))
                compare-bytes
                records)))

(defn rrset
  "Group records into RRsets keyed by `[canonical-owner type]` — the unit a
  signature covers (RFC 4035 §2.2). Class is not part of the key because this
  library is IN-only, which the `class-in` constant says out loud."
  [records]
  (group-by (juxt #(canonical-name (:zone/name %)) :zone/type) records))

(defn hex
  "Octets as lowercase hex — for DS digests, key material in a zone file, and
  test failure output, where a one-octet difference is otherwise invisible."
  [bs]
  (apply str (map #(let [h #?(:clj (Integer/toHexString (bit-and % 0xFF))
                              :cljs (.toString (bit-and % 0xFF) 16))]
                     (if (= 1 (count h)) (str "0" h) h))
                  bs)))
