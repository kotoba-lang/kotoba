(ns dnssec.sign
  "RRSIG, DNSKEY, DS and the NSEC chain — RFC 4034 / 4035, RFC 8080 for Ed25519.

  Crypto is an **injected capability**, never imported. A signer is
  `(fn [algorithm key-material octets] -> signature-octets)` and a digest is
  `(fn [algorithm octets] -> digest-octets)`, both supplied by the caller.

  This is not portability theatre. It is the same boundary
  `kotoba-lang/godaddy-dns` draws around a registrar API and for a stronger
  reason: a library that imported a signing implementation would also have to
  hold, or at least touch, the zone-signing key. Keeping the primitive outside
  means the key can live in an HSM, in `kagi`, or in a JVM `KeyStore`, and this
  code never sees it — the same discipline `cloud-itonami.dns-provider` uses to
  make 'the actor reads a secret' structurally impossible rather than merely
  discouraged.

  It also makes the *serialization* testable on its own, which is the half that
  actually breaks. A DNSSEC bug is almost never in the signature arithmetic; it
  is in which bytes got signed. With an injected signer, a test can assert on
  the exact blob without any crypto at all — see `test/dnssec/sign_test.cljc`,
  where the 'signer' returns the input.

  ## What gets signed

  RFC 4035 §5.3.2, and the order matters:

      RRSIG_RDATA (the RRSIG's own rdata, with an empty signature field)
      || RR(1) || RR(2) || …

  Each `RR(i)` is the canonical form from `dnssec.canonical`, the RRset is in
  canonical order, and the RRSIG rdata prefix includes the type covered,
  algorithm, labels, original TTL, expiration, inception, key tag and signer's
  name. Omitting that prefix — signing only the records — is a real and common
  mistake that produces signatures no validator accepts, because a validator
  reconstructs the blob from the RRSIG it received."
  (:require [kotoba.lang.text :as str]
            [dnssec.canonical :as c]))

;; ── algorithms ────────────────────────────────────────────────────────────

(def algorithms
  "DNSSEC algorithm numbers (IANA registry). Only the ones worth deploying in
  2026 are named: RSA/SHA-1 (5) and the DSA family are deprecated by RFC 8624
  and are deliberately absent, so a caller cannot pick one by autocompleting."
  {:rsasha256 8
   :rsasha512 10
   :ecdsap256sha256 13
   :ecdsap384sha384 14
   :ed25519 15                                  ; RFC 8080
   :ed448 16})

(def digests
  "DS digest types (RFC 4034 §5.1.4 and RFC 6605). SHA-1 (1) is omitted for the
  same reason."
  {:sha256 2
   :sha384 4})

(defn- algo-number [a] (if (integer? a) a (or (get algorithms a)
                                              (throw (ex-info "unknown algorithm" {:algorithm a})))))
(defn- digest-number [d] (if (integer? d) d (or (get digests d)
                                                (throw (ex-info "unknown digest" {:digest d})))))

;; ── DNSKEY ────────────────────────────────────────────────────────────────

(def ^:const flag-zone-key 256)
(def ^:const flag-secure-entry-point 257)

(defn dnskey
  "A DNSKEY record. `:ksk?` sets the Secure Entry Point bit (257 rather than
  256) — the bit that says this key is the one a DS in the parent points at.

  The KSK/ZSK split is convention, not protocol: nothing stops one key doing
  both. It exists so the key the parent has to be told about can be rotated on
  a slow, coordinated schedule while the key that signs every RRset rotates
  quickly on its own."
  [{:keys [name algorithm public-key ksk? ttl]}]
  {:zone/name (c/canonical-name name)
   :zone/type "DNSKEY"
   :zone/class "IN"
   :zone/ttl (or ttl 3600)
   :zone/rdata {:zone/raw (-> (vec (c/u16 (if ksk? flag-secure-entry-point flag-zone-key)))
                              (into (c/u8 3))          ; protocol; RFC 4034 §2.1.2 fixes it at 3
                              (into (c/u8 (algo-number algorithm)))
                              (into (vec public-key)))}})

(defn key-tag
  "RFC 4034 Appendix B — the 16-bit identifier that ties an RRSIG to a DNSKEY.

  It is a checksum, not a hash: sum the RDATA as alternating high/low octets,
  add the carry, take the low 16 bits. Two keys **can** collide, which is why a
  validator must try every DNSKEY with the matching tag rather than assuming
  the first is right.

  Appendix B.1 gives algorithm 1 (RSA/MD5) a different rule — the tag is taken
  from the last three octets. That algorithm is deprecated and unsupported
  here, so the general rule is the only one implemented, and passing algorithm
  1 is an error rather than a silently wrong tag."
  [dnskey-rdata-octets algorithm]
  (when (= 1 (algo-number algorithm))
    (throw (ex-info "algorithm 1 (RSA/MD5) uses a different key tag rule and is deprecated"
                    {:algorithm algorithm})))
  (let [bs (vec dnskey-rdata-octets)
        acc (reduce (fn [sum i]
                      (+ sum (if (even? i)
                               (bit-shift-left (bit-and (nth bs i) 0xFF) 8)
                               (bit-and (nth bs i) 0xFF))))
                    0
                    (range (count bs)))
        acc (+ acc (bit-and (bit-shift-right acc 16) 0xFFFF))]
    (bit-and acc 0xFFFF)))

(defn dnskey-tag
  "The key tag of a DNSKEY record built by `dnskey`."
  [dnskey-record algorithm]
  (key-tag (get-in dnskey-record [:zone/rdata :zone/raw]) algorithm))

;; ── DS ────────────────────────────────────────────────────────────────────

(defn ds-digest-input
  "The octets a DS digest is taken over (RFC 4034 §5.1.4):

      canonical owner name of the DNSKEY || DNSKEY RDATA

  Exposed separately from `ds` so a test can assert on it without a hash
  function, and so a caller using an HSM can hand exactly these bytes to it."
  [dnskey-record]
  (into (vec (c/encode-name (:zone/name dnskey-record)))
        (get-in dnskey-record [:zone/rdata :zone/raw])))

(defn ds
  "The DS record that goes in the **parent** zone — the single link that makes
  a signed child reachable from the root. A correctly signed zone whose DS was
  never published in the parent is, to every validator, simply unsigned.

  `digest-fn` is `(fn [digest-type octets] -> octets)`."
  [dnskey-record {:keys [algorithm digest-type digest-fn ttl]
                  :or {digest-type :sha256}}]
  (let [tag (dnskey-tag dnskey-record algorithm)
        dt (digest-number digest-type)
        d (digest-fn digest-type (ds-digest-input dnskey-record))]
    {:zone/name (:zone/name dnskey-record)
     :zone/type "DS"
     :zone/class "IN"
     :zone/ttl (or ttl 3600)
     :zone/rdata {:zone/raw (-> (vec (c/u16 tag))
                                (into (c/u8 (algo-number algorithm)))
                                (into (c/u8 dt))
                                (into (vec d)))}
     :dnssec/key-tag tag
     :dnssec/digest-type digest-type}))

;; ── RRSIG ─────────────────────────────────────────────────────────────────

(defn- label-count
  "The `labels` field of an RRSIG: the number of labels in the owner name, **not
  counting the root and not counting a leading wildcard** (RFC 4034 §3.1.3).
  A validator uses it to reconstruct the name a wildcard answer was synthesized
  from, so an off-by-one here breaks wildcard proofs specifically — everything
  else keeps validating, which is why it survives testing."
  [name]
  (let [ls (c/labels name)]
    (count (if (= "*" (first ls)) (rest ls) ls))))

(defn rrsig-rdata-prefix
  "The RRSIG RDATA **without** the signature field — the prefix that is both
  signed and later emitted (RFC 4035 §5.3.2)."
  [{:keys [type-covered algorithm name original-ttl expiration inception
           key-tag signer]}]
  (-> (vec (c/u16 (c/rr-type->int type-covered)))
      (into (c/u8 (algo-number algorithm)))
      (into (c/u8 (label-count name)))
      (into (c/u32 original-ttl))
      (into (c/u32 expiration))
      (into (c/u32 inception))
      (into (c/u16 key-tag))
      (into (c/encode-name signer))))

(defn signing-blob
  "The exact octets an RRSIG signs:

      RRSIG_RDATA (signature field empty) || RR(1) || RR(2) || …

  in canonical RRset order with the original TTL. This is the function to reach
  for when a signature will not validate: compare this blob between signer and
  validator and the disagreement is always visible in it."
  [records params]
  (into (rrsig-rdata-prefix params)
        (mapcat #(c/encode-rr % (:original-ttl params))
                (c/sort-rrset records))))

(defn rrsig
  "Sign one RRset.

  `sign-fn` is `(fn [algorithm key-material octets] -> signature-octets)`.
  `inception` and `expiration` are seconds since the epoch — RFC 4034 §3.1.5
  actually specifies 32-bit *serial* arithmetic (RFC 1982) for them, so a
  validator compares them in sequence space; that only matters after 2106 and
  is noted rather than implemented.

  The records must all share an owner and type; a caller passing a mixed set
  would get a signature covering records the RRSIG claims not to cover, so it
  is refused rather than signed."
  [records {:keys [algorithm key key-tag signer original-ttl inception expiration
                   sign-fn ttl]}]
  (when (empty? records)
    (throw (ex-info "cannot sign an empty RRset" {})))
  (let [owners (into #{} (map #(c/canonical-name (:zone/name %))) records)
        types (into #{} (map :zone/type) records)]
    (when (or (> (count owners) 1) (> (count types) 1))
      (throw (ex-info "an RRSIG covers exactly one (owner, type) RRset"
                      {:owners owners :types types})))
    (let [owner (first owners)
          type-covered (first types)
          params {:type-covered type-covered :algorithm algorithm :name owner
                  :original-ttl original-ttl :expiration expiration
                  :inception inception :key-tag key-tag :signer signer}
          blob (signing-blob records params)
          sig (sign-fn algorithm key blob)]
      {:zone/name owner
       :zone/type "RRSIG"
       :zone/class "IN"
       :zone/ttl (or ttl original-ttl)
       :zone/rdata {:zone/raw (into (rrsig-rdata-prefix params) (vec sig))}
       :dnssec/type-covered type-covered
       :dnssec/key-tag key-tag
       :dnssec/inception inception
       :dnssec/expiration expiration})))

;; ── NSEC ──────────────────────────────────────────────────────────────────

(defn type-bitmap
  "The NSEC/NSEC3 type bit maps field (RFC 4034 §4.1.2).

  Types are grouped into 256-type windows; each window is
  `[window-number, bitmap-length, bitmap…]` and **only non-empty windows are
  emitted**. Within a window the bit for type `t` is bit `t mod 256`, counted
  from the **most** significant bit of the first octet — the endianness that
  reads backwards and is the usual source of a bitmap claiming the wrong types
  exist."
  [types]
  (let [nums (sort (map c/rr-type->int types))
        windows (group-by #(quot % 256) nums)]
    (vec (mapcat
          (fn [[win ts]]
            (let [maxbit (apply max (map #(mod % 256) ts))
                  len (inc (quot maxbit 8))
                  octets (reduce (fn [acc t]
                                   (let [b (mod t 256)]
                                     (update acc (quot b 8)
                                             bit-or (bit-shift-right 0x80 (mod b 8)))))
                                 (vec (repeat len 0))
                                 ts)]
              (into [win len] octets)))
          (sort-by key windows)))))

(defn nsec
  "One NSEC record: this name, the **next** name in canonical order, and the
  types that exist here.

  NSEC proves nonexistence by exhaustion — a validator that receives the NSEC
  for the name immediately before the one it asked about, and sees the queried
  name is not covered, knows it does not exist. That is also NSEC's known cost:
  walking the chain enumerates the entire zone. A registry that considers its
  name list confidential wants NSEC3 (RFC 5155) instead, and should say so
  rather than discover it."
  [{:keys [name next-name types ttl]}]
  {:zone/name (c/canonical-name name)
   :zone/type "NSEC"
   :zone/class "IN"
   :zone/ttl (or ttl 3600)
   :zone/rdata {:zone/raw (into (vec (c/encode-name next-name))
                                (type-bitmap types))}})

(defn nsec-chain
  "Build the whole NSEC chain for a zone.

  The chain is **circular**: the last name's `next` is the apex, which is what
  lets a validator prove that a name sorting after everything in the zone does
  not exist. A chain that stops at the last name leaves that entire range
  unprovable, and queries beyond the last name fail to validate rather than
  returning a proven NXDOMAIN.

  Every NSEC also asserts `NSEC` and `RRSIG` at its own name, because those
  records exist there once the zone is signed."
  [records {:keys [apex ttl]}]
  (let [by-name (group-by #(c/canonical-name (:zone/name %)) records)
        names (c/sort-names (keys by-name))
        apex' (c/canonical-name apex)]
    (mapv (fn [[nm next-nm]]
            (nsec {:name nm
                   :next-name (or next-nm apex')
                   :types (into #{"NSEC" "RRSIG"}
                                (map :zone/type (get by-name nm)))
                   :ttl ttl}))
          (map vector names (concat (rest names) [nil])))))
