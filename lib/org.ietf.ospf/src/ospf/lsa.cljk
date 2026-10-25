(ns ospf.lsa
  "The LSA header, common to all five LSA types (RFC 2328 Appendix A.4.1),
  and the §13.1 rule for which of two instances of the same LSA is more
  recent.

  RFC 2328 Appendix A.4.1, the wire layout (20 octets):

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |            LS age             |    Options    |    LS type    |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                        Link State ID                          |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     Advertising Router                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     LS sequence number                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |         LS checksum           |             length            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  `:ls-checksum` is carried through as an opaque 16-bit value, not
  computed or verified — see the README's \"What this is not\" section.
  RFC 2328 Appendix A.4.1 defines it as 'the Fletcher checksum of the
  complete contents of the LSA, including the LSA header but excluding
  the LS age field' — a different algorithm from the RFC 1071 checksum
  `ospf.checksum` implements for the packet header, and one §12.1.7 does
  not itself specify ('It is documented in Annex B of [Ref6]'). This
  library does not implement it: half a checksum that looks load-bearing
  and silently never rejects a corrupt LSA is worse than no checksum at
  all. §12.1.7's own 'calculation of the checksum is not optional' is
  therefore a requirement this codec does not meet and does not claim to. `:ls-sequence-number` decodes as a *signed*
  32-bit integer — see `ospf.bytes` for why unsigned decoding would
  invert the newer/older comparison built on top of it."
  (:require [ospf.bytes :as b]))

(def header-length
  "The LSA header is 20 octets, RFC 2328 Appendix A.4.1."
  20)

(defn encode
  "Encode an LSA header map to its 20-octet wire form."
  [{:keys [ls-age options ls-type link-state-id advertising-router
           ls-sequence-number ls-checksum length]}]
  (vec (concat (b/u16->bytes ls-age)
               [(bit-and options 0xFF) (bit-and ls-type 0xFF)]
               (b/u32->bytes link-state-id)
               (b/u32->bytes advertising-router)
               (b/i32->bytes ls-sequence-number)
               (b/u16->bytes ls-checksum)
               (b/u16->bytes length))))

(defn decode
  "Decode a 20-octet LSA header from the front of `bs`. Returns
  `[:ok {:header <map> :rest <bytes after the header>}]` or
  `[:error :ospf/lsa-header-too-short]`."
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) header-length)
      [:error :ospf/lsa-header-too-short]
      [:ok {:header {:ls-age (b/bytes->u16 (bs 0) (bs 1))
                     :options (bs 2)
                     :ls-type (bs 3)
                     :link-state-id (b/bytes->u32 (bs 4) (bs 5) (bs 6) (bs 7))
                     :advertising-router (b/bytes->u32 (bs 8) (bs 9) (bs 10) (bs 11))
                     :ls-sequence-number (b/bytes->i32 (bs 12) (bs 13) (bs 14) (bs 15))
                     :ls-checksum (b/bytes->u16 (bs 16) (bs 17))
                     :length (b/bytes->u16 (bs 18) (bs 19))}
             :rest (subvec bs header-length)}])))

;; ── §13.1: which instance is more recent ────────────────────────────────────
;;
;; RFC 2328 Appendix B, Architectural Constants (quoted for both values,
;; since both are easy to misremember and the tie-break order depends on
;; getting them right):
;;
;;   "MaxAge: The maximum age that an LSA can attain. ... The value of
;;   MaxAge is set to 1 hour."
;;
;;   "MaxAgeDiff: The maximum time dispersion that can occur, as an LSA is
;;   flooded throughout the AS. ... The value of MaxAgeDiff is set to
;;   15 minutes."

(def max-age
  "RFC 2328 Appendix B, MaxAge: 1 hour, in the same seconds unit LS age
  is carried in."
  3600)

(def max-age-diff
  "RFC 2328 Appendix B, MaxAgeDiff: 15 minutes."
  900)

(defn- abs* [n] (if (neg? n) (- n) n))

(defn compare-instances
  "Which of two LSA-header maps (`a` and `b`, each shaped like `decode`'s
  `:header`) is the more recent instance of the same LSA, per RFC 2328
  §13.1 — quoted here verbatim because the tie-break order is the whole
  rule:

    'The LSA having the newer LS sequence number is more recent. ... If
    both instances have the same LS sequence number, then:

    If the two instances have different LS checksums, then the instance
    having the larger LS checksum (when considered as a 16-bit unsigned
    integer) is considered more recent.

    Else, if only one of the instances has its LS age field set to
    MaxAge, the instance of age MaxAge is considered to be more recent.

    Else, if the LS age fields of the two instances differ by more than
    MaxAgeDiff, the instance having the smaller (younger) LS age is
    considered to be more recent.

    Else, the two instances are considered to be identical.'

  Returns `:a`, `:b`, or `:same`. §13.1 does not itself define an
  identifier match — a caller comparing two headers for two different
  LSAs (different LS type / Link State ID / Advertising Router) is
  asking a question this function does not answer; that identity check
  is the caller's responsibility, per the section's opening sentence
  ('For two instances of the same LSA...')."
  [a b]
  (let [sa (:ls-sequence-number a) sb (:ls-sequence-number b)]
    (cond
      (> sa sb) :a
      (< sa sb) :b

      (not= (:ls-checksum a) (:ls-checksum b))
      (if (> (:ls-checksum a) (:ls-checksum b)) :a :b)

      (not= (= max-age (:ls-age a)) (= max-age (:ls-age b)))
      (if (= max-age (:ls-age a)) :a :b)

      (> (abs* (- (:ls-age a) (:ls-age b))) max-age-diff)
      (if (< (:ls-age a) (:ls-age b)) :a :b)

      :else :same)))
